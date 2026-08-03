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
  l.price ? `${l.price.toLocaleString("en-US")} ${l.currency}` : null;
const fmtArea = (l: Listing) => (l.areaSqm ? `${l.areaSqm} m²` : null);
const fmtDist = (m?: number) =>
  m == null ? null : m < 1000 ? `${m} m` : `${(m / 1000).toFixed(1)} km`;

export const PROPERTY_CARD_SECTIONS: SectionDef[] = [
  {
    id: "summary",
    title: "Property",
    kind: "fields",
    fields: [
      { key: "name", label: "Name", get: (l) => l.condoName || l.title },
      { key: "price", label: "Price", get: fmtPrice },
      { key: "area", label: "Area", get: fmtArea },
      {
        key: "ppsqm",
        label: "Price/m²",
        get: (l) =>
          l.pricePerSqm
            ? `${Math.round(l.pricePerSqm).toLocaleString("en-US")} ${l.currency}`
            : null,
      },
      { key: "beds", label: "Beds", get: (l) => l.bedrooms?.toString() ?? null },
      { key: "baths", label: "Baths", get: (l) => l.bathrooms?.toString() ?? null },
      {
        key: "deal",
        label: "Type",
        get: (l) => (l.dealType === "sale" ? "For sale" : "For rent"),
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
    title: "Condominium amenities",
    kind: "list",
    getList: (l) => l.amenities ?? [],
  },
  {
    id: "proximity",
    title: "Proximity",
    kind: "fields",
    fields: [
      {
        key: "school1",
        label: "Nearest school",
        get: (l) => {
          const s = l.proximity?.nearestSchools?.[0];
          return s ? `${s.name} (${fmtDist(s.distanceM)})` : null;
        },
      },
      {
        key: "school2",
        label: "2nd school",
        get: (l) => {
          const s = l.proximity?.nearestSchools?.[1];
          return s ? `${s.name} (${fmtDist(s.distanceM)})` : null;
        },
      },
      {
        key: "metro1",
        label: "Nearest metro",
        get: (l) => {
          const m = l.proximity?.nearestMetro?.[0];
          return m ? `${m.name} (${fmtDist(m.distanceM)})` : null;
        },
      },
      {
        key: "metro2",
        label: "2nd metro",
        get: (l) => {
          const m = l.proximity?.nearestMetro?.[1];
          return m ? `${m.name} (${fmtDist(m.distanceM)})` : null;
        },
      },
      {
        key: "bus",
        label: "Bus stop",
        get: (l) => {
          const b = l.proximity?.nearestBusStop;
          return b ? `${b.name} (${fmtDist(b.distanceM)})` : null;
        },
      },
      {
        key: "cbd",
        label: "CBD distance",
        get: (l) => fmtDist(l.proximity?.cbdDistanceM),
      },
    ],
  },
  /**
   * Détails lus dans le DESCRIPTIF de l'annonce (scraper/pipeline/details.py).
   * Placés EN DERNIER et volontairement bruts : la couverture va de 24 %
   * (charges) à 78 % (année de construction), et chaque champ absent disparaît
   * tout seul — PropertyCard filtre les valeurs nulles, et la section entière
   * ne s'affiche pas si tout est vide.
   */
  {
    id: "details",
    title: "# From listing text",
    kind: "fields",
    fields: [
      { key: "d_floor", label: "# floor", get: (l) =>
          l.details?.floor != null ? `${l.details.floor}` : null },
      { key: "d_building", label: "# building", get: (l) => l.details?.building ?? null },
      // Année seule si l'immeuble est debout ; sinon on dit que la livraison est
      // À VENIR — un « 2028 » nu se lit comme une date de construction passée.
      { key: "d_year", label: "# built", get: (l) => {
          const { yearBuilt: y, delivered: liv } = l.details ?? {};
          if (y == null) return liv == null ? null : liv ? "delivered" : "not delivered yet";
          return liv === false ? `${y} (not delivered yet)` : `${y}`;
        } },
      { key: "d_furnished", label: "# furnished", get: (l) => l.details?.furnished ?? null },
      { key: "d_cam", label: "# CAM fee", get: (l) =>
          l.details?.camFeeThb != null
            ? `${l.details.camFeeThb.toLocaleString("en-US")} THB/mo`
            : null },
      { key: "d_quota", label: "# quota", get: (l) => l.details?.quota ?? null },
      { key: "d_owner", label: "# owner", get: (l) => l.details?.ownerNationality ?? null },
      // NOMBRE puis libellés : le compte se compare d'une annonce à l'autre, le
      // libellé reste un commentaire lisible sans qu'on ait à décider si
      // « Sky » et « Horizon View » sont une vue ou deux.
      { key: "d_views", label: "# views", get: (l) => {
          const v = l.details?.views;
          if (!v?.length) return null;
          const n = l.details?.viewCount;
          return n != null ? `${n}; ${v.join(", ")}` : v.join(", ");
        } },
      // Tarifs des charges : « government » = tarif public refacturé sans marge.
      // Un tarif chiffré est toujours celui du bailleur, donc une marge.
      { key: "d_utilities", label: "# utilities", get: (l) => {
          const { utilityRate: r, elecThbKwh: e, waterThbM3: w } = l.details ?? {};
          if (r == null) return null;
          if (r === "government") return "government rate";
          const p = [e != null ? `${e} THB/kWh` : null, w != null ? `${w} THB/m³` : null];
          return `landlord rate${p.some(Boolean) ? ` — ${p.filter(Boolean).join(", ")}` : ""}`;
        } },
      { key: "d_pets", label: "# pets", get: (l) =>
          l.details?.petsAllowed == null
            ? null
            : l.details.petsAllowed ? "allowed" : "not allowed" },
      { key: "d_listedby", label: "# listed by", get: (l) => l.details?.listedBy ?? null },
      { key: "d_developer", label: "# developer", get: (l) => l.details?.developer ?? null },
      { key: "d_minrent", label: "# min. rental", get: (l) =>
          l.details?.minRentalMonths != null ? `${l.details.minRentalMonths} mo` : null },
      { key: "d_landmark", label: "# landmark", get: (l) =>
          l.details?.landmark ? `${l.details.landmark[0]} (${l.details.landmark[1]} km)` : null },
      { key: "d_unitref", label: "# unit ref", get: (l) => l.details?.unitRef ?? null },
    ],
  },
];
