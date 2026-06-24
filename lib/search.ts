/**
 * search.ts — Recherche texte sur les annonces (condo, rue, quartier, adresse).
 * Tokens séparés par espace = ET logique (tous présents). Insensible à la casse.
 * Ex. "sukhumvit 33" → annonces dont le texte contient "sukhumvit" ET "33".
 */
import type { Listing } from "@/lib/types";

export function searchListings(listings: Listing[], q: string): Listing[] {
  const tokens = q.toLowerCase().split(/\s+/).filter(Boolean);
  if (!tokens.length) return [];
  return listings.filter((l) => {
    const blob = [l.condoName, l.title, l.street, l.khet, l.khwaeng, l.addressRaw]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return tokens.every((t) => blob.includes(t));
  });
}
