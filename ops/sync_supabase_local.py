"""sync_supabase_local.py — Réplique Supabase → SQLite local, puis purge le serveur.

Principe : le LOCAL est l'archive de référence (append-only, jamais purgé) ;
le serveur ne garde que la fenêtre chaude. Une ligne n'est supprimée du serveur
QUE si sa copie est vérifiée dans l'archive locale.

  1. SYNC   : upsert de toutes les tables vers archive/lowi-archive.db
              (introspection des colonnes → résiste aux évolutions de schéma).
  2. VERIFY : comptes par table + présence id par id des candidates à la purge.
  3. PRUNE  : (--prune) supprime du serveur les annonces INACTIVES délistées
              depuis > RETENTION_DAYS + leurs images/price_history/amenities.
              Jamais les actives, jamais scan_runs/khet_snapshots/pois.

Usage :
  scraper/.venv/Scripts/python.exe ops/sync_supabase_local.py            # sync seul
  scraper/.venv/Scripts/python.exe ops/sync_supabase_local.py --prune    # sync + purge
  scraper/.venv/Scripts/python.exe ops/sync_supabase_local.py --prune --dry-run
Planifié : ops/sync-archive.ps1 (tâche Windows hebdo).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE = os.path.join(ROOT, "archive", "lowi-archive.db")
RETENTION_DAYS = 90          # inactives délistées depuis plus de X jours → purgées du serveur
PRUNE_TABLES_CHILDREN = ["price_history", "listing_images", "listing_amenities"]
SYNC_TABLES = ["listings", "listing_images", "listing_amenities",
               "price_history", "scan_runs", "khet_snapshots", "pois"]

for line in open(os.path.join(ROOT, "scraper", ".env"), encoding="utf-8"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())
sys.path.insert(0, os.path.join(ROOT, "scraper"))
import psycopg  # noqa: E402


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def pg_columns(conn, table: str) -> list[str]:
    rows = conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",
        (table,)).fetchall()
    return [r[0] for r in rows]


def ensure_sqlite_table(db: sqlite3.Connection, table: str, cols: list[str]) -> None:
    qcols = ", ".join(f'"{c}"' for c in cols)
    if "id" in cols:
        db.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({qcols}, PRIMARY KEY ("id"))')
    else:
        db.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({qcols})')
        db.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS "ux_{table}_all" ON "{table}" ({qcols})')
    # colonnes ajoutées côté serveur depuis la dernière sync → on les ajoute en local
    existing = {r[1] for r in db.execute(f'PRAGMA table_info("{table}")')}
    for c in cols:
        if c not in existing:
            db.execute(f'ALTER TABLE "{table}" ADD COLUMN "{c}"')


def adapt(v):
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, datetime):
        return v.isoformat()
    if v is not None and type(v).__name__ == "Decimal":
        return float(v)
    return v


def sync(pg, db) -> dict[str, tuple[int, int]]:
    """Upsert toutes les tables. Retourne {table: (rows_serveur, rows_local)}."""
    stats = {}
    for table in SYNC_TABLES:
        cols = pg_columns(pg, table)
        if not cols:
            log(f"  {table}: absente côté serveur, ignorée")
            continue
        ensure_sqlite_table(db, table, cols)
        qcols = ", ".join(f'"{c}"' for c in cols)
        cur = pg.execute(f'SELECT {qcols} FROM "{table}"')
        n = 0
        ph = ", ".join("?" for _ in cols)
        verb = "INSERT OR REPLACE" if "id" in cols else "INSERT OR IGNORE"
        while True:
            batch = cur.fetchmany(5000)
            if not batch:
                break
            db.executemany(f'{verb} INTO "{table}" ({qcols}) VALUES ({ph})',
                           [tuple(adapt(v) for v in row) for row in batch])
            n += len(batch)
        db.commit()
        local_n = db.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
        stats[table] = (n, local_n)
        log(f"  {table}: {n} lignes serveur → {local_n} en archive")
    return stats


def prune(pg, db, dry_run: bool) -> None:
    cand = pg.execute(
        "SELECT id FROM listings WHERE status='inactive' "
        "AND delisted_at IS NOT NULL AND delisted_at < now() - interval '%s days'"
        % RETENTION_DAYS).fetchall()
    ids = [r[0] for r in cand]
    log(f"  candidates à la purge (inactives >{RETENTION_DAYS} j) : {len(ids)}")
    if not ids:
        return

    # GARDE-FOU : chaque id doit exister dans l'archive locale, sinon on ne touche à rien
    missing = [i for i in ids
               if not db.execute('SELECT 1 FROM "listings" WHERE "id"=?', (i,)).fetchone()]
    if missing:
        log(f"  ⛔ {len(missing)} candidates ABSENTES de l'archive locale → purge ANNULÉE "
            f"(ex: {missing[:3]}). Relancer la sync.")
        return

    if dry_run:
        log(f"  [dry-run] {len(ids)} annonces seraient supprimées du serveur (archive OK)")
        return

    CHUNK = 500
    for i in range(0, len(ids), CHUNK):
        chunk = ids[i:i + CHUNK]
        for child in PRUNE_TABLES_CHILDREN:
            pg.execute(f'DELETE FROM "{child}" WHERE listing_id = ANY(%s)', (chunk,))
        pg.execute("DELETE FROM listings WHERE id = ANY(%s)", (chunk,))
        pg.commit()
    log(f"  ✓ {len(ids)} annonces purgées du serveur (copies vérifiées en archive)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prune", action="store_true", help="purge serveur après sync vérifiée")
    ap.add_argument("--dry-run", action="store_true", help="montre la purge sans l'exécuter")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(ARCHIVE), exist_ok=True)
    log(f"▶ sync Supabase → {ARCHIVE}")
    db = sqlite3.connect(ARCHIVE)
    with psycopg.connect(os.environ["SUPABASE_DB_URL"], connect_timeout=30) as pg:
        stats = sync(pg, db)
        # sanity minimal : la table maîtresse doit avoir au moins autant de lignes en local
        srv, loc = stats.get("listings", (0, 0))
        if loc < srv:
            log(f"⛔ archive listings ({loc}) < serveur ({srv}) — purge interdite")
        elif args.prune or args.dry_run:
            prune(pg, db, args.dry_run)
    size_mb = os.path.getsize(ARCHIVE) / 1e6
    log(f"✓ terminé — archive {size_mb:.0f} Mo")
    db.close()


if __name__ == "__main__":
    main()
