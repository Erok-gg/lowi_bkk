import { redirect } from "next/navigation";
import { getListings } from "@/lib/listings-db";
import ListingsTable from "@/components/ListingsTable";
import { isAuthed } from "@/lib/auth";
import { isPlausible } from "@/lib/market-bounds";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function ToRentPage() {
  if (!(await isAuthed())) redirect("/login?next=/to-rent");
  const all = await getListings();
  // Mêmes bornes que la vente, côté location (lib/market-bounds.ts) : un « loyer »
  // à 300 THB est un prix journalier, pas une affaire.
  const listings = all.filter((l) => l.dealType === "rent" && isPlausible(l));
  return <ListingsTable deal="rent" listings={listings} allListings={all} />;
}
