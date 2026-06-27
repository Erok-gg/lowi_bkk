"use client";

import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { BED_CATS, bestDiscounts, bestYields, type BedCat, type DealRow } from "@/lib/deals";

const DealsMiniMap = dynamic(() => import("./DealsMiniMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center bg-anthracite-deep text-text-muted">
      Loading map…
    </div>
  ),
});

const fmt = (v: number | null | undefined) =>
  v == null ? "—" : Math.round(v).toLocaleString("en-US");

type Mode = "discounts" | "yields";

export default function DealsView({ rows }: { rows: DealRow[] }) {
  const [mode, setMode] = useState<Mode>("discounts");
  const [cat, setCat] = useState<BedCat>("1");
  const [showHow, setShowHow] = useState(false);

  const top = useMemo(
    () => (mode === "discounts" ? bestDiscounts(rows, cat) : bestYields(rows, cat)),
    [rows, mode, cat]
  );
  const points = useMemo(
    () => top.map((r) => ({ id: r.id, lat: r.lat, lng: r.lng, name: r.name })),
    [top]
  );

  const Tab = ({ m, label }: { m: Mode; label: string }) => (
    <button
      onClick={() => setMode(m)}
      className={`rounded-md px-3 py-1.5 text-sm transition ${
        mode === m ? "bg-surface text-gold" : "text-text-muted hover:text-text"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="flex h-full flex-col">
      {/* En-tête : onglets + sélecteur chambres */}
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-violet-soft px-4 py-3">
        <div className="flex items-center gap-2">
          <Tab m="discounts" label="Best discounts" />
          <Tab m="yields" label="Best yields" />
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowHow((v) => !v)}
            className="rounded-md border border-violet-soft px-2.5 py-1 text-xs text-text-muted transition hover:border-violet-fluo hover:text-text"
          >
            ⓘ How it&apos;s computed
          </button>
          <div className="flex items-center gap-2">
            <span className="text-xs text-text-muted">Beds</span>
            <div className="flex overflow-hidden rounded-md border border-violet-soft">
              {BED_CATS.map((c) => (
                <button
                  key={c}
                  onClick={() => setCat(c)}
                  className={`px-2.5 py-1.5 text-xs transition ${
                    cat === c ? "bg-violet/30 text-gold" : "text-text-muted hover:text-text"
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Méthodologie / formules — visibles pour pouvoir critiquer la méthode */}
      {showHow && (
        <div className="shrink-0 border-b border-violet-soft bg-surface/40 px-4 py-3 text-xs leading-relaxed text-text-muted">
          <p className="mb-1">
            <span className="text-text">Comparable</span> = same district + bedroom count (1/2/3/4+).{" "}
            <span className="text-text">Baseline</span> = average of the 10 median listings of the comparable group.
            Sale prices bounded 800k–100M THB; figures are gross (before charges, taxes, vacancy).
          </p>
          {mode === "discounts" ? (
            <ul className="list-inside list-disc space-y-0.5">
              <li><span className="text-gold">Market discount</span> = (baseline sale price/m² − listing price/m²) ÷ baseline × 100</li>
              <li><span className="text-gold">Δ since listed</span> = (first recorded price − current price) ÷ first price × 100 <span className="text-text-faint">(from price history; mostly 0 until prices move over successive scrapes)</span></li>
            </ul>
          ) : (
            <ul className="list-inside list-disc space-y-0.5">
              <li><span className="text-gold">Est. yield</span> = (baseline rent/m² × 12) ÷ listing sale price/m² × 100</li>
              <li className="text-text-faint">Estimated: uses the comparable-group median rent, not this exact unit&apos;s lease.</li>
            </ul>
          )}
        </div>
      )}

      {/* Corps : tableau + minimap */}
      <div className="flex min-h-0 flex-1">
        <div className="min-w-0 flex-1 overflow-auto">
          <table className="w-full border-collapse text-sm">
            <thead className="sticky top-0 bg-anthracite-deep">
              <tr className="border-b border-violet-soft text-left text-text-muted">
                <th className="px-3 py-2 font-medium">#</th>
                <th className="px-3 py-2 font-medium">Listing</th>
                <th className="px-3 py-2 font-medium">District</th>
                <th className="px-3 py-2 text-right font-medium">Price</th>
                <th className="px-3 py-2 text-right font-medium">Price/m²</th>
                <th className="px-3 py-2 text-right font-medium">Area</th>
                {mode === "discounts" ? (
                  <>
                    <th className="px-3 py-2 text-right font-medium">Market discount</th>
                    <th className="px-3 py-2 text-right font-medium">Δ since listed</th>
                  </>
                ) : (
                  <th className="px-3 py-2 text-right font-medium">Est. yield</th>
                )}
              </tr>
            </thead>
            <tbody>
              {top.map((r, i) => (
                <tr key={r.id} className="border-b border-violet-soft/40 hover:bg-surface/40">
                  <td className="px-3 py-2 text-text-faint">{i + 1}</td>
                  <td className="px-3 py-2">
                    <a href={r.sourceUrl} target="_blank" rel="noreferrer" className="text-text hover:text-gold">
                      {r.name}
                    </a>
                  </td>
                  <td className="px-3 py-2 text-text-muted">{r.khet?.replace(" District", "") || "—"}</td>
                  <td className="px-3 py-2 text-right">{fmt(r.price)}</td>
                  <td className="px-3 py-2 text-right text-text-muted">{fmt(r.pricePerSqm)}</td>
                  <td className="px-3 py-2 text-right text-text-muted">{r.areaSqm ? `${fmt(r.areaSqm)} m²` : "—"}</td>
                  {mode === "discounts" ? (
                    <>
                      <td className={`px-3 py-2 text-right font-medium ${(r.marketDiscountPct ?? 0) > 0 ? "text-gold" : "text-text-faint"}`}>
                        {r.marketDiscountPct != null ? `${r.marketDiscountPct} %` : "—"}
                      </td>
                      <td className={`px-3 py-2 text-right ${(r.temporalDiscountPct ?? 0) > 0 ? "text-gold" : "text-text-faint"}`}>
                        {r.temporalDiscountPct ? `−${r.temporalDiscountPct} %` : "—"}
                      </td>
                    </>
                  ) : (
                    <td className="px-3 py-2 text-right font-medium text-gold">
                      {r.estYieldPct != null ? `${r.estYieldPct} %` : "—"}
                    </td>
                  )}
                </tr>
              ))}
              {top.length === 0 && (
                <tr>
                  <td colSpan={mode === "discounts" ? 8 : 7} className="px-3 py-10 text-center text-text-faint">
                    Not enough comparable listings for this category.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Minimap : pins des biens affichés */}
        <div className="hidden w-2/5 shrink-0 border-l border-violet-soft md:block">
          <DealsMiniMap points={points} />
        </div>
      </div>
    </div>
  );
}
