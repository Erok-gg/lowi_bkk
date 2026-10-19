/** POST /api/compte/mot-de-passe — { nouveau } sur le compte connecté. */
import { NextResponse } from "next/server";
import { poseMotDePasse } from "@/bilan_RE/web/lib/comptes";
import { compteCourant } from "@/bilan_RE/web/lib/session";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const compte = await compteCourant();
  if (!compte) return NextResponse.json({ erreur: "not_signed_in" }, { status: 401 });

  const { nouveau } = (await req.json().catch(() => ({}))) as { nouveau?: string };
  // 10 caractères : le mot de passe que NOUS générons en fait 12 ; demander
  // moins que ce qu'on envoie serait incohérent.
  if (!nouveau || nouveau.length < 10) return NextResponse.json({ erreur: "too_short" }, { status: 400 });

  poseMotDePasse(compte.id, nouveau);
  return NextResponse.json({ ok: true });
}
