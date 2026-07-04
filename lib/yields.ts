/**
 * yields.ts — Prix/m², loyers/m² et rendements par quartier (ou par rue).
 *
 * MÉTHODE (v2, "double médiane par condo") :
 * On ne connaît ni l'année de construction, ni l'étage, ni la vue. Le condo
 * encapsule tout ça (vétusté, standing, micro-localisation, amenities) → on
 * neutralise en agrégeant PAR CONDO d'abord :
 *   1. médiane des annonces de chaque condo (l'étage/la vue = bruit écrasé) ;
 *   2. médiane des condos du quartier (1 condo = 1 voix : un immeuble à 80
 *      annonces ne pèse plus 80× un immeuble à 1 annonce).
 * Rendement : PAR CONDO quand c'est possible (loyer/m² médian × 12 ÷ prix/m²
 * médian DU MÊME immeuble → l'âge, le standing et l'emplacement se simplifient
 * dans la division), puis médiane de ces rendements within-condo. En dessous de
 * MIN_PAIRED_CONDOS immeubles appariés, repli sur le ratio des médianes du
 * quartier (méthode marquée "ratio").
 * Robustesse : winsorisation p5–p95 des valeurs par groupe (si n ≥ 20) et
 * badge lowSample sous LOW_SAMPLE_CONDOS immeubles.
 * Limite assumée : prix AFFICHÉS (pas transactionnels) → classement relatif.
 */
import type { Listing } from "@/lib/types";

/** Seuil de condos appariés (vente+location) pour le rendement within-condo. */
export const MIN_PAIRED_CONDOS = 5;
/** Sous ce nombre de condos distincts, la stat est signalée "échantillon faible". */
export const LOW_SAMPLE_CONDOS = 20;
/** Winsorisation p5–p95 seulement si le groupe a au moins n valeurs. */
const WINSOR_MIN_N = 20;

export type YieldMethod = "within-condo" | "ratio";

export interface YieldRow {
  khet: string;
  nSale: number; // annonces vente
  nRent: number; // annonces location
  nSaleCondos: number; // condos distincts côté vente (1 condo = 1 voix)
  nRentCondos: number;
  nPairedCondos: number; // condos avec vente ET location
  saleMedianPsqm: number | null; // médiane des médianes-condo
  rentMedianPsqm: number | null;
  grossYieldPct: number | null;
  yieldMethod: YieldMethod | null;
  lowSample: boolean;
}

export interface StreetYieldRow extends Omit<YieldRow, "khet"> {
  street: string;
}

/** Strates de chambres : le 0–1BR est le segment commun/liquide du marché BKK
 *  (comparer les quartiers à panier constant, sans biais de mix penthouse). */
export type BedStratum = "0-1" | "2" | "3+" | "all";
export const BED_STRATA: BedStratum[] = ["0-1", "2", "3+", "all"];

export function matchBedStratum(beds: number | null, s: BedStratum): boolean {
  if (s === "all") return true;
  if (beds == null) return false;
  if (s === "0-1") return beds <= 1;
  if (s === "2") return beds === 2;
  return beds >= 3;
}

/**
 * Moyenne des `n` biens médians : on trie, on prend les ~`n` valeurs centrées sur
 * la médiane et on les moyenne. Plus robuste qu'un seul point médian (lisse un
 * médian isolé) tout en restant insensible aux extrêmes. `<n` valeurs → moyenne
 * de ce qu'on a ; 0 valeur → null. (Conservé pour lib/deals.ts.)
 */
export function medianAvg(vals: number[], n = 3): number | null {
  const f = vals.filter((v) => Number.isFinite(v) && v > 0).sort((a, b) => a - b);
  if (!f.length) return null;
  const mid = Math.floor(f.length / 2);
  const start = Math.max(0, Math.min(mid - Math.floor(n / 2), f.length - n));
  const win = f.slice(start, start + n);
  return win.reduce((s, x) => s + x, 0) / win.length;
}

function median(vals: number[]): number | null {
  const f = vals.filter((v) => Number.isFinite(v) && v > 0).sort((a, b) => a - b);
  if (!f.length) return null;
  const mid = Math.floor(f.length / 2);
  return f.length % 2 ? f[mid] : (f[mid - 1] + f[mid]) / 2;
}

/** Écrête aux percentiles 5/95 du groupe (si n ≥ WINSOR_MIN_N) : les annonces
 *  aberrantes restent comptées mais ne tirent plus les médianes de condo. */
function winsorize(vals: number[]): number[] {
  if (vals.length < WINSOR_MIN_N) return vals;
  const sorted = [...vals].sort((a, b) => a - b);
  const q = (p: number) => sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))];
  const lo = q(0.05);
  const hi = q(0.95);
  return vals.map((v) => Math.min(hi, Math.max(lo, v)));
}

/** Même normalisation de nom de condo que lib/cross-match.ts. */
function normCondo(name: string | null): string {
  if (!name) return "";
  return name
    .split(",")[0]
    .toLowerCase()
    .replace(/[^a-z0-9 ]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

/** Médiane de prix/m² par condo. Une annonce sans nom de condo compte comme son
 *  propre "immeuble" (1 voix), plutôt que d'être jetée. */
function condoMedians(listings: Listing[]): Map<string, number> {
  const vals = listings.map((l) => l.pricePerSqm!).filter((v) => v > 0);
  const clamped = winsorize(vals);
  const byCondo = new Map<string, number[]>();
  let i = 0;
  for (const l of listings) {
    if (!(l.pricePerSqm! > 0)) continue;
    const key = normCondo(l.condoName) || `#${l.id}`;
    (byCondo.get(key) ?? byCondo.set(key, []).get(key)!).push(clamped[i]);
    i++;
  }
  const out = new Map<string, number>();
  for (const [k, v] of byCondo) {
    const m = median(v);
    if (m != null) out.set(k, m);
  }
  return out;
}

/** Agrège un groupe d'annonces (un quartier, une rue) selon la méthode v2. */
function aggregate(arr: Listing[]): Omit<YieldRow, "khet"> {
  const sale = arr.filter((l) => l.dealType === "sale" && (l.pricePerSqm ?? 0) > 0);
  const rent = arr.filter((l) => l.dealType === "rent" && (l.pricePerSqm ?? 0) > 0);

  const saleByCondo = condoMedians(sale);
  const rentByCondo = condoMedians(rent);

  const saleMedianPsqm = median([...saleByCondo.values()]);
  const rentMedianPsqm = median([...rentByCondo.values()]);

  // rendements within-condo : uniquement les immeubles présents des deux côtés
  const pairedYields: number[] = [];
  for (const [condo, saleMed] of saleByCondo) {
    const rentMed = rentByCondo.get(condo);
    if (rentMed != null && condo.charAt(0) !== "#") {
      pairedYields.push((rentMed * 12) / saleMed * 100);
    }
  }

  let grossYieldPct: number | null = null;
  let yieldMethod: YieldMethod | null = null;
  if (pairedYields.length >= MIN_PAIRED_CONDOS) {
    grossYieldPct = median(pairedYields);
    yieldMethod = "within-condo";
  } else if (saleMedianPsqm && rentMedianPsqm) {
    grossYieldPct = (rentMedianPsqm * 12) / saleMedianPsqm * 100;
    yieldMethod = "ratio";
  }

  return {
    nSale: sale.length,
    nRent: rent.length,
    nSaleCondos: saleByCondo.size,
    nRentCondos: rentByCondo.size,
    nPairedCondos: pairedYields.length,
    saleMedianPsqm,
    rentMedianPsqm,
    grossYieldPct: grossYieldPct == null ? null : Math.round(grossYieldPct * 10) / 10,
    yieldMethod,
    lowSample: saleByCondo.size < LOW_SAMPLE_CONDOS || rentByCondo.size < LOW_SAMPLE_CONDOS,
  };
}

export function computeYieldsByKhet(
  listings: Listing[],
  stratum: BedStratum = "all"
): YieldRow[] {
  const byKhet = new Map<string, Listing[]>();
  for (const l of listings) {
    if (!l.khet || !matchBedStratum(l.bedrooms, stratum)) continue;
    (byKhet.get(l.khet) ?? byKhet.set(l.khet, []).get(l.khet)!).push(l);
  }
  const rows: YieldRow[] = [];
  for (const [khet, arr] of byKhet) rows.push({ khet, ...aggregate(arr) });
  return rows;
}

/** Rendement par rue répertoriée pour un quartier donné (rues non nulles). */
export function computeYieldsByStreet(
  listings: Listing[],
  khet: string,
  stratum: BedStratum = "all"
): StreetYieldRow[] {
  const byStreet = new Map<string, Listing[]>();
  for (const l of listings) {
    if (l.khet !== khet || !l.street || !matchBedStratum(l.bedrooms, stratum)) continue;
    (byStreet.get(l.street) ?? byStreet.set(l.street, []).get(l.street)!).push(l);
  }
  const rows: StreetYieldRow[] = [];
  for (const [street, arr] of byStreet) rows.push({ street, ...aggregate(arr) });
  return rows;
}
