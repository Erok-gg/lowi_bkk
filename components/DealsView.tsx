"use client";

import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import {
  BED_CATS,
  bestDiscounts,
  bestDiscountsByKhet,
  bestYields,
  bestYieldsByKhet,
  type BedCat,
  type DealRow,
  type KhetGroup,
} from "@/lib/deals";

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

const fmtPrice = (v: number | null | undefined) =>
  v == null ? "—" : v >= 1_000_000 ? `${(v / 1_000_000).toFixed(2)}M` : Math.round(v).toLocaleString("en-US");

/** Le filtre prix se saisit en millions de THB (ex: "6.98" ou "6,98M" → 6 980 000). */
const parsePriceM = (v: string): number | null => {
  const cleaned = v.trim().replace(",", ".").replace(/m$/i, "");
  if (!cleaned) return null;
  const n = Number(cleaned);
  return Number.isFinite(n) ? n * 1_000_000 : null;
};

type Mode = "discounts" | "yields";

/** Tableau des annonces — partagé entre la vue plate (top 20) et les groupes par quartier. */
function DealsTable({ rows, mode }: { rows: DealRow[]; mode: Mode }) {
  return (
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
              <th className="px-3 py-2 text-right font-medium">St. discount</th>
              <th className="px-3 py-2 text-right font-medium">Condo discount</th>
              <th className="px-3 py-2 text-right font-medium">Δ since listed</th>
            </>
          ) : (
            <>
              <th className="px-3 py-2 text-right font-medium">Est. yield</th>
              <th className="px-3 py-2 font-medium">Basis</th>
            </>
          )}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={r.id} className="border-b border-violet-soft/40 hover:bg-surface/40">
            <td className="px-3 py-2 text-text-faint">{i + 1}</td>
            <td className="px-3 py-2">
              <a href={r.sourceUrl} target="_blank" rel="noreferrer" className="text-text hover:text-gold">
                {r.name}
              </a>
            </td>
            <td className="px-3 py-2 text-text-muted">{r.khet?.replace(" District", "") || "—"}</td>
            <td className="px-3 py-2 text-right">{fmtPrice(r.price)}</td>
            <td className="px-3 py-2 text-right text-text-muted">{fmt(r.pricePerSqm)}</td>
            <td className="px-3 py-2 text-right text-text-muted">{r.areaSqm ? `${fmt(r.areaSqm)} m²` : "—"}</td>
            {mode === "discounts" ? (
              <>
                <td className={`px-3 py-2 text-right font-medium ${(r.streetDiscountPct ?? 0) > 0 ? "text-gold" : "text-text-faint"}`}>
                  {r.streetDiscountPct != null ? `${r.streetDiscountPct} %` : "—"}
                </td>
                <td className={`px-3 py-2 text-right font-medium ${(r.condoDiscountPct ?? 0) > 0 ? "text-gold" : "text-text-faint"}`}>
                  {r.condoDiscountPct != null ? `${r.condoDiscountPct} %` : "—"}
                </td>
                <td className={`px-3 py-2 text-right ${(r.temporalDiscountPct ?? 0) > 0 ? "text-gold" : "text-text-faint"}`}>
                  {r.temporalDiscountPct ? `−${r.temporalDiscountPct} %` : "—"}
                </td>
              </>
            ) : (
              <>
                <td className="px-3 py-2 text-right font-medium text-gold">
                  {r.estYieldPct != null ? `${r.estYieldPct} %` : "—"}
                </td>
                <td className="px-3 py-2 text-text-faint">{r.yieldBasis ?? "—"}</td>
              </>
            )}
          </tr>
        ))}
        {rows.length === 0 && (
          <tr>
            <td colSpan={mode === "discounts" ? 9 : 8} className="px-3 py-10 text-center text-text-faint">
              Not enough comparable listings for this category.
            </td>
          </tr>
        )}
      </tbody>
    </table>
  );
}

export default function DealsView({ rows }: { rows: DealRow[] }) {
  const [mode, setMode] = useState<Mode>("discounts");
  const [cat, setCat] = useState<BedCat>("1");
  const [khetSel, setKhetSel] = useState<string>("");
  const [groupByDistrict, setGroupByDistrict] = useState(false);
  const [priceMin, setPriceMin] = useState<string>("");
  const [priceMax, setPriceMax] = useState<string>("");
  const [search, setSearch] = useState<string>("");
  const [showHow, setShowHow] = useState(false);

  const khets = useMemo(
    () => [...new Set(rows.map((r) => r.khet).filter(Boolean))].sort() as string[],
    [rows]
  );

  const scoped = useMemo(() => {
    const min = parsePriceM(priceMin);
    const max = parsePriceM(priceMax);
    const q = search.trim().toLowerCase();
    return rows.filter((r) => {
      if (khetSel && r.khet !== khetSel) return false;
      if (min != null && r.price < min) return false;
      if (max != null && r.price > max) return false;
      if (q && !r.name.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [rows, khetSel, priceMin, priceMax, search]);

  const top = useMemo(
    () => (mode === "discounts" ? bestDiscounts(scoped, cat) : bestYields(scoped, cat)),
    [scoped, mode, cat]
  );
  const groups = useMemo<KhetGroup[]>(
    () =>
      groupByDistrict
        ? mode === "discounts"
          ? bestDiscountsByKhet(scoped, cat)
          : bestYieldsByKhet(scoped, cat)
        : [],
    [scoped, mode, cat, groupByDistrict]
  );

  const displayedRows = groupByDistrict ? groups.flatMap((g) => g.rows) : top;
  const points = useMemo(
    () => displayedRows.map((r) => ({ id: r.id, lat: r.lat, lng: r.lng, name: r.name })),
    [displayedRows]
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
      {/* Onglets */}
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-violet-soft px-4 py-3">
        <div className="flex items-center gap-2">
          <Tab m="discounts" label="Best discounts" />
          <Tab m="yields" label="Best yields" />
        </div>
        <button
          onClick={() => setShowHow((v) => !v)}
          className="rounded-md border border-violet-soft px-2.5 py-1 text-xs text-text-muted transition hover:border-violet-fluo hover:text-text"
        >
          ⓘ How it&apos;s computed
        </button>
      </div>

      {/* Bandeau de filtres */}
      <div className="flex shrink-0 flex-wrap items-center gap-3 border-b border-violet-soft bg-surface/20 px-4 py-2.5">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search listing…"
          className="w-36 rounded-md border border-violet-soft bg-anthracite-deep px-2 py-1.5 text-xs text-text placeholder:text-text-faint focus:outline-none"
        />
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-text-muted">Price (M)</span>
          <input
            type="text"
            inputMode="decimal"
            value={priceMin}
            onChange={(e) => setPriceMin(e.target.value)}
            placeholder="6.98"
            className="w-20 rounded-md border border-violet-soft bg-anthracite-deep px-2 py-1.5 text-xs text-text placeholder:text-text-faint focus:outline-none"
          />
          <span className="text-text-faint">–</span>
          <input
            type="text"
            inputMode="decimal"
            value={priceMax}
            onChange={(e) => setPriceMax(e.target.value)}
            placeholder="15M"
            className="w-20 rounded-md border border-violet-soft bg-anthracite-deep px-2 py-1.5 text-xs text-text placeholder:text-text-faint focus:outline-none"
          />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted">District</span>
          <select
            value={khetSel}
            onChange={(e) => setKhetSel(e.target.value)}
            disabled={groupByDistrict}
            className="rounded-md border border-violet-soft bg-anthracite-deep px-2 py-1.5 text-xs text-text-muted transition hover:text-text focus:text-text focus:outline-none disabled:opacity-40"
          >
            <option value="">All districts</option>
            {khets.map((k) => (
              <option key={k} value={k}>
                {k.replace(" District", "")}
              </option>
            ))}
          </select>
        </div>
        <label className="flex items-center gap-1.5 text-xs text-text-muted">
          <input
            type="checkbox"
            checked={groupByDistrict}
            onChange={(e) => setGroupByDistrict(e.target.checked)}
          />
          Top 10 per district
        </label>
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

      {/* Méthodologie / formules — visibles pour pouvoir critiquer la méthode */}
      {showHow && (
        <div className="shrink-0 border-b border-violet-soft bg-surface/40 px-4 py-3 text-xs leading-relaxed text-text-muted">
          <p className="mb-1">
            <span className="text-text">Comparable</span> = same <span className="text-text">condo (building)</span> + bedroom count (1/2/3/4+), excluding the listing itself.{" "}
            Fewer than {"3"} peers in the building → falls back to same <span className="text-text">street</span> + bedroom count.
            District is only used to filter/group the table, not to compute the baseline.{" "}
            <span className="text-text">Baseline</span> = average of the ~10 median listings of the comparable group.
            Sale prices bounded 800k–100M THB; figures are gross (before charges, taxes, vacancy).
          </p>
          {mode === "discounts" ? (
            <ul className="list-inside list-disc space-y-0.5">
              <li><span className="text-gold">St. discount</span> = discount vs. the street baseline only (— if fewer than 3 street peers)</li>
              <li><span className="text-gold">Condo discount</span> = discount vs. the building baseline only (— if fewer than 3 building peers)</li>
              <li><span className="text-gold">Δ since listed</span> = (first recorded price − current price) ÷ first price × 100 <span className="text-text-faint">(from price history; mostly 0 until prices move over successive scrapes)</span></li>
              <li className="text-text-faint">Ranking uses the condo discount when available, the street discount otherwise.</li>
            </ul>
          ) : (
            <ul className="list-inside list-disc space-y-0.5">
              <li><span className="text-gold">Est. yield</span> = (baseline rent/m² × 12) ÷ listing sale price/m² × 100</li>
              <li className="text-text-faint">Estimated: uses the comparable-group median rent (same building, or street if too few), not this exact unit&apos;s lease.</li>
            </ul>
          )}
          <p className="mt-1 text-text-faint">
            &quot;Top 10 per district&quot; recomputes the ranking within each district separately (min 1 comparable
            listing) instead of a single citywide top 20. Search and price range filter the pool before ranking.
          </p>
        </div>
      )}

      {/* Corps : tableau(x) + minimap */}
      <div className="flex min-h-0 flex-1">
        <div className="min-w-0 flex-1 overflow-auto">
          {groupByDistrict ? (
            groups.length === 0 ? (
              <div className="px-3 py-10 text-center text-text-faint">
                Not enough comparable listings for this category.
              </div>
            ) : (
              groups.map((g) => (
                <div key={g.khet} className="border-b border-violet-soft">
                  <div className="sticky top-0 bg-anthracite-deep px-3 py-1.5 text-xs font-medium text-gold">
                    {g.khet.replace(" District", "")}
                  </div>
                  <DealsTable rows={g.rows} mode={mode} />
                </div>
              ))
            )
          ) : (
            <DealsTable rows={top} mode={mode} />
          )}
        </div>

        {/* Minimap : pins des biens affichés */}
        <div className="hidden w-2/5 shrink-0 border-l border-violet-soft md:block">
          <DealsMiniMap points={points} />
        </div>
      </div>
    </div>
  );
}
