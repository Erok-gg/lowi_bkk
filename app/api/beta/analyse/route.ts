import { NextResponse } from "next/server";
import { isAuthed } from "@/lib/auth";
import { disponible, lancer, suivi, urlAcceptee } from "@/bilan_RE/web/lib/rapport";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** POST { url } → lance (ou retrouve) le rapport. Réponse : { id, etat } ou { erreur }. */
export async function POST(req: Request) {
  if (!(await isAuthed())) return NextResponse.json({ erreur: "Not signed in." }, { status: 401 });
  const { url } = (await req.json().catch(() => ({}))) as { url?: string };
  if (!url) return NextResponse.json({ erreur: "Paste the link of a listing." }, { status: 400 });
  const ok = urlAcceptee(url);
  if (!ok.ok) return NextResponse.json({ erreur: ok.raison }, { status: 400 });
  if (!disponible())
    return NextResponse.json(
      { erreur: "Analysis runs on the Lowi data server only during the beta. This server cannot reach it." },
      { status: 503 },
    );
  const id = lancer(url);
  return NextResponse.json(suivi(id));
}

/** GET ?id= → état, rang dans la file, compteurs et temps restant estimé. */
export async function GET(req: Request) {
  if (!(await isAuthed())) return NextResponse.json({ erreur: "Not signed in." }, { status: 401 });
  const id = new URL(req.url).searchParams.get("id") ?? "";
  return NextResponse.json(suivi(id));
}

