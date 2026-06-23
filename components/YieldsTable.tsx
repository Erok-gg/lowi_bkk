"use client";

import { useMemo, useState } from "react";
import type { YieldRow } from "@/lib/yields";

type Key = keyof YieldRow;
const fmt = (v: number | null) => (v == null ? "—" : Math.round(v).toLocaleString("fr-FR"));

export default function YieldsTable({ rows }: { rows: YieldRow[] }) {
  const [sort, setSort] = useState<{ key: Key; dir: 1 | -1 }>({ key: "grossYieldPct", dir: -1 });

  const sorted = useMemo(() => {
    const out = [...rows];
    const { key, dir } = sort;
    out.sort((a, b) => {
      if (key === "khet") return a.khet < b.khet ? -dir : a.khet > b.khet ? dir : 0;
      const va = (a[key] ?? -Infinity) as number;
      const vb = (b[key] ?? -Infinity) as number;
      return va < vb ? -dir : va > vb ? dir : 0;
    });
    return out;
  }, [rows, sort]);

  const setKey = (key: Key) =>
    setSort((s) => (s.key === key ? { key, dir: (s.dir * -1) as 1 | -1 } : { key, dir: -1 }));
  const arrow = (key: Key) => (sort.key === key ? (sort.dir === 1 ? " ▲" : " ▼") : "");

  const cols: { key: Key; label: string }[] = [
    { key: "khet", label: "Quartier" },
    { key: "nSale", label: "Nb vente" },
    { key: "nRent", label: "Nb loc." },
    { key: "saleMedianPsqm", label: "Prix vente/m²" },
    { key: "rentMedianPsqm", label: "Loyer/m² (mois)" },
    { key: "grossYieldPct", label: "Rendement brut" },
  ];

  return (
    <div className="h-full overflow-auto p-4">
      <div className="mb-3">
        <h1 className="text-lg font-semibold text-text">
          Rendements <span className="text-gold">par quartier</span>
        </h1>
        <p className="text-sm text-text-muted">
          Rendement brut ≈ loyer/m² × 12 ÷ prix-vente/m² (médianes). Indicatif —
          plus fiable quand un quartier a assez d'annonces vente ET location.
        </p>
      </div>
      <table className="w-full max-w-3xl border-collapse text-sm">
        <thead>
          <tr className="border-b border-violet-soft text-left text-text-muted">
            {cols.map((c) => (
              <th key={c.key} onClick={() => setKey(c.key)}
                className={`cursor-pointer select-none px-3 py-2 font-medium hover:text-text ${c.key === "khet" ? "" : "text-right"}`}>
                {c.label}{arrow(c.key)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <tr key={r.khet} className="border-b border-violet-soft/40 hover:bg-surface/40">
              <td className="px-3 py-2 text-text">{r.khet.replace(" District", "")}</td>
              <td className="px-3 py-2 text-right text-text-muted">{r.nSale}</td>
              <td className="px-3 py-2 text-right text-text-muted">{r.nRent}</td>
              <td className="px-3 py-2 text-right">{fmt(r.saleMedianPsqm)}</td>
              <td className="px-3 py-2 text-right">{fmt(r.rentMedianPsqm)}</td>
              <td className={`px-3 py-2 text-right font-medium ${r.grossYieldPct ? "text-gold" : "text-text-faint"}`}>
                {r.grossYieldPct != null ? `${r.grossYieldPct} %` : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
