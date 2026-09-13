"""sitemap.py — Découverte des annonces par le sitemap XML que le site publie.

POURQUOI CE MODULE EXISTE. Le 2026-09-12, robots.txt de fazwaz.com a ajouté
`Disallow: /*?*order_by=`. Or `order_by=user_updated_at|desc` était ce qui
faisait tenir un catalogue de ~84 000 condos Bangkok dans une fenêtre de
150 pages : sans tri par fraîcheur, la fenêtre couvre 2,7 % du catalogue
(mesure du 2026-08-23 : ~2 800 pages) et la majorité des nouveautés n'est
jamais vue. Le MÊME robots.txt déclare `Sitemap: …/sitemap-listings.xml` —
le canal de découverte que le site publie LUI-MÊME à destination des robots,
avec un `<lastmod>` par annonce. C'est exactement le signal que donnait
`order_by=user_updated_at`, sans le paramètre interdit, et sur le catalogue
ENTIER. On ne contourne rien : on lit ce que le site demande de lire.

MESURÉ le 2026-09-13 sur fazwaz.com :
  - 27 fichiers × 8 000 URL = 213 683 annonces nationales, 75 Mo ;
  - 84 534 condos Bangkok (49 019 location, 35 515 vente) — notre base n'en
    portait que 10 915 actives ;
  - 17/17 URL tirées au sort (7 que notre base croyait délistées, 5 inconnues,
    4 datées 2020-2023) répondent 200 avec un prix affiché : le sitemap décrit
    le stock VIVANT, et c'est notre fenêtre de 150 pages qui délistait à tort
    (~300 « retirées » par jour au ledger, cf. journal du 2026-09-13).

CE QUE `lastmod` VEUT DIRE, ET CE QU'ON EN FAIT. Hypothèse (non prouvée, mais
c'est le champ que `user_updated_at` triait) : la date de dernière mise à jour
de l'annonce côté site. Une annonce dont `lastmod` est antérieur à notre
`last_seen` n'a pas bougé depuis notre dernier passage → on la confirme sans
rouvrir sa fiche (le rôle que jouait le prix lu en page de liste dans la
dédup incrémentale). Le reste se visite, fraîcheur d'abord, sous un budget
par run pour que la reprise du retard (11 135 inconnues + 5 825 à réactiver
dans la fenêtre de 60 j) s'étale sur des jours et non sur une nuit.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
# Un bloc <url> par annonce ; <lastmod> et <image:loc> sont optionnels dans
# la norme, on ne suppose donc pas leur ordre ni leur présence.
_URL_BLOC_RE = re.compile(r"<url>(.*?)</url>", re.S)
_LASTMOD_RE = re.compile(r"<lastmod>\s*([^<\s]+)\s*</lastmod>")
_IMAGE_RE = re.compile(r"<image:loc>\s*([^<\s]+)\s*</image:loc>")


def parse_index(xml: str) -> list[str]:
    """URLs des fichiers listés par un index de sitemap (vide si ce n'en est pas un)."""
    if "<sitemapindex" not in xml:
        return []
    return _LOC_RE.findall(xml)


def parse_shard(xml: str) -> list[dict]:
    """Entrées `{url, lastmod, image}` d'un fichier sitemap (lastmod/image = None si absents)."""
    entrees = []
    for bloc in _URL_BLOC_RE.findall(xml):
        m = _LOC_RE.search(bloc)
        if not m:
            continue
        lm = _LASTMOD_RE.search(bloc)
        im = _IMAGE_RE.search(bloc)
        entrees.append({"url": m.group(1), "lastmod": lm.group(1) if lm else None,
                        "image": im.group(1) if im else None})
    return entrees


def _aware(iso: str) -> datetime:
    d = datetime.fromisoformat(iso)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def age_jours(lastmod: str, maintenant: datetime | None = None) -> float:
    maintenant = maintenant or datetime.now(timezone.utc)
    return (maintenant - _aware(lastmod)).total_seconds() / 86400


def deja_vu_depuis(last_seen: str | None, lastmod: str | None) -> bool:
    """Vrai si notre dernier passage est postérieur à la dernière modification
    déclarée par le site : rien n'a bougé, inutile de rouvrir la fiche.
    Sans l'une des deux dates on ne peut rien affirmer → False (on visite)."""
    if not last_seen or not lastmod:
        return False
    try:
        return _aware(last_seen) >= _aware(lastmod)
    except ValueError:
        return False


def trier(existing: dict | None, lastmod: str | None, fenetre_jours: float,
          budget_dispo: bool, a_images: bool,
          maintenant: datetime | None = None) -> str:
    """Que faire d'une annonce vue dans le sitemap : `visiter`, `confirmer`,
    `reporter` ou `ignorer`.

    Trois faits pèsent, dans cet ordre :
      1. PRÉSENTE DANS LE SITEMAP = VIVANTE (mesure 17/17). Une annonce active
         chez nous et présente ici se confirme toujours (touch), quel que soit
         l'âge de son lastmod — sinon `last_seen` vieillit et l'agent
         `fraicheur` crie au loup sur du stock parfaitement vivant.
      2. `lastmod` > `last_seen` = MISE À JOUR côté site → il faut rouvrir la
         fiche. Si le budget est épuisé on REPORTE sans toucher : un touch
         écraserait `last_seen` et la mise à jour serait perdue pour toujours.
      3. La FENÊTRE (`fenetre_jours`) ne concerne que ce qu'on ne suit pas
         encore — inconnues, ou délistées chez nous : au-delà, on ignore. C'est
         la définition de série des 150 pages (« ~2 mois de fraîcheur »)
         conservée telle quelle, pour ne pas casser les courbes.
    """
    if lastmod is None:
        return "visiter" if budget_dispo else "reporter"
    if existing is None:
        if age_jours(lastmod, maintenant) >= fenetre_jours:
            return "ignorer"
        return "visiter" if budget_dispo else "reporter"

    vu = deja_vu_depuis(existing.get("last_seen"), lastmod)
    if existing.get("status") == "active":
        if vu and a_images:
            return "confirmer"
        if budget_dispo:
            return "visiter"          # mise à jour côté site, ou photos manquantes
        return "confirmer" if vu else "reporter"

    # délistée chez nous (à tort ou à raison) : réactivation soumise à la fenêtre
    if age_jours(lastmod, maintenant) >= fenetre_jours:
        return "ignorer"
    if budget_dispo:
        return "visiter"
    return "confirmer" if vu else "reporter"


# ───────────────────────── cache disque ─────────────────────────
# Le run vente et le run location sont deux PROCESSUS (agents.json enchaîne
# `--deal-type sale` puis `rent`) : sans cache, chacun retélécharge 75 Mo en
# 27 requêtes. Le site régénère ses sitemaps une fois par nuit (lastmod de
# l'index ≈ 02:00 Bangkok), un cache de quelques heures ne perd rien.

def lire_cache(chemin: Path, max_age_minutes: float) -> list[dict] | None:
    try:
        data = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if time.time() - float(data.get("fetched_at", 0)) > max_age_minutes * 60:
        return None
    return data.get("entrees") or None


def ecrire_cache(chemin: Path, entrees: list[dict]) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps({"fetched_at": time.time(), "entrees": entrees}),
                      encoding="utf-8")
