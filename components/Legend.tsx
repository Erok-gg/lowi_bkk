"use client";

import { POI_CATEGORIES } from "@/config/poi-config";

interface LegendProps {
  hidden: Set<string>;
  onToggle: (categoryId: string, visible: boolean) => void;
}

/**
 * Légende des POI — case à cocher par catégorie (data-driven via poi-config).
 * Cliquer affiche/masque la couche correspondante sur la carte.
 */
export default function Legend({ hidden, onToggle }: LegendProps) {
  return (
    <div className="absolute right-4 top-16 z-10 w-52 rounded-lg border border-violet-soft bg-surface/90 p-3 backdrop-blur">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-muted">
        Calques
      </p>
      <ul className="space-y-1.5">
        {POI_CATEGORIES.map((cat) => {
          const visible = !hidden.has(cat.id);
          return (
            <li key={cat.id}>
              <label className="flex cursor-pointer items-center gap-2 text-sm text-text">
                <input
                  type="checkbox"
                  checked={visible}
                  onChange={(e) => onToggle(cat.id, e.target.checked)}
                  className="accent-violet-fluo"
                />
                <span
                  className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: cat.color }}
                />
                <span className={visible ? "" : "opacity-50"}>{cat.label}</span>
              </label>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
