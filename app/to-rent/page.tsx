import { redirect } from "next/navigation";
import { getListings } from "@/lib/listings-db";
import ListingsTable from "@/components/ListingsTable";
import { isAuthed } from "@/lib/auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function ToRentPage() {
  if (!(await isAuthed())) redirect("/login?next=/to-rent");
  const all = await getListings();
  const listings = all.filter((l) => l.dealType === "rent");
  return <ListingsTable deal="rent" listings={listings} allListings={all} />;
}
