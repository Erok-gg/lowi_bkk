/**
 * listings-db.ts — Lecture (server-only) des annonces.
 * - Si SUPABASE_DB_URL est défini → Postgres Supabase (online).
 * - Sinon → SQLite local du scraper (node:sqlite).
 * L'UI ne change pas selon la source.
 */
import "server-only";
import type { Listing } from "@/lib/types";
import type { TensionInput, KhetSnapshot } from "@/lib/tension";
import { memoTTL } from "@/lib/cache";

const num = (v: unknown): number | null =>
  v == null || v === "" ? null : Number(v);

// timestamptz (pg → Date) ou texte ISO (SQLite) → chaîne ISO uniforme.
const iso = (v: unknown): string =>
  v == null ? "" : v instanceof Date ? v.toISOString() : String(v);

/** Colonnes de détails lues dans le descriptif. Le préfixe `d_` les distingue
 *  des champs fournis par la source elle-même. */
const COLONNES_DETAIL = [
  "d_etage", "d_cam_fee_thb", "d_meuble", "d_vues", "d_vues_n", "d_batiment",
  "d_elec_kwh", "d_eau_m3", "d_tarif_regime", "d_quota", "d_proprietaire", "d_animaux_ok",
  "d_publie_par", "d_annee_construction", "d_livre", "d_promoteur", "d_duree_min_mois",
  "d_landmark", "d_unite_ref",
] as const;

/** Les listes sont stockées en TEXT (SQLite) ou jsonb (Postgres). */
function parseListe(v: unknown): unknown {
  if (v == null) return null;
  if (typeof v !== "string") return v;
  try {
    return JSON.parse(v);
  } catch {
    return null;
  }
}

function rowToDetails(r: Record<string, unknown>): Listing["details"] {
  if (!("d_etage" in r)) return undefined; // colonnes absentes de cette base
  const d = {
    floor: num(r.d_etage),
    camFeeThb: num(r.d_cam_fee_thb),
    furnished: (r.d_meuble as string) ?? null,
    views: parseListe(r.d_vues) as string[] | null,
    viewCount: num(r.d_vues_n),
    building: (r.d_batiment as string) ?? null,
    elecThbKwh: num(r.d_elec_kwh),
    waterThbM3: num(r.d_eau_m3),
    utilityRate: (r.d_tarif_regime as "government" | "private") ?? null,
    quota: (r.d_quota as string) ?? null,
    ownerNationality: (r.d_proprietaire as string) ?? null,
    petsAllowed: r.d_animaux_ok == null ? null : Boolean(r.d_animaux_ok),
    listedBy: (r.d_publie_par as string) ?? null,
    yearBuilt: num(r.d_annee_construction),
    delivered: r.d_livre == null ? null : Boolean(r.d_livre),
    developer: (r.d_promoteur as string) ?? null,
    minRentalMonths: num(r.d_duree_min_mois),
    landmark: parseListe(r.d_landmark) as [string, number] | null,
    unitRef: (r.d_unite_ref as string) ?? null,
  };
  // Tout vide = pas de détails du tout : évite d'afficher une section morte.
  return Object.values(d).some((v) => v != null && v !== "") ? d : undefined;
}

/**
 * Quelle source de donnees ?
 *
 * LOWI_SQLITE_DB force la lecture d'un fichier SQLite precis et prime sur
 * Supabase. C'est ce qui permet de previsualiser un scrap ISOLE sans toucher a
 * la production — et sans dependre d'astuces de shell : sous cmd, `set VAR=`
 * SUPPRIME la variable, Next recharge alors .env.local et repart sur Supabase.
 */
function useSupabase(): boolean {
  return !process.env.LOWI_SQLITE_DB && Boolean(process.env.SUPABASE_DB_URL);
}

function rowToListing(r: Record<string, unknown>, images: Listing["images"]): Listing {
  return {
    details: rowToDetails(r),
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
  // Les colonnes de détails ne sont pas encore appliquées en production
  // (supabase/migrations/details_descriptif.sql). On les sélectionne seulement
  // si elles existent, pour que la page fonctionne avant ET après la migration.
  const { rows: cols } = await db.query(
    `select column_name from information_schema.columns
     where table_name = 'listings' and column_name = any($1)`,
    [COLONNES_DETAIL as unknown as string[]]
  );
  const extra = cols.length ? ", " + cols.map((c) => c.column_name).join(", ") : "";
  const { rows } = await db.query(
    `select id, source, source_url, title, deal_type, quota, tenure, price, currency,
            area_sqm, price_per_sqm, bedrooms, bathrooms, condo_name,
            address_raw, khet, khwaeng, street, lat, lng, status, first_seen, last_seen${extra}
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
  // LOWI_SQLITE_DB permet de pointer sur une base de TEST sans toucher a la
  // production : c'est ce qui rend previsualisable un scrap isole.
  const dbPath =
    process.env.LOWI_SQLITE_DB ?? join(process.cwd(), "scraper", "output", "bangkok.db");
  if (!existsSync(dbPath)) return [];
  const db = new DatabaseSync(dbPath, { readOnly: true });
  try {
    const presentes = new Set(
      (db.prepare("pragma table_info(listings)").all() as Record<string, unknown>[])
        .map((c) => c.name as string)
    );
    const dispo = COLONNES_DETAIL.filter((c) => presentes.has(c));
    const extra = dispo.length ? ", " + dispo.join(", ") : "";
    const rows = db
      .prepare(
        `select id, source, source_url, title, deal_type, quota, tenure, price, currency,
                area_sqm, price_per_sqm, bedrooms, bathrooms, condo_name,
                address_raw, khet, khwaeng, street, lat, lng, status, first_seen, last_seen${extra}
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

/**
 * Toutes les annonces actives. Mémoïsé : les pages sont en `force-dynamic`
 * (l'accès dépend d'un cookie) et rejouaient donc cette requête de 16 000 lignes
 * à chaque navigation, alors que les données ne bougent qu'au rythme des scraps.
 */
export const getListings = memoTTL(
  "listings",
  async (): Promise<Listing[]> =>
    useSupabase() ? fromSupabase() : fromSqlite()
);

/**
 * Prix d'origine (max historique) par listing_id, depuis price_history.
 * Sert à la décote temporelle (baisse de prix depuis le 1er relevé).
 */
export const getOriginalPrices = memoTTL("original-prices", async (): Promise<Map<string, number>> => {
  const out = new Map<string, number>();
  if (useSupabase()) {
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
});

/* ───────────────────────── Tension (séries temporelles) ───────────────────────── */

const dealOf = (v: unknown): TensionInput["dealType"] =>
  (v as TensionInput["dealType"]) ?? "sale";

/**
 * Annonces réduites à leur dimension temporelle — ACTIVES + DISPARUES
 * (inactive/sold), pour calculer âge et time-on-market. Payload léger.
 */
export const getTensionInputs = memoTTL("tension-inputs", async (): Promise<TensionInput[]> => {
  if (useSupabase()) {
    const db = await getPool();
    const { rows } = await db.query(
      `select khet, street, deal_type, status, first_seen, delisted_at, condo_name
       from listings where khet is not null`
    );
    return rows.map((r) => ({
      khet: (r.khet as string) ?? null,
      street: (r.street as string) ?? null,
      dealType: dealOf(r.deal_type),
      status: r.status as TensionInput["status"],
      firstSeen: r.first_seen ? iso(r.first_seen) : null,
      delistedAt: r.delisted_at ? iso(r.delisted_at) : null,
      // Dénominateur de la pression vendeuse (annonces par immeuble)
      condoName: (r.condo_name as string) ?? null,
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
        `select khet, street, deal_type, status, first_seen, delisted_at, condo_name
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
      // Dénominateur de la pression vendeuse (annonces par immeuble)
      condoName: (r.condo_name as string) ?? null,
    }));
  } finally {
    db.close();
  }
});

/**
 * Séries temporelles par quartier × deal_type (khet_snapshots) pour les pentes.
 * Résilient : tant que la colonne `deal_type` n'est pas migrée (ou la table vide),
 * on retourne [] → la tension dégrade gracieusement (composantes de tendance nulles).
 */
export const getKhetSnapshots = memoTTL("khet-snapshots", async (): Promise<KhetSnapshot[]> => {
  const mapRow =(r: Record<string, unknown>): KhetSnapshot => ({
    takenAt: iso(r.taken_at),
    khet: r.khet as string,
    dealType: (r.deal_type as KhetSnapshot["dealType"]) ?? null,
    activeCount: num(r.active_count),
    avgPricePerSqm: num(r.avg_price_per_sqm),
    // Le momentum prix se calcule sur la médiane (cf. lib/tension.ts) ; la
    // moyenne reste lue pour le repli des instantanés qui n'ont pas de médiane.
    medianPricePerSqm: num(r.median_price_per_sqm),
  });
  const SQL =
    "select taken_at, khet, deal_type, active_count, avg_price_per_sqm," +
    " median_price_per_sqm from khet_snapshots order by taken_at";

  if (useSupabase()) {
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
});
