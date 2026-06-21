/**
 * auth.ts — Gate par mot de passe partagé (cookie, runtime Node).
 * Évite le middleware Edge (incompatible Vercel ici). Vérifié dans les pages
 * (server components) et les routes API.
 * Mot de passe : env BASIC_AUTH_PASSWORD. Non défini → accès ouvert (dev).
 */
import "server-only";
import { cookies } from "next/headers";
import { createHash } from "node:crypto";

export const AUTH_COOKIE = "lowi_auth";

export function tokenFor(password: string): string {
  return createHash("sha256").update(password).digest("hex");
}

/** Token attendu (hash du mot de passe configuré), ou null si pas de gate. */
export function expectedToken(): string | null {
  const pw = process.env.BASIC_AUTH_PASSWORD;
  return pw ? tokenFor(pw) : null;
}

export async function isAuthed(): Promise<boolean> {
  const exp = expectedToken();
  if (!exp) return true; // pas de mot de passe configuré → ouvert
  const store = await cookies();
  return store.get(AUTH_COOKIE)?.value === exp;
}
