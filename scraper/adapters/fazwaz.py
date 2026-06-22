"""fazwaz.py — Adaptateur FazWaz.

Stratégie robuste & polie : les pages de LISTE exposent un JSON-LD
(SingleFamilyResidence) par annonce avec nom, chambres, surface, géo, district ;
le prix est lu dans le HTML de la carte. 1 requête de liste = N annonces.
La page de détail n'est requêtée que si `fetch_detail` est activé (galerie + SDB).

robots.txt FazWaz : seules /api/ et /graphql sont interdites — les pages
d'annonces sont autorisées.
"""
from __future__ import annotations

import json
import re
from html import unescape
from typing import Iterator
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from adapters.base import BaseAdapter
from pipeline.fetch import Fetcher

ID_RE = re.compile(r"-u(\d+)(?:[/?#]|$)")
PRICE_RE = re.compile(r"฿\s*([0-9][0-9,]*)")
# location FazWaz = /property-rent/ (singulier), vente = /property-sales/
LISTING_HREF_RE = re.compile(r"/property-(sales|rent)/[^\"'#?]+-u\d+")
OWNERSHIP_RE = re.compile(r'"ownership":\[\[(\d+)\]')
# Code d'ownership de l'unité FazWaz → (quota, freehold). Codes "Quota" = freehold ;
# leasehold/company (autres codes) = écartés (on ne scrape que du freehold).
FAZWAZ_OWNERSHIP = {1: ("thai", True), 2: ("foreigner", True)}


class FazwazAdapter(BaseAdapter):
    source = "fazwaz"

    # ───────────────────────── liste ─────────────────────────
    def list_urls(self, fetcher: Fetcher, limit: int | None = None) -> Iterator[dict]:
        base = self.config["base_url"]
        page_param = self.config.get("page_param", "page")
        max_pages = self.config.get("max_pages", 1)
        yielded = 0

        for search in self.config["searches"]:
            path = search["path"]
            for page in range(1, max_pages + 1):
                url = urljoin(base + "/", path.lstrip("/"))
                if page > 1:
                    url = f"{url}?{page_param}={page}"
                html = fetcher.get_text(url)
                if not html:
                    break
                stubs = self._parse_list_page(html)
                if not stubs:
                    break
                for stub in stubs:
                    yield stub
                    yielded += 1
                    if limit and yielded >= limit:
                        return

    def _parse_list_page(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")

        # 1) JSON-LD : map url -> données structurées
        by_url: dict[str, dict] = {}
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string or "")
            except (json.JSONDecodeError, TypeError):
                continue
            for item in data if isinstance(data, list) else [data]:
                if not isinstance(item, dict) or item.get("@type") != "SingleFamilyResidence":
                    continue
                url = item.get("url")
                if not url:
                    continue
                addr = item.get("address") or {}
                geo = item.get("geo") or {}
                floor = item.get("floorSize") or {}
                by_url[url] = {
                    "condo_name": item.get("name"),
                    "bedrooms": item.get("numberOfRooms"),
                    "area_sqm": floor.get("value"),
                    "lat": geo.get("latitude"),
                    "lng": geo.get("longitude"),
                    "district": addr.get("addressLocality"),
                    "image_url": item.get("image"),
                }

        # 2) Prix depuis les cartes HTML : map url -> prix
        price_by_url: dict[str, int] = {}
        for a in soup.find_all("a", href=LISTING_HREF_RE):
            href = a.get("href", "")
            full = href if href.startswith("http") else urljoin(self.config["base_url"], href)
            full = full.split("?")[0].split("#")[0]
            if full in price_by_url:
                continue
            card = a
            for _ in range(4):  # remonte de quelques niveaux pour trouver le prix
                card = card.parent
                if card is None:
                    break
                m = PRICE_RE.search(card.get_text(" ", strip=True))
                if m:
                    price_by_url[full] = int(m.group(1).replace(",", ""))
                    break

        # 3) Fusion
        stubs: list[dict] = []
        for url, d in by_url.items():
            clean = url.split("?")[0].split("#")[0]
            m = ID_RE.search(clean)
            deal = "rent" if "/property-rent/" in clean else "sale"
            stub = {
                "source_url": clean,
                "source_id": m.group(1) if m else clean,
                "deal_type": deal,
                "price": price_by_url.get(clean),
                **d,
            }
            stubs.append(stub)
        return stubs

    # ───────────────────────── détail ─────────────────────────
    def parse_listing(self, fetcher: Fetcher, stub: dict) -> dict | None:
        rec = dict(stub)
        rec["source"] = self.source
        rec["currency"] = "THB"
        rec["bathrooms"] = None
        rec["amenities"] = []
        rec["image_urls"] = [stub["image_url"]] if stub.get("image_url") else []

        # titre lisible depuis le slug ou le nom
        beds = stub.get("bedrooms")
        name = stub.get("condo_name") or "Condo"
        rec["title"] = f"{beds}BR condo — {name}" if beds else f"Condo — {name}"

        if self.config.get("fetch_detail"):
            self._enrich_from_detail(fetcher, rec)
            # Freehold uniquement — UNIQUEMENT pour la vente. Une location n'a pas
            # de notion de quota/tenure → on ne la jette jamais.
            if rec.get("deal_type") == "sale" and rec.get("_skip"):
                return None

        rec["raw_data"] = {k: stub.get(k) for k in
                           ("condo_name", "bedrooms", "area_sqm", "lat", "lng", "district", "price")}
        return rec

    def _enrich_from_detail(self, fetcher: Fetcher, rec: dict) -> None:
        html = fetcher.get_text(rec["source_url"], referer=self.config["base_url"])
        if not html:
            return
        # tenure + quota depuis le code d'ownership de l'unité
        m = OWNERSHIP_RE.search(unescape(html))
        code = int(m.group(1)) if m else None
        if code in FAZWAZ_OWNERSHIP:
            quota, _ = FAZWAZ_OWNERSHIP[code]
            rec["quota"] = quota
            rec["tenure"] = "freehold"
        elif code is not None:
            # code connu mais hors Quota (leasehold/company) → écarté
            rec["tenure"] = "leasehold"
            rec["_skip"] = True
        # code introuvable → on garde (quota inconnu, tenure freehold par défaut)
        else:
            rec.setdefault("tenure", "freehold")

        # bathrooms : "<n> Bathroom"
        mb = re.search(r"(\d+)\s+Bathroom", html)
        if mb:
            rec["bathrooms"] = int(mb.group(1))
        # amenities : scan par mots-clés (robuste, sans DOM fragile)
        rec["amenities"] = _scan_amenities(html)
        # galerie : images CDN, plus grandes variantes uniques (hors icônes/logo)
        imgs = re.findall(r"https://cdn\.fazwaz\.com/[^\s\"'<>]+?\.(?:jpe?g|webp)", html)
        max_imgs = self.config.get("image", {}).get("max_per_listing", 1)
        seen, gallery = set(), []
        for u in imgs:
            if re.search(r"logo|icon|avatar|agent|placeholder", u, re.I):
                continue
            key = re.sub(r"/\d+x\d+/", "/", u)  # dédup par image (hors taille)
            if key in seen:
                continue
            seen.add(key)
            gallery.append(u)
            if len(gallery) >= max_imgs:
                break
        if gallery:
            rec["image_urls"] = gallery


#: amenities de condominium courants (scan robuste sur le HTML de la fiche)
COMMON_AMENITIES = [
    "Swimming Pool", "Communal Pool", "Private Pool", "Sauna", "Steam Room",
    "Jacuzzi", "Fitness", "Gym", "Garden", "Communal Garden", "Parking",
    "Security", "24-hour Security", "CCTV", "Reception", "Concierge", "Lift",
    "Elevator", "Wi-Fi", "Library", "Co-Working", "Clubhouse", "Playground",
    "Kids Club", "Sky Garden", "Rooftop", "Pet Friendly", "Bar", "Restaurant",
    "Shuttle", "EV Charger",
]


def _scan_amenities(html: str) -> list[str]:
    low = html.lower()
    found = []
    for a in COMMON_AMENITIES:
        if a.lower() in low and a not in found:
            found.append(a)
    return found
