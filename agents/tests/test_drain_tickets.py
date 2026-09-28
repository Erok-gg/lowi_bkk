"""test_drain_tickets.py — le drainage automatique des tickets organize.

POURQUOI CE TEST EXISTE
Le 2026-09-28, 33 tickets attendaient depuis le 16/09 : la routine qui devait
les drainer était désactivée sur l'autre poste, et rien ne le disait. Ce test
verrouille, avec un modèle SIMULÉ (aucun appel réseau) :
  1. un ticket drainé passe en done/ et ses réponses passent par `decider()` ;
  2. une paire OMISE par le modèle n'est pas marquée tranchée ;
  3. une extraction contredite par le code est COMPTÉE (`paires_fausses`) ;
  4. si tous les appels échouent, le ticket reste OUVERT et un constat sort.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_drain_tickets.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from agents.core import escalation                     # noqa: E402
from agents.bots import organize, drain_tickets as dt  # noqa: E402

tmp = tempfile.mkdtemp(prefix="lowi-drain-")
organize.STATE = os.path.join(tmp, "organize")
organize.REVUE = os.path.join(organize.STATE, "revue.jsonl")
organize.EN_TICKET = os.path.join(organize.STATE, "paires-en-ticket.txt")
organize.FAITES = os.path.join(organize.STATE, "paires-faites.txt")
organize.LOTS = os.path.join(organize.STATE, "lots")
dt.REPONSES = os.path.join(organize.STATE, "reponses")
escalation.QUEUE = os.path.join(tmp, "queue")
escalation.DONE = os.path.join(escalation.QUEUE, "done")
os.makedirs(organize.STATE, exist_ok=True)


class Led:
    def __init__(self):
        self.constats = []
    def escalate(self, *a, **k): pass
    def resolve_escalation(self, *a, **k): pass
    def finding(self, agent, sev, kind, msg, detail=None, run_id=None):
        self.constats.append(kind)
    def __getattr__(self, n):
        return lambda *a, **k: None


def paire(i, st_a, st_b, da, fsb, pa, pb):
    def cote(tag, st, d, fs, p):
        s = "ACTIVE" if st == "active" else f"INACTIVE (delisted on {d})"
        return (f"Listing {tag} : Condo X - Khet - 1 bed - 30.00 sqm - {p:,} THB (rent)\n"
                f"  first seen on {fs} - status {s}")
    return {"cle": f"a{i}|b{i}", "ida": f"a{i}", "idb": f"b{i}", "source": "ddproperty",
            "condo": "Condo X", "khet": "Khet",
            "texte": cote("A", st_a, da, "2026-06-01", pa) + "\n" + cote("B", st_b, None, fsb, pb),
            "dates": {"da": da or "", "fsb": fsb}}


paires = [paire(1, "inactive", "active", "2026-07-01", "2026-07-10", 10000, 10000),  # same_unit
          paire(2, "inactive", "active", "2026-07-20", "2026-07-10", 10000, 12000),  # insufficient
          paire(3, "inactive", "active", "2026-07-01", "2026-07-10", 10000, 10100)]  # omise


def ecrire_ticket(led):
    os.makedirs(organize.LOTS, exist_ok=True)
    t = escalation.create(agent="organize", kind="comparaison_deleguee", severity="low",
                          subject="test", evidence={"paires": paires},
                          asked_of_claude="test", ledger=led)
    with open(os.path.join(organize.LOTS, t), "w", encoding="utf-8") as f:
        json.dump({"ticket": t, "paires": paires}, f)
    return t


def modele_simule(prompt):
    v1 = dt.verite_code(paires[0]); v2 = dict(dt.verite_code(paires[1]))
    v2["b_active"] = False                     # extraction FAUSSE, voulue
    return json.dumps([{"index": 1, **v1}, {"index": 2, **v2}]), 0.0


led = Led()
t = ecrire_ticket(led)
dt.social_leads.appeler_claude = modele_simule
orig = dt.traiter_ticket
dt.traiter_ticket = lambda nom, journal=print: orig(nom, appel=modele_simule, journal=journal)
m = dt.run(led, 0, "test", {})
assert m["tickets_draines"] == 1 and m["reponses"] == 2, m
assert m["paires_fausses"] == 1, m
assert m["revue_ajoutee"] == 1, m                       # paire 1 → same_unit
assert os.path.exists(os.path.join(escalation.DONE, t)), "ticket non refermé"
faites = open(organize.FAITES, encoding="utf-8").read()
assert "a3|b3" not in faites, "paire omise marquée tranchée (défaut du 2026-08-17)"
assert "extraction_degradee" in led.constats           # 1/2 > 5 %
print("✓ ticket drainé, paire omise non tranchée, extraction fausse comptée")

# 4. appels tous en échec → ticket ouvert + constat
def en_panne(prompt):
    raise RuntimeError("OAuth session expired")
led2 = Led()
t2 = ecrire_ticket(led2)
dt.traiter_ticket = lambda nom, journal=print: orig(nom, appel=en_panne, journal=journal)
m2 = dt.run(led2, 0, "test", {})
assert m2["tickets_draines"] == 0 and m2["tickets_restants"] == 1, m2
# (même nom que t possible : horodatage à la seconde, t est déjà en done/)
assert os.path.exists(os.path.join(escalation.QUEUE, t2)), "ticket refermé sans réponse"
assert "haiku_injoignable" in led2.constats, led2.constats
print("✓ Haiku injoignable : ticket laissé ouvert, constat émis")
print("\nTOUS LES ESSAIS PASSENT")
