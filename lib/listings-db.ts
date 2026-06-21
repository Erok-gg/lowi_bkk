/**
 * listings-db.ts — Lecture (server-only) des annonces.
 * - Si SUPABASE_DB_URL est défini → Postgres Supabase (online).
 * - Sinon → SQLite local du scraper (node:sqlite).
 * L'UI ne change pas selon la source.
 */
import "server-only";
import type { Listing } from "@/lib/types";

const num = (v: unknown): number | null =>
  v == null || v === "" ? null : Number(v);

function rowToListing(r: Record<string, unknown>, images: Listing["images"]): Listing {
  return {
    id: r.id as string,
    source: r.source as string,
    sourceUrl: r.source_url as string,
    title: (r.title as string) ?? "",
    dealType: r.deal_type as Listing["dealType"],
    quota: r.quota as Listing["quota"],
    tenure: (r.tenure as Listing["tenure"]) ?? undefined,
    price: num(r.price) ?? 0,
    currency: (r.currency as string) ?? "THB",
    areaSqm: num(r.area_sqm),
    pricePerSqm: num(r.price_per_sqm),
    bedrooms: num(r.bedrooms),
    bathrooms: num(r.bathrooms),
    condoName: (r.condo_name as string) ?? null,
    amenities: [],
    addressRaw: (r.address_raw as string) ?? null,
    khet: (r.khet as string) ?? null,
    khwaeng: (r.khwaeng as string) ?? null,
    street: (r.street as string) ?? null,
    lat: num(r.lat),
    lng: num(r.lng),
    status: r.status as Listing["status"],
    firstSeen: "",
    lastSeen: "",
    images,
  };
}

/* ───────────────────────── Supabase (Postgres) ───────────────────────── */
import type { Pool as PgPool } from "pg";
let pool: PgPool | null = null;

async function getPool(): Promise<PgPool> {
  if (pool) return pool;
  const { Pool } = await import("pg");
  pool = new Pool({
    connectionString: process.env.SUPABASE_DB_URL,
    ssl: { rejectUnauthorized: false },
    max: 3,
  });
  return pool;
}

async function fromSupabase(): Promise<Listing[]> {
  const db = await getPool();
  const { rows } = await db.query(
    `select id, source, source_url, title, deal_type, quota, tenure, price, currency,
            area_sqm, price_per_sqm, bedrooms, bathrooms, condo_name,
            address_raw, khet, khwaeng, street, lat, lng, status
     from listings where status = 'active'`
  );
  const imgs = await db.query(
    "select listing_id, storage_path, width, height, ord from listing_images order by ord"
  );
  const byId = new Map<string, Listing["images"]>();
  for (const im of imgs.rows) {
    const arr = byId.get(im.listing_id) ?? [];
    arr.push({
      storagePath: im.storage_path,
      width: im.width,
      height: im.height,
      order: im.ord,
    });
    byId.set(im.listing_id, arr);
  }
  return rows.map((r) => rowToListing(r, byId.get(r.id) ?? []));
}

/* ───────────────────────── SQLite local ───────────────────────── */
async function fromSqlite(): Promise<Listing[]> {
  const { DatabaseSync } = await import("node:sqlite");
  const { join } = await import("node:path");
  const { existsSync } = await import("node:fs");
  const dbPath = join(process.cwd(), "scraper", "output", "bangkok.db");
  if (!existsSync(dbPath)) return [];
  const db = new DatabaseSync(dbPath, { readOnly: true });
  try {
    const rows = db
      .prepare(
        `select id, source, source_url, title, deal_type, quota, tenure, price, currency,
                area_sqm, price_per_sqm, bedrooms, bathrooms, condo_name,
                address_raw, khet, khwaeng, street, lat, lng, status
         from listings where status = 'active'`
      )
      .all() as Record<string, unknown>[];
    const imgStmt = db.prepare(
      "select storage_path, width, height, ord from listing_images where listing_id = ? order by ord"
    );
    return rows.map((r) => {
      const images = (imgStmt.all(r.id as string) as Record<string, unknown>[]).map((im) => ({
        storagePath: im.storage_path as string,
        width: im.width as number,
        height: im.height as number,
        order: im.ord as number,
      }));
      return rowToListing(r, images);
    });
  } finally {
    db.close();
  }
}

export async function getListings(): Promise<Listing[]> {
  return process.env.SUPABASE_DB_URL ? fromSupabase() : fromSqlite();
}
