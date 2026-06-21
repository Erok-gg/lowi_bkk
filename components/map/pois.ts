/**
 * pois.ts — Ajout et contrôle des couches POI sur la carte MapLibre.
 * Entièrement piloté par config/poi-config.ts (aucune couleur/zoom en dur ici).
 */
import type { Map as MapLibreMap, MapGeoJSONFeature } from "maplibre-gl";
import maplibregl from "maplibre-gl";
import { getMapColors } from "@/config/theme";
import {
  POI_CATEGORIES,
  POI_SOURCES,
  type PoiCategory,
} from "@/config/poi-config";

const circleLayerId = (id: string) => `poi-${id}`;
const labelLayerId = (id: string) => `poi-${id}-label`;

/** Charge les sources GeoJSON puis ajoute une couche par catégorie. */
export async function addPoiLayers(map: MapLibreMap) {
  const colors = getMapColors();

  // Charge les 2 sources (overview + local)
  for (const src of Object.values(POI_SOURCES)) {
    if (map.getSource(src.id)) continue;
    try {
      const res = await fetch(src.url);
      if (!res.ok) {
        console.warn(`POI source ${src.url} indisponible — lancer \`npm run geo:pois\``);
        continue;
      }
      map.addSource(src.id, { type: "geojson", data: await res.json() });
    } catch {
      console.warn(`POI source ${src.url} : échec de chargement`);
    }
  }

  for (const cat of POI_CATEGORIES) {
    const src = POI_SOURCES[cat.group];
    if (!map.getSource(src.id)) continue;
    const visible = cat.defaultVisible === false ? "none" : "visible";

    if (cat.geometry === "line") {
      map.addLayer({
        id: circleLayerId(cat.id),
        type: "line",
        source: src.id,
        filter: ["==", ["get", "category"], cat.id],
        minzoom: cat.minzoom,
        layout: { visibility: visible, "line-cap": "round", "line-join": "round" },
        paint: {
          // couleur officielle portée par la feature (tag OSM colour) ; repli config
          "line-color": ["coalesce", ["get", "color"], cat.color],
          "line-width": ["interpolate", ["linear"], ["zoom"], 10, 2, 15, 4],
          "line-opacity": 0.95,
        },
      });
      continue;
    }

    // Catégorie de points : un cercle + (optionnel) un label texte
    map.addLayer({
      id: circleLayerId(cat.id),
      type: "circle",
      source: src.id,
      filter: ["==", ["get", "category"], cat.id],
      minzoom: cat.minzoom,
      layout: { visibility: visible },
      paint: {
        "circle-radius": cat.radius ?? 4,
        "circle-color": cat.color,
        "circle-stroke-width": 1,
        "circle-stroke-color": colors.background,
        "circle-opacity": 0.95,
      },
    });

    if (cat.labelMinzoom != null) {
      map.addLayer({
        id: labelLayerId(cat.id),
        type: "symbol",
        source: src.id,
        filter: ["==", ["get", "category"], cat.id],
        minzoom: cat.labelMinzoom,
        layout: {
          visibility: visible,
          "text-field": ["get", "name"],
          "text-size": 10,
          "text-font": ["Noto Sans Regular"],
          "text-offset": [0, 0.9],
          "text-anchor": "top",
          "text-optional": true,
        },
        paint: {
          "text-color": cat.color,
          "text-halo-color": colors.labelHalo,
          "text-halo-width": 1.2,
        },
      });
    }
  }

  attachPoiPopups(map);
}

/** Affiche/masque toutes les couches d'une catégorie (légende). */
export function setCategoryVisibility(
  map: MapLibreMap,
  categoryId: string,
  visible: boolean
) {
  const v = visible ? "visible" : "none";
  for (const id of [circleLayerId(categoryId), labelLayerId(categoryId)]) {
    if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", v);
  }
}

/** Popup au survol d'un POI ponctuel (nom + catégorie). */
function attachPoiPopups(map: MapLibreMap) {
  const popup = new maplibregl.Popup({
    closeButton: false,
    closeOnClick: false,
    offset: 10,
  });
  const labelById = new Map(POI_CATEGORIES.map((c) => [c.id, c.label]));

  const pointLayers = POI_CATEGORIES.filter((c) => c.geometry === "point").map((c) =>
    circleLayerId(c.id)
  );

  for (const layerId of pointLayers) {
    if (!map.getLayer(layerId)) continue;
    map.on("mouseenter", layerId, (e) => {
      map.getCanvas().style.cursor = "pointer";
      const f = e.features?.[0] as MapGeoJSONFeature | undefined;
      if (!f || f.geometry.type !== "Point") return;
      const name = (f.properties?.name as string) || "—";
      const cat = labelById.get(f.properties?.category as string) ?? "";
      const [lng, lat] = f.geometry.coordinates as [number, number];
      popup
        .setLngLat([lng, lat])
        .setHTML(
          `<div style="padding:6px 10px"><div style="font-weight:600">${name}</div>` +
            `<div style="font-size:11px;opacity:.7">${cat}</div></div>`
        )
        .addTo(map);
    });
    map.on("mouseleave", layerId, () => {
      map.getCanvas().style.cursor = "";
      popup.remove();
    });
  }
}
