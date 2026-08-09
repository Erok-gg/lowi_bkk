"""overseer — vérifier le travail des onze autres.

Il ne juge pas au feeling : il compare une sortie observée à un contrat déclaré
dans le SKILL.md de chaque agent, et relit le ledger. C'est ce qui rend vraie la
promesse du deck — « auditable from a human perspective ».

CE QU'IL NE FAIT PAS : aucune tâche métier. S'il arbitrait les doublons ou
calculait une statistique, il en deviendrait partie prenante et ne pourrait plus
l'auditer. Son indépendance est sa seule valeur.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone

from agents.core import alert, escalation, local_llm
from agents.orchestrator import is_due

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")
AUDITS = os.path.join(ROOT, "audits")
REGISTRY = json.load(open(os.path.join(ROOT, "agents.json"), encoding="utf-8"))

SYSTEM = """Tu rédiges un audit en français clair, pour quelqu'un qui n'a pas suivi le cycle.
Une phrase par agent : ce qui a été fait, et ce qui cloche s'il y a lieu.
Pas de jargon, pas de JSON recopié, pas de superlatif.
Réponds UNIQUEMENT en JSON : {"resume":"<80 mots", "point_dattention":"<30 mots ou vide"}"""


def contrat_de(agent: str) -> set[str]:
    """Champs de PREMIER NIVEAU du contrat déclaré dans le SKILL.md.

    Le suivi de profondeur est nécessaire : plusieurs contrats imbriquent une
    liste d'objets (`detail`), dont les clés ne sont pas des champs attendus au
    premier niveau."""
    path = os.path.join(SKILLS, agent, "SKILL.md")
    if not os.path.exists(path):
        return set()
    src = open(path, encoding="utf-8").read()
    m = re.search(r"## Contrat de sortie\s*```json\s*(.*?)```", src, re.S)
    if not m:
        return set()

    bloc, champs, profondeur, i = m.group(1), set(), 0, 0
    while i < len(bloc):
        c = bloc[i]
        if c in "{[":
            profondeur += 1
        elif c in "}]":
            profondeur -= 1
        elif c == '"':
            fin = bloc.find('"', i + 1)
            if fin == -1:
                break
            mot = bloc[i + 1:fin]
            reste = bloc[fin + 1:].lstrip()
            if profondeur == 1 and reste.startswith(":"):
                champs.add(mot)
            i = fin
        i += 1
    return champs


def run(led, run_id: int, lane: str, spec: dict) -> dict:
    depuis = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(timespec="seconds")
    runs = [r for r in led.runs_since(depuis) if r["agent"] != "overseer"]

    honores, violes, lignes = 0, 0, []
    vus = set()

    for r in runs:
        agent = r["agent"]
        vus.add(agent)
        attendus = contrat_de(agent)
        try:
            metrics = json.loads(r["metrics"] or "{}")
        except json.JSONDecodeError:
            metrics = {}

        manquants = attendus - set(metrics) if attendus else set()
        if r["status"] == "ok" and not manquants:
            honores += 1
            etat = "contrat honoré"
        else:
            violes += 1
            etat = (f"statut={r['status']}"
                    + (f", champs manquants : {', '.join(sorted(manquants))}"
                       if manquants else ""))
            led.finding("overseer", "medium", "contrat_viole",
                        f"{agent} : {etat}",
                        {"agent": agent, "run": r["id"], "manquants": sorted(manquants)},
                        run_id)
        lignes.append(f"{agent} ({r['status']}) — {etat} — "
                      f"{json.dumps(metrics, ensure_ascii=False)[:160]}")

    # Un agent MUET est plus inquiétant qu'un agent en erreur : c'est la signature
    # d'une tâche qui ne se déclenche plus. Les 3 tâches Windows étaient invisibles
    # ainsi pendant trois semaines.
    #
    # "dû" ici doit suivre le MÊME calcul que l'orchestrateur (is_due, cadence
    # every_days par agent) — pas seulement "appartient à cette lane". Bug trouvé
    # le 2026-08-09 : la version précédente comparait TOUT agent de la lane contre
    # une fenêtre d'observation d'1 jour (depuis, ligne ~66), alors que la plupart
    # des agents daily ont une cadence de 4 jours (voire 7/14). Résultat : un faux
    # positif "agent_muet" sévérité haute + email quasi chaque jour, sur des agents
    # parfaitement à jour — bruit qui aurait masqué une vraie panne. Vu sur 4
    # tickets consécutifs (07-31, 08-01, 08-06, 08-08) avant d'être diagnostiqué.
    dus = [a["name"] for a in REGISTRY["agents"]
           if lane in a.get("lanes", []) and a["name"] != "overseer"
           and is_due(led, a)[0]]
    muets = [a for a in dus if a not in vus]
    for a in muets:
        led.finding("overseer", "high", "agent_muet",
                    f"{a} n'a produit aucun run sur ce cycle alors qu'il était dû",
                    {"agent": a, "lane": lane}, run_id)

    # Rédaction : le modèle local met en français ; s'il tombe, on garde le brut.
    resume = " · ".join(lignes[:12]) or "Aucun run sur la période."
    red = local_llm.ask_safe(
        SYSTEM,
        f"Cycle « {lane} ». {len(runs)} run(s).\n" + "\n".join(lignes[:12])
        + (f"\nAgents muets : {', '.join(muets)}" if muets else ""),
        {"resume": "str", "point_dattention": "str"},
        ledger=led, agent="overseer", run_id=run_id, num_predict=500)
    if red:
        resume = red["resume"]

    escalades = 0
    if muets:
        escalation.create(
            agent="overseer", kind="agent_muet", severity="high",
            subject=f"{len(muets)} agent(s) muet(s) sur le cycle {lane} : {', '.join(muets)}",
            evidence={"muets": muets, "lane": lane, "runs_observes": len(runs)},
            asked_of_claude="Un agent dû qui ne produit aucun run signale une tâche qui ne "
                            "se déclenche plus. Vérifier la tâche LowiBKK-Agents "
                            "(Export-ScheduledTask, chercher des guillemets échappés dans "
                            "<Arguments>) puis le module de l'agent.",
            ledger=led)
        escalades += 1
        alert.alert("overseer", f"Agents muets sur le cycle {lane}",
                    f"{', '.join(muets)} n'ont produit aucun run alors qu'ils étaient dus.")

    # Écriture de l'audit lisible
    os.makedirs(AUDITS, exist_ok=True)
    jour = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = os.path.join(AUDITS, f"{jour}.md")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"\n## Cycle « {lane} » — {datetime.now(timezone.utc):%H:%M} UTC\n\n")
        f.write(resume.strip() + "\n\n")
        if red and red.get("point_dattention", "").strip():
            f.write(f"**Point d'attention** — {red['point_dattention'].strip()}\n\n")
        if muets:
            f.write(f"**Agents muets** : {', '.join(muets)}\n\n")
        f.write("| agent | statut | métriques |\n|---|---|---|\n")
        for r in runs:
            m = (r["metrics"] or "{}").replace("|", "/")[:120]
            f.write(f"| {r['agent']} | {r['status']} | `{m}` |\n")

    return {"runs_verifies": len(runs), "contrats_honores": honores,
            "contrats_violes": violes, "agents_muets": muets,
            "escalades": escalades, "audit": path}
