/**
 * tension.ts — Indice de TENSION du marché par quartier, calculé à partir des
 * scraps successifs (dimension temporelle des annonces + snapshots).
 *
 * Indice composite 0–100 (plus haut = plus tendu), combinant 4 signaux normalisés
 * par RANG CENTILE cross-quartiers (robuste aux unités/extrêmes) :
 *   - Absorption  : vitesse d'écoulement (time-on-market des annonces disparues,
 *                   sinon âge des annonces actives). Court = tendu.
 *   - Rareté      : peu d'annonces actives = tendu.
 *   - Tendance stock : pente du nb d'actives (khet_snapshots). En baisse = tendu.
 *   - Momentum prix  : pente du prix/m² (khet_snapshots). En hausse = tendu.
 *
 * Les composantes de TENDANCE nécessitent de l'historique : tant qu'il n'y a pas
 * assez de snapshots, elles valent null et leur poids est redistribué (dégradation
 * gracieuse). Une CONFIANCE par quartier reflète la taille d'échantillon.
 *
 * Indépendant du backend (mêmes données, que la source soit Supabase ou SQLite).
 */
import type { DealType, ListingStatus } from "@/lib/types";
import { medianAvg } from "@/lib/yields";

/* ───────────────────────────── entrées (DB) ───────────────────────────── */

/** Une annonce réduite à sa dimension temporelle (actives + disparues). */
export interface TensionInput {
  khet: string | null;
  street: string | null;
  dealType: DealType;
  status: ListingStatus;
  firstSeen: string | null; // ISO
  delistedAt: string | null; // ISO (date de passage inactive/sold)
}

/** Une ligne de khet_snapshots (série temporelle par quartier × deal_type). */
export interface KhetSnapshot {
  takenAt: string; // ISO
  khet: string;
  dealType: DealType | null; // null = snapshots hérités (avant séparation vente/loc)
  activeCount: number | null;
  avgPricePerSqm: number | null;
}

/* ───────────────────────────── sorties ───────────────────────────── */

export type Confidence = "high" | "medium" | "low";

export interface TensionRow {
  khet: string;
  dealType: DealType;
  nActive: number;
  nDelisted: number;
  medianAgeDays: number | null;
  medianTomDays: number | null; // time-on-market des disparues (si assez d'historique)
  stockTrend: number | null; // pente du nb d'actives/jour (négatif = stock baisse)
  priceMomentum: number | null; // pente du prix/m²/jour
  tensionScore: number | null; // 0–100
  confidence: Confidence;
}

export interface TensionStreetRow {
  street: string;
  dealType: DealType;
  nActive: number;
  nDelisted: number;
  medianAgeDays: number | null;
  medianTomDays: number | null;
  tensionScore: number | null;
  confidence: Confidence;
}

/* ───────────────────────────── réglages (tunables) ───────────────────────────── */

/** Poids des composantes (modulaire — réglable sans toucher au cœur). */
export const WEIGHTS = {
  absorption: 40,
  scarcity: 15,
  stockTrend: 20,
  priceMomentum: 25,
} as const;

const MIN_DELISTINGS = 3; // disparitions mini pour un time-on-market fiable
const MIN_SNAPSHOTS = 3; // points mini pour une pente fiable
const DAY = 86_400_000;

/* ───────────────────────────── helpers ───────────────────────────── */

const days = (fromIso: string, toMs: number): number | null => {
  const t = Date.parse(fromIso);
  return Number.isFinite(t) ? (toMs - t) / DAY : null;
};

/**
 * Rang centile (0–100) de chaque valeur au sein de l'ensemble (les `null` restent
 * `null`). Un seul point défini → 50 (neutre). O(n²) assumé (n ≈ 50 quartiers).
 */
function percentileRanks(values: (number | null)[]): (number | null)[] {
  const defined = values.filter((v): v is number => v != null);
  if (defined.length <= 1) return values.map((v) => (v == null ? null : 50));
  return values.map((v) => {
    if (v == null) return null;
    let below = 0;
    let equal = 0;
    for (const d of defined) {
      if (d < v) below++;
      else if (d === v) equal++;
    }
    return ((below + 0.5 * equal) / defined.length) * 100;
  });
}

/** Pente d'une régression linéaire simple (y sur x). null si trop peu de points. */
function slope(points: { x: number; y: number }[]): number | null {
  const pts = points.filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
  if (pts.length < MIN_SNAPSHOTS) return null;
  const n = pts.length;
  let sx = 0, sy = 0, sxx = 0, sxy = 0;
  for (const p of pts) {
    sx += p.x; sy += p.y; sxx += p.x * p.x; sxy += p.x * p.y;
  }
  const denom = n * sxx - sx * sx;
  if (denom === 0) return null;
  return (n * sxy - sx * sy) / denom;
}

function confidenceOf(nActive: number, nDelisted: number, nSnap: number): Confidence {
  if (nActive < 3) return "low";
  if (nActive >= 8 && (nDelisted >= MIN_DELISTINGS || nSnap >= MIN_SNAPSHOTS + 1)) return "high";
  return "medium";
}

/** Combine des scores (0–100) pondérés ; redistribue le poids des composantes absentes. */
function combine(parts: { score: number | null; weight: number }[]): number | null {
  let wsum = 0;
  let acc = 0;
  for (const p of parts) {
    if (p.score == null) continue;
    acc += p.score * p.weight;
    wsum += p.weight;
  }
  return wsum === 0 ? null : Math.round(acc / wsum);
}

/* ───────────────────────── agrégat intermédiaire par quartier ───────────────────────── */

interface Raw {
  key: string;
  nActive: number;
  nDelisted: number;
  medianAgeDays: number | null;
  medianTomDays: number | null;
  absorptionDays: number | null; // TOM si fiable, sinon âge médian
  stockTrend: number | null;
  priceMomentum: number | null;
  nSnap: number;
}

/** Construit les métriques brutes d'un groupe (quartier ou rue) à une date `nowMs`. */
function rawOf(key: string, arr: TensionInput[], snaps: KhetSnapshot[], nowMs: number): Raw {
  const actives = arr.filter((l) => l.status === "active");
  const ages = actives
    .map((l) => (l.firstSeen ? days(l.firstSeen, nowMs) : null))
    .filter((v): v is number => v != null && v >= 0);
  const delisted = arr.filter(
    (l) => l.status !== "active" && l.firstSeen && l.delistedAt
  );
  const toms = delisted
    .map((l) => {
      const end = Date.parse(l.delistedAt as string);
      return l.firstSeen && Number.isFinite(end) ? days(l.firstSeen, end) : null;
    })
    .filter((v): v is number => v != null && v >= 0);

  const medianAgeDays = medianAvg(ages, 3);
  const medianTomDays = toms.length >= MIN_DELISTINGS ? medianAvg(toms, 3) : null;

  // pentes (sur snapshots du deal_type courant uniquement)
  const t0 = snaps.length ? Math.min(...snaps.map((s) => Date.parse(s.takenAt))) : 0;
  const stockPts = snaps
    .filter((s) => s.activeCount != null)
    .map((s) => ({ x: (Date.parse(s.takenAt) - t0) / DAY, y: s.activeCount as number }));
  const pricePts = snaps
    .filter((s) => s.avgPricePerSqm != null)
    .map((s) => ({ x: (Date.parse(s.takenAt) - t0) / DAY, y: s.avgPricePerSqm as number }));

  return {
    key,
    nActive: actives.length,
    nDelisted: delisted.length,
    medianAgeDays,
    medianTomDays,
    absorptionDays: medianTomDays ?? medianAgeDays,
    stockTrend: slope(stockPts),
    priceMomentum: slope(pricePts),
    nSnap: snaps.length,
  };
}

/* ───────────────────────────── API publique ───────────────────────────── */

/**
 * Tension par quartier pour un deal_type donné. Les snapshots sont filtrés sur ce
 * deal_type (les snapshots hérités `dealType=null` sont ignorés pour ne pas mélanger
 * vente et location).
 */
export function computeTensionByKhet(
  inputs: TensionInput[],
  snapshots: KhetSnapshot[],
  dealType: DealType,
  now: number = Date.now()
): TensionRow[] {
  const byKhet = new Map<string, TensionInput[]>();
  for (const l of inputs) {
    if (!l.khet || l.dealType !== dealType) continue;
    const arr = byKhet.get(l.khet) ?? [];
    arr.push(l);
    byKhet.set(l.khet, arr);
  }
  const snapByKhet = new Map<string, KhetSnapshot[]>();
  for (const s of snapshots) {
    if (s.dealType !== dealType) continue;
    const arr = snapByKhet.get(s.khet) ?? [];
    arr.push(s);
    snapByKhet.set(s.khet, arr);
  }

  const raws: Raw[] = [];
  for (const [khet, arr] of byKhet) {
    raws.push(rawOf(khet, arr, snapByKhet.get(khet) ?? [], now));
  }

  // normalisation cross-quartiers (rang centile)
  const absRank = percentileRanks(raws.map((r) => r.absorptionDays));
  const scaRank = percentileRanks(raws.map((r) => r.nActive));
  const stkRank = percentileRanks(raws.map((r) => r.stockTrend));
  const momRank = percentileRanks(raws.map((r) => r.priceMomentum));

  return raws.map((r, i) => {
    // tendu = absorption courte / peu de stock / stock en baisse / prix en hausse
    const absScore = absRank[i] == null ? null : 100 - (absRank[i] as number);
    const scaScore = scaRank[i] == null ? null : 100 - (scaRank[i] as number);
    const stkScore = stkRank[i] == null ? null : 100 - (stkRank[i] as number);
    const momScore = momRank[i];
    const tensionScore = combine([
      { score: absScore, weight: WEIGHTS.absorption },
      { score: scaScore, weight: WEIGHTS.scarcity },
      { score: stkScore, weight: WEIGHTS.stockTrend },
      { score: momScore, weight: WEIGHTS.priceMomentum },
    ]);
    return {
      khet: r.key,
      dealType,
      nActive: r.nActive,
      nDelisted: r.nDelisted,
      medianAgeDays: r.medianAgeDays == null ? null : Math.round(r.medianAgeDays),
      medianTomDays: r.medianTomDays == null ? null : Math.round(r.medianTomDays),
      stockTrend: r.stockTrend,
      priceMomentum: r.priceMomentum,
      tensionScore,
      confidence: confidenceOf(r.nActive, r.nDelisted, r.nSnap),
    };
  });
}

/**
 * Tension par rue répertoriée d'un quartier (rues non nulles). Uniquement les
 * composantes per-listing (absorption + rareté) : pas de snapshots à l'échelle rue.
 * Normalisation au sein du quartier.
 */
export function computeTensionByStreet(
  inputs: TensionInput[],
  khet: string,
  dealType: DealType,
  now: number = Date.now()
): TensionStreetRow[] {
  const byStreet = new Map<string, TensionInput[]>();
  for (const l of inputs) {
    if (l.khet !== khet || l.dealType !== dealType || !l.street) continue;
    const arr = byStreet.get(l.street) ?? [];
    arr.push(l);
    byStreet.set(l.street, arr);
  }

  const raws: Raw[] = [];
  for (const [street, arr] of byStreet) raws.push(rawOf(street, arr, [], now));

  const absRank = percentileRanks(raws.map((r) => r.absorptionDays));
  const scaRank = percentileRanks(raws.map((r) => r.nActive));

  // poids restreints aux 2 composantes per-listing
  return raws.map((r, i) => {
    const absScore = absRank[i] == null ? null : 100 - (absRank[i] as number);
    const scaScore = scaRank[i] == null ? null : 100 - (scaRank[i] as number);
    const tensionScore = combine([
      { score: absScore, weight: WEIGHTS.absorption },
      { score: scaScore, weight: WEIGHTS.scarcity },
    ]);
    return {
      street: r.key,
      dealType,
      nActive: r.nActive,
      nDelisted: r.nDelisted,
      medianAgeDays: r.medianAgeDays == null ? null : Math.round(r.medianAgeDays),
      medianTomDays: r.medianTomDays == null ? null : Math.round(r.medianTomDays),
      tensionScore,
      confidence: confidenceOf(r.nActive, r.nDelisted, 0),
    };
  });
}
