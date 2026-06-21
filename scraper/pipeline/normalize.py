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


def normalize(rec: dict) -> dict:
    price = _num(rec.get("price"))
    if price == 0:
        price = None  # 0 = prix indisponible (ex. projet neuf en fourchette)
    area = _num(rec.get("area_sqm"))
    ppsqm = round(price / area, 2) if price and area else None
    now = datetime.now(timezone.utc).isoformat()

    source = rec["source"]
    source_id = rec.get("source_id") or rec["source_url"]

    return {
        "id": f"{source}:{source_id}",
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
    }
