"""test_pouls_cycle_long.py — un cycle long n'est pas un cycle vide.

POURQUOI CE TEST EXISTE
Mesuré le 2026-10-01 (ticket `2026-10-01T010003-pouls-cycle_vide.json`). Le
cycle du 30/09 a duré 21 h 30 : démarré à 08:07, suspendu 14 h 24 par une
veille prolongée (capot fermé à 10:12), terminé à 05:37. Ses 4 extracteurs
étaient tous `ok` (runs #641-#644 du ledger). Mais `battement()` comptait les
extracteurs sur une fenêtre fixe de 12 h, et ils avaient démarré 21 h 30 plus
tôt. Le témoin a donc été écrit avec `extracteurs_lances: 0`, et
`cycle_vide` a crié à tort, mail compris (règle 2).

Le correctif : l'orchestrateur passe son PID, et le cycle se compte comme
l'ensemble des runs de CE processus (`start_run` y inscrit `os.getpid()`)
depuis sa création. Un homonyme laissé par un PID recyclé est donc exclu.

Ce que ce test vérifie :
  1. cycle de 21 h 30, avec le PID → 4 extracteurs, annonces recomptées ;
  2. un run plus ancien portant le même PID (recyclé) est exclu ;
  3. `verifier()` ne crie pas `cycle_vide` après ce battement ;
  4. sans PID → ancienne fenêtre de 12 h (0 extracteur ici), et un vrai cycle
     vide alerte toujours ;
  5. réel : `_demarrage_processus(os.getpid())` répond dans le processus
     courant, ce dont dépend la production.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_pouls_cycle_long.py
N'utilise NI ledger.db NI le vrai pouls.json : tout dans un dossier temporaire.
"""
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

import ops.pouls as pouls                                # noqa: E402

MAINTENANT = datetime.now(timezone.utc)
PID = 16436                                              # PID réel du 30/09
CREATION = MAINTENANT - timedelta(hours=21, minutes=36)
DEBUT = (MAINTENANT - timedelta(hours=21, minutes=30)).isoformat()
FIN = (MAINTENANT - timedelta(minutes=5)).isoformat()
HOMONYME = (MAINTENANT - timedelta(days=8)).isoformat()

dossier = tempfile.mkdtemp()
faux = os.path.join(dossier, "ledger.db")
cx = sqlite3.connect(faux)
cx.execute("""create table agent_runs (
    id integer primary key autoincrement, agent text not null,
    tier text, lane text, started_at text not null, ended_at text,
    status text not null, exit_code integer, metrics text,
    log_path text, pid integer)""")
cx.executemany(
    "insert into agent_runs(agent,started_at,status,metrics,tier,pid)"
    " values(?,?,?,?,'T0',?)", [
        ("extract-fazwaz", DEBUT, "ok", '{"nouvelles": 472, "changees": 30}', PID),
        ("extract-ddproperty", DEBUT, "ok", '{"nouvelles": 2000, "changees": 80}', PID),
        ("extract-nestopa", DEBUT, "ok", '{"nouvelles": 16, "changees": 2}', PID),
        ("extract-propertyscout", DEBUT, "ok", '{"nouvelles": 72, "changees": 11}', PID),
        ("overseer", FIN, "ok", "{}", PID),
        # même PID, 8 jours plus tôt : un autre processus (PID recyclé)
        ("extract-livinginsider", HOMONYME, "ok", '{"nouvelles": 999}', PID),
    ])
cx.commit()
cx.close()
pouls.LEDGER = faux
pouls.POULS = pouls.Path(dossier) / "pouls.json"
pouls.DEJA_CRIE = pouls.Path(dossier) / "pouls-alertes.json"

vrai_demarrage = pouls._demarrage_processus
pouls._demarrage_processus = lambda pid: CREATION if pid == PID else None
try:
    etat = pouls.battement("daily", extraction_tentee=True, pid=PID)
finally:
    pouls._demarrage_processus = vrai_demarrage
assert etat["extracteurs_lances"] == 4 and etat["extracteurs_ok"] == 4, etat
print("1. cycle de 21 h 30 avec PID -> 4 extracteurs : OK")
assert etat["annonces_ecrites"] == 472 + 30 + 2000 + 80 + 16 + 2 + 72 + 11, etat
assert etat["agents_lances"] == 5, etat
print("2. homonyme d'un PID recycle exclu (5 runs, annonces exactes) : OK")

cris = []
vrai_crier = pouls._crier
pouls._crier = lambda motif, sujet, corps, preuves: cris.append(motif)
try:
    code = pouls.verifier(pouls.SEUIL_DEFAUT_H)
finally:
    pouls._crier = vrai_crier
assert code == 0 and not cris, f"cycle_vide crie a tort (defaut du 2026-10-01) : {cris}"
print("3. verifier() -> aucune alerte : OK")

etat_sans = pouls.battement("daily", extraction_tentee=True)
assert etat_sans["extracteurs_lances"] == 0, etat_sans
cris = []
pouls._crier = lambda motif, sujet, corps, preuves: cris.append(motif)
try:
    code = pouls.verifier(pouls.SEUIL_DEFAUT_H)
finally:
    pouls._crier = vrai_crier
assert code == 1 and cris == ["cycle_vide"], f"un vrai cycle vide doit alerter : {cris}"
print("4. sans PID -> fenetre de 12 h, un cycle vide alerte toujours : OK")

assert pouls._demarrage_processus(os.getpid()) is not None, \
    "la date de creation du processus courant doit etre lisible"
print("5. _demarrage_processus(propre PID) reel -> date lue : OK")

print("\nTOUS LES ESSAIS PASSENT")
