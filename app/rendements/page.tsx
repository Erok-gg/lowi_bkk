import { redirect } from "next/navigation";
import { getListings } from "@/lib/listings-db";
import YieldsTable from "@/components/YieldsTable";
import { isAuthed } from "@/lib/auth";
import { keepPlausible } from "@/lib/market-bounds";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function RendementsPage() {
  if (!(await isAuthed())) redirect("/login?next=/rendements");
  // le calcul (double médiane par condo, strate de chambres) vit côté client
  // pour que le toggle de segment recalcule sans aller-retour serveur.
  // Assaini en amont : une médiane est bien plus sensible à une aberration
  // qu'une ligne de tableau, et jusqu'ici seuls les tableaux filtraient.
  const listings = keepPlausible(await getListings());
  return <YieldsTable listings={listings} />;
}
