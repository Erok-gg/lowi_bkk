"""db.py — accès Supabase pour les agents.

Reprend le pattern éprouvé de study/run_study.py : les variables viennent de
scraper/.env, la connexion passe par le pooler session (bypass RLS).
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.dirname(ROOT)
_LOADED = False


def load_env() -> None:
    global _LOADED
    if _LOADED:
        return
    for name in ("scraper/.env", ".env.local"):
        path = os.path.join(PROJECT, name)
        if not os.path.exists(path):
            continue
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    sys.path.insert(0, os.path.join(PROJECT, "scraper"))
    _LOADED = True


def connect():
    load_env()
    import psycopg  # importé après load_env pour bénéficier du sys.path
    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        raise RuntimeError("SUPABASE_DB_URL absent de scraper/.env et .env.local")
    return psycopg.connect(url)


def query(sql: str, params: tuple = ()) -> list[dict]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        if cur.description is None:
            return []
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def scalar(sql: str, params: tuple = ()):
    rows = query(sql, params)
    if not rows:
        return None
    return next(iter(rows[0].values()))
