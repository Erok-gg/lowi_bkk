"""test_reap_run_long.py — un run long n'est pas un run mort.

POURQUOI CE TEST EXISTE
Mesuré le 2026-10-01 à 02:14 : le cycle du 30/09, coupé 14 h 24 par une veille
prolongée (capot fermé à 10:12, Kernel-Power 42 « Hibernate from Sleep - Fixed
Timeout » à 10:42, reprise à 01:06), tournait toujours — `extract-ddproperty`
à la page 143/150, journal écrit à la seconde. Un `orchestrator status` lancé
depuis la session de réparation a ouvert le ledger, et `reap_stale()` a classé
le run #642 `interrompu` : son âge (18 h) dépassait le filet de 12 h, alors que
son PID était vivant. Le filet ne devait couvrir que les runs sans PID et les
PID recyclés ; il fermait aussi les runs simplement longs.

Ce que ce test verrouille :
  1. run de 20 h, PID vivant, processus créé AVANT le run → reste `running` ;
  2. run de 20 h, PID vivant, processus créé APRÈS le run (PID recyclé)
     → `interrompu` ;
  3. run de 20 h, PID vivant, date de création illisible → `interrompu`
     (comportement d'avant : dans le doute on garde le filet) ;
  4. run récent, PID mort → `interrompu` (inchangé) ;
  5. `_cree_le` réel : le propre PID du test a une date de création récente,
     un PID terminé n'en a pas.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_reap_run_long.py

Windows uniquement. N'utilise NI ledger.db NI queue/ : base temporaire.
"""
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from agents.core.ledger import Ledger                    # noqa: E402

maintenant = datetime.now(timezone.utc)
il_y_a_20h = (maintenant - timedelta(hours=20)).isoformat(timespec="seconds")
il_y_a_5min = (maintenant - timedelta(minutes=5)).isoformat(timespec="seconds")

tmp = tempfile.mkdtemp()
led = Ledger(os.path.join(tmp, "ledger-test.db"))


def inserer(started_at, pid):
    cur = led.conn.execute(
        "insert into agent_runs(agent,tier,lane,started_at,status,pid)"
        " values('extract-test','T0','daily',?, 'running', ?)", (started_at, pid))
    led.conn.commit()
    return cur.lastrowid


def statut(run_id):
    return led.conn.execute(
        "select status from agent_runs where id=?", (run_id,)).fetchone()[0]


vrai_vivant, vrai_cree = Ledger._processus_vivant, Ledger._cree_le


def scenario(started_at, vivant, cree):
    Ledger._processus_vivant = staticmethod(lambda pid: vivant)
    Ledger._cree_le = staticmethod(lambda pid: cree)
    try:
        rid = inserer(started_at, 4242)
        led.reap_stale()
        return statut(rid)
    finally:
        Ledger._processus_vivant, Ledger._cree_le = vrai_vivant, vrai_cree
        led.conn.execute("delete from agent_runs")
        led.conn.commit()


s = scenario(il_y_a_20h, True, maintenant - timedelta(hours=21))
assert s == "running", f"run long mais vivant (meme processus) ferme a tort : {s}"
print("1. 20 h, PID vivant, cree avant le run -> running : OK")

s = scenario(il_y_a_20h, True, maintenant - timedelta(hours=2))
assert s == "interrompu", f"PID recycle non detecte : {s}"
print("2. 20 h, PID vivant mais cree apres le run (recycle) -> interrompu : OK")

s = scenario(il_y_a_20h, True, None)
assert s == "interrompu", f"date de creation illisible : le filet doit jouer ({s})"
print("3. 20 h, date de creation illisible -> interrompu : OK")

s = scenario(il_y_a_5min, False, None)
assert s == "interrompu", f"PID mort non referme : {s}"
print("4. run recent, PID mort -> interrompu : OK")

# ------------------------------------------------ 5. lecture WMI réelle
cree = Ledger._cree_le(os.getpid())
assert cree is not None, "WMI n'a pas rendu la date de creation du propre PID"
assert abs((datetime.now(timezone.utc) - cree).total_seconds()) < 600, \
    f"date de creation du propre PID incoherente : {cree}"
p = subprocess.Popen([sys.executable, "-c", "pass"])
p.wait()
assert Ledger._cree_le(p.pid) is None, "un PID termine ne doit pas avoir de date"
print("5. _cree_le reel : propre PID date, PID termine -> None : OK")

led.conn.close()
print("\nTOUS LES ESSAIS PASSENT")
