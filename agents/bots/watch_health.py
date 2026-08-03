"""watch-health — voir qu'un scrap est cassé le jour où il casse.

Le bug FazWaz du 2026-07-23 (0 annonce, corrigé par 0980a1f) a couru plusieurs
jours sans détection. Cet agent existe pour ça.

Signature d'un parseur cassé par changement de DOM :
    volume effondré à zéro AVEC zéro trace d'erreur
Le site répond, on ne comprend plus sa réponse. C'est le cas qui échappe à toute
surveillance naïve fondée sur les codes HTTP.
"""
from __future__ import annotations

import json
import os
import statistics

from agents.core import alert, escalation, local_llm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = json.load(open(os.path.join(ROOT, "agents.json"), encoding="utf-8"))
EXTRACTEURS = [a for a in REGISTRY["agents"] if a["famille"] == "Extraction"]

SYSTEM = """Tu rédiges un constat court en français à partir de chiffres de supervision.
Tu ne juges pas, tu décris. Une phrase, factuelle, sans jargon.
Réponds UNIQUEMENT en JSON : {"constat":"<25 mots"}"""


def _metrics(row) -> dict:
    try:
        return json.loads(row["metrics"] or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


def _classer(nouvelles: int | None, erreurs: int, mediane: float | None,
             bande: list | None) -> tuple[str, str]:
    """Rend (verdict, sévérité)."""
    if nouvelles is None:
        return "metriques_absentes", "medium"
    if nouvelles == 0 and erreurs == 0:
        return "parseur_casse", "high"
    if nouvelles == 0 and erreurs > 0:
        return "panne_reseau", "high"
    if mediane and mediane > 0 and nouvelles < 0.25 * mediane:
        return "derive", "medium"
    if bande and nouvelles > bande[1]:
        return "volume_anormal", "low"
    return "ok", "low"


def run(led, run_id: int, lane: str, spec: dict) -> dict:
    detail, anomalies, escalades = [], 0, 0

    for ext in EXTRACTEURS:
        name = ext["name"]
        last = led.last_run(name, only_ok=True)
        if last is None:
            detail.append({"source": name, "verdict": "jamais_execute"})
            continue

        m = _metrics(last)
        nouvelles = m.get("nouvelles")
        erreurs = m.get("traces_erreur", 0)

        histo = [_metrics(r).get("nouvelles") for r in led.recent_runs(name, 10)]
        histo = [h for h in histo if isinstance(h, int)]
        mediane = statistics.median(histo) if len(histo) >= 3 else None
        bande = (ext.get("bandes") or {}).get("nouvelles")

        verdict, severite = _classer(nouvelles, erreurs, mediane, bande)
        detail.append({"source": name, "verdict": verdict, "nouvelles": nouvelles,
                       "mediane": mediane, "erreurs": erreurs})

        if verdict == "ok":
            continue
        anomalies += 1

        # Le modèle local ne sert qu'à rédiger ; s'il tombe, on garde le constat brut.
        phrase = f"{name} : {verdict} (nouvelles={nouvelles}, médiane={mediane})"
        red = local_llm.ask_safe(
            SYSTEM,
            f"Source {name}. Verdict technique : {verdict}. "
            f"Nouvelles annonces ce run : {nouvelles}. Médiane des 10 derniers : {mediane}. "
            f"Traces d'erreur : {erreurs}.",
            {"constat": "str"}, ledger=led, agent="watch-health", run_id=run_id)
        if red:
            phrase = red["constat"]

        led.finding(name, severite, verdict, phrase,
                    {"nouvelles": nouvelles, "mediane": mediane, "erreurs": erreurs,
                     "run_id": last["id"]}, run_id)

        # Escalade : deux runs consécutifs à zéro, jamais sur un seul.
        if verdict == "parseur_casse":
            avant = led.recent_runs(name, 2)
            zeros = sum(1 for r in avant if _metrics(r).get("nouvelles") == 0)
            if zeros >= 2:
                escalation.create(
                    agent=name, kind="parser_break", severity="high",
                    subject=f"{name} : 0 annonce sur 2 runs consécutifs, sans erreur HTTP",
                    evidence={"runs": [r["id"] for r in avant], "mediane_historique": mediane,
                              "bande_attendue": bande, "observe": 0,
                              "log": last["log_path"]},
                    asked_of_claude=(
                        f"Diagnostiquer le parsing de {name} : le site répond mais la "
                        f"structure n'est plus reconnue. Inspecter une page de liste réelle, "
                        f"identifier le changement, proposer un correctif SUR UNE BRANCHE. "
                        f"Précédent identique : commit 0980a1f (FazWaz, 2026-07-23)."),
                    ledger=led)
                escalades += 1
                alert.alert(name, f"{name} ne ramène plus rien (parseur probablement cassé)",
                            f"Deux runs consécutifs à 0 annonce sans erreur HTTP.\n"
                            f"Médiane historique : {mediane}\nLog : {last['log_path']}\n"
                            f"Un ticket a été déposé pour Claude.")

    return {"sources_verifiees": len(EXTRACTEURS), "anomalies": anomalies,
            "escalades": escalades, "detail": detail}
