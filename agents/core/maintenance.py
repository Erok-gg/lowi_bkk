"""maintenance.py — une nuit sans cycle, décidée, n'est pas une panne.

POURQUOI CE MODULE EXISTE (2026-10-07, demande de l'utilisateur)
Le cycle du 2026-10-08 est suspendu volontairement : l'instance Supabase vient
de subir une maintenance (index retirés, VACUUM, fillfactor — journal du
2026-10-07) et on lui laisse une nuit sans remontée. Désactiver la tâche
Windows aurait suffi à ne pas lancer le cycle, mais DEUX surveillances
l'auraient pris pour une panne : `ops/veille-cycle.py` (« le cycle n'est pas
parti » → ticket + Opus) et `ops/pouls.py --verifier` (« cycle_manquant »
après 26 h). Un garde-fou qui crie au loup pendant une maintenance apprend à
être ignoré (règle 2).

D'où une fenêtre déclarée dans `agents/state/maintenance.json` :

    {"debut": "<iso avec fuseau>", "fin": "<iso avec fuseau>", "motif": "..."}

que lisent l'orchestrateur (ne lance pas `--due`/`--boot` dedans) et les deux
surveillances (se taisent dedans, et ne comptent pas la fenêtre dans l'âge du
dernier battement). Le fichier reste après la fin : il est la trace de la
maintenance, et une fenêtre échue ne fait plus rien. Un fichier illisible =
pas de maintenance — on préfère une fausse alerte à un cycle sauté en silence.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

FICHIER = Path(__file__).resolve().parents[1] / "state" / "maintenance.json"


def fenetre(chemin: Path = FICHIER) -> dict | None:
    """La fenêtre déclarée (dates en datetime aware), ou None."""
    try:
        d = json.loads(chemin.read_text(encoding="utf-8"))
        debut = datetime.fromisoformat(d["debut"])
        fin = datetime.fromisoformat(d["fin"])
        if debut.tzinfo is None or fin.tzinfo is None or fin <= debut:
            return None
        return {"debut": debut, "fin": fin, "motif": d.get("motif", "")}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def active(maintenant: datetime | None = None, chemin: Path = FICHIER) -> dict | None:
    """La fenêtre si `maintenant` tombe dedans, sinon None."""
    f = fenetre(chemin)
    t = maintenant or datetime.now(timezone.utc)
    if f and f["debut"] <= t < f["fin"]:
        return f
    return None
