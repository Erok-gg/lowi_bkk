"""backfill_condo_years.py — relève l'année de livraison, un immeuble à la fois.

L'année est une propriété du BÂTIMENT : une seule fiche suffit à la connaître
pour toutes les annonces de l'immeuble. On visite donc UNE annonce par condo
(≈3 700 requêtes) au lieu d'une par annonce (≈34 000), en privilégiant
DDproperty qui expose la donnée en clair dans son __NEXT_DATA__
(project.metaByType.verified.completionYear) ; FazWaz sert de secours via le
motif « Completed (Mois AAAA) » de la fiche.

Reprend là où il s'est arrêté : les condos déjà renseignés sont sautés, les
échecs sont mémorisés pour ne pas être retentés à chaque exécution.

Usage :
  python backfill_condo_years.py --sqlite [--limit 100] [--min-listings 3]
  python backfill_condo_years.py            # Supabase
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pipeline.fetch import Fetcher  # noqa: E402

ROOT = Path(__file__).parent
ARCHIVE = ROOT.parent / "archive" / "lowi-archive.db"
CACHE = ROOT / "output" / "condo-year-cache.json"

NEXT_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
FAZWAZ_YEAR = (re.compile(r"Completed\s*\(\s*(?:\w+\s+)?(\d{4})\s*\)"),
               re.compile(r"completed\s+in\s+(?:\w+\s+)?(\d{4})", re.I))


def _fetcher(name: str) -> Fetcher:
    cfg = json.loads((ROOT / "config" / f"{name}.json").read_text(encoding="utf-8"))
    return Fetcher(cfg["base_url"], cfg["user_agent"],
                   cfg.get("rate_limit_seconds", 3.0),
                   cfg.get("timeout_seconds", 30),
                   cfg.get("respect_robots", True))


def _walk_year(node) -> int | None:
    """Cherche completionYear n'importe où dans le __NEXT_DATA__."""
    if isinstance(node, dict):
        for k, v in node.items():
            if str(k) == "completionYear" and str(v).isdigit():
                return int(v)
            found = _walk_year(v)
            if found:
                return found
    elif isinstance(node, list):
        for v in node:
            found = _walk_year(v)
            if found:
                return found
    return None


def extraire_annee(html: str, source: str) -> int | None:
    if source == "ddproperty":
        m = NEXT_RE.search(html)
        if m:
            try:
                y = _walk_year(json.loads(m.group(1)))
                if y and 1970 <= y <= 2040:
                    return y
            except json.JSONDecodeError:
                pass
        m = re.search(r"Completed\s+in\s+(?:\w+\s+)?(\d{4})", html, re.I)
        return int(m.group(1)) if m and 1970 <= int(m.group(1)) <= 2040 else None
    for pat in FAZWAZ_YEAR:
        m = pat.search(html)
        if m and 1970 <= int(m.group(1)) <= 2040:
            return int(m.group(1))
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sqlite", action="store_true", help="lire/écrire dans l'archive locale")
    ap.add_argument("--limit", type=int, default=0, help="nombre max de condos à traiter")
    ap.add_argument("--min-listings", type=int, default=1,
                    help="ne traiter que les condos ayant au moins N annonces")
    args = ap.parse_args()

    if not args.sqlite:
        sys.exit("Mode Supabase non branché ici : lancer avec --sqlite, puis "
                 "synchroniser, ou appliquer condos.sql côté serveur.")

    CACHE.parent.mkdir(exist_ok=True)
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}

    con = sqlite3.connect(ARCHIVE)
    con.row_factory = sqlite3.Row
    con.execute("""create table if not exists condos (
        name text primary key, name_normalized text, khet text, lat real, lng real,
        year_built integer, year_source text, year_seen_at text,
        n_listings integer default 0, n_sale integer default 0, n_rent integer default 0,
        first_seen text, last_seen text)""")

    # Amorçage / rafraîchissement du référentiel depuis les annonces
    now = datetime.now(timezone.utc).isoformat()
    con.execute("""insert into condos (name, khet, lat, lng, n_listings, n_sale, n_rent, first_seen, last_seen)
        select condo_name, max(khet), avg(lat), avg(lng), count(*),
               sum(case when deal_type='sale' then 1 else 0 end),
               sum(case when deal_type='rent' then 1 else 0 end), ?, ?
        from listings where condo_name is not null and trim(condo_name) <> ''
        group by condo_name
        on conflict(name) do update set
          n_listings=excluded.n_listings, n_sale=excluded.n_sale, n_rent=excluded.n_rent,
          khet=coalesce(condos.khet, excluded.khet),
          lat=coalesce(condos.lat, excluded.lat), lng=coalesce(condos.lng, excluded.lng),
          last_seen=excluded.last_seen""", (now, now))
    con.commit()

    # Une annonce représentative par condo — DDproperty d'abord (donnée structurée)
    q = """select c.name,
                  (select l.source_url from listings l where l.condo_name=c.name
                    order by case l.source when 'ddproperty' then 0 when 'fazwaz' then 1 else 2 end,
                             l.last_seen desc limit 1) as url,
                  (select l.source from listings l where l.condo_name=c.name
                    order by case l.source when 'ddproperty' then 0 when 'fazwaz' then 1 else 2 end,
                             l.last_seen desc limit 1) as source
           from condos c
           where c.year_built is null and c.n_listings >= ?
           order by c.n_listings desc"""
    cibles = [r for r in con.execute(q, (args.min_listings,)).fetchall()
              if r["url"] and cache.get(r["name"]) != "echec"]
    if args.limit:
        cibles = cibles[:args.limit]

    print(f"{len(cibles)} immeuble(s) à renseigner "
          f"(≥{args.min_listings} annonce(s), {len(cache)} déjà tentés)")

    fetchers: dict[str, Fetcher] = {}
    ok = ko = 0
    for i, r in enumerate(cibles, 1):
        src = r["source"]
        if src not in ("ddproperty", "fazwaz"):
            continue
        if src not in fetchers:
            fetchers[src] = _fetcher(src)
        html = fetchers[src].get_text(r["url"], referer=fetchers[src].base_url)
        year = extraire_annee(html, src) if html else None
        if year:
            con.execute("update condos set year_built=?, year_source=?, year_seen_at=? where name=?",
                        (year, src, datetime.now(timezone.utc).isoformat(), r["name"]))
            con.commit()
            cache[r["name"]] = year
            ok += 1
        else:
            cache[r["name"]] = "echec"
            ko += 1
        if i % 10 == 0 or i == len(cibles):
            CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
            print(f"  [{i}/{len(cibles)}] {ok} trouvées, {ko} sans année — dernier : "
                  f"{r['name'][:40]} → {year or '—'}")

    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    tot = con.execute("select count(*) from condos where year_built is not null").fetchone()[0]
    print(f"\n✓ {ok} années relevées ({ko} échecs) — {tot} immeubles datés au total")


if __name__ == "__main__":
    main()
