"""hipflat.py — Adaptateur Hipflat (hipflat.co.th, groupe Lifull Connect).

Sonde du 2026-10-20 :
- robots.txt : `Allow: /` sauf `/generate-seo-friendly-url` et `/api/v1/projects/`
  (non utilisés ici).
- SERP rendue serveur, 30 cartes/page : titre, prix, district, chambres, SDB,
  surface. Le prix étant sur la carte, la dédup incrémentale de run.py
  s'applique. Prix en USD par défaut : le cookie `_wl_currency=THB` (celui que
  pose `POST /api/currency`) les rend en baht.
- Volume : 62 233 ventes / 118 991 locations annoncées sur Bangkok, mais la
  pagination s'arrête à la page 167 (≈ 5 010 annonces par recherche). D'où le
  découpage : district → chambres → double passe prix croissant/décroissant
  (`?sort=price_asc|price_desc`). Ce qui reste invisible au milieu d'un segment
  trop gros est une TRANCHE DE PRIX connue : `ids_hors_couverture` la protège
  du délistage (sinon on rejoue le défaut FazWaz des 150 pages, 2026-09-13).
- SYNDICATION : 7 fiches sur 28 échantillonnées (toutes en tête de liste,
  « Premium ») sont des annonces FazWaz — référence d'unité `U6011645`, plans
  sur cdn.fazwaz.com. Déjà scrapées à la source, elles sont ÉCARTÉES ; leur
  identifiant est mémorisé (`output/hipflat-ecartees.json`) pour ne pas rouvrir
  la fiche à chaque run. Les 21 autres viennent de flux d'agences (Proppit).
- Nom d'immeuble et coordonnées : seulement sur la fiche (fil d'Ariane, ld+json
  `geo`) — toute nouvelle annonce ouvre donc sa fiche.
"""
from __future__ import annotations

import html as _html
import json
import os
import re
from pathlib import Path
from typing import Iterator

from adapters.base import BaseAdapter
from pipeline import description
from pipeline.fetch import Fetcher

PLAFOND = 5010   # 167 pages × 30, mesuré le 2026-10-20
_DEAL_SLUG = {"sale": "condo-for-sale", "rent": "condo-for-rent"}
_BEDS = [("studio", 0), ("one-bed", 1), ("two-bed", 2), ("three-bed", 3), ("four-bed", 4)]

CARD_RE = re.compile(r"<div class='snippet'>(.*?)<div class=\"snippet-ctas\"", re.S)
HREF_RE = re.compile(r"href='(https://www\.hipflat\.co\.th/en/ads/([a-z0-9]+))'")
PRICE_RE = re.compile(r"snippet-price'>([^<]+)<")
ADDR_RE = re.compile(r"snippet-address'>([^<]+)<")
TITLE_RE = re.compile(r"snippet-title'>([^<]+)<")
DESC_RE = re.compile(r'snippet-description-2 snippet-description">(.*?)</p>', re.S)
INFO_RE = re.compile(r'alt="(beds|baths|space)"\s*/>\s*([^<]+)<')
IMG_RE = re.compile(r"<img alt=\"[^\"]*\" src='(https://img\.hipcdn\.com/[^']+)'")
TOTAL_RE = re.compile(r"([0-9,]+) results")
LDJSON_RE = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.S)
FAZWAZ_REF = re.compile(r"U\d{6,8}")


def _num(v):
    try:
        return float(str(v).replace(",", "")) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _prix(txt: str | None) -> float | None:
    """« ฿7,280,000 » → 7280000. Une autre devise (cookie perdu) → None plutôt
    qu'un montant en USD rangé en THB."""
    if not txt:
        return None
    t = _html.unescape(txt).strip()
    if not t.startswith("฿"):
        return None
    return _num(re.sub(r"[^\d.]", "", t))


def _total(html: str) -> int | None:
    m = TOTAL_RE.search(html or "")
    return int(m.group(1).replace(",", "")) if m else None


class HipflatAdapter(BaseAdapter):
    source = "hipflat"

    def __init__(self, config: dict):
        super().__init__(config)
        # même racine que run.py : un scrap de test (LOWI_OUTPUT_DIR) ne touche pas au cache de production
        out = Path(os.environ.get("LOWI_OUTPUT_DIR") or Path(__file__).resolve().parent.parent / "output")
        self._ecart_path = Path(config.get("ecartees_cache") or out / "hipflat-ecartees.json")
        try:
            self._ecartees: set[str] = set(json.loads(self._ecart_path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            self._ecartees = set()
        self._n_ecartees = len(self._ecartees)
        # (deal, district, chambres, prix_max_vu_croissant, prix_min_vu_decroissant)
        self.tranches_non_vues: list[tuple] = []
        self._cookie_pose = False

    # ── session ───────────────────────────────────────────────────────────
    def _thb(self, fetcher: Fetcher) -> None:
        if self._cookie_pose:
            return
        sess = getattr(fetcher, "_session", None)
        if sess is not None:
            sess.cookies.set("_wl_currency", "THB", domain="www.hipflat.co.th")
        self._cookie_pose = True

    def _page(self, fetcher: Fetcher, path: str, page: int, sort: str | None) -> str | None:
        params = []
        if sort:
            params.append(f"sort={sort}")
        if page > 1:
            params.append(f"page={page}")
        url = self.config["base_url"] + path + ("?" + "&".join(params) if params else "")
        return fetcher.get_text(url, referer=self.config["base_url"])

    # ── sonde ─────────────────────────────────────────────────────────────
    def sonder(self, fetcher: Fetcher) -> tuple[bool, str]:
        """Hipflat : cartes `<div class='snippet'>` rendues serveur, prix en ฿."""
        self._thb(fetcher)
        searches = self.config.get("searches") or []
        if not searches:
            return False, "config sans 'searches'"
        html = self._page(fetcher, f"/en/{_DEAL_SLUG[searches[0]['deal_type']]}/bangkok", 1, None)
        if not html:
            return False, "page de liste inaccessible (0 octet ou erreur réseau)"
        cartes = CARD_RE.findall(html)
        if not cartes:
            return False, "aucune carte <div class='snippet'> (structure changée)"
        if _prix((PRICE_RE.search(cartes[0]) or [None, None])[1]) is None:
            return False, "prix illisible ou pas en ฿ (cookie _wl_currency ignoré ?)"
        return super().sonder(fetcher)

    # ── liste ─────────────────────────────────────────────────────────────
    def list_urls(self, fetcher: Fetcher, limit: int | None = None) -> Iterator[dict]:
        self._thb(fetcher)
        districts = self.config.get("districts") or []
        max_pages = int(self.config.get("max_pages", 167))
        yielded = 0
        try:
            for search in self.config["searches"]:
                deal = search["deal_type"]
                base_path = f"/en/{_DEAL_SLUG[deal]}/bangkok"
                vus: set[str] = set()
                for d in districts:
                    for stub in self._segment(fetcher, deal, d, f"{base_path}/{d}", None, vus, max_pages):
                        yield stub
                        yielded += 1
                        if limit and yielded >= limit:
                            return
        finally:
            self._sauver_ecartees()
            if self.tranches_non_vues:
                print(f"[COUVERTURE] hipflat : {len(self.tranches_non_vues)} segment(s) au-delà "
                      f"de {PLAFOND} annonces — tranches de prix non vues protégées du délistage")

    def _segment(self, fetcher, deal, district, path, beds, vus, max_pages) -> Iterator[dict]:
        html = self._page(fetcher, path, 1, None)
        if not html:
            return
        total = _total(html) or 0
        if total <= PLAFOND or max_pages < 167:
            yield from self._parcourir(fetcher, deal, district, path, None, vus, max_pages, html)
            return
        if beds is None:
            # trop gros : découpe par chambres (les 5 segments couvrent tout le district)
            for slug, n in _BEDS:
                yield from self._segment(fetcher, deal, district, f"{path}/{slug}", n, vus, max_pages)
            return
        # encore trop gros : les deux bouts de la distribution des prix
        hauts: list[float] = []
        bas: list[float] = []
        for stub in self._parcourir(fetcher, deal, district, path, "price_asc", vus, max_pages, None, bas):
            yield stub
        for stub in self._parcourir(fetcher, deal, district, path, "price_desc", vus, max_pages, None, hauts):
            yield stub
        if bas and hauts and max(bas) < min(hauts):
            self.tranches_non_vues.append((deal, district, beds, max(bas), min(hauts)))
            print(f"  [segment] {deal} {district} {beds} ch. : {total} annonces, "
                  f"tranche {max(bas):,.0f}–{min(hauts):,.0f} ฿ non vue")

    def _parcourir(self, fetcher, deal, district, path, sort, vus, max_pages,
                   premiere: str | None, prix_vus: list | None = None) -> Iterator[dict]:
        base = self.config["base_url"]
        for page in range(1, max_pages + 1):
            html = premiere if (page == 1 and premiere) else self._page(fetcher, path, page, sort)
            cartes = CARD_RE.findall(html or "")
            if not cartes:
                break
            for c in cartes:
                m = HREF_RE.search(c)
                if not m:
                    continue
                url, gid = m.group(1), m.group(2)
                prix = _prix((PRICE_RE.search(c) or [None, None])[1])
                if prix_vus is not None and prix is not None:
                    prix_vus.append(prix)
                if gid in vus or gid in self._ecartees:
                    continue
                vus.add(gid)
                info = {k: v.strip() for k, v in INFO_RE.findall(c)}
                desc = DESC_RE.search(c)
                yield {
                    "source_url": url,
                    "source_id": gid,
                    "deal_type": deal,
                    "title": _html.unescape((TITLE_RE.search(c) or [None, ""])[1]).strip() or None,
                    "price": prix,
                    "area_sqm": _num(re.sub(r"[^\d.]", "", info.get("space", "")) or None),
                    "bedrooms": int(_num(info["beds"])) if _num(info.get("beds")) is not None else None,
                    "bathrooms": int(_num(info["baths"])) if _num(info.get("baths")) is not None else None,
                    "district": district.replace("-", " ").title(),
                    "full_address": _html.unescape((ADDR_RE.search(c) or [None, ""])[1]).strip() or None,
                    "description": description.clean(desc.group(1)) if desc else None,
                    "image_urls": IMG_RE.findall(c)[:1],
                    "_sans_image": "no-image-placeholder" in c,
                }
            if len(cartes) < 30:
                break

    # ── délistage : ce que le scan n'a pas pu voir ────────────────────────
    def ids_hors_couverture(self, store, deal_type: str | None) -> set[str]:
        """Annonces actives en base situées dans une tranche de prix que la
        pagination plafonnée n'a pas montrée : non vues ≠ disparues."""
        if not self.tranches_non_vues:
            return set()
        db = getattr(store, "db", None)
        if db is None:
            return set()
        q = ("select id, deal_type, bedrooms, price, raw_data from listings "
             "where source=? and status='active'")
        out: set[str] = set()
        for r in db.execute(q, (self.source,)).fetchall():
            if deal_type and r["deal_type"] != deal_type:
                continue
            try:
                seg = (json.loads(r["raw_data"] or "{}") or {}).get("district_slug")
            except ValueError:
                seg = None
            for deal, district, beds, lo, hi in self.tranches_non_vues:
                if (r["deal_type"] == deal and seg == district
                        and (r["bedrooms"] if (r["bedrooms"] or 0) < 4 else 4) == beds
                        and r["price"] is not None and lo <= float(r["price"]) <= hi):
                    out.add(r["id"])
                    break
        return out

    def _sauver_ecartees(self) -> None:
        if len(self._ecartees) == self._n_ecartees:
            return
        self._ecart_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._ecart_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(sorted(self._ecartees)), encoding="utf-8")
        tmp.replace(self._ecart_path)
        self._n_ecartees = len(self._ecartees)

    # ── fiche ─────────────────────────────────────────────────────────────
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
            if not self._lire_fiche(html, rec):
                self._ecartees.add(stub["source_id"])
                print(f"  [syndiquee-fazwaz] hipflat:{stub['source_id']} ({rec.get('reference')}) écartée")
                return None
            rec["page_text"] = description.texte_integral(html)
        district_slug = re.sub(r"\s+", "-", (stub.get("district") or "").lower())
        rec["raw_data"] = {"district_slug": district_slug,
                           **{k: rec.get(k) for k in ("condo_name", "bedrooms", "area_sqm",
                                                      "price", "reference")}}
        if not rec.get("condo_name"):
            rec["condo_name"] = None
        return rec

    def _lire_fiche(self, html: str, rec: dict) -> bool:
        """Complète rec depuis le ld+json de la fiche. False = annonce FazWaz
        syndiquée (déjà couverte à la source)."""
        for bloc in LDJSON_RE.findall(html):
            try:
                data = json.loads(bloc)
            except ValueError:
                continue
            for node in data if isinstance(data, list) else [data]:
                if not isinstance(node, dict):
                    continue
                if node.get("@type") == "BreadcrumbList":
                    items = node.get("itemListElement") or []
                    ref = (items[-1].get("name") or "").strip() if items else ""
                    rec["reference"] = ref or None
                    if FAZWAZ_REF.fullmatch(ref):
                        return False
                    for it in items:
                        if "/en/projects/" in str(it.get("item") or ""):
                            rec["condo_name"] = (it.get("name") or "").strip() or None
                elif node.get("geo"):
                    geo = node["geo"]
                    rec["lat"], rec["lng"] = _num(geo.get("latitude")), _num(geo.get("longitude"))
                    rec["amenities"] = [a.get("name") for a in (node.get("amenityFeature") or [])
                                        if isinstance(a, dict) and a.get("name")][:30]
                    if node.get("description"):
                        rec["description"] = description.clean(node["description"]) or rec.get("description")
                    fs = (node.get("floorSize") or {}).get("value")
                    if fs and not rec.get("area_sqm"):
                        rec["area_sqm"] = _num(fs)
        if "cdn.fazwaz.com" in html and FAZWAZ_REF.search(rec.get("reference") or ""):
            return False
        return True
