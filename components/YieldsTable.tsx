"use client";

import Link from "next/link";
import { Fragment, useMemo, useState } from "react";
import type { BedStratum, YieldRow } from "@/lib/yields";
import {
  BED_STRATA,
  LOW_SAMPLE_CONDOS,
  MIN_PAIRED_CONDOS,
  computeYieldsByKhet,
  computeYieldsByStreet,
} from "@/lib/yields";
import type { Listing } from "@/lib/types";

type Key = keyof YieldRow;
const fmt = (v: number | null) => (v == null ? "—" : Math.round(v).toLocaleString("en-US"));

const STRATUM_LABEL: Record<BedStratum, string> = {
  "0-1": "Studio–1BR",
  "2": "2BR",
  "3+": "3BR+",
  all: "All (mixed)",
};

export default function YieldsTable({ listings }: { listings: Listing[] }) {
  const [sort, setSort] = useState<{ key: Key; dir: 1 | -1 }>({ key: "grossYieldPct", dir: -1 });
  const [open, setOpen] = useState<string | null>(null);
  const [stratum, setStratum] = useState<BedStratum>("0-1");
  const [showMethod, setShowMethod] = useState(false);

  const rows = useMemo(() => computeYieldsByKhet(listings, stratum), [listings, stratum]);

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

  const cols: { key: Key; label: string; title?: string }[] = [
    { key: "khet", label: "District" },
    { key: "nSaleCondos", label: "Sale bldgs", title: "Distinct condos with sale listings (1 building = 1 vote)" },
    { key: "nRentCondos", label: "Rent bldgs", title: "Distinct condos with rent listings" },
    { key: "nPairedCondos", label: "Paired", title: "Condos with BOTH sale and rent → within-condo yield" },
    { key: "saleMedianPsqm", label: "Sale price/m²", title: "Median across condo medians (double median)" },
    { key: "rentMedianPsqm", label: "Rent/m² (month)", title: "Median across condo medians (double median)" },
    { key: "grossYieldPct", label: "Gross yield" },
  ];

  const streetRows = (khet: string) =>
    computeYieldsByStreet(listings, khet, stratum).sort(
      (a, b) => (b.grossYieldPct ?? -Infinity) - (a.grossYieldPct ?? -Infinity)
    );

  return (
    <div className="h-full overflow-auto p-4">
      <div className="mb-3 max-w-4xl">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-text">
            Yields <span className="text-gold">by district</span>
          </h1>
          <Link href="/yields-map" className="rounded-md border border-violet-soft px-3 py-1.5 text-sm text-text-muted transition hover:border-violet-fluo hover:text-text">
            Map view →
          </Link>
        </div>

        {/* Strate de chambres : comparer à panier constant */}
        <div className="mt-2 flex items-center gap-2">
          <span className="text-xs text-text-muted">Segment</span>
          <div className="flex overflow-hidden rounded-md border border-violet-soft">
            {BED_STRATA.map((s) => (
              <button key={s} onClick={() => setStratum(s)}
                className={`px-2.5 py-1 text-xs transition ${
                  stratum === s ? "bg-violet/30 text-gold" : "text-text-muted hover:text-text"
                }`}>
                {STRATUM_LABEL[s]}
              </button>
            ))}
          </div>
          <button onClick={() => setShowMethod((v) => !v)}
            className="ml-auto text-xs text-violet-fluo underline-offset-2 hover:underline">
            {showMethod ? "Hide method" : "How is this computed?"}
          </button>
        </div>

        {showMethod && (
          <div className="mt-2 rounded-md border border-violet-soft bg-surface/60 p-3 text-xs leading-relaxed text-text-muted">
            <p className="mb-1.5">
              <b className="text-text">Double median, per building.</b> Listings never expose construction
              year, floor or view — but a condo building embodies all of them (age, standing,
              micro-location, amenities). So each side is computed as the <b>median of each condo&apos;s
              listings</b> (floor/view noise is crushed), then the <b>median across condos</b> —
              1 building = 1 vote, so a tower with 80 listings no longer outweighs 80 buildings with one.
            </p>
            <p className="mb-1.5">
              <b className="text-text">Within-condo yield.</b> When a building has both sale and rent
              listings, yield = its median rent/m² × 12 ÷ its median sale price/m² : age, standing and
              location cancel out in the division. The district yield is the median of those
              per-building yields (needs ≥ {MIN_PAIRED_CONDOS} paired buildings, otherwise falls back to
              the ratio of district medians, flagged <span className="text-gold">†</span>).
            </p>
            <p>
              <b className="text-text">Guards.</b> Values are winsorized at p5–p95 per district;
              districts with fewer than {LOW_SAMPLE_CONDOS} buildings on either side carry a{" "}
              <span className="rounded bg-violet/25 px-1 text-[10px] text-gold">low sample</span> badge.
              The default segment (Studio–1BR) compares districts on the same basket — a district full
              of penthouses would otherwise just look &quot;expensive&quot;. Asking prices, not transactions :
              a relative ranking, not an appraisal.
            </p>
          </div>
        )}

        <p className="mt-2 text-sm text-text-muted">
          Segment: <b className="text-text">{STRATUM_LABEL[stratum]}</b>. Click a row for the
          per-street breakdown.
        </p>
      </div>

      <table className="w-full max-w-4xl border-collapse text-sm">
        <thead>
          <tr className="border-b border-violet-soft text-left text-text-muted">
            {cols.map((c) => (
              <th key={c.key} onClick={() => setKey(c.key)} title={c.title}
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
                    {r.lowSample && (
                      <span className="ml-2 rounded bg-violet/25 px-1 py-0.5 text-[10px] text-gold"
                        title={`Fewer than ${LOW_SAMPLE_CONDOS} buildings on one side — indicative only`}>
                        low sample
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right text-text-muted" title={`${r.nSale} listings`}>{r.nSaleCondos}</td>
                  <td className="px-3 py-2 text-right text-text-muted" title={`${r.nRent} listings`}>{r.nRentCondos}</td>
                  <td className="px-3 py-2 text-right text-text-muted">{r.nPairedCondos}</td>
                  <td className="px-3 py-2 text-right">{fmt(r.saleMedianPsqm)}</td>
                  <td className="px-3 py-2 text-right">{fmt(r.rentMedianPsqm)}</td>
                  <td className={`px-3 py-2 text-right font-medium ${r.grossYieldPct ? "text-gold" : "text-text-faint"}`}
                    title={r.yieldMethod === "within-condo"
                      ? `Median of ${r.nPairedCondos} within-condo yields`
                      : r.yieldMethod === "ratio" ? "Ratio of district medians (few paired buildings)" : ""}>
                    {r.grossYieldPct != null
                      ? <>{r.grossYieldPct} %{r.yieldMethod === "ratio" && <span className="text-text-faint"> †</span>}</>
                      : "—"}
                  </td>
                </tr>
                {expanded && streets.length === 0 && (
                  <tr key={`${r.khet}-empty`} className="border-b border-violet-soft/20 bg-anthracite-deep/40">
                    <td colSpan={7} className="px-3 py-2 pl-8 text-xs text-text-faint">
                      No street-level address recorded for this district (in this segment) yet.
                    </td>
                  </tr>
                )}
                {expanded && streets.map((s) => (
                  <tr key={`${r.khet}-${s.street}`} className="border-b border-violet-soft/20 bg-anthracite-deep/40 text-text-muted">
                    <td className="px-3 py-1.5 pl-8 text-xs">{s.street}</td>
                    <td className="px-3 py-1.5 text-right text-xs">{s.nSaleCondos}</td>
                    <td className="px-3 py-1.5 text-right text-xs">{s.nRentCondos}</td>
                    <td className="px-3 py-1.5 text-right text-xs">{s.nPairedCondos}</td>
                    <td className="px-3 py-1.5 text-right text-xs">{fmt(s.saleMedianPsqm)}</td>
                    <td className="px-3 py-1.5 text-right text-xs">{fmt(s.rentMedianPsqm)}</td>
                    <td className={`px-3 py-1.5 text-right text-xs ${s.grossYieldPct ? "text-gold/80" : "text-text-faint"}`}>
                      {s.grossYieldPct != null
                        ? <>{s.grossYieldPct} %{s.yieldMethod === "ratio" && " †"}</>
                        : "—"}
                    </td>
                  </tr>
                ))}
              </Fragment>
            );
          })}
        </tbody>
      </table>
      <p className="mt-2 max-w-4xl text-[11px] text-text-faint">
        † yield from the ratio of district medians (fewer than {MIN_PAIRED_CONDOS} buildings listed on
        both sides) — less reliable than the within-condo median used elsewhere.
      </p>
    </div>
  );
}
