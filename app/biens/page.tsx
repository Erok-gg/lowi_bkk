import { redirect } from "next/navigation";
import { getListings } from "@/lib/listings-db";
import ListingsTable from "@/components/ListingsTable";
import { isAuthed } from "@/lib/auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function BiensPage() {
  if (!(await isAuthed())) redirect("/login?next=/biens");
  const listings = await getListings();
  return <ListingsTable listings={listings} />;
}
