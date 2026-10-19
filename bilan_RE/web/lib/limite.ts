/**
 * limite.ts — plafond simple par adresse, en mémoire du serveur.
 *
 * POURQUOI. Les routes de compte sont les premières pages de ce projet
 * ouvertes sans mot de passe partagé : créer un compte envoie un e-mail, et un
 * script peut en demander mille. Le plafond n'est pas une sécurité forte (la
 * mémoire se perd au redémarrage, comme la file des rapports) ; il coupe
 * l'abus trivial, et c'est tout ce qu'il prétend faire.
 */
import "server-only";

type Seau = { jetons: number; dernier: number };
const G = globalThis as unknown as { __lowiLimite?: Map<string, Seau> };
const SEAUX: Map<string, Seau> = (G.__lowiLimite ??= new Map());

/** Vrai si l'appel est autorisé. `par` = combien d'appels par `fenetreMs`. */
export function autorise(cle: string, par = 10, fenetreMs = 600_000): boolean {
  const n = Date.now();
  const s = SEAUX.get(cle);
  if (!s || n - s.dernier > fenetreMs) {
    SEAUX.set(cle, { jetons: par - 1, dernier: n });
    return true;
  }
  if (s.jetons <= 0) return false;
  s.jetons -= 1;
  return true;
}

/** L'adresse telle que le proxy la donne. Sur PC2 derrière rien, c'est vide :
 *  on retombe sur une clé unique, donc un plafond global — volontaire, mieux
 *  qu'un plafond qui ne s'applique à personne. */
export function adresse(req: Request): string {
  const h = req.headers;
  return (
    h.get("x-forwarded-for")?.split(",")[0].trim() ||
    h.get("x-real-ip") ||
    "inconnue"
  );
}

/** Racine publique du site, pour les liens des e-mails. */
export function racine(req: Request): string {
  if (process.env.NEXT_PUBLIC_SITE_URL) return process.env.NEXT_PUBLIC_SITE_URL.replace(/\/$/, "");
  try {
    const u = new URL(req.url);
    return `${u.protocol}//${u.host}`;
  } catch {
    return "";
  }
}
