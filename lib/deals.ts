/**
 * deals.ts — "Bonnes affaires" : pour chaque bien en VENTE, calcule une décote
 * marché (prix/m² sous la médiane comparable), une décote temporelle (baisse de
 * prix depuis le 1er relevé) et un rendement estimé (loyer médian comparable).
 * Comparable = MÊME CONDO (immeuble) + même tranche de chambres — le plus
 * proche possible, deux lots du même bâtiment sont vraiment comparables (même
 * standing, même micro-localisation). Si l'immeuble n'a pas assez de pairs
 * (MIN_COMPARABLES), repli sur la RUE + tranche de chambres. Le quartier
 * (khet) n'est plus utilisé comme base de comparaison : trop grossier, un
 * même khet mélange des rues et des immeubles très différents en standing.
 * Baseline = moyenne des ~10 valeurs médianes (medianAvg, lib/yields), la
 * fenêtre se réduisant naturellement à ce qui est disponible.
 */
import type { Listing } from "@/lib/types";
import { medianAvg } from "@/lib/yields";
import { normalizeCondoName } from "@/lib/condo-name";
import { isPlausible } from "@/lib/market-bounds";

export type BedCat = "1" | "2" | "3" | "4+";
export const BED_CATS: BedCat[] = ["1", "2", "3", "4+"];

const BASELINE_N = 10;
/** Sous ce nombre de PAIRS (hors le bien lui-même), le groupe est jugé trop
 *  petit pour servir de référence — on descend d'un cran (condo → rue). */
const MIN_COMPARABLES = 3;

// Bornes de plausibilité : lib/market-bounds.ts, source unique partagée avec
// les pages, la tension et la vue SQL `listings_sane`.
const saleInRange = (l: Listing) => l.dealType === "sale" && isPlausible(l);

/** Tranche de chambres : 1, 2, 3, ou 4 (regroupe 4+). null si inconnu. */
function bucket(beds: number | null): number | null {
  if (beds == null) return null;
  return beds >= 4 ? 4 : beds;
}

export function matchBedCat(beds: number | null, cat: BedCat): boolean {
  const b = bucket(beds);
  return cat === "4+" ? b === 4 : b === Number(cat);
}

const condoKeyOf = (condoName: string | null, beds: number | null) => {
  const c = normalizeCondoName(condoName);
  return c ? `${c}|${bucket(beds)}` : null;
};
const streetKeyOf = (street: string | null, beds: number | null) =>
  street ? `${street}|${bucket(beds)}` : null;

export type CompareBasis = "condo" | "street" | null;

export interface DealRow {
  id: string;
  name: string;
  khet: string | null;
  condoName: string | null;
  street: string | null;
  bedrooms: number | null;
  price: number;
  pricePerSqm: number;
  areaSqm: number | null;
  lat: number | null;
  lng: number | null;
  sourceUrl: string;
  marketDiscountPct: number | null; // meilleure décote dispo (condo, sinon rue) — sert au classement
  compareBasis: CompareBasis; // sur quoi marketDiscountPct est calculée
  condoDiscountPct: number | null; // décote vs pairs du MÊME immeuble uniquement
  streetDiscountPct: number | null; // décote vs pairs de la MÊME rue uniquement
  temporalDiscountPct: number | null; // % de baisse depuis le 1er relevé
  estYieldPct: number | null; // rendement estimé (loyer médian comparable)
  yieldBasis: CompareBasis;
}

interface Entry { id: string; pricePerSqm: number }

/** Regroupe les annonces d'un deal_type par clé condo et par clé rue (+ tranche). */
function buildGroups(listings: Listing[], deal: "sale" | "rent") {
  const byCondo = new Map<string, Entry[]>();
  const byStreet = new Map<string, Entry[]>();
  for (const l of listings) {
    if (l.dealType !== deal || l.pricePerSqm == null || l.bedrooms == null) continue;
    // Les DEUX baselines sont assainies : une location à 300 THB/mois faussait
    // le rendement estimé aussi sûrement qu'un prix de vente aberrant.
    if (!isPlausible(l)) continue;
    const entry = { id: l.id, pricePerSqm: l.pricePerSqm };
    const ck = condoKeyOf(l.condoName, l.bedrooms);
    if (ck) (byCondo.get(ck) ?? byCondo.set(ck, []).get(ck)!).push(entry);
    const sk = streetKeyOf(l.street, l.bedrooms);
    if (sk) (byStreet.get(sk) ?? byStreet.set(sk, []).get(sk)!).push(entry);
  }
  return { byCondo, byStreet };
}

/** Baseline sur UN SEUL groupe (condo OU rue), exclut le bien lui-même
 *  (sinon un immeuble à 2 lots se compare à moitié à lui-même). */
function baselineForGroup(
  selfId: string,
  key: string | null,
  byKey: Map<string, Entry[]>
): number | null {
  const group = (key ? byKey.get(key) : undefined)?.filter((e) => e.id !== selfId) ?? [];
  if (group.length < MIN_COMPARABLES) return null;
  return medianAvg(group.map((e) => e.pricePerSqm), BASELINE_N);
}

/** Baseline pour un bien donné : condo d'abord, rue en repli — sert au
 *  classement (bestDiscounts/bestYields), qui a besoin d'une seule valeur. */
function baselineFor(
  selfId: string,
  condoKey: string | null,
  streetKey: string | null,
  byCondo: Map<string, Entry[]>,
  byStreet: Map<string, Entry[]>
): { value: number; basis: CompareBasis } | null {
  const condoVal = baselineForGroup(selfId, condoKey, byCondo);
  if (condoVal != null) return { value: condoVal, basis: "condo" };
  const streetVal = baselineForGroup(selfId, streetKey, byStreet);
  if (streetVal != null) return { value: streetVal, basis: "street" };
  return null;
}

/** Enrichit chaque bien en vente avec décotes + rendement estimé. */
export function enrichSaleDeals(
  listings: Listing[],
  originalPrices: Map<string, number>
): DealRow[] {
  const saleGroups = buildGroups(listings, "sale");
  const rentGroups = buildGroups(listings, "rent");

  const rows: DealRow[] = [];
  for (const l of listings) {
    if (!saleInRange(l) || l.pricePerSqm == null || l.bedrooms == null) continue;
    const condoKey = condoKeyOf(l.condoName, l.bedrooms);
    const streetKey = streetKeyOf(l.street, l.bedrooms);
    const sBase = baselineFor(l.id, condoKey, streetKey, saleGroups.byCondo, saleGroups.byStreet);
    const rBase = baselineFor(l.id, condoKey, streetKey, rentGroups.byCondo, rentGroups.byStreet);
    const condoSaleBase = baselineForGroup(l.id, condoKey, saleGroups.byCondo);
    const streetSaleBase = baselineForGroup(l.id, streetKey, saleGroups.byStreet);
    const pct = (base: number | null) =>
      base ? Math.round(((base - l.pricePerSqm!) / base) * 1000) / 10 : null;
    const orig = originalPrices.get(l.id);
    rows.push({
      id: l.id,
      name: l.condoName || l.title || "—",
      khet: l.khet,
      condoName: l.condoName,
      street: l.street,
      bedrooms: l.bedrooms,
      price: l.price,
      pricePerSqm: l.pricePerSqm,
      areaSqm: l.areaSqm,
      lat: l.lat,
      lng: l.lng,
      sourceUrl: l.sourceUrl,
      marketDiscountPct:
        sBase ? Math.round(((sBase.value - l.pricePerSqm) / sBase.value) * 1000) / 10 : null,
      compareBasis: sBase?.basis ?? null,
      condoDiscountPct: pct(condoSaleBase),
      streetDiscountPct: pct(streetSaleBase),
      temporalDiscountPct:
        orig && orig > l.price ? Math.round(((orig - l.price) / orig) * 1000) / 10 : orig ? 0 : null,
      estYieldPct:
        rBase ? Math.round(((rBase.value * 12) / l.pricePerSqm) * 1000) / 10 : null,
      yieldBasis: rBase?.basis ?? null,
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
