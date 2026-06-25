import { redirect } from "next/navigation";
import { getListings } from "@/lib/listings-db";
import YieldsMapShell, { type YListing } from "@/components/YieldsMapShell";
import { isAuthed } from "@/lib/auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function YieldsMapPage() {
  if (!(await isAuthed())) redirect("/login?next=/yields-map");
  // payload léger : seuls les champs utiles à la choroplèthe + filtres
  const listings: YListing[] = (await getListings()).map((l) => ({
    khet: l.khet,
    dealType: l.dealType,
    pricePerSqm: l.pricePerSqm,
    bedrooms: l.bedrooms,
    lat: l.lat,
    lng: l.lng,
  }));
  return <YieldsMapShell listings={listings} />;
}
