"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * LowiHeader — header Lowi sombre. Logo « lowi » (police MCTen) + accent or.
 * Nav inline en anglais, sans sélecteur de langue ni menu hamburger.
 */
const LINKS = [
  { href: "/", label: "The map" },
  { href: "/for-sale", label: "For sale" },
  { href: "/to-rent", label: "To rent" },
  { href: "/rendements", label: "Yields" },
];

export default function LowiHeader() {
  const pathname = usePathname();

  return (
    <header className="z-30 flex h-14 shrink-0 items-center justify-between border-b border-violet-soft bg-anthracite-deep px-4">
      <Link href="/" className="font-logo text-2xl text-text">
        <span className="text-gold">lowi</span>
        <span className="ml-1 align-middle text-[10px] uppercase tracking-widest text-text-faint">bkk</span>
      </Link>

      <nav className="flex items-center gap-1">
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
    </header>
  );
}
