"""propertyscout.py — Adaptateur PropertyScout.

App Next.js : les SERP (`/en/bangkok/sales/`, `/en/bangkok/rentals/`) exposent la
liste complète des annonces dans `__NEXT_DATA__` → `pageProps.rentals.data`
(id, prix, surface, chambres, SDB, gpsLat/Long, buildingName, district, images).
1 requête de liste = ~20 annonces avec tout le nécessaire. La fiche n'est visitée
(`fetch_detail`) que pour enrichir : quota (`saleQuota`), tenure, amenities, galerie.
robots autorise `/en/*/`.
"""
from __future__ import annotations

import json
import re
from typing import Iterator
from urllib.parse import urljoin

from adapters.base import BaseAdapter
from pipeline.fetch import Fetcher

NEXT_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
HREF_RE = re.compile(r'href="(https://propertyscout\.co\.th/en/[^"]+?-(\d+)/)"')


def _next_data(html: str) -> dict | None:
    m = NEXT_RE.search(html)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _num(v):
    try:
        return float(v) if v not in (None, "", "null") else None
    except (TypeError, ValueError):
        return None


def _int(v):
    f = _num(v)
    return int(f) if f is not None else None


_WORDNUM = {
    "studio": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def _rooms(v):
    """Nombre de pièces : accepte un entier, "4", ou un mot ("four_bedrooms")."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).lower()
    m = re.search(r"\d+", s)
    if m:
        return int(m.group())
    for w, n in _WORDNUM.items():
        if w in s:
            return n
    return None


def _imgs(item: dict) -> list[str]:
    out: list[str] = []
    cdn = item.get("cdnImages") or item.get("sortedImages")
    if isinstance(cdn, list):
        for x in cdn:
            if isinstance(x, str):
                out.append(x)
            elif isinstance(x, dict):
                u = x.get("url") or x.get("src") or x.get("large") or x.get("original")
                if u:
                    out.append(u)
    if not out and item.get("featuredImageUrl"):
        out.append(item["featuredImageUrl"])
    return out


def _district(item: dict) -> str | None:
    return item.get("district_ps_en") or item.get("district") or item.get("neighborhood_ps_en")


class PropertyscoutAdapter(BaseAdapter):
    source = "propertyscout"

    def list_urls(self, fetcher: Fetcher, limit: int | None = None) -> Iterator[dict]:
        base = self.config["base_url"]
        page_param = self.config.get("page_param", "page")
        max_pages = self.config.get("max_pages", 1)
        yielded = 0

        for search in self.config["searches"]:
            deal = search["deal_type"]
            base_path = urljoin(base + "/", search["path"].lstrip("/")).rstrip("/")
            for page in range(1, max_pages + 1):
                # pagination par chemin : /en/bangkok/sales/page-2/
                url = base_path + "/" if page == 1 else f"{base_path}/page-{page}/"
                html = fetcher.get_text(url, referer=base)
                if not html:
                    break
                data = _next_data(html)
                if not data:
                    break
                pp = (data.get("props") or {}).get("pageProps") or {}
                items = (pp.get("rentals") or {}).get("data") or []
                if not items:
                    break
                # map id -> URL de fiche depuis les ancres HTML
                id2url = {gid: u for u, gid in HREF_RE.findall(html)}
                for it in items:
                    gid = str(it.get("id") or "")
                    if not gid:
                        continue
                    src_url = id2url.get(gid) or f"{base}/en/{gid}/"
                    # prix selon le type : vente = salePrice ; location = lowestPrice (loyer/mois)
                    price = (_num(it.get("salePrice")) if deal == "sale"
                             else _num(it.get("lowestPrice") or it.get("rentPrice")))
                    yield {
                        "source_url": src_url,
                        "source_id": gid,
                        "deal_type": deal,
                        "price": price,
                        "area_sqm": _num(it.get("floorSize")),
                        "bedrooms": _rooms(it.get("bedroomsCount") if it.get("bedroomsCount") is not None else it.get("numberBedrooms")),
                        "bathrooms": _rooms(it.get("numberBathrooms")),
                        "lat": _num(it.get("gpsLat")),
                        "lng": _num(it.get("gpsLong")),
                        "condo_name": it.get("buildingName"),
                        "district": _district(it),
                        "image_urls": _imgs(it),
                    }
                    yielded += 1
                    if limit and yielded >= limit:
                        return
                # plus de page suivante → on arrête
                if not (pp.get("paginationLinks") or {}).get("nextLink"):
                    break

    def parse_listing(self, fetcher: Fetcher, stub: dict) -> dict | None:
        rec = dict(stub)
        rec["source"] = self.source
        rec["currency"] = "THB"
        rec["amenities"] = []
        name = stub.get("condo_name") or "Condo"
        beds = stub.get("bedrooms")
        rec["title"] = f"{beds}BR condo — {name}" if beds else f"Condo — {name}"

        if self.config.get("fetch_detail"):
            self._enrich(fetcher, rec)
            # freehold uniquement pour la vente (jamais de drop sur le locatif)
            if rec.get("deal_type") == "sale" and rec.get("_skip"):
                return None

        rec["raw_data"] = {k: stub.get(k) for k in
                           ("condo_name", "bedrooms", "area_sqm", "lat", "lng", "district", "price")}
        return rec

    def _enrich(self, fetcher: Fetcher, rec: dict) -> None:
        html = fetcher.get_text(rec["source_url"], referer=self.config["base_url"])
        if not html:
            return
        data = _next_data(html)
        p = ((data or {}).get("props") or {}).get("pageProps", {}).get("property")
        if not isinstance(p, dict):
            return
        # chambres / SDB / surface (souvent absents du SERP)
        if rec.get("bedrooms") is None:
            rec["bedrooms"] = _rooms(p.get("bedroomsCount") if p.get("bedroomsCount") is not None else p.get("numberBedrooms"))
        if rec.get("bathrooms") is None:
            rec["bathrooms"] = _rooms(p.get("numberBathrooms"))
        if not rec.get("area_sqm"):
            rec["area_sqm"] = _num(p.get("floorSize"))
        # quota (vente) : saleQuota = "foreign"/"thai"
        q = (p.get("saleQuota") or "").lower()
        if "foreign" in q:
            rec["quota"] = "foreigner"
        elif "thai" in q:
            rec["quota"] = "thai"
        # tenure
        ten = (p.get("tenure") or "").lower()
        if "lease" in ten:
            rec["tenure"] = "leasehold"
            rec["_skip"] = True
        else:
            rec.setdefault("tenure", "freehold")
        # amenities : flags communal*/amenity* à true
        amen = []
        for k, v in p.items():
            if v is True and (k.startswith("communal") or k.startswith("amenity")):
                label = re.sub(r"(communal|amenity)", "", k)
                label = re.sub(r"([A-Z])", r" \1", label).strip()
                if label:
                    amen.append(label)
        rec["amenities"] = amen[:30]
        # galerie complète si dispo
        imgs = _imgs(p)
        if imgs:
            rec["image_urls"] = imgs[: self.config.get("image", {}).get("max_per_listing", 6)]
