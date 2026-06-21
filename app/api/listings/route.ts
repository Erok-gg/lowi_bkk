import { NextResponse } from "next/server";
import { getListings } from "@/lib/listings-db";

// Lecture du SQLite local via node:sqlite → runtime Node obligatoire.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    return NextResponse.json({ listings: await getListings() });
  } catch (e) {
    console.error("GET /api/listings", e);
    return NextResponse.json(
      { listings: [], error: (e as Error).message },
      { status: 500 }
    );
  }
}
