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
                 battement date de quand ? »

CE QU'IL SURVEILLE
  1. absence de battement depuis plus de `--seuil-heures` (défaut 26 h : une
     journée plus la marge d'un cycle long) ;
  2. cycle passé mais VIDE — aucun extracteur lancé alors que certains étaient
     dus. C'est le défaut exact du 2026-08-24 ;
  3. cycle passé mais STÉRILE — les extracteurs ont tourné sans rien écrire.
     C'est le défaut du 2026-08-25 (4 790 erreurs de verrou SQLite).

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


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def battement(lane: str = "?") -> dict:
    """Déposé par le cycle, à la fin. Contient de quoi juger SANS le ledger."""
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


def main() -> int:
    ap = argparse.ArgumentParser(description="Témoin de vie du cycle de scrap.")
    ap.add_argument("--battement", action="store_true",
                    help="déposer le témoin (appelé PAR le cycle, à la fin)")
    ap.add_argument("--verifier", action="store_true",
                    help="contrôler le témoin (appelé CONTRE le cycle, tâche séparée)")
    ap.add_argument("--lane", default="?")
    ap.add_argument("--seuil-heures", type=int, default=SEUIL_DEFAUT_H)
    args = ap.parse_args()

    if args.battement:
        etat = battement(args.lane)
        print(json.dumps(etat, ensure_ascii=False, indent=1))
        return 0
    if args.verifier:
        return verifier(args.seuil_heures)
    ap.error("préciser --battement ou --verifier")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
