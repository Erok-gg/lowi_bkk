"use client";

import dynamic from "next/dynamic";
import type { YieldRow } from "@/lib/yields";

// MapLibre touche `window` → chargement client uniquement.
const YieldsMap = dynamic(() => import("./YieldsMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center bg-anthracite-deep text-text-muted">
      Loading map…
    </div>
  ),
});

export default function YieldsMapShell({ rows }: { rows: YieldRow[] }) {
  return <YieldsMap rows={rows} />;
}
