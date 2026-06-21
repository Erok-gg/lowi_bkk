"use client";

import dynamic from "next/dynamic";

// MapLibre touche `window` — on charge MapView uniquement côté client.
const MapView = dynamic(() => import("./MapView"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center bg-anthracite-deep text-text-muted">
      Chargement de la carte…
    </div>
  ),
});

export default function MapShell() {
  return <MapView />;
}
