"""apply_migrations.py — applique les fichiers de supabase/migrations/ sur Supabase.

Les migrations sont ecrites idempotentes (add column if not exists / create table
if not exists), donc rejouables sans risque.

Usage : python apply_migrations.py [nom.sql ...]      (defaut : toutes)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
MIG = ROOT / "supabase" / "migrations"


def db_url() -> str:
    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        env = ROOT / "scraper" / ".env"
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("SUPABASE_DB_URL="):
                url = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not url:
        sys.exit("SUPABASE_DB_URL introuvable (scraper/.env)")
    return url


def main() -> None:
    noms = sys.argv[1:] or sorted(p.name for p in MIG.glob("*.sql"))
    with psycopg.connect(db_url(), autocommit=True) as con:
        for nom in noms:
            f = MIG / nom
            if not f.exists():
                print(f"  ! {nom} introuvable"); continue
            sql = f.read_text(encoding="utf-8")
            try:
                with con.cursor() as cur:
                    cur.execute(sql)
                print(f"  ✓ {nom}")
            except Exception as e:
                print(f"  ✗ {nom} : {str(e)[:160]}")


if __name__ == "__main__":
    main()
