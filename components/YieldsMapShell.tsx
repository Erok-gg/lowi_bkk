"use client";

import dynamic from "next/dynamic";
import type { DealType } from "@/lib/types";

export interface YListing {
  khet: string | null;
  dealType: DealType;
  pricePerSqm: number | null;
  bedrooms: number | null;
  lat: number | null;
  lng: number | null;
}

// MapLibre touche `window` → chargement client uniquement.
const YieldsMap = dynamic(() => import("./YieldsMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center bg-anthracite-deep text-text-muted">
      Loading map…
    </div>
  ),
});

export default function YieldsMapShell({ listings }: { listings: YListing[] }) {
  return <YieldsMap listings={listings} />;
}
