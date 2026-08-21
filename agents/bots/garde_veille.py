"""garde-veille — pose la demande d'éveil Windows pour tout le cycle, et
distingue une interruption due à la veille d'une vraie panne.

Contexte (2026-08-16) : deux cycles d'affilée, extract-ddproperty coupé net en
pleine extraction par une mise en veille moderne (`Kernel-Power`, motif
« Idle Timeout »). Sans ce garde-fou, un run `interrompu` par la veille se
confond avec un run `interrompu` par une vraie panne (réseau mort, exception
non attrapée) — watch-health et overseer n'ont aucun moyen de faire la
différence, alors que la réponse n'est pas la même : rien à corriger dans le
premier cas (la cadence relance déjà l'agent au cycle suivant, cf. is_due()),
un bug à diagnostiquer dans le second.

Ce que cet agent NE fait PAS : relancer lui-même l'agent coupé. Inutile —
`orchestrator.is_due()` se fonde sur le dernier succès, pas sur le dernier
run ; un `interrompu` n'est jamais un succès, donc l'agent concerné est déjà
« dû » et repart de lui-même dans la même lane, juste après garde-veille. La
seule vraie correction ici est le verrou d'éveil ; la détection sert à ne pas
crier au loup sur watch-health/overseer pour une coupure déjà auto-corrigée.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timedelta, timezone

from agents.core import wake_lock

#: Un peu plus large qu'un cycle mesuré (2 h à 6,2 h) pour ne rien manquer.
FENETRE_HEURES = 30

_DATE_RE = re.compile(r"/Date\((\d+)\)/")


def _parse_date_ps(brut: str) -> datetime | None:
    """PowerShell (Windows PowerShell 5.1, pas pwsh) sérialise les DateTime en
    JSON legacy `/Date(ms_epoch)/` — pas en ISO 8601. Vérifié le 2026-08-16."""
    m = _DATE_RE.match(brut)
    if not m:
        return None
    return datetime.fromtimestamp(int(m.group(1)) / 1000, tz=timezone.utc)


def _evenements_veille(depuis: datetime, jusqu_a: datetime) -> list[tuple[datetime, int]]:
    """Journal Système, `Microsoft-Windows-Kernel-Power`, Id 506 (entrée en
    veille) / 507 (sortie). ~1-2 s via PowerShell — appelé une fois par
    cycle, pas par agent.

    ⚠ `Get-WinEvent -FilterHashtable` interprète StartTime/EndTime en HEURE
    LOCALE, jamais en UTC — vérifié le 2026-08-16 en comparant les événements
    trouvés à `Get-Date`. Un ledger en UTC passé tel quel décale la fenêtre de
    l'écart local (+7 h à Bangkok) et fait manquer les coupures les plus
    récentes, exactement celles qu'on cherche."""
    debut = depuis.astimezone().strftime("%Y-%m-%dT%H:%M:%S")
    fin = jusqu_a.astimezone().strftime("%Y-%m-%dT%H:%M:%S")
    ps = (
        "Get-WinEvent -FilterHashtable @{LogName='System';"
        "ProviderName='Microsoft-Windows-Kernel-Power'; Id=506,507;"
        f"StartTime='{debut}';EndTime='{fin}'}} -ErrorAction SilentlyContinue |"
        " Select-Object Id,TimeCreated | ConvertTo-Json -Compress"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if out.returncode != 0 or not out.stdout.strip():
        return []
    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = [data]
    resultat = []
    for e in data:
        d = _parse_date_ps(e.get("TimeCreated", ""))
        if d is not None:
            resultat.append((d, e.get("Id")))
    return resultat


def run(led, run_id: int, lane: str, spec: dict) -> dict:
    verrou_pose = wake_lock.acquire()

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=FENETRE_HEURES)).isoformat()
    interrompus = led.conn.execute(
        "select id, agent, started_at, ended_at from agent_runs"
        " where status='interrompu' and started_at >= ? order by started_at",
        (cutoff,)).fetchall()

    if not interrompus:
        return {"verrou_veille_pose": verrou_pose, "runs_interrompus_examines": 0,
                "coupures_veille_detectees": 0}

    debut_fenetre = min(datetime.fromisoformat(r["started_at"]) for r in interrompus)
    veilles = _evenements_veille(debut_fenetre, datetime.now(timezone.utc))
    entrees_veille = [d for d, i in veilles if i == 506]

    detectees = 0
    for r in interrompus:
        debut = datetime.fromisoformat(r["started_at"])
        fin = datetime.fromisoformat(r["ended_at"]) if r["ended_at"] else datetime.now(timezone.utc)
        coupe_par_veille = any(debut <= v <= fin for v in entrees_veille)
        if not coupe_par_veille:
            continue
        detectees += 1
        led.finding(
            r["agent"], "low", "coupure_veille",
            f"{r['agent']} interrompu par une mise en veille (run #{r['id']}), "
            f"pas une panne — relancé automatiquement au prochain cycle dû.",
            {"run_id": r["id"], "started_at": r["started_at"], "ended_at": r["ended_at"]},
            run_id)

    return {"verrou_veille_pose": verrou_pose,
            "runs_interrompus_examines": len(interrompus),
            "coupures_veille_detectees": detectees}
