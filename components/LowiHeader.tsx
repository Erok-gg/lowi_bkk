"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

/**
 * LowiHeader — header Lowi RE-TEINTÉ SOMBRE (porté de ++FILES++/Github/lowi).
 * Garde le logo « lowi » (police MCTen) + l'accent or, structure nav + hamburger
 * drawer + langues FR/EN/TH. Sans auth Supabase (app privée basic-auth).
 */
const LINKS = [
  { href: "/", label: "Carte" },
  { href: "/biens", label: "Biens" },
  { href: "/rendements", label: "Rendements" },
];
const LANGS = ["FR", "EN", "TH"] as const;

function Hamburger() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  );
}
function Close() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

export default function LowiHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [lang, setLang] = useState<(typeof LANGS)[number]>("FR");

  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  return (
    <header className="z-30 flex h-14 shrink-0 items-center justify-between border-b border-violet-soft bg-anthracite-deep px-4">
      <Link href="/" className="font-logo text-2xl text-text">
        <span className="text-gold">lowi</span>
        <span className="ml-1 align-middle text-[10px] uppercase tracking-widest text-text-faint">bkk</span>
      </Link>

      {/* nav desktop */}
      <nav className="hidden items-center gap-1 md:flex">
        {LINKS.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className={`rounded-md px-3 py-1.5 text-sm transition ${
              pathname === l.href
                ? "bg-surface text-gold"
                : "text-text-muted hover:text-text"
            }`}
          >
            {l.label}
          </Link>
        ))}
      </nav>

      <div className="flex items-center gap-2">
        <div className="hidden gap-1 md:flex">
          {LANGS.map((l) => (
            <button
              key={l}
              onClick={() => setLang(l)}
              className={`rounded px-1.5 py-0.5 text-xs transition ${
                lang === l ? "text-gold" : "text-text-faint hover:text-text-muted"
              }`}
            >
              {l}
            </button>
          ))}
        </div>
        <button
          className="rounded-md border border-violet-soft p-1.5 text-text-muted transition hover:text-gold"
          onClick={() => setOpen(true)}
          aria-label="Menu"
        >
          <Hamburger />
        </button>
      </div>

      {/* overlay + drawer */}
      <div
        className={`fixed inset-0 z-40 bg-black/60 transition-opacity ${open ? "opacity-100" : "pointer-events-none opacity-0"}`}
        onClick={() => setOpen(false)}
      />
      <aside
        className={`fixed right-0 top-0 z-50 flex h-full w-72 flex-col border-l border-violet-soft bg-surface transition-transform ${open ? "translate-x-0" : "translate-x-full"}`}
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-center justify-between border-b border-violet-soft px-4 py-3">
          <span className="font-logo text-xl text-gold">lowi</span>
          <button onClick={() => setOpen(false)} aria-label="Fermer" className="text-text-muted hover:text-text">
            <Close />
          </button>
        </div>
        <nav className="flex flex-col gap-1 p-3">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`rounded-md px-3 py-2.5 text-base transition ${
                pathname === l.href ? "bg-anthracite-deep text-gold" : "text-text hover:bg-anthracite-deep"
              }`}
            >
              {l.label}
            </Link>
          ))}
        </nav>
        <div className="mt-auto flex gap-2 border-t border-violet-soft p-4">
          {LANGS.map((l) => (
            <button
              key={l}
              onClick={() => setLang(l)}
              className={`rounded px-2 py-1 text-sm ${lang === l ? "text-gold" : "text-text-faint"}`}
            >
              {l}
            </button>
          ))}
        </div>
      </aside>
    </header>
  );
}
