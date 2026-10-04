"""test_pouls_cycle_en_cours.py — un cycle en cours n'est pas un cycle manquant.

POURQUOI CE TEST EXISTE
Mesuré le 2026-10-04 (ticket `2026-10-02T010004-pouls-cycle_manquant.json`).
Le cycle du 01/10 a fini à 05:37 (heure de Bangkok) ; le suivant est parti
normalement à 01:00 le 02/10 et a fini à 11:33. Le contrôle de 08:00 tombait
entre les deux : 26,4 h depuis la dernière FIN, au-dessus du seuil de 26 h, et
`cycle_manquant` a crié (mail compris) pendant que les 4 extracteurs tournaient
sans problème. L'âge du dernier battement mesure l'écart entre deux fins, pas
l'absence de cycle.

Le correctif : si le ledger montre un cycle en cours démarré APRÈS le dernier
battement, `verifier()` se tait sur ce motif ; `verifier_cycle_long` garde la
durée de ce cycle sous surveillance (seuil de 16 h inchangé).

Ce que ce test vérifie :
  1. battement vieux de 26,4 h + cycle démarré il y a 7 h → pas d'alerte ;
  2. même battement, aucun cycle en cours → `cycle_manquant` crie toujours ;
  3. battement vieux de 26,4 h + run `running` resté d'AVANT le battement
     (cycle mort, pas un nouveau) → `cycle_manquant` crie toujours.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_pouls_cycle_en_cours.py
N'utilise NI ledger.db NI le vrai pouls.json : tout dans un dossier temporaire.
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
PID = 23372                                              # PID réel du 02/10
FIN_PRECEDENTE = MAINTENANT - timedelta(hours=26, minutes=24)

cris = []


def preparer(runs):
    dossier = tempfile.mkdtemp()
    faux = os.path.join(dossier, "ledger.db")
    cx = sqlite3.connect(faux)
    cx.execute("""create table agent_runs (
        id integer primary key autoincrement, agent text not null,
        tier text, lane text, started_at text not null, ended_at text,
        status text not null, exit_code integer, metrics text,
        log_path text, pid integer)""")
    cx.executemany("insert into agent_runs(agent,started_at,status,tier,pid)"
                   " values(?,?,?,'T0',?)", runs)
    cx.commit()
    cx.close()
    pouls.LEDGER = faux
    pouls.POULS = pouls.Path(dossier) / "pouls.json"
    pouls.DEJA_CRIE = pouls.Path(dossier) / "pouls-alertes.json"
    pouls.POULS.write_text(json.dumps({
        "termine_a": FIN_PRECEDENTE.isoformat(), "lane": "daily",
        "extracteurs_lances": 4, "annonces_ecrites": 5089}), encoding="utf-8")
    cris.clear()


pouls._crier = lambda motif, *a, **k: cris.append(motif)
pouls._demarrage_processus = lambda pid: None    # repli sur started_at

# 1. cycle en cours depuis 7 h, démarré après le battement
il_y_a_7h = (MAINTENANT - timedelta(hours=7)).isoformat()
preparer([("garde-veille", il_y_a_7h, "ok", PID),
          ("extract-fazwaz", il_y_a_7h, "ok", PID),
          ("extract-ddproperty", il_y_a_7h, "running", PID)])
assert pouls.verifier(26) == 0 and not cris, cris
print("1. battement de 26,4 h + cycle en cours depuis 7 h -> silence : OK")

# 2. aucun cycle en cours : la vraie absence crie toujours
preparer([("overseer", FIN_PRECEDENTE.isoformat(), "ok", PID)])
assert pouls.verifier(26) == 1 and cris == ["cycle_manquant"], cris
print("2. aucun cycle en cours -> cycle_manquant : OK")

# 3. run `running` antérieur au battement : vestige, pas un nouveau cycle
vieux = (FIN_PRECEDENTE - timedelta(hours=3)).isoformat()
preparer([("backup-apres-cycle", vieux, "running", 999)])
assert pouls.verifier(26) == 1 and cris == ["cycle_manquant"], cris
print("3. run 'running' antérieur au battement -> cycle_manquant : OK")

print("test_pouls_cycle_en_cours : OK")
