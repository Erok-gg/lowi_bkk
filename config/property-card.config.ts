/**
 * property-card.config.ts — Définition DATA-DRIVEN de la fiche bien.
 * Pour réordonner / masquer / renommer un champ : éditer ce fichier.
 * Le composant PropertyCard.tsx se contente d'itérer sur ces sections,
 * sans logique de présentation en dur.
 */
import type { Listing } from "@/lib/types";

export interface FieldDef {
  key: string;
  label: string;
  /** Extrait + formate la valeur à afficher depuis un Listing. */
  get: (l: Listing) => string | null;
  /** Si false, le champ est masqué sans être supprimé. */
  enabled?: boolean;
}

export interface SectionDef {
  id: string;
  title: string;
  /** "fields" = liste de champs ; "list" = liste à puces (ex: amenities). */
  kind: "fields" | "list";
  fields?: FieldDef[];
  /** Pour kind="list". */
  getList?: (l: Listing) => string[];
  enabled?: boolean;
}

const fmtPrice = (l: Listing) =>
  l.price ? `${l.price.toLocaleString("fr-FR")} ${l.currency}` : null;
const fmtArea = (l: Listing) => (l.areaSqm ? `${l.areaSqm} m²` : null);
const fmtDist = (m?: number) =>
  m == null ? null : m < 1000 ? `${m} m` : `${(m / 1000).toFixed(1)} km`;

export const PROPERTY_CARD_SECTIONS: SectionDef[] = [
  {
    id: "summary",
    title: "Le bien",
    kind: "fields",
    fields: [
      { key: "name", label: "Nom", get: (l) => l.condoName || l.title },
      { key: "price", label: "Prix", get: fmtPrice },
      { key: "area", label: "Surface", get: fmtArea },
      {
        key: "ppsqm",
        label: "Prix/m²",
        get: (l) =>
          l.pricePerSqm
            ? `${Math.round(l.pricePerSqm).toLocaleString("fr-FR")} ${l.currency}`
            : null,
      },
      { key: "beds", label: "Chambres", get: (l) => l.bedrooms?.toString() ?? null },
      { key: "baths", label: "SDB", get: (l) => l.bathrooms?.toString() ?? null },
      {
        key: "deal",
        label: "Type",
        get: (l) => (l.dealType === "sale" ? "Vente" : "Location"),
      },
      {
        key: "quota",
        label: "Quota",
        get: (l) => (l.quota === "foreigner" ? "Foreigner" : "Thai"),
      },
    ],
  },
  {
    id: "amenities",
    title: "Amenities du condominium",
    kind: "list",
    getList: (l) => l.amenities ?? [],
  },
  {
    id: "proximity",
    title: "Proximité",
    kind: "fields",
    fields: [
      {
        key: "school1",
        label: "École la + proche",
        get: (l) => {
          const s = l.proximity?.nearestSchools?.[0];
          return s ? `${s.name} (${fmtDist(s.distanceM)})` : null;
        },
      },
      {
        key: "school2",
        label: "2e école",
        get: (l) => {
          const s = l.proximity?.nearestSchools?.[1];
          return s ? `${s.name} (${fmtDist(s.distanceM)})` : null;
        },
      },
      {
        key: "metro1",
        label: "Métro le + proche",
        get: (l) => {
          const m = l.proximity?.nearestMetro?.[0];
          return m ? `${m.name} (${fmtDist(m.distanceM)})` : null;
        },
      },
      {
        key: "metro2",
        label: "2e métro",
        get: (l) => {
          const m = l.proximity?.nearestMetro?.[1];
          return m ? `${m.name} (${fmtDist(m.distanceM)})` : null;
        },
      },
      {
        key: "bus",
        label: "Arrêt de bus",
        get: (l) => {
          const b = l.proximity?.nearestBusStop;
          return b ? `${b.name} (${fmtDist(b.distanceM)})` : null;
        },
      },
      {
        key: "cbd",
        label: "Distance CBD",
        get: (l) => fmtDist(l.proximity?.cbdDistanceM),
      },
    ],
  },
];
