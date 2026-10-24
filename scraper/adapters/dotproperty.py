"""dotproperty.py — Adaptateur DotProperty (dotproperty.co.th), source de production.

Historique : écrit le 2026-08-05 comme outil de VÉRIFICATION, sur l'hypothèse
« DotProperty syndique FazWaz » (90/90 photos sur cdn/img.fazwaz.com). Cette
lecture était FAUSSE, mesuré le 2026-10-22 : les adresses img.fazwaz.com
encodent un chemin du stockage du groupe Lifull Connect
(`prd-lifullconnect-backend-b2b-images/ingester/...`), le même que les photos
Hipflat ; l'hébergeur des photos ne dit rien de l'origine de l'annonce (une
annonce examinée venait de PropertyScout). Mesure directe sur 179 annonces de
6 pages : 153 (85 %) ont un même immeuble au même prix déjà en base (DDproperty,
FazWaz surtout), 26 (15 %) n'existent dans aucune de nos sources.

Sonde du 2026-10-22 :
- robots.txt autorise les pages de liste et les annonces.
- `/en/condos-for-sale|rent/bangkok?page=N` : ld+json `ItemList`, 30 annonces
  avec prix, chambres, immeuble, quartier, coordonnées, photo. **Aucun
  plafond** de pagination (page 2 080 pleine, 2 100 vide) : couverture
  complète possible, contrairement à Hipflat (167 pages).
- La SURFACE n'est que sur la page de l'annonce (« 2 Beds 1 Bath 72 SqM
  Floor 9 ») : chaque nouvelle annonce ouvre sa fiche — d'où `max_nouvelles`.
- Le prix étant dans la liste, la dédup incrémentale de run.py s'applique.
"""
from __future__ import annotations

import json
import re
from typing import Iterator
from urllib.parse import urljoin

from adapters.base import BaseAdapter
from pipeline import description
from pipeline.fetch import Fetcher

LD_RE = re.compile(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
ID_RE = re.compile(r"_([a-f0-9]{8,}-[a-f0-9-]+)$", re.I)
#: bloc d'infos de la fiche, en texte visible : « 2 Beds 1 Bath 72 SqM Floor 9 »
SURFACE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*SqM\b")
SDB_RE = re.compile(r"(\d+)\s*Baths?\b")
ETAGE_RE = re.compile(r"\bFloor\s+(\d+)\b")


def _num(v):
    try:
        return float(str(v).replace(",", "")) if v not in (None, "", "null") else None
    except (TypeError, ValueError):
        return None


def _item_list(html: str) -> list[dict]:
    for raw in LD_RE.findall(html or ""):
        try:
            d = json.loads(raw.strip())
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and d.get("@type") == "ItemList":
            return d.get("itemListElement") or []
    return []


def _texte_visible(html: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))


def _district(locality: str | None) -> str | None:
    """« Bangkok-yai » → « Bangkok Yai » (canonisé ensuite par run.py)."""
    if not locality:
        return None
    return " ".join(w.capitalize() for w in re.split(r"[-\s]+", locality) if w)


class DotpropertyAdapter(BaseAdapter):
    source = "dotproperty"

    def sonder(self, fetcher: Fetcher) -> tuple[bool, str]:
        """DotProperty : ld+json `ItemList` sur la page de liste."""
        searches = self.config.get("searches") or []
        if not searches:
            return False, "config sans 'searches'"
        base = self.config["base_url"]
        html = fetcher.get_text(urljoin(base + "/", searches[0]["path"].lstrip("/")), referer=base)
        if not html:
            return False, "page de liste inaccessible (0 octet ou erreur réseau)"
        if not _item_list(html):
            return False, "ld+json ItemList absent ou vide (structure changée)"
        return super().sonder(fetcher)

    def list_urls(self, fetcher: Fetcher, limit: int | None = None) -> Iterator[dict]:
        base = self.config["base_url"]
        page_param = self.config.get("page_param", "page")
        max_pages = self.config.get("max_pages", 1)
        yielded = 0

        for search in self.config["searches"]:
            deal = search["deal_type"]
            path = search["path"]
            vus: set[str] = set()
            for page in range(1, max_pages + 1):
                url = urljoin(base + "/", path.lstrip("/"))
                if page > 1:
                    url = f"{url}?{page_param}={page}"
                items = _item_list(fetcher.get_text(url, referer=base) or "")
                if not items:
                    break
                for it in items:
                    prop = (it or {}).get("item") or {}
                    if prop.get("@type") != "RealEstateListing":
                        continue
                    src_url = (prop.get("url") or "").split("?")[0].split("#")[0]
                    m = ID_RE.search(src_url)
                    if not m or m.group(1) in vus:
                        continue
                    vus.add(m.group(1))
                    about = prop.get("about") or {}
                    addr = about.get("address") or {}
                    geo = about.get("geo") or {}
                    offers = prop.get("offers") or {}
                    if (offers.get("priceCurrency") or "THB") != "THB":
                        continue
                    yield {
                        "source_url": src_url,
                        "source_id": m.group(1),
                        "deal_type": deal,
                        "title": prop.get("name"),
                        "price": _num(offers.get("price")),
                        "condo_name": ((about.get("containedInPlace") or {}).get("name") or "").strip() or None,
                        "bedrooms": about.get("numberOfBedrooms"),
                        "district": _district(addr.get("addressLocality")),
                        "khwaeng": addr.get("streetAddress"),
                        "lat": _num(geo.get("latitude")),
                        "lng": _num(geo.get("longitude")),
                        "image_urls": [prop["image"]] if prop.get("image") else [],
                        "date_publiee": prop.get("datePosted"),
                    }
                    yielded += 1
                    if limit and yielded >= limit:
                        return

    def parse_listing(self, fetcher: Fetcher, stub: dict) -> dict | None:
        rec = dict(stub)
        rec["source"] = self.source
        rec["currency"] = "THB"
        rec["tenure"] = "freehold"
        rec["amenities"] = []
        if rec.get("price") is None:
            return None
        html = fetcher.get_text(stub["source_url"], referer=self.config["base_url"])
        if html:
            t = _texte_visible(html)
            ms = SURFACE_RE.search(t)
            if ms:
                rec["area_sqm"] = _num(ms.group(1))
            mb = SDB_RE.search(t)
            if mb:
                rec["bathrooms"] = int(mb.group(1))
            me = ETAGE_RE.search(t)
            if me:
                rec["floor"] = me.group(1)
            rec["description"] = description.extract(html)
            rec["page_text"] = description.texte_integral(html)
        # `datePosted` = date de (re)publication déclarée, même nature que le
        # posted_at DDproperty (remontée en tête de liste, cf. 2026-08-02) :
        # gardée en raw_data, jamais substituée à first_seen.
        rec["raw_data"] = {k: rec.get(k) for k in
                           ("condo_name", "bedrooms", "area_sqm", "floor", "district",
                            "price", "date_publiee")}
        return rec
