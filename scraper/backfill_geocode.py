"""backfill_geocode.py — Complète street/lat/lng/khet des annonces existantes.

Pour chaque condo distinct sans rue (ou sans coords), interroge Nominatim une
seule fois (cache) et met à jour TOUTES les annonces du même condo. Ne remplit
que les champs manquants — n'écrase jamais des coords déjà précises (FazWaz/DDP).
Quand de nouvelles coords arrivent et que le khet est vide, on le déduit par
point-in-polygon (KhetMatcher).

Usage :
  .venv/Scripts/python.exe backfill_geocode.py --limit 20      # test
  .venv/Scripts/python.exe backfill_geocode.py                 # tout
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from pipeline.geocode import Geocoder, _norm  # noqa: E402
from pipeline.geo_match import KhetMatcher  # noqa: E402

ROOT = Path(__file__).resolve().parent


def load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="nb max de condos distincts à géocoder (test)")
    args = ap.parse_args()

    load_env()
    dsn = os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        sys.exit("SUPABASE_DB_URL manquant (scraper/.env)")

    db = psycopg.connect(dsn, connect_timeout=20, autocommit=True)
    geo = Geocoder()
    matcher = KhetMatcher()

    rows = db.execute(
        "select id, condo_name, khet, street, lat, lng from listings "
        "where status='active' and condo_name is not null "
        "and (street is null or lat is null)"
    ).fetchall()
    print(f"{len(rows)} annonce(s) à compléter")

    # regroupe par (condo normalisé, khet) → une requête Nominatim par groupe
    groups: dict[tuple[str, str], list] = {}
    for r in rows:
        groups.setdefault((_norm(r[1]), r[2] or ""), []).append(r)
    print(f"{len(groups)} condo(s) distinct(s)")

    n_geocoded = n_street = n_coords = n_khet = 0
    for i, ((_, _), items) in enumerate(groups.items()):
        if args.limit and n_geocoded >= args.limit:
            break
        ref = items[0]
        condo, khet = ref[1], ref[2]
        res = geo.lookup(condo, khet)
        n_geocoded += 1
        if not res:
            print(f"  [miss] {condo} ({khet})")
            continue
        street, lat, lng = res.get("street"), res.get("lat"), res.get("lng")
        new_khet = None
        if lat and lng:
            new_khet = matcher.match(lat, lng)
        for (lid, _cn, cur_khet, cur_street, cur_lat, cur_lng) in items:
            sets, vals = [], []
            if street and not cur_street:
                sets.append("street=%s"); vals.append(street); n_street += 1
            if lat and lng and cur_lat is None:
                sets += ["lat=%s", "lng=%s"]; vals += [lat, lng]; n_coords += 1
            if new_khet and not cur_khet:
                sets.append("khet=%s"); vals.append(new_khet); n_khet += 1
            if sets:
                vals.append(lid)
                db.execute(f"update listings set {','.join(sets)} where id=%s", vals)
        print(f"  [ok]   {condo} → street={street} coords={'y' if lat else 'n'}")

    db.close()
    print(f"\n✓ {n_geocoded} condos géocodés | +street {n_street} | +coords {n_coords} | +khet {n_khet}")


if __name__ == "__main__":
    main()
