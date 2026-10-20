"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useSearch, type DealFilter } from "@/components/SearchProvider";
import PublicNav from "@/bilan_RE/web/components/PublicNav";
import type { Langue } from "@/bilan_RE/web/i18n";

/**
 * LowiHeader — header Lowi sombre. Logo « lowi » (police MCTen) + accent or.
 *
 * DEUX NAVS, une seule barre (2026-10-19).
 *   · Pages internes (carte, tableaux, rendements, tension, deals) : la nav
 *     complète en anglais, derrière le mot de passe partagé. C'est l'outil.
 *   · Pages du produit (`/beta…`) : `PublicNav` — connexion, inscription,
 *     langue, et rien qui mène à la carte. Demande explicite : « la landpage ne
 *     donne pas accès à la map ou autres infos ».
 * Le partage se fait sur l'URL, pas sur un drapeau passé à la main : une page
 * ajoutée sous /beta hérite automatiquement de la bonne nav.
 */
const LINKS: { href: string; label: string; match?: string[] }[] = [
  { href: "/", label: "The map" },
  { href: "/for-sale", label: "For sale" },
  { href: "/to-rent", label: "To rent" },
  // Yields ouvre la CARTE en premier ; la table reste accessible via "Table view".
  { href: "/yields-map", label: "Yields", match: ["/yields-map", "/rendements"] },
  { href: "/tension", label: "Tension", match: ["/tension", "/tension-table"] },
  { href: "/deals", label: "Deals" },
  { href: "/beta", label: "Buyer report", match: ["/beta"] },
];

const DEALS: { value: DealFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "sale", label: "Buy" },
  { value: "rent", label: "Rent" },
];

function MapSearch() {
  const search = useSearch();
  const controller = search?.controller ?? null;
  const q = search?.query ?? "";
  const deal = search?.deal ?? "all";
  const [open, setOpen] = useState(false);

  const apply = (v: string) => search?.setQuery(v);
  // changer de deal réinitialise les filtres du bandeau (prix vente ≠ prix loyer).
  const pickDeal = (d: DealFilter) => {
    search?.setDeal(d);
    search?.setMapFilters({});
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

export default function LowiHeader({
  langue = "en",
  email = null,
}: {
  langue?: Langue;
  email?: string | null;
}) {
  const pathname = usePathname();
  const produit = pathname === "/beta" || pathname.startsWith("/beta/");

  // Le header est rendu HORS du layout `/beta`, il pose donc lui-même le thème
  // Ledger (vert/or/blanc) à partir de l'URL — sinon une barre sombre coifferait
  // une page claire. Le partage se fait sur le chemin, pas sur un drapeau.
  if (produit)
    return (
      <header className="theme-ledger relative z-30 flex h-14 shrink-0 items-center justify-between border-b border-rule-strong bg-page px-4 print:hidden">
        {/* Le logo renvoie à la landing du produit, pas à la carte. */}
        <Link href="/beta" className="font-logo text-2xl text-ink">
          <span className="text-gold-ink">lowi</span>
        </Link>
        <PublicNav langue={langue} email={email} />
      </header>
    );

  return (
    <header className="relative z-30 flex h-14 shrink-0 print:hidden items-center justify-between border-b border-violet-soft bg-anthracite-deep px-4">
      <Link href="/" className="font-logo text-2xl text-text">
        <span className="text-gold">lowi</span>
        <span className="ml-1 align-middle text-[10px] uppercase tracking-widest text-text-faint">bkk</span>
      </Link>

      {/* Barre de recherche centrée (visible sur la carte) */}
      <div className="absolute left-1/2 -translate-x-1/2">
        <MapSearch />
      </div>

      {/* Défilable sur mobile : sinon la nav élargit tout le document et la page
          déborde à droite (constaté sur le bilan acheteur à 390 px, 2026-10-17). */}
      <nav className="ml-3 flex min-w-0 items-center gap-1 overflow-x-auto whitespace-nowrap">
        {LINKS.map((l) => {
          const active = (l.match ?? [l.href]).some((m) => pathname === m || pathname.startsWith(m + "/"));
          return (
            <Link
              key={l.href}
              href={l.href}
              className={`shrink-0 rounded-md px-3 py-1.5 text-sm transition ${
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
