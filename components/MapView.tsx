"use client";

import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import {
  BASE_STYLE_URL,
  INITIAL_VIEW,
  MAX_BOUNDS,
  LAYERS,
  applyThemeToBaseStyle,
} from "@/config/map-config";
import { getMapColors } from "@/config/theme";
import { addPoiLayers, setCategoryVisibility } from "@/components/map/pois";
import { POI_CATEGORIES } from "@/config/poi-config";
import Legend from "@/components/Legend";
import PropertyCard from "@/components/PropertyCard";
import { computeProximity } from "@/lib/proximity";
import { applyUrlFilters } from "@/lib/filters";
import type { Listing } from "@/lib/types";

interface KhetProps {
  name?: string;
  name_en?: string;
  name_th?: string;
  [k: string]: unknown;
}

export default function MapView() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const hoveredId = useRef<string | number | null>(null);
  const listingsById = useRef<Map<string, Listing>>(new Map());
  const [selected, setSelected] = useState<string | null>(null);
  const [card, setCard] = useState<{ listing: Listing; x: number; y: number } | null>(null);
  // catégories POI masquées (cochées par défaut sauf defaultVisible:false)
  const [hidden, setHidden] = useState<Set<string>>(
    () => new Set(POI_CATEGORIES.filter((c) => c.defaultVisible === false).map((c) => c.id))
  );

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

    // expose l'instance pour debug console (window.__map)
    (window as unknown as { __map?: maplibregl.Map }).__map = map;

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    map.on("load", async () => {
      applyThemeToBaseStyle(map);

      // Biens (récupérés une fois) : servent aux compteurs par quartier ET aux pinpoints
      let listings: Listing[] = [];
      try {
        const res = await fetch("/api/listings");
        if (res.ok) {
          const all: Listing[] = (await res.json()).listings ?? [];
          const params = new URLSearchParams(window.location.search);
          listings = applyUrlFilters(all, params);
        }
      } catch {
        /* pas de DB / API */
      }
      // nb de biens par quartier (clé = khet, qui = name_en du GeoJSON via point-in-polygon)
      const countByKhet: Record<string, number> = {};
      for (const l of listings) {
        if (l.khet) countByKhet[l.khet] = (countByKhet[l.khet] ?? 0) + 1;
      }

      // Charge les quartiers (GeoJSON statique généré via Overpass)
      let data: GeoJSON.FeatureCollection | null = null;
      try {
        const res = await fetch("/data/bangkok-khet.geojson");
        if (res.ok) data = await res.json();
      } catch {
        /* géré ci-dessous */
      }
      if (!data) {
        console.warn("bangkok-khet.geojson introuvable — lancer `npm run geo:khet`");
        return;
      }

      // ids stables (hover) + nb de biens par quartier
      data.features.forEach((f, i) => {
        if (f.id == null) f.id = i;
        const name = (f.properties?.name_en || f.properties?.name) as string | undefined;
        if (f.properties) f.properties.count = name ? countByKhet[name] ?? 0 : 0;
      });

      map.addSource(LAYERS.districtsSource, {
        type: "geojson",
        data,
        promoteId: undefined,
      });

      // Remplissage léger violet, plus marqué au survol
      map.addLayer({
        id: LAYERS.districtsFill,
        type: "fill",
        source: LAYERS.districtsSource,
        paint: {
          "fill-color": [
            "case",
            ["boolean", ["feature-state", "hover"], false],
            colors.districtFillHover,
            colors.districtFill,
          ],
          "fill-opacity": 1,
        },
      });

      // Bordure normale (violet sombre)
      map.addLayer({
        id: LAYERS.districtsLine,
        type: "line",
        source: LAYERS.districtsSource,
        paint: {
          "line-color": colors.districtLine,
          "line-width": 1,
        },
      });

      // Bordure GLOW jaune au survol (large + floue grâce au blur)
      map.addLayer({
        id: LAYERS.districtsLineHover,
        type: "line",
        source: LAYERS.districtsSource,
        paint: {
          "line-color": colors.districtLineHover,
          "line-width": [
            "case",
            ["boolean", ["feature-state", "hover"], false],
            3,
            0,
          ],
          "line-blur": 3,
          "line-opacity": [
            "case",
            ["boolean", ["feature-state", "hover"], false],
            1,
            0,
          ],
        },
      });

      // Labels des quartiers — GRANDS + nb de biens (en or), uniquement en dézoom
      map.addLayer({
        id: LAYERS.districtsLabel,
        type: "symbol",
        source: LAYERS.districtsSource,
        maxzoom: 11.6, // disparaît dès qu'on zoome un peu
        layout: {
          "text-field": [
            "format",
            ["coalesce", ["get", "name_en"], ["get", "name"]],
            {},
            "\n",
            {},
            [
              "concat",
              ["to-string", ["get", "count"]],
              ["case", [">", ["get", "count"], 1], " biens", " bien"],
            ],
            { "text-color": colors.districtLineHover, "font-scale": 1.15 },
          ],
          "text-size": ["interpolate", ["linear"], ["zoom"], 9, 20, 11.6, 13],
          "text-font": ["Noto Sans Regular"],
          "text-line-height": 1.3,
          // toujours visibles : ne cèdent pas la place aux pins/POI
          "text-allow-overlap": true,
          "text-ignore-placement": true,
        },
        paint: {
          "text-color": "#ece9f5",
          "text-halo-color": colors.labelHalo,
          "text-halo-width": 2.6,
          "text-halo-blur": 0.4,
        },
      });

      // --- Interactions ---
      const setHover = (id: string | number | null) => {
        if (hoveredId.current != null) {
          map.setFeatureState(
            { source: LAYERS.districtsSource, id: hoveredId.current },
            { hover: false }
          );
        }
        hoveredId.current = id;
        if (id != null) {
          map.setFeatureState(
            { source: LAYERS.districtsSource, id },
            { hover: true }
          );
        }
      };

      map.on("mousemove", LAYERS.districtsFill, (e) => {
        map.getCanvas().style.cursor = "pointer";
        const f = e.features?.[0];
        if (f && f.id !== hoveredId.current) setHover(f.id ?? null);
      });

      map.on("mouseleave", LAYERS.districtsFill, () => {
        map.getCanvas().style.cursor = "";
        setHover(null);
      });

      // Couches POI (métro, hôpitaux, écoles, bus, commerces…) — pilotées par poi-config
      await addPoiLayers(map);

      // ── Pinpoints des biens (réutilise les biens déjà récupérés) ──
      {
        const geoListings = listings.filter((l) => l.lat != null && l.lng != null);
        if (geoListings.length) {
          listingsById.current = new Map(geoListings.map((l) => [l.id, l]));
          map.addSource("listings", {
            type: "geojson",
            data: {
              type: "FeatureCollection",
              features: geoListings.map((l) => ({
                type: "Feature",
                properties: { id: l.id },
                geometry: { type: "Point", coordinates: [l.lng!, l.lat!] },
              })),
            },
          });
          map.addLayer({
            id: "listings-pins",
            type: "circle",
            source: "listings",
            paint: {
              // pins des BIENS : or Lowi, contour fin
              "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 6, 16, 11],
              "circle-color": "#c9a84c",
              "circle-stroke-width": 0.5,
              "circle-stroke-color": "#ffffff",
              "circle-opacity": 1,
            },
          });

          map.on("mouseenter", "listings-pins", async (e) => {
            map.getCanvas().style.cursor = "pointer";
            const f = e.features?.[0];
            if (!f) return;
            const l = listingsById.current.get(f.properties?.id as string);
            if (!l || l.lat == null || l.lng == null) return;
            const pt = e.point;
            setCard({ listing: l, x: pt.x, y: pt.y });
            const prox = await computeProximity(l.lat, l.lng);
            setCard((c) => (c && c.listing.id === l.id ? { ...c, listing: { ...l, proximity: prox } } : c));
          });
          map.on("mouseleave", "listings-pins", () => {
            map.getCanvas().style.cursor = "";
          });
        }
      }

      // Labels quartiers TOUJOURS au-dessus (pins + POI)
      if (map.getLayer(LAYERS.districtsLabel)) map.moveLayer(LAYERS.districtsLabel);

      // Clic → zoom plein cadre sur le quartier
      map.on("click", LAYERS.districtsFill, (e) => {
        const f = e.features?.[0];
        if (!f) return;
        const props = f.properties as KhetProps;
        setCard(null);
        setSelected(props.name_en || props.name || "District");
        const bounds = geometryBounds(f.geometry);
        if (bounds) {
          map.fitBounds(bounds, { padding: 40, duration: 800, maxZoom: 15 });
        }
      });
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  const resetView = () => {
    setSelected(null);
    mapRef.current?.flyTo({
      center: INITIAL_VIEW.center,
      zoom: INITIAL_VIEW.zoom,
      duration: 800,
    });
  };

  const toggleCategory = (categoryId: string, visible: boolean) => {
    setHidden((prev) => {
      const next = new Set(prev);
      if (visible) next.delete(categoryId);
      else next.add(categoryId);
      return next;
    });
    if (mapRef.current) setCategoryVisibility(mapRef.current, categoryId, visible);
  };

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" />

      <Legend hidden={hidden} onToggle={toggleCategory} />

      {/* Property card — top-left of the screen (tooltip) */}
      {card && (
        <div className="absolute left-4 top-4 z-30">
          <div className="relative">
            <button
              onClick={() => setCard(null)}
              className="absolute -right-2 -top-2 z-10 flex h-6 w-6 items-center justify-center rounded-full border border-violet-soft bg-surface text-text-muted hover:text-text"
              aria-label="Close"
            >
              ×
            </button>
            <PropertyCard listing={card.listing} />
          </div>
        </div>
      )}

      {/* Title banner — hidden while a property card is shown (avoid overlap) */}
      {!card && (
        <div className="pointer-events-none absolute left-4 top-4 z-10">
          <h1 className="text-lg font-semibold tracking-wide text-text">
            Bangkok <span className="text-violet-fluo">Real Estate</span>
          </h1>
          {selected && (
            <p className="mt-1 text-sm text-text-muted">
              District: <span className="text-glow">{selected}</span>
            </p>
          )}
        </div>
      )}

      {/* Back to overview */}
      {selected && (
        <button
          onClick={resetView}
          className="absolute bottom-6 left-4 z-10 rounded-md border border-violet-soft bg-surface px-3 py-2 text-sm text-text shadow-violet-glow transition hover:border-violet-fluo"
        >
          ← Overview
        </button>
      )}
    </div>
  );
}

/** Calcule la bbox d'une géométrie Polygon/MultiPolygon. */
function geometryBounds(
  geom: GeoJSON.Geometry
): [[number, number], [number, number]] | null {
  let minX = Infinity,
    minY = Infinity,
    maxX = -Infinity,
    maxY = -Infinity;

  const visit = (coords: number[]) => {
    const [x, y] = coords;
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x > maxX) maxX = x;
    if (y > maxY) maxY = y;
  };
  const walk = (arr: unknown): void => {
    if (Array.isArray(arr)) {
      if (typeof arr[0] === "number") visit(arr as number[]);
      else arr.forEach(walk);
    }
  };

  if (geom.type === "Polygon" || geom.type === "MultiPolygon") {
    walk(geom.coordinates);
  } else {
    return null;
  }
  if (minX === Infinity) return null;
  return [
    [minX, minY],
    [maxX, maxY],
  ];
}
