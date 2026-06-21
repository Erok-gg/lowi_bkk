/**
 * fetch-pois.ts — Génère les POI de Bangkok via Overpass API.
 *
 * Produit deux fichiers (séparés par seuil de zoom d'affichage) :
 *   public/data/pois.geojson        → vue d'ensemble (métro lignes+stations,
 *                                      hôpitaux, écoles, aéroports, gares, monuments)
 *   public/data/pois-local.geojson  → zoom quartier (commerces/malls, arrêts de bus)
 *
 * Chaque feature porte une propriété `category` consommée par config/poi-config.ts.
 *
 * Usage : npm run geo:pois
 */
import { writeFileSync, mkdirSync, readFileSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";

const OVERPASS = "https://overpass-api.de/api/interpreter";
const OUT_DIR = resolve(process.cwd(), "public", "data");

type Group = "overview" | "local";

// Catégories du groupe "local" (n'apparaissent qu'au zoom quartier)
const LOCAL_CATEGORIES = new Set(["mall", "bus_stop"]);

const query = `
[out:json][timeout:300];
area["boundary"="administrative"]["admin_level"="4"]["name:en"="Bangkok"]->.bkk;
(
  // métro / skytrain : stations
  node["railway"="station"](area.bkk);
  // métro / skytrain : lignes — relations de route (couleur + nom officiels)
  relation["route"="subway"](area.bkk);
  relation["route"="light_rail"](area.bkk);
  relation["route"="monorail"](area.bkk);
  relation["route"="tram"](area.bkk);
  // hôpitaux
  node["amenity"="hospital"](area.bkk);
  way["amenity"="hospital"](area.bkk);
  // écoles : amenity=school + capture PAR NOM (intl) — certaines ne sont pas taguées
  nwr["amenity"="school"](area.bkk);
  nwr["name"~"international school",i](area.bkk);
  nwr["name"~"นานาชาติ"](area.bkk);
  // marques connues sans "International" dans le nom (précises pour éviter les collisions)
  nwr["name"~"patana|denla british|brighton college|bangkok prep|american school of bangkok",i](area.bkk);
  // aéroports
  node["aeroway"="aerodrome"](area.bkk);
  way["aeroway"="aerodrome"](area.bkk);
  // monuments / lieux notables (nommés uniquement, filtré en JS)
  node["historic"](area.bkk);
  node["tourism"="attraction"](area.bkk);
  // commerces importants (malls)
  node["shop"="mall"](area.bkk);
  way["shop"="mall"](area.bkk);
  // arrêts de bus
  node["highway"="bus_stop"](area.bkk);
);
out body geom;
`;

interface OsmMember {
  type: "node" | "way" | "relation";
  role?: string;
  geometry?: { lat: number; lon: number }[];
}
interface OsmEl {
  type: "node" | "way" | "relation";
  id: number;
  lat?: number;
  lon?: number;
  tags?: Record<string, string>;
  geometry?: { lat: number; lon: number }[];
  members?: OsmMember[];
}

/**
 * Liste blanche d'écoles internationales connues de Bangkok dont le nom OSM
 * ne contient PAS "International" / "นานาชาติ" (sinon elles seraient ratées).
 * Pour en ajouter une : compléter ce tableau (minuscules, mot/marque distinctif).
 */
const INTL_SCHOOL_KEYWORDS = [
  // uniquement des phrases DISTINCTIVES (pas de sous-chaînes ambiguës type "nist")
  "patana",
  "denla british",
  "brighton college",
  "bangkok prep",
  "american school of bangkok",
];

/**
 * Une école est-elle "internationale" ?
 * Critère 1 : nom EN "International" ou nom TH "นานาชาติ".
 * Critère 2 : appartient à la liste blanche des marques connues (exhaustivité).
 */
function isInternationalSchool(t: Record<string, string>): boolean {
  const fields = [t.name, t["name:en"], t["name:th"]].filter(Boolean).join(" ");
  if (/international|นานาชาติ/i.test(fields)) return true;
  const low = fields.toLowerCase();
  return INTL_SCHOOL_KEYWORDS.some((kw) => low.includes(kw));
}

/** Détermine la catégorie d'un élément ponctuel/surfacique à partir de ses tags. */
function classify(el: OsmEl): string | null {
  const t = el.tags ?? {};
  if (t.railway === "station") {
    const metro =
      t.station === "subway" ||
      t.station === "light_rail" ||
      t.subway === "yes" ||
      t.light_rail === "yes" ||
      t.monorail === "yes";
    return metro ? "metro_station" : "train_station";
  }
  if (t.amenity === "hospital") return "hospital";
  // École : doit "ressembler" à une école (tag amenity OU nom contenant school/โรงเรียน/lycée)
  // ET être internationale. Évite les faux positifs des éléments juste nommés "...นานาชาติ".
  const names = [t.name, t["name:en"], t["name:th"]].filter(Boolean).join(" ");
  const isOtherFeature =
    !!t.highway || !!t.railway || !!t.aeroway || !!t.shop || !!t.public_transport;
  const looksLikeSchool =
    t.amenity === "school" ||
    t.amenity === "college" ||
    t.amenity === "kindergarten" ||
    t.building === "school" ||
    /school|โรงเรียน|école|lycée|lycee/i.test(names);
  if (looksLikeSchool && !isOtherFeature) {
    return isInternationalSchool(t) ? "school" : null;
  }
  if (t.aeroway === "aerodrome") return "airport";
  if (t.shop === "mall") return "mall";
  if (t.highway === "bus_stop") return "bus_stop";
  if (t.historic || t.tourism === "attraction") return "monument";
  return null;
}

/** Centroïde simple (moyenne des sommets) d'une géométrie de way. */
function centroid(geom: { lat: number; lon: number }[]): [number, number] {
  let x = 0,
    y = 0;
  for (const g of geom) {
    x += g.lon;
    y += g.lat;
  }
  return [x / geom.length, y / geom.length];
}

async function main() {
  console.log("→ Requête Overpass (POI de Bangkok)…");
  const res = await fetch(OVERPASS, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      "User-Agent": "bangkok-map/0.1 (personal project)",
      Accept: "application/json",
    },
    body: "data=" + encodeURIComponent(query),
  });
  if (!res.ok) throw new Error(`Overpass HTTP ${res.status} — ${await res.text()}`);
  const data = (await res.json()) as { elements: OsmEl[] };

  const overview: GeoJSON.Feature[] = [];
  const local: GeoJSON.Feature[] = [];
  const counts: Record<string, number> = {};
  const seen = new Set<string>();

  for (const el of data.elements) {
    // Lignes de métro : relations de route → 1 feature LineString par tronçon,
    // avec la couleur officielle (tag colour/color) portée par chaque feature.
    if (
      el.type === "relation" &&
      el.tags?.route &&
      /subway|light_rail|monorail|tram/.test(el.tags.route)
    ) {
      const lineColor = el.tags.colour || el.tags.color || null;
      const lineName = el.tags["name:en"] || el.tags.name || el.tags.ref || null;
      for (const mem of el.members ?? []) {
        if (mem.type !== "way" || !mem.geometry || mem.geometry.length < 2) continue;
        const coords = mem.geometry.map((g) => [g.lon, g.lat]);
        const key =
          "metro_line|" +
          (lineColor ?? "") +
          "|" +
          JSON.stringify(coords[0]) +
          JSON.stringify(coords[coords.length - 1]);
        if (seen.has(key)) continue;
        seen.add(key);
        overview.push({
          type: "Feature",
          properties: { category: "metro_line", name: lineName, color: lineColor },
          geometry: { type: "LineString", coordinates: coords },
        });
        counts["metro_line"] = (counts["metro_line"] ?? 0) + 1;
      }
      continue;
    }

    const category = classify(el);
    if (!category) continue;
    const t = el.tags ?? {};
    const name = t["name:en"] || t.name || null;

    // monuments/malls non nommés = bruit → on ignore
    if ((category === "monument" || category === "mall") && !name) continue;

    // Catégories ponctuelles (les lignes sont gérées plus haut)
    let coord: [number, number] | null = null;
    if (el.type === "node" && el.lon != null && el.lat != null) {
      coord = [el.lon, el.lat];
    } else if (el.geometry && el.geometry.length) {
      coord = centroid(el.geometry);
    }
    if (!coord) continue;

    // dédoublonnage grossier (mêmes nom+catégorie+coord arrondie)
    const key =
      category + "|" + (name ?? "") + "|" + coord.map((c) => Math.round(c * 1000)).join(",");
    if (seen.has(key)) continue;
    seen.add(key);

    const feature: GeoJSON.Feature = {
      type: "Feature",
      properties: { category, name },
      geometry: { type: "Point", coordinates: coord },
    };
    const group: Group = LOCAL_CATEGORIES.has(category) ? "local" : "overview";
    (group === "local" ? local : overview).push(feature);
    counts[category] = (counts[category] ?? 0) + 1;
  }

  // --- Fusion du seed manuel d'écoles internationales (garantit l'exhaustivité) ---
  const SEED = resolve(process.cwd(), "data", "intl-schools-seed.json");
  const STOP = new Set([
    "school", "international", "bangkok", "british", "college", "campus", "the",
  ]);
  const coordsOf = (f: GeoJSON.Feature) =>
    (f.geometry as GeoJSON.Point).coordinates as [number, number];
  if (existsSync(SEED)) {
    const seed = JSON.parse(readFileSync(SEED, "utf8")) as GeoJSON.FeatureCollection;
    const existingSchools = overview.filter((f) => f.properties?.category === "school");
    let added = 0;
    for (const sf of seed.features ?? []) {
      if (sf.properties?.category !== "school") continue;
      const sName = String(sf.properties?.name ?? "");
      const [slng, slat] = coordsOf(sf);
      const tokens = (sName.toLowerCase().match(/[a-zà-ÿ]+/g) ?? []).filter(
        (w) => w.length >= 4 && !STOP.has(w)
      );
      const dup = existingSchools.some((f) => {
        const nm = String(f.properties?.name ?? "").toLowerCase();
        if (tokens.some((tk) => nm.includes(tk))) return true;
        const [lng, lat] = coordsOf(f);
        return Math.abs(lng - slng) < 0.004 && Math.abs(lat - slat) < 0.004;
      });
      if (dup) continue;
      overview.push({
        type: "Feature",
        properties: { category: "school", name: sName, source: "seed" },
        geometry: { type: "Point", coordinates: [slng, slat] },
      });
      added++;
    }
    counts["school"] = (counts["school"] ?? 0) + added;
    console.log(`✓ seed écoles : ${added} ajoutée(s) (${seed.features.length} dans le seed)`);
  }

  mkdirSync(OUT_DIR, { recursive: true });
  writeFileSync(
    resolve(OUT_DIR, "pois.geojson"),
    JSON.stringify({ type: "FeatureCollection", features: overview })
  );
  writeFileSync(
    resolve(OUT_DIR, "pois-local.geojson"),
    JSON.stringify({ type: "FeatureCollection", features: local })
  );

  console.log("✓ POI par catégorie :", counts);
  console.log(
    `✓ overview=${overview.length} → pois.geojson | local=${local.length} → pois-local.geojson`
  );
}

main().catch((e) => {
  console.error("✗ Échec :", e.message);
  process.exit(1);
});
