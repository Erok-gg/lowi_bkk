"""test_pouls_battement_sans_extraction.py — un rattrapage isolé ne doit pas
effacer le témoin d'un vrai cycle d'extraction.

POURQUOI CE TEST EXISTE
Mesuré le 2026-09-09 (ticket `2026-09-09T130002-pouls-cycle_vide.json`). Le
cycle réel avait tourné 18:12 -> 01:12 (4 extracteurs ok sur 5, cf.
`docs/journal-technique.md` du 09/09). À 11:00, un rattrapage au logon
(`LowiBKK-RattrapageBoot`, PC2) a relancé `garde-veille` — le seul agent
`always_run`, rien d'autre n'était dû puisque le cycle de nuit avait déjà tout
fait. `battement()` recalculait alors `extracteurs_lances` sur les
« dernières 12 h » : à 16 h 48 du début réel de l'extraction, la fenêtre ne la
voyait plus, et le témoin a été réécrit à `extracteurs_lances: 0`.
`ops/pouls.py --verifier` a lu ce témoin et crié `cycle_vide` pour un cycle
qui avait pourtant tourné le jour même.

Le correctif : `battement(extraction_tentee=False)` — posé par l'appelant
(`agents/orchestrator.py`) pour `--boot`, `run-lane --skip-extraction`, et
`run <agent>` sur un agent qui n'est pas un extracteur — ne touche PAS aux
champs d'extraction du témoin, il reconduit ceux déjà en place.

Ce que ce test vérifie :
  1. un battement `extraction_tentee=False` reconduit tel quel le compte
     d'extracteurs déjà déposé par le vrai cycle ;
  2. `verifier()` ne crie donc PAS `cycle_vide` après ce battement ;
  3. un battement `extraction_tentee=True` continue, lui, à recalculer
     depuis le ledger (aucune régression sur le chemin normal).

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_pouls_battement_sans_extraction.py
"""
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

import ops.pouls as pouls                                # noqa: E402

MAINTENANT = datetime.now(timezone.utc)
# L'écart mesuré le 2026-09-09 : extraction démarrée 16 h 48 avant le
# rattrapage isolé, largement au-delà de la fenêtre de 12 h de battement().
DEBUT_EXTRACTION = (MAINTENANT - timedelta(hours=16, minutes=48)).isoformat()


def _ledger_factice(chemin: str) -> None:
    cx = sqlite3.connect(chemin)
    cx.execute("""create table agent_runs (
        id integer primary key autoincrement, agent text not null,
        tier text, lane text, started_at text not null, ended_at text,
        status text not null, exit_code integer, metrics text,
        log_path text, pid integer)""")
    lignes = [
        ("extract-fazwaz", DEBUT_EXTRACTION, "ok", '{"nouvelles": 120, "changees": 30}'),
        ("extract-ddproperty", DEBUT_EXTRACTION, "ok", '{"nouvelles": 400, "changees": 50}'),
        ("extract-propertyscout", DEBUT_EXTRACTION, "ok", '{"nouvelles": 10, "changees": 2}'),
        ("extract-nestopa", DEBUT_EXTRACTION, "ok", '{"nouvelles": 5, "changees": 1}'),
        ("extract-livinginsider", DEBUT_EXTRACTION, "ok", '{"nouvelles": 8, "changees": 0}'),
    ]
    cx.executemany(
        "insert into agent_runs(agent,started_at,status,metrics,tier) "
        "values(?,?,?,?,'T0')", lignes)
    cx.commit()
    cx.close()


def _a_l_instant(quand, appel):
    """Simule l'horloge murale au moment de l'appel — l'incident dépend de
    l'écart entre la fin réelle du cycle et le rattrapage, pas de la date du
    jour où ce test tourne."""
    vrai = pouls._maintenant
    pouls._maintenant = lambda: quand
    try:
        return appel()
    finally:
        pouls._maintenant = vrai


dossier = tempfile.mkdtemp()
faux = os.path.join(dossier, "ledger.db")
_ledger_factice(faux)
pouls.LEDGER = faux
pouls.POULS = pouls.Path(dossier) / "pouls.json"
pouls.DEJA_CRIE = pouls.Path(dossier) / "pouls-alertes.json"

# ─────────────────────────────── 1. le vrai cycle dépose un témoin sain
#     Battement posé À LA FIN du cycle réel (7 h après son début), bien avant
#     que 12 h ne se soient écoulées.
FIN_CYCLE_REEL = datetime.fromisoformat(DEBUT_EXTRACTION) + timedelta(hours=7)
etat_reel = _a_l_instant(
    FIN_CYCLE_REEL, lambda: pouls.battement("daily", extraction_tentee=True))
assert etat_reel["extracteurs_lances"] == 5, (
    f"le vrai cycle doit voir ses 5 extracteurs : {etat_reel}")
assert etat_reel["annonces_ecrites"] == 120 + 30 + 400 + 50 + 10 + 2 + 5 + 1 + 8, \
    f"annonces_ecrites mal recalculé : {etat_reel}"
print(f"1. battement du vrai cycle -> {etat_reel['extracteurs_lances']} extracteurs : OK")

# ─────────────────────────────── 2. le rattrapage isolé ne l'efface pas
etat_rattrapage = pouls.battement("daily", extraction_tentee=False)
assert etat_rattrapage["extracteurs_lances"] == 5, (
    f"un rattrapage sans extraction NE DOIT PAS effacer le compte du vrai "
    f"cycle : {etat_rattrapage}")
assert etat_rattrapage.get("extraction_sautee_ici") is True
print("2. rattrapage isole (garde-veille seul) -> compte du vrai cycle reconduit : OK")

# ─────────────────────────────── 3. verifier() ne crie pas cycle_vide
cris = []
vrai_crier = pouls._crier
pouls._crier = lambda motif, sujet, corps, preuves: cris.append(motif)
try:
    code = pouls.verifier(pouls.SEUIL_DEFAUT_H)
finally:
    pouls._crier = vrai_crier

assert code == 0 and not cris, (
    f"cycle_vide n'aurait jamais du crier ici (regression du 2026-09-09) : {cris}")
print("3. verifier() apres rattrapage isole -> aucune alerte cycle_vide : OK")

# ─────────────────────────────── 4. un vrai cycle vide continue d'alerter
#     (le correctif ne doit pas rendre la surveillance muette, règle 2)
# Ledger factice vidé : plus aucun extracteur dans les 12 dernieres heures.
cx = sqlite3.connect(faux)
cx.execute("delete from agent_runs")
cx.commit()
cx.close()
etat_vide = pouls.battement("daily", extraction_tentee=True)
assert etat_vide["extracteurs_lances"] == 0

cris = []
pouls._crier = lambda motif, sujet, corps, preuves: cris.append(motif)
try:
    code = pouls.verifier(pouls.SEUIL_DEFAUT_H)
finally:
    pouls._crier = vrai_crier
assert code == 1 and cris == ["cycle_vide"], (
    f"un VRAI cycle vide doit toujours alerter : {cris}")
print("4. vrai cycle vide (extraction tentee, 0 extracteur) -> alerte levee : OK")

print("\nTOUS LES ESSAIS PASSENT")
