"use client";

import { useEffect, useMemo, useState } from "react";
import type { Listing } from "@/lib/types";
import { applyFilters, filtersToParams, filtersFromParams, type Filters } from "@/lib/filters";

/* ───────────────────────── Réglette double-curseur (activable) ───────────── */
function RangeSlider({
  label, min, max, step, lo, hi, onChange, fmt, active, onToggleActive,
}: {
  label: string; min: number; max: number; step: number;
  lo: number; hi: number; onChange: (lo: number, hi: number) => void;
  fmt: (v: number) => string; active: boolean; onToggleActive: (v: boolean) => void;
}) {
  const span = max - min || 1;
  const leftPct = ((lo - min) / span) * 100;
  const rightPct = ((hi - min) / span) * 100;
  return (
    <div className={`mb-4 ${active ? "" : "opacity-50"}`}>
      <div className="mb-1 flex items-center justify-between text-xs text-text-muted">
        <label className="flex cursor-pointer items-center gap-1.5">
          <input type="checkbox" checked={active}
            onChange={(e) => onToggleActive(e.target.checked)} className="accent-violet-fluo" />
          {label}
        </label>
        <span className="text-text">{fmt(lo)} – {fmt(hi)}</span>
      </div>
      <div className="range-dual">
        <div className="range-track" />
        <div className="range-fill" style={{ left: `${leftPct}%`, right: `${100 - rightPct}%` }} />
        <input type="range" min={min} max={max} step={step} value={lo} disabled={!active}
          onChange={(e) => onChange(Math.min(+e.target.value, hi), hi)} />
        <input type="range" min={min} max={max} step={step} value={hi} disabled={!active}
          onChange={(e) => onChange(lo, Math.max(+e.target.value, lo))} />
      </div>
    </div>
  );
}

/* ───────────────────────── Multi-sélection (chips) ───────────────────────── */
function MultiToggle({
  label, options, selected, onToggle,
}: {
  label: string; options: { value: string; label: string }[];
  selected: Set<string>; onToggle: (v: string) => void;
}) {
  if (options.length === 0) return null;
  return (
    <div className="mb-4">
      <div className="mb-1.5 text-xs text-text-muted">{label}</div>
      <div className="flex flex-wrap gap-1.5">
        {options.map((o) => {
          const on = selected.has(o.value);
          return (
            <button key={o.value} onClick={() => onToggle(o.value)}
              className={`rounded-full border px-2.5 py-1 text-xs transition ${
                on ? "border-violet-fluo bg-violet/20 text-text"
                   : "border-violet-soft text-text-muted hover:text-text"}`}>
              {o.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ───────────────────────────── helpers ───────────────────────────── */
type SortKey = "name" | "khet" | "dealType" | "price" | "pricePerSqm" | "bedrooms" | "bathrooms" | "areaSqm";
const fmtInt = (v: number) => Math.round(v).toLocaleString("fr-FR");
const name = (l: Listing) => l.condoName || l.title || "—";

function bounds(vals: number[]): [number, number] {
  const f = vals.filter((v) => Number.isFinite(v));
  return f.length ? [Math.min(...f), Math.max(...f)] : [0, 0];
}

/* ───────────────────────────── composant ───────────────────────────── */
export default function ListingsTable({ listings }: { listings: Listing[] }) {
  const [pB0, pB1] = useMemo(() => bounds(listings.map((l) => l.price)), [listings]);
  const [aB0, aB1] = useMemo(() => bounds(listings.map((l) => l.areaSqm ?? NaN)), [listings]);
  const [ppB0, ppB1] = useMemo(() => bounds(listings.map((l) => l.pricePerSqm ?? NaN)), [listings]);
  const bedMax = useMemo(() => Math.max(0, ...listings.map((l) => l.bedrooms ?? 0)), [listings]);
  const bathMax = useMemo(() => Math.max(0, ...listings.map((l) => l.bathrooms ?? 0)), [listings]);
  const khets = useMemo(
    () => [...new Set(listings.map((l) => l.khet).filter(Boolean))].sort() as string[],
    [listings]
  );
  const sources = useMemo(
    () => [...new Set(listings.map((l) => l.source))].sort(), [listings]
  );

  // état initial : on relit l'URL (filtres partagés avec la carte) sinon les bornes
  const init = useMemo(
    () => filtersFromParams(new URLSearchParams(typeof window !== "undefined" ? window.location.search : "")),
    []
  );
  const [price, setPrice] = useState<[number, number]>([init.priceMin ?? pB0, init.priceMax ?? pB1]);
  const [area, setArea] = useState<[number, number]>([init.areaMin ?? aB0, init.areaMax ?? aB1]);
  const [ppsqm, setPpsqm] = useState<[number, number]>([init.ppsqmMin ?? ppB0, init.ppsqmMax ?? ppB1]);
  const [beds, setBeds] = useState<[number, number]>([init.bedsMin ?? 0, init.bedsMax ?? bedMax]);
  const [baths, setBaths] = useState<[number, number]>([init.bathsMin ?? 0, init.bathsMax ?? bathMax]);
  const [quota, setQuota] = useState<Set<string>>(init.quota);
  const [deal, setDeal] = useState<Set<string>>(init.deal);
  const [src, setSrc] = useState<Set<string>>(init.source);
  const [khetSel, setKhetSel] = useState<Set<string>>(init.khet);
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "price", dir: -1 });

  // Activation par réglette (case à cocher). Active d'office si l'URL portait le critère.
  const [active, setActive] = useState<Record<string, boolean>>({
    price: init.priceMin != null || init.priceMax != null,
    area: init.areaMin != null || init.areaMax != null,
    ppsqm: init.ppsqmMin != null || init.ppsqmMax != null,
    beds: init.bedsMin != null || init.bedsMax != null,
    baths: init.bathsMin != null || init.bathsMax != null,
  });
  const setAct = (k: string, v: boolean) => setActive((p) => ({ ...p, [k]: v }));

  // Filtres courants : une fourchette ne compte que si sa case est cochée
  const filters = useMemo<Filters>(() => ({
    priceMin: active.price ? price[0] : undefined,
    priceMax: active.price ? price[1] : undefined,
    areaMin: active.area ? area[0] : undefined,
    areaMax: active.area ? area[1] : undefined,
    ppsqmMin: active.ppsqm ? ppsqm[0] : undefined,
    ppsqmMax: active.ppsqm ? ppsqm[1] : undefined,
    bedsMin: active.beds ? beds[0] : undefined,
    bedsMax: active.beds ? beds[1] : undefined,
    bathsMin: active.baths ? baths[0] : undefined,
    bathsMax: active.baths ? baths[1] : undefined,
    quota, deal, source: src, khet: khetSel,
  }), [active, price, area, ppsqm, beds, baths, quota, deal, src, khetSel]);

  // Sync vers l'URL (la carte relit ces params pour ses pinpoints)
  useEffect(() => {
    const qs = filtersToParams(filters).toString();
    const url = qs ? `?${qs}` : window.location.pathname;
    window.history.replaceState(null, "", url);
  }, [filters]);

  const toggle = (set: Set<string>, setter: (s: Set<string>) => void) => (v: string) => {
    const n = new Set(set);
    n.has(v) ? n.delete(v) : n.add(v);
    setter(n);
  };

  const rows = useMemo(() => {
    const out = applyFilters(listings, filters);
    const { key, dir } = sort;
    out.sort((a, b) => {
      let va: string | number, vb: string | number;
      if (key === "name") { va = name(a).toLowerCase(); vb = name(b).toLowerCase(); }
      else if (key === "khet") { va = (a.khet || "").toLowerCase(); vb = (b.khet || "").toLowerCase(); }
      else if (key === "dealType") { va = a.dealType; vb = b.dealType; }
      else { va = (a[key] ?? -Infinity) as number; vb = (b[key] ?? -Infinity) as number; }
      return va < vb ? -dir : va > vb ? dir : 0;
    });
    return out;
  }, [listings, filters, sort]);

  const setSortKey = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, dir: (s.dir * -1) as 1 | -1 } : { key, dir: 1 }));

  const arrow = (key: SortKey) => (sort.key === key ? (sort.dir === 1 ? " ▲" : " ▼") : "");

  const cols: { key: SortKey; label: string; align?: string }[] = [
    { key: "name", label: "Nom de l'annonce" },
    { key: "khet", label: "Quartier" },
    { key: "dealType", label: "Type" },
    { key: "price", label: "Prix", align: "text-right" },
    { key: "pricePerSqm", label: "Prix/m²", align: "text-right" },
    { key: "bedrooms", label: "Ch.", align: "text-right" },
    { key: "bathrooms", label: "SDB", align: "text-right" },
    { key: "areaSqm", label: "Surface", align: "text-right" },
  ];

  return (
    <div className="flex h-full">
      {/* ───── Filtres (colonne gauche) ───── */}
      <aside className="w-72 shrink-0 overflow-y-auto border-r border-violet-soft bg-surface/40 p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-gold">Filtres</h2>
        <p className="mb-2 text-[11px] text-text-faint">Coche une réglette pour l'activer.</p>
        <RangeSlider label="Prix (THB)" min={pB0} max={pB1} step={Math.max(1, Math.round((pB1 - pB0) / 100))}
          lo={price[0]} hi={price[1]} onChange={(a, b) => setPrice([a, b])}
          active={!!active.price} onToggleActive={(v) => setAct("price", v)}
          fmt={(v) => (v >= 1e6 ? (v / 1e6).toFixed(1) + "M" : fmtInt(v))} />
        <RangeSlider label="Surface (m²)" min={aB0} max={aB1} step={1}
          lo={area[0]} hi={area[1]} onChange={(a, b) => setArea([a, b])}
          active={!!active.area} onToggleActive={(v) => setAct("area", v)} fmt={fmtInt} />
        <RangeSlider label="Prix/m² (THB)" min={ppB0} max={ppB1} step={Math.max(1, Math.round((ppB1 - ppB0) / 100))}
          lo={ppsqm[0]} hi={ppsqm[1]} onChange={(a, b) => setPpsqm([a, b])}
          active={!!active.ppsqm} onToggleActive={(v) => setAct("ppsqm", v)} fmt={fmtInt} />
        <RangeSlider label="Chambres" min={0} max={bedMax} step={1}
          lo={beds[0]} hi={beds[1]} onChange={(a, b) => setBeds([a, b])}
          active={!!active.beds} onToggleActive={(v) => setAct("beds", v)} fmt={(v) => `${v}`} />
        <RangeSlider label="Salles de bains" min={0} max={bathMax} step={1}
          lo={baths[0]} hi={baths[1]} onChange={(a, b) => setBaths([a, b])}
          active={!!active.baths} onToggleActive={(v) => setAct("baths", v)} fmt={(v) => `${v}`} />

        <MultiToggle label="Quota" selected={quota} onToggle={toggle(quota, setQuota)}
          options={[{ value: "foreigner", label: "Foreigner" }, { value: "thai", label: "Thai" }]} />
        <MultiToggle label="Type" selected={deal} onToggle={toggle(deal, setDeal)}
          options={[{ value: "sale", label: "Vente" }, { value: "rent", label: "Location" }]} />
        <MultiToggle label="Source" selected={src} onToggle={toggle(src, setSrc)}
          options={sources.map((s) => ({ value: s, label: s }))} />
        <MultiToggle label="Quartier" selected={khetSel} onToggle={toggle(khetSel, setKhetSel)}
          options={khets.map((k) => ({ value: k, label: k.replace(" District", "") }))} />
      </aside>

      {/* ───── Tableau ───── */}
      <div className="min-w-0 flex-1 overflow-auto">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-violet-soft bg-anthracite-deep px-4 py-2 text-sm text-text-muted">
          <span><span className="text-text">{rows.length}</span> bien(s)</span>
        </div>
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-9 bg-anthracite-deep">
            <tr className="border-b border-violet-soft text-left text-text-muted">
              {cols.map((c) => (
                <th key={c.key}
                  onClick={() => setSortKey(c.key)}
                  className={`cursor-pointer select-none px-4 py-2.5 font-medium hover:text-text ${c.align || ""}`}>
                  {c.label}{arrow(c.key)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((l) => (
              <tr key={l.id} className="border-b border-violet-soft/40 hover:bg-surface/40">
                <td className="px-4 py-2.5">
                  <a href={l.sourceUrl} target="_blank" rel="noreferrer" className="text-text hover:text-gold">
                    {name(l)}
                  </a>
                </td>
                <td className="px-4 py-2.5 text-text-muted">{l.khet?.replace(" District", "") || "—"}</td>
                <td className="px-4 py-2.5">
                  <span className={l.dealType === "rent" ? "text-blue" : "text-gold"}>
                    {l.dealType === "rent" ? "Location" : "Vente"}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-right">{l.price ? fmtInt(l.price) : "—"}</td>
                <td className="px-4 py-2.5 text-right text-text-muted">{l.pricePerSqm ? fmtInt(l.pricePerSqm) : "—"}</td>
                <td className="px-4 py-2.5 text-right">{l.bedrooms ?? "—"}</td>
                <td className="px-4 py-2.5 text-right">{l.bathrooms ?? "—"}</td>
                <td className="px-4 py-2.5 text-right">{l.areaSqm ? `${fmtInt(l.areaSqm)} m²` : "—"}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={8} className="px-4 py-10 text-center text-text-faint">
                Aucun bien ne correspond aux filtres.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
