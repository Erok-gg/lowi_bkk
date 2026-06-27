"""purge_extra_images.py — Réduit le Storage à 1 image par bien.

Garde l'image de couverture (ord=0), supprime toutes les autres (ord>=1) du
Storage Supabase ET des lignes listing_images. Suppression en lot (rapide).
DESTRUCTIF — choix utilisateur pour repasser sous le palier gratuit (1 Go).

Usage :
  .venv/Scripts/python.exe purge_extra_images.py --limit 200   # test
  .venv/Scripts/python.exe purge_extra_images.py               # tout
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from pipeline.keepawake import prevent_sleep  # noqa: E402
from pipeline.storage import SupabaseStorage  # noqa: E402

ROOT = Path(__file__).resolve().parent
BATCH = 100


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
    ap.add_argument("--limit", type=int, default=None, help="nb max d'objets à purger (test)")
    args = ap.parse_args()

    prevent_sleep()
    load_env()
    dsn = os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        sys.exit("SUPABASE_DB_URL manquant (scraper/.env)")
    storage = SupabaseStorage.from_env()
    if not storage:
        sys.exit("SUPABASE_URL / SUPABASE_SERVICE_KEY manquants (Storage)")

    db = psycopg.connect(dsn, connect_timeout=20, autocommit=True)
    rows = db.execute(
        "select id, storage_path from listing_images where ord >= 1 order by listing_id"
    ).fetchall()
    if args.limit:
        rows = rows[: args.limit]
    print(f"{len(rows)} image(s) secondaire(s) à purger (ord>=1)")

    deleted_obj = deleted_row = 0
    for i in range(0, len(rows), BATCH):
        chunk = rows[i : i + BATCH]
        paths = [r[1] for r in chunk]
        ids = [r[0] for r in chunk]
        deleted_obj += storage.delete_many(paths)
        db.execute("delete from listing_images where id = any(%s)", (ids,))
        deleted_row += len(ids)
        print(f"  {min(i + BATCH, len(rows))}/{len(rows)} — objets {deleted_obj}, lignes {deleted_row}")

    db.close()
    print(f"\n✓ Purge terminée : {deleted_obj} objets Storage supprimés, {deleted_row} lignes listing_images")


if __name__ == "__main__":
    main()
