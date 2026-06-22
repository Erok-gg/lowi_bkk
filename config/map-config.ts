/**
 * map-config.ts — Configuration de la carte (source unique).
 * Pour changer le fond de carte, le centrage, les seuils de zoom des POI :
 * tout est ici. Le composant MapView ne fait que consommer ces valeurs.
 *
 * Source de tuiles : OpenFreeMap (gratuit, sans clé API, schéma OpenMapTiles).
 * Style de base sombre, qu'on re-teinte ensuite avec notre palette (getMapColors).
 * Pour swapper de fournisseur (MapTiler, Stadia...), changer BASE_STYLE_URL.
 */
import { getMapColors } from "./theme";
import type { Map as MapLibreMap } from "maplibre-gl";

export const BASE_STYLE_URL = "https://tiles.openfreemap.org/styles/dark";

/** Vue initiale : Bangkok entier. */
export const INITIAL_VIEW = {
  center: [100.523, 13.736] as [number, number], // [lng, lat] centre BKK
  zoom: 10.2,
  minZoom: 9,
  maxZoom: 18,
};

/** Bornes pour empêcher de se perdre loin de Bangkok. */
export const MAX_BOUNDS: [[number, number], [number, number]] = [
  [100.2, 13.45], // SW
  [100.95, 14.05], // NE
];

/**
 * Seuils de zoom d'apparition des couches POI.
 * Dézoomé : métro, eau, rues, monuments, stations, hôpitaux, écoles, aéroports, train.
 * Zoomé sur un quartier : + commerces + arrêts de bus.
 */
export const POI_ZOOM = {
  overview: 9, // métro, hôpitaux, écoles, aéroports, gares — visibles d'emblée
  district: 13.5, // commerces, arrêts de bus — au zoom quartier
};

/** IDs des sources/couches qu'on ajoute par-dessus le fond. */
export const LAYERS = {
  districtsSource: "khet",
  districtsFill: "khet-fill",
  districtsLine: "khet-line",
  districtsLineHover: "khet-line-hover",
  districtsLabel: "khet-label",
};

/**
 * Re-teinte le fond de carte OpenFreeMap vers notre palette
 * (fond anthracite, eau bleu sombre). Appelée après le chargement du style.
 */
export function applyThemeToBaseStyle(map: MapLibreMap) {
  const colors = getMapColors();
  const style = map.getStyle();
  if (!style?.layers) return;

  for (const layer of style.layers) {
    try {
      if (layer.type === "background") {
        map.setPaintProperty(layer.id, "background-color", colors.background);
      } else if (/water|ocean|sea/i.test(layer.id) && layer.type === "fill") {
        map.setPaintProperty(layer.id, "fill-color", colors.water);
      } else if (/boundary|admin/i.test(layer.id)) {
        // masque les frontières admin du fond → évite le double trait avec nos quartiers
        map.setLayoutProperty(layer.id, "visibility", "none");
      }
    } catch {
      // certaines couches n'ont pas la propriété — on ignore
    }
  }
}
