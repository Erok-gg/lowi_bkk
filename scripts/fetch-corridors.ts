/**
 * fetch-corridors.ts — Masques de contexte de la carte :
 *   - lignes de transport EN CONSTRUCTION (Overpass, `railway=construction`)
 *   - zones de développement majeures (seed manuel `data/dev-zones-seed.json`)
 *   - centres d'activité expat (seed manuel `data/expat-zones-seed.json`)
 *   - zones industrielles (Overpass `landuse=industrial`, filtrées par surface)
 *
 * Produit public/data/corridors.geojson avec quatre catégories :
 *   - future_line     : LineString { name, color, opening }
 *   - dev_zone        : Polygon    { name, color, status, note }
 *   - expat_zone      : Polygon    { name, color, note }
 *   - industrial_zone : Polygon    { name, color }
 *
 * BBox volontairement plus large que Bangkok : la Purple Sud finit à Rat Burana
 * mais la Red Rangsit→Thammasat sort en Pathum Thani.
 *
 * Usage : npm run geo:corridors
 */
import { writeFileSync, mkdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const OVERPASS = "https://overpass-api.de/api/interpreter";
const OUT = resolve(process.cwd(), "public", "data", "corridors.geojson");
const SEED = resolve(process.cwd(), "data", "dev-zones-seed.json");
const EXPAT_SEED = resolve(process.cwd(), "data", "expat-zones-seed.json");

// sud, ouest, nord, est
const BBOX = "13.45,100.30,14.12,100.98";

// Surface minimale (km²) d'une zone industrielle pour être affichée : écarte
// les petits ateliers, ne garde que les vrais estates (Lat Krabang, Bang Chan…).
const INDUSTRIAL_MIN_KM2 = 0.25;

const query = `
[out:json][timeout:300];
(
  way["railway"="construction"](${BBOX});
  way["landuse"="industrial"](${BBOX});
);
out body geom;
`;

interface OsmEl {
  type: string;
  id: number;
  tags?: Record<string, string>;
  geometry?: { lat: number; lon: number }[];
}

/** Identification de la ligne par son nom (EN ou TH) → libellé + couleur officielle + horizon. */
const LINES: { re: RegExp; name: string; color: string; opening: string }[] = [
  { re: /orange|ส้ม/i, name: "MRT Orange Line", color: "#F68B1F", opening: "E 2028 · W 2030" },
  { re: /purple|ม่วง/i, name: "MRT Purple Line South ext.", color: "#76338E", opening: "2029" },
  { re: /red|แดง/i, name: "SRT Red Line ext.", color: "#C4342B", opening: "2029" },
  { re: /high[- ]?speed|ความเร็วสูง|hsr|สามสนามบิน/i, name: "HSR 3 airports", color: "#0E7490", opening: "2032+ (pending)" },
  { re: /pink|ชมพู/i, name: "MRT Pink Line ext.", color: "#E86AA6", opening: "—" },
  { re: /yellow|เหลือง/i, name: "MRT Yellow Line ext.", color: "#D9B100", opening: "—" },
];

/** Sous-types de construction ferroviaire qu'on retient (écarte siding/spur industriels). */
const KEEP_CONSTRUCTION = new Set(["subway", "light_rail", "monorail", "rail"]);

const ZONE_COLORS: Record<string, string> = {
  acted: "#3ad97f", // financé/en chantier
  pending: "#e8b84c", // décidé sur le papier seulement
  delivered: "#8f9bb3", // livré (déjà pricé)
};

const EXPAT_COLOR = "#4c9be8";
const INDUSTRIAL_COLOR = "#8a7355";

/** Surface approximative (km²) d'un anneau lng/lat (shoelace + m/deg à 13.7°N). */
function ringAreaKm2(ring: [number, number][]): number {
  const kmPerDegLat = 110.57;
  const kmPerDegLng = 111.32 * Math.cos((13.7 * Math.PI) / 180);
  let sum = 0;
  for (let i = 0; i < ring.length; i++) {
    const [x1, y1] = ring[i];
    const [x2, y2] = ring[(i + 1) % ring.length];
    sum += x1 * y2 - x2 * y1;
  }
  return Math.abs(sum / 2) * kmPerDegLat * kmPerDegLng;
}

async function main() {
  console.log("→ Overpass : lignes en construction…");
  const res = await fetch(OVERPASS, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      "User-Agent": "bangkok-map/0.1 (personal project)",
      Accept: "application/json",
    },
    body: "data=" + encodeURIComponent(query),
  });
  if (!res.ok) throw new Error(`Overpass HTTP ${res.status}`);
  const data = (await res.json()) as { elements: OsmEl[] };

  const features: GeoJSON.Feature[] = [];
  const counts = new Map<string, number>();

  let nIndustrial = 0;
  for (const el of data.elements) {
    if (el.type !== "way" || !el.geometry || el.geometry.length < 2) continue;
    const t = el.tags ?? {};

    // ── zones industrielles (polygones fermés, filtrés par surface) ──
    if (t.landuse === "industrial") {
      const ring = el.geometry.map((g) => [g.lon, g.lat] as [number, number]);
      if (ring.length < 4) continue;
      if (ringAreaKm2(ring) < INDUSTRIAL_MIN_KM2) continue;
      features.push({
        type: "Feature",
        geometry: { type: "Polygon", coordinates: [[...ring, ring[0]]] },
        properties: {
          category: "industrial_zone",
          name: t["name:en"] || t.name || "Industrial area",
          color: INDUSTRIAL_COLOR,
        },
      });
      nIndustrial++;
      continue;
    }

    const sub = t.construction ?? "";
    if (!KEEP_CONSTRUCTION.has(sub)) continue;

    const nameBlob = [t.name, t["name:en"], t["name:th"], t.ref, t.line]
      .filter(Boolean)
      .join(" ");
    const line = LINES.find((L) => L.re.test(nameBlob));
    // sans identification : segment "under construction" générique (gris) —
    // gardé seulement s'il est long (>300 m ~ 4+ points), pour éviter le bruit
    if (!line && el.geometry.length < 4) continue;

    const name = line ? `${line.name} (${line.opening})` : "Rail under construction";
    features.push({
      type: "Feature",
      geometry: {
        type: "LineString",
        coordinates: el.geometry.map((g) => [g.lon, g.lat]),
      },
      properties: {
        category: "future_line",
        name,
        color: line?.color ?? "#8a8fa3",
        opening: line?.opening ?? "",
      },
    });
    counts.set(name, (counts.get(name) ?? 0) + 1);
  }

  console.log("→ Zones de développement (seed manuel)…");
  const seed = JSON.parse(readFileSync(SEED, "utf-8")) as {
    zones: { name: string; status: string; horizon: string; note: string; polygon: [number, number][] }[];
  };
  for (const z of seed.zones) {
    const ring = [...z.polygon, z.polygon[0]]; // ferme l'anneau
    features.push({
      type: "Feature",
      geometry: { type: "Polygon", coordinates: [ring] },
      properties: {
        category: "dev_zone",
        name: z.name,
        color: ZONE_COLORS[z.status] ?? "#8a8fa3",
        status: z.status,
        note: z.note,
      },
    });
  }

  console.log("→ Centres d'activité expat (seed manuel)…");
  const expat = JSON.parse(readFileSync(EXPAT_SEED, "utf-8")) as {
    zones: { name: string; note: string; polygon: [number, number][] }[];
  };
  for (const z of expat.zones) {
    features.push({
      type: "Feature",
      geometry: { type: "Polygon", coordinates: [[...z.polygon, z.polygon[0]]] },
      properties: {
        category: "expat_zone",
        name: z.name,
        color: EXPAT_COLOR,
        note: z.note,
      },
    });
  }

  mkdirSync(resolve(process.cwd(), "public", "data"), { recursive: true });
  writeFileSync(OUT, JSON.stringify({ type: "FeatureCollection", features }));

  console.log(`✓ ${OUT}`);
  console.log(
    `  ${features.length} features — dev:${seed.zones.length} · expat:${expat.zones.length} · industriel:${nIndustrial} :`
  );
  for (const [name, n] of [...counts.entries()].sort((a, b) => b[1] - a[1])) {
    console.log(`  - ${name} : ${n} segments`);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
