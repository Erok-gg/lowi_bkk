/** POST /api/compte/deconnexion — ferme la session côté serveur ET le cookie. */
import { NextRequest, NextResponse } from "next/server";
import { COOKIE_SESSION, retireSession } from "@/bilan_RE/web/lib/session";
import { disponibleComptes } from "@/bilan_RE/web/lib/comptes";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const res = NextResponse.json({ ok: true });
  // Le cookie part même sans base : sinon on resterait « connecté » à rien.
  if (disponibleComptes()) retireSession(res, req.cookies.get(COOKIE_SESSION)?.value);
  else res.cookies.set(COOKIE_SESSION, "", { path: "/", maxAge: 0 });
  return res;
}
