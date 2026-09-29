"""test_status_hors_lanes.py — `orchestrator status` ne doit jamais afficher
DÛ pour un agent que le scheduler n'invoque jamais.

POURQUOI CE TEST EXISTE
Constaté le 2026-09-16 (réparation autonome) : `regle-alimentation`,
`verifie-backup` et `storage` portent tous les trois `"lanes": []` dans
agents.json — neutralisés à dessein (préférence manuelle pour le premier,
rôle repris ailleurs après la bascule SQLite pour les deux autres, cf. leurs
`_pourquoi`). `cmd_status()` calculait pourtant `is_due()` pour TOUS les
agents sans regarder `lanes`, et affichait « DÛ » avec un retard de 20 à 30
jours sur ces trois-là — un garde-fou qui crie au loup (règle 2 du
CLAUDE.md) : rien ne les invoque via `--due`, donc rien ne les fait jamais
« à jour ». Le correctif affiche « manuel (hors lanes) » pour tout agent à
`lanes` vide, sans passer par `is_due()`.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_status_hors_lanes.py
"""
import io
import os
import sys
import tempfile
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import agents.orchestrator as orch                          # noqa: E402
from agents.core.ledger import Ledger                        # noqa: E402

ancien_registry = orch.REGISTRY

with tempfile.TemporaryDirectory() as tmp:
    ledger_path = os.path.join(tmp, "ledger.db")
    led = Ledger(ledger_path)
    try:
        orch.REGISTRY = {"agents": [
            {"name": "agent-manuel-test", "tier": "T0", "every_days": 1,
             "lanes": []},
            {"name": "agent-lane-test", "tier": "T0", "every_days": 1,
             "lanes": ["daily"]},
        ]}

        sortie = io.StringIO()
        with redirect_stdout(sortie):
            orch.cmd_status(led)
        texte = sortie.getvalue()
    finally:
        orch.REGISTRY = ancien_registry
        led.conn.close()

# 1. l'agent hors lanes ne doit JAMAIS afficher DÛ ni à jour (calcul de
#    cadence sans objet puisque --due ne le regarde pas)
ligne_manuel = next(l for l in texte.splitlines() if "agent-manuel-test" in l)
assert "manuel (hors lanes)" in ligne_manuel, (
    f"agent à lanes vide doit s'afficher « manuel (hors lanes) » : {ligne_manuel!r}")
assert "DÛ" not in ligne_manuel, (
    f"un agent jamais invoqué par le scheduler ne doit jamais crier DÛ : {ligne_manuel!r}")
print("1. agent à lanes vide -> « manuel (hors lanes) », jamais DÛ : OK")

# 2. un agent normal (dans une lane) garde le calcul DÛ/à jour habituel
ligne_lane = next(l for l in texte.splitlines() if "agent-lane-test" in l)
assert "DÛ" in ligne_lane or "à jour" in ligne_lane, (
    f"un agent dans une lane doit garder le calcul de cadence normal : {ligne_lane!r}")
print("2. agent dans une lane -> calcul DÛ/à jour inchangé : OK")

print("\nTOUS LES ESSAIS PASSENT")
