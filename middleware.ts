import { NextRequest, NextResponse } from "next/server";

/**
 * Basic auth gate — protège tout le site (outil privé).
 * Définir BASIC_AUTH_USER et BASIC_AUTH_PASSWORD dans les env (.env.local / Vercel).
 * Si non définis (dev local), l'accès est laissé ouvert.
 */
export function middleware(req: NextRequest) {
  const user = process.env.BASIC_AUTH_USER;
  const pass = process.env.BASIC_AUTH_PASSWORD;

  // Pas de credentials configurés → pas de gate (dev)
  if (!user || !pass) return NextResponse.next();

  const auth = req.headers.get("authorization");
  if (auth) {
    const [scheme, encoded] = auth.split(" ");
    if (scheme === "Basic" && encoded) {
      const decoded = atob(encoded);
      const idx = decoded.indexOf(":");
      const u = decoded.slice(0, idx);
      const p = decoded.slice(idx + 1);
      if (u === user && p === pass) return NextResponse.next();
    }
  }

  return new NextResponse("Authentification requise", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="Bangkok Map", charset="UTF-8"' },
  });
}

export const config = {
  // Protège tout sauf assets statiques internes Next
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
