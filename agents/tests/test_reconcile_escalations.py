"""test_reconcile_escalations.py — le ledger ne doit pas mentir sur les escalades.

POURQUOI CE TEST EXISTE
Le 2026-08-29, `orchestrator status` affichait « 12 escalades ouvertes » datant du
2026-07-31/08-01. Les 12 tickets étaient pourtant déjà dans `queue/done/`, résolus
par des sessions passées qui avaient édité/déplacé le fichier à la main au lieu
d'appeler `escalation.resolve()` — le seul chemin qui met aussi à jour le ledger.
Le compteur ne pouvait donc que croître, jamais décroître : un garde-fou qui ment
(règle 2 de CLAUDE.md). `escalation.reconcile()` referme dans le ledger toute
escalade dont le ticket est déjà dans `queue/done/`, quel que soit le chemin par
lequel il y est arrivé.

Ce qu'il verrouille, dans l'ordre :
  1. un ticket déjà dans queue/done/ mais encore 'open' en base est refermé ;
  2. un ticket encore dans queue/ (jamais traité) n'est PAS refermé à tort ;
  3. un ticket déjà 'done' en base n'est pas retraité (idempotence) ;
  4. le nombre rendu = le nombre réellement réconcilié, pas le total ouvert.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_reconcile_escalations.py

Tout est redirigé vers un dossier temporaire : ni la vraie file de tickets ni le
vrai ledger.db ne sont touchés.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from agents.core import escalation                      # noqa: E402

tmp = tempfile.mkdtemp(prefix="lowi-reconcile-")
escalation.QUEUE = os.path.join(tmp, "queue")
escalation.DONE = os.path.join(escalation.QUEUE, "done")
os.makedirs(escalation.DONE, exist_ok=True)


class LedgerFactice:
    """Reproduit juste ce dont reconcile() a besoin : open_escalations() + resolve()."""

    def __init__(self, lignes):
        self.lignes = lignes          # liste de dicts, comme des sqlite3.Row
        self.resolutions = []

    def open_escalations(self):
        return [l for l in self.lignes if l["status"] == "open"]

    def resolve(self, ticket, resolution, status="done"):
        self.resolutions.append((ticket, resolution))
        for l in self.lignes:
            if l["ticket"] == ticket:
                l["status"] = status


# Ticket A : déjà déplacé vers done/ (résolu à la main, ledger jamais notifié).
ticket_a = "2026-07-31T070708-overseer-agent_muet.json"
with open(os.path.join(escalation.DONE, ticket_a), "w", encoding="utf-8") as f:
    json.dump({"ticket": ticket_a, "resolution": "traite a la main"}, f)

# Ticket B : encore dans la file, jamais traité — ne doit pas être touché.
ticket_b = "2026-08-01T030748-watch-sources-nouvelle_source.json"
with open(os.path.join(escalation.QUEUE, ticket_b), "w", encoding="utf-8") as f:
    json.dump({"ticket": ticket_b}, f)

# Ticket C : déjà 'done' en base — ne doit pas repasser par resolve() une 2e fois.
ticket_c = "2026-08-01T033222-overseer-agent_muet.json"
with open(os.path.join(escalation.DONE, ticket_c), "w", encoding="utf-8") as f:
    json.dump({"ticket": ticket_c, "resolution": "deja clos"}, f)

led = LedgerFactice([
    {"ticket": ticket_a, "status": "open"},
    {"ticket": ticket_b, "status": "open"},
    {"ticket": ticket_c, "status": "done"},
])

# ------------------------------------------------------------- 1+2+3. reconcile
n = escalation.reconcile(led)
assert n == 1, f"un seul ticket (A) devait etre reconcilie, pas {n}"
assert led.resolutions == [(ticket_a,
    "Réconcilié automatiquement (orchestrator status) : le ticket était "
    "déjà dans queue/done/ mais le ledger n'avait jamais été mis à jour.")], led.resolutions
statuts = {l["ticket"]: l["status"] for l in led.lignes}
assert statuts[ticket_a] == "done", "A aurait du etre referme"
assert statuts[ticket_b] == "open", "B est encore dans la file, ne doit pas etre touche"
assert statuts[ticket_c] == "done", "C etait deja clos, doit le rester"
print("1re passe : A reconcilie, B intact (encore en file), C intact (deja clos) — OK")

# --------------------------------------------------------------- 4. idempotence
n2 = escalation.reconcile(led)
assert n2 == 0, f"une 2e passe ne doit rien reconcilier de plus, a trouve {n2}"
print("2e passe idempotente : 0 reconciliation supplementaire — OK")

print("\nTOUS LES ESSAIS PASSENT")
