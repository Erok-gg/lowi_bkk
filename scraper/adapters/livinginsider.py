"""livinginsider.py — Adaptateur LivingInsider.

Site 100% serveur (aucun JS requis pour lire le contenu utile — vérifié par
fetch brut sans navigateur). robots.txt ouvert (`User-agent: *` sans Disallow
sur /searchword_en/ ni /detail_en/, sitemaps publiés).

Contrairement à FazWaz/DDproperty/PropertyScout, la page de LISTE
(`/searchword_en/Condo/<Buysell|Rent>/<page>/...`) n'expose qu'un ld+json
`ItemList` d'URLs nues — aucun prix/surface/chambre en liste. Chaque fiche est
donc TOUJOURS visitée (pas de dédup incrémentale possible côté liste : le stub
n'a pas de prix à comparer).

Flux national, pas de filtre géo à la source. Bangkok se filtre à la fiche, à
partir du texte libre de l'adresse (« … District, Bangkok », comme DDproperty
filtre sur `fullAddress.endswith("Bangkok")`) : toute fiche sans "Bangkok"
dans son adresse est écartée.

Pas de coordonnées serveur (uniquement des marqueurs de POI proches sur la
carte, jamais le bien lui-même) → comme Nestopa, le khet est posé en texte
brut et les coordonnées viennent du géocodage (`--geocode`).

Aucun champ tenure/quota par fiche (seulement des filtres de RECHERCHE
globaux « Freehold/Leasehold », « Foreign Quota » — jamais un attribut de
l'annonce elle-même). Freehold par défaut (comme DDproperty quand `tenureCode`
est absent), quota toujours None.

Vérifié le 2026-08-05 : contrairement à DotProperty (voir
agents/state/watch-sources/registre.json), les images sont servies depuis
www.livinginsider.com (galerie propre, pas de CDN FazWaz/DDproperty/
PropertyScout) — inventaire indépendant, pas une resyndication.
"""
from __future__ import annotations

import html as _html
import json
import re
from datetime import datetime, timezone
from typing import Iterator
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from adapters.base import BaseAdapter
from pipeline import description
from pipeline.fetch import Fetcher

LD_RE = re.compile(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
ID_RE = re.compile(r"-(\d+)/?(?:[?#]|$)")
# Format d'adresse INCONSTANT selon les fiches (vérifié le 2026-08-05 sur 17
# fiches réelles) : tantôt propre "... <District> District, Bangkok", tantôt
# du thaï mélangé sans le mot "District" du tout ("... Hua Mak Bang Kapi
# Bangkok 10240"). Deux motifs, du plus au moins précis :
#   1) forme propre → nom de district exact.
#   2) "<...> Bangkok <code postal 10xxx>" → on prend les 2 derniers mots
#      avant "Bangkok" comme meilleure estimation (district ou sous-district,
#      canonisé ensuite par KhetMatcher.canoniser ; à défaut, --geocode
#      rattrape via lat/lng).
# Le code postal 10xxx exclut Samut Prakan/Chon Buri (postaux hors plage)
# et les zones touristiques (Pattaya, Phuket, Chiang Mai, Khao Yai...) —
# vérifié : 0 faux positif sur 17 fiches réelles, dont 3 hors Bangkok.
DISTRICT_CLEAN_RE = re.compile(r"([A-Za-z][A-Za-z\s]*?)\s+District,\s*Bangkok")
BANGKOK_POSTAL_RE = re.compile(r"([A-Za-z][A-Za-z\s]{2,40}?)\s+Bangkok\s+10\d{3}\b")
CREATED_RE = re.compile(r"Created\s+(\d{2})/(\d{2})/(\d{4})")
# Galerie : images uploadées par les agents (exclut logos/icônes/placeholders).
GALLERY_RE = re.compile(
    r"https://www\.livinginsider\.com/upload/topic\d+/[^\s\"'<>]+?\.(?:jpe?g|png|webp)", re.I)


def _ld_blocks(html: str) -> list[dict]:
    out = []
    for raw in LD_RE.findall(html):
        try:
            d = json.loads(raw.strip())
        except json.JSONDecodeError:
            continue
        out.append(d)
    return out


def _find_type(blocks: list[dict], type_: str) -> dict | None:
    for d in blocks:
        if isinstance(d, dict) and d.get("@type") == type_:
            return d
    return None


def _num(v):
    try:
        return float(v) if v not in (None, "", "null") else None
    except (TypeError, ValueError):
        return None


class LivinginsiderAdapter(BaseAdapter):
    source = "livinginsider"

    # ───────────────────────── liste ─────────────────────────
    def sonder(self, fetcher: Fetcher) -> tuple[bool, str]:
        """LivingInsider : flux ld+json `ItemList` d'URLs nues sur la page
        de liste — aucun prix/surface en liste (contrairement aux 3 autres
        sources récentes), donc rien d'autre à vérifier à ce stade."""
        searches = self.config.get("searches") or []
        if not searches:
            return False, "config sans 'searches'"
        base = self.config["base_url"]
        path = searches[0]["path"].replace("{page}", "1")
        html = fetcher.get_text(urljoin(base + "/", path.lstrip("/")), referer=base)
        if not html:
            return False, "page de liste inaccessible (0 octet ou erreur réseau)"
        item_list = _find_type(_ld_blocks(html), "ItemList")
        if not item_list or not item_list.get("itemListElement"):
            return False, "ld+json 'ItemList' absent ou vide sur la page de liste"
        return super().sonder(fetcher)

    def list_urls(self, fetcher: Fetcher, limit: int | None = None) -> Iterator[dict]:
        base = self.config["base_url"]
        max_pages = self.config.get("max_pages", 1)
        yielded = 0

        for search in self.config["searches"]:
            deal = search["deal_type"]
            for page in range(1, max_pages + 1):
                # pagination par chemin : /searchword_en/Condo/Buysell/<page>/<slug>.html
                path = search["path"].replace("{page}", str(page))
                url = urljoin(base + "/", path.lstrip("/"))
                html = fetcher.get_text(url, referer=base)
                if not html:
                    break
                item_list = _find_type(_ld_blocks(html), "ItemList")
                items = (item_list or {}).get("itemListElement") or []
                if not items:
                    break
                seen_this_page = 0
                for it in items:
                    src_url = (it.get("url") or "").split("?")[0].split("#")[0]
                    if not src_url:
                        continue
                    m = ID_RE.search(src_url)
                    if not m:
                        continue
                    seen_this_page += 1
                    yield {
                        "source_url": src_url,
                        "source_id": m.group(1),
                        "deal_type": deal,
                    }
                    yielded += 1
                    if limit and yielded >= limit:
                        return
                if seen_this_page == 0:
                    break

    # ───────────────────────── détail ─────────────────────────
    def parse_listing(self, fetcher: Fetcher, stub: dict) -> dict | None:
        html = fetcher.get_text(stub["source_url"], referer=self.config["base_url"])
        if not html:
            return None

        rec = dict(stub)
        rec["source"] = self.source
        rec["currency"] = "THB"
        rec["amenities"] = []
        rec["image_urls"] = []
        # tenure jamais exposée par fiche (seulement un filtre de recherche
        # global) → freehold par défaut, comme DDproperty quand tenureCode
        # est absent. quota jamais exposé → None.
        rec["tenure"] = "freehold"

        blocks = _ld_blocks(html)
        product = _find_type(blocks, "Product")
        breadcrumb = _find_type(blocks, "BreadcrumbList")

        rec["description"] = description.extract(html)
        rec["page_text"] = description.texte_integral(html)
        full_text = rec["page_text"] or ""

        # Bangkok uniquement — le flux est national, on filtre à la fiche.
        dm = DISTRICT_CLEAN_RE.search(full_text)
        if dm:
            rec["district"] = dm.group(1).strip()
        else:
            pm = BANGKOK_POSTAL_RE.search(full_text)
            if not pm:
                return None  # ni forme propre ni code postal Bangkok → pas Bangkok (ou trop ambigu)
            words = pm.group(1).strip().split()
            rec["district"] = " ".join(words[-2:]) if words else None

        if product:
            offers = product.get("offers") or {}
            rec["price"] = _num(offers.get("price"))
            rec["source_id"] = str(product.get("sku") or stub.get("source_id"))
            img = product.get("image")
            if img:
                rec["image_urls"].append(img)
        raw_title = (product or {}).get("name") or stub.get("source_url")
        rec["title"] = _html.unescape(raw_title) if raw_title else raw_title

        # nom d'immeuble : 3e maillon du fil d'Ariane (Accueil > Zone > Projet > Annonce)
        if breadcrumb:
            crumbs = breadcrumb.get("itemListElement") or []
            proj = next((c for c in crumbs if c.get("position") == 3), None)
            if proj and proj.get("name"):
                rec["condo_name"] = _html.unescape(proj["name"])

        # bloc "Property information" : Floor Size / Bedrooms / Bathrooms,
        # en paires étiquette|valeur (dupliquées desktop+mobile dans le DOM,
        # on prend juste la première occurrence de chaque étiquette).
        soup = BeautifulSoup(html, "html.parser")
        title_span = soup.find("span", class_="property-inform-title")
        if title_span:
            container = title_span.find_parent("div", class_="form-group")
            block = container.find_next_sibling("div") if container else None
            if block:
                txt = block.get_text("|", strip=True)
                m = re.search(r"Floor Size\|([\d.]+)", txt)
                if m:
                    rec["area_sqm"] = _num(m.group(1))
                m = re.search(r"\bBedrooms\|(\d+)", txt)
                if m:
                    rec["bedrooms"] = int(m.group(1))
                m = re.search(r"\bBathrooms\|(\d+)", txt)
                if m:
                    rec["bathrooms"] = int(m.group(1))

        # date de publication annoncée par le site ("Created DD/MM/YYYY").
        # Comme pour DDproperty : mesure le time-on-market à la source, mais
        # PAS un substitut fiable à first_seen (cf. journal technique
        # 2026-08-02 sur DDproperty — même prudence tant que non vérifié ici).
        cm = CREATED_RE.search(full_text)
        if cm:
            d, mo, y = cm.groups()
            try:
                rec["posted_at"] = datetime(
                    int(y), int(mo), int(d), tzinfo=timezone.utc
                ).isoformat()
            except ValueError:
                pass

        # galerie : images uploadées, dédupliquées, hors icônes/placeholders
        max_imgs = self.config.get("image", {}).get("max_per_listing", 1)
        seen, gallery = set(list(rec["image_urls"])), list(rec["image_urls"])
        for u in GALLERY_RE.findall(html):
            if u in seen:
                continue
            seen.add(u)
            gallery.append(u)
            if len(gallery) >= max_imgs:
                break
        rec["image_urls"] = gallery

        rec["raw_data"] = {k: rec.get(k) for k in
                           ("condo_name", "bedrooms", "area_sqm", "district", "price")}
        return rec
