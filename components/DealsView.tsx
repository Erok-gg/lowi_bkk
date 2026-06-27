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
