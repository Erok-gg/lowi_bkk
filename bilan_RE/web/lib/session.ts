/**
 * session.ts — le pont entre les cookies Next et la base des comptes.
 *
 * Séparé de `comptes.ts` à dessein : `comptes.ts` ne connaît que SQLite et peut
 * être testé sans Next (voir bilan_RE/tests/test_comptes.ts), ce fichier-ci est
 * le seul à toucher à `next/headers`.
 */
import "server-only";
import { cookies } from "next/headers";
import {
  COOKIE_SESSION,
  COOKIE_VISITEUR,
  JOURS_SESSION,
  compteDeSession,
  disponibleComptes,
  fermeSession,
  ouvreSession,
  type Compte,
} from "./comptes";

/** Le compte connecté, ou null. Ne lève jamais : une base absente (Vercel, où
 *  la beta ne tourne pas) doit donner « non connecté », pas une page en erreur. */
export async function compteCourant(): Promise<Compte | null> {
  try {
    if (!disponibleComptes()) return null;
    const c = await cookies();
    return compteDeSession(c.get(COOKIE_SESSION)?.value);
  } catch {
    return null;
  }
}

/** Options du cookie de session. `secure` seulement en production : en dev le
 *  serveur est en http, et un cookie `secure` y serait jeté en silence. */
export function optionsCookie(expire: Date) {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    expires: expire,
    maxAge: JOURS_SESSION * 86400,
  };
}

/** Pose la session sur une réponse de route API. */
export function poseSession(res: { cookies: { set: (n: string, v: string, o: object) => void } }, compteId: string) {
  const { jeton, expire } = ouvreSession(compteId);
  res.cookies.set(COOKIE_SESSION, jeton, optionsCookie(expire));
}

export function retireSession(
  res: { cookies: { set: (n: string, v: string, o: object) => void } },
  jetonBrut: string | undefined,
) {
  fermeSession(jetonBrut);
  res.cookies.set(COOKIE_SESSION, "", { ...optionsCookie(new Date(0)), maxAge: 0 });
}

export { COOKIE_SESSION, COOKIE_VISITEUR };
