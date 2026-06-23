import { redirect } from "next/navigation";
import { getListings } from "@/lib/listings-db";
import { computeYieldsByKhet } from "@/lib/yields";
import YieldsTable from "@/components/YieldsTable";
import { isAuthed } from "@/lib/auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function RendementsPage() {
  if (!(await isAuthed())) redirect("/login?next=/rendements");
  const rows = computeYieldsByKhet(await getListings());
  return <YieldsTable rows={rows} />;
}
