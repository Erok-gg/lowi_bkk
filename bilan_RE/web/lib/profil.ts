/**
 * profil — ce que la personne a choisi dans les menus de la page d'accueil
 * (« I invest in properties », « I am a foreigner »…), relu côté serveur.
 *
 * Porté par un cookie et non par l'URL du rapport (2026-10-22) : le rapport est
 * partagé par toutes les personnes qui collent la même annonce (identifiant =
 * l'URL), et le lien du PDF, construit à deux endroits, n'a pas à le transporter.
 * Limite connue : c'est le dernier choix fait DANS CE NAVIGATEUR qui vaut pour
 * tous ses rapports. Retour arrière : ne plus passer `profil` à `Report`.
 */
import { cookies } from "next/headers";
import type { Profil } from "./types";

export const COOKIE_PROFIL = "lowi_profil";

export function lireProfil(v: string | undefined): Profil | undefined {
  const [but, nat] = (v ?? "").split("|");
  if (!["invest", "live", "sell"].includes(but) || !["foreigner", "thai"].includes(nat)) return undefined;
  return { but, nat } as Profil;
}

export async function profilCourant(): Promise<Profil | undefined> {
  return lireProfil((await cookies()).get(COOKIE_PROFIL)?.value);
}
