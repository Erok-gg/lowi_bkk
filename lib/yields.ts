/**
 * yields.ts — Rendement locatif par quartier, calculé à partir des annonces.
 * Rendement brut ≈ (loyer/m² médian × 12) / (prix-vente/m² médian) × 100.
 * Indépendant du backend (mêmes données que getListings).
 */
import type { Listing } from "@/lib/types";

export interface YieldRow {
  khet: string;
  nSale: number;
  nRent: number;
  saleMedianPsqm: number | null;
  rentMedianPsqm: number | null;
  grossYieldPct: number | null;
}

export interface StreetYieldRow {
  street: string;
  nSale: number;
  nRent: number;
  saleMedianPsqm: number | null;
  rentMedianPsqm: number | null;
  grossYieldPct: number | null;
}

function median(vals: number[]): number | null {
  const f = vals.filter((v) => Number.isFinite(v) && v > 0).sort((a, b) => a - b);
  if (!f.length) return null;
  const mid = Math.floor(f.length / 2);
  return f.length % 2 ? f[mid] : (f[mid - 1] + f[mid]) / 2;
}

export function computeYieldsByKhet(listings: Listing[]): YieldRow[] {
  const byKhet = new Map<string, Listing[]>();
  for (const l of listings) {
    if (!l.khet) continue;
    const arr = byKhet.get(l.khet) ?? [];
    arr.push(l);
    byKhet.set(l.khet, arr);
  }

  const rows: YieldRow[] = [];
  for (const [khet, arr] of byKhet) {
    const sale = arr.filter((l) => l.dealType === "sale");
    const rent = arr.filter((l) => l.dealType === "rent");
    const saleP = median(sale.map((l) => l.pricePerSqm ?? NaN));
    const rentP = median(rent.map((l) => l.pricePerSqm ?? NaN));
    rows.push({
      khet,
      nSale: sale.length,
      nRent: rent.length,
      saleMedianPsqm: saleP,
      rentMedianPsqm: rentP,
      grossYieldPct:
        saleP && rentP ? Math.round((rentP * 12 / saleP) * 1000) / 10 : null,
    });
  }
  return rows;
}

/** Rendement par rue répertoriée pour un quartier donné (rues non nulles). */
export function computeYieldsByStreet(listings: Listing[], khet: string): StreetYieldRow[] {
  const byStreet = new Map<string, Listing[]>();
  for (const l of listings) {
    if (l.khet !== khet || !l.street) continue;
    const arr = byStreet.get(l.street) ?? [];
    arr.push(l);
    byStreet.set(l.street, arr);
  }

  const rows: StreetYieldRow[] = [];
  for (const [street, arr] of byStreet) {
    const sale = arr.filter((l) => l.dealType === "sale");
    const rent = arr.filter((l) => l.dealType === "rent");
    const saleP = median(sale.map((l) => l.pricePerSqm ?? NaN));
    const rentP = median(rent.map((l) => l.pricePerSqm ?? NaN));
    rows.push({
      street,
      nSale: sale.length,
      nRent: rent.length,
      saleMedianPsqm: saleP,
      rentMedianPsqm: rentP,
      grossYieldPct:
        saleP && rentP ? Math.round((rentP * 12 / saleP) * 1000) / 10 : null,
    });
  }
  return rows;
}
