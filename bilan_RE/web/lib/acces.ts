/**
 * acces.ts — qui peut voir les pages du produit.
 *
 * Deux portes distinctes, à ne pas confondre :
 *   · `lib/auth.ts` (mot de passe partagé) protège l'OUTIL interne — carte,
 *     tableaux, rendements, tension. Inchangé.
 *   · ici : les pages `/beta…` (landing, bilan, comptes) peuvent être ouvertes
 *     au public, mais seulement si `LOWI_BETA_PUBLIQUE=1` est posé. Sans la
 *     variable, rien ne change : le mot de passe partagé s'applique comme
 *     avant. Ouvrir au public reste une décision explicite, et l'interrupteur
 *     est aussi le chemin du retour (règle 7 : savoir défaire).
 */
import "server-only";
import { isAuthed } from "@/lib/auth";

export function betaPublique(): boolean {
  return process.env.LOWI_BETA_PUBLIQUE === "1";
}

/** Vrai si la page du produit peut être servie à ce visiteur. */
export async function accesProduit(): Promise<boolean> {
  return betaPublique() || (await isAuthed());
}
