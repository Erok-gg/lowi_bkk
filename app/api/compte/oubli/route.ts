/**
 * POST /api/compte/oubli — { email } → nouveau mot de passe par e-mail.
 *
 * Réponse TOUJOURS identique, compte ou pas : cette route ne doit pas servir à
 * savoir qui est client. Et pas de lien magique : le canal e-mail est déjà le
 * canal du mot de passe, un jeton de plus n'ajouterait rien ici.
 */
import { NextRequest, NextResponse } from "next/server";
import { disponibleComptes, emailPlausible, regenereMotDePasse, trouveParEmail } from "@/bilan_RE/web/lib/comptes";
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
  if (!autorise(`oubli:${adresse(req)}`, 5)) return NextResponse.json({ erreur: "too_many" }, { status: 429 });

  const { email, langue } = (await req.json().catch(() => ({}))) as { email?: string; langue?: string };
  if (email && emailPlausible(email)) {
    const compte = trouveParEmail(email);
    if (compte) {
      const mdp = regenereMotDePasse(compte.id);
      envoie(lettreMotDePasse(compte.email, mdp, `${racine(req)}/beta/login`, langueValide(langue ?? compte.langue ?? "en")));
    }
  }
  return NextResponse.json({ ok: true });
}
