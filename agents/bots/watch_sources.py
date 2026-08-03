"""watch-sources — étendre la couverture sans que ça dépende de ta mémoire.

Sonde des sources candidates, repère celles qui ont un blob structuré exploitable,
et escalade l'écriture d'un adaptateur. Respecte la posture du projet : une source
qui interdit explicitement le crawl n'est jamais proposée.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

from agents.core import escalation

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "state", "watch-sources")
REGISTRE = os.path.join(STATE, "registre.json")

CANDIDATES_INITIALES = [
    {"nom": "hipflat", "url": "https://www.hipflat.co.th/en/market/bangkok-c1"},
    {"nom": "thailand-property", "url": "https://www.thailand-property.com/condos-for-sale/bangkok"},
    {"nom": "baania", "url": "https://www.baania.com/en/listing/bangkok"},
    {"nom": "dotproperty", "url": "https://www.dotproperty.co.th/en/condos-for-sale/bangkok"},
]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _fetch(url: str, timeout: int = 20) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept-Language": "en-US,en;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(400_000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, ""


def _robots_permissif(url: str) -> bool:
    """Prudent par défaut : on ne propose pas une source qui interdit tout."""
    m = re.match(r"(https?://[^/]+)", url)
    if not m:
        return False
    code, txt = _fetch(m.group(1) + "/robots.txt", timeout=10)
    if code != 200 or not txt:
        return True   # illisible → autorisé par défaut (RFC), comme pipeline/fetch.py
    bloc = re.split(r"user-agent:\s*\*", txt, flags=re.I)
    if len(bloc) < 2:
        return True
    return not re.search(r"^\s*disallow:\s*/\s*$", bloc[1], re.I | re.M)


def _sonder(c: dict) -> dict:
    code, html = _fetch(c["url"])
    blob = None
    if "__NEXT_DATA__" in html:
        blob = "__NEXT_DATA__"
    elif re.search(r'type=["\']application/ld\+json', html):
        blob = "ld+json"
    elif "window.__NUXT__" in html:
        blob = "__NUXT__"
    # ordre de grandeur : compter les liens ressemblant à des fiches
    annonces = len(set(re.findall(r'href="([^"]*(?:condo|property|listing)[^"]*)"', html)))
    permissif = _robots_permissif(c["url"]) if code == 200 else False
    prometteuse = bool(code == 200 and blob and annonces >= 20 and permissif)
    return {**c, "http": code, "blob": blob, "liens_fiches": annonces,
            "robots_permissif": permissif, "prometteuse": prometteuse}


def run(led, run_id: int, lane: str, spec: dict) -> dict:
    os.makedirs(STATE, exist_ok=True)
    if os.path.exists(REGISTRE):
        registre = json.load(open(REGISTRE, encoding="utf-8"))
    else:
        registre = {"candidates": CANDIDATES_INITIALES, "connues_prometteuses": []}

    resultats = [_sonder(c) for c in registre["candidates"]]
    deja = set(registre.get("connues_prometteuses", []))
    nouvelles = [r["nom"] for r in resultats if r["prometteuse"] and r["nom"] not in deja]

    escalades = 0
    for r in resultats:
        if r["nom"] not in nouvelles:
            continue
        escalation.create(
            agent="watch-sources", kind="nouvelle_source", severity="low",
            subject=f"Source candidate exploitable : {r['nom']}",
            evidence=r,
            asked_of_claude=(
                f"Écrire scraper/adapters/{r['nom']}.py (implémente base.py) et "
                f"scraper/config/{r['nom']}.json. Blob repéré : {r['blob']}. "
                f"Respecter la posture du projet : freehold uniquement, cadence ~hebdo, "
                f"robots.txt respecté. SUR UNE BRANCHE."),
            ledger=led)
        escalades += 1
        led.finding("watch-sources", "low", "nouvelle_source",
                    f"{r['nom']} devient exploitable ({r['blob']}, "
                    f"{r['liens_fiches']} fiches repérées)", r, run_id)

    registre["connues_prometteuses"] = sorted(deja | set(nouvelles))
    registre["dernier_sondage"] = resultats
    json.dump(registre, open(REGISTRE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    return {"sondees": len(resultats),
            "prometteuses": sum(1 for r in resultats if r["prometteuse"]),
            "nouvelles_prometteuses": nouvelles, "escalades": escalades}
