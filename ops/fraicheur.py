"""fraicheur.py — le stock actif doit être RÉELLEMENT confirmé, pas seulement marqué actif.

POURQUOI CE MODULE EXISTE
Mesuré le 2026-09-09. `recense.py` rafraîchissait `last_seen` des annonces vues
au catalogue — sauf qu'il sautait ce rafraîchissement dès que le parcours avait
le moindre trou, et il en a un à chaque run (1 à 6 pages sur ~2 600). Résultat au
moment du constat :

    ddproperty     69 149 actives    9,6 % confirmées < 48 h   (plus ancienne : 23/07)
    fazwaz         10 997 actives   60,1 %
    nestopa         3 287 actives   19,4 %
    propertyscout   1 385 actives   89,2 %
    livinginsider     509 actives  100,0 %

Autrement dit : 8,9 % des actives n'avaient pas été revues depuis plus de 30
jours, et `missed_count` ne dépassait jamais 1 — le délai de grâce ne tournait
même pas. Le stock « actif » enflait sans que rien ne le confirme.

**Et RIEN ne le signalait.** `recense.py` rend `code 0` même quand il s'abstient
(à raison : une abstention n'est pas une panne). Son abstention se lit dans
`flux_non_conclusifs`, que personne ne lisait. Panne parfaitement muette pendant
des semaines — exactement le mode de défaillance que le projet cherche à
éliminer.

CE QU'IL SURVEILLE, et pourquoi ces deux-là seulement
  1. **Le mécanisme est mort** — un recensement qui a lu des pages et rafraîchi
     ZÉRO annonce. Ce n'est pas un seuil, c'est un binaire : l'outil a tourné et
     n'a rien fait. C'est le défaut du 2026-09-09, mot pour mot.
  2. **La fraîcheur s'effondre** — la part d'actives confirmées < 48 h tombe très
     en dessous de ce que CETTE source relève d'habitude. Le repère est la
     MÉDIANE DE SON PROPRE HISTORIQUE, pas une valeur écrite en dur : les sources
     n'ont pas les mêmes cadences (nestopa est gelée à une page par conception,
     elle plafonnera toujours bas — un seuil commun crierait au loup sur elle
     chaque nuit, règle 2).

CE QU'IL NE FAIT PAS, délibérément : aucun seuil absolu de fraîcheur. Il en
faudrait un par source, et le fixer aujourd'hui reviendrait à graver l'état
ACTUEL — qui est cassé — comme référence. Le garde-fou se tait donc tant qu'il
n'a pas `MIN_HISTORIQUE` relevés sains derrière lui, plutôt que de juger sur du
vide.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Même raison que dans ops/pouls.py : lancé à la main dans une console cp1252,
# les caractères ⚠/✓ plantent en UnicodeEncodeError avant même d'afficher l'alerte.
for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.core import alert, escalation          # noqa: E402
from agents.core.metrics import aplatir            # noqa: E402

BASE = ROOT / "scraper" / "output" / "bangkok.db"
LEDGER = ROOT / "agents" / "ledger.db"
HISTORIQUE = ROOT / "agents" / "state" / "fraicheur.jsonl"
DEJA_CRIE = ROOT / "agents" / "state" / "fraicheur-alertes.json"

#: 48 h : tous les extracteurs sont en `every_days: 1`. Une annonce vivante doit
#: donc être revue chaque nuit ; 48 h laisse la marge d'un cycle manqué sans
#: crier pour autant.
FENETRE_H = 48

#: 4 relevés : de quoi avoir une médiane qui veut dire quelque chose. En dessous,
#: le garde-fou se TAIT sur la dérive — juger une tendance sur deux points, c'est
#: la meilleure façon de crier au loup (règle 2).
MIN_HISTORIQUE = 4

#: 0,5 = « largement différente de ce qu'elle relève au quotidien ». Une source
#: qui tombe sous la MOITIÉ de sa propre médiane a un problème, quelle que soit
#: sa cadence habituelle. Volontairement large : on cherche l'effondrement (le
#: 2026-09-09, ddproperty était à 9,6 % pour une médiane attendue bien plus
#: haute), pas la fluctuation d'une nuit un peu courte.
CHUTE_ALERTE = 0.5

#: 30 relevés gardés : un mois de recul, assez pour une médiane stable sans
#: laisser le fichier grossir indéfiniment.
GARDE_RELEVES = 30


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def mesurer() -> dict:
    """Relevé du jour : par source, la part d'actives confirmées récemment."""
    seuil = (_maintenant() - timedelta(hours=FENETRE_H)).isoformat()
    releve = {"mesure_a": _maintenant().isoformat(timespec="seconds"),
              "fenetre_h": FENETRE_H, "sources": {}}
    cx = sqlite3.connect(f"file:{BASE}?mode=ro", uri=True, timeout=60)
    try:
        for source, actives, frais in cx.execute(
                "select source, count(*), "
                "sum(case when last_seen >= ? then 1 else 0 end) "
                "from listings where status='active' group by source", (seuil,)):
            releve["sources"][source] = {
                "actives": actives, "frais": frais or 0,
                "pct": round(100 * (frais or 0) / actives, 1) if actives else 0.0}
    finally:
        cx.close()
    return releve


def _recensements_muets() -> list[dict]:
    """Recensements qui ont LU des pages et rafraîchi ZÉRO annonce.

    C'est le défaut du 2026-09-09 pris à la source. `rafraichies` n'apparaît
    dans les métriques que depuis le correctif du même jour : une exécution
    antérieure ne porte pas la clé, et on ne juge pas ce qu'on ne mesure pas —
    ces runs-là sont simplement ignorés.
    """
    muets = []
    try:
        cx = sqlite3.connect(f"file:{LEDGER}?mode=ro", uri=True)
        cx.row_factory = sqlite3.Row
        depuis = (_maintenant() - timedelta(hours=36)).isoformat()
        for r in cx.execute(
                "select agent, metrics from agent_runs where agent like 'extract-%' "
                "and started_at >= ? and status <> 'running'", (depuis,)):
            try:
                m = aplatir(json.loads(r["metrics"] or "{}"))
            except (json.JSONDecodeError, TypeError):
                continue
            if "rafraichies" not in m:
                continue                      # pas de recensement, ou run d'avant le correctif
            if (m.get("pages_lues") or 0) > 0 and not m.get("rafraichies"):
                muets.append({"agent": r["agent"],
                              "pages_lues": m.get("pages_lues"),
                              "rafraichies": m.get("rafraichies")})
        cx.close()
    except sqlite3.Error:
        pass                                  # le ledger n'est pas indispensable ici
    return muets


def _historique() -> list[dict]:
    if not HISTORIQUE.exists():
        return []
    releves = []
    for ligne in HISTORIQUE.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if ligne:
            try:
                releves.append(json.loads(ligne))
            except json.JSONDecodeError:
                continue
    return releves


def _ajouter(releve: dict) -> None:
    HISTORIQUE.parent.mkdir(parents=True, exist_ok=True)
    releves = (_historique() + [releve])[-GARDE_RELEVES:]
    HISTORIQUE.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in releves),
        encoding="utf-8")


def _mediane(valeurs: list[float]) -> float:
    v = sorted(valeurs)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def _deja_crie_aujourdhui(motif: str) -> bool:
    """Une alerte par motif et par jour — répéter n'informe pas, ça anesthésie."""
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
        agent="fraicheur", kind=motif, severity="high", subject=sujet,
        evidence=preuves,
        asked_of_claude=(
            "Le stock actif n'est plus confirmé par les scans. Vérifier D'ABORD "
            "que le recensement rafraîchit bien `last_seen` (metrique "
            "`rafraichies` du dernier run extract-*, et scraper/recense.py : le "
            "rafraîchissement doit précéder les abstentions du parcours troué), "
            "PUIS la couverture du scan de la source. Corriger SUR UNE BRANCHE."))
    alert.alert("fraicheur", sujet, corps)
    print(f"  ⚠ ALERTE : {sujet}")


def verifier(chute: float = CHUTE_ALERTE) -> int:
    """Rend 0 si tout va bien, 1 si une alerte a été levée."""
    releve = mesurer()
    passe = _historique()
    alertes = 0

    # ── 1. le mécanisme a-t-il seulement fait quelque chose ? ──────────────
    muets = _recensements_muets()
    if muets:
        detail = ", ".join(f"{m['agent']} ({m['pages_lues']} pages lues, "
                           f"0 rafraîchie)" for m in muets)
        _crier("rafraichissement_mort",
               f"Recensement sans effet : {detail}",
               f"Un recensement a parcouru le catalogue et n'a rafraîchi AUCUNE "
               f"annonce. C'est le défaut du 2026-09-09 : le rafraîchissement de "
               f"`last_seen` était sauté dès que le parcours avait un trou, et il "
               f"en a un à chaque run.\n\n{detail}",
               {"muets": muets})
        alertes = 1

    # ── 2. la fraîcheur s'est-elle effondrée ? ─────────────────────────────
    if len(passe) < MIN_HISTORIQUE:
        print(f"  · dérive non jugée — {len(passe)} relevé(s) sur "
              f"{MIN_HISTORIQUE} requis (le garde-fou se tait plutôt que de "
              f"juger sur du vide)")
    else:
        for source, cour in releve["sources"].items():
            anciens = [r["sources"][source]["pct"] for r in passe
                       if source in r.get("sources", {})]
            if len(anciens) < MIN_HISTORIQUE:
                continue
            med = _mediane(anciens)
            if med <= 0:
                continue
            if cour["pct"] < med * chute:
                _crier(
                    f"fraicheur_effondree_{source}",
                    f"{source} : {cour['pct']} % d'actives confirmées < {FENETRE_H} h "
                    f"(médiane habituelle {med:.1f} %)",
                    f"{source} tient {cour['actives']} annonces pour actives, mais "
                    f"seules {cour['frais']} ({cour['pct']} %) ont été confirmées "
                    f"depuis moins de {FENETRE_H} h. Sa médiane sur les "
                    f"{len(anciens)} derniers relevés est de {med:.1f} %.\n"
                    f"Un stock 'actif' que plus rien ne confirme gonfle en silence : "
                    f"le délai de grâce ne tourne pas et les statistiques portent "
                    f"sur des annonces peut-être mortes.",
                    {"source": source, "pct": cour["pct"], "mediane": med,
                     "seuil_chute": chute, "releves": len(anciens),
                     "actives": cour["actives"], "frais": cour["frais"]})
                alertes = 1

    _ajouter(releve)

    if not alertes:
        detail = "  ".join(f"{s} {d['pct']}%" for s, d in
                           sorted(releve["sources"].items(),
                                  key=lambda kv: -kv[1]["actives"]))
        print(f"  ✓ fraîcheur < {FENETRE_H} h — {detail}")
    return 1 if alertes else 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Surveille que le stock actif est réellement confirmé.")
    ap.add_argument("--mesurer", action="store_true",
                    help="relever sans juger (affiche et enregistre)")
    ap.add_argument("--verifier", action="store_true",
                    help="relever ET juger (appelé par le cycle)")
    ap.add_argument("--chute", type=float, default=CHUTE_ALERTE,
                    help=f"part de la médiane sous laquelle on alerte "
                         f"(défaut {CHUTE_ALERTE})")
    args = ap.parse_args()

    if args.mesurer:
        releve = mesurer()
        _ajouter(releve)
        print(json.dumps(releve, ensure_ascii=False, indent=1))
        return 0
    if args.verifier:
        return verifier(args.chute)
    ap.error("préciser --mesurer ou --verifier")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
