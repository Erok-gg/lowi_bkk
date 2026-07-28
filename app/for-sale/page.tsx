import { redirect } from "next/navigation";
import { getListings } from "@/lib/listings-db";
import ListingsTable from "@/components/ListingsTable";
import { isAuthed } from "@/lib/auth";
import { isPlausible } from "@/lib/market-bounds";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function ForSalePage() {
  if (!(await isAuthed())) redirect("/login?next=/for-sale");
  const all = await getListings();
  // Bornes de plausibilité : lib/market-bounds.ts (source unique). Elles étaient
  // redéclarées ici, donc le tableau excluait des annonces que la carte et les
  // rendements continuaient de compter.
  const listings = all.filter((l) => l.dealType === "sale" && isPlausible(l));
  return <ListingsTable deal="sale" listings={listings} allListings={all} />;
}
