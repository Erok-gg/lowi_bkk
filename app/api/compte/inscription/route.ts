/**
 * POST /api/compte/inscription — { email, langue?, consentement, code? }
 *
 * On ne demande QUE l'e-mail (décision du 2026-10-19). Le mot de passe est
 * généré ici et parti par e-mail : la personne n'en choisit pas, donc n'en
 * réutilise pas un. Nom, prénom, naissance, nationalité viendront au paiement.
 *
 * Réponse identique que le compte existe ou non : sinon la route dit à un
 * inconnu quelles adresses sont déjà clientes.
 */
import { NextRequest, NextResponse } from "next/server";
import {
  creeCompte,
  disponibleComptes,
  emailPlausible,
  enregistreConsentement,
  regenereMotDePasse,
  trouveParEmail,
  COOKIE_VISITEUR,
  VERSION_CONSENTEMENT,
} from "@/bilan_RE/web/lib/comptes";
import { poseSession } from "@/bilan_RE/web/lib/session";
import { envoie, lettreMotDePasse } from "@/bilan_RE/web/lib/mail";
import { accesProduit } from "@/bilan_RE/web/lib/acces";
import { adresse, autorise, racine } from "@/bilan_RE/web/lib/limite";
import { langueValide } from "@/bilan_RE/web/i18n";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  // Même porte que les pages : tant que la beta n'est pas ouverte au public,
  // ces routes restent derrière le mot de passe partagé. Sinon on pourrait
  // créer des comptes sur un service encore fermé.
  if (!(await accesProduit())) return NextResponse.json({ erreur: "closed" }, { status: 403 });
  if (!disponibleComptes()) return NextResponse.json({ erreur: "accounts_unavailable" }, { status: 503 });
  if (!autorise(`inscription:${adresse(req)}`, 10)) return NextResponse.json({ erreur: "too_many" }, { status: 429 });

  const body = (await req.json().catch(() => ({}))) as {
    email?: string;
    langue?: string;
    consentement?: boolean;
    code?: string;
  };
  const email = (body.email ?? "").trim();
  if (!emailPlausible(email)) return NextResponse.json({ erreur: "bad_email" }, { status: 400 });
  if (!body.consentement) return NextResponse.json({ erreur: "consent_required" }, { status: 400 });

  const langue = langueValide(body.langue);
  const existant = trouveParEmail(email);
  const { compte, motDePasse } = existant
    ? { compte: existant, motDePasse: regenereMotDePasse(existant.id) }
    : creeCompte({ email, langue, origine: "inscription", codeApporteur: body.code ?? null });

  // Preuve du consentement au texte en vigueur (PDPA et RGPD : il faut pouvoir
  // montrer QUOI a été accepté, pas seulement QUE ça l'a été).
  const visiteur = req.cookies.get(COOKIE_VISITEUR)?.value ?? "";
  enregistreConsentement({ necessaires: true, mesure: false, marketing: false }, compte.id, visiteur);

  const remis = motDePasse
    ? envoie(lettreMotDePasse(email, motDePasse, `${racine(req)}/beta/login`, langue))
    : true;

  const res = NextResponse.json({ ok: true, email, mail: remis, version: VERSION_CONSENTEMENT });
  // La session s'ouvre tout de suite : la personne continue sans attendre le
  // mail, qui ne sert qu'à revenir plus tard.
  poseSession(res, compte.id);
  return res;
}
