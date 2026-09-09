"""test_pouls_pid_recycle.py — un PID recyclé n'est pas un cycle de 199 heures.

POURQUOI CE TEST EXISTE
Mesuré le 2026-09-09. Windows réattribue les PID, et le ledger en garde la trace
pour toujours. Le PID 26632 portait à la fois `garde-veille` du
2026-08-31T18:00:21 et le cycle du 2026-09-08T18:12:13. `_cycle_en_cours()`
datait le début du cycle par `min(started_at)` sur le seul PID : il remontait
donc huit jours en arrière et annonçait « Cycle en cours depuis 199 h (seuil
16 h) — bloqué sur extract-ddproperty ».

Le cycle avait 14 h et tournait normalement — le recensement DDproperty écrivait
sa page 2559/3200 à l'instant du constat. Deux tickets de sévérité haute ont été
ouverts pour rien (2026-09-08T210002 et 2026-09-09T005239), et c'est exactement
le garde-fou qui crie au loup : à force, on cesse de lire ses alertes (règle 2).

Ce que le correctif garantit, et que ce test vérifie :
  1. une ligne antérieure au démarrage du processus est ignorée ;
  2. quand la date de démarrage est indéterminable (processus en session
     « Services », accès refusé — le cas courant depuis une session
     interactive), le repli borne le début au `started_at` de l'agent bloqué.
     Il peut SOUS-estimer la durée du cycle ; il ne doit jamais en inventer une.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_pouls_pid_recycle.py
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
PID = 26632          # le PID réellement recyclé, gardé tel quel

# Les deux dates de l'incident, rejouées en relatif pour rester vraies demain :
VIEUX = (MAINTENANT - timedelta(days=8, hours=6)).isoformat()   # homonyme mort
DEBUT = (MAINTENANT - timedelta(hours=14)).isoformat()          # cycle réel


def _ledger_factice(chemin: str) -> None:
    cx = sqlite3.connect(chemin)
    cx.execute("""create table agent_runs (
        id integer primary key autoincrement, agent text not null,
        tier text, lane text, started_at text not null, ended_at text,
        status text not null, exit_code integer, metrics text,
        log_path text, pid integer)""")
    lignes = [
        # ── cycle d'il y a 8 jours, terminé : même PID, réattribué depuis ──
        ("garde-veille", VIEUX, "ok", PID),
        ("extract-fazwaz", VIEUX, "ok", PID),
        # ── cycle en cours, celui qu'on veut dater ──
        ("garde-veille", DEBUT, "ok", PID),
        ("extract-fazwaz", DEBUT, "failed", PID),
        ("extract-ddproperty", DEBUT, "running", PID),
    ]
    cx.executemany(
        "insert into agent_runs(agent,started_at,status,pid,tier) "
        "values(?,?,?,?,'T0')", lignes)
    cx.commit()
    cx.close()


def _sans_date_de_demarrage(appel):
    """Simule le cas courant : OpenProcess refusé, démarrage indéterminable."""
    vrai = pouls._demarrage_processus
    pouls._demarrage_processus = lambda _pid: None
    try:
        return appel()
    finally:
        pouls._demarrage_processus = vrai


def _avec_date_de_demarrage(quand, appel):
    vrai = pouls._demarrage_processus
    pouls._demarrage_processus = lambda _pid: quand
    try:
        return appel()
    finally:
        pouls._demarrage_processus = vrai


dossier = tempfile.mkdtemp()
faux = os.path.join(dossier, "ledger.db")
_ledger_factice(faux)
pouls.LEDGER = faux

# ─────────────────────────────── 1. date de démarrage connue
info = _avec_date_de_demarrage(
    datetime.fromisoformat(DEBUT) - timedelta(seconds=5), pouls._cycle_en_cours)
assert info is not None, "un run 'running' doit être vu"
assert info["debut"] == DEBUT, (
    f"le début du cycle doit être {DEBUT} (démarrage du processus), pas "
    f"{info['debut']} — la ligne du PID recyclé doit être écartée")
duree_h = (MAINTENANT - datetime.fromisoformat(info["debut"])).total_seconds() / 3600
assert duree_h < pouls.SEUIL_CYCLE_LONG_DEFAUT_H, (
    f"un cycle de {duree_h:.1f} h ne doit pas franchir le seuil de "
    f"{pouls.SEUIL_CYCLE_LONG_DEFAUT_H} h")
print(f"1. PID recycle, demarrage connu -> cycle date a {duree_h:.1f} h : OK")

# ─────────────────────────────── 2. démarrage indéterminable (repli)
info = _sans_date_de_demarrage(pouls._cycle_en_cours)
assert info["debut"] == DEBUT, (
    f"sans date de demarrage, le repli doit borner le debut au started_at de "
    f"l'agent bloque ({DEBUT}), pas remonter au PID recycle ({info['debut']})")
print("2. PID recycle, demarrage inconnu -> repli sur l'agent bloque : OK")

# ─────────────────────────────── 3. l'alerte ne se déclenche plus
assert _sans_date_de_demarrage(
    lambda: pouls.verifier_cycle_long(pouls.SEUIL_CYCLE_LONG_DEFAUT_H)) == 0, \
    "un cycle de 14 h ne doit lever AUCUNE alerte (seuil 16 h)"
print("3. cycle de 14 h -> aucune alerte : OK")

# ─────────────────────────────── 4. mais un vrai cycle long alerte toujours
#     Le correctif ne doit pas rendre la surveillance muette (règle 2, envers).
cx = sqlite3.connect(faux)
bloque_depuis = (MAINTENANT - timedelta(hours=20)).isoformat()
cx.execute("update agent_runs set started_at=? where status='running'",
           (bloque_depuis,))
cx.commit()
cx.close()

cris = []
vrai_crier = pouls._crier
pouls._crier = lambda motif, sujet, corps, preuves: cris.append(sujet)
try:
    code = _sans_date_de_demarrage(
        lambda: pouls.verifier_cycle_long(pouls.SEUIL_CYCLE_LONG_DEFAUT_H))
finally:
    pouls._crier = vrai_crier

assert code == 1 and cris, \
    "un cycle reellement bloque depuis 20 h DOIT toujours alerter"
assert "20 h" in cris[0], f"la duree annoncee doit etre la vraie : {cris[0]}"
print(f"4. cycle reellement bloque 20 h -> alerte levee : OK")

print("\nTOUS LES ESSAIS PASSENT")
