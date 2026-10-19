/** POST /api/langue — { langue } : mémorise la langue choisie (cookie 1 an). */
import { NextResponse } from "next/server";
import { COOKIE_LANGUE } from "@/bilan_RE/web/lib/langue";
import { LANGUES, langueValide } from "@/bilan_RE/web/i18n";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const { langue } = (await req.json().catch(() => ({}))) as { langue?: string };
  if (!langue || !(LANGUES as readonly string[]).includes(langue))
    return NextResponse.json({ erreur: "bad_language" }, { status: 400 });

  const res = NextResponse.json({ ok: true, langue: langueValide(langue) });
  // Nécessaire au fonctionnement (préférence d'affichage) : pas de consentement
  // à demander pour celui-ci, et pas httpOnly — aucun intérêt à le cacher.
  res.cookies.set(COOKIE_LANGUE, langue, { httpOnly: false, sameSite: "lax", path: "/", maxAge: 365 * 86400 });
  return res;
}
