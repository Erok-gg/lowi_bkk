"""normalize.py — Met un enregistrement brut au format du schéma normalisé
(aligné sur lib/types.ts et supabase/schema.sql).
"""
from __future__ import annotations

from datetime import datetime, timezone


def _num(v):
    try:
        return float(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None


#: Tranche de surface (m²) pour regrouper les annonces d'un même type de lot.
#: Absorbe les écarts de saisie entre agents (44 / 45 / 45,5 m² = même lot type).
AREA_BUCKET = 5


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
    area = _num(rec.get("area_sqm"))
    bucket = int(round(area / AREA_BUCKET) * AREA_BUCKET) if area else 0
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
    }
    rec_out["unit_key"] = unit_key(rec_out)
    return rec_out
