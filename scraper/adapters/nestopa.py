"""nestopa.py — Adaptateur Nestopa.

SPA, mais le flux global `/th-en/for-sale|for-rent?page=N` rend 24 annonces/page
en ld+json (items `Product` : sku, prix, image, offers.url). L'URL de fiche encode
tout : `/property/<bangkok-khet-khwaeng>/<n>-bedroom-<n>-bathroom-<n>-sqm-<condo>-<id>`.
On pagine le flux et on **filtre Bangkok par l'URL**. Pas de coords côté serveur
→ khet déduit du slug d'URL (matché aux noms de khet du GeoJSON).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterator
from urllib.parse import urljoin

from adapters.base import BaseAdapter
from pipeline import description
from pipeline.fetch import Fetcher

LD_RE = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
ID_RE = re.compile(r"-(\d+)/?$")

# ── Extraction du nom de condo depuis le titre Nestopa ──────────────────────
# Le titre porte le nom du projet après "at/in <projet>" ou juste après le
# préfixe "N Bed N Bath N sqm". On retire dimensions + adjectifs/bruit marketing.
_DIM = re.compile(r"\b\d+(?:\.\d+)?[\s-]*(?:sq\.?\s*m\.?|sqm|bed(?:room)?s?|baths?|bathrooms?)\b", re.I)
_FLOOR = re.compile(r"\bon\s+\d+(?:st|nd|rd|th)?\s+floor\b", re.I)
_NOISE = re.compile(
    r"\b(?:for\s+(?:sale|rent)|condo(?:minium)?|duplex|penthouse|studio|house|townhouse|villa|"
    r"retail\s+space|corner|buy[\s-]?to[\s-]?let|spacious|stunning|exclusive|design|large|unique|"
    r"modern|luxury|luxurious|beautiful|gorgeous|brand[\s-]?new|new|prime|rare|high[\s-]?end|"
    r"well[\s-]?maintained|family|tranquil|renovated|with\s+garden|high\s+floor|riverfront|"
    r"architect|fully\s+furnished|ready\s+to\s+move|upscale|massive|prestigious|elegant|cozy|"
    r"bright|triplex|triple|with\s+triplex)\b",
    re.I,
)
_PREP = re.compile(r"\b(?:at|in)\s+", re.I)


def clean_condo_name(title: str | None) -> str | None:
    """Déduit le nom du condo depuis un titre d'annonce Nestopa."""
    if not title:
        return None
    # retire un éventuel préfixe "NBR — " issu d'un ancien titre
    t = re.sub(r"^\d+BR\s*—\s*", "", title).split(",")[0]
    t = _FLOOR.sub(" ", t)
    m = list(_PREP.finditer(t))
    cand = t[m[-1].end():] if m else _DIM.sub(" ", t)
    cand = _NOISE.sub(" ", cand)
    cand = _DIM.sub(" ", cand)
    # retire mentions sale/rent isolées + ponctuation résiduelle
    cand = re.sub(r"\b(?:sale|rent|bangkok)\b", " ", cand, flags=re.I)
    cand = re.sub(r"\s+", " ", cand)
    cand = re.sub(r"^[\s\-/:.]+|[\s\-/:.]+$", "", cand)
    return cand.strip() or None
# Le nom du Product ("1 Bedroom 1 Bathroom 46 Sq.m ...") est plus fiable que le
# slug (qui perd les décimales : "38-5-sqm"). On parse le nom en priorité.
BEDS_RE = re.compile(r"(\d+)\s*(?:bedroom|bed)\b", re.I)
BATHS_RE = re.compile(r"(\d+)\s*(?:bathroom|baths?)\b", re.I)
SQM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:sq\.?\s*m|sqm)", re.I)


def _products(node):
    if isinstance(node, dict):
        if node.get("@type") == "Product":
            yield node
        for v in node.values():
            yield from _products(v)
    elif isinstance(node, list):
        for v in node:
            yield from _products(v)


def _khet_slug_map() -> dict[str, str]:
    """slug -> nom de khet canonique, depuis le GeoJSON des quartiers."""
    path = Path(__file__).resolve().parents[2] / "public" / "data" / "bangkok-khet.geojson"
    out: dict[str, str] = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        for f in data.get("features", []):
            name = (f.get("properties") or {}).get("name_en")
            if name:
                slug = re.sub(r"[^a-z]+", "-", name.lower().replace(" district", "")).strip("-")
                out[slug] = name
    return out


class NestopaAdapter(BaseAdapter):
    source = "nestopa"

    def sonder(self, fetcher: Fetcher) -> tuple[bool, str]:
        """Nestopa : flux ld+json, items de type `Product`.

        La sonde demande l'URL QUE LA PRODUCTION DEMANDE, pas une variante
        commode : avec `respect_robots: false` (arbitrage du 2026-08-22) c'est
        `?page=1`. Tester la page bare pendant que le scan réel passe par
        `?page=` avait justement laissé la source à 0 annonce du 2026-08-17 au
        2026-08-22 avec une sonde verte."""
        searches = self.config.get("searches") or []
        if not searches:
            return False, "config sans 'searches'"
        base = self.config["base_url"]
        url = urljoin(base + "/", searches[0]["path"].lstrip("/"))
        if not self.config.get("respect_robots", True):
            url = f"{url}?{self.config.get('page_param', 'page')}=1"
        html = fetcher.get_text(url, referer=base)
        if not html:
            return False, "page de liste inaccessible (0 octet, erreur réseau, ou 403)"
        blocks = LD_RE.findall(html)
        if not blocks:
            return False, "aucun bloc ld+json sur la page de liste"
        prods = []
        for b in blocks:
            try:
                prods += list(_products(json.loads(b)))
            except json.JSONDecodeError:
                continue
        if not prods:
            return False, "ld+json présent mais aucun item '@type':'Product' — structure du flux changée"
        # PAS de super().sonder() ici : la sonde générique rappellerait
        # list_urls(), qui reparcourrait le flux entier — c'est le scan complet
        # qu'on cherche justement à éviter avant de savoir s'il vaut la peine.
        # Ce qui est vérifié ci-dessus suffit : le flux répond et son ld+json
        # contient toujours des Product.
        return True, f"{url.rsplit('/', 1)[-1]} ok — {len(prods)} item(s) Product"

    def __init__(self, config: dict):
        super().__init__(config)
        self._khets = _khet_slug_map()

    def _match_khet(self, loc_slug: str) -> str | None:
        # loc_slug ex: "bangkok-phaya-thai-sam-sen-nai" → cherche un slug de khet dedans
        for slug, name in self._khets.items():
            if slug and slug in loc_slug:
                return name
        return None

    def list_urls(self, fetcher: Fetcher, limit: int | None = None) -> Iterator[dict]:
        base = self.config["base_url"]
        page_param = self.config.get("page_param", "page")
        max_pages = self.config.get("max_pages", 1)
        yielded = 0

        for search in self.config["searches"]:
            deal = search["deal_type"]
            # ARRÊT SUR REJEU — mesuré le 2026-08-23 : au-delà de sa 50e page,
            # le flux ne rend NI page vide NI 404, il RENVOIE LA PAGE 1 (mêmes
            # sku, même taille, vérifié aux pages 51, 52, 150, 300, 600, 1200).
            # Le `break` sur page vide ci-dessous ne se déclenche donc jamais :
            # avec max_pages=150 on redemandait 100 fois la page 1 par flux,
            # soit ~200 requêtes inutiles et 10 min de scan par cycle, sans une
            # seule annonce de plus. On s'arrête sur la vraie fin : une page qui
            # n'apporte aucun sku nouveau.
            vus: set[str] = set()
            for page in range(1, max_pages + 1):
                url = urljoin(base + "/", search["path"].lstrip("/"))
                url = f"{url}?{page_param}={page}"
                html = fetcher.get_text(url, referer=base)
                if not html:
                    break
                prods = []
                for b in LD_RE.findall(html):
                    try:
                        prods += list(_products(json.loads(b)))
                    except json.JSONDecodeError:
                        pass
                if not prods:
                    break
                skus_page = {str(p.get("sku") or "") for p in prods}
                if skus_page and skus_page <= vus:
                    print(f"  [nestopa] {search['path']} page {page} : aucun sku "
                          f"nouveau — fin du flux (le site rejoue une page déjà vue)")
                    break
                vus |= skus_page
                for p in prods:
                    offers = p.get("offers") or {}
                    src_url = (offers.get("url") or "").split("?")[0]
                    # Bangkok uniquement (filtre par l'URL)
                    if "/property/bangkok" not in src_url:
                        continue
                    m = ID_RE.search(src_url)
                    sku = str(p.get("sku") or (m.group(1) if m else ""))
                    if not sku:
                        continue
                    # slug localisation + slug bien
                    parts = src_url.split("/property/", 1)[-1].split("/")
                    loc_slug = parts[0] if parts else ""
                    item_slug = parts[1] if len(parts) > 1 else ""
                    name = p.get("name") or ""
                    # nom (décimales OK) en priorité, slug en repli
                    beds = BEDS_RE.search(name) or BEDS_RE.search(item_slug.replace("-", " "))
                    baths = BATHS_RE.search(name) or BATHS_RE.search(item_slug.replace("-", " "))
                    sqm = SQM_RE.search(name)
                    area = float(sqm.group(1)) if sqm else None
                    img = p.get("image")
                    yield {
                        "source_url": src_url,
                        "source_id": sku,
                        "deal_type": deal,
                        "price": offers.get("price"),
                        "area_sqm": area,
                        "bedrooms": int(beds.group(1)) if beds else None,
                        "bathrooms": int(baths.group(1)) if baths else None,
                        "lat": None,
                        "lng": None,
                        "condo_name": clean_condo_name(name) or name,
                        "raw_title": name,
                        # Nestopa ne visite pas de page détail : le descriptif ne
                        # peut venir que du Product ld+json du flux.
                        "description": description.clean(p.get("description")),
                        "district": self._match_khet(loc_slug),
                        "image_urls": [img] if img else [],
                    }
                    yielded += 1
                    if limit and yielded >= limit:
                        return

    def parse_listing(self, fetcher: Fetcher, stub: dict) -> dict | None:
        rec = dict(stub)
        rec["source"] = self.source
        rec["currency"] = "THB"
        rec["amenities"] = []
        rec["title"] = stub.get("raw_title") or stub.get("condo_name") or "Condo"
        rec["description"] = stub.get("description")
        rec["raw_data"] = {k: stub.get(k) for k in
                           ("condo_name", "bedrooms", "area_sqm", "district", "price")}
        return rec
