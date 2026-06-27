/**
 * deals.ts — "Bonnes affaires" : pour chaque bien en VENTE, calcule une décote
 * marché (prix/m² sous la médiane comparable), une décote temporelle (baisse de
 * prix depuis le 1er relevé) et un rendement estimé (loyer médian comparable).
 * Comparable = même quartier + même tranche de chambres. Baseline = moyenne des
 * 10 valeurs médianes (medianAvg, lib/yields).
 */
import type { Listing } from "@/lib/types";
import { medianAvg } from "@/lib/yields";

export type BedCat = "1" | "2" | "3" | "4+";
export const BED_CATS: BedCat[] = ["1", "2", "3", "4+"];

const BASELINE_N = 10;
// Bornes de prix de vente plausibles (mêmes que la page For sale) : écarte les
// aberrations (loyer mal classé en vente, prix erronés) qui faussent les décotes.
const SALE_MIN = 800_000;
const SALE_MAX = 100_000_000;

const saleInRange = (l: Listing) =>
  l.dealType === "sale" && !!l.price && l.price >= SALE_MIN && l.price <= SALE_MAX;

/** Tranche de chambres : 1, 2, 3, ou 4 (regroupe 4+). null si inconnu. */
function bucket(beds: number | null): number | null {
  if (beds == null) return null;
  return beds >= 4 ? 4 : beds;
}

export function matchBedCat(beds: number | null, cat: BedCat): boolean {
  const b = bucket(beds);
  return cat === "4+" ? b === 4 : b === Number(cat);
}

const keyOf = (khet: string | null, beds: number | null) => `${khet ?? ""}|${bucket(beds)}`;

export interface DealRow {
  id: string;
  name: string;
  khet: string | null;
  bedrooms: number | null;
  price: number;
  pricePerSqm: number;
  areaSqm: number | null;
  lat: number | null;
  lng: number | null;
  sourceUrl: string;
  marketDiscountPct: number | null; // % sous la médiane comparable (>0 = bonne affaire)
  temporalDiscountPct: number | null; // % de baisse depuis le 1er relevé
  estYieldPct: number | null; // rendement estimé (loyer médian comparable)
}

/** Baseline prix/m² (moyenne des 10 médians) par (khet+tranche) pour un deal_type. */
function baselineByKey(listings: Listing[], deal: "sale" | "rent"): Map<string, number> {
  const groups = new Map<string, number[]>();
  for (const l of listings) {
    if (l.dealType !== deal || l.pricePerSqm == null || l.bedrooms == null) continue;
    if (deal === "sale" && !saleInRange(l)) continue; // baseline vente assainie
    const k = keyOf(l.khet, l.bedrooms);
    (groups.get(k) ?? groups.set(k, []).get(k)!).push(l.pricePerSqm);
  }
  const out = new Map<string, number>();
  for (const [k, vals] of groups) {
    const m = medianAvg(vals, BASELINE_N);
    if (m != null) out.set(k, m);
  }
  return out;
}

/** Enrichit chaque bien en vente avec décotes + rendement estimé. */
export function enrichSaleDeals(
  listings: Listing[],
  originalPrices: Map<string, number>
): DealRow[] {
  const saleBase = baselineByKey(listings, "sale");
  const rentBase = baselineByKey(listings, "rent");

  const rows: DealRow[] = [];
  for (const l of listings) {
    if (!saleInRange(l) || l.pricePerSqm == null || l.bedrooms == null) continue;
    const k = keyOf(l.khet, l.bedrooms);
    const sBase = saleBase.get(k);
    const rBase = rentBase.get(k);
    const orig = originalPrices.get(l.id);
    rows.push({
      id: l.id,
      name: l.condoName || l.title || "—",
      khet: l.khet,
      bedrooms: l.bedrooms,
      price: l.price,
      pricePerSqm: l.pricePerSqm,
      areaSqm: l.areaSqm,
      lat: l.lat,
      lng: l.lng,
      sourceUrl: l.sourceUrl,
      marketDiscountPct:
        sBase ? Math.round(((sBase - l.pricePerSqm) / sBase) * 1000) / 10 : null,
      temporalDiscountPct:
        orig && orig > l.price ? Math.round(((orig - l.price) / orig) * 1000) / 10 : orig ? 0 : null,
      estYieldPct:
        rBase ? Math.round(((rBase * 12) / l.pricePerSqm) * 1000) / 10 : null,
    });
  }
  return rows;
}

/** Top N par décote marché (descendante) pour une tranche de chambres. */
export function bestDiscounts(rows: DealRow[], cat: BedCat, limit = 20): DealRow[] {
  return rows
    .filter((r) => matchBedCat(r.bedrooms, cat) && r.marketDiscountPct != null)
    .sort((a, b) => (b.marketDiscountPct ?? -Infinity) - (a.marketDiscountPct ?? -Infinity))
    .slice(0, limit);
}

/** Top N par rendement estimé (descendant) pour une tranche de chambres. */
export function bestYields(rows: DealRow[], cat: BedCat, limit = 20): DealRow[] {
  return rows
    .filter((r) => matchBedCat(r.bedrooms, cat) && r.estYieldPct != null)
    .sort((a, b) => (b.estYieldPct ?? -Infinity) - (a.estYieldPct ?? -Infinity))
    .slice(0, limit);
}
