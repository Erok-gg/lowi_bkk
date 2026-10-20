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
from pipeline import description
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


def _posted_at(posted) -> str | None:
    """Date de publication annoncée par le site → ISO UTC.

    `postedOn.unix` est un horodatage en secondes. C'est la seule date de mise en
    ligne RÉELLE dont on dispose : `first_seen` ne dit que le moment où NOTRE
    scan a croisé l'annonce, ce qui borne le time-on-market par la cadence de
    scan et non par le marché.
    """
    if not isinstance(posted, dict):
        return None
    unix = posted.get("unix")
    if not isinstance(unix, (int, float)) or unix <= 0:
        return None
    from datetime import datetime, timezone
    return datetime.fromtimestamp(unix, timezone.utc).isoformat()


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


#: Code de tenure du blob de liste. Meme convention que la fiche detail
#: (tenureCode "F"/"L"), verifiee identique le 2026-08-23.
_TENURE = {"F": "freehold", "L": "leasehold"}


def _bloc_page(node) -> dict:
    """Le dict du blob qui porte les blocs annexes, trouve PAR CONTENU.

    Meme principe que `_walk_listings` : le chemin exact a deja bouge une fois
    (`listings` -> `listingsData.items`, journal du 2026-08-11), donc on
    cherche la cle, pas le chemin."""
    if isinstance(node, dict):
        if any(isinstance(node.get(k), dict) and node.get(k)
               for k in ("contactAgentCardData", "enquiryModalData")):
            return node
        for v in node.values():
            r = _bloc_page(v)
            if r:
                return r
    elif isinstance(node, list):
        for v in node:
            r = _bloc_page(v)
            if r:
                return r
    return {}


def _cartes_annexes(data: dict) -> dict:
    """Les annonces de la page, vues par les blocs ANNEXES du meme blob.

    POURQUOI CE SECOND CHEMIN (mesure du 2026-10-21). Dans la nuit du 19 au
    20/10, DDproperty s'est mis a elaguer `listingsData` — le tableau qui porte
    la charge utile d'une annonce — tout en continuant a servir, pour les
    MEMES 20 annonces, les blocs annexes `contactAgentCardData` et
    `enquiryModalData`, tous deux indexes par identifiant d'annonce.

    Mesure sur 16 pages (vente + location, pages 1-8) : `listingsData` ne
    rendait plus que **10/160 annonces en vente (6 %) et 2/160 en location
    (1 %)**, pendant que `contactAgentCardData` en rendait **20/20 sur les 16
    pages**. La veille encore (run 927 du ledger), le recensement voyait
    48 321 annonces sur 2 615 pages, soit 18,5/page — la structure etait saine.

    CE QUE CE CHEMIN RECUPERE, ET CE QU'IL PERD. Sur les 10 identifiants
    presents des DEUX cotes le 2026-10-21, `url` et `price` sont identiques
    10/10. La carte annexe porte url, prix, nom d'immeuble, chambres, type
    d'annonce, agent (id/nom/type) — 160/160 renseignes. Elle NE porte PAS
    `fullAddress`, `floorArea`, `bathrooms`, `tenure`, `postedOn`, l'agence ni
    `isAutoRepost` : ces champs viennent de la fiche detail, que `fetch_detail`
    visite deja et qui, elle, est intacte (verifie le 2026-10-21 sur
    500669058 : surface 54 m2, 1 SDB, lat/lng, tenure freehold, description).
    Un stub issu de ce chemin n'a donc pas de khet tant que la fiche n'est pas
    lue — le rattrapage se fait par point-in-polygon sur les coordonnees.

    PRIORITE. `listingsData` reste la source principale quand elle repond :
    elle est plus riche. Ce chemin ne COMPLETE que les identifiants absents.
    Quand DDproperty remettra son tableau complet, il reprendra tout seul la
    main et cette fonction ne rendra plus rien de neuf."""
    cartes = data.get("contactAgentCardData")
    if not isinstance(cartes, dict):
        return {}
    return {str(k): v for k, v in cartes.items() if isinstance(v, dict)}


def _ids_annonces_page(data: dict, bangkok_seulement: bool = False) -> set[str]:
    """Identifiants que la page DIT porter, selon ses blocs annexes.

    Sert de verite terrain a la sonde : sans elle, « 1 stub obtenu » ne
    distingue pas une page qui ne porte qu'une annonce d'une page qui en porte
    vingt dont on n'a su en lire qu'une (defaut du 2026-10-20 : la sonde de la
    passe couloirs a repondu OK avec 1 stub alors que la page en portait 20).

    `bangkok_seulement` applique le meme filtre province que `_parse_list`,
    pour que les deux comptages soient comparables."""
    cartes = _cartes_annexes(data)
    if bangkok_seulement:
        return {sid for sid, c in cartes.items()
                if (c.get("localizedTitle") or "").strip().lower().endswith("bangkok")}
    ids = {sid for sid in cartes}
    bloc = data.get("enquiryModalData")
    if isinstance(bloc, dict):
        ids |= {str(k) for k in bloc if str(k).isdigit()}
    return ids


class DdpropertyAdapter(BaseAdapter):
    source = "ddproperty"

    def sonder(self, fetcher: Fetcher) -> tuple[bool, str]:
        """DDproperty (Next.js) : tout vient du blob `__NEXT_DATA__`. Vérifié
        AVANT extraction — le chemin exact du tableau d'annonces a déjà
        bougé une fois dans la journée (`listings` puis `listingsData.items`,
        cf. journal technique 2026-08-11), d'où l'identification par
        contenu (`fullAddress`) plutôt que par chemin figé."""
        searches = self.config.get("searches") or []
        if not searches:
            return False, "config sans 'searches'"
        base = self.config["base_url"]
        html = fetcher.get_text(f"{base}{searches[0]['path']}")
        if not html:
            return False, "page de liste inaccessible (0 octet ou erreur réseau)"
        data = _next_data(html)
        if not data:
            return False, "__NEXT_DATA__ absent ou illisible (JSON invalide)"
        annonces, stubs = self._couverture(data, searches[0]["deal_type"])
        if not annonces and not stubs:
            return False, ("__NEXT_DATA__ présent mais la page ne porte aucune annonce "
                           "(ni 'fullAddress', ni carte annexe) — structure du blob changée")
        # Un nombre de stubs NON NUL ne suffit pas : le 2026-10-20, la passe
        # couloirs a repondu « sonde OK — 1 stub obtenu » sur une page qui en
        # portait 20, et a scanne le catalogue a 5 % sans que rien ne le dise.
        # On compare donc a ce que la page ELLE-MEME annonce porter, au lieu
        # de se contenter d'un « au moins un ». Pas de seuil arbitraire : la
        # reference est mesuree sur la page du jour.
        if annonces and len(stubs) < len(annonces):
            manquantes = len(annonces) - len(stubs)
            return False, (f"page 1 : {len(stubs)}/{len(annonces)} annonces extraites "
                           f"({manquantes} perdues) — le blob est élagué, "
                           f"la charge utile n'est plus servie pour toutes les annonces")
        ok, msg = super().sonder(fetcher)
        if not ok:
            return ok, msg
        # Le message de base dit « 1 stub obtenu » (il sonde avec limit=1) :
        # on y ajoute la couverture réelle, sinon le journal ne permet pas de
        # distinguer une page pleine d'une page élaguée — c'est precisement
        # cette ambiguite qui a laisse passer le 2026-10-20.
        elague = next(_walk_listings(data), None) is None
        return True, (f"{msg} — couverture {len(stubs)}/{len(annonces)} annonces"
                      + (" (listingsData élaguée, reprise par les cartes annexes)"
                         if elague else ""))

    def _couverture(self, data: dict, deal: str) -> tuple[set[str], set[str]]:
        """(identifiants Bangkok annoncés par la page, identifiants extraits).

        Les stubs sont comptés par le VRAI parseur (`_parse_list`), pas par une
        copie qui pourrait diverger. Le premier ensemble est restreint à
        Bangkok : une page annonce parfois des annonces de province que le
        filtre écarte à bon droit (2 sur 200 le 2026-10-21) — les compter
        comme perdues ferait crier la sonde au loup."""
        annonces = _ids_annonces_page(_bloc_page(data), bangkok_seulement=True)
        stubs = {str(s["source_id"]) for s in self._parse_list(data, deal)}
        return annonces, stubs

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
            # Qui publie, et quand. Ces champs sont dans le MÊME blob que le
            # reste — on les ignorait, alors qu'ils tranchent la question
            # « plusieurs lots ou plusieurs annonces du même lot ? » : deux
            # annonces identiques du même agent sont un doublon, deux annonces
            # identiques d'agences concurrentes ne le sont pas.
            agent = it.get("agent") or {}
            produits = it.get("products") or {}
            stubs.append({
                "source_url": url,
                "source_id": m.group(1) if m else url,
                "deal_type": deal,
                "price": _price_num(it.get("price")),
                "condo_name": prop.get("projectName") or it.get("localizedTitle"),
                "bedrooms": _int(it.get("bedrooms")),
                "bathrooms": _int(it.get("bathrooms")),
                "full_address": full,
                "agent_id": str(agent["id"]) if agent.get("id") is not None else None,
                "agency_id": str(agent["agencyId"]) if agent.get("agencyId") is not None else None,
                # Noms : meme blob, sonde du 2026-10-17 (`agent.name`,
                # `agency.name`, `listerType`). Vont dans la table `courtiers`
                # (une ligne par agent), pas dans `listings`.
                "agent_name": (agent.get("name") or "").strip() or None,
                "agency_name": ((it.get("agency") or {}).get("name") or "").strip() or None,
                "lister_type": it.get("listerType"),
                "agent_profile_url": agent.get("profileUrl"),
                # Date de publication RÉELLE annoncée par le site. Mesure le
                # time-on-market à la source, au lieu de le déduire de la date
                # à laquelle NOUS avons vu l'annonce pour la première fois.
                "posted_at": _posted_at(it.get("postedOn")),
                # Le site signale lui-même ses republications automatiques.
                "is_auto_repost": produits.get("isAutoRepost"),
                # Surface et tenure sont DANS LE BLOB DE LISTE — verifie le
                # 2026-08-23 (`floorArea: 117`, `additionalData.tenure: "F"`).
                # On les ignorait, et c'etaient justement les deux champs qui
                # justifiaient d'ouvrir la page detail. La fiche les ecrase
                # ensuite si elle repond ; ici on remplit un trou, on ne
                # remplace rien. Sans eux, une annonce recensee mais jamais
                # visitee n'a pas de prix au m2, donc aucune valeur d'analyse.
                "area_sqm": _float(it.get("floorArea")),
                "tenure": _TENURE.get(
                    str((it.get("additionalData") or {}).get("tenure") or "").upper()),
                **addr,
            })
        stubs += self._stubs_annexes(data, deal, seen)
        return stubs

    def _stubs_annexes(self, data: dict, deal: str, deja: set[str]) -> list[dict]:
        """Complete la page par les cartes annexes (cf. `_cartes_annexes`).

        Ne tourne que sur les annonces que `listingsData` n'a PAS rendues :
        quand le site repond normalement, cette methode ne produit rien."""
        bloc = _bloc_page(data)
        if not bloc:
            return []
        out = []
        for sid, carte in _cartes_annexes(bloc).items():
            url = (carte.get("url") or "").split("#")[0].split("?")[0]
            if not url or url in deja:
                continue
            # Filtre province. `fullAddress` manque ici ; le suffixe du titre
            # localise le remplace. Mesure du 2026-10-21 sur 200 cartes :
            # 198 « …, Bangkok », 2 « …, Nakhon Ratchasima », et le slug de
            # l'URL dit exactement la meme chose 200/200 — aucun desaccord.
            titre = (carte.get("localizedTitle") or "").strip()
            if not titre.lower().endswith("bangkok"):
                continue
            deja.add(url)
            m = ID_RE.search(url)
            agent = carte.get("agent") or {}
            out.append({
                "source_url": url,
                "source_id": m.group(1) if m else sid,
                "deal_type": deal,
                "price": _price_num(carte.get("price")) or _float(carte.get("price")),
                "condo_name": carte.get("propertyName") or carte.get("localizedTitle"),
                "bedrooms": _int(carte.get("bedrooms")),
                "bathrooms": None,
                # Pas d'adresse dans ce bloc : le khet viendra du
                # point-in-polygon sur les coordonnees de la fiche detail.
                "full_address": "",
                "agent_id": str(agent["id"]) if agent.get("id") is not None else None,
                "agency_id": None,
                "agent_name": (agent.get("name") or "").strip() or None,
                "agency_name": None,
                "lister_type": carte.get("listerType"),
                "agent_profile_url": None,
                "posted_at": None,
                "is_auto_repost": None,
                "area_sqm": None,
                "tenure": None,
                **_parse_address(""),
            })
        return out

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
        rec["description"] = description.extract(html, data)
        rec["page_text"] = description.texte_integral(html)
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
            # année de livraison du PROJET (pas de l'annonce) : DDproperty
            # l'expose sous listingDetail.project.metaByType.verified.
            # C'est une propriété de l'immeuble → elle alimente la table `condos`
            # et vaut ensuite pour toutes ses annonces, passées et futures.
            year = _find_value(data, "completionYear")
            if year and str(year).isdigit() and 1970 <= int(year) <= 2040:
                rec["year_built"] = int(year)
            # Adresse, agence et date de publication : la fiche les porte aussi
            # (`propertyOverviewData.propertyInfo.fullAddress`, `agencyId`,
            # `postedOn`). On ne les lisait pas ici parce que la liste les
            # fournissait toujours — jusqu'au 2026-10-21, ou l'elagage de
            # `listingsData` a laisse khwaeng, street, agency_id et posted_at a
            # 0 % sur les annonces reprises par les cartes annexes, contre
            # 94-100 % la veille (mesure sur 4 962 annonces du 19-20/10).
            # COMPLEMENT SEULEMENT : si la liste a repondu, elle fait foi.
            if not rec.get("full_address"):
                plein = _find_value(data, "fullAddress")
                if plein:
                    rec["full_address"] = str(plein)
                    decoupe = _parse_address(str(plein))
                    # KHWAENG ET RUE SEULEMENT — PAS LE KHET. La fiche ecrit
                    # « Watthana » la ou le point-in-polygon sur les coordonnees
                    # ecrit « Vadhana District » : melanger les deux
                    # orthographes scinderait les statistiques par quartier en
                    # deux groupes pour le meme khet. Les coordonnees sont la
                    # (100 % sur les 12 annonces reprises le 2026-10-21) et
                    # restent la seule source du khet.
                    for cle in ("khwaeng", "street"):
                        if decoupe.get(cle) and not rec.get(cle):
                            rec[cle] = decoupe[cle]
            if not rec.get("agency_id"):
                aid = _find_value(data, "agencyId")
                if aid is not None:
                    rec["agency_id"] = str(aid)
            if not rec.get("posted_at"):
                poste = _find_with_keys(data, {"unix"})
                if poste:
                    rec["posted_at"] = _posted_at(poste)
            if rec.get("is_auto_repost") is None:
                repost = _find_value(data, "isAutoRepost")
                if isinstance(repost, bool):
                    rec["is_auto_repost"] = repost

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
