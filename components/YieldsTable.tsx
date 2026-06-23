"use client";

import { Fragment, useMemo, useState } from "react";
import type { YieldRow } from "@/lib/yields";
import { computeYieldsByStreet } from "@/lib/yields";
import type { Listing } from "@/lib/types";

type Key = keyof YieldRow;
const fmt = (v: number | null) => (v == null ? "—" : Math.round(v).toLocaleString("en-US"));

export default function YieldsTable({ rows, listings }: { rows: YieldRow[]; listings: Listing[] }) {
  const [sort, setSort] = useState<{ key: Key; dir: 1 | -1 }>({ key: "grossYieldPct", dir: -1 });
  const [open, setOpen] = useState<string | null>(null);

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
    { key: "khet", label: "District" },
    { key: "nSale", label: "#Sale" },
    { key: "nRent", label: "#Rent" },
    { key: "saleMedianPsqm", label: "Sale price/m²" },
    { key: "rentMedianPsqm", label: "Rent/m² (month)" },
    { key: "grossYieldPct", label: "Gross yield" },
  ];

  const streetRows = (khet: string) =>
    computeYieldsByStreet(listings, khet).sort(
      (a, b) => (b.grossYieldPct ?? -Infinity) - (a.grossYieldPct ?? -Infinity)
    );

  return (
    <div className="h-full overflow-auto p-4">
      <div className="mb-3">
        <h1 className="text-lg font-semibold text-text">
          Yields <span className="text-gold">by district</span>
        </h1>
        <p className="text-sm text-text-muted">
          Gross yield ≈ rent/m² × 12 ÷ sale price/m² (medians). Indicative — more
          reliable when a district has enough sale AND rent listings. Click a row
          for the per-street breakdown.
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
          {sorted.map((r) => {
            const expanded = open === r.khet;
            const streets = expanded ? streetRows(r.khet) : [];
            return (
              <Fragment key={r.khet}>
                <tr
                  onClick={() => setOpen(expanded ? null : r.khet)}
                  className="cursor-pointer border-b border-violet-soft/40 hover:bg-surface/40">
                  <td className="px-3 py-2 text-text">
                    <span className="mr-1 inline-block w-3 text-text-faint">{expanded ? "▾" : "▸"}</span>
                    {r.khet.replace(" District", "")}
                  </td>
                  <td className="px-3 py-2 text-right text-text-muted">{r.nSale}</td>
                  <td className="px-3 py-2 text-right text-text-muted">{r.nRent}</td>
                  <td className="px-3 py-2 text-right">{fmt(r.saleMedianPsqm)}</td>
                  <td className="px-3 py-2 text-right">{fmt(r.rentMedianPsqm)}</td>
                  <td className={`px-3 py-2 text-right font-medium ${r.grossYieldPct ? "text-gold" : "text-text-faint"}`}>
                    {r.grossYieldPct != null ? `${r.grossYieldPct} %` : "—"}
                  </td>
                </tr>
                {expanded && streets.length === 0 && (
                  <tr key={`${r.khet}-empty`} className="border-b border-violet-soft/20 bg-anthracite-deep/40">
                    <td colSpan={6} className="px-3 py-2 pl-8 text-xs text-text-faint">
                      No street-level address recorded for this district yet.
                    </td>
                  </tr>
                )}
                {expanded && streets.map((s) => (
                  <tr key={`${r.khet}-${s.street}`} className="border-b border-violet-soft/20 bg-anthracite-deep/40 text-text-muted">
                    <td className="px-3 py-1.5 pl-8 text-xs">{s.street}</td>
                    <td className="px-3 py-1.5 text-right text-xs">{s.nSale}</td>
                    <td className="px-3 py-1.5 text-right text-xs">{s.nRent}</td>
                    <td className="px-3 py-1.5 text-right text-xs">{fmt(s.saleMedianPsqm)}</td>
                    <td className="px-3 py-1.5 text-right text-xs">{fmt(s.rentMedianPsqm)}</td>
                    <td className={`px-3 py-1.5 text-right text-xs ${s.grossYieldPct ? "text-gold/80" : "text-text-faint"}`}>
                      {s.grossYieldPct != null ? `${s.grossYieldPct} %` : "—"}
                    </td>
                  </tr>
                ))}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
