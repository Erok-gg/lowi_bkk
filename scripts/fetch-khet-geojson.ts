/**
 * fetch-khet-geojson.ts — Génère data/bangkok-khet.geojson via Overpass API.
 *
 * Récupère les 50 Khet (districts) de Bangkok (boundary=administrative,
 * admin_level=6 dans le schéma OSM Thailande), assemble les relations en
 * polygones (osmtogeojson) et écrit un GeoJSON allégé.
 *
 * Usage : npm run geo:khet
 */
import { writeFileSync, mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import osmtogeojson from "osmtogeojson";

const OVERPASS = "https://overpass-api.de/api/interpreter";
// Sert depuis /public pour être accessible via fetch("/data/...") côté carte.
const OUT = resolve(process.cwd(), "public", "data", "bangkok-khet.geojson");

// admin_level des Khet (districts) de Bangkok. Khwaeng (sous-districts) = 8.
const KHET_ADMIN_LEVEL = 6;

const query = `
[out:json][timeout:180];
relation["boundary"="administrative"]["admin_level"="4"]["name:en"="Bangkok"];
map_to_area->.bkk;
relation["boundary"="administrative"]["admin_level"="${KHET_ADMIN_LEVEL}"](area.bkk);
out body;
>;
out skel qt;
`;

async function main() {
  console.log("→ Requête Overpass (Khet de Bangkok)…");
  const res = await fetch(OVERPASS, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      "User-Agent": "bangkok-map/0.1 (personal project)",
      Accept: "application/json",
    },
    body: "data=" + encodeURIComponent(query),
  });
  if (!res.ok) {
    throw new Error(`Overpass HTTP ${res.status} — ${await res.text()}`);
  }
  const osm = await res.json();

  console.log("→ Conversion OSM → GeoJSON…");
  const gj = osmtogeojson(osm) as GeoJSON.FeatureCollection;

  // Garde uniquement les polygones de districts, allège les propriétés
  const features = gj.features
    .filter(
      (f) =>
        (f.geometry?.type === "Polygon" || f.geometry?.type === "MultiPolygon") &&
        f.properties?.admin_level === String(KHET_ADMIN_LEVEL)
    )
    .map((f, i) => {
      const p = f.properties ?? {};
      return {
        type: "Feature" as const,
        id: i,
        properties: {
          name: p.name ?? p["name:en"] ?? `khet-${i}`,
          name_en: p["name:en"] ?? p.name ?? null,
          name_th: p["name:th"] ?? null,
          ref: p.ref ?? null,
        },
        geometry: f.geometry,
      };
    });

  if (features.length === 0) {
    throw new Error(
      "Aucun district trouvé — vérifier KHET_ADMIN_LEVEL (essayer 8) ou la dispo d'Overpass."
    );
  }

  const out: GeoJSON.FeatureCollection = {
    type: "FeatureCollection",
    features,
  };

  mkdirSync(dirname(OUT), { recursive: true });
  writeFileSync(OUT, JSON.stringify(out));
  console.log(`✓ ${features.length} quartiers écrits → ${OUT}`);
}

main().catch((e) => {
  console.error("✗ Échec :", e.message);
  process.exit(1);
});
