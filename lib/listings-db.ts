/**
 * listings-db.ts — Lecture (server-only) des annonces.
 * - Si SUPABASE_DB_URL est défini → Postgres Supabase (online).
 * - Sinon → SQLite local du scraper (node:sqlite).
 * L'UI ne change pas selon la source.
 */
import "server-only";
import type { Listing } from "@/lib/types";
import type { TensionInput, KhetSnapshot } from "@/lib/tension";

const num = (v: unknown): number | null =>
  v == null || v === "" ? null : Number(v);

// timestamptz (pg → Date) ou texte ISO (SQLite) → chaîne ISO uniforme.
const iso = (v: unknown): string =>
  v == null ? "" : v instanceof Date ? v.toISOString() : String(v);

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
    firstSeen: iso(r.first_seen),
    lastSeen: iso(r.last_seen),
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
            address_raw, khet, khwaeng, street, lat, lng, status, first_seen, last_seen
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
                address_raw, khet, khwaeng, street, lat, lng, status, first_seen, last_seen
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

/**
 * Prix d'origine (max historique) par listing_id, depuis price_history.
 * Sert à la décote temporelle (baisse de prix depuis le 1er relevé).
 */
export async function getOriginalPrices(): Promise<Map<string, number>> {
  const out = new Map<string, number>();
  if (process.env.SUPABASE_DB_URL) {
    const db = await getPool();
    const { rows } = await db.query(
      "select listing_id, max(price) as orig from price_history group by listing_id"
    );
    for (const r of rows) out.set(r.listing_id, Number(r.orig));
    return out;
  }
  const { DatabaseSync } = await import("node:sqlite");
  const { join } = await import("node:path");
  const { existsSync } = await import("node:fs");
  const dbPath = join(process.cwd(), "scraper", "output", "bangkok.db");
  if (!existsSync(dbPath)) return out;
  const db = new DatabaseSync(dbPath, { readOnly: true });
  try {
    const rows = db
      .prepare("select listing_id, max(price) as orig from price_history group by listing_id")
      .all() as Record<string, unknown>[];
    for (const r of rows) out.set(r.listing_id as string, Number(r.orig));
  } finally {
    db.close();
  }
  return out;
}

/* ───────────────────────── Tension (séries temporelles) ───────────────────────── */

const dealOf = (v: unknown): TensionInput["dealType"] =>
  (v as TensionInput["dealType"]) ?? "sale";

/**
 * Annonces réduites à leur dimension temporelle — ACTIVES + DISPARUES
 * (inactive/sold), pour calculer âge et time-on-market. Payload léger.
 */
export async function getTensionInputs(): Promise<TensionInput[]> {
  if (process.env.SUPABASE_DB_URL) {
    const db = await getPool();
    const { rows } = await db.query(
      `select khet, street, deal_type, status, first_seen, delisted_at
       from listings where khet is not null`
    );
    return rows.map((r) => ({
      khet: (r.khet as string) ?? null,
      street: (r.street as string) ?? null,
      dealType: dealOf(r.deal_type),
      status: r.status as TensionInput["status"],
      firstSeen: r.first_seen ? iso(r.first_seen) : null,
      delistedAt: r.delisted_at ? iso(r.delisted_at) : null,
    }));
  }
  const { DatabaseSync } = await import("node:sqlite");
  const { join } = await import("node:path");
  const { existsSync } = await import("node:fs");
  const dbPath = join(process.cwd(), "scraper", "output", "bangkok.db");
  if (!existsSync(dbPath)) return [];
  const db = new DatabaseSync(dbPath, { readOnly: true });
  try {
    const rows = db
      .prepare(
        `select khet, street, deal_type, status, first_seen, delisted_at
         from listings where khet is not null`
      )
      .all() as Record<string, unknown>[];
    return rows.map((r) => ({
      khet: (r.khet as string) ?? null,
      street: (r.street as string) ?? null,
      dealType: dealOf(r.deal_type),
      status: r.status as TensionInput["status"],
      firstSeen: r.first_seen ? iso(r.first_seen) : null,
      delistedAt: r.delisted_at ? iso(r.delisted_at) : null,
    }));
  } finally {
    db.close();
  }
}

/**
 * Séries temporelles par quartier × deal_type (khet_snapshots) pour les pentes.
 * Résilient : tant que la colonne `deal_type` n'est pas migrée (ou la table vide),
 * on retourne [] → la tension dégrade gracieusement (composantes de tendance nulles).
 */
export async function getKhetSnapshots(): Promise<KhetSnapshot[]> {
  const mapRow = (r: Record<string, unknown>): KhetSnapshot => ({
    takenAt: iso(r.taken_at),
    khet: r.khet as string,
    dealType: (r.deal_type as KhetSnapshot["dealType"]) ?? null,
    activeCount: num(r.active_count),
    avgPricePerSqm: num(r.avg_price_per_sqm),
  });
  const SQL =
    "select taken_at, khet, deal_type, active_count, avg_price_per_sqm from khet_snapshots order by taken_at";

  if (process.env.SUPABASE_DB_URL) {
    try {
      const db = await getPool();
      const { rows } = await db.query(SQL);
      return rows.map(mapRow);
    } catch {
      return [];
    }
  }
  try {
    const { DatabaseSync } = await import("node:sqlite");
    const { join } = await import("node:path");
    const { existsSync } = await import("node:fs");
    const dbPath = join(process.cwd(), "scraper", "output", "bangkok.db");
    if (!existsSync(dbPath)) return [];
    const db = new DatabaseSync(dbPath, { readOnly: true });
    try {
      const rows = db.prepare(SQL).all() as Record<string, unknown>[];
      return rows.map(mapRow);
    } finally {
      db.close();
    }
  } catch {
    return [];
  }
}
