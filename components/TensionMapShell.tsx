"use client";

import dynamic from "next/dynamic";
import type { TensionInput, KhetSnapshot } from "@/lib/tension";

// MapLibre touche `window` → chargement client uniquement.
const TensionMap = dynamic(() => import("./TensionMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center bg-anthracite-deep text-text-muted">
      Loading map…
    </div>
  ),
});

export default function TensionMapShell({
  inputs,
  snapshots,
}: {
  inputs: TensionInput[];
  snapshots: KhetSnapshot[];
}) {
  return <TensionMap inputs={inputs} snapshots={snapshots} />;
}
