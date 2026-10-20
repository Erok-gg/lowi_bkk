"""propertyhub.py — Adaptateur PropertyHub (propertyhub.in.th).

App Next.js. Sonde du 2026-10-20 :
- robots.txt : `Allow: /` (rien d'interdit).
- SERP `/en/condo-for-sale|for-rent/bangkok/<page>` : `__NEXT_DATA__` →
  `pageProps.listings.listings` porte prix, surface, chambres, SDB, nom et
  adresse du projet, `refreshedAt`. Le prix étant dans la liste, la dédup
  incrémentale de run.py (prix inchangé → fiche non rouverte) s'applique.
- Volume annoncé : 151 117 locations / 64 158 ventes (zone « Bangkok »).
- Chaque page > 1 renvoie 120 lignes : 60 sponsorisées, LES MÊMES d'une page
  à l'autre (EXCLUSIVE/PREMIUM), + 60 gratuites. On ne relaie donc chaque
  identifiant qu'une fois par run.
- La zone « Bangkok » est la province MÉTROPOLITAINE : la dernière page de
  location sortait sur « Muang Samut Prakarn ». Filtre sur l'adresse du projet.
- Aucun tri par fraîcheur exposé (`?sort=newest`, `?orderBy=` sans effet) :
  la couverture complète passe par toutes les pages.
- Coordonnées : absentes de la liste. Elles sont celles du PROJET
  (`listing.project.location` sur la fiche), donc mises en cache par
  project_id (`output/propertyhub-projets.json`) : une fiche ouverte renseigne
  aussi les ~6 `nearbyProjects`. Une nouvelle annonce d'un projet connu n'ouvre
  aucune fiche.
- `contactInformation` (téléphone, e-mail du vendeur) n'est JAMAIS recopié.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Iterator

from adapters.base import BaseAdapter
from pipeline import description
from pipeline.fetch import Fetcher

NEXT_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
IMG_BASE = "https://bcdn.propertyhub.in.th"
_DEAL_SLUG = {"sale": "condo-for-sale", "rent": "condo-for-rent"}
_ROOMTYPE_BEDS = {"STUDIO": 0, "ONE_BED_ROOM": 1, "TWO_BED_ROOM": 2,
                  "THREE_BED_ROOM": 3, "FOUR_BED_ROOM": 4}


def _next_data(html: str) -> dict | None:
    m = NEXT_RE.search(html or "")
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


def _img(path: str | None) -> str | None:
    if not path:
        return None
    return path if path.startswith("http") else IMG_BASE + path


def _price(price: dict, deal: str) -> float | None:
    """Seul `type == AMOUNT` est un montant ; les autres types (prix sur
    demande…) n'en sont pas."""
    price = price or {}
    if deal == "sale":
        p = price.get("forSale") or {}
        return _num(p.get("price")) if p.get("type") == "AMOUNT" else None
    m = (price.get("forRent") or {}).get("monthly") or {}
    return _num(m.get("price")) if m.get("type") == "AMOUNT" else None


def _district(address: str | None) -> str | None:
    """« Huai Khwang Bangkok » → « Huai Khwang » (canonisé ensuite par
    KhetMatcher.canoniser dans run.py)."""
    if not address:
        return None
    a = address.strip()
    if a.endswith("Bangkok"):
        return a[: -len("Bangkok")].strip() or None
    return a


class PropertyhubAdapter(BaseAdapter):
    source = "propertyhub"

    def __init__(self, config: dict):
        super().__init__(config)
        # même racine que run.py : un scrap de test (LOWI_OUTPUT_DIR) ne touche pas au cache de production
        out = Path(os.environ.get("LOWI_OUTPUT_DIR") or Path(__file__).resolve().parent.parent / "output")
        self._cache_path = Path(config.get("projets_cache") or out / "propertyhub-projets.json")
        try:
            self._projets: dict = json.loads(self._cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._projets = {}
        self._cache_sale = False

    # ── cache projet → coordonnées ────────────────────────────────────────
    def _noter_projet(self, p: dict | None, fiche: bool = False) -> None:
        if not isinstance(p, dict) or not p.get("id"):
            return
        loc = p.get("location") or {}
        lat, lng = _num(loc.get("lat")), _num(loc.get("lng"))
        # Projet SANS coordonnées vu sur sa propre fiche : on le note quand même
        # (lat None), sinon chaque nouvelle annonce de ce projet rouvrirait une
        # fiche pour rien — 3 fiches sur 25 au 2e passage du test du 2026-10-20.
        if (lat is None or lng is None) and not fiche:
            return
        info = p.get("projectInfo") or {}
        entree = {"lat": lat, "lng": lng, "address": p.get("address"),
                  "year_built": _int(info.get("completedYear"))}
        anc = self._projets.get(str(p["id"])) or {}
        # un nearbyProject ne porte pas projectInfo : ne pas effacer l'année déjà connue
        if entree["year_built"] is None:
            entree["year_built"] = anc.get("year_built")
        if anc != entree:
            self._projets[str(p["id"])] = entree
            self._cache_sale = True

    def sauver_cache(self) -> None:
        if not self._cache_sale:
            return
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._projets, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._cache_path)
        self._cache_sale = False

    # ── sonde ─────────────────────────────────────────────────────────────
    def sonder(self, fetcher: Fetcher) -> tuple[bool, str]:
        """PropertyHub (Next.js) : liste dans `__NEXT_DATA__` →
        `props.pageProps.listings.listings`."""
        searches = self.config.get("searches") or []
        if not searches:
            return False, "config sans 'searches'"
        html = fetcher.get_text(self._url(searches[0], 1), referer=self.config["base_url"])
        if not html:
            return False, "page de liste inaccessible (0 octet ou erreur réseau)"
        data = _next_data(html)
        if not data:
            return False, "__NEXT_DATA__ absent ou illisible (JSON invalide)"
        pp = (data.get("props") or {}).get("pageProps") or {}
        if not ((pp.get("listings") or {}).get("listings")):
            return False, "__NEXT_DATA__ présent mais props.pageProps.listings.listings introuvable ou vide"
        return super().sonder(fetcher)

    def _url(self, search: dict, page: int) -> str:
        base = self.config["base_url"]
        zone = search.get("zone", "bangkok")
        path = f"/en/{_DEAL_SLUG[search['deal_type']]}/{zone}"
        return f"{base}{path}" if page == 1 else f"{base}{path}/{page}"

    # ── liste ─────────────────────────────────────────────────────────────
    def list_urls(self, fetcher: Fetcher, limit: int | None = None) -> Iterator[dict]:
        base = self.config["base_url"]
        max_pages = self.config.get("max_pages", 1)
        yielded = 0
        try:
            for search in self.config["searches"]:
                deal = search["deal_type"]
                vus: set[str] = set()   # sponsorisées répétées sur chaque page
                for page in range(1, max_pages + 1):
                    html = fetcher.get_text(self._url(search, page), referer=base)
                    data = _next_data(html) if html else None
                    if not data:
                        break
                    bloc = ((data.get("props") or {}).get("pageProps") or {}).get("listings") or {}
                    items = bloc.get("listings") or []
                    if not items:
                        break
                    for it in items:
                        gid = str(it.get("id") or "")
                        if not gid or gid in vus:
                            continue
                        vus.add(gid)
                        if it.get("propertyType") not in (None, "CONDO"):
                            continue
                        proj = it.get("project") or {}
                        addr = proj.get("address") or ""
                        # province métropolitaine : Samut Prakan/Nonthaburi hors périmètre
                        if not addr.endswith("Bangkok"):
                            continue
                        ri = it.get("roomInformation") or {}
                        beds = ri.get("numberOfBed")
                        if beds is None:
                            beds = _ROOMTYPE_BEDS.get(ri.get("roomType") or "")
                        cover = _img(it.get("coverPicture"))
                        yield {
                            "source_url": f"{base}/en/listings/{it.get('slug')}---{gid}",
                            "source_id": gid,
                            "deal_type": deal,
                            "title": it.get("title"),
                            "price": _price(it.get("price"), deal),
                            "area_sqm": _num(ri.get("roomArea")),
                            "bedrooms": _int(beds),
                            "bathrooms": _int(ri.get("numberOfBath")),
                            "floor": ri.get("onFloor"),
                            "condo_name": (proj.get("nameEnglish") or proj.get("name") or "").strip() or None,
                            "project_id": str(proj.get("id") or "") or None,
                            "district": _district(addr),
                            "full_address": addr or None,
                            "refreshed_at": it.get("refreshedAt"),
                            "created_at": it.get("createdAt"),
                            "sponsor": it.get("sponsorPackage"),
                            "image_urls": [cover] if cover else [],
                        }
                        yielded += 1
                        if limit and yielded >= limit:
                            return
                    pag = bloc.get("pagination") or {}
                    if pag.get("totalPages") and page >= int(pag["totalPages"]):
                        break
        finally:
            self.sauver_cache()

    # ── fiche ─────────────────────────────────────────────────────────────
    def parse_listing(self, fetcher: Fetcher, stub: dict) -> dict | None:
        rec = dict(stub)
        rec["source"] = self.source
        rec["currency"] = "THB"
        rec["tenure"] = "freehold"   # condo : le leasehold n'est pas exposé en liste, voir _enrich
        rec.setdefault("amenities", [])
        if not rec.get("title"):
            name = stub.get("condo_name") or "Condo"
            rec["title"] = f"Condo — {name}"

        projet = self._projets.get(stub.get("project_id") or "")
        mode = self.config.get("fetch_detail", "si_projet_inconnu")
        if mode == "toujours" or (mode == "si_projet_inconnu" and not projet):
            self._enrich(fetcher, rec)
            projet = self._projets.get(stub.get("project_id") or "")
            if rec.get("_skip"):
                return None
        if projet and projet.get("lat") is not None:
            rec.setdefault("lat", projet["lat"])
            rec.setdefault("lng", projet["lng"])
            if projet.get("year_built") and not rec.get("year_built"):
                rec["year_built"] = projet["year_built"]
        if rec.get("price") is None:
            return None   # « prix sur demande » : rien d'exploitable pour les stats

        rec["raw_data"] = {k: stub.get(k) for k in
                           ("condo_name", "project_id", "bedrooms", "area_sqm", "floor",
                            "district", "price", "refreshed_at", "created_at", "sponsor")}
        for k in ("_lister_type", "_loyer_en_place"):
            if rec.get(k) is not None:
                rec["raw_data"][k.lstrip("_")] = rec[k]
        return rec

    def _enrich(self, fetcher: Fetcher, rec: dict) -> None:
        html = fetcher.get_text(rec["source_url"], referer=self.config["base_url"])
        if not html:
            return
        data = _next_data(html)
        pp = ((data or {}).get("props") or {}).get("pageProps") or {}
        L = pp.get("listing")
        if not isinstance(L, dict):
            return
        proj = L.get("project") or {}
        self._noter_projet(proj, fiche=True)
        for np in ((L.get("nearbyProjects") or {}).get("result") or []):
            self._noter_projet(np)
        if proj.get("location"):
            rec["lat"] = _num(proj["location"].get("lat"))
            rec["lng"] = _num(proj["location"].get("lng"))
        yb = _int(((proj.get("projectInfo") or {}).get("completedYear")))
        if yb:
            rec["year_built"] = yb
        # texte libre : `detail` est du HTML (<p>…) — la description, pas la page
        rec["description"] = description.clean(L.get("detail"))
        rec["page_text"] = description.texte_integral(html)
        # tenure : renseignée seulement pour les maisons (landAndHouseInformation)
        ten = str(((L.get("landAndHouseInformation") or {}).get("tenure")) or "").lower()
        if "lease" in ten:
            rec["tenure"] = "leasehold"
            if rec.get("deal_type") == "sale":
                rec["_skip"] = True
        fac = proj.get("facilities") or {}
        rec["amenities"] = [k for k, v in fac.items() if v is True][:30]
        # vendeur : identifiant + nature (particulier/agence), jamais ses coordonnées
        rec["agent_id"] = str(L.get("userId")) if L.get("userId") else None
        contacts = L.get("contactInformation") or []
        if contacts and isinstance(contacts[0], dict):
            rec["_lister_type"] = "agent" if contacts[0].get("isAgency") else "owner"
        # vente occupée : loyer en cours déclaré par le vendeur (rendement réel du lot)
        loyer = (((L.get("price") or {}).get("forSale") or {}).get("existingRentalContract") or {})
        if loyer.get("price"):
            rec["_loyer_en_place"] = _num(loyer.get("price"))
        imgs = [_img(i.get("pictureUrl")) for i in (L.get("images") or []) if isinstance(i, dict)]
        imgs = [u for u in imgs if u]
        if imgs:
            rec["image_urls"] = imgs[: self.config.get("image", {}).get("max_per_listing", 1)]
