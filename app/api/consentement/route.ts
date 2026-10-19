/**
 * POST /api/consentement — { mesure, marketing }
 *
 * Deux écritures, pas une : le COOKIE sert à ne plus afficher le bandeau et à
 * décider ce qu'on charge ; la LIGNE en base est la preuve (quel texte, quelle
 * version, quand). Un consentement sans trace ne se prouve pas.
 *
 * Le cookie de consentement n'est pas httpOnly : la page doit pouvoir le lire
 * pour décider côté navigateur de charger ou non un script de mesure.
 */
import { NextRequest, NextResponse } from "next/server";
import { randomBytes } from "node:crypto";
import {
  COOKIE_CONSENT,
  COOKIE_VISITEUR,
  VERSION_CONSENTEMENT,
  disponibleComptes,
  enregistreConsentement,
} from "@/bilan_RE/web/lib/comptes";
import { compteCourant } from "@/bilan_RE/web/lib/session";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const body = (await req.json().catch(() => ({}))) as { mesure?: boolean; marketing?: boolean };
  const cats = { necessaires: true as const, mesure: Boolean(body.mesure), marketing: Boolean(body.marketing) };

  const res = NextResponse.json({ ok: true, version: VERSION_CONSENTEMENT });
  res.cookies.set(COOKIE_CONSENT, `${VERSION_CONSENTEMENT}:${cats.mesure ? 1 : 0}${cats.marketing ? 1 : 0}`, {
    httpOnly: false,
    sameSite: "lax",
    path: "/",
    maxAge: 180 * 86400, // 6 mois : on redemande ensuite, le consentement n'est pas éternel
  });

  // Identifiant de navigateur, aléatoire, sans lien avec une personne : il ne
  // sert qu'à rattacher la preuve au clic quand il n'y a pas encore de compte.
  let visiteur = req.cookies.get(COOKIE_VISITEUR)?.value;
  if (!visiteur) {
    visiteur = randomBytes(8).toString("hex");
    res.cookies.set(COOKIE_VISITEUR, visiteur, { httpOnly: true, sameSite: "lax", path: "/", maxAge: 180 * 86400 });
  }

  if (disponibleComptes()) {
    const compte = await compteCourant();
    try {
      enregistreConsentement(cats, compte?.id ?? null, visiteur);
    } catch {
      // La preuve manque, le cookie est posé : on ne bloque pas la personne,
      // mais ça doit rester visible — la trace d'erreur part dans les logs Next.
      console.error("[consentement] trace non enregistrée");
    }
  }
  return res;
}
