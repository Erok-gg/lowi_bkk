"use client";

import { useSearch, type MapFilters } from "@/components/SearchProvider";

/**
 * MapFilterBand — bandeau de filtres sous la nav, sur la carte principale.
 * Champs libres (prix min/max, chambres, distance métro). S'adapte à Buy/Rent
 * (libellés Price ↔ Rent). Masqué quand le deal est "All".
 */

function Field({
  label,
  value,
  placeholder,
  onChange,
  width = "w-24",
}: {
  label: string;
  value: number | undefined;
  placeholder: string;
  onChange: (v: number | undefined) => void;
  width?: string;
}) {
  return (
    <label className="flex flex-col">
      <span className="mb-0.5 text-[10px] uppercase tracking-wide text-text-faint">{label}</span>
      <input
        type="number"
        inputMode="numeric"
        value={value ?? ""}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))}
        className={`${width} rounded-md border border-violet-soft bg-anthracite-deep px-2 py-1 text-sm text-text outline-none focus:border-violet-fluo`}
      />
    </label>
  );
}

export default function MapFilterBand() {
  const search = useSearch();
  if (!search) return null;
  const { deal, mapFilters, setMapFilters } = search;
  if (deal === "all") return null; // pas de bandeau en mode All

  const isRent = deal === "rent";
  const set = (patch: Partial<MapFilters>) => setMapFilters({ ...mapFilters, ...patch });
  const hasAny =
    mapFilters.priceMin != null ||
    mapFilters.priceMax != null ||
    mapFilters.beds != null ||
    mapFilters.metroMax != null;

  return (
    <div className="absolute left-1/2 top-3 z-20 -translate-x-1/2">
      <div className="flex items-end gap-3 rounded-xl border border-violet-soft bg-surface/95 px-4 py-2 shadow-xl backdrop-blur">
        <Field
          label={isRent ? "Min rent" : "Min price"}
          value={mapFilters.priceMin}
          placeholder={isRent ? "฿/mo" : "฿"}
          onChange={(v) => set({ priceMin: v })}
          width="w-28"
        />
        <Field
          label={isRent ? "Max rent" : "Max price"}
          value={mapFilters.priceMax}
          placeholder={isRent ? "฿/mo" : "฿"}
          onChange={(v) => set({ priceMax: v })}
          width="w-28"
        />
        <Field
          label="Beds"
          value={mapFilters.beds}
          placeholder="any"
          onChange={(v) => set({ beds: v })}
          width="w-16"
        />
        <Field
          label="Metro ≤ (m)"
          value={mapFilters.metroMax}
          placeholder="m"
          onChange={(v) => set({ metroMax: v })}
          width="w-20"
        />
        {hasAny && (
          <button
            onClick={() => setMapFilters({})}
            className="mb-1 rounded-md px-2 py-1 text-xs text-text-muted transition hover:text-text"
          >
            Clear
          </button>
        )}
      </div>
    </div>
  );
}
