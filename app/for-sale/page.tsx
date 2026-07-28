import { redirect } from "next/navigation";
import { getListings } from "@/lib/listings-db";
import ListingsTable from "@/components/ListingsTable";
import { isAuthed } from "@/lib/auth";
import { isPlausible } from "@/lib/market-bounds";
import { buildUnitMatchesLite } from "@/lib/cross-match";
import { toListingRow } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function ForSalePage() {
  if (!(await isAuthed())) redirect("/login?next=/for-sale");
  const all = await getListings();
  // Bornes de plausibilité : lib/market-bounds.ts (source unique). Elles étaient
  // redéclarées ici, donc le tableau excluait des annonces que la carte et les
  // rendements continuaient de compter.
  const listings = all.filter((l) => l.dealType === "sale" && isPlausible(l));
  // L'appariement vente↔location a besoin des DEUX catégories, mais seuls le
  // prix de la contrepartie et le rendement sont affichés : on apparie ici et
  // on n'envoie que ces deux nombres, au lieu des 16 000 annonces actives.
  const matches = buildUnitMatchesLite(all, new Set(listings.map((l) => l.id)));
  return (
    <ListingsTable deal="sale" listings={listings.map(toListingRow)} matches={matches} />
  );
}
