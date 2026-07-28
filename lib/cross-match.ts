/**
 * cross-match.ts — Rapproche la MÊME UNITÉ entre vente et location.
 * But : sur une annonce vente, afficher le loyer mensuel d'une location du même
 * appartement (et inversement), + le rendement annuel réel sur ces deux chiffres.
 *
 * Unité = même condo (nom normalisé) + même quartier + même nb de chambres,
 * avec surface à ±7 % quand les deux surfaces sont connues. Pas de fusion :
 * on ne fait qu'associer une contrepartie probable.
 */
import type { Listing } from "@/lib/types";
import { normalizeCondoName as normCondo } from "@/lib/condo-name";

export interface UnitMatch {
  counterpart: Listing; // l'annonce de l'autre deal_type
  annualYieldPct: number; // loyer mensuel × 12 / prix de vente × 100
}

/** Ce que le tableau affiche réellement de la contrepartie : son prix et le
 *  rendement. Suffisant côté client, et évite d'expédier au navigateur les
 *  16 000 annonces dont seuls ces deux nombres étaient tirés. */
export interface UnitMatchLite {
  counterpartPrice: number;
  annualYieldPct: number;
}

const AREA_TOL = 0.07;

const unitKey = (l: Listing) => `${normCondo(l.condoName)}|${l.khet ?? ""}|${l.bedrooms ?? "?"}`;

/** true si les deux annonces désignent plausiblement la même unité. */
function sameUnit(a: Listing, b: Listing): boolean {
  if (a.areaSqm && b.areaSqm) {
    const diff = Math.abs(a.areaSqm - b.areaSqm) / Math.max(a.areaSqm, b.areaSqm);
    return diff <= AREA_TOL;
  }
  return true; // surface inconnue d'un côté → on s'en tient au condo+khet+chambres
}

/**
 * Construit, pour chaque annonce, la contrepartie la plus proche de l'autre
 * deal_type (par surface), et le rendement annuel associé.
 */
export function buildUnitMatches(listings: Listing[]): Map<string, UnitMatch> {
  const groups = new Map<string, Listing[]>();
  for (const l of listings) {
    if (!l.condoName) continue;
    const k = unitKey(l);
    const arr = groups.get(k) ?? [];
    arr.push(l);
    groups.set(k, arr);
  }

  const out = new Map<string, UnitMatch>();
  const closest = (l: Listing, candidates: Listing[]): Listing | null => {
    const ok = candidates.filter((c) => sameUnit(l, c));
    if (!ok.length) return null;
    if (!l.areaSqm) return ok[0];
    return ok.reduce((best, c) =>
      Math.abs((c.areaSqm ?? Infinity) - l.areaSqm!) <
      Math.abs((best.areaSqm ?? Infinity) - l.areaSqm!)
        ? c
        : best
    );
  };

  for (const arr of groups.values()) {
    const sales = arr.filter((l) => l.dealType === "sale");
    const rents = arr.filter((l) => l.dealType === "rent");
    if (!sales.length || !rents.length) continue;

    for (const l of arr) {
      const counterpart = closest(l, l.dealType === "sale" ? rents : sales);
      if (!counterpart) continue;
      const salePrice = l.dealType === "sale" ? l.price : counterpart.price;
      const monthlyRent = l.dealType === "rent" ? l.price : counterpart.price;
      if (!salePrice || !monthlyRent) continue;
      out.set(l.id, {
        counterpart,
        annualYieldPct: Math.round(((monthlyRent * 12) / salePrice) * 1000) / 10,
      });
    }
  }
  return out;
}

/**
 * Version allégée, destinée à être calculée SUR LE SERVEUR puis sérialisée.
 *
 * Le tableau ne tire de la contrepartie que son prix et le rendement, mais
 * `buildUnitMatches` a besoin de l'ensemble vente + location pour l'apparier.
 * Faire tourner l'appariement côté client obligeait donc à expédier au
 * navigateur les 16 000 annonces actives — l'essentiel des 19,6 Mo que pesait
 * /for-sale. On apparie côté serveur et on n'envoie que ces deux nombres.
 */
export function buildUnitMatchesLite(
  listings: Listing[],
  pourIds?: Set<string>
): Record<string, UnitMatchLite> {
  const out: Record<string, UnitMatchLite> = {};
  for (const [id, m] of buildUnitMatches(listings)) {
    if (pourIds && !pourIds.has(id)) continue; // seulement les lignes affichées
    if (!m.counterpart.price) continue;
    out[id] = {
      counterpartPrice: m.counterpart.price,
      annualYieldPct: m.annualYieldPct,
    };
  }
  return out;
}
