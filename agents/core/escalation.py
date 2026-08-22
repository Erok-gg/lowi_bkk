"""escalation.py — passer la main à Claude.

Il n'y a ni CLI `claude` ni clé API sur la machine. L'escalade est donc une FILE
DE TICKETS sur disque, drainée par une tâche planifiée Claude Code — qui, elle,
a l'accès au dépôt et aux outils, et peut donc vraiment réparer un adaptateur et
committer. Latence : bornée par la fréquence de cette tâche, pas instantanée.

Un ticket doit être auto-portant : la session qui le lit n'a pas cette
conversation. Il porte les preuves, pas seulement le symptôme.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE = os.path.join(ROOT, "queue")
DONE = os.path.join(QUEUE, "done")

SEVERITIES = ("low", "medium", "high")


def create(agent: str, kind: str, severity: str, subject: str,
           evidence: dict, asked_of_claude: str, ledger=None) -> str:
    """Écrit un ticket et le déclare au ledger. Rend le nom du ticket."""
    assert severity in SEVERITIES, severity
    os.makedirs(QUEUE, exist_ok=True)
    os.makedirs(DONE, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
    name = f"{stamp}-{agent}-{kind}.json"
    # L'horodatage est à la SECONDE : deux escalades du même agent et du même
    # motif dans la même seconde portaient le même nom, et la seconde écrasait
    # la première SANS BRUIT — une escalade perdue, donc invisible. Trouvé en
    # testant le dépôt de tickets le 2026-08-21.
    n = 2
    while os.path.exists(os.path.join(QUEUE, name)):
        name = f"{stamp}-{agent}-{kind}-{n}.json"
        n += 1

    payload = {
        "ticket": name,
        "agent": agent,
        "kind": kind,
        "severity": severity,
        "subject": subject,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "skill": f"agents/skills/{agent}/SKILL.md",
        "evidence": evidence,
        "asked_of_claude": asked_of_claude,
        "garde_fous": [
            "Toute modification de code part sur une BRANCHE dédiée, jamais sur main.",
            "Aucune fusion ni suppression d'annonces : findings uniquement.",
            "Consigner la résolution dans agents/audits/CHANGELOG.md.",
        ],
    }
    with open(os.path.join(QUEUE, name), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    if ledger is not None:
        ledger.escalate(name, agent, kind, severity)
    return name


def pending() -> list[dict]:
    if not os.path.isdir(QUEUE):
        return []
    out = []
    for fn in sorted(os.listdir(QUEUE)):
        if fn.endswith(".json"):
            try:
                out.append(json.load(open(os.path.join(QUEUE, fn), encoding="utf-8")))
            except json.JSONDecodeError:
                continue
    return out


def resolve(ticket: str, resolution: str, ledger=None) -> bool:
    """Déplace le ticket vers done/ en y ajoutant la résolution."""
    src = os.path.join(QUEUE, ticket)
    if not os.path.exists(src):
        return False
    payload = json.load(open(src, encoding="utf-8"))
    payload["resolution"] = resolution
    payload["resolved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    os.makedirs(DONE, exist_ok=True)
    with open(os.path.join(DONE, ticket), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.remove(src)
    if ledger is not None:
        ledger.resolve(ticket, resolution)
    return True
