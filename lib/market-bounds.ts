/**
 * market-bounds.ts — BORNES DE PLAUSIBILITÉ, source unique.
 *
 * POURQUOI CE FICHIER. Les mêmes bornes existaient en trois exemplaires sans se
 * connaître : `SALE_MIN/SALE_MAX` dans lib/deals.ts, `MIN_PRICE/MAX_PRICE`
 * redéclarés dans app/for-sale/page.tsx, et rien du tout en SQL. Conséquence
 * mesurée le 2026-07-28 : les 114 annonces au-dessus de 100 M et les 68
 * en dessous de 800 k étaient exclues du tableau de vente, mais comptaient
 * toujours dans la carte, dans les rendements et dans la tension. La vue
 * `opportunites` n'en savait rien non plus, et affichait en tête de liste des
 * LOCATIONS mal classées en vente (NOBLE STATE 39 : 27 000 THB pour 35 m²,
 * soit un écart de −100 % qui n'est qu'un défaut de source).
 *
 * Un bien hors bornes n'est pas « pas cher » : c'est une donnée à écarter. Le
 * pendant SQL de ce fichier est la vue `listings_sane`
 * (supabase/migrations/plausibilite.sql) — les deux DOIVENT rester alignés,
 * c'est pourquoi les valeurs sont commentées des deux côtés.
 *
 * Ces bornes filtrent les statistiques, elles ne suppriment rien : l'annonce
 * reste en base, et une anomalie de source reste consultable.
 */
import type { Listing } from "@/lib/types";

/** Prix de vente plausible pour un condo à Bangkok (THB).
 *  Sous 800 k : quasi toujours un loyer mal classé en vente, ou un prix « à
 *  partir de » tronqué. Au-dessus de 100 M : penthouses et villas hors marché
 *  comparable, qui écrasent toutes les médianes de leur quartier. */
export const SALE_MIN = 800_000;
export const SALE_MAX = 100_000_000;

/** Loyer mensuel plausible (THB). Sous 3 000, c'est un prix journalier ou une
 *  chambre en colocation ; au-dessus de 500 000, une villa ou une erreur de
 *  saisie (prix de vente placé dans le champ loyer). */
export const RENT_MIN = 3_000;
export const RENT_MAX = 500_000;

/** Surface plausible (m²). Le plancher écarte les saisies en `wah²` et les
 *  zéros ; le plafond écarte les surfaces de PROJET saisies dans le champ du
 *  lot (relevé : un 1BR annoncé à 3 757 m² au Tempo Ruamrudee). */
export const AREA_MIN = 15;
export const AREA_MAX = 500;

/** Le prix de l'annonce est-il dans la fourchette plausible de son deal_type ? */
export function priceInRange(dealType: Listing["dealType"], price: number | null): boolean {
  if (!price) return false;
  return dealType === "sale"
    ? price >= SALE_MIN && price <= SALE_MAX
    : price >= RENT_MIN && price <= RENT_MAX;
}

/** Surface plausible, ou inconnue (une surface absente n'est pas une aberration :
 *  elle prive juste l'annonce des statistiques au m²). */
export function areaPlausible(areaSqm: number | null): boolean {
  return areaSqm == null || (areaSqm >= AREA_MIN && areaSqm <= AREA_MAX);
}

/**
 * L'annonce peut-elle entrer dans une STATISTIQUE (médiane, décote, tension) ?
 * C'est le seul prédicat que les agrégats doivent utiliser — ne pas refiltrer
 * à la main ailleurs, sinon on recrée la divergence que ce fichier supprime.
 */
export function isPlausible(l: Pick<Listing, "dealType" | "price" | "areaSqm">): boolean {
  return priceInRange(l.dealType, l.price) && areaPlausible(l.areaSqm);
}

/** Écarte les aberrations d'une liste d'annonces. */
export function keepPlausible<T extends Pick<Listing, "dealType" | "price" | "areaSqm">>(
  listings: T[]
): T[] {
  return listings.filter(isPlausible);
}
