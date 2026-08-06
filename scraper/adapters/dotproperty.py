"""dotproperty.py — Adaptateur DotProperty.

⚠ USAGE PRÉVU : VÉRIFICATION UNIQUEMENT, pas une source de production.

Investigation du 2026-08-05 (voir agents/state/watch-sources/registre.json et
docs/journal-technique.md) : 90/90 annonces échantillonnées sur 3 pages
indépendantes chargent leurs photos EXCLUSIVEMENT depuis cdn.fazwaz.com /
img.fazwaz.com — DotProperty Bangkok semble syndiquer FazWaz, déjà scrapé.
Cet adaptateur sert à vérifier l'hypothèse sur 3 runs indépendants
(ops/verif-dotproperty.py) avant de trancher définitivement.

Les pages `/en/condos-for-sale/bangkok` et `/en/condos-for-rent/bangkok`
exposent un ld+json `ItemList` COMPLET (prix, chambres, adresse, geo, image) —
contrairement à LivingInsider, aucune fiche détail n'est nécessaire, tout vient
de la page de liste. Déjà filtré Bangkok par l'URL (pas de filtre à la fiche).
"""
from __future__ import annotations

import json
import re
from typing import Iterator
from urllib.parse import urljoin

from adapters.base import BaseAdapter
from pipeline.fetch import Fetcher

LD_RE = re.compile(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
ID_RE = re.compile(r"[a-f0-9]{4,}-[a-f0-9-]+$", re.I)


def _num(v):
    try:
        return float(v) if v not in (None, "", "null") else None
    except (TypeError, ValueError):
        return None


def _item_list(html: str) -> list[dict]:
    for raw in LD_RE.findall(html):
        try:
            d = json.loads(raw.strip())
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and d.get("@type") == "ItemList":
            return d.get("itemListElement") or []
    return []


class DotpropertyAdapter(BaseAdapter):
    source = "dotproperty"

    def list_urls(self, fetcher: Fetcher, limit: int | None = None) -> Iterator[dict]:
        base = self.config["base_url"]
        page_param = self.config.get("page_param", "page")
        max_pages = self.config.get("max_pages", 1)
        yielded = 0

        for search in self.config["searches"]:
            deal = search["deal_type"]
            path = search["path"]
            for page in range(1, max_pages + 1):
                url = urljoin(base + "/", path.lstrip("/"))
                if page > 1:
                    url = f"{url}?{page_param}={page}"
                html = fetcher.get_text(url, referer=base)
                if not html:
                    break
                items = _item_list(html)
                if not items:
                    break
                for it in items:
                    prop = (it or {}).get("item") or {}
                    if prop.get("@type") != "RealEstateListing":
                        continue
                    src_url = (prop.get("url") or "").split("?")[0].split("#")[0]
                    if not src_url:
                        continue
                    m = ID_RE.search(src_url)
                    about = prop.get("about") or {}
                    addr = about.get("address") or {}
                    geo = about.get("geo") or {}
                    offers = prop.get("offers") or {}
                    yield {
                        "source_url": src_url,
                        "source_id": m.group(0) if m else src_url,
                        "deal_type": deal,
                        "title": prop.get("name"),
                        "price": _num(offers.get("price")),
                        "condo_name": (about.get("containedInPlace") or {}).get("name"),
                        "bedrooms": about.get("numberOfBedrooms"),
                        "district": addr.get("addressLocality"),
                        "lat": _num(geo.get("latitude")),
                        "lng": _num(geo.get("longitude")),
                        "image_urls": [prop["image"]] if prop.get("image") else [],
                        "posted_at": prop.get("datePosted"),
                    }
                    yielded += 1
                    if limit and yielded >= limit:
                        return

    def parse_listing(self, fetcher: Fetcher, stub: dict) -> dict | None:
        # Tout vient déjà de la liste (ld+json ItemList complet) — pas de fiche
        # détail à visiter. Cf. docstring : cet adaptateur est un outil de
        # vérification, pas un pipeline de production.
        rec = dict(stub)
        rec["source"] = self.source
        rec["currency"] = "THB"
        rec["tenure"] = "freehold"
        rec["amenities"] = []
        rec["raw_data"] = {k: rec.get(k) for k in
                           ("condo_name", "bedrooms", "district", "price", "image_urls")}
        return rec
