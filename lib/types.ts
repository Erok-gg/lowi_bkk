/**
 * types.ts — Schéma de listing NORMALISÉ. Source de vérité côté front,
 * aligné sur la table `listings` de Supabase (supabase/schema.sql).
 * Le scraper Python produit des dicts conformes à cette forme (via normalize.py).
 */

export type DealType = "sale" | "rent";
export type Quota = "foreigner" | "thai";
export type Tenure = "freehold" | "leasehold";
export type ListingStatus = "active" | "inactive" | "sold";

export interface ListingImage {
  storagePath: string; // chemin dans Supabase Storage (webp 1024x768)
  width: number;
  height: number;
  order: number;
}

/** Proximité calculée (lib/proximity.ts) — modulaire/interchangeable. */
export interface Proximity {
  nearestSchools: { name: string; distanceM: number }[];
  nearestMetro: { name: string; line?: string; distanceM: number }[];
  nearestBusStop?: { name: string; distanceM: number };
  cbdDistanceM?: number;
}

export interface Listing {
  id: string;
  source: string; // ex: "fazwaz"
  sourceUrl: string;
  title: string;
  dealType: DealType;
  quota: Quota;
  tenure?: Tenure;
  price: number;
  currency: string; // ex: "THB"
  areaSqm: number | null;
  pricePerSqm: number | null;
  bedrooms: number | null;
  bathrooms: number | null;
  condoName: string | null;
  amenities: string[]; // amenities du condominium
  addressRaw: string | null;
  khet: string | null; // quartier (district)
  khwaeng: string | null; // sous-district
  street: string | null;
  lat: number | null;
  lng: number | null;
  status: ListingStatus;
  firstSeen: string; // ISO
  lastSeen: string; // ISO
  images: ListingImage[];
  proximity?: Proximity;
  rawData?: Record<string, unknown>;
}

/** Stats agrégées (vues khet_stats / street_stats). */
export interface AreaStats {
  area: string; // nom du quartier ou de la rue
  level: "khet" | "street";
  activeCount: number;
  avgPricePerSqm: number | null;
  medianPricePerSqm: number | null;
  typeDistribution: Record<string, number>;
}
