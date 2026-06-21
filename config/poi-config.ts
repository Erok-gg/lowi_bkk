/**
 * poi-config.ts — Définition DATA-DRIVEN des catégories de POI.
 * Pour changer une couleur, un seuil de zoom d'apparition, un libellé,
 * ou masquer une catégorie : éditer ce fichier. La carte (components/map/pois.ts)
 * et la légende (composant Legend) itèrent sur ces catégories.
 */
import { theme } from "./theme";
import { POI_ZOOM } from "./map-config";

const c = theme.colors;

export type PoiGeometry = "point" | "line";
export type PoiGroup = "overview" | "local";

export interface PoiCategory {
  id: string; // = valeur de la propriété `category` dans le GeoJSON
  label: string; // libellé légende (FR)
  color: string;
  geometry: PoiGeometry;
  group: PoiGroup; // overview = visible dézoomé ; local = au zoom quartier
  minzoom: number; // seuil d'apparition de la couche
  labelMinzoom?: number; // seuil d'apparition du texte (sinon pas de label)
  radius?: number; // rayon du cercle (point)
  defaultVisible?: boolean; // décoché par défaut dans la légende si false
}

export const POI_CATEGORIES: PoiCategory[] = [
  {
    id: "metro_line",
    label: "Lignes métro/BTS",
    color: c.violetFluo,
    geometry: "line",
    group: "overview",
    minzoom: POI_ZOOM.overview,
  },
  {
    id: "metro_station",
    label: "Stations métro",
    color: "#c084fc",
    geometry: "point",
    group: "overview",
    minzoom: POI_ZOOM.overview,
    labelMinzoom: 12.5,
    radius: 4,
  },
  {
    id: "train_station",
    label: "Gares",
    color: "#60a5fa",
    geometry: "point",
    group: "overview",
    minzoom: POI_ZOOM.overview,
    labelMinzoom: 12.5,
    radius: 4,
  },
  {
    id: "airport",
    label: "Aéroports",
    color: c.blue,
    geometry: "point",
    group: "overview",
    minzoom: POI_ZOOM.overview,
    labelMinzoom: 9,
    radius: 6,
  },
  {
    id: "hospital",
    label: "Hôpitaux",
    color: c.danger,
    geometry: "point",
    group: "overview",
    minzoom: POI_ZOOM.overview,
    labelMinzoom: 13,
    radius: 4,
  },
  {
    id: "school",
    label: "Écoles internationales",
    color: c.warning,
    geometry: "point",
    group: "overview",
    minzoom: 10,
    labelMinzoom: 12.5,
    radius: 4,
  },
  {
    id: "monument",
    label: "Monuments / lieux",
    color: c.success,
    geometry: "point",
    group: "overview",
    minzoom: 11.5,
    labelMinzoom: 13.5,
    radius: 3.5,
    defaultVisible: false,
  },
  {
    id: "mall",
    label: "Commerces (malls)",
    color: "#f472b6",
    geometry: "point",
    group: "local",
    minzoom: POI_ZOOM.district,
    labelMinzoom: 14,
    radius: 4,
  },
  {
    id: "bus_stop",
    label: "Arrêts de bus",
    color: c.textMuted,
    geometry: "point",
    group: "local",
    minzoom: POI_ZOOM.district,
    labelMinzoom: 15.5,
    radius: 2.5,
    defaultVisible: false,
  },
];

/** Fichiers GeoJSON par groupe (servis depuis /public). */
export const POI_SOURCES: Record<PoiGroup, { id: string; url: string }> = {
  overview: { id: "pois", url: "/data/pois.geojson" },
  local: { id: "pois-local", url: "/data/pois-local.geojson" },
};
