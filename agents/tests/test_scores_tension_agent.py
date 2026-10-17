"""test_scores_tension_agent.py — l'agent mensuel tient-il son contrat, sans crier au loup ?

POURQUOI CE TEST EXISTE
L'agent tourne une fois par mois, ~50 min : une panne passerait inaperçue un mois
entier. On vérifie, sur la VRAIE base mais un petit lot (5 immeubles), que :
  · il rend tous les champs de son contrat (SKILL.md), ceux que l'overseer contrôle ;
  · il écrit son fichier de façon atomique là où on le lui dit ;
  · il ne lève un constat MOYEN que si les deux grandes sources sont écartées
    (règle 2 : un garde-fou qui crie au loup apprend à être ignoré).
Passe sans rien tester (et le dit) si la base de référence est absente du poste.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_scores_tension_agent.py
"""
import json
import os
import sys
import tempfile

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RACINE)
sys.stdout.reconfigure(encoding="utf-8")

from agents.bots import scores_tension          # noqa: E402
from agents.bots.overseer import contrat_de     # noqa: E402
from study.tension import donnees, lot          # noqa: E402

# la base de référence vit dans le checkout principal (un worktree n'en a pas)
for cand in (donnees.DB, r"C:\Lowi_bkk\scraper\output\bangkok.db"):
    if os.path.exists(cand):
        donnees.DB = cand
        break
else:
    print("base de référence absente : test non exécuté sur ce poste")
    sys.exit(0)


class FauxLedger:
    def __init__(self):
        self.constats = []

    def finding(self, agent, severite, nature, message, preuves=None, run_id=None):
        self.constats.append((severite, nature, message))


def main():
    with tempfile.TemporaryDirectory() as d:
        lot.SORTIE = d
        led = FauxLedger()
        m = scores_tension.run(led, 0, "daily", {"limite": 5})
        attendus = contrat_de("scores-tension")
        manquants = attendus - set(m)
        assert not manquants, f"contrat incomplet : {manquants}"
        print(f"ok  contrat honoré ({len(attendus)} champs)")
        assert os.path.dirname(m["fichier"]) == d and os.path.exists(m["fichier"])
        res = json.load(open(m["fichier"], encoding="utf-8"))
        assert len(res["immeubles"]) == m["immeubles"] == 5
        assert not [f for f in os.listdir(d) if f.endswith(".tmp")], "fichier temporaire laissé"
        print(f"ok  fichier écrit ({m['immeubles']} immeubles, {m['duree_s']} s)")
        ecartees = set(res["sources"]) - set(m["sources_gardees"])
        moyens = [c for c in led.constats if c[0] == "medium"]
        if {"ddproperty", "fazwaz"} <= ecartees:
            assert any(c[1] == "score_sans_grande_source" for c in moyens)
        else:
            assert not [c for c in moyens if c[1] == "score_sans_grande_source"], moyens
        print(f"ok  constats proportionnés : {[c[1] for c in led.constats] or 'aucun'}")
    print("\nTOUS LES ESSAIS PASSENT")


if __name__ == "__main__":
    main()
