"""supabase_store.py — Stockage ONLINE (Postgres Supabase) via psycopg.

Même interface que SqliteStore (BaseStore) → le pipeline ne change pas.
Connexion Postgres directe (pooler session) → bypass RLS (utilisateur postgres).
DSN lu depuis SUPABASE_DB_URL.
"""
from __future__ import annotations

from datetime import datetime, timezone

import psycopg
from psycopg.types.json import Json

from store.base import BaseStore

_COLS = (
    "source", "source_url", "title", "deal_type", "quota", "tenure", "price",
    "currency", "area_sqm", "price_per_sqm", "bedrooms", "bathrooms", "condo_name",
    "address_raw", "khet", "khwaeng", "street", "lat", "lng",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SupabaseStore(BaseStore):
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.db = psycopg.connect(dsn, connect_timeout=20, autocommit=True)

    def _reconnect(self) -> None:
        try:
            self.db.close()
        except Exception:
            pass
        self.db = psycopg.connect(self.dsn, connect_timeout=20, autocommit=True)

    def _execute(self, sql: str, params=()):
        """execute avec reconnexion auto si la connexion Postgres a sauté
        (blip réseau / timeout pooler) → un blip ne tue plus le run."""
        try:
            return self.db.execute(sql, params)
        except (psycopg.OperationalError, psycopg.InterfaceError):
            self._reconnect()
            return self.db.execute(sql, params)

    def get_listing(self, listing_id: str) -> dict | None:
        row = self._execute(
            "select id, price from listings where id=%s", (listing_id,)
        ).fetchone()
        return {"id": row[0], "price": row[1]} if row else None

    def has_images(self, listing_id: str) -> bool:
        return self._execute(
            "select 1 from listing_images where listing_id=%s limit 1", (listing_id,)
        ).fetchone() is not None

    def touch_listing(self, listing_id: str) -> None:
        self._execute(
            "update listings set status='active', last_seen=%s where id=%s",
            (_now(), listing_id),
        )

    def upsert_listing(self, norm: dict, images: list[dict] | None) -> tuple[str, float | None]:
        existing = self.get_listing(norm["id"])
        now = _now()
        vals = [norm.get(c) for c in _COLS]

        if existing is None:
            placeholders = ",".join(["%s"] * (len(_COLS) + 5))  # id + cols + status + 2 dates + raw_data
            self._execute(
                f"insert into listings (id,{','.join(_COLS)},status,first_seen,last_seen,raw_data) "
                f"values ({placeholders})",
                (norm["id"], *vals, "active", now, now, Json(norm.get("raw_data", {}))),
            )
            if norm.get("price") is not None:
                self._add_price(norm["id"], norm["price"], now)
            self._set_images(norm["id"], images)
            self._set_amenities(norm["id"], norm.get("amenities", []))
            return "new", None

        old_price = existing["price"]
        new_price = norm.get("price")
        set_clause = ",".join(f"{c}=%s" for c in _COLS)
        self._execute(
            f"update listings set {set_clause},status='active',last_seen=%s,raw_data=%s where id=%s",
            (*vals, now, Json(norm.get("raw_data", {})), norm["id"]),
        )
        status = "unchanged"
        if new_price is not None and old_price is not None and float(new_price) != float(old_price):
            self._add_price(norm["id"], new_price, now)
            status = "changed"
        if images is not None:
            self._set_images(norm["id"], images)
        return status, old_price

    def _add_price(self, listing_id: str, price: float, when: str) -> None:
        self._execute(
            "insert into price_history (listing_id,price,observed_at) values (%s,%s,%s)",
            (listing_id, price, when),
        )

    def _set_images(self, listing_id: str, images: list[dict] | None) -> None:
        if images is None:
            return
        self._execute("delete from listing_images where listing_id=%s", (listing_id,))
        for im in images:
            self._execute(
                "insert into listing_images (listing_id,storage_path,width,height,ord) "
                "values (%s,%s,%s,%s,%s)",
                (listing_id, im["storage_path"], im.get("width"), im.get("height"), im.get("ord", 0)),
            )

    def _set_amenities(self, listing_id: str, amenities: list[str]) -> None:
        self._execute("delete from listing_amenities where listing_id=%s", (listing_id,))
        for a in amenities:
            self._execute(
                "insert into listing_amenities (listing_id,name) values (%s,%s)", (listing_id, a)
            )

    def count_active(self, source: str, deal_type: str | None = None) -> int:
        q = "select count(*) from listings where source=%s and status='active'"
        params: list = [source]
        if deal_type:
            q += " and deal_type=%s"
            params.append(deal_type)
        return self._execute(q, params).fetchone()[0]

    def mark_missing_inactive(self, source: str, seen_ids: set[str],
                              deal_type: str | None = None) -> list[str]:
        q = "select id from listings where source=%s and status='active'"
        params: list = [source]
        if deal_type:
            q += " and deal_type=%s"
            params.append(deal_type)
        active = {r[0] for r in self._execute(q, params).fetchall()}
        missing = list(active - seen_ids)
        now = _now()
        for lid in missing:
            self._execute(
                "update listings set status='inactive', delisted_at=%s where id=%s", (now, lid)
            )
        return missing

    def get_image_paths(self, listing_id: str) -> list[str]:
        return [
            r[0] for r in self._execute(
                "select storage_path from listing_images where listing_id=%s", (listing_id,)
            ).fetchall()
        ]

    def delete_images(self, listing_id: str) -> None:
        self._execute("delete from listing_images where listing_id=%s", (listing_id,))

    def record_scan_run(self, source: str, scanned: int, new: int,
                        removed: int, changed: int, notes: str = "") -> None:
        now = _now()
        self._execute(
            "insert into scan_runs (started_at,finished_at,source,scanned_count,"
            "new_count,removed_count,changed_count,notes) values (%s,%s,%s,%s,%s,%s,%s,%s)",
            (now, now, source, scanned, new, removed, changed, notes),
        )

    def khet_stats(self) -> list[dict]:
        rows = self._execute(
            "select khet, count(*) filter (where status='active') as active_count, "
            "round(avg(price_per_sqm) filter (where status='active')) as avg_price_per_sqm "
            "from listings where khet is not null group by khet order by active_count desc"
        ).fetchall()
        return [{"khet": r[0], "active_count": r[1], "avg_price_per_sqm": r[2]} for r in rows]

    def record_khet_snapshots(self) -> int:
        now = _now()
        rows = self._execute(
            "select khet, count(*) filter (where status='active') as ac, "
            "round(avg(price_per_sqm) filter (where status='active')) as avg, "
            "percentile_cont(0.5) within group (order by price_per_sqm) "
            "  filter (where status='active') as med "
            "from listings where khet is not null group by khet"
        ).fetchall()
        for khet, ac, avg, med in rows:
            self._execute(
                "insert into khet_snapshots (taken_at,khet,active_count,avg_price_per_sqm,"
                "median_price_per_sqm) values (%s,%s,%s,%s,%s)",
                (now, khet, ac, avg, med),
            )
        return len(rows)

    def close(self) -> None:
        self.db.close()
