"""sqlite_store.py — Stockage LOCAL (SQLite) reflétant supabase/schema.sql.

Gère le diff (new/changed/unchanged), l'historique de prix, le passage en
inactif des annonces disparues, les scan_runs et les stats par khet.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from store.base import BaseStore

_SCHEMA = """
create table if not exists listings (
  id text primary key, source text not null, source_url text not null,
  title text, deal_type text, quota text, tenure text default 'freehold',
  price real, currency text default 'THB',
  area_sqm real, price_per_sqm real, bedrooms integer, bathrooms integer,
  condo_name text, address_raw text, khet text, khwaeng text, street text,
  lat real, lng real, status text not null default 'active',
  first_seen text not null, last_seen text not null, delisted_at text, raw_data text
);
create table if not exists khet_snapshots (
  id integer primary key autoincrement, taken_at text not null, khet text not null,
  active_count integer, avg_price_per_sqm real, median_price_per_sqm real
);
create table if not exists listing_images (
  id integer primary key autoincrement, listing_id text not null,
  storage_path text not null, width integer, height integer, ord integer default 0
);
create table if not exists listing_amenities (
  id integer primary key autoincrement, listing_id text not null, name text not null
);
create table if not exists price_history (
  id integer primary key autoincrement, listing_id text not null,
  price real not null, observed_at text not null
);
create table if not exists scan_runs (
  id integer primary key autoincrement, started_at text not null, finished_at text,
  source text not null, scanned_count integer, new_count integer,
  removed_count integer, changed_count integer, notes text
);
create index if not exists idx_listings_khet on listings(khet);
create index if not exists idx_listings_status on listings(status);
create index if not exists idx_images_listing on listing_images(listing_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteStore(BaseStore):
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(_SCHEMA)
        self.db.commit()

    def get_listing(self, listing_id: str) -> dict | None:
        row = self.db.execute("select * from listings where id=?", (listing_id,)).fetchone()
        return dict(row) if row else None

    def has_images(self, listing_id: str) -> bool:
        row = self.db.execute(
            "select 1 from listing_images where listing_id=? limit 1", (listing_id,)
        ).fetchone()
        return row is not None

    def touch_listing(self, listing_id: str) -> None:
        self.db.execute(
            "update listings set status='active', last_seen=? where id=?",
            (_now(), listing_id),
        )
        self.db.commit()

    def upsert_listing(self, norm: dict, images: list[dict] | None) -> tuple[str, float | None]:
        existing = self.get_listing(norm["id"])
        now = _now()
        cols = (
            "source", "source_url", "title", "deal_type", "quota", "tenure", "price",
            "currency", "area_sqm", "price_per_sqm", "bedrooms", "bathrooms", "condo_name",
            "address_raw", "khet", "khwaeng", "street", "lat", "lng",
        )

        if existing is None:
            self.db.execute(
                f"insert into listings (id,{','.join(cols)},status,first_seen,last_seen,raw_data) "
                f"values (?,{','.join('?' for _ in cols)},'active',?,?,?)",
                (norm["id"], *[norm.get(c) for c in cols], now, now,
                 json.dumps(norm.get("raw_data", {}), ensure_ascii=False)),
            )
            if norm.get("price") is not None:
                self._add_price(norm["id"], norm["price"], now)
            self._set_images(norm["id"], images)
            self._set_amenities(norm["id"], norm.get("amenities", []))
            self.db.commit()
            return "new", None

        old_price = existing["price"]
        new_price = norm.get("price")
        self.db.execute(
            f"update listings set {','.join(c+'=?' for c in cols)},"
            f"status='active',last_seen=?,raw_data=? where id=?",
            (*[norm.get(c) for c in cols], now,
             json.dumps(norm.get("raw_data", {}), ensure_ascii=False), norm["id"]),
        )
        status = "unchanged"
        if new_price is not None and old_price is not None and float(new_price) != float(old_price):
            self._add_price(norm["id"], new_price, now)
            status = "changed"
        if images is not None:
            self._set_images(norm["id"], images)
        self.db.commit()
        return status, old_price

    def _add_price(self, listing_id: str, price: float, when: str) -> None:
        self.db.execute(
            "insert into price_history (listing_id,price,observed_at) values (?,?,?)",
            (listing_id, price, when),
        )

    def _set_images(self, listing_id: str, images: list[dict] | None) -> None:
        if images is None:
            return
        self.db.execute("delete from listing_images where listing_id=?", (listing_id,))
        for im in images:
            self.db.execute(
                "insert into listing_images (listing_id,storage_path,width,height,ord) "
                "values (?,?,?,?,?)",
                (listing_id, im["storage_path"], im.get("width"), im.get("height"), im.get("ord", 0)),
            )

    def _set_amenities(self, listing_id: str, amenities: list[str]) -> None:
        self.db.execute("delete from listing_amenities where listing_id=?", (listing_id,))
        for a in amenities:
            self.db.execute(
                "insert into listing_amenities (listing_id,name) values (?,?)", (listing_id, a)
            )

    def count_active(self, source: str, deal_type: str | None = None) -> int:
        q = "select count(*) c from listings where source=? and status='active'"
        params: list = [source]
        if deal_type:
            q += " and deal_type=?"
            params.append(deal_type)
        return self.db.execute(q, params).fetchone()["c"]

    def mark_missing_inactive(self, source: str, seen_ids: set[str],
                              deal_type: str | None = None) -> list[str]:
        q = "select id from listings where source=? and status='active'"
        params: list = [source]
        if deal_type:
            q += " and deal_type=?"
            params.append(deal_type)
        active = {r["id"] for r in self.db.execute(q, params).fetchall()}
        missing = list(active - seen_ids)
        now = _now()
        for lid in missing:
            self.db.execute(
                "update listings set status='inactive', delisted_at=? where id=?", (now, lid)
            )
        self.db.commit()
        return missing

    def get_image_paths(self, listing_id: str) -> list[str]:
        return [
            r["storage_path"]
            for r in self.db.execute(
                "select storage_path from listing_images where listing_id=?", (listing_id,)
            ).fetchall()
        ]

    def delete_images(self, listing_id: str) -> None:
        self.db.execute("delete from listing_images where listing_id=?", (listing_id,))
        self.db.commit()

    def record_scan_run(self, source: str, scanned: int, new: int,
                        removed: int, changed: int, notes: str = "") -> None:
        now = _now()
        self.db.execute(
            "insert into scan_runs (started_at,finished_at,source,scanned_count,"
            "new_count,removed_count,changed_count,notes) values (?,?,?,?,?,?,?,?)",
            (now, now, source, scanned, new, removed, changed, notes),
        )
        self.db.commit()

    def khet_stats(self) -> list[dict]:
        rows = self.db.execute(
            "select khet, count(*) as active_count, "
            "round(avg(price_per_sqm)) as avg_price_per_sqm "
            "from listings where status='active' and khet is not null "
            "group by khet order by active_count desc"
        ).fetchall()
        return [dict(r) for r in rows]

    def record_khet_snapshots(self) -> int:
        now = _now()
        rows = self.khet_stats()
        for r in rows:
            self.db.execute(
                "insert into khet_snapshots (taken_at,khet,active_count,avg_price_per_sqm,"
                "median_price_per_sqm) values (?,?,?,?,?)",
                (now, r["khet"], r["active_count"], r["avg_price_per_sqm"], None),
            )
        self.db.commit()
        return len(rows)

    def close(self) -> None:
        self.db.close()
