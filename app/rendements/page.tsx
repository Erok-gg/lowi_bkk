import { redirect } from "next/navigation";
import { getListings } from "@/lib/listings-db";
import YieldsTable from "@/components/YieldsTable";
import { isAuthed } from "@/lib/auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function RendementsPage() {
  if (!(await isAuthed())) redirect("/login?next=/rendements");
  // le calcul (double médiane par condo, strate de chambres) vit côté client
  // pour que le toggle de segment recalcule sans aller-retour serveur
  const listings = await getListings();
  return <YieldsTable listings={listings} />;
}
