"""pouls.py — rendre le silence impossible.

POURQUOI CE MODULE EXISTE
Les 24 et 25 août 2026, le système n'a rien scrapé deux nuits d'affilée et
**rien ne l'a signalé**. Il a fallu lire les journaux de Windows pour s'en
apercevoir. Les deux causes étaient différentes — un cycle parti sur la mauvaise
lane, puis un cycle jamais parti — mais le symptôme était le même : un silence
qui ressemble exactement à un fonctionnement normal.

Aucune des surveillances existantes ne pouvait le voir, et ce n'est pas un
oubli, c'est structurel : `watch-health` et `overseer` sont des AGENTS. Ils
tournent *dans* le cycle. Un cycle qui ne démarre pas ne les lance pas non plus.
Une surveillance qui vit à l'intérieur de ce qu'elle surveille ne peut pas
constater sa propre absence.

D'où ce module, et sa seule règle de conception : **il doit s'exécuter en dehors
du cycle**. Une tâche Windows séparée l'appelle plusieurs fois par jour ; il lit
un témoin déposé par le cycle et crie si ce témoin est trop vieux. Il ne dépend
d'aucun agent, d'aucun ledger sain, d'aucun réseau.

DEUX MODES
  --battement  : déposé PAR le cycle, à la fin. « je suis passé, voilà ce que
                 j'ai fait ».
  --verifier   : lancé CONTRE le cycle, par sa propre tâche. « le dernier
                 battement date de quand ? », ET « le cycle en cours dure
                 depuis quand ? » (voir point 4).

CE QU'IL SURVEILLE
  1. absence de battement depuis plus de `--seuil-heures` (défaut 26 h : une
     journée plus la marge d'un cycle long) ;
  2. cycle passé mais VIDE — aucun extracteur lancé alors que certains étaient
     dus. C'est le défaut exact du 2026-08-24 ;
  3. cycle passé mais STÉRILE — les extracteurs ont tourné sans rien écrire.
     C'est le défaut du 2026-08-25 (4 790 erreurs de verrou SQLite).
  4. cycle EN COURS depuis plus de `--seuil-cycle-long-heures` (défaut 16 h).
     Ajouté le 2026-08-28 : `LowiBKK-Agents` a perdu son `ExecutionTimeLimit`
     (10 h, tuait l'orchestrateur au milieu de `remonter-supabase` 3 nuits de
     suite — agents/audits/reparations-2026-08-2{7,8}.md) au profit d'un
     lot batché (~10x plus rapide) et de CE signal : un cycle qui ne finit
     toujours pas après 16 h alerte au lieu de tourner indéfiniment sans que
     personne ne le sache. Contrairement aux 3 points ci-dessus (lus depuis
     `pouls.json`, déposé APRÈS coup), celui-ci lit le ledger — seule source
     qui connaît un cycle EN COURS. C'est une dépendance assumée : si le
     ledger est illisible pendant un cycle en cours, ce point-là se tait
     (les 3 premiers, eux, restent indépendants de tout).

Il ne crie qu'UNE FOIS PAR JOUR pour un même motif : une alerte répétée toutes
les trois heures est une alerte qu'on apprend à ignorer (règle 2).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Lancé à la main dans une console cp1252 (ACP par défaut sur ce poste), les
# caractères ⚠/✓/✗ plantent en UnicodeEncodeError avant même d'afficher
# l'alerte. Connu depuis le 2026-08-22 (journal technique) pour tout script
# `ops/` lancé hors sous-processus — agents/core/shell.py force déjà l'UTF-8
# pour les ENFANTS, rien ne le faisait pour un lancement direct.
for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.core import alert, escalation          # noqa: E402
from agents.core.metrics import aplatir            # noqa: E402

POULS = ROOT / "agents" / "state" / "pouls.json"
DEJA_CRIE = ROOT / "agents" / "state" / "pouls-alertes.json"
LEDGER = ROOT / "agents" / "ledger.db"

#: 26 h : un cycle quotidien plus deux heures de marge. En dessous, un cycle
#: long (le recensement DDproperty dure 1 h 35) déclencherait une fausse alerte.
SEUIL_DEFAUT_H = 26

#: 16 h : au-delà, un cycle démarré à 01:00 tourne encore après 17:00 — plus
#: aucune marge raisonnable, même pour la nuit la plus lente mesurée à ce jour
#: (~11h35 le 2026-08-26). Choisi par l'utilisateur le 2026-08-28 en
#: contrepartie du retrait de l'`ExecutionTimeLimit` de `LowiBKK-Agents`.
SEUIL_CYCLE_LONG_DEFAUT_H = 16


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def battement(lane: str = "?", extraction_tentee: bool = True) -> dict:
    """Déposé par le cycle, à la fin. Contient de quoi juger SANS le ledger.

    `extraction_tentee=False` : cette invocation n'a délibérément pas touché à
    l'extraction (`--boot`, `run-lane --skip-extraction`, ou `run <agent>` sur
    un agent qui n'est pas un extracteur). Mesuré le 2026-09-09 : un
    rattrapage au logon (PC2) a relancé `garde-veille` seul, 16 h 48 après le
    début du cycle réel (extraction 18:12 → 01:12, `docs/journal-technique.md`
    du 09/09) ; la fenêtre de calcul (« dernières 12 h ») ne voyait plus les
    extracteurs de la veille, pourtant réussis à 4/5, et a redéposé
    `extracteurs_lances: 0` — `cycle_vide` a crié à tort
    (ticket `2026-09-09T130002-pouls-cycle_vide.json`). Une invocation qui ne
    pouvait de toute façon pas produire d'extraction ne doit pas écraser le
    dernier constat réel : elle reconduit le témoin précédent sur ces champs."""
    if not extraction_tentee:
        etat = {"termine_a": _maintenant().isoformat(), "lane": lane,
                 "extraction_sautee_ici": True}
        precedent = {}
        try:
            precedent = json.loads(POULS.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
        for cle in ("agents_lances", "extracteurs_lances", "extracteurs_ok",
                    "annonces_ecrites"):
            if cle in precedent:
                etat[cle] = precedent[cle]
        POULS.parent.mkdir(parents=True, exist_ok=True)
        POULS.write_text(json.dumps(etat, ensure_ascii=False, indent=1),
                          encoding="utf-8")
        return etat

    etat = {"termine_a": _maintenant().isoformat(), "lane": lane}
    try:
        cx = sqlite3.connect(f"file:{LEDGER}?mode=ro", uri=True)
        cx.row_factory = sqlite3.Row
        depuis = (_maintenant() - timedelta(hours=12)).isoformat()
        runs = cx.execute(
            "select agent, status, metrics from agent_runs where started_at >= ?",
            (depuis,)).fetchall()
        cx.close()
        extracteurs = [r for r in runs if r["agent"].startswith("extract-")]
        ecrites = 0
        for r in extracteurs:
            try:
                m = aplatir(json.loads(r["metrics"] or "{}"))
            except (json.JSONDecodeError, TypeError):
                continue
            ecrites += (m.get("nouvelles") or 0) + (m.get("changees") or 0)
        etat.update({
            "agents_lances": len(runs),
            "extracteurs_lances": len(extracteurs),
            "extracteurs_ok": sum(1 for r in extracteurs if r["status"] == "ok"),
            "annonces_ecrites": ecrites,
        })
    except sqlite3.Error as e:
        # Le battement doit être déposé MÊME si le ledger est illisible : c'est
        # justement le cas où on a besoin de savoir que le cycle est passé.
        etat["ledger_illisible"] = str(e)[:200]

    POULS.parent.mkdir(parents=True, exist_ok=True)
    POULS.write_text(json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8")
    return etat


def _deja_crie_aujourdhui(motif: str) -> bool:
    """Une alerte par motif et par jour. Répéter n'informe pas, ça anesthésie."""
    jour = _maintenant().strftime("%Y-%m-%d")
    try:
        hist = json.loads(DEJA_CRIE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        hist = {}
    if hist.get(motif) == jour:
        return True
    hist[motif] = jour
    DEJA_CRIE.parent.mkdir(parents=True, exist_ok=True)
    DEJA_CRIE.write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")
    return False


def _crier(motif: str, sujet: str, corps: str, preuves: dict) -> None:
    if _deja_crie_aujourdhui(motif):
        print(f"  (déjà signalé aujourd'hui : {motif})")
        return
    escalation.create(
        agent="pouls", kind=motif, severity="high", subject=sujet,
        evidence=preuves,
        asked_of_claude=(
            "Le cycle de nuit n'a pas produit ce qu'il devait. Diagnostiquer "
            "SANS supposer que l'orchestrateur a tourné : vérifier d'abord la "
            "tâche Windows LowiBKK-Agents (dernier déclenchement, code retour), "
            "puis les journaux Windows (Kernel-Power 42/107, powercfg /lastwake), "
            "puis seulement le ledger. Corriger SUR UNE BRANCHE."))
    alert.alert("pouls", sujet, corps)
    print(f"  ⚠ ALERTE : {sujet}")


def verifier(seuil_h: int) -> int:
    """Rend 0 si tout va bien, 1 si une alerte a été levée."""
    maintenant = _maintenant()

    if not POULS.exists():
        _crier("pouls_absent", "Aucun cycle n'a jamais déposé de battement",
               f"Le témoin {POULS} n'existe pas. Soit le cycle n'a jamais tourné "
               f"depuis la mise en place, soit il ne va jamais jusqu'au bout.",
               {"temoin": str(POULS)})
        return 1

    etat = json.loads(POULS.read_text(encoding="utf-8"))
    fin = datetime.fromisoformat(etat["termine_a"])
    age_h = (maintenant - fin).total_seconds() / 3600

    if age_h > seuil_h:
        _crier("cycle_manquant",
               f"Aucun cycle depuis {age_h:.0f} h (seuil {seuil_h} h)",
               f"Dernier cycle terminé le {fin.astimezone():%d/%m à %H:%M}.\n"
               f"Le scrap quotidien ne tourne plus. Vérifier la tâche Windows "
               f"LowiBKK-Agents avant toute autre piste.",
               {"dernier_cycle": etat["termine_a"], "age_heures": round(age_h, 1),
                "seuil_heures": seuil_h, "dernier_etat": etat})
        return 1

    # Un cycle passé ne suffit pas : il faut qu'il ait fait quelque chose.
    if etat.get("extracteurs_lances", 0) == 0:
        _crier("cycle_vide",
               "Le dernier cycle n'a lancé AUCUN extracteur",
               f"Cycle terminé le {fin.astimezone():%d/%m à %H:%M}, lane "
               f"« {etat.get('lane')} », {etat.get('agents_lances')} agents lancés, "
               f"zéro extracteur. C'est le défaut du 2026-08-24 (lane hebdomadaire "
               f"qui remplaçait la quotidienne).",
               {"etat": etat})
        return 1

    if etat.get("extracteurs_lances", 0) and not etat.get("annonces_ecrites"):
        _crier("cycle_sterile",
               "Les extracteurs ont tourné sans rien écrire",
               f"{etat.get('extracteurs_lances')} extracteurs lancés, zéro annonce "
               f"écrite. C'est le défaut du 2026-08-25 (verrous SQLite) : le scan "
               f"a lieu, mais rien n'arrive en base.",
               {"etat": etat})
        return 1

    print(f"  ✓ dernier cycle il y a {age_h:.1f} h — "
          f"{etat.get('extracteurs_lances')} extracteurs, "
          f"{etat.get('annonces_ecrites')} annonces écrites")
    return 0


def _demarrage_processus(pid: int) -> datetime | None:
    """Date de création du processus `pid`, ou None si indéterminable.

    Windows RECYCLE les PID, et le ledger en garde la trace pour toujours :
    mesuré le 2026-09-09, le PID 26632 portait à la fois `garde-veille` du
    2026-08-31T18:00:21 et le cycle du 2026-09-08T18:12:13. Un `min(started_at)`
    par PID remontait donc huit jours en arrière et annonçait « cycle en cours
    depuis 199 h » alors que le cycle avait 14 h et tournait normalement — deux
    tickets de sévérité haute ouverts pour rien (règle 2).

    La date de création tranche : une ligne antérieure au démarrage du processus
    appartient forcément à un homonyme, pas à ce cycle.
    """
    try:
        import ctypes
        from ctypes import wintypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not h:
            return None
        creation = wintypes.FILETIME()
        autres = [wintypes.FILETIME() for _ in range(3)]
        ok = kernel32.GetProcessTimes(h, ctypes.byref(creation),
                                      *[ctypes.byref(f) for f in autres])
        kernel32.CloseHandle(h)
        if not ok:
            return None
        # FILETIME : intervalles de 100 ns depuis le 1601-01-01 UTC.
        ticks = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        return datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=ticks / 10)
    except Exception:                                    # noqa: BLE001
        return None


def _cycle_en_cours() -> dict | None:
    """Le cycle actuellement EN COURS, s'il y en a un — lu dans le ledger.

    Repère : au moins une ligne `agent_runs` `status='running'`. Son début
    n'est PAS le `started_at` de cette ligne (ce serait le début de CET
    agent, pas du cycle) : toutes les lignes d'un même lancement de
    l'orchestrateur partagent le même `pid` (vérifié le 2026-08-28) — le
    début du cycle est le plus ancien `started_at` de ce `pid`, **parmi les
    lignes postérieures au démarrage de ce processus** (cf.
    `_demarrage_processus` : sans ce filtre, un PID recyclé fait remonter le
    début du cycle à celui d'un homonyme mort depuis des jours).

    Quand la date de démarrage est indéterminable (processus déjà terminé,
    accès refusé), on se replie sur le `started_at` de l'agent bloqué : c'est
    une borne basse honnête — elle peut sous-estimer la durée du cycle, jamais
    inventer un cycle de 199 h.
    """
    try:
        cx = sqlite3.connect(f"file:{LEDGER}?mode=ro", uri=True)
        cx.row_factory = sqlite3.Row
        bloque = cx.execute(
            "select agent, pid, started_at from agent_runs where status='running' "
            "order by started_at limit 1").fetchone()
        if not bloque or bloque["pid"] is None:
            cx.close()
            return None
        ne = _demarrage_processus(bloque["pid"])
        plancher = ne.isoformat() if ne else bloque["started_at"]
        debut = cx.execute(
            "select min(started_at) from agent_runs where pid=? and started_at >= ?",
            (bloque["pid"], plancher)).fetchone()[0] or bloque["started_at"]
        finis = cx.execute(
            "select count(*) from agent_runs where pid=? and started_at >= ? "
            "and status<>'running'", (bloque["pid"], plancher)).fetchone()[0]
        cx.close()
        return {"agent_bloque": bloque["agent"], "debut": debut, "agents_finis": finis}
    except sqlite3.Error:
        return None


def verifier_cycle_long(seuil_h: int) -> int:
    """Alerte si un cycle est EN COURS depuis plus de `seuil_h`.

    Distinct de `verifier()` : celui-ci porte sur un cycle qui vient de finir
    (ou de ne jamais démarrer), celui-ci sur un cycle qui n'a PAS FINI. Les
    deux sont complémentaires, pas redondants — voir le docstring du module.
    """
    info = _cycle_en_cours()
    if info is None:
        return 0
    debut = datetime.fromisoformat(info["debut"])
    duree_h = (_maintenant() - debut).total_seconds() / 3600
    if duree_h <= seuil_h:
        return 0
    _crier(
        "cycle_long",
        f"Cycle en cours depuis {duree_h:.0f} h (seuil {seuil_h} h) — "
        f"bloqué sur {info['agent_bloque']}",
        f"Le cycle démarré le {debut.astimezone():%d/%m à %H:%M} n'est toujours "
        f"pas terminé {duree_h:.1f} h plus tard. {info['agents_finis']} agent(s) "
        f"déjà terminé(s) cette nuit, actuellement bloqué sur « "
        f"{info['agent_bloque']} ». Vérifier `agents.orchestrator status` et le "
        f"log de cet agent avant toute autre piste.",
        {"debut": info["debut"], "duree_heures": round(duree_h, 1),
         "seuil_heures": seuil_h, "agent_bloque": info["agent_bloque"],
         "agents_finis": info["agents_finis"]},
    )
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Témoin de vie du cycle de scrap.")
    ap.add_argument("--battement", action="store_true",
                    help="déposer le témoin (appelé PAR le cycle, à la fin)")
    ap.add_argument("--verifier", action="store_true",
                    help="contrôler le témoin (appelé CONTRE le cycle, tâche séparée)")
    ap.add_argument("--lane", default="?")
    ap.add_argument("--seuil-heures", type=int, default=SEUIL_DEFAUT_H)
    ap.add_argument("--seuil-cycle-long-heures", type=int,
                    default=SEUIL_CYCLE_LONG_DEFAUT_H,
                    help="alerte si un cycle EN COURS dépasse ce nombre d'heures "
                         "(defaut 16 — contrepartie du retrait de "
                         "l'ExecutionTimeLimit de LowiBKK-Agents le 2026-08-28)")
    args = ap.parse_args()

    if args.battement:
        etat = battement(args.lane)
        print(json.dumps(etat, ensure_ascii=False, indent=1))
        return 0
    if args.verifier:
        r1 = verifier(args.seuil_heures)
        r2 = verifier_cycle_long(args.seuil_cycle_long_heures)
        return 1 if (r1 or r2) else 0
    ap.error("préciser --battement ou --verifier")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
