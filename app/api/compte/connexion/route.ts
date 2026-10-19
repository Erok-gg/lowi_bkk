/** POST /api/compte/connexion — { email, motDePasse } → ouvre la session. */
import { NextRequest, NextResponse } from "next/server";
import { connecte, disponibleComptes } from "@/bilan_RE/web/lib/comptes";
import { poseSession } from "@/bilan_RE/web/lib/session";
import { accesProduit } from "@/bilan_RE/web/lib/acces";
import { adresse, autorise } from "@/bilan_RE/web/lib/limite";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  // Même porte que les pages : tant que la beta n'est pas ouverte au public,
  // ces routes restent derrière le mot de passe partagé. Sinon on pourrait
  // créer des comptes sur un service encore fermé.
  if (!(await accesProduit())) return NextResponse.json({ erreur: "closed" }, { status: 403 });
  if (!disponibleComptes()) return NextResponse.json({ erreur: "accounts_unavailable" }, { status: 503 });
  // Plafond serré : c'est la porte où l'on devine des mots de passe.
  if (!autorise(`connexion:${adresse(req)}`, 20)) return NextResponse.json({ erreur: "too_many" }, { status: 429 });

  const { email, motDePasse } = (await req.json().catch(() => ({}))) as { email?: string; motDePasse?: string };
  const compte = email && motDePasse ? connecte(email, motDePasse) : null;
  if (!compte) return NextResponse.json({ erreur: "bad_credentials" }, { status: 401 });

  const res = NextResponse.json({ ok: true, aRenouveler: Boolean(compte.mdp_a_renouveler) });
  poseSession(res, compte.id);
  return res;
}
