"""test_tickets.py — le mode « T1 absent » de bout en bout.

POURQUOI CE TEST EXISTE
Le 2e poste (24/7) est trop faible pour Ollama : `organize` y dépose ses paires
en ticket au lieu de les comparer. Un mécanisme de délégation sans test de bout
en bout est précisément ce qui est arrivé au T2 promis le 2026-07-31 —
`agents/README.md` annonçait une tâche qui drainait `agents/queue/`, aucune ne le
faisait, et `queue/done/` est resté vide cinq jours sans que rien ne le dise.

Ce qu'il verrouille, dans l'ordre :
  1. le ticket est AUTO-PORTANT (consigne, schéma, texte des paires) ;
  2. deux dépôts successifs ne soumettent jamais deux fois la même paire ;
  3. une réponse incohérente est REJETÉE par `coherent()`, pas enregistrée ;
  4. une paire OMISE de la réponse n'est pas marquée tranchée — c'est le défaut
     du 2026-08-17, des paires en échec notées « traitées » ;
  5. une paire d'un ticket drainé sans réponse redevient tirable ;
  6. `ask_safe` est SILENCIEUX quand T1 est déclaré absent — sinon 6 constats de
     sévérité haute par cycle, tous les jours (règle 2).

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_tickets.py

Tout est redirigé vers un dossier temporaire : ni la vraie file de tickets ni le
vrai journal de reprise ne sont touchés.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from agents.core import escalation, local_llm          # noqa: E402
from agents.bots import organize                       # noqa: E402

tmp = tempfile.mkdtemp(prefix="lowi-tickets-")
organize.STATE = os.path.join(tmp, "organize")
organize.REVUE = os.path.join(organize.STATE, "revue.jsonl")
organize.EN_TICKET = os.path.join(organize.STATE, "paires-en-ticket.txt")
organize.FAITES = os.path.join(organize.STATE, "paires-faites.txt")
organize.LOTS = os.path.join(organize.STATE, "lots")
os.makedirs(organize.STATE, exist_ok=True)
escalation.QUEUE = os.path.join(tmp, "queue")
escalation.DONE = os.path.join(escalation.QUEUE, "done")

# Marqueur d'absence, dans le temporaire lui aussi.
local_llm.MARQUEUR_ABSENT = os.path.join(tmp, "t1-absent")
open(local_llm.MARQUEUR_ABSENT, "w").close()
assert local_llm.t1_absent(), "le marqueur devrait etre vu"


class LedgerFactice:
    def __init__(self):
        self.escalades = []
        self.constats = []

    def escalate(self, *a):
        self.escalades.append(a)

    def finding(self, *a, **k):
        self.constats.append(a)


def paire(i, sta="inactive", stb="active", da="2026-06-01", fsb="2026-07-15"):
    return {"ida": f"a{i}", "idb": f"b{i}", "source": "fazwaz", "deal_type": "sale",
            "condo_name": f"Condo {i}", "khet": "Vadhana", "bedrooms": 1,
            "sa": 35.0, "sb": 35.0, "pa": 5_000_000, "pb": 5_000_000,
            "sta": sta, "stb": stb, "fsa": "2026-01-01", "fsb": fsb,
            "da": da, "db": None, "aga": None, "agb": None}


led = LedgerFactice()
ambigues = [paire(i) for i in range(1, 11)]

# ---------------------------------------------------------------- 1. depot
os.environ["ORGANIZE_TICKET_LOT"] = "4"
m = organize.deposer_en_ticket(led, 1, ambigues)
print("depot :", json.dumps(m, ensure_ascii=False))
assert m["paires_deposees"] == 4, m
assert len(led.escalades) == 1, led.escalades
ticket = m["ticket"]
assert os.path.exists(os.path.join(escalation.QUEUE, ticket)), "ticket absent de la file"
assert os.path.exists(os.path.join(organize.LOTS, ticket)), "sidecar absent"

# Le ticket doit etre auto-portant : consigne, schema, textes des paires.
t = json.load(open(os.path.join(escalation.QUEUE, ticket), encoding="utf-8"))
assert t["severity"] == "low", t["severity"]
assert "schema_attendu" in t["evidence"] and "paires" in t["evidence"]
assert "Listing A" in t["evidence"]["paires"][0]["texte"]
print("ticket auto-portant : OK  (severite", t["severity"], ")")
lot1 = {p["cle"] for p in t["evidence"]["paires"]}

# ------------------------------------------- 2. un 2e depot ne redepose pas
m2 = organize.deposer_en_ticket(led, 2, ambigues)
print("2e depot :", m2["paires_deposees"], "paires (doit etre 4 NOUVELLES)")
assert m2["paires_deposees"] == 4
assert m2["ticket"] != ticket, "collision de nom de ticket"
lot2 = {p["cle"] for p in json.load(open(os.path.join(organize.LOTS, m2["ticket"]), encoding="utf-8"))["paires"]}
assert not (lot1 & lot2), "des paires ont ete deposees deux fois"
print("aucun recouvrement entre les deux lots : OK")

# ------------------------------------------------------------- 3. reponses
# Trois reponses sur quatre : A retiree le 01/06, B vue le 15/07 -> same_unit.
# La quatrieme est OMISE volontairement (cas « je ne sais pas »).
cles = sorted(lot1)
rep = {"ticket": ticket, "reponses": [
    {"cle": c, "a_active": False, "b_active": True, "a_retiree": True,
     "b_retiree": False, "b_apres_a": True, "ecart_prix_pct": 0.0}
    for c in cles[:3]
]}
# Une reponse incoherente pour verifier le rejet par `coherent()` :
rep["reponses"][2].update({"a_retiree": False})     # b_apres_a sans retrait de A

f_rep = os.path.join(tmp, "reponses.json")
json.dump(rep, open(f_rep, "w", encoding="utf-8"), ensure_ascii=False)

r = organize.appliquer_reponses(f_rep)
print("application :", json.dumps(r, ensure_ascii=False))
assert r["reponses"] == 3
assert r["revue_ajoutee"] == 2, r          # 2 tranchees
assert r["abstentions"] == 1, r            # 1 incoherente -> insufficient
assert r["rejets"] == 0, r

lignes = [json.loads(l) for l in open(organize.REVUE, encoding="utf-8")]
assert len(lignes) == 2
assert lignes[0]["verdict_modele"] == "same_unit", lignes[0]
assert lignes[0]["statut_revue"] == "en_attente"
assert lignes[0]["origine"] == f"ticket:{ticket}"
print("file de revue : OK  ->", lignes[0]["verdict_modele"])

# ------------------------------------- 4. la paire omise n'est pas « faite »
faits = {l.strip() for l in open(organize.FAITES, encoding="utf-8") if l.strip()}
assert len(faits) == 3, faits
assert cles[3] not in faits, "la paire omise a ete marquee tranchee a tort"
print("paire omise NON marquee tranchee : OK")

# ------------------------ 5. ticket draine sans reponse -> paires liberees
escalation.resolve(ticket, "traite")       # deplace vers done/
libere = organize._purger_en_ticket()
print("paires liberees apres drainage :", libere)
restantes = {l.strip() for l in open(organize.EN_TICKET, encoding="utf-8") if l.strip()}
assert cles[3] not in restantes, "la paire non repondue reste bloquee"
assert lot2 <= restantes, "les paires du ticket encore en attente ont ete liberees a tort"
print("purge : OK  (le ticket encore en file est preserve)")

# --------------------------------- 6. ask_safe silencieux quand T1 absent
led2 = LedgerFactice()
out = local_llm.ask_safe("s", "u", {"x": "bool"}, ledger=led2, agent="test")
assert out is None
assert led2.constats == [], "ask_safe a journalise une panne alors que T1 est declare absent"
ok, msg = local_llm.health()
assert ok, msg
print("ask_safe silencieux : OK  | health :", msg)

print("\nTOUS LES ESSAIS PASSENT")
