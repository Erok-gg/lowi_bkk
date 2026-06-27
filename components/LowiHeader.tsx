"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useSearch, type DealFilter } from "@/components/SearchProvider";

/**
 * LowiHeader — header Lowi sombre. Logo « lowi » (police MCTen) + accent or.
 * Nav inline en anglais, sans sélecteur de langue ni menu hamburger.
 * Barre de recherche centrée (uniquement sur la carte) : filtre les pins.
 */
const LINKS: { href: string; label: string; match?: string[] }[] = [
  { href: "/", label: "The map" },
  { href: "/for-sale", label: "For sale" },
  { href: "/to-rent", label: "To rent" },
  // Yields ouvre la CARTE en premier ; la table reste accessible via "Table view".
  { href: "/yields-map", label: "Yields", match: ["/yields-map", "/rendements"] },
  { href: "/deals", label: "Deals" },
];

const DEALS: { value: DealFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "sale", label: "Buy" },
  { value: "rent", label: "Rent" },
];

function MapSearch() {
  const search = useSearch();
  const controller = search?.controller ?? null;
  const [q, setQ] = useState("");
  const [deal, setDeal] = useState<DealFilter>("all");
  const [open, setOpen] = useState(false);

  const apply = (v: string, d: DealFilter = deal) => {
    setQ(v);
    controller?.run(v, d);
  };
  const pickDeal = (d: DealFilter) => {
    setDeal(d);
    controller?.run(q, d);
  };
  const suggestions = controller && q.trim() ? controller.suggest(q, deal) : [];

  // La carte n'a pas encore enregistré son controller (autre page) → pas de barre.
  if (!controller) return null;

  return (
    <div className="flex items-center gap-2">
      {/* Sélecteur type : All / Buy / Rent */}
      <div className="flex overflow-hidden rounded-md border border-violet-soft">
        {DEALS.map((d) => (
          <button
            key={d.value}
            onClick={() => pickDeal(d.value)}
            className={`px-2.5 py-1.5 text-xs transition ${
              deal === d.value ? "bg-violet/30 text-gold" : "text-text-muted hover:text-text"
            }`}
          >
            {d.label}
          </button>
        ))}
      </div>

      <div className="relative w-72 max-w-[34vw]">
        <input
          value={q}
          onChange={(e) => { apply(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          placeholder="Search a street, condo, district…"
          className="w-full rounded-md border border-violet-soft bg-surface px-3 py-1.5 pr-8 text-sm text-text outline-none focus:border-violet-fluo"
        />
        {q && (
          <button
            onClick={() => { apply(""); setOpen(false); }}
            aria-label="Clear"
            className="absolute right-2 top-1 flex h-6 w-6 items-center justify-center rounded text-text-muted hover:text-text"
          >
            ×
          </button>
        )}
        {open && suggestions.length > 0 && (
          <ul className="absolute left-0 right-0 z-50 mt-1 max-h-72 overflow-auto rounded-md border border-violet-soft bg-surface text-sm shadow-xl">
            {suggestions.map((s) => (
              <li key={s.kind + s.val}>
                <button
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => { apply(s.val); setOpen(false); }}
                  className="flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left hover:bg-anthracite-deep"
                >
                  <span className="truncate text-text">{s.val}</span>
                  <span className="shrink-0 text-[10px] uppercase tracking-wide text-text-faint">{s.kind}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default function LowiHeader() {
  const pathname = usePathname();

  return (
    <header className="relative z-30 flex h-14 shrink-0 items-center justify-between border-b border-violet-soft bg-anthracite-deep px-4">
      <Link href="/" className="font-logo text-2xl text-text">
        <span className="text-gold">lowi</span>
        <span className="ml-1 align-middle text-[10px] uppercase tracking-widest text-text-faint">bkk</span>
      </Link>

      {/* Barre de recherche centrée (visible sur la carte) */}
      <div className="absolute left-1/2 -translate-x-1/2">
        <MapSearch />
      </div>

      <nav className="flex items-center gap-1">
        {LINKS.map((l) => {
          const active = (l.match ?? [l.href]).includes(pathname);
          return (
            <Link
              key={l.href}
              href={l.href}
              className={`rounded-md px-3 py-1.5 text-sm transition ${
                active ? "bg-surface text-gold" : "text-text-muted hover:text-text"
              }`}
            >
              {l.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
