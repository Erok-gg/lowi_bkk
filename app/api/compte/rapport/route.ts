/**
 * POST /api/compte/rapport — { email, rapportId, consentement, langue? }
 *
 * C'est la porte du rapport complet (demande du 2026-10-19) : on demande
 * l'e-mail, on crée le compte avec ce login et un mot de passe aléatoire, on
 * attache le rapport au compte (il y reste, consultable et téléchargeable) et
 * on envoie deux lettres : le mot de passe et le lien du rapport.
 *
 * ⚠ LE PAIEMENT N'EST PAS BRANCHÉ. `paye` reste à 0 : la colonne et la
 * référence existent, mais rien ne les remplit tant qu'aucun prestataire n'est
 * choisi. Pendant la beta, posséder le rapport suffit donc à l'ouvrir. Le jour
 * où le paiement arrive, c'est son retour qui pose `paye = 1`, et
 * `app/beta/r/[id]/pdf` n'a qu'une ligne à durcir (voir le commentaire là-bas).
 */
import { NextRequest, NextResponse } from "next/server";
import {
  COOKIE_VISITEUR,
  creeCompte,
  disponibleComptes,
  emailPlausible,
  enregistreConsentement,
  lieRapport,
  marqueMailEnvoye,
  trouveParEmail,
} from "@/bilan_RE/web/lib/comptes";
import { compteCourant, poseSession } from "@/bilan_RE/web/lib/session";
import { envoie, lettreMotDePasse, lettreRapport } from "@/bilan_RE/web/lib/mail";
import { accesProduit } from "@/bilan_RE/web/lib/acces";
import { adresse, autorise, racine } from "@/bilan_RE/web/lib/limite";
import { lire } from "@/bilan_RE/web/lib/rapport";
import { langueValide } from "@/bilan_RE/web/i18n";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  // Même porte que les pages : tant que la beta n'est pas ouverte au public,
  // ces routes restent derrière le mot de passe partagé. Sinon on pourrait
  // créer des comptes sur un service encore fermé.
  if (!(await accesProduit())) return NextResponse.json({ erreur: "closed" }, { status: 403 });
  if (!disponibleComptes()) return NextResponse.json({ erreur: "accounts_unavailable" }, { status: 503 });
  if (!autorise(`rapport:${adresse(req)}`, 20)) return NextResponse.json({ erreur: "too_many" }, { status: 429 });

  const body = (await req.json().catch(() => ({}))) as {
    email?: string;
    rapportId?: string;
    consentement?: boolean;
    langue?: string;
    code?: string;
  };
  const id = (body.rapportId ?? "").trim();
  if (!/^[0-9a-f]{16}$/.test(id)) return NextResponse.json({ erreur: "bad_report" }, { status: 400 });

  const langue = langueValide(body.langue);
  // Déjà connecté : on ne redemande pas l'e-mail.
  const deja = await compteCourant();
  const email = deja ? deja.email : (body.email ?? "").trim();
  if (!deja) {
    if (!emailPlausible(email)) return NextResponse.json({ erreur: "bad_email" }, { status: 400 });
    if (!body.consentement) return NextResponse.json({ erreur: "consent_required" }, { status: 400 });
  }

  const existant = deja ?? trouveParEmail(email);
  const { compte, motDePasse } = existant
    ? { compte: existant, motDePasse: null as string | null }
    : creeCompte({ email, langue, origine: "pdf", codeApporteur: body.code ?? null });

  if (!deja) {
    const visiteur = req.cookies.get(COOKIE_VISITEUR)?.value ?? "";
    enregistreConsentement({ necessaires: true, mesure: false, marketing: false }, compte.id, visiteur);
  }

  // Le titre vient du rapport déjà calculé : pas de recalcul ici.
  const r = lire(id);
  const titre = r?.annonce ? `${r.annonce.condo} · ${r.annonce.khet}` : null;
  lieRapport(compte.id, id, r?.url ?? null, titre, 0);

  const lien = `${racine(req)}/beta/r/${id}`;
  if (motDePasse) envoie(lettreMotDePasse(compte.email, motDePasse, `${racine(req)}/beta/login`, langue));
  const remis = envoie(lettreRapport(compte.email, lien, langue, compte.id));
  if (remis) marqueMailEnvoye(compte.id, id);

  const res = NextResponse.json({ ok: true, email: compte.email, mail: remis, nouveau: Boolean(motDePasse) });
  if (!deja) poseSession(res, compte.id);
  return res;
}
