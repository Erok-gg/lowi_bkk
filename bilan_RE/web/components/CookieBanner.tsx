"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { useEffect, useState } from "react";
import { traducteur, type Langue } from "../i18n";
import { VERSION_CONSENTEMENT } from "../lib/consentement-version";

/**
 * CookieBanner — l'encart RGPD / PDPA.
 *
 * Ce qu'il fait, et pourquoi dans cet ordre :
 *   · il ne s'affiche que sur les pages du PRODUIT (`/beta…`). L'outil interne
 *     est privé et ne pose qu'un cookie de connexion : rien à consentir ;
 *   · « Necessary only » est à portée égale de « Accept all » (un refus qui
 *     demande trois clics n'est pas un consentement libre) ;
 *   · rien d'optionnel n'est chargé avant le choix. Il n'y a d'ailleurs AUCUN
 *     script de mesure aujourd'hui : la case existe pour le jour où il y en
 *     aura un, et elle est à zéro d'ici là ;
 *   · le choix part au serveur (preuve en base, `consentements`) ET revient en
 *     cookie lisible par la page.
 *
 * Il lit le cookie lui-même plutôt que de recevoir l'état en props : le serveur
 * sert les pages du produit en `force-dynamic`, mais un rendu mis en cache par
 * le navigateur ne doit pas réafficher le bandeau à quelqu'un qui a répondu.
 */

const COOKIE = "lowi_consent";
const VERSION = VERSION_CONSENTEMENT;

function dejaRepondu(): boolean {
  if (typeof document === "undefined") return true;
  const m = document.cookie.match(/(?:^|;\s*)lowi_consent=([^;]+)/);
  // Version différente = texte modifié depuis : on redemande.
  return Boolean(m && decodeURIComponent(m[1]).startsWith(VERSION + ":"));
}

export default function CookieBanner({ langue }: { langue: Langue }) {
  const t = traducteur(langue);
  const pathname = usePathname();
  const [visible, setVisible] = useState(false);
  const [detail, setDetail] = useState(false);
  const [mesure, setMesure] = useState(false);
  const [marketing, setMarketing] = useState(false);

  // Après le premier rendu seulement : lire `document.cookie` au rendu serveur
  // ferait diverger le HTML et l'hydratation.
  useEffect(() => {
    if (!dejaRepondu()) setVisible(true);
  }, []);

  const produit = pathname === "/beta" || pathname.startsWith("/beta/");
  if (!visible || !produit) return null;

  async function repond(m: boolean, k: boolean) {
    setVisible(false);
    try {
      await fetch("/api/consentement", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ mesure: m, marketing: k }),
      });
    } catch {
      // Le réseau a lâché : on réaffichera au prochain chargement plutôt que
      // de prétendre avoir enregistré un choix.
      setVisible(true);
    }
  }

  const Case = ({
    on,
    set,
    titre,
    detail: d,
    fige,
  }: {
    on: boolean;
    set?: (v: boolean) => void;
    titre: string;
    detail: string;
    fige?: boolean;
  }) => (
    <label className="flex items-start gap-3 py-2">
      <input
        type="checkbox"
        checked={on}
        disabled={fige}
        onChange={(e) => set?.(e.target.checked)}
        className="mt-1 h-4 w-4 shrink-0 accent-violet-fluo"
      />
      <span>
        <span className="block text-sm font-medium text-text">{titre}</span>
        <span className="block text-xs text-text-faint">{d}</span>
      </span>
    </label>
  );

  return (
    <div
      role="dialog"
      aria-label={t("cookie_title")}
      className="fixed inset-x-0 bottom-0 z-[60] border-t border-violet-soft bg-surface/95 px-4 py-4 backdrop-blur print:hidden"
    >
      <div className="mx-auto flex max-w-4xl flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-text">{t("cookie_title")}</p>
          <p className="mt-1 text-xs leading-relaxed text-text-muted">{t("cookie_body")}</p>
          <Link href="/beta/privacy" className="mt-1 inline-block text-xs text-gold underline">
            {t("cookie_more")}
          </Link>

          {detail && (
            <div className="mt-2 border-t border-violet-soft pt-2">
              <Case on fige titre={t("cookie_necessary")} detail={t("cookie_necessary_d")} />
              <Case on={mesure} set={setMesure} titre={t("cookie_measure")} detail={t("cookie_measure_d")} />
              <Case on={marketing} set={setMarketing} titre={t("cookie_marketing")} detail={t("cookie_marketing_d")} />
              <button
                type="button"
                onClick={() => repond(mesure, marketing)}
                className="mt-2 rounded-md bg-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-fluo"
              >
                {t("cookie_save")}
              </button>
            </div>
          )}
        </div>

        {!detail && (
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            {/* Refuser est aussi court qu'accepter : un clic, même taille. */}
            <button
              type="button"
              onClick={() => repond(false, false)}
              className="rounded-md border border-violet-soft px-4 py-2 text-sm text-text transition hover:border-violet-fluo"
            >
              {t("cookie_refuse")}
            </button>
            <button
              type="button"
              onClick={() => repond(true, true)}
              className="rounded-md bg-violet px-4 py-2 text-sm font-medium text-white transition hover:bg-violet-fluo"
            >
              {t("cookie_accept")}
            </button>
            <button
              type="button"
              onClick={() => setDetail(true)}
              className="rounded-md px-2 py-2 text-xs text-text-faint underline transition hover:text-text"
            >
              {t("cookie_choose")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export { COOKIE, VERSION };
