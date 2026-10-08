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
from agents.core.metrics import aplatir

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = json.load(open(os.path.join(ROOT, "agents.json"), encoding="utf-8"))
# Lanes vide = extracteur suspendu à dessein (extract-livinginsider le
# 2026-09-26). Le juger sur son dernier run, figé, relevait « parseur_casse »
# en sévérité haute chaque nuit sur une source arrêtée volontairement (règle 2).
EXTRACTEURS = [a for a in REGISTRY["agents"]
               if a["famille"] == "Extraction" and a.get("lanes")]

# CONSIGNES EN ANGLAIS, CONTENU EN FRANÇAIS.
#
# Mesuré le 2026-08-01 sur 90 paires réelles : des consignes en français donnent
# 12,2 % de sorties internement incohérentes, les mêmes traduites 0 %. La cause
# est la LANGUE DE L'INSTRUCTION, pas le nommage des champs — qwen3 tient mal
# une contrainte de format énoncée en français.
#
# Cet appel exige du JSON, donc c'est bien une sortie contrainte. On traduit
# l'instruction, jamais le résultat : le constat doit rester lisible par un
# francophone.
SYSTEM = """You write ONE short factual sentence from monitoring figures.
Describe, never judge. No jargon, no numbers repeated verbatim.

Reply ONLY with JSON: {"constat":"<25 words"}
The value of "constat" MUST be written in FRENCH."""


def _metrics(row) -> dict:
    """Metriques APLATIES du run : `nouvelles` peut vivre dans les etapes.

    2026-08-23 : cette fonction lisait la racine seule. Depuis le chainage
    `then` (2026-08-06) les extracteurs y rangent {"etapes": [...]}, donc
    `nouvelles` valait None sur 24 runs -> verdict `metriques_absentes`
    (medium, muet) au lieu de `parseur_casse` (high, escalade + mail). Nestopa
    ramenait 0 annonce depuis le 2026-08-17 sans que rien ne le dise."""
    try:
        return aplatir(json.loads(row["metrics"] or "{}"))
    except (json.JSONDecodeError, TypeError):
        return {}


#: Au-delà, les échecs d'images cessent d'être du bruit réseau. Sur le cycle du
#: 2026-08-11 : 1 par source, 3 pour PropertyScout — donc un seuil à 10 ne
#: déclenchera que sur une vraie dégradation, pas sur les aléas d'un CDN.
SEUIL_ERREURS_IMAGES = 10


#: Marqueur écrit par l'adaptateur FazWaz (`_attendre_regeneration`) quand le
#: site n'a pas régénéré son sitemap après 3 h d'attente : il rescanne alors
#: l'ancien, qui ne contient par construction aucune nouvelle annonce.
MARQUEUR_SITEMAP_FIGE = "[sitemap-non-regenere]"


def _sitemap_fige(log_path: str | None) -> bool:
    """Le run a-t-il scanné un sitemap que le site n'avait pas régénéré ?

    2026-10-08 : 3 constats `parseur_casse` (high) en 5 nuits sur FazWaz
    (04/10 ×2, 07/10), tous faux — sonde de structure OK, 0 erreur, sitemap
    non régénéré ; le marqueur est dans les 2 journaux postérieurs à
    l'attente de régénération (runs 702, 733 ; 686 la précède). Chaque
    nuit suivante a repris 130 à 278 nouvelles : rien n'était cassé chez nous.
    Lu dans le journal plutôt que dans les métriques pour ne pas toucher au
    contrat de sortie des extracteurs (et pour couvrir les runs déjà en base)."""
    if not log_path:
        return False
    try:
        with open(log_path, encoding="utf-8", errors="replace") as f:
            return any(MARQUEUR_SITEMAP_FIGE in ligne for ligne in f)
    except OSError:
        return False


def _classer(nouvelles: int | None, erreurs: int, mediane: float | None,
             bande: list | None, err_images: int = 0,
             sitemap_fige: bool = False) -> tuple[str, str]:
    """Rend (verdict, sévérité).

    ⚠ `err_images` est SÉPARÉ des autres erreurs, et c'est le point.
    Jusqu'au 2026-08-11 cette fonction ne voyait que la collecte : une source
    dont toutes les photos échouaient était déclarée SAINE, parce que
    `traces_erreur` et `erreurs_http` restaient à zéro. Le périmètre de la
    mesure, pas le comptage, était en cause — « source saine » voulait dire
    « le scraping va bien », et personne ne le savait.

    L'ordre compte : un parseur cassé prime sur des images perdues.
    """
    if nouvelles is None:
        return "metriques_absentes", "medium"
    # Zéro nouvelle sur un sitemap figé : cause connue et extérieure, pas un
    # parseur cassé. Constat gardé (une nuit sans nouvelles FazWaz reste un
    # trou), mais ni escalade `parser_break` ni mail. La persistance sur deux
    # runs est relevée en `high` dans run(), pas ici.
    if nouvelles == 0 and erreurs == 0 and sitemap_fige:
        return "sitemap_non_regenere", "medium"
    if nouvelles == 0 and erreurs == 0:
        return "parseur_casse", "high"
    if nouvelles == 0 and erreurs > 0:
        return "panne_reseau", "high"
    if mediane and mediane > 0 and nouvelles < 0.25 * mediane:
        return "derive", "medium"
    if bande and nouvelles > bande[1]:
        return "volume_anormal", "low"
    # Les annonces arrivent, mais leurs photos non : la source n'est pas « saine ».
    if err_images >= SEUIL_ERREURS_IMAGES:
        return "images_perdues", "medium"
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

        err_images = m.get("erreurs_images", 0) or 0
        fige = _sitemap_fige(last["log_path"])
        verdict, severite = _classer(nouvelles, erreurs, mediane, bande, err_images,
                                     sitemap_fige=fige)
        # Deux runs d'affilée sur un sitemap figé = le site ne publie plus son
        # sitemap : là, c'est un vrai trou de collecte qui mérite d'être vu.
        if verdict == "sitemap_non_regenere":
            avant = led.recent_runs(name, 2)
            if len(avant) >= 2 and all(_sitemap_fige(r["log_path"]) for r in avant):
                severite = "high"
        detail.append({"source": name, "verdict": verdict, "nouvelles": nouvelles,
                       "mediane": mediane, "erreurs": erreurs,
                       "erreurs_images": err_images})

        if verdict == "ok":
            continue
        anomalies += 1

        # Le modèle local ne sert qu'à rédiger ; s'il tombe, on garde le constat brut.
        phrase = f"{name} : {verdict} (nouvelles={nouvelles}, médiane={mediane})"
        red = local_llm.ask_safe(
            SYSTEM,
            f"Source {name}. Verdict technique : {verdict}. "
            f"Nouvelles annonces ce run : {nouvelles}. Médiane des 10 derniers : {mediane}. "
            f"Traces d'erreur : {erreurs}. Échecs sur les images : {err_images}.",
            {"constat": "str"}, ledger=led, agent="watch-health", run_id=run_id)
        if red:
            phrase = red["constat"]

        led.finding(name, severite, verdict, phrase,
                    {"nouvelles": nouvelles, "mediane": mediane, "erreurs": erreurs,
                     "erreurs_images": err_images, "run_id": last["id"]}, run_id)

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
