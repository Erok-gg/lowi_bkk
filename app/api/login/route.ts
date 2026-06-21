import { NextRequest, NextResponse } from "next/server";
import { AUTH_COOKIE, tokenFor } from "@/lib/auth";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const pw = process.env.BASIC_AUTH_PASSWORD;
  let password = "";
  try {
    password = (await req.json())?.password ?? "";
  } catch {
    /* corps vide */
  }

  // Pas de mot de passe configuré → accès ouvert (dev)
  if (!pw || password === pw) {
    const res = NextResponse.json({ ok: true });
    if (pw) {
      res.cookies.set(AUTH_COOKIE, tokenFor(pw), {
        httpOnly: true,
        secure: true,
        sameSite: "lax",
        path: "/",
        maxAge: 60 * 60 * 24 * 30, // 30 jours
      });
    }
    return res;
  }
  return NextResponse.json({ ok: false }, { status: 401 });
}
