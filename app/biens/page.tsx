import { getListings } from "@/lib/listings-db";
import ListingsTable from "@/components/ListingsTable";

// Lit le SQLite local (node:sqlite) → runtime Node, données fraîches.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function BiensPage() {
  const listings = await getListings();
  return <ListingsTable listings={listings} />;
}
