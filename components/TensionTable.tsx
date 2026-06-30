"use client";

import Link from "next/link";
import { Fragment, useMemo, useState } from "react";
import {
  computeTensionByKhet,
  computeTensionByStreet,
  type TensionInput,
  type KhetSnapshot,
  type TensionRow,
} from "@/lib/tension";
import type { DealType } from "@/lib/types";

type Key = keyof TensionRow;
const fmt = (v: number | null, suffix = "") => (v == null ? "—" : `${v}${suffix}`);

const DEALS: { v: DealType; label: string }[] = [
  { v: "rent", label: "Rent" },
  { v: "sale", label: "Sale" },
];

const CONF_COLOR: Record<string, string> = {
  high: "text-success",
  medium: "text-warning",
  low: "text-text-faint",
};

export default function TensionTable({
  inputs,
  snapshots,
}: {
  inputs: TensionInput[];
  snapshots: KhetSnapshot[];
}) {
  const [deal, setDeal] = useState<DealType>("rent");
  const [sort, setSort] = useState<{ key: Key; dir: 1 | -1 }>({ key: "tensionScore", dir: -1 });
  const [open, setOpen] = useState<string | null>(null);

  const rows = useMemo(() => computeTensionByKhet(inputs, snapshots, deal), [inputs, snapshots, deal]);

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
    { key: "tensionScore", label: "Tension" },
    { key: "medianTomDays", label: "Time on market" },
    { key: "nActive", label: "#Active" },
    { key: "nDelisted", label: "#Gone" },
    { key: "stockTrend", label: "Stock trend" },
    { key: "confidence", label: "Conf." },
  ];

  const tomCell = (r: { medianTomDays: number | null; medianAgeDays: number | null }) =>
    r.medianTomDays != null ? `${r.medianTomDays} d` : r.medianAgeDays != null ? `${r.medianAgeDays} d*` : "—";
  const trendCell = (v: number | null) => (v == null ? "—" : v < 0 ? "↓" : v > 0 ? "↑" : "→");

  const streetRows = (khet: string) =>
    computeTensionByStreet(inputs, khet, deal).sort(
      (a, b) => (b.tensionScore ?? -Infinity) - (a.tensionScore ?? -Infinity)
    );

  return (
    <div className="h-full overflow-auto p-4">
      <div className="mb-3">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-text">
            Market tension <span className="text-gold">by district</span>
          </h1>
          <div className="flex items-center gap-2">
            <div className="flex overflow-hidden rounded-md border border-violet-soft">
              {DEALS.map((d) => (
                <button
                  key={d.v}
                  onClick={() => setDeal(d.v)}
                  className={`px-3 py-1.5 text-xs transition ${
                    deal === d.v ? "bg-violet/30 text-gold" : "text-text-muted hover:text-text"
                  }`}
                >
                  {d.label}
                </button>
              ))}
            </div>
            <Link href="/tension" className="rounded-md border border-violet-soft px-3 py-1.5 text-sm text-text-muted transition hover:border-violet-fluo hover:text-text">
              Map view →
            </Link>
          </div>
        </div>
        <p className="text-sm text-text-muted">
          Composite 0–100 (higher = tenser): absorption speed, scarcity, stock trend & price momentum.
          Time on market is from de-listed units; <code>*</code> = age of live listings (fallback while history
          is thin). Indicative — strengthens as scrapes accumulate. Click a row for the per-street breakdown.
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
                  className={`cursor-pointer border-b border-violet-soft/40 hover:bg-surface/40 ${
                    r.confidence === "low" ? "opacity-45" : ""
                  }`}>
                  <td className="px-3 py-2 text-text">
                    <span className="mr-1 inline-block w-3 text-text-faint">{expanded ? "▾" : "▸"}</span>
                    {r.khet.replace(" District", "")}
                  </td>
                  <td className={`px-3 py-2 text-right font-medium ${r.tensionScore != null ? "text-gold" : "text-text-faint"}`}>
                    {fmt(r.tensionScore)}
                  </td>
                  <td className="px-3 py-2 text-right text-text-muted">{tomCell(r)}</td>
                  <td className="px-3 py-2 text-right text-text-muted">{r.nActive}</td>
                  <td className="px-3 py-2 text-right text-text-muted">{r.nDelisted}</td>
                  <td className="px-3 py-2 text-right text-text-muted">{trendCell(r.stockTrend)}</td>
                  <td className={`px-3 py-2 text-right text-xs ${CONF_COLOR[r.confidence]}`}>{r.confidence}</td>
                </tr>
                {expanded && streets.length === 0 && (
                  <tr className="border-b border-violet-soft/20 bg-anthracite-deep/40">
                    <td colSpan={7} className="px-3 py-2 pl-8 text-xs text-text-faint">
                      No street-level address recorded for this district yet.
                    </td>
                  </tr>
                )}
                {expanded && streets.map((s) => (
                  <tr key={`${r.khet}-${s.street}`} className="border-b border-violet-soft/20 bg-anthracite-deep/40 text-text-muted">
                    <td className="px-3 py-1.5 pl-8 text-xs">{s.street}</td>
                    <td className={`px-3 py-1.5 text-right text-xs ${s.tensionScore != null ? "text-gold/80" : "text-text-faint"}`}>
                      {fmt(s.tensionScore)}
                    </td>
                    <td className="px-3 py-1.5 text-right text-xs">{tomCell(s)}</td>
                    <td className="px-3 py-1.5 text-right text-xs">{s.nActive}</td>
                    <td className="px-3 py-1.5 text-right text-xs">{s.nDelisted}</td>
                    <td className="px-3 py-1.5 text-right text-xs">—</td>
                    <td className={`px-3 py-1.5 text-right text-xs ${CONF_COLOR[s.confidence]}`}>{s.confidence}</td>
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
