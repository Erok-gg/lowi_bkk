"""repertorier-annonces — après les extracteurs, tient `condo_norm` à jour (bilan acheteur).

Lance bilan_RE/ops/repertorier-annonces.py et rend sa ligne de métriques.
Pourquoi un agent : le bilan retrouve un immeuble sur tous les portails par ce
nom normalisé, indexé (18 ms au lieu de 1,5 s, mesuré le 2026-10-17). Une
annonce nouvelle n'est trouvable par son immeuble qu'une fois répertoriée.
Mesuré : ~2 s en passage quotidien (annonces vues depuis le dernier passage),
2 min 11 au tout premier passage (migration + 195 610 lignes).

Constat MOYEN seulement si des annonces restent non répertoriées après le
passage (règle 2 : un nom vide normalisé reçoit "" et ne compte pas).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(RACINE, "bilan_RE", "ops", "repertorier-annonces.py")


def run(led, run_id: int, lane: str, spec: dict) -> dict:
    r = subprocess.run([sys.executable, SCRIPT], cwd=RACINE, capture_output=True, text=True,
                       encoding="utf-8", timeout=3600)
    if r.returncode:
        raise RuntimeError(f"repertorier-annonces a échoué (code {r.returncode}) : {r.stderr[-1500:]}")
    m = json.loads(r.stdout.strip().splitlines()[-1])
    if m["lignes_nulles_restantes"]:
        led.finding("repertorier-annonces", "medium", "annonces_non_repertoriees",
                    f"{m['lignes_nulles_restantes']} annonce(s) sans condo_norm après le passage",
                    m, run_id)
    return m
