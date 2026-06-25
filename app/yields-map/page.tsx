import { redirect } from "next/navigation";
import { getListings } from "@/lib/listings-db";
import { computeYieldsByKhet } from "@/lib/yields";
import YieldsMapShell from "@/components/YieldsMapShell";
import { isAuthed } from "@/lib/auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function YieldsMapPage() {
  if (!(await isAuthed())) redirect("/login?next=/yields-map");
  const rows = computeYieldsByKhet(await getListings());
  return <YieldsMapShell rows={rows} />;
}
