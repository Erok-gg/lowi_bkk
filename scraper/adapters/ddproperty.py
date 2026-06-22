"""ddproperty.py — Adaptateur DDproperty.

DDproperty est une app Next.js : toutes les données sont dans le blob
`__NEXT_DATA__` rendu côté serveur (lisible en HTTP simple, pas de Chrome).

- Pages de LISTE : id, url, prix, adresse complète (rue/khwaeng/khet/province),
  chambres/SDB → permet la dédup AVANT de visiter les fiches.
- Pages de DÉTAIL : coordonnées précises (listingLocationData.center),
  galerie d'images, amenities, MRT proches. Accès via la session réchauffée
  (cookie Cloudflare obtenu en parcourant la liste d'abord) + Referer.
"""
from __future__ import annotations

import json
import re
from typing import Iterator

from adapters.base import BaseAdapter
from adapters.fazwaz import COMMON_AMENITIES
from pipeline.fetch import Fetcher

NEXT_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
ID_RE = re.compile(r"-(\d+)(?:[#?]|$)")
PGIMG_RE = re.compile(r"https://[a-z0-9-]+\.pgimgs\.com/[^\s\"'<>]+?\.(?:jpe?g|webp)", re.I)


def _next_data(html: str) -> dict | None:
    m = NEXT_RE.search(html)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _walk_listings(node) -> Iterator[dict]:
    if isinstance(node, dict):
        if "fullAddress" in node and ("price" in node or "url" in node):
            yield node
        for v in node.values():
            yield from _walk_listings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_listings(v)


def _find_with_keys(node, required: set[str]):
    if isinstance(node, dict):
        if required <= set(node.keys()):
            return node
        for v in node.values():
            r = _find_with_keys(v, required)
            if r is not None:
                return r
    elif isinstance(node, list):
        for v in node:
            r = _find_with_keys(v, required)
            if r is not None:
                return r
    return None


def _find_value(node, key: str):
    """Première valeur scalaire trouvée pour `key` dans l'arbre."""
    if isinstance(node, dict):
        v = node.get(key)
        if v is not None and not isinstance(v, (dict, list)):
            return v
        for vv in node.values():
            r = _find_value(vv, key)
            if r is not None:
                return r
    elif isinstance(node, list):
        for vv in node:
            r = _find_value(vv, key)
            if r is not None:
                return r
    return None


def _find_stat_amenities(node):
    """Trouve l'objet dont 'amenities' est la rangée de stats (dicts avec 'unit')."""
    if isinstance(node, dict):
        a = node.get("amenities")
        if isinstance(a, list) and any(isinstance(x, dict) and "unit" in x for x in a):
            return node
        for v in node.values():
            r = _find_stat_amenities(v)
            if r is not None:
                return r
    elif isinstance(node, list):
        for v in node:
            r = _find_stat_amenities(v)
            if r is not None:
                return r
    return None


def _price_num(price) -> float | None:
    if isinstance(price, dict):
        if isinstance(price.get("value"), (int, float)):
            return float(price["value"])
        for k in ("pretty", "localeStringValue", "amount"):
            if price.get(k):
                digits = re.sub(r"[^\d]", "", str(price[k]))
                if digits:
                    return float(digits)
    return None


def _parse_address(full: str) -> dict:
    parts = [p.strip() for p in (full or "").split(",") if p.strip()]
    out = {"street": None, "khwaeng": None, "khet": None, "province": None}
    if len(parts) >= 1:
        out["province"] = parts[-1]
    if len(parts) >= 2:
        out["khet"] = parts[-2]
    if len(parts) >= 3:
        out["khwaeng"] = parts[-3]
    if len(parts) >= 4:
        out["street"] = parts[0]
    return out


class DdpropertyAdapter(BaseAdapter):
    source = "ddproperty"

    # ───────────────────────── liste ─────────────────────────
    def list_urls(self, fetcher: Fetcher, limit: int | None = None) -> Iterator[dict]:
        base = self.config["base_url"]
        max_pages = self.config.get("max_pages", 1)
        page_param = self.config.get("page_param", "page")
        yielded = 0

        for search in self.config["searches"]:
            deal = search["deal_type"]
            for page in range(1, max_pages + 1):
                sep = "&" if "?" in search["path"] else "?"
                url = f"{base}{search['path']}{sep}{page_param}={page}"
                html = fetcher.get_text(url, referer=base)
                if not html:
                    break
                data = _next_data(html)
                if not data:
                    break
                stubs = self._parse_list(data, deal)
                if not stubs:
                    break
                for stub in stubs:
                    yield stub
                    yielded += 1
                    if limit and yielded >= limit:
                        return

    def _parse_list(self, data: dict, deal: str) -> list[dict]:
        stubs, seen = [], set()
        for it in _walk_listings(data):
            full = it.get("fullAddress") or ""
            if not full.lower().endswith("bangkok"):
                continue  # province Bangkok uniquement
            url = (it.get("url") or "").split("#")[0].split("?")[0]
            if not url or url in seen:
                continue
            seen.add(url)
            m = ID_RE.search(url)
            addr = _parse_address(full)
            prop = it.get("property") or {}
            stubs.append({
                "source_url": url,
                "source_id": m.group(1) if m else url,
                "deal_type": deal,
                "price": _price_num(it.get("price")),
                "condo_name": prop.get("projectName") or it.get("localizedTitle"),
                "bedrooms": _int(it.get("bedrooms")),
                "bathrooms": _int(it.get("bathrooms")),
                "full_address": full,
                **addr,
            })
        return stubs

    # ───────────────────────── détail ─────────────────────────
    def parse_listing(self, fetcher: Fetcher, stub: dict) -> dict | None:
        rec = dict(stub)
        rec["source"] = self.source
        rec["currency"] = "THB"
        rec["district"] = stub.get("khet")  # rattachement khet par texte (PIP affine si coords)
        rec["amenities"] = []
        rec["image_urls"] = []
        rec["title"] = stub.get("condo_name") or "Condo"

        html = fetcher.get_text(rec["source_url"], referer=self.config["base_url"])
        if html:
            self._enrich_from_detail(html, rec)
            # Freehold uniquement — seulement pour la vente (une location n'a pas de tenure)
            if rec.get("deal_type") == "sale" and rec.get("_skip"):
                return None

        rec["raw_data"] = {k: stub.get(k) for k in
                           ("full_address", "khwaeng", "street", "price", "bedrooms")}
        return rec

    def _enrich_from_detail(self, html: str, rec: dict) -> None:
        data = _next_data(html)
        if data:
            # coordonnées précises
            center = _find_with_keys(data, {"lat", "lng"})
            if center:
                rec["lat"], rec["lng"] = center["lat"], center["lng"]
            # tenure : on ne garde que le freehold (tenureCode 'F')
            tcode = _find_value(data, "tenureCode") or _find_value(data, "tenure")
            if tcode:
                if str(tcode).upper().startswith("F"):
                    rec["tenure"] = "freehold"
                else:
                    rec["tenure"] = "leasehold"
                    rec["_skip"] = True
            else:
                rec.setdefault("tenure", "freehold")
            # tableau de stats (beds/baths/area) : liste de dicts avec 'unit'
            stat_node = _find_stat_amenities(data)
            if stat_node:
                if stat_node.get("title"):
                    rec["title"] = stat_node["title"]
                self._parse_amenity_stats(stat_node.get("amenities") or [], rec)
            # prix : fallback depuis la fiche si absent dans la liste
            if not rec.get("price"):
                price_node = _find_with_keys(data, {"amount", "priceType"})
                if price_node:
                    rec["price"] = _price_num(price_node)

        # facilities (piscine, gym…) via scan mots-clés sur le HTML
        rec["amenities"] = _scan_facilities(html)
        # galerie : images pgimgs (hors icônes/agents/placeholders ${viewType})
        max_imgs = self.config.get("image", {}).get("max_per_listing", 1)
        seen, gallery = set(), []
        for u in PGIMG_RE.findall(html):
            if "${" in u or re.search(r"logo|icon|avatar|/agent/|placeholder", u, re.I):
                continue
            key = re.sub(r"\.V\d+\.", ".", u)
            if key in seen:
                continue
            seen.add(key)
            gallery.append(u)
            if len(gallery) >= max_imgs:
                break
        if gallery:
            rec["image_urls"] = gallery

    @staticmethod
    def _parse_amenity_stats(amenities: list, rec: dict) -> None:
        for a in amenities:
            unit = str(a.get("unit", "")).lower()
            val = a.get("value")
            if "bed" in unit and rec.get("bedrooms") is None:
                rec["bedrooms"] = _int(val)
            elif "bath" in unit and rec.get("bathrooms") is None:
                rec["bathrooms"] = _int(val)
            elif ("sqm" in unit or "sq" in unit) and not rec.get("area_sqm"):
                rec["area_sqm"] = _float(val)


def _scan_facilities(html: str) -> list[str]:
    low = html.lower()
    return [a for a in COMMON_AMENITIES if a.lower() in low]


def _int(v):
    # 1er nombre entier (gère les fourchettes type "1 - 3")
    m = re.search(r"\d[\d,]*", str(v) if v is not None else "")
    if not m:
        return None
    try:
        return int(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _float(v):
    # 1er nombre (gère les fourchettes type "40 - 136 SqM", les milliers "1,199")
    m = re.search(r"\d[\d,]*\.?\d*", str(v) if v is not None else "")
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None
