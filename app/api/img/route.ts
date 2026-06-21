import { NextRequest, NextResponse } from "next/server";
import { readFile } from "node:fs/promises";
import { join, normalize } from "node:path";

// Sert les images webp du scraper (scraper/output/...) en local.
// À l'online : remplacé par les URLs Supabase Storage.
export const runtime = "nodejs";

const ROOT = join(process.cwd(), "scraper", "output");

export async function GET(req: NextRequest) {
  const p = req.nextUrl.searchParams.get("p") || "";
  // anti path-traversal : on reste sous scraper/output
  const safe = normalize(p).replace(/^(\.\.[/\\])+/, "");
  const full = join(ROOT, safe);
  if (!full.startsWith(ROOT) || !/\.(webp|jpe?g|png)$/i.test(full)) {
    return new NextResponse("Bad path", { status: 400 });
  }
  try {
    const buf = await readFile(full);
    return new NextResponse(buf, {
      headers: {
        "Content-Type": "image/webp",
        "Cache-Control": "public, max-age=86400",
      },
    });
  } catch {
    return new NextResponse("Not found", { status: 404 });
  }
}
