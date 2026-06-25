"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { BASE_STYLE_URL, INITIAL_VIEW, MAX_BOUNDS, applyThemeToBaseStyle } from "@/config/map-config";
import { getMapColors } from "@/config/theme";
import type { YieldRow } from "@/lib/yields";

/**
 * YieldsMap — choroplèthe des rendements bruts par quartier (calcul moyenne des
 * 3 biens médians, cf. lib/yields.ts). Couleur du rouge sombre (faible) au vert
 * fluo (élevé) ; quartiers sans donnée en gris.
 */

// paliers de couleur (rendement brut %)
const STOPS: [number, string][] = [
  [3, "#7a1f2b"],
  [5, "#9a5a12"],
  [7, "#9ca700"],
  [9, "#4cc06a"],
  [12, "#3ad97f"],
];
const NO_DATA = "#2a2a38";

export default function YieldsMap({ rows }: { rows: YieldRow[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const colors = getMapColors();
    const byName = new Map(rows.map((r) => [r.khet, r.grossYieldPct]));

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: BASE_STYLE_URL,
      center: INITIAL_VIEW.center,
      zoom: INITIAL_VIEW.zoom,
      minZoom: INITIAL_VIEW.minZoom,
      maxZoom: INITIAL_VIEW.maxZoom,
      maxBounds: MAX_BOUNDS,
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    (window as unknown as { __yieldsMap?: maplibregl.Map }).__yieldsMap = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    map.on("load", async () => {
      applyThemeToBaseStyle(map);
      let data: GeoJSON.FeatureCollection | null = null;
      try {
        const res = await fetch("/data/bangkok-khet.geojson");
        if (res.ok) data = await res.json();
      } catch { /* géré */ }
      if (!data) return;

      data.features.forEach((f, i) => {
        if (f.id == null) f.id = i;
        const name = (f.properties?.name_en || f.properties?.name) as string | undefined;
        const y = name ? byName.get(name) : null;
        if (f.properties) {
          f.properties.name = name ?? "";
          f.properties.yield = y == null ? -1 : y; // -1 = pas de donnée
        }
      });

      map.addSource("khet-yields", { type: "geojson", data });

      const fillColor = [
        "case",
        ["<", ["get", "yield"], 0],
        NO_DATA,
        ["interpolate", ["linear"], ["get", "yield"], ...STOPS.flatMap(([v, c]) => [v, c])],
      ] as unknown as maplibregl.ExpressionSpecification;

      map.addLayer({
        id: "khet-yields-fill",
        type: "fill",
        source: "khet-yields",
        paint: {
          "fill-color": fillColor,
          "fill-opacity": 0.8,
        },
      });
      map.addLayer({
        id: "khet-yields-line",
        type: "line",
        source: "khet-yields",
        paint: { "line-color": colors.districtLine, "line-width": 1 },
      });
      map.addLayer({
        id: "khet-yields-label",
        type: "symbol",
        source: "khet-yields",
        layout: {
          "text-field": [
            "case",
            ["<", ["get", "yield"], 0],
            ["get", "name"],
            ["concat", ["get", "name"], "\n", ["to-string", ["get", "yield"]], " %"],
          ],
          "text-size": ["interpolate", ["linear"], ["zoom"], 9, 12, 12, 16],
          "text-font": ["Noto Sans Regular"],
          "text-line-height": 1.3,
        },
        paint: {
          "text-color": "#ffffff",
          "text-halo-color": colors.labelHalo,
          "text-halo-width": 2.2,
        },
      });

      // popup au survol (détail rendement)
      const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
      map.on("mousemove", "khet-yields-fill", (e) => {
        const f = e.features?.[0];
        if (!f) return;
        map.getCanvas().style.cursor = "pointer";
        const p = f.properties as { name?: string; yield?: number };
        const r = rows.find((x) => x.khet === p.name);
        const y = p.yield != null && p.yield >= 0 ? `${p.yield} %` : "—";
        popup.setLngLat(e.lngLat).setHTML(
          `<div style="font:12px sans-serif;color:#1a1a1a">
             <strong>${(p.name || "").replace(" District", "")}</strong><br/>
             Gross yield: <b>${y}</b><br/>
             Sale/m²: ${r?.saleMedianPsqm ? Math.round(r.saleMedianPsqm).toLocaleString("en-US") : "—"}<br/>
             Rent/m²: ${r?.rentMedianPsqm ? Math.round(r.rentMedianPsqm).toLocaleString("en-US") : "—"}<br/>
             ${r ? `${r.nSale} sale · ${r.nRent} rent` : ""}
           </div>`
        ).addTo(map);
      });
      map.on("mouseleave", "khet-yields-fill", () => {
        map.getCanvas().style.cursor = "";
        popup.remove();
      });
    });

    return () => { map.remove(); mapRef.current = null; };
  }, [rows]);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" />

      {/* Légende */}
      <div className="absolute bottom-6 left-4 z-10 rounded-md border border-violet-soft bg-surface/95 p-3 text-xs text-text">
        <div className="mb-1.5 font-semibold text-gold">Gross yield /m²</div>
        <div className="flex items-center gap-2">
          <div className="h-3 w-32 rounded" style={{ background: `linear-gradient(to right, ${STOPS.map((s) => s[1]).join(", ")})` }} />
        </div>
        <div className="mt-1 flex w-32 justify-between text-text-muted">
          <span>3%</span><span>7%</span><span>12%+</span>
        </div>
        <div className="mt-1.5 flex items-center gap-1.5 text-text-muted">
          <span className="inline-block h-3 w-3 rounded" style={{ background: NO_DATA }} /> no data
        </div>
      </div>

      <div className="absolute left-4 top-4 z-10 flex items-center gap-3">
        <h1 className="text-lg font-semibold tracking-wide text-text">
          Yields <span className="text-violet-fluo">map</span>
        </h1>
        <Link href="/rendements" className="rounded-md border border-violet-soft bg-surface/95 px-2.5 py-1 text-xs text-text-muted transition hover:border-violet-fluo hover:text-text">
          Table view →
        </Link>
      </div>
    </div>
  );
}
