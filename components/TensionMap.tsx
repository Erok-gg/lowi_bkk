"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { BASE_STYLE_URL, INITIAL_VIEW, MAX_BOUNDS, applyThemeToBaseStyle } from "@/config/map-config";
import { getMapColors } from "@/config/theme";
import {
  computeTensionByKhet,
  type TensionInput,
  type KhetSnapshot,
  type TensionRow,
} from "@/lib/tension";
import type { DealType } from "@/lib/types";

/**
 * TensionMap — choroplèthe de la TENSION du marché par quartier (lib/tension.ts),
 * basculable entre Location et Vente. Plus c'est rouge, plus le marché est tendu
 * (annonces qui s'écoulent vite, stock rare/en baisse, prix/m² en hausse).
 * Les quartiers à faible échantillon (confiance basse) sont rendus en transparence.
 */

// échelle froide (détendu) → chaude (tendu) ; distincte de l'échelle Yields.
const STOPS: [number, string][] = [
  [0, "#3b4cc0"], [25, "#7a9bd4"], [50, "#e8c97a"], [75, "#e8804a"], [100, "#c2304a"],
];
const NO_DATA = "#2a2a38";

const DEALS: { v: DealType; label: string }[] = [
  { v: "rent", label: "Rent" },
  { v: "sale", label: "Sale" },
];

function Seg<T extends string>({
  options, value, onChange,
}: {
  options: { v: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex overflow-hidden rounded-md border border-violet-soft">
      {options.map((o) => (
        <button
          key={o.v}
          onClick={() => onChange(o.v)}
          className={`px-3 py-1 text-xs transition ${
            value === o.v ? "bg-violet/30 text-gold" : "text-text-muted hover:text-text"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export default function TensionMap({
  inputs,
  snapshots,
}: {
  inputs: TensionInput[];
  snapshots: KhetSnapshot[];
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const dataRef = useRef<GeoJSON.FeatureCollection | null>(null);
  const rowsRef = useRef<Map<string, TensionRow>>(new Map());

  const [deal, setDeal] = useState<DealType>("rent");
  const [ready, setReady] = useState(false);

  // (re)calcule la tension pour le deal_type courant + recolore la carte.
  const recompute = (d: DealType) => {
    const map = mapRef.current;
    const data = dataRef.current;
    if (!map || !data) return;
    const rows = computeTensionByKhet(inputs, snapshots, d);
    rowsRef.current = new Map(rows.map((r) => [r.khet, r]));
    data.features.forEach((f) => {
      const name = (f.properties?.name as string) || "";
      const r = rowsRef.current.get(name);
      if (f.properties) {
        f.properties.tension = r?.tensionScore == null ? -1 : r.tensionScore;
        f.properties.conf = r?.confidence ?? "none";
      }
    });
    (map.getSource("khet-tension") as maplibregl.GeoJSONSource | undefined)?.setData(data);
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
    (window as unknown as { __tensionMap?: maplibregl.Map }).__tensionMap = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    map.on("load", async () => {
      applyThemeToBaseStyle(map);
      let data: GeoJSON.FeatureCollection | null = null;
      try {
        const res = await fetch("/data/bangkok-khet.geojson");
        if (res.ok) data = await res.json();
      } catch { /* géré */ }
      if (!data) return;

      // tension initiale (location)
      const rows0 = computeTensionByKhet(inputs, snapshots, "rent");
      rowsRef.current = new Map(rows0.map((r) => [r.khet, r]));
      data.features.forEach((f, i) => {
        if (f.id == null) f.id = i;
        const name = (f.properties?.name_en || f.properties?.name) as string | undefined;
        const r = name ? rowsRef.current.get(name) : undefined;
        if (f.properties) {
          f.properties.name = name ?? "";
          f.properties.tension = r?.tensionScore == null ? -1 : r.tensionScore;
          f.properties.conf = r?.confidence ?? "none";
        }
      });
      dataRef.current = data;

      map.addSource("khet-tension", { type: "geojson", data });

      const fillColor = [
        "case",
        ["<", ["get", "tension"], 0],
        NO_DATA,
        ["interpolate", ["linear"], ["get", "tension"], ...STOPS.flatMap(([v, c]) => [v, c])],
      ] as unknown as maplibregl.ExpressionSpecification;

      // confiance basse → transparence accrue
      const fillOpacity = [
        "match",
        ["get", "conf"],
        "low", 0.32,
        0.82,
      ] as unknown as maplibregl.ExpressionSpecification;

      map.addLayer({
        id: "khet-tension-fill",
        type: "fill",
        source: "khet-tension",
        paint: { "fill-color": fillColor, "fill-opacity": fillOpacity },
      });
      map.addLayer({
        id: "khet-tension-line",
        type: "line",
        source: "khet-tension",
        paint: { "line-color": colors.districtLine, "line-width": 1 },
      });
      map.addLayer({
        id: "khet-tension-label",
        type: "symbol",
        source: "khet-tension",
        layout: {
          "text-field": [
            "case",
            ["<", ["get", "tension"], 0],
            ["get", "name"],
            ["concat", ["get", "name"], "\n", ["to-string", ["get", "tension"]]],
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

      // popup au survol (détail de la tension du deal_type courant)
      const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
      map.on("mousemove", "khet-tension-fill", (e) => {
        const f = e.features?.[0];
        if (!f) return;
        map.getCanvas().style.cursor = "pointer";
        const name = (f.properties?.name as string) || "";
        const r = rowsRef.current.get(name);
        const score = r?.tensionScore != null ? String(r.tensionScore) : "—";
        const tom = r?.medianTomDays != null
          ? `${r.medianTomDays} d (sold)`
          : r?.medianAgeDays != null
            ? `${r.medianAgeDays} d (live)`
            : "—";
        const trend = r?.stockTrend != null
          ? r.stockTrend < 0 ? "stock ↓" : "stock ↑"
          : "—";
        const conf = r ? r.confidence : "no data";
        popup.setLngLat(e.lngLat).setHTML(
          `<div style="font:12px sans-serif;color:#1a1a1a">
             <strong>${name.replace(" District", "")}</strong><br/>
             Tension: <b>${score}</b> / 100<br/>
             Time on market: ${tom}<br/>
             Stock trend: ${trend}<br/>
             ${r ? `${r.nActive} active · ${r.nDelisted} gone` : "no data"}<br/>
             <span style="color:#666">confidence: ${conf}</span>
           </div>`
        ).addTo(map);
      });
      map.on("mouseleave", "khet-tension-fill", () => {
        map.getCanvas().style.cursor = "";
        popup.remove();
      });

      setReady(true);
    });

    return () => { map.remove(); mapRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inputs, snapshots]);

  // recolore dès que le toggle change (et une fois la carte prête)
  useEffect(() => {
    if (ready) recompute(deal);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deal, ready]);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" />

      {/* Titre + toggle + lien table */}
      <div className="absolute left-4 top-4 z-10 flex items-center gap-3">
        <h1 className="text-lg font-semibold tracking-wide text-text">
          Market <span className="text-violet-fluo">tension</span>
        </h1>
        <Seg options={DEALS} value={deal} onChange={(v) => setDeal(v)} />
        <Link href="/tension-table" className="rounded-md border border-violet-soft bg-surface/95 px-2.5 py-1 text-xs text-text-muted transition hover:border-violet-fluo hover:text-text">
          Table view →
        </Link>
      </div>

      {/* Légende */}
      <div className="absolute bottom-6 left-4 z-10 rounded-md border border-violet-soft bg-surface/95 p-3 text-xs text-text">
        <div className="mb-1.5 font-semibold text-gold">Market tension</div>
        <div className="h-3 w-32 rounded" style={{ background: `linear-gradient(to right, ${STOPS.map((s) => s[1]).join(", ")})` }} />
        <div className="mt-1 flex w-32 justify-between text-text-muted">
          <span>calm</span><span>tense</span>
        </div>
        <div className="mt-1.5 flex items-center gap-1.5 text-text-muted">
          <span className="inline-block h-3 w-3 rounded" style={{ background: NO_DATA }} /> no data
          <span className="ml-2 opacity-40">▨</span> low confidence
        </div>
        <div className="mt-2 max-w-[16rem] border-t border-violet-soft pt-1.5 text-[10px] leading-snug text-text-faint">
          Composite of absorption speed, scarcity, stock trend & rent momentum, per district.
          Indicative — strengthens as more scrapes accumulate over time.
        </div>
      </div>
    </div>
  );
}
