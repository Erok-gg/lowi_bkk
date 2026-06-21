/**
 * proximity.ts — Resolver de proximité générique (côté client).
 * Calcule, pour un point (lat/lng), les POI les plus proches par catégorie
 * + la distance au CBD. Catégories interchangeables (lit les POI de /public).
 */
import type { Proximity } from "@/lib/types";

// CBD de Bangkok (zone Sathorn/Silom — cœur d'affaires). Ajustable.
const CBD: [number, number] = [100.534, 13.724]; // [lng, lat]

interface PoiPoint {
  category: string;
  name: string | null;
  lng: number;
  lat: number;
}

let cache: PoiPoint[] | null = null;
let loading: Promise<PoiPoint[]> | null = null;

function haversineM(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6371000;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLng = ((lng2 - lng1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLng / 2) ** 2;
  return Math.round(2 * R * Math.asin(Math.sqrt(a)));
}

async function loadPois(): Promise<PoiPoint[]> {
  if (cache) return cache;
  if (loading) return loading;
  loading = (async () => {
    const out: PoiPoint[] = [];
    for (const url of ["/data/pois.geojson", "/data/pois-local.geojson"]) {
      try {
        const res = await fetch(url);
        if (!res.ok) continue;
        const gj = (await res.json()) as GeoJSON.FeatureCollection;
        for (const f of gj.features) {
          if (f.geometry?.type !== "Point") continue;
          const [lng, lat] = f.geometry.coordinates as [number, number];
          out.push({
            category: (f.properties?.category as string) ?? "",
            name: (f.properties?.name as string) ?? null,
            lng,
            lat,
          });
        }
      } catch {
        /* ignore */
      }
    }
    cache = out;
    return out;
  })();
  return loading;
}

function nearest(points: PoiPoint[], lat: number, lng: number, n: number) {
  return points
    .map((p) => ({ name: p.name ?? "—", distanceM: haversineM(lat, lng, p.lat, p.lng) }))
    .sort((a, b) => a.distanceM - b.distanceM)
    .slice(0, n);
}

export async function computeProximity(lat: number, lng: number): Promise<Proximity> {
  const pois = await loadPois();
  const schools = pois.filter((p) => p.category === "school");
  const metros = pois.filter((p) => p.category === "metro_station");
  const buses = pois.filter((p) => p.category === "bus_stop");
  return {
    nearestSchools: nearest(schools, lat, lng, 2),
    nearestMetro: nearest(metros, lat, lng, 2),
    nearestBusStop: nearest(buses, lat, lng, 1)[0],
    cbdDistanceM: haversineM(lat, lng, CBD[1], CBD[0]),
  };
}
