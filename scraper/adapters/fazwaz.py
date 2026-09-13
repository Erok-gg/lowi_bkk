"""fazwaz.py — Adaptateur FazWaz.

Stratégie robuste & polie : les pages de LISTE exposent un JSON-LD
(SingleFamilyResidence) par annonce avec nom, chambres, surface, géo, district ;
le prix est lu dans le HTML de la carte. 1 requête de liste = N annonces.
La page de détail n'est requêtée que si `fetch_detail` est activé (galerie + SDB).

robots.txt FazWaz : /api/, /graphql et — depuis le 2026-09-12 — toute URL
portant `order_by=` sont interdits ; les pages d'annonces et les sitemaps
sont autorisés.

DEUX MODES DE DÉCOUVERTE (`config.discovery`) :
  - `list` (historique) : pages de liste paginées, JSON-LD par annonce, prix
    lu dans la carte HTML → dédup incrémentale sur le prix. Ne couvre que
    `max_pages` pages ; SANS `order_by` c'est 2,7 % du catalogue, et
    `order_by` est désormais interdit par robots.txt.
  - `sitemap` (depuis le 2026-09-13) : `sitemap-listings.xml` déclaré par
    robots.txt, un `<lastmod>` par annonce, catalogue entier. Le stub ne porte
    que l'URL, le slug et lastmod ; prix, surface, SDB, coordonnées et nom
    exact se lisent sur la fiche de détail (meta `title`/`description` +
    attributs `:lat`/`:lng`). Mesures et règles : pipeline/sitemap.py.
"""
from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path
from typing import Iterator
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup
from scrapling.parser import Adaptor

from adapters.base import BaseAdapter
from pipeline import description, sitemap
from pipeline.fetch import Fetcher

# Base sqlite du parsing adaptatif (scrapling) : pointee explicitement dans
# output/ (gitignore, hors venv) plutot que le defaut du paquet dans
# site-packages/, qui disparaitrait a chaque reconstruction du venv.
_ADAPTIVE_DB = str(Path(__file__).resolve().parent.parent / "output" / "scrapling-adaptive.db")

ID_RE = re.compile(r"-u(\d+)(?:[/?#]|$)")
PRICE_RE = re.compile(r"฿\s*([0-9][0-9,]*)")
# location FazWaz = /property-rent/ (singulier), vente = /property-sales/
LISTING_HREF_RE = re.compile(r"/property-(sales|rent)/[^\"'#?]+-u\d+")
OWNERSHIP_RE = re.compile(r'"ownership":\[\[(\d+)\]')
# Slug d'une URL d'annonce condo Bangkok du sitemap :
#   /property-sales/2-bedroom-condo-for-sale-at-aspire-sathorn-taksin-priva-in-bang-kho-bangkok-u6741301
# Le nom y est aplati (tirets) — la fiche donne le nom EXACT, qui prime.
SLUG_RE = re.compile(
    r"/property-(?:sales|rent)/(?:(studio)|(\d+)-bedroom)-condo-for-(?:sale|rent)"
    r"-at-(?P<name>.+?)-in-(?P<khwaeng>.+?)-bangkok-u(?P<id>\d+)$")
# Marqueurs de la FICHE (mode sitemap) — vérifiés le 2026-09-13 sur 17 fiches :
#   <meta name="title" content="2 Bedroom Condo for Sale at Aspire Sathorn-Taksin Priva for ฿4,045,300 | U6741301">
#   <meta name="description" content="This property is a 45 SqM condo with 2 bedrooms and 1 bathroom …">
#   <location-matrix … :lat="13.7128744" :lng="100.4635746" …>
META_TITLE_RE = re.compile(r'<meta\s+(?:name|property)="(?:og:)?title"\s+content="([^"]*)"')
META_DESC_RE = re.compile(r'<meta\s+(?:name|property)="(?:og:)?description"\s+content="([^"]*)"')
TITLE_RE = re.compile(r"^(?:(Studio)|(\d+)\s+Bedroom)\s+\S+\s+for\s+(?:Sale|Rent)\s+at\s+(?P<name>.+?)"
                      r"(?:\s+for\s+฿\s*(?P<price>[\d,]+)(?:/mo)?)?\s*\|\s*U\d+\s*$")
LATLNG_RE = re.compile(r':lat="(-?\d+\.\d+)"\s+:lng="(-?\d+\.\d+)"')
# Code d'ownership de l'unité FazWaz → (quota, freehold). Codes "Quota" = freehold ;
# leasehold/company (autres codes) = écartés (on ne scrape que du freehold).
FAZWAZ_OWNERSHIP = {1: ("thai", True), 2: ("foreigner", True)}


# Emplacement du PRIX sur la fiche (`.price-message`, localise par `statut_marche`
# via le parsing adaptatif). FazWaz y met normalement le montant
# (« ฿5,000,000 ») et le REMPLACE par un mot quand le lot n'est plus a vendre —
# c'est le « Sale Price | Sold » visible a l'ecran.

#: Mots qui, a cet emplacement, disent que le lot est SORTI DU MARCHE.
#: Tout le reste (un montant) signifie qu'il y est encore.
_STATUTS = {"sold": "sold", "rented": "rented", "reserved": "reserved",
            "under offer": "under_offer", "off market": "off_market"}


def statut_marche(html: str, url: str) -> str | None:
    """`sold`, `rented`… ou None si la fiche affiche un prix.

    POURQUOI CE CHAMP EXISTE. La section tension le disait en preambule :
    « delistage = vendu OU retire OU artefact de fenetre ». Trois causes tres
    differentes, agregees faute de pouvoir les separer. Une annonce marquee
    vendue AVANT de disparaitre les separe enfin — c'est le seul signal de
    VENTE directement observable dont on dispose, tout le reste etant du prix
    affiche.

    Signale par l'utilisateur le 2026-08-03 sur `u6588016` (The Alcove Thonglor
    10, Vadhana) : la page affichait « Sold », notre base la portait `active` a
    6 500 000 THB. Nous comptions un lot vendu comme de l'offre vivante.

    ⚠ PREVALENCE FAIBLE, mesuree : sur 45 annonces actives tirees au sort,
    ZERO n'etait marquee vendue (borne haute ~6,5 % a cet effectif). Ce n'est
    donc pas un biais massif — c'est un signal rare et sur, a ne pas confondre
    avec une correction de volume.

    ⚠ COUVERTURE PARTIELLE : le marqueur n'est present QUE sur la fiche de
    detail, absent de la page de liste (verifie). Il ne sera donc lu que pour
    les fiches reellement ouvertes — la dedup incrementale saute celles dont le
    prix n'a pas bouge, ce qui est precisement le cas d'un lot vendu dont le
    prix a disparu. Angle mort a garder en tete.

    LOCALISATION DU BLOC — parsing adaptatif (scrapling), 2026-08-29 : au lieu
    d'un regex fige sur `class="price-message"` (un renommage de classe cote
    FazWaz aurait fait taire ce signal SANS le moindre echec de `sonder()`,
    puisque le reste de la fiche continuerait de parser), le bloc est localise
    par selecteur CSS avec relocalisation par similarite structurelle
    (`auto_save`/`adaptive`) : un changement mineur de balisage se rattrape,
    un vrai changement de structure fait toujours remonter `[]` (comportement
    identique a l'ancien regex qui ne matchait plus rien).
    """
    page = Adaptor(content=html, url=url, adaptive=True,
                    storage_args={"storage_file": _ADAPTIVE_DB})
    els = page.css(".price-message", auto_save=True) or page.css(".price-message", adaptive=True)
    if not els:
        return None
    v = " ".join(els[0].get_all_text(strip=True, separator=" ").split()).lower()
    return _STATUTS.get(v)


class FazwazAdapter(BaseAdapter):
    source = "fazwaz"

    def __init__(self, config: dict):
        super().__init__(config)
        if self._mode_sitemap():
            # Sans page de liste, le prix n'existe que sur la fiche : un scan
            # sans détail écrirait des annonces sans prix.
            self.config["fetch_detail"] = True

    def _mode_sitemap(self) -> bool:
        return self.config.get("discovery", "list") == "sitemap"

    def sonder(self, fetcher: Fetcher) -> tuple[bool, str]:
        """FazWaz s'appuie sur un JSON-LD par annonce (ou `@graph` depuis
        juil. 2026) sur la page de liste — vérifié le marqueur AVANT de
        tenter une extraction complète. En mode sitemap : index → 1er fichier
        → 1 fiche (3 requêtes), chaque marqueur nommé dans le diagnostic."""
        if self._mode_sitemap():
            return self._sonder_sitemap(fetcher)
        searches = self.config.get("searches") or []
        if not searches:
            return False, "config sans 'searches'"
        base = self.config["base_url"]
        html = fetcher.get_text(urljoin(base + "/", searches[0]["path"].lstrip("/")))
        if not html:
            return False, "page de liste inaccessible (0 octet ou erreur réseau)"
        if "application/ld+json" not in html:
            return False, "JSON-LD absent de la page de liste (attendu : 1 bloc par annonce, ou '@graph' depuis juil. 2026)"
        # 2026-09-13 : la page SANS order_by passe (ci-dessus), mais
        # list_urls() (appelé par super().sonder) construit sa requête AVEC
        # order_by — si robots.txt l'interdit désormais, list_urls ne voit
        # jamais la vraie page et remonte "structure changée" à tort. Ce
        # n'est pas un parseur cassé : nommer la vraie cause ici évite de
        # chercher un changement de structure qui n'existe pas.
        order_by = self.config.get("order_by")
        if order_by:
            url_triee = urljoin(base + "/", searches[0]["path"].lstrip("/")) + \
                f"?order_by={quote(order_by, safe='')}"
            if not fetcher.allowed(url_triee):
                return False, (
                    f"robots.txt interdit désormais order_by ({url_triee}) — "
                    "PAS un changement de structure (la page sans order_by charge son "
                    "JSON-LD normalement). Décision de posture requise : voir "
                    "config/fazwaz.json._order_by_comment et CLAUDE.md § posture scraping "
                    "avant de toucher au tri par fraîcheur."
                )
        return super().sonder(fetcher)

    # ───────────────────────── sitemap ─────────────────────────
    def _sitemap_filter(self) -> re.Pattern:
        return re.compile(self.config.get(
            "sitemap_filter", r"condo-for-(?:sale|rent)-.*-bangkok-u\d+$"))

    def _deal_types(self) -> set[str]:
        return {s.get("deal_type", "sale") for s in self.config.get("searches") or []}

    def _stub_sitemap(self, entree: dict) -> dict | None:
        """Entrée de sitemap → stub, ou None si hors périmètre (autre ville,
        villa, deal_type non demandé). Le slug fournit un nom et un nombre de
        chambres provisoires (exclusions + titre) ; la fiche les précise."""
        url = entree["url"].split("?")[0].split("#")[0]
        if not self._sitemap_filter().search(url):
            return None
        deal = "rent" if "/property-rent/" in url else "sale"
        if deal not in self._deal_types():
            return None
        m = SLUG_RE.search(url)
        mid = ID_RE.search(url)
        stub = {
            "source_url": url,
            "source_id": mid.group(1) if mid else url,
            "deal_type": deal,
            "lastmod": entree.get("lastmod"),
            "image_url": entree.get("image"),
            "price": None,
        }
        if m:
            stub["condo_name"] = m.group("name").replace("-", " ").title()
            stub["bedrooms"] = 0 if m.group(1) else int(m.group(2))
            stub["district"] = m.group("khwaeng").replace("-", " ").title()
        return stub

    def _sonder_sitemap(self, fetcher: Fetcher) -> tuple[bool, str]:
        index_url = self.config.get("sitemap_index")
        if not index_url:
            return False, "config sans 'sitemap_index'"
        xml = fetcher.get_text(index_url)
        if not xml:
            return False, f"index sitemap inaccessible ({index_url}) — 0 octet ou erreur réseau"
        fichiers = sitemap.parse_index(xml)
        if not fichiers:
            return False, f"index sitemap sans <sitemapindex>/<loc> ({index_url})"
        xml1 = fetcher.get_text(fichiers[0])
        if not xml1:
            return False, f"1er fichier sitemap inaccessible ({fichiers[0]})"
        entrees = sitemap.parse_shard(xml1)
        stubs = [s for s in map(self._stub_sitemap, entrees) if s]
        if not stubs:
            return False, (f"1er fichier sitemap : {len(entrees)} <url> mais aucune ne passe "
                           f"le filtre '{self._sitemap_filter().pattern}' / deal_types {sorted(self._deal_types())}")
        if not any(s["lastmod"] for s in stubs):
            return False, "sitemap sans <lastmod> : plus de signal de fraîcheur (mode sitemap inutilisable tel quel)"
        # La fiche porte désormais TOUT (prix, surface, coordonnées) : ses
        # marqueurs font partie de la structure à sonder.
        frais = max(stubs, key=lambda s: s["lastmod"] or "")
        html = fetcher.get_text(frais["source_url"], referer=self.config["base_url"])
        if not html:
            return False, f"fiche de détail inaccessible ({frais['source_url']})"
        if not META_TITLE_RE.search(html):
            return False, "fiche de détail : <meta name=\"title\"> absente (prix/nom/chambres y sont lus)"
        if not LATLNG_RE.search(html):
            return False, "fiche de détail : attributs :lat/:lng absents (coordonnées y sont lues)"
        return True, (f"sitemap : {len(fichiers)} fichiers, {len(stubs)}/{len(entrees)} URL "
                      f"retenues dans le 1er, fiche OK ({frais['source_url'].rsplit('-', 1)[-1]})")

    def _entrees_sitemap(self, fetcher: Fetcher) -> list[dict]:
        cache = Path(self.config.get("sitemap_cache") or
                     Path(__file__).resolve().parent.parent / "output" / f"{self.source}-sitemap.json")
        ttl = float(self.config.get("sitemap_cache_minutes", 180))
        entrees = sitemap.lire_cache(cache, ttl)
        if entrees is not None:
            print(f"  sitemap : {len(entrees)} entrées relues du cache ({cache.name}, < {ttl:.0f} min)")
            return entrees
        xml = fetcher.get_text(self.config["sitemap_index"]) or ""
        fichiers = sitemap.parse_index(xml)
        entrees = []
        for i, f in enumerate(fichiers, 1):
            x = fetcher.get_text(f)
            if not x:
                # Un fichier manquant = un pan du catalogue invisible ce run.
                # Avec --full, ses annonces seraient « absentes » → délistées à
                # tort. On préfère rendre le scan incomplet et le dire.
                raise RuntimeError(f"fichier sitemap {i}/{len(fichiers)} inaccessible : {f}")
            part = sitemap.parse_shard(x)
            entrees.extend(part)
            print(f"  ── sitemap {i}/{len(fichiers)} : {len(part)} URL", flush=True)
        sitemap.ecrire_cache(cache, entrees)
        return entrees

    def _list_urls_sitemap(self, fetcher: Fetcher, limit: int | None) -> Iterator[dict]:
        stubs = [s for s in map(self._stub_sitemap, self._entrees_sitemap(fetcher)) if s]
        # Fraîcheur d'abord : le budget de visites de run.py (max_detail_visits)
        # tombe alors sur les mises à jour les plus récentes, et le retard se
        # reprend par la queue, jour après jour.
        stubs.sort(key=lambda s: s["lastmod"] or "", reverse=True)
        print(f"  sitemap : {len(stubs)} annonces dans le périmètre "
              f"({', '.join(sorted(self._deal_types()))}), triées par lastmod", flush=True)
        for i, stub in enumerate(stubs, 1):
            if limit and i > limit:
                return
            if i % 10000 == 0:
                print(f"  ── sitemap : {i}/{len(stubs)} parcourues", flush=True)
            yield stub

    # ───────────────────────── liste ─────────────────────────
    def list_urls(self, fetcher: Fetcher, limit: int | None = None) -> Iterator[dict]:
        if self._mode_sitemap():
            yield from self._list_urls_sitemap(fetcher, limit)
            return
        base = self.config["base_url"]
        page_param = self.config.get("page_param", "page")
        max_pages = self.config.get("max_pages", 1)
        order_by = self.config.get("order_by")  # ex. "user_updated_at|desc" — annonces les + fraîches d'abord
        yielded = 0

        for search in self.config["searches"]:
            path = search["path"]
            for page in range(1, max_pages + 1):
                url = urljoin(base + "/", path.lstrip("/"))
                params = []
                if page > 1:
                    params.append(f"{page_param}={page}")
                if order_by:
                    params.append(f"order_by={quote(order_by, safe='')}")
                if params:
                    url = f"{url}?{'&'.join(params)}"
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
            # depuis ~juil. 2026 : FazWaz regroupe tous les schémas d'une page
            # (Organization, RealEstateAgent, annonces) dans UN seul tag via "@graph"
            # au lieu d'un tag par annonce. On aplatit dans les deux cas.
            if isinstance(data, dict) and isinstance(data.get("@graph"), list):
                items = data["@graph"]
            elif isinstance(data, list):
                items = data
            else:
                items = [data]
            for item in items:
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
            if rec.get("_indisponible"):
                # Fiche injoignable et AUCUN prix connu (mode sitemap) : ne pas
                # écrire une annonce sans prix. run.py la retire des « vues ».
                stub["_indisponible"] = True
                return None
            # Freehold uniquement — UNIQUEMENT pour la vente. Une location n'a pas
            # de notion de quota/tenure → on ne la jette jamais.
            if rec.get("deal_type") == "sale" and rec.get("_skip"):
                return None
            beds = rec.get("bedrooms")
            name = rec.get("condo_name") or "Condo"
            rec["title"] = f"{beds}BR condo — {name}" if beds else f"Condo — {name}"

        rec["raw_data"] = {k: rec.get(k) for k in
                           ("condo_name", "bedrooms", "area_sqm", "lat", "lng", "district", "price", "lastmod")}
        return rec

    def _completer_depuis_fiche(self, html: str, rec: dict) -> None:
        """Mode sitemap : le stub n'a ni prix, ni surface, ni coordonnées — la
        page de liste qui les portait (JSON-LD) n'est plus parcourue. La fiche
        les expose dans ses meta `title`/`description` et sur le composant
        carte. Le nom EXACT de la fiche remplace le nom aplati du slug (les
        regroupements par immeuble en dépendent)."""
        mt = META_TITLE_RE.search(html)
        if mt:
            t = TITLE_RE.match(unescape(mt.group(1)).strip())
            if t:
                rec["condo_name"] = t.group("name").strip()
                rec["bedrooms"] = 0 if t.group(1) else int(t.group(2))
                if t.group("price") and rec.get("price") is None:
                    rec["price"] = int(t.group("price").replace(",", ""))
        # Surface et SDB : la meta description les porte quand elle est
        # générée (« This property is a 45 SqM condo with … 1 bathroom »), mais
        # l'agent peut l'avoir rédigée lui-même — mesuré le 2026-09-13 : 18/40
        # fiches sans SqM, 16/40 sans SDB par la meta seule. Repli sur le bloc
        # d'infos de la fiche : « 118 SqM <small>Size</small> » et
        # « 2 <small> Bathrooms </small> ».
        md = META_DESC_RE.search(html)
        d = unescape(md.group(1)) if md else ""
        ms = (re.search(r"(\d+(?:\.\d+)?)\s*SqM", d)
              or re.search(r"(\d+(?:\.\d+)?)\s*SqM\s*<small>\s*Size", html))
        if ms and rec.get("area_sqm") is None:
            rec["area_sqm"] = float(ms.group(1))
        mb = (re.search(r"(\d+)\s+bathroom", d)
              or re.search(r"(\d+)\s*<small>\s*Bathrooms?\s*</small>", html))
        if mb:
            rec["bathrooms"] = int(mb.group(1))
        ml = LATLNG_RE.search(html)
        if ml and rec.get("lat") is None:
            rec["lat"], rec["lng"] = float(ml.group(1)), float(ml.group(2))

    def _enrich_from_detail(self, fetcher: Fetcher, rec: dict) -> None:
        html = fetcher.get_text(rec["source_url"], referer=self.config["base_url"])
        if not html:
            if rec.get("price") is None:
                rec["_indisponible"] = True
            return
        if rec.get("price") is None:
            self._completer_depuis_fiche(html, rec)
        rec["description"] = description.extract(html)
        rec["page_text"] = description.texte_integral(html)
        rec["market_status"] = statut_marche(html, rec["source_url"])
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

        # année de livraison du PROJET (pas de l'annonce) : FazWaz l'écrit sous
        # la forme "Completed (Mar 2024)" ou "completed in Mar 2024". Propriété
        # de l'immeuble → alimente la table `condos` et vaut ensuite pour toutes
        # ses annonces, passées et futures.
        my = (re.search(r"Completed\s*\(\s*(?:\w+\s+)?(\d{4})\s*\)", html)
              or re.search(r"completed\s+in\s+(?:\w+\s+)?(\d{4})", html, re.I))
        if my and 1970 <= int(my.group(1)) <= 2040:
            rec["year_built"] = int(my.group(1))

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
