/**
 * tension.ts — Indice de TENSION du marché par quartier, calculé à partir des
 * scraps successifs (dimension temporelle des annonces + snapshots).
 *
 * Indice composite 0–100 (plus haut = plus tendu), combinant 4 signaux normalisés
 * par RANG CENTILE cross-quartiers (robuste aux unités/extrêmes) :
 *   - Absorption      : vitesse d'écoulement (time-on-market des disparues,
 *                       sinon âge des actives). Court = tendu.
 *   - Pression vendeuse : annonces actives PAR IMMEUBLE. Beaucoup de vendeurs
 *                       simultanés dans un même immeuble = marché mou.
 *   - Tendance stock  : pente du nb d'actives (khet_snapshots). En baisse = tendu.
 *   - Momentum prix   : pente du prix/m² (khet_snapshots). En hausse = tendu.
 *
 * ── RÉVISION DU 2026-07-28 ───────────────────────────────────────────────────
 * La composante « rareté » valait `100 − rang(nombre d'annonces actives)` :
 * PEU D'ANNONCES = TENDU, par construction. Or 25 des 55 quartiers ont moins de
 * 20 annonces actives et obtenaient donc mécaniquement le score maximal. La
 * périphérie ressortait plus tendue que le centre alors qu'elle n'a tout
 * simplement presque pas de condos (Taling Chan : 2 annonces sur 6 immeubles).
 * Le compte brut confondait TAILLE du marché et TENSION.
 *
 * Elle est remplacée par la PRESSION VENDEUSE = actives / nombre d'immeubles du
 * quartier, insensible à la taille du marché et interprétable : 9,6 annonces par
 * immeuble à Bangkok Yai, ce sont des vendeurs en concurrence, donc un marché
 * mou. Le dénominateur vient du référentiel `condos`.
 *
 * Deux garde-fous ajoutés :
 *   - RÉTRÉCISSEMENT des petits échantillons vers la médiane du marché
 *     (poids n/(n+K)) : un quartier à 5 annonces ne flotte plus librement.
 *   - SEUIL DE PUBLICATION : sous MIN_ACTIVE_TO_PUBLISH annonces, le score vaut
 *     null. Mieux vaut « données insuffisantes » qu'un chiffre dénué de sens.
 *
 * L'absorption reste calculée mais son historique est contaminé : jusqu'au
 * correctif du délistage (2026-07-28), une annonce était délistée dès la
 * première absence d'un scan, ce qui produisait un time-on-market égal à la
 * cadence de scan (6,9 j identiques sur des quartiers très différents).
 * Passer `reliableDelistingSince` pour n'utiliser que les disparitions
 * postérieures au correctif.
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
  /** Immeuble — dénominateur de la pression vendeuse. Optionnel : sans lui, la
   *  composante est neutralisée et son poids redistribué. */
  condoName?: string | null;
}

/** Options de calcul (toutes facultatives — comportement inchangé si omises). */
export interface TensionOptions {
  /** Ignore les disparitions antérieures à cette date ISO pour le time-on-market.
   *  À régler sur la date du correctif de délistage : avant, une annonce était
   *  délistée dès sa première absence d'un scan et le TOM valait la cadence de
   *  scan, pas le marché. */
  reliableDelistingSince?: string;
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
  /** Immeubles distincts du quartier — dénominateur de la pression vendeuse. */
  nCondos: number;
  /** Annonces actives par immeuble. Forte valeur = vendeurs en concurrence. */
  supplyPressure: number | null;
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
  absorption: 35,
  /** ex-`scarcity`, redéfinie : actives PAR IMMEUBLE, pas compte brut. */
  supplyPressure: 25,
  stockTrend: 20,
  priceMomentum: 20,
} as const;

const MIN_DELISTINGS = 3; // disparitions mini pour un time-on-market fiable
const MIN_SNAPSHOTS = 3; // points mini pour une pente fiable
const MIN_CONDOS = 3; // immeubles mini pour une pression vendeuse interprétable
const DAY = 86_400_000;

/** Sous ce nombre d'annonces actives, aucun score n'est publié : à 2 ou 3
 *  annonces, la statistique n'a pas de sens et un chiffre serait trompeur.
 *  25 des 55 quartiers tombent dans ce cas — c'est simplement honnête. */
export const MIN_ACTIVE_TO_PUBLISH = 10;

/** Force du rétrécissement des petits échantillons vers la médiane du marché.
 *  Poids propre = n/(n+K) : à n=5 le quartier compte pour 20 %, à n=20 pour 50 %,
 *  à n=100 pour 83 %. Empêche un quartier minuscule de trôner en tête. */
const SHRINK_K = 20;

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
  nCondos: number;
  /** Annonces actives par immeuble : forte valeur = vendeurs en concurrence. */
  supplyPressure: number | null;
  medianAgeDays: number | null;
  medianTomDays: number | null;
  absorptionDays: number | null; // TOM si fiable, sinon âge médian
  stockTrend: number | null;
  priceMomentum: number | null;
  nSnap: number;
}

/** Construit les métriques brutes d'un groupe (quartier ou rue) à une date `nowMs`. */
function rawOf(
  key: string,
  arr: TensionInput[],
  snaps: KhetSnapshot[],
  nowMs: number,
  opts: TensionOptions = {}
): Raw {
  const actives = arr.filter((l) => l.status === "active");
  const ages = actives
    .map((l) => (l.firstSeen ? days(l.firstSeen, nowMs) : null))
    .filter((v): v is number => v != null && v >= 0);

  // Immeubles distincts du groupe — dénominateur de la pression vendeuse.
  const condos = new Set(arr.map((l) => l.condoName).filter((c): c is string => !!c));
  const nCondos = condos.size;
  const supplyPressure = nCondos >= MIN_CONDOS ? actives.length / nCondos : null;

  const sinceMs = opts.reliableDelistingSince
    ? Date.parse(opts.reliableDelistingSince)
    : null;
  const delisted = arr.filter(
    (l) =>
      l.status !== "active" &&
      l.firstSeen &&
      l.delistedAt &&
      // Avant le correctif du délistage, une annonce disparaissait dès sa
      // première absence d'un scan : le TOM mesurait la cadence, pas le marché.
      (sinceMs == null || Date.parse(l.delistedAt) >= sinceMs)
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
    nCondos,
    supplyPressure,
    medianAgeDays,
    medianTomDays,
    absorptionDays: medianTomDays ?? medianAgeDays,
    stockTrend: slope(stockPts),
    priceMomentum: slope(pricePts),
    nSnap: snaps.length,
  };
}

/**
 * Rétrécit un score vers la médiane du marché à proportion de la taille
 * d'échantillon : `(n·score + K·médiane) / (n + K)`.
 *
 * Sans ce traitement, un quartier à 3 annonces produit un score aussi tranché
 * qu'un quartier à 1 500 — alors qu'il n'est que du bruit. Le rétrécissement ne
 * masque pas l'information, il la pondère par sa fiabilité.
 */
function shrink(score: number | null, n: number, marketMedian: number | null): number | null {
  if (score == null) return null;
  if (marketMedian == null) return score;
  return (n * score + SHRINK_K * marketMedian) / (n + SHRINK_K);
}

/** Médiane simple d'une liste de nombres (null si vide). */
function median(values: (number | null)[]): number | null {
  const v = values.filter((x): x is number => x != null).sort((a, b) => a - b);
  if (!v.length) return null;
  const m = v.length >> 1;
  return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
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
  now: number = Date.now(),
  opts: TensionOptions = {}
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
    raws.push(rawOf(khet, arr, snapByKhet.get(khet) ?? [], now, opts));
  }

  // normalisation cross-quartiers (rang centile)
  const absRank = percentileRanks(raws.map((r) => r.absorptionDays));
  // Pression vendeuse : beaucoup d'annonces par immeuble = vendeurs en
  // concurrence = marché MOU. On inverse donc le rang, comme pour l'absorption.
  const supRank = percentileRanks(raws.map((r) => r.supplyPressure));
  const stkRank = percentileRanks(raws.map((r) => r.stockTrend));
  const momRank = percentileRanks(raws.map((r) => r.priceMomentum));

  // Scores bruts, avant rétrécissement — la médiane du marché sert de point
  // d'attraction pour les quartiers à faible échantillon.
  const bruts = raws.map((r, i) => {
    const absScore = absRank[i] == null ? null : 100 - (absRank[i] as number);
    const supScore = supRank[i] == null ? null : 100 - (supRank[i] as number);
    const stkScore = stkRank[i] == null ? null : 100 - (stkRank[i] as number);
    const momScore = momRank[i];
    return combine([
      { score: absScore, weight: WEIGHTS.absorption },
      { score: supScore, weight: WEIGHTS.supplyPressure },
      { score: stkScore, weight: WEIGHTS.stockTrend },
      { score: momScore, weight: WEIGHTS.priceMomentum },
    ]);
  });
  // Médiane calculée sur les seuls quartiers assez fournis pour être crédibles.
  const marketMedian = median(
    bruts.filter((_, i) => raws[i].nActive >= MIN_ACTIVE_TO_PUBLISH)
  );

  return raws.map((r, i) => {
    // Sous le seuil de publication, aucun score : « données insuffisantes »
    // vaut mieux qu'un chiffre que personne ne peut interpréter.
    const tensionScore =
      r.nActive < MIN_ACTIVE_TO_PUBLISH
        ? null
        : (() => {
            const s = shrink(bruts[i], r.nActive, marketMedian);
            return s == null ? null : Math.round(s);
          })();
    return {
      khet: r.key,
      dealType,
      nActive: r.nActive,
      nDelisted: r.nDelisted,
      nCondos: r.nCondos,
      supplyPressure:
        r.supplyPressure == null ? null : Math.round(r.supplyPressure * 100) / 100,
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
  now: number = Date.now(),
  opts: TensionOptions = {}
): TensionStreetRow[] {
  const byStreet = new Map<string, TensionInput[]>();
  for (const l of inputs) {
    if (l.khet !== khet || l.dealType !== dealType || !l.street) continue;
    const arr = byStreet.get(l.street) ?? [];
    arr.push(l);
    byStreet.set(l.street, arr);
  }

  const raws: Raw[] = [];
  for (const [street, arr] of byStreet) raws.push(rawOf(street, arr, [], now, opts));

  const absRank = percentileRanks(raws.map((r) => r.absorptionDays));
  const supRank = percentileRanks(raws.map((r) => r.supplyPressure));

  // poids restreints aux 2 composantes per-listing
  const bruts = raws.map((r, i) => {
    const absScore = absRank[i] == null ? null : 100 - (absRank[i] as number);
    const supScore = supRank[i] == null ? null : 100 - (supRank[i] as number);
    return combine([
      { score: absScore, weight: WEIGHTS.absorption },
      { score: supScore, weight: WEIGHTS.supplyPressure },
    ]);
  });
  // À l'échelle de la rue les effectifs sont plus petits encore : même seuil de
  // publication et même rétrécissement, sinon une rue à 2 annonces trônerait.
  const streetMedian = median(
    bruts.filter((_, i) => raws[i].nActive >= MIN_ACTIVE_TO_PUBLISH)
  );

  return raws.map((r, i) => {
    const tensionScore =
      r.nActive < MIN_ACTIVE_TO_PUBLISH
        ? null
        : (() => {
            const s = shrink(bruts[i], r.nActive, streetMedian);
            return s == null ? null : Math.round(s);
          })();
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
