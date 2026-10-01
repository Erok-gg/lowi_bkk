"""test_overseer_cycle_long.py — un agent qui a tourné en début de cycle long
n'est pas muet.

POURQUOI CE TEST EXISTE
Mesuré le 2026-10-01 (ticket `2026-09-30T223736-overseer-agent_muet.json`).
Le cycle du 30/09 a duré 28 h 36 entre `garde-veille` (29/09 18:01 UTC,
premier agent) et l'overseer (30/09 22:37), dont 14 h 24 de veille prolongée
avec le capot fermé. L'overseer ne relisait que les runs des dernières 24 h :
il n'a plus vu `garde-veille` et l'a déclaré muet, en sévérité haute avec
mail, alors qu'il avait tourné normalement.

Ce que ce test vérifie (`overseer._debut_du_cycle`) :
  1. il remonte au premier run de CE processus, même à plus de 24 h ;
  2. il ignore un run plus ancien qui porte le même PID (PID recyclé) ;
  3. il rend None si la date de création est illisible, et l'overseer garde
     alors sa fenêtre de 24 h.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_overseer_cycle_long.py
Base temporaire : ni ledger.db ni queue/.
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

import ops.pouls as pouls                                # noqa: E402
from agents.bots import overseer                         # noqa: E402
from agents.core.ledger import Ledger                    # noqa: E402

maintenant = datetime.now(timezone.utc)
pid = os.getpid()
debut = (maintenant - timedelta(hours=28, minutes=36)).isoformat(timespec="seconds")
homonyme = (maintenant - timedelta(days=8)).isoformat(timespec="seconds")

led = Ledger(os.path.join(tempfile.mkdtemp(), "ledger-test.db"))
led.conn.executemany(
    "insert into agent_runs(agent,tier,lane,started_at,ended_at,status,pid)"
    " values(?,'T0','daily',?,?,'ok',?)", [
        ("garde-veille", homonyme, homonyme, pid),
        ("garde-veille", debut, debut, pid),
        ("extract-fazwaz", (maintenant - timedelta(hours=20)).isoformat(timespec="seconds"),
         None, pid),
    ])
led.conn.commit()

vrai = pouls._demarrage_processus
pouls._demarrage_processus = lambda p: maintenant - timedelta(hours=29)
try:
    trouve = overseer._debut_du_cycle(led)
finally:
    pouls._demarrage_processus = vrai
assert trouve == debut, f"debut du cycle attendu {debut}, obtenu {trouve}"
print("1. debut du cycle retrouve a 28 h 36 (au-dela des 24 h) : OK")
print("2. homonyme de 8 jours (PID recycle) ignore : OK")

pouls._demarrage_processus = lambda p: None
try:
    assert overseer._debut_du_cycle(led) is None
finally:
    pouls._demarrage_processus = vrai
print("3. creation illisible -> None (fenetre de 24 h conservee) : OK")

led.conn.close()
print("\nTOUS LES ESSAIS PASSENT")
