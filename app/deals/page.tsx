import { redirect } from "next/navigation";
import { getListings, getOriginalPrices } from "@/lib/listings-db";
import { enrichSaleDeals } from "@/lib/deals";
import DealsView from "@/components/DealsView";
import { isAuthed } from "@/lib/auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function DealsPage() {
  if (!(await isAuthed())) redirect("/login?next=/deals");
  const [listings, originalPrices] = await Promise.all([getListings(), getOriginalPrices()]);
  const rows = enrichSaleDeals(listings, originalPrices);
  return <DealsView rows={rows} />;
}
