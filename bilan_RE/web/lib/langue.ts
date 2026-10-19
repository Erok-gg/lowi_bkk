/**
 * langue.ts — quelle langue sert-on, côté serveur.
 *
 * Ordre : cookie posé par le sélecteur → en-tête Accept-Language du navigateur
 * → anglais. Le choix explicite passe donc toujours devant la devinette.
 */
import "server-only";
import { cookies, headers } from "next/headers";
import { langueDepuisEntete, langueValide, traducteur, type Langue, type T } from "../i18n";

export const COOKIE_LANGUE = "lowi_lang";

export async function langueCourante(): Promise<Langue> {
  try {
    const c = await cookies();
    const choisie = c.get(COOKIE_LANGUE)?.value;
    if (choisie) return langueValide(choisie);
    const h = await headers();
    return langueDepuisEntete(h.get("accept-language")) ?? "en";
  } catch {
    return "en";
  }
}

/** `const { langue, t } = await i18n()` dans un server component. */
export async function i18n(): Promise<{ langue: Langue; t: T }> {
  const langue = await langueCourante();
  return { langue, t: traducteur(langue) };
}
