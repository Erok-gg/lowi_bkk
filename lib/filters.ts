/**
 * filters.ts — Filtres partagés entre la vue Tableau et la carte.
 * Le tableau écrit l'état dans l'URL (query params) ; la carte le relit pour
 * n'afficher que les pinpoints correspondants. Une seule source de logique.
 */
import type { Listing } from "@/lib/types";

export interface Filters {
  priceMin?: number; priceMax?: number;
  areaMin?: number; areaMax?: number;
  ppsqmMin?: number; ppsqmMax?: number;
  bedsMin?: number; bedsMax?: number;
  bathsMin?: number; bathsMax?: number;
  quota: Set<string>;
  deal: Set<string>;
  source: Set<string>;
  khet: Set<string>;
}

const inRange = (v: number | null | undefined, lo?: number, hi?: number) =>
  v == null ? true : (lo == null || v >= lo) && (hi == null || v <= hi);

export function applyFilters(listings: Listing[], f: Filters): Listing[] {
  return listings.filter((l) => {
    if (!inRange(l.price, f.priceMin, f.priceMax)) return false;
    if (!inRange(l.areaSqm, f.areaMin, f.areaMax)) return false;
    if (!inRange(l.pricePerSqm, f.ppsqmMin, f.ppsqmMax)) return false;
    if (!inRange(l.bedrooms ?? 0, f.bedsMin, f.bedsMax)) return false;
    if (!inRange(l.bathrooms ?? 0, f.bathsMin, f.bathsMax)) return false;
    if (f.quota.size && !(l.quota && f.quota.has(l.quota))) return false;
    if (f.deal.size && !f.deal.has(l.dealType)) return false;
    if (f.source.size && !f.source.has(l.source)) return false;
    if (f.khet.size && !(l.khet && f.khet.has(l.khet))) return false;
    return true;
  });
}

/* ─────────── (dé)sérialisation URL ─────────── */
const N = (s: string | null) => (s != null && s !== "" ? Number(s) : undefined);
const SET = (s: string | null) => new Set(s ? s.split(",").filter(Boolean) : []);

export function filtersToParams(f: Filters): URLSearchParams {
  const p = new URLSearchParams();
  const put = (k: string, v?: number) => v != null && p.set(k, String(v));
  put("pmin", f.priceMin); put("pmax", f.priceMax);
  put("amin", f.areaMin); put("amax", f.areaMax);
  put("ppmin", f.ppsqmMin); put("ppmax", f.ppsqmMax);
  put("bmin", f.bedsMin); put("bmax", f.bedsMax);
  put("btmin", f.bathsMin); put("btmax", f.bathsMax);
  if (f.quota.size) p.set("quota", [...f.quota].join(","));
  if (f.deal.size) p.set("deal", [...f.deal].join(","));
  if (f.source.size) p.set("source", [...f.source].join(","));
  if (f.khet.size) p.set("khet", [...f.khet].join(","));
  return p;
}

export function filtersFromParams(p: URLSearchParams): Filters {
  return {
    priceMin: N(p.get("pmin")), priceMax: N(p.get("pmax")),
    areaMin: N(p.get("amin")), areaMax: N(p.get("amax")),
    ppsqmMin: N(p.get("ppmin")), ppsqmMax: N(p.get("ppmax")),
    bedsMin: N(p.get("bmin")), bedsMax: N(p.get("bmax")),
    bathsMin: N(p.get("btmin")), bathsMax: N(p.get("btmax")),
    quota: SET(p.get("quota")), deal: SET(p.get("deal")),
    source: SET(p.get("source")), khet: SET(p.get("khet")),
  };
}

export function applyUrlFilters(listings: Listing[], p: URLSearchParams): Listing[] {
  return applyFilters(listings, filtersFromParams(p));
}
