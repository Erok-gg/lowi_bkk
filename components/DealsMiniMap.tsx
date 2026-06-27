"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { BASE_STYLE_URL, INITIAL_VIEW, MAX_BOUNDS, applyThemeToBaseStyle } from "@/config/map-config";

export interface MiniPoint {
  id: string;
  lat: number | null;
  lng: number | null;
  name: string;
}

/** Petite carte qui pin une liste de biens (top-20 courant) et recadre dessus. */
export default function DealsMiniMap({ points }: { points: MiniPoint[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const readyRef = useRef(false);
  const pointsRef = useRef<MiniPoint[]>(points);
  pointsRef.current = points;

  const update = () => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    const src = map.getSource("deals") as maplibregl.GeoJSONSource | undefined;
    if (!src) return;
    const pts = pointsRef.current.filter((p) => p.lat != null && p.lng != null);
    src.setData({
      type: "FeatureCollection",
      features: pts.map((p) => ({
        type: "Feature",
        properties: { name: p.name },
        geometry: { type: "Point", coordinates: [p.lng!, p.lat!] },
      })),
    });
    if (pts.length) {
      const b = new maplibregl.LngLatBounds();
      pts.forEach((p) => b.extend([p.lng!, p.lat!]));
      map.fitBounds(b, { padding: 50, maxZoom: 14, duration: 500 });
    }
  };

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: BASE_STYLE_URL,
      center: INITIAL_VIEW.center,
      zoom: 9.5,
      minZoom: INITIAL_VIEW.minZoom,
      maxZoom: INITIAL_VIEW.maxZoom,
      maxBounds: MAX_BOUNDS,
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    map.on("load", () => {
      applyThemeToBaseStyle(map);
      map.addSource("deals", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "deals-pins",
        type: "circle",
        source: "deals",
        paint: {
          "circle-radius": 7,
          "circle-color": "#c9a84c",
          "circle-stroke-width": 1,
          "circle-stroke-color": "#ffffff",
        },
      });
      const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
      map.on("mouseenter", "deals-pins", (e) => {
        const f = e.features?.[0];
        if (!f) return;
        map.getCanvas().style.cursor = "pointer";
        const c = (f.geometry as GeoJSON.Point).coordinates as [number, number];
        popup.setLngLat(c)
          .setHTML(`<div style="font:12px sans-serif;color:#1a1a1a">${f.properties?.name || ""}</div>`)
          .addTo(map);
      });
      map.on("mouseleave", "deals-pins", () => {
        map.getCanvas().style.cursor = "";
        popup.remove();
      });
      readyRef.current = true;
      update();
    });
    return () => { map.remove(); mapRef.current = null; readyRef.current = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { update(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [points]);

  return <div ref={containerRef} className="h-full w-full" />;
}
