import { redirect } from "next/navigation";
import { getListings } from "@/lib/listings-db";
import ListingsTable from "@/components/ListingsTable";
import { isAuthed } from "@/lib/auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Exclusions dures demandées sur la page vente.
const MIN_PRICE = 800_000;
const MAX_PRICE = 100_000_000;

export default async function ForSalePage() {
  if (!(await isAuthed())) redirect("/login?next=/for-sale");
  const all = await getListings();
  const listings = all.filter(
    (l) => l.dealType === "sale" && l.price >= MIN_PRICE && l.price <= MAX_PRICE
  );
  return <ListingsTable deal="sale" listings={listings} allListings={all} />;
}
