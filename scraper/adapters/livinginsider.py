"""livinginsider.py — Adaptateur LivingInsider.

⚠ ÉTAT AU 2026-10-20 — deux modes, `mode` dans la config :
  * "liste" (défaut) : on lit les CARTES des pages de liste et on n'ouvre plus
    aucune fiche. Raison mesurée : depuis le 25/09, chaque fiche répond
    202 + `x-amzn-waf-action: challenge` (AWS WAF, corps de 2 012 octets) ;
    depuis le 20/10 au plus tard, la liste LOCATION aussi. La liste VENTE
    passe en 200 et ses cartes portent prix, surface, chambres, SDB, étage et
    nom d'immeuble — assez pour une annonce, et assez pour la dédup
    incrémentale que l'ancienne liste (ItemList d'URL nues) interdisait.
    Ce qu'on perd : description, page_text, posted_at, galerie complète.
  * "fiche" : l'ancien chemin (visite de chaque fiche), gardé pour le jour où
    le blocage serait levé. Il NE contourne PAS le challenge : une fiche
    bloquée est marquée indisponible, pas parsée.
  Franchir le challenge (navigateur réel, jeton `aws-waf-token`) est une
  décision de posture laissée à l'utilisateur — voir le journal du 2026-10-20.

  La refonte du site (vers le 17/09) a aussi changé la pagination :
  `/searchword_en/.../<n>/...` sert toujours la page 1 et son ItemList est un
  bloc figé de 12 URL ; la vraie liste est `/en/condo-buysell/<n>`.

  Filtre Bangkok en mode liste : une carte ne dit PAS où est le bien (ni
  province ni district dans le HTML, vérifié). On ne garde donc que les
  immeubles déjà connus à Bangkok par les autres sources (référentiel lu dans
  la base locale), qui fournit aussi khet et coordonnées. Mesuré sur 120
  cartes : 77 reconnues ; les écartées sont surtout Pattaya / Hua Hin /
  Samut Prakan, mais aussi quelques vrais immeubles de Bangkok absents du
  référentiel (Via Botani, Waterford Diamond…) — on préfère perdre une
  annonce que d'en importer une hors Bangkok.

Historique (mode fiche, 2026-08-05) :

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
from pathlib import Path
from typing import Iterator
import sqlite3
import statistics
from urllib.parse import unquote, urljoin

from scrapling.parser import Adaptor

from adapters.base import BaseAdapter
from pipeline import description
from pipeline.fetch import Fetcher
from pipeline.normalize import _norm_condo

# Cf. adapters/fazwaz.py : meme base sqlite de parsing adaptatif, pointee hors
# venv pour survivre a sa reconstruction.
_ADAPTIVE_DB = str(Path(__file__).resolve().parent.parent / "output" / "scrapling-adaptive.db")

LD_RE = re.compile(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
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


# ───────────────────────── challenge AWS WAF ─────────────────────────
# Le challenge arrive en 202 avec un corps HTML de ~2 Ko qui pose un jeton en
# JS (`window.awsWafCookieDomainList`). `Fetcher.get_text()` rend le corps
# quel que soit le statut : sans ce test, le challenge passait pour une fiche
# « hors Bangkok » et la source tournait « ok » à 0 annonce (défaut du
# 25/09 → 20/10). Le seuil de taille évite de confondre avec une vraie page
# qui citerait le mot (les vraies pages pèsent 0,5 à 2 Mo).
WAF_MARQUEUR = "awsWafCookie"
WAF_TAILLE_MAX = 20_000


def est_challenge(html: str | None) -> bool:
    return bool(html) and len(html) < WAF_TAILLE_MAX and WAF_MARQUEUR in html


# ───────────────────────── cartes de liste ─────────────────────────
CARD_ID_RE = re.compile(r"-(\d+)/?$")
PRICE_RE = re.compile(r"฿\s*([\d,]+(?:\.\d+)?)")
# Un MORCEAU de prix entier : « ฿ 4,500,000 », « ฿ 5.6M », « ฿ 22K /mo ».
# Plein-match obligatoire : un titre comme « … | ฿39.9M » ou « ฿188,000,000🌟 »
# ne doit pas fournir le prix. Le premier jet lisait « le premier ฿ venu » sans
# suffixe : 49 annonces sur 801 sont sorties à 2,4 à 119 THB (scan du 20/10).
PRICE_TOKEN_RE = re.compile(r"^฿\s*([\d,]+(?:\.\d+)?)\s*([MK])?\s*(/\s*mo)?$", re.I)
MULT = {None: 1, "M": 1_000_000, "K": 1_000}
SEP = "\x1f"
AREA_RE = re.compile(r"^([\d.,]+)\s*Sq\.?m", re.I)
FLOOR_RE = re.compile(r"^Fl\.\s*(.+)$")
BEDS_RE = re.compile(r"^(Studio|\d+)$", re.I)
# Référence interne d'agence en tête de titre, ex. « (A010668) Lumpini … ».
TITLE_REF_RE = re.compile(r"^\([A-Z0-9-]{3,}\)\s*")


def _carte_vers_stubs(anchor, base: str, deal: str) -> list[dict]:
    """Lit une carte de liste (2026-10-20). `anchor` = le lien de détail qui
    porte le texte de la carte. Ordre des morceaux observé :
    Condo | Sell | <titre> | <immeuble> | <ch.> | <SDB> | Fl. x | <m²> Sq.m. |
    ฿ <prix> | (<prix/m²>) | Created/Boosted … — l'immeuble peut manquer, d'où
    la lecture par motifs plutôt que par position fixe.

    Une carte « Sell&Rent » porte DEUX prix, arrondis : « ฿ 5.6M » (vente) et
    « ฿ 22K /mo » (loyer). On en tire deux annonces (même identifiant, deux
    deal_type, comme FazWaz) : c'est le seul accès aux loyers tant que la liste
    location est derrière le challenge."""
    href = anchor.attrib.get("href") or ""
    m = CARD_ID_RE.search(href.split("?")[0])
    if not m:
        return []
    # Séparateur \x1f (unit separator) et non « | » : les titres d'annonce
    # contiennent souvent des « | » (« 2BR | … | ฿39.9M »), qui les découpaient
    # en morceaux dont un passait pour le prix.
    parts = [p for p in anchor.get_all_text(separator=SEP, strip=True).split(SEP) if p]
    prix: dict[str, tuple[float, bool]] = {}          # deal -> (prix, arrondi ?)
    for p in parts:
        t = PRICE_TOKEN_RE.match(p.strip())
        if not t:
            continue
        unite = (t.group(2) or "").upper() or None
        v = _num(t.group(1).replace(",", ""))
        if v is None:
            continue
        d = "rent" if t.group(3) else ("sale" if unite == "M" or deal == "sale" else deal)
        prix.setdefault(d, (v * MULT[unite], unite is not None))
    if not prix:
        return []
    title_el = anchor.css("p[title]")
    title = (title_el[0].attrib.get("title") if title_el else None) or ""
    title = _html.unescape(title).strip()

    # Immeuble = premier texte du bloc QUI SUIT le titre dans le DOM. La
    # lecture par position dans le texte (« le morceau après le titre »)
    # rendait « Condo » — l'étiquette de catégorie — sur 1 carte sur 6 :
    # l'attribut `title` et le texte affiché diffèrent dès qu'il y a un emoji
    # ou une double espace, et le titre n'était alors pas retrouvé.
    condo = None
    sib = title_el[0].next if title_el else None
    if sib is not None:
        txt = [t for t in sib.get_all_text(separator=SEP, strip=True).split(SEP) if t]
        if txt and not (BEDS_RE.match(txt[0]) or AREA_RE.match(txt[0])
                        or FLOOR_RE.match(txt[0]) or PRICE_RE.search(txt[0])):
            condo = txt[0].strip()

    # caractéristiques : après le titre (le titre lui-même peut contenir « 1 »)
    i = next((k + 1 for k, p in enumerate(parts) if p.strip() == title), 0)
    if not i and condo:
        i = next((k + 1 for k, p in enumerate(parts) if p.strip() == condo), 0)
    beds = baths = area = floor = None
    specs = [p for p in parts[i:] if BEDS_RE.match(p) or AREA_RE.match(p) or FLOOR_RE.match(p)]
    nums = [p for p in specs if BEDS_RE.match(p)]
    if nums:
        beds = 0 if nums[0].lower() == "studio" else int(nums[0])
    if len(nums) > 1 and nums[1].isdigit():
        baths = int(nums[1])
    for p in specs:
        if AREA_RE.match(p):
            area = _num(AREA_RE.match(p).group(1).replace(",", ""))
        elif FLOOR_RE.match(p):
            floor = FLOOR_RE.match(p).group(1)

    url = urljoin(base + "/", unquote(href).lstrip("/")) if href.startswith("/") else href
    return [{
        "source_url": url.split("?")[0],
        # Préfixe « LV » : c'est l'identifiant que portaient les 9 318 lignes
        # écrites en mode fiche (`sku` du ld+json Product). Sans lui, chaque
        # annonce déjà connue renaîtrait sous un second id.
        "source_id": "LV" + m.group(1),
        "deal_type": d,
        "title": TITLE_REF_RE.sub("", title) or condo,
        "condo_name": condo,
        "price": v,
        "_prix_arrondi": arrondi,
        "area_sqm": area,
        "bedrooms": beds,
        "bathrooms": baths,
        "_etage": floor,
    } for d, (v, arrondi) in prix.items()]


def _image_carte(card) -> str | None:
    for img in card.css("img"):
        src = img.attrib.get("src") or ""
        if "/upload/" in src and "mod_member" not in src:   # photo du bien, pas l'avatar de l'agent
            return src
    return None


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

    # ───────────────────────── état du run ─────────────────────────
    def _mode(self) -> str:
        return self.config.get("mode", "liste")

    def _etat(self) -> dict:
        """Compteurs du run, lus par `ids_hors_couverture` et imprimés en fin
        de recherche. Pas d'`__init__` surchargé : la base n'en attend pas."""
        if not hasattr(self, "_e"):
            self._e = {"bloques": set(), "challenges": 0, "hors_ref": 0, "vus": set()}
        return self._e

    def _page_url(self, search: dict, page: int) -> str:
        base = self.config["base_url"]
        if page == 1 and search.get("path_first"):
            path = search["path_first"]
        else:
            path = search["path"].replace("{page}", str(page))
        return urljoin(base + "/", path.lstrip("/"))

    # ───────────────────────── référentiel Bangkok ─────────────────────────
    def _referentiel(self) -> dict[str, tuple]:
        """Immeuble normalisé → (khet, lat, lng), d'après les AUTRES sources.

        C'est le filtre Bangkok du mode liste (une carte ne dit pas où est le
        bien) ET la source de son khet et de ses coordonnées. Khet = le plus
        fréquent, coordonnées = médianes : une annonce mal géolocalisée ne
        déplace pas l'immeuble. Lu une fois par run (~5 000 immeubles)."""
        if hasattr(self, "_ref"):
            return self._ref
        chemin = Path(self.config.get("referentiel_db") or
                      Path(__file__).resolve().parent.parent / "output" / "bangkok.db")
        acc: dict[str, dict] = {}
        try:
            db = sqlite3.connect(f"file:{chemin}?mode=ro", uri=True)
            rows = db.execute(
                "select condo_name, khet, lat, lng from listings "
                "where source != ? and condo_name is not null and khet is not null",
                (self.source,)).fetchall()
            db.close()
        except sqlite3.Error as e:
            print(f"  ⚠ référentiel immeubles illisible ({chemin}) : {e} — aucune carte retenue")
            rows = []
        for name, khet, lat, lng in rows:
            k = _norm_condo(name)
            if not k:
                continue
            d = acc.setdefault(k, {"khet": {}, "lat": [], "lng": []})
            d["khet"][khet] = d["khet"].get(khet, 0) + 1
            if lat is not None and lng is not None:
                d["lat"].append(lat)
                d["lng"].append(lng)
        self._ref = {
            k: (max(d["khet"], key=d["khet"].get),
                statistics.median(d["lat"]) if d["lat"] else None,
                statistics.median(d["lng"]) if d["lng"] else None)
            for k, d in acc.items()}
        print(f"  référentiel Bangkok : {len(self._ref)} immeubles connus des autres sources")
        return self._ref

    # ───────────────────────── liste ─────────────────────────
    def sonder(self, fetcher: Fetcher) -> tuple[bool, str]:
        """Page 1 de la PREMIÈRE recherche : challenge WAF, puis présence de
        cartes lisibles (lien de détail + prix). L'ancien marqueur (ItemList
        ld+json) a survécu à la refonte sous forme de bloc figé et laissait
        passer une source morte (« 1 stub obtenu » chaque nuit, 17/09 → 18/10)."""
        searches = self.config.get("searches") or []
        if not searches:
            return False, "config sans 'searches'"
        url = self._page_url(searches[0], 1)
        html = fetcher.get_text(url, referer=self.config["base_url"])
        if not html:
            return False, "page de liste inaccessible (0 octet ou erreur réseau)"
        if est_challenge(html):
            return False, (f"challenge AWS WAF sur la page de liste ({url}) — "
                           "pas de contournement sans décision (posture)")
        doc = Adaptor(content=html, url=url)
        cartes = [s for a in doc.css('a[href*="/en/detail/"]')
                  for s in _carte_vers_stubs(a, self.config["base_url"], searches[0]["deal_type"])]
        if not cartes:
            return False, "aucune carte lisible (lien /en/detail/ + prix ฿) sur la page de liste"
        return True, f"page 1 ok — {len(cartes)} cartes lisibles ({cartes[0]['source_id']})"

    def list_urls(self, fetcher: Fetcher, limit: int | None = None) -> Iterator[dict]:
        base = self.config["base_url"]
        max_pages = self.config.get("max_pages", 1)
        mode_liste = self._mode() == "liste"
        ref = self._referentiel() if mode_liste else {}
        etat = self._etat()
        yielded = 0

        for search in self.config["searches"]:
            deal = search["deal_type"]
            n_cartes = n_retenues = n_hors_ref = 0
            for page in range(1, max_pages + 1):
                url = self._page_url(search, page)
                html = fetcher.get_text(url, referer=base)
                if not html:
                    break
                if est_challenge(html):
                    # On s'arrête net : insister ne ferait que confirmer au
                    # pare-feu qu'un robot frappe à la porte.
                    etat["bloques"].add(deal)
                    etat["challenges"] += 1
                    print(f"  [WAF-CHALLENGE] {self.source} {deal} page {page} : challenge "
                          f"AWS WAF (202) — recherche abandonnée, aucun contournement")
                    break
                doc = Adaptor(content=html, url=url)
                neuves = 0
                stubs = ((a, st) for a in doc.css('a[href*="/en/detail/"]')
                         for st in _carte_vers_stubs(a, base, deal))  # lien image : aucun
                for anchor, stub in stubs:
                    key = (stub["deal_type"], stub["source_id"])
                    if key in etat["vus"]:
                        continue                 # carte « boostée » répétée de page en page
                    etat["vus"].add(key)
                    neuves += 1
                    n_cartes += 1
                    if mode_liste:
                        hit = ref.get(_norm_condo(stub.get("condo_name")))
                        if not hit:
                            n_hors_ref += 1
                            continue
                        stub["district"], stub["lat"], stub["lng"] = hit
                        # la photo est dans le bloc frère du lien texte
                        img = _image_carte(anchor.parent) if anchor.parent is not None else None
                        stub["image_urls"] = [img] if img else []
                        if not img:
                            stub["_sans_image"] = True
                    n_retenues += 1
                    yield stub
                    yielded += 1
                    if limit and yielded >= limit:
                        return
                if neuves == 0:
                    break                        # fin de pagination (ou page identique)
            etat["hors_ref"] += n_hors_ref
            print(f"  ── liste {deal} : {n_cartes} cartes distinctes, {n_retenues} retenues"
                  + (f", {n_hors_ref} hors référentiel Bangkok" if mode_liste else ""))

    def ids_hors_couverture(self, store, deal_type: str | None) -> set[str]:
        """Ne pas délister ce que le scan ne POUVAIT pas voir :
        1. tout un type d'annonce dont la liste a renvoyé un challenge
           (location depuis le 20/10) — l'absence n'y prouve rien ;
        2. en mode liste, les annonces dont l'immeuble n'est pas au
           référentiel : écrites en mode fiche (filtre par adresse), elles sont
           écartées ici par construction, pas parce qu'elles ont disparu."""
        etat = self._etat()
        proteges: set[str] = set()
        for deal in etat["bloques"]:
            if deal_type in (None, deal):
                proteges |= store.ids_actifs(self.source, deal)
        db = getattr(store, "db", None)
        if self._mode() == "liste" and db is not None:
            ref = self._referentiel()
            q = "select id, condo_name from listings where source=? and status='active'"
            params: list = [self.source]
            if deal_type:
                q += " and deal_type=?"
                params.append(deal_type)
            for lid, name in db.execute(q, params).fetchall():
                if _norm_condo(name) not in ref:
                    proteges.add(lid)
        return proteges

    # ───────────────────────── détail ─────────────────────────
    def parse_listing(self, fetcher: Fetcher, stub: dict) -> dict | None:
        if self._mode() == "liste":
            return self._depuis_carte(stub)
        html = fetcher.get_text(stub["source_url"], referer=self.config["base_url"])
        if not html:
            return None
        if est_challenge(html):
            # Ni écrite ni comptée comme vue : run.py la retire de seen_ids,
            # un --full ne la croira donc pas vivante.
            stub["_indisponible"] = True
            self._etat()["challenges"] += 1
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
        #
        # Localisation par parsing adaptatif (scrapling, 2026-08-29) au lieu
        # d'un chemin DOM figé (span.property-inform-title → div.form-group
        # parent → div frère suivant) : un renommage de classe ou de balise
        # côté LivingInsider se rattrape par similarité structurelle au lieu
        # de faire disparaître silencieusement Floor Size/Bedrooms/Bathrooms
        # de toutes les fiches sans qu'aucun sonder() ne s'en aperçoive (le
        # marqueur de structure de LivingInsider est le ld+json de liste,
        # indépendant de ce bloc HTML de détail).
        page = Adaptor(content=html, url=rec["source_url"], adaptive=True,
                        storage_args={"storage_file": _ADAPTIVE_DB})
        title_els = (page.css(".property-inform-title", auto_save=True)
                     or page.css(".property-inform-title", adaptive=True))
        # Parent DIRECT du titre (pas filtre par classe, contrairement à
        # l'original `find_parent("div", class_="form-group")`) : la classe du
        # conteneur n'est pas ce qui nous interesse, seule la relation
        # « le bloc de valeurs suit son parent » compte, et elle survit à un
        # renommage de classe sur le conteneur ou le titre lui-même.
        parent = title_els[0].parent if title_els else None
        block = parent.next if parent is not None else None
        if block:
            txt = block.get_all_text(separator="|", strip=True)
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

    def _depuis_carte(self, stub: dict) -> dict:
        """Enregistrement complet à partir de la seule carte de liste.
        Coordonnées = celles de l'IMMEUBLE au référentiel, pas du lot : c'est
        dit dans raw_data pour qu'aucune analyse ne les prenne pour une
        géolocalisation propre à l'annonce."""
        rec = {k: v for k, v in stub.items() if not k.startswith("_")}
        rec.update({
            "source": self.source,
            "currency": "THB",
            "amenities": [],
            "tenure": "freehold",          # jamais exposée par annonce (cf. mode fiche)
            "image_urls": stub.get("image_urls") or [],
        })
        rec["raw_data"] = {
            "mode": "liste",
            "etage": stub.get("_etage"),
            "coords": "referentiel_immeuble",
            # « ฿ 5.6M » : prix arrondi à 100 000 THB près par le site lui-même
            "prix_arrondi": bool(stub.get("_prix_arrondi")),
            **{k: rec.get(k) for k in ("condo_name", "bedrooms", "area_sqm", "district", "price")},
        }
        return rec
