/**
 * condo-name.ts — Normalisation du nom d'immeuble, source unique côté TypeScript.
 *
 * POURQUOI. Le même immeuble s'écrit « The Base Sukhumvit 77 », « The Base
 * Sukhumvit 77, Bangkok » ou « the base sukhumvit 77 » selon la source. Tout
 * regroupement par immeuble — double médiane de lib/yields.ts, recoupement
 * vente/location de lib/cross-match.ts, pression vendeuse de lib/tension.ts —
 * dépend donc d'une normalisation, et surtout de LA MÊME.
 *
 * Cette fonction existait en double, à l'identique, dans yields.ts et
 * cross-match.ts ; tension.ts, lui, comparait les noms bruts et comptait donc
 * deux immeubles là où il n'y en avait qu'un. Un seul exemplaire désormais.
 *
 * ⚠ DIVERGENCE CONNUE avec `_norm_condo` de scraper/pipeline/normalize.py, qui
 * retire en plus les mots vides (bangkok / condo / project / residence) et
 * conserve les caractères thaïs. Les deux ne produisent donc pas toujours la
 * même clé. Ce n'est pas corrigé ici à dessein : aligner les deux déplacerait
 * toutes les médianes déjà publiées, et cela mérite sa propre décision datée.
 * Conséquence pratique : ne PAS comparer un regroupement TS à un `unit_key`.
 */

/** Minuscules, suffixe après virgule retiré (« , Bangkok »), alphanumérique. */
export function normalizeCondoName(name: string | null | undefined): string {
  if (!name) return "";
  return name
    .split(",")[0]
    .toLowerCase()
    .replace(/[^a-z0-9 ]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}
