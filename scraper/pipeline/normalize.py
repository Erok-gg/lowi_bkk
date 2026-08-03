"""normalize.py — Met un enregistrement brut au format du schéma normalisé
(aligné sur lib/types.ts et supabase/schema.sql).
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone

from pipeline import details

# Les 12 champs extraits du descriptif. Ordre fige : il sert de reference aux
# stores (colonnes) et au tooltip.
CHAMPS_DETAIL = tuple(details.CHAMPS)


def _details(description: str | None, area_sqm: float | None = None) -> dict:
    """Extrait les details, avec les memes cles quelle que soit la source.

    Toujours les 12 cles, meme vides : un store ne doit pas avoir a deviner
    quelles colonnes existent selon l'annonce. Les listes partent en JSON, seul
    format commun a SQLite (TEXT) et Postgres (jsonb)."""
    brut = details.extraire(description, area_sqm) if description else {}
    out = {}
    for cle in CHAMPS_DETAIL:
        v = brut.get(cle)
        out[f"d_{cle}"] = json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v
    return out


def _num(v):
    try:
        return float(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None


#: Tranche de surface (m²) pour regrouper les annonces d'un même type de lot.
#: Absorbe les écarts de saisie entre agents (44 / 45 / 45,5 m² = même lot type).
AREA_BUCKET = 5


def _tranche(area: float | None) -> int:
    """Tranche de surface, arrondie EXACTEMENT comme le fait SQL.

    `round()` de Python applique l'arrondi bancaire (au pair le plus proche) :
    `round(8.5) == 8`. `round()` de Postgres et de SQLite arrondissent au plus
    loin de zéro : `round(8.5) == 9`. Une surface de 42,5 m² recevait donc la
    tranche 40 si l'unit_key venait du scrape, et 45 s'il venait du backfill SQL
    (`supabase/migrations/backfill_unit_key.sql`) — deux cohortes pour un même
    lot, et la republication qu'on cherche justement à rattraper passait au
    travers. Relevé sur l'archive : 263 annonces pile sur une frontière de
    tranche, dont 124 réellement divergentes.

    On adopte la convention SQL (`floor(x + 0.5)`), parce que c'est elle qui a
    produit les 34 183 unit_key déjà en base.
    """
    if not area or area <= 0:
        return 0
    return int(math.floor(area / AREA_BUCKET + 0.5) * AREA_BUCKET)


def _norm_condo(name: str | None) -> str:
    """Nom d'immeuble ramené à une forme comparable (suffixe ', Bangkok',
    mots vides, casse, ponctuation)."""
    import re
    s = (name or "").casefold().replace(",", " ")
    s = re.sub(r"\bbangkok\b|\bcondo(minium)?\b|\bproject\b|\bresidences?\b", " ", s)
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip()


def unit_key(rec: dict) -> str | None:
    """Identifiant de COHORTE : immeuble × chambres × tranche de surface × type.

    Sert d'unité d'analyse à la place de l'annonce. Une annonce republiée par
    un agent (suppression puis reparution sous un nouvel identifiant) retombe
    dans la même cohorte : le stock de la cohorte ne bouge pas, donc le repost
    n'est plus lu à tort comme une absorption suivie d'une nouvelle offre.
    Mesuré sur l'archive : 3 015 reposts probables en moins de 7 jours.

    ⚠ Une cohorte peut contenir plusieurs lots réellement distincts (dix 45 m²
    identiques dans une tour). Ce n'est donc PAS un compteur de biens uniques —
    seulement la bonne maille pour suivre l'écoulement de l'offre et comparer
    des prix à périmètre comparable.
    """
    condo = _norm_condo(rec.get("condo_name"))
    if not condo:
        return None
    bucket = _tranche(_num(rec.get("area_sqm")))
    beds = rec.get("bedrooms")
    beds = int(beds) if isinstance(beds, (int, float)) else -1
    return f"{condo}|{beds}|{bucket}|{rec.get('deal_type') or '?'}"


def normalize(rec: dict) -> dict:
    price = _num(rec.get("price"))
    if price == 0:
        price = None  # 0 = prix indisponible (ex. projet neuf en fourchette)
    area = _num(rec.get("area_sqm"))
    ppsqm = round(price / area, 2) if price and area else None
    now = datetime.now(timezone.utc).isoformat()

    source = rec["source"]
    source_id = rec.get("source_id") or rec["source_url"]
    deal = rec.get("deal_type") or "sale"
    # deal_type dans l'id : une même unité peut être listée en vente ET en location
    # (ex. FazWaz partage l'id d'unité) → 2 lignes distinctes, indispensable pour
    # le rendement et le « vendu ET loué ».

    rec_out = {
        "id": f"{source}:{deal}:{source_id}",
        "source": source,
        "source_url": rec["source_url"],
        "title": rec.get("title"),
        "deal_type": rec.get("deal_type"),
        "quota": rec.get("quota"),  # foreigner/thai (FazWaz) — None si non exposé (DDproperty)
        "tenure": rec.get("tenure", "freehold"),  # freehold only (leasehold écarté à la source)
        "price": price,
        "currency": rec.get("currency", "THB"),
        "area_sqm": area,
        "price_per_sqm": ppsqm,
        "bedrooms": rec.get("bedrooms"),
        "bathrooms": rec.get("bathrooms"),
        "condo_name": rec.get("condo_name"),
        # Descriptif libre — la seule matière textuelle de la base. Capturé
        # depuis le 2026-07-31 ; NON rétroactif (les annonces antérieures
        # resteront à NULL sans re-scrape complet).
        "description": rec.get("description"),
        # TEXTE INTEGRAL de la page, non tronque : c'est la MATIERE PREMIERE.
        # `description` en est un produit fini (tronque a 4000, nettoye, cadre) ;
        # `page_text` permet de REJOUER une extraction quand un motif se revele
        # faux, sans re-scraper. Trois motifs ont du etre corriges le 2026-08-02.
        "page_text": rec.get("page_text"),
        # Détails extraits du descriptif (cf. pipeline/details.py). Branché ICI
        # plutôt que dans chaque adaptateur : les 4 sources passent par
        # normalize(), donc un seul point d'entrée et un seul comportement.
        **_details(rec.get("description"), area),
        "address_raw": rec.get("full_address") or rec.get("district"),
        "khet": rec.get("district"),  # affiné par geo_match si lat/lng
        "khwaeng": rec.get("khwaeng"),
        "street": rec.get("street"),
        "lat": _num(rec.get("lat")),
        "lng": _num(rec.get("lng")),
        "status": "active",
        "first_seen": now,
        "last_seen": now,
        "amenities": rec.get("amenities", []),
        "image_urls": rec.get("image_urls", []),
        "raw_data": rec.get("raw_data", {}),
        # Année de livraison du PROJET (relevée sur la fiche) — propriété du
        # bâtiment, alimente le référentiel `condos`.
        "year_built": rec.get("year_built"),
        # Empreinte photo (poids en octets + nombre) : deux annonces qui
        # réutilisent les mêmes fichiers sont le même lot, même si le nombre
        # de photos diffère.
        "photo_count": rec.get("photo_count"),
        "photo_sizes": rec.get("photo_sizes"),
        # QUI publie : deux annonces identiques du MÊME agent sont un doublon ;
        # les mêmes venant d'agences concurrentes sont deux mises en marché d'un
        # même lot, voire deux lots distincts. Sans ce champ, la question n'est
        # pas décidable — cf. journal technique du 2026-07-28 (soir).
        "agent_id": rec.get("agent_id"),
        "agency_id": rec.get("agency_id"),
        # QUAND l'annonce a été publiée, d'après la SOURCE. `first_seen` ne dit
        # que la date de notre premier passage : le time-on-market qui en découle
        # est borné par la cadence de scan.
        "posted_at": rec.get("posted_at"),
        # Republication signalée par le site lui-même.
        "is_auto_repost": rec.get("is_auto_repost"),
    }
    rec_out["unit_key"] = unit_key(rec_out)
    return rec_out
