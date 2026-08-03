/**
 * types.ts — Schéma de listing NORMALISÉ. Source de vérité côté front,
 * aligné sur la table `listings` de Supabase (supabase/schema.sql).
 * Le scraper Python produit des dicts conformes à cette forme (via normalize.py).
 */

export type DealType = "sale" | "rent";
export type Quota = "foreigner" | "thai";
export type Tenure = "freehold" | "leasehold";
export type ListingStatus = "active" | "inactive" | "sold";

export interface ListingImage {
  storagePath: string; // chemin dans Supabase Storage (webp 1024x768)
  width: number;
  height: number;
  order: number;
}

/** Proximité calculée (lib/proximity.ts) — modulaire/interchangeable. */
export interface Proximity {
  nearestSchools: { name: string; distanceM: number }[];
  nearestMetro: { name: string; line?: string; distanceM: number }[];
  nearestBusStop?: { name: string; distanceM: number };
  cbdDistanceM?: number;
}

export interface Listing {
  id: string;
  source: string; // ex: "fazwaz"
  sourceUrl: string;
  title: string;
  dealType: DealType;
  quota: Quota;
  tenure?: Tenure;
  price: number;
  currency: string; // ex: "THB"
  areaSqm: number | null;
  pricePerSqm: number | null;
  bedrooms: number | null;
  bathrooms: number | null;
  condoName: string | null;
  amenities: string[]; // amenities du condominium
  addressRaw: string | null;
  khet: string | null; // quartier (district)
  khwaeng: string | null; // sous-district
  street: string | null;
  lat: number | null;
  lng: number | null;
  status: ListingStatus;
  firstSeen: string; // ISO
  lastSeen: string; // ISO
  images: ListingImage[];
  proximity?: Proximity;
  rawData?: Record<string, unknown>;
  /** Attributs lus dans le DESCRIPTIF de l'annonce (cf. scraper/pipeline/details.py).
   *  Absent tant que la source n'a pas été re-scrapée : toujours tester la valeur. */
  details?: ListingDetails;
}

/**
 * Détails extraits du descriptif. Tous optionnels — la couverture va de 24 %
 * (charges) à 78 % (année de construction), et DDproperty n'en fournit presque
 * aucun (son descriptif parle du projet, pas du lot).
 */
export interface ListingDetails {
  floor?: number | null;
  camFeeThb?: number | null;
  furnished?: string | null;
  views?: string[] | null;
  /** NOMBRE de vues dégagées. « Blocked View » est une anti-vue : conservée dans
   *  `views` pour l'information, mais exclue de ce décompte (284 annonces). */
  viewCount?: number | null;
  /** Tour au sein de la résidence (« A », « B », « 2 »). Deux annonces d'un même
   *  ensemble mais de tours différentes sont des lots forcément distincts. */
  building?: string | null;
  /** Électricité refacturée, THB/kWh. Renseigné seulement quand le bailleur
   *  applique son propre tarif — voir `utilityRate`. */
  elecThbKwh?: number | null;
  /** Eau refacturée, THB/m³. */
  waterThbM3?: number | null;
  /** `government` = tarif public sans marge ; `private` = tarif du bailleur.
   *  UNE colonne pour l'eau ET l'électricité : sur 1 451 annonces qui donnent les
   *  deux, le régime est identique dans 1 445 cas. */
  utilityRate?: "government" | "private" | null;
  quota?: string | null;
  /** Nationalite/structure du VENDEUR — distincte du quota du lot. */
  ownerNationality?: string | null;
  petsAllowed?: boolean | null;
  listedBy?: string | null;
  yearBuilt?: number | null;
  /** L'immeuble est-il LIVRÉ ? Lu du statut annoncé par la source, sinon déduit
   *  de l'année. La prose est ignorée quand une année existe : « Building
   *  completed in 2027 » est un gabarit au passé pour une livraison à venir. */
  delivered?: boolean | null;
  developer?: string | null;
  minRentalMonths?: number | null;
  /** [nom du point de repère, distance en km] */
  landmark?: [string, number] | null;
  unitRef?: string | null;
}

/** Stats agrégées (vues khet_stats / street_stats). */
export interface AreaStats {
  area: string; // nom du quartier ou de la rue
  level: "khet" | "street";
  activeCount: number;
  avgPricePerSqm: number | null;
  medianPricePerSqm: number | null;
  typeDistribution: Record<string, number>;
}

/**
 * Projection d'une annonce pour le TABLEAU — ce que la page envoie réellement
 * au navigateur.
 *
 * Le tableau affiche neuf colonnes, mais recevait des `Listing` complets :
 * images, amenities, `rawData`, proximité, adresse brute… tout traversait le
 * réseau pour n'être jamais lu. Sur 8 000 lignes de vente PLUS les 16 000
 * actives passées en second argument, /for-sale pesait 19,6 Mo par chargement.
 * Cette forme ne porte que les champs affichés ou filtrés.
 */
export interface ListingRow {
  id: string;
  source: string;
  sourceUrl: string;
  title: string;
  condoName: string | null;
  dealType: DealType;
  quota: Quota;
  price: number;
  areaSqm: number | null;
  pricePerSqm: number | null;
  bedrooms: number | null;
  bathrooms: number | null;
  khet: string | null;
}

/** Réduit une annonce complète à sa projection de tableau. */
export function toListingRow(l: Listing): ListingRow {
  return {
    id: l.id,
    source: l.source,
    sourceUrl: l.sourceUrl,
    title: l.title,
    condoName: l.condoName,
    dealType: l.dealType,
    quota: l.quota,
    price: l.price,
    areaSqm: l.areaSqm,
    pricePerSqm: l.pricePerSqm,
    bedrooms: l.bedrooms,
    bathrooms: l.bathrooms,
    khet: l.khet,
  };
}
