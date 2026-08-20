"""sync_supabase_local.py — Réplique Supabase → SQLite local, puis purge le serveur.

Principe : le LOCAL est l'archive de référence (append-only, jamais purgé) ;
le serveur ne garde que la fenêtre chaude. Une ligne n'est supprimée du serveur
QUE si sa copie est vérifiée dans l'archive locale.

  1. SYNC   : upsert de toutes les tables vers archive/lowi-archive.db
              (tables ET colonnes ET clés primaires lues au catalogue à chaque
              run → résiste aux évolutions de schéma, y compris l'ajout d'une
              table entière).
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

for line in open(os.path.join(ROOT, "scraper", ".env"), encoding="utf-8"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())
sys.path.insert(0, os.path.join(ROOT, "scraper"))
import psycopg  # noqa: E402


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def pg_tables(conn) -> list[str]:
    """Toutes les tables de `public`, lues au catalogue à chaque run.

    C'était une liste figée de 7 noms jusqu'au 2026-08-20, alors que la doc
    annonçait « réplique TOUTES les tables ». Conséquence mesurée ce jour-là :
    condos (4 514), cohort_snapshots (578 683) et posted_at_history (23 479)
    n'avaient JAMAIS été archivées — 606 676 lignes hors de l'archive censée
    servir de référence historique avant purge.
    """
    rows = conn.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' AND table_type='BASE TABLE' "
        "ORDER BY table_name").fetchall()
    return [r[0] for r in rows]


def pg_columns(conn, table: str) -> list[str]:
    rows = conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",
        (table,)).fetchall()
    return [r[0] for r in rows]


def pg_primary_key(conn, table: str) -> list[str]:
    """Colonnes de la PK réelle, dans l'ordre — au lieu de supposer « id ».

    `condos` a pour PK `name` : la supposition lui posait un UNIQUE INDEX sur
    ses 19 colonnes avec INSERT OR IGNORE, donc une ligne de PLUS à chaque
    changement d'agrégat (n_listings, n_sale… bougent à chaque scan) au lieu
    d'un upsert sur le nom de l'immeuble.
    """
    rows = conn.execute(
        "SELECT a.attname FROM pg_index i "
        "JOIN pg_class c ON c.oid = i.indrelid "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "JOIN unnest(i.indkey) WITH ORDINALITY AS k(attnum, ord) ON true "
        "JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.attnum "
        "WHERE n.nspname='public' AND c.relname=%s AND i.indisprimary "
        "ORDER BY k.ord", (table,)).fetchall()
    return [r[0] for r in rows]


def ensure_sqlite_table(db: sqlite3.Connection, table: str, cols: list[str],
                        pk: list[str]) -> None:
    qcols = ", ".join(f'"{c}"' for c in cols)
    if pk:
        qpk = ", ".join(f'"{c}"' for c in pk)
        db.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({qcols}, PRIMARY KEY ({qpk}))')
    else:
        # sans PK côté serveur, le dédoublonnage ne peut porter que sur la ligne entière
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
    for table in pg_tables(pg):
        cols = pg_columns(pg, table)
        if not cols:
            log(f"  {table}: absente côté serveur, ignorée")
            continue
        pk = pg_primary_key(pg, table)
        ensure_sqlite_table(db, table, cols, pk)
        qcols = ", ".join(f'"{c}"' for c in cols)
        cur = pg.execute(f'SELECT {qcols} FROM "{table}"')
        n = 0
        ph = ", ".join("?" for _ in cols)
        verb = "INSERT OR REPLACE" if pk else "INSERT OR IGNORE"
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
        # Le garde-fou ne portait que sur `listings` : une table mal répliquée
        # ailleurs laissait la purge s'exécuter. Il porte maintenant sur TOUTES
        # les tables — l'archive doit être au moins aussi fournie que le serveur
        # partout, puisque c'est elle qui autorise à supprimer là-bas.
        deficits = [f"{t} ({loc} < {srv})" for t, (srv, loc) in sorted(stats.items())
                    if loc < srv]
        if deficits:
            log("⛔ archive en retard sur le serveur — purge interdite : "
                + ", ".join(deficits))
        elif args.prune or args.dry_run:
            prune(pg, db, args.dry_run)
    size_mb = os.path.getsize(ARCHIVE) / 1e6
    log(f"✓ terminé — archive {size_mb:.0f} Mo")
    db.close()


if __name__ == "__main__":
    main()
