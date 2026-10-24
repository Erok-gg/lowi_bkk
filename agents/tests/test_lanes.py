"""test_lanes.py — un cycle de nuit ne doit jamais partir à vide.

POURQUOI CE TEST EXISTE
Le 2026-08-24, premier cycle de la cadence quotidienne : la tâche s'est
déclenchée à 01:00, la machine s'est réveillée, `garde-veille` a tourné… et
AUCUN extracteur. Le ledger le montre : un seul run sur tout le cycle.

Deux défauts empilés, tous deux corrigés dans agents/orchestrator.py :

  1. **la lane se calculait en UTC.** Le cycle part à 01:00 à Bangkok, soit
     18:00 la veille en UTC : le calendrier hebdomadaire était décalé d'un jour.
  2. **le jour hebdomadaire REMPLAÇAIT le quotidien** au lieu de s'y ajouter.
     `weekly` ne retenait que les agents portant ce mot — ni extraction, ni
     analyse, ni sauvegarde. Invisible tant que l'extraction tournait tous les
     4 jours (elle repartait la nuit suivante), c'est une journée de marché
     perdue par semaine depuis le passage au quotidien.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_lanes.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from agents.orchestrator import REGISTRY, lanes_actives   # noqa: E402


def agents_de(lane: str) -> set[str]:
    actives = lanes_actives(lane)
    return {a["name"] for a in REGISTRY["agents"]
            if actives & set(a.get("lanes", []))}

quotidien = agents_de("daily")
hebdo = agents_de("weekly")

# --------------------------------- 1. le jour hebdomadaire n'enlève rien
manquants = quotidien - hebdo
assert not manquants, f"le jour hebdomadaire perd des agents : {sorted(manquants)}"
print(f"hebdo ⊇ quotidien : OK  ({len(quotidien)} agents quotidiens, {len(hebdo)} le jour hebdo)")

# --------------------------------- 2. l'extraction tourne les DEUX jours
# Un extracteur suspendu à dessein (`lanes` vide ET motif écrit dans
# `_suspendu`) est exclu — extract-livinginsider le 2026-09-26. Exiger le motif
# garde le test utile : une lane vidée par erreur, sans explication, échoue
# toujours.
# Un extracteur rattaché à une AUTRE lane déclarée dans `lanes` (2026-10-22 :
# `soir`, DotProperty, tâche LowiBKK-Soir de 21:00) a son propre créneau : il
# est exclu ici et vérifié en 5. Une lane non déclarée reste une erreur.
autres_lanes = set(REGISTRY.get("lanes", {})) - {"daily", "weekly"}
extracteurs = {a["name"] for a in REGISTRY["agents"]
               if a.get("famille") == "Extraction"
               and not (not a.get("lanes") and a.get("_suspendu"))
               and not (a.get("lanes") and set(a["lanes"]) <= autres_lanes)}
assert extracteurs, "registre sans agent d'extraction — test sans objet"
for lane in ("daily", "weekly"):
    absents = extracteurs - agents_de(lane)
    assert not absents, f"lane {lane} : extracteurs jamais lancés {sorted(absents)}"
print(f"extraction presente sur les 2 lanes : OK  ({len(extracteurs)} extracteurs)")

# --------------------------------- 3. le jour hebdomadaire ajoute bien ses agents
ajouts = hebdo - quotidien
assert ajouts, "le jour hebdomadaire n'ajoute plus rien : archivage et sondage perdus"
print(f"ajouts du jour hebdomadaire : OK  -> {sorted(ajouts)}")

# --------------------------------- 4. aucune lane ne peut partir a vide
for lane in ("daily", "weekly"):
    assert len(agents_de(lane)) >= 5, f"lane {lane} quasi vide : {agents_de(lane)}"
print("aucune lane vide : OK")

# --------------------------------- 5. une lane annexe tient le poste éveillé
# Sans garde-veille, un scrap du soir est exposé à la mise en veille qui a tué
# extract-ddproperty deux cycles d'affilée (2026-08-16).
for lane in sorted(autres_lanes):
    noms = agents_de(lane)
    if not any(n.startswith("extract-") for n in noms):
        continue
    assert "garde-veille" in noms, f"lane {lane} : extracteur sans garde-veille {sorted(noms)}"
    print(f"lane annexe {lane} : garde-veille present : OK  -> {sorted(noms)}")

print("\nTOUS LES ESSAIS PASSENT")
