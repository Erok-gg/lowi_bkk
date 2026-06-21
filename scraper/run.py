"""run.py — Orchestrateur du scraper (LOCAL).

Enchaîne : adaptateur (liste→détail) → normalisation → matching khet →
images webp 1024×768 → store SQLite (diff + price_history) → fiches HTML →
scan_run + stats.

Exemples :
  python run.py --source fazwaz --limit 5
  python run.py --source fazwaz --full          # marque les disparues inactives
  python run.py --source fazwaz --fetch-detail  # galerie + SDB via page détail

Demain (online) : ajouter --store supabase (SupabaseStore, même interface).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# imports relatifs au dossier scraper/
sys.path.insert(0, str(Path(__file__).resolve().parent))

from adapters.fazwaz import FazwazAdapter  # noqa: E402
from adapters.ddproperty import DdpropertyAdapter  # noqa: E402
from pipeline.fetch import Fetcher  # noqa: E402
from pipeline.normalize import normalize  # noqa: E402
from pipeline.geo_match import KhetMatcher  # noqa: E402
from pipeline.images import process_images  # noqa: E402
from pipeline.fiche import write_fiche  # noqa: E402
from store.sqlite_store import SqliteStore  # noqa: E402

ADAPTERS = {"fazwaz": FazwazAdapter, "ddproperty": DdpropertyAdapter}
ROOT = Path(__file__).resolve().parent
CONFIG_DIR = ROOT / "config"
OUTPUT_DIR = ROOT / "output"


def load_env() -> None:
    """Charge scraper/.env (simple) dans os.environ (sans dépendance)."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def load_config(source: str) -> dict:
    path = CONFIG_DIR / f"{source}.json"
    if not path.exists():
        sys.exit(f"Config introuvable : {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def make_store(kind: str):
    if kind == "supabase":
        load_env()
        dsn = os.environ.get("SUPABASE_DB_URL")
        if not dsn:
            sys.exit("SUPABASE_DB_URL manquant (scraper/.env)")
        from store.supabase_store import SupabaseStore
        print("→ store : Supabase (Postgres)")
        return SupabaseStore(dsn)
    print("→ store : SQLite local")
    return SqliteStore(OUTPUT_DIR / "bangkok.db")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="fazwaz", choices=list(ADAPTERS))
    ap.add_argument("--limit", type=int, default=None, help="nb max d'annonces (test)")
    ap.add_argument("--full", action="store_true",
                    help="scan complet : marque les annonces disparues comme inactives")
    ap.add_argument("--fetch-detail", action="store_true",
                    help="récupère galerie + SDB via la page de détail")
    ap.add_argument("--no-images", action="store_true", help="saute le traitement des images")
    ap.add_argument("--store", default="sqlite", choices=["sqlite", "supabase"],
                    help="destination : SQLite local (défaut) ou Supabase")
    args = ap.parse_args()

    cfg = load_config(args.source)
    if args.fetch_detail:
        cfg["fetch_detail"] = True

    adapter = ADAPTERS[args.source](cfg)
    fetcher = Fetcher(
        base_url=cfg["base_url"], user_agent=cfg["user_agent"],
        rate_limit_seconds=cfg.get("rate_limit_seconds", 2.5),
        timeout_seconds=cfg.get("timeout_seconds", 30),
        respect_robots=cfg.get("respect_robots", True),
        image_rate_limit_seconds=cfg.get("image_rate_limit_seconds", 0.4),
    )
    matcher = KhetMatcher()
    store = make_store(args.store)

    print(f"▶ Scan {args.source} (max_pages={cfg.get('max_pages')}, limit={args.limit})")

    n_new = n_changed = n_unchanged = n_skipped = n_total = 0
    seen_ids: set[str] = set()
    price_alerts: list[str] = []

    for stub in adapter.list_urls(fetcher, limit=args.limit):
        lid = f"{args.source}:{stub.get('source_id')}"
        seen_ids.add(lid)
        n_total += 1

        # ── Dédup incrémentale : on évite de re-visiter la fiche d'une annonce
        # déjà connue dont le prix (lu dans la liste) n'a pas bougé. Raccourcit
        # fortement les scraps futurs.
        existing = store.get_listing(lid)
        stub_price = stub.get("price")
        if (existing is not None and stub_price is not None
                and existing["price"] is not None
                and float(existing["price"]) == float(stub_price)
                and store.has_images(lid)):
            store.touch_listing(lid)
            n_unchanged += 1
            n_skipped += 1
            print(f"  [skip-dedup] {lid} — {stub.get('condo_name')} (prix inchangé)")
            continue

        # Nouvelle annonce ou prix changé → on visite la fiche (détail + galerie)
        rec = adapter.parse_listing(fetcher, stub)
        if not rec:
            continue
        norm = normalize(rec)
        # matching khet par lat/lng (sinon district texte du JSON-LD)
        khet = matcher.match(norm.get("lat"), norm.get("lng"))
        if khet:
            norm["khet"] = khet

        need_images = (not args.no_images) and bool(norm.get("image_urls")) and (
            existing is None or not store.has_images(norm["id"])
        )
        images = (
            process_images(fetcher, norm["id"], norm["image_urls"], OUTPUT_DIR, cfg["image"])
            if need_images else None
        )

        status, old_price = store.upsert_listing(norm, images)
        if status == "new":
            n_new += 1
        elif status == "changed":
            n_changed += 1
            price_alerts.append(
                f"  ⚠ prix changé {norm['id']}: {old_price} → {norm['price']} {norm['currency']}"
            )
        else:
            n_unchanged += 1

        # fiche HTML (relit les images stockées si on n'en a pas reprocessé)
        imgs_for_fiche = images or [
            {"storage_path": f"images/{norm['id'].replace(':', '_')}/0.webp"}
        ] if norm.get("image_urls") else []
        write_fiche(norm, imgs_for_fiche, OUTPUT_DIR)

        print(f"  [{status:9}] {norm['id']} — {norm.get('condo_name')} "
              f"({norm.get('price')} {norm['currency']}, {norm.get('khet')})")

    removed = 0
    if args.full:
        removed = store.mark_missing_inactive(args.source, seen_ids)

    store.record_scan_run(args.source, n_total, n_new, removed, n_changed,
                          notes="full" if args.full else "partial")

    print("\n── Résumé ──")
    print(f"  scannées : {n_total} | nouvelles : {n_new} | changées : {n_changed} "
          f"| inchangées : {n_unchanged} (dont {n_skipped} dédup, fiche non re-visitée) "
          f"| retirées : {removed}")
    if price_alerts:
        print("\nAlertes prix :")
        print("\n".join(price_alerts))

    stats = store.khet_stats()
    if stats:
        print("\n── Stats par khet (actives) ──")
        for s in stats[:15]:
            print(f"  {s['khet']:<22} {s['active_count']:>4} annonces | "
                  f"prix/m² moyen : {s['avg_price_per_sqm']}")

    print(f"\n✓ DB : {OUTPUT_DIR / 'bangkok.db'}")
    print(f"✓ Fiches : {OUTPUT_DIR / 'fiches'}  |  Images : {OUTPUT_DIR / 'images'}")
    store.close()


if __name__ == "__main__":
    main()
