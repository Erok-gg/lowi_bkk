"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { LANGUES, NOMS, traducteur, type Langue } from "../i18n";

/**
 * PublicNav — la nav du PRODUIT, pas celle de l'outil interne.
 *
 * Demande du 2026-10-19 : la landing ne donne accès ni à la carte ni au reste ;
 * sa nav ne porte que la connexion, l'inscription et la langue. Les pages
 * internes (carte, tableaux, rendements, tension) gardent la leur et leur
 * mot de passe partagé — c'est `LowiHeader` qui choisit selon l'URL.
 */
export default function PublicNav({
  langue,
  email,
}: {
  langue: Langue;
  email: string | null;
}) {
  const t = traducteur(langue);
  const router = useRouter();
  const [ouvert, setOuvert] = useState(false);

  async function changeLangue(l: Langue) {
    setOuvert(false);
    await fetch("/api/langue", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ langue: l }),
    });
    // Rechargement complet, pas `router.refresh()` : la langue est lue dans le
    // LAYOUT, et le cache du routeur client lui resservait l'ancien rendu —
    // constaté le 2026-10-19, le cookie passait bien à `th` et la page restait
    // en anglais jusqu'à une navigation réelle.
    window.location.reload();
  }

  async function deconnexion() {
    await fetch("/api/compte/deconnexion", { method: "POST" });
    router.push("/beta");
    router.refresh();
  }

  return (
    <nav className="flex min-w-0 items-center gap-1 overflow-x-auto whitespace-nowrap">
      {/* Sélecteur de langue : trois langues au départ (en/th/zh). */}
      <div className="relative shrink-0">
        <button
          type="button"
          onClick={() => setOuvert(!ouvert)}
          aria-label={t("nav_language")}
          aria-expanded={ouvert}
          className="rounded-md px-2.5 py-1.5 text-sm text-muted transition hover:text-ink"
        >
          {NOMS[langue]} <span aria-hidden="true">▾</span>
        </button>
        {ouvert && (
          <ul className="absolute right-0 z-50 mt-1 w-32 overflow-hidden rounded-md border border-rule bg-surface text-sm shadow-xl">
            {LANGUES.map((l) => (
              <li key={l}>
                <button
                  type="button"
                  onClick={() => changeLangue(l)}
                  className={`block w-full px-3 py-2 text-left hover:bg-page ${
                    l === langue ? "text-gold-ink" : "text-muted"
                  }`}
                >
                  {NOMS[l]}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {email ? (
        <>
          <Link
            href="/beta/reports"
            className="shrink-0 rounded-md px-3 py-1.5 text-sm text-muted transition hover:text-ink"
          >
            {t("nav_reports")}
          </Link>
          <button
            type="button"
            onClick={deconnexion}
            className="shrink-0 rounded-md px-3 py-1.5 text-sm text-faint transition hover:text-ink"
            title={email}
          >
            {t("nav_signout")}
          </button>
        </>
      ) : (
        <>
          <Link
            href="/beta/login"
            className="shrink-0 rounded-md px-3 py-1.5 text-sm text-muted transition hover:text-ink"
          >
            {t("nav_signin")}
          </Link>
          <Link
            href="/beta/signup"
            className="shrink-0 rounded-md bg-brand-deep px-3 py-1.5 text-sm font-medium text-white transition hover:bg-brand"
          >
            {t("nav_signup")}
          </Link>
        </>
      )}
    </nav>
  );
}
