"""alert.py — deux canaux, deux usages.

  CHANGELOG.md  journal exhaustif, append-only : tout run, tout finding, toute
                modification faite par Claude. C'est la trace d'audit.
  E-mail        SÉVÉRITÉ HAUTE uniquement (scrap cassé, panne muette du modèle,
                modification de code, purge refusée). Évite la fatigue d'alerte.

L'e-mail n'est pas envoyé par ce module : il n'y a pas de SMTP configuré sur la
machine, et en ajouter un signifierait stocker un mot de passe applicatif en
clair. À la place, on dépose une demande dans queue/ que la session Claude
planifiée envoie via le connecteur Gmail — elle est déjà authentifiée.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDITS = os.path.join(ROOT, "audits")
CHANGELOG = os.path.join(AUDITS, "CHANGELOG.md")
MAILBOX = os.path.join(ROOT, "queue", "mail")

HEADER = """# Journal des agents — Lowi BKK

Append-only. Une ligne par événement. Ne pas réécrire l'historique : c'est la
trace d'audit du système. Les alertes de sévérité haute partent en plus par
e-mail (voir agents/core/alert.py).

| Horodatage (UTC) | Agent | Niveau | Événement |
|---|---|---|---|
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(agent: str, severity: str, event: str) -> None:
    """Ajoute une ligne au CHANGELOG. Toujours appelé, quel que soit le niveau."""
    os.makedirs(AUDITS, exist_ok=True)
    if not os.path.exists(CHANGELOG):
        with open(CHANGELOG, "w", encoding="utf-8") as f:
            f.write(HEADER)
    safe = event.replace("|", "/").replace("\n", " ").strip()
    with open(CHANGELOG, "a", encoding="utf-8") as f:
        f.write(f"| {_now()} | {agent} | {severity} | {safe} |\n")


def alert(agent: str, subject: str, body: str, severity: str = "high") -> None:
    """Journalise TOUJOURS ; ne dépose une demande d'e-mail que si sévérité haute."""
    log(agent, severity, subject)
    if severity != "high":
        return
    os.makedirs(MAILBOX, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
    payload = {
        "to": "schoenauer.anthony@gmail.com",
        "subject": f"[Lowi BKK] {subject}",
        "body": body,
        "agent": agent,
        "created_at": _now(),
    }
    path = os.path.join(MAILBOX, f"{stamp}-{agent}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def pending_mail() -> list[dict]:
    if not os.path.isdir(MAILBOX):
        return []
    out = []
    for fn in sorted(os.listdir(MAILBOX)):
        if fn.endswith(".json"):
            try:
                d = json.load(open(os.path.join(MAILBOX, fn), encoding="utf-8"))
                d["_file"] = fn
                out.append(d)
            except json.JSONDecodeError:
                continue
    return out


def mark_sent(filename: str) -> None:
    path = os.path.join(MAILBOX, filename)
    if os.path.exists(path):
        os.remove(path)
