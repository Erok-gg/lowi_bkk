"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { BASE_STYLE_URL, INITIAL_VIEW, MAX_BOUNDS, applyThemeToBaseStyle } from "@/config/map-config";
import { getMapColors } from "@/config/theme";
import { computeYieldsByKhet, type YieldRow } from "@/lib/yields";
import { computeNearestMetroSchool } from "@/lib/proximity";
import type { Listing } from "@/lib/types";
import type { YListing } from "@/components/YieldsMapShell";

/**
 * YieldsMap — choroplèthe des rendements bruts par quartier (moyenne des 3 biens
 * médians, lib/yields.ts), avec filtres : chambres, distance métro, distance
 * école. À chaque filtre, on recalcule les rendements sur le sous-ensemble et on
 * recolore la carte.
 */

const STOPS: [number, string][] = [
  [3, "#7a1f2b"], [5, "#9a5a12"], [7, "#9ca700"], [9, "#4cc06a"], [12, "#3ad97f"],
];
const NO_DATA = "#2a2a38";

type Enriched = YListing & { metroM: number | null; schoolM: number | null };
type Beds = "all" | "1" | "2" | "3" | "4+";

const BEDS: Beds[] = ["all", "1", "2", "3", "4+"];
const METRO: { v: number; label: string }[] = [
  { v: 0, label: "Any" }, { v: 500, label: "≤500m" }, { v: 1000, label: "≤1km" },
];
const SCHOOL: { v: number; label: string }[] = [
  { v: 0, label: "Any" }, { v: 1000, label: "≤1km" }, { v: 2000, label: "≤2km" },
];

function Seg<T extends string | number>({
  label, options, value, onChange,
}: {
  label: string;
  options: { v: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-14 shrink-0 text-xs text-text-muted">{label}</span>
      <div className="flex overflow-hidden rounded-md border border-violet-soft">
        {options.map((o) => (
          <button
            key={String(o.v)}
            onClick={() => onChange(o.v)}
            className={`px-2 py-1 text-xs transition ${
              value === o.v ? "bg-violet/30 text-gold" : "text-text-muted hover:text-text"
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function YieldsMap({ listings }: { listings: YListing[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const dataRef = useRef<GeoJSON.FeatureCollection | null>(null);
  const enrichedRef = useRef<Enriched[]>([]);
  const rowsRef = useRef<Map<string, YieldRow>>(new Map());

  const [beds, setBeds] = useState<Beds>("all");
  const [metroMax, setMetroMax] = useState(0);
  const [schoolMax, setSchoolMax] = useState(0);
  const [ready, setReady] = useState(false);

  // (re)calcule les rendements sur le sous-ensemble filtré + recolore la carte.
  const recompute = (b: Beds, mMax: number, sMax: number) => {
    const map = mapRef.current;
    const data = dataRef.current;
    if (!map || !data) return;
    const matchBeds = (n: number | null) =>
      b === "all" ? true : b === "4+" ? (n ?? 0) >= 4 : (n ?? -1) === Number(b);
    const sub = enrichedRef.current.filter(
      (l) =>
        matchBeds(l.bedrooms) &&
        (mMax === 0 || (l.metroM != null && l.metroM <= mMax)) &&
        (sMax === 0 || (l.schoolM != null && l.schoolM <= sMax))
    );
    const rows = computeYieldsByKhet(sub as unknown as Listing[]);
    rowsRef.current = new Map(rows.map((r) => [r.khet, r]));
    data.features.forEach((f) => {
      const name = (f.properties?.name as string) || "";
      const y = rowsRef.current.get(name)?.grossYieldPct;
      if (f.properties) f.properties.yield = y == null ? -1 : y;
    });
    (map.getSource("khet-yields") as maplibregl.GeoJSONSource | undefined)?.setData(data);
  };

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const colors = getMapColors();

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

      // rendements initiaux (sans filtre)
      const rows0 = computeYieldsByKhet(listings as unknown as Listing[]);
      const byName0 = new Map(rows0.map((r) => [r.khet, r]));
      rowsRef.current = byName0;
      data.features.forEach((f, i) => {
        if (f.id == null) f.id = i;
        const name = (f.properties?.name_en || f.properties?.name) as string | undefined;
        const r = name ? byName0.get(name) : undefined;
        if (f.properties) {
          f.properties.name = name ?? "";
          f.properties.yield = r?.grossYieldPct == null ? -1 : r.grossYieldPct;
        }
      });
      dataRef.current = data;

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
        paint: { "fill-color": fillColor, "fill-opacity": 0.8 },
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

      // popup au survol (détail du rendement filtré courant)
      const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
      map.on("mousemove", "khet-yields-fill", (e) => {
        const f = e.features?.[0];
        if (!f) return;
        map.getCanvas().style.cursor = "pointer";
        const name = (f.properties?.name as string) || "";
        const r = rowsRef.current.get(name);
        const y = r?.grossYieldPct != null ? `${r.grossYieldPct} %` : "—";
        popup.setLngLat(e.lngLat).setHTML(
          `<div style="font:12px sans-serif;color:#1a1a1a">
             <strong>${name.replace(" District", "")}</strong><br/>
             Gross yield: <b>${y}</b><br/>
             Sale/m²: ${r?.saleMedianPsqm ? Math.round(r.saleMedianPsqm).toLocaleString("en-US") : "—"}<br/>
             Rent/m²: ${r?.rentMedianPsqm ? Math.round(r.rentMedianPsqm).toLocaleString("en-US") : "—"}<br/>
             ${r ? `${r.nSale} sale · ${r.nRent} rent` : "no data"}
           </div>`
        ).addTo(map);
      });
      map.on("mouseleave", "khet-yields-fill", () => {
        map.getCanvas().style.cursor = "";
        popup.remove();
      });

      // distances métro/école (pour les filtres) — calculées une fois
      const withCoords = listings.filter((l) => l.lat != null && l.lng != null);
      const dists = await computeNearestMetroSchool(
        withCoords.map((l) => ({ lat: l.lat!, lng: l.lng! }))
      );
      let i = 0;
      enrichedRef.current = listings.map((l) =>
        l.lat != null && l.lng != null
          ? { ...l, metroM: dists[i].metroM, schoolM: dists[i++].schoolM }
          : { ...l, metroM: null, schoolM: null }
      );
      setReady(true);
    });

    return () => { map.remove(); mapRef.current = null; };
  }, [listings]);

  // applique les filtres dès qu'ils changent (et quand les distances sont prêtes)
  useEffect(() => {
    if (ready) recompute(beds, metroMax, schoolMax);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [beds, metroMax, schoolMax, ready]);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" />

      {/* Titre + lien table */}
      <div className="absolute left-4 top-4 z-10 flex items-center gap-3">
        <h1 className="text-lg font-semibold tracking-wide text-text">
          Yields <span className="text-violet-fluo">map</span>
        </h1>
        <Link href="/rendements" className="rounded-md border border-violet-soft bg-surface/95 px-2.5 py-1 text-xs text-text-muted transition hover:border-violet-fluo hover:text-text">
          Table view →
        </Link>
      </div>

      {/* Filtres */}
      <div className="absolute left-4 top-14 z-10 flex flex-col gap-2 rounded-md border border-violet-soft bg-surface/95 p-3">
        <Seg label="Beds" value={beds} onChange={(v) => setBeds(v)}
          options={BEDS.map((b) => ({ v: b, label: b === "all" ? "All" : b }))} />
        <Seg label="Metro" value={metroMax} onChange={(v) => setMetroMax(v)} options={METRO} />
        <Seg label="School" value={schoolMax} onChange={(v) => setSchoolMax(v)} options={SCHOOL} />
        {!ready && (metroMax > 0 || schoolMax > 0) && (
          <span className="text-[10px] text-text-faint">Computing distances…</span>
        )}
      </div>

      {/* Légende */}
      <div className="absolute bottom-6 left-4 z-10 rounded-md border border-violet-soft bg-surface/95 p-3 text-xs text-text">
        <div className="mb-1.5 font-semibold text-gold">Gross yield /m²</div>
        <div className="h-3 w-32 rounded" style={{ background: `linear-gradient(to right, ${STOPS.map((s) => s[1]).join(", ")})` }} />
        <div className="mt-1 flex w-32 justify-between text-text-muted">
          <span>3%</span><span>7%</span><span>12%+</span>
        </div>
        <div className="mt-1.5 flex items-center gap-1.5 text-text-muted">
          <span className="inline-block h-3 w-3 rounded" style={{ background: NO_DATA }} /> no data
        </div>
      </div>
    </div>
  );
}
