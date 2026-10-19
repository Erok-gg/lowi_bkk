import Link from "next/link";
import { redirect } from "next/navigation";
import { accesProduit } from "@/bilan_RE/web/lib/acces";
import AnalyseForm from "@/bilan_RE/web/components/AnalyseForm";
import { i18n } from "@/bilan_RE/web/lib/langue";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Landing du produit.
 *
 * ACCÈS (2026-10-19). Elle est faite pour être publique — nav réduite à
 * connexion / inscription, aucun lien vers la carte ni vers les tableaux. Mais
 * l'ouverture ne se fait PAS en silence : il faut poser `LOWI_BETA_PUBLIQUE=1`.
 * Sans cette variable, le mot de passe partagé reste en place, exactement comme
 * avant. Ouvrir au public est une décision, pas un effet de bord d'un commit —
 * et le chemin du retour est le même interrupteur (règle 7).
 */


export default async function BetaPage() {
  if (!(await accesProduit())) redirect("/login?next=/beta");
  const { t, langue } = await i18n();

  const POINTS = [
    { t: t("land_p1_t"), d: t("land_p1_d") },
    { t: t("land_p2_t"), d: t("land_p2_d") },
    { t: t("land_p3_t"), d: t("land_p3_d") },
    { t: t("land_p4_t"), d: t("land_p4_d") },
  ];

  return (
    <div className="h-full overflow-y-auto">
      <section className="mx-auto flex max-w-3xl flex-col items-center px-4 pb-16 pt-14 text-center sm:pt-24">
        <span className="mb-6 rounded-full border border-gold/40 px-3 py-1 text-xs uppercase tracking-[0.18em] text-gold">
          {t("land_badge")}
        </span>
        <h1 className="text-3xl font-semibold leading-tight text-text sm:text-5xl">
          {t("land_title_a")}{" "}
          {/* La mise en valeur du mot « before » n'existe qu'en anglais : en thaï
              et en chinois la phrase se construit autrement, les deux morceaux
              suivants sont alors vides et rien ne casse. */}
          {t("land_title_em") && <span className="text-violet-fluo">{t("land_title_em")}</span>}{" "}
          {t("land_title_b")}
        </h1>
        <p className="mt-5 max-w-xl text-base text-text-muted sm:text-lg">{t("land_sub")}</p>
        <div className="mt-10 w-full max-w-2xl text-left">
          <AnalyseForm langue={langue} />
          <p className="mt-3 text-center text-xs text-text-faint">{t("land_free")}</p>
        </div>
      </section>
      <section className="mx-auto grid max-w-5xl gap-4 px-4 pb-20 sm:grid-cols-2 lg:grid-cols-4">
        {POINTS.map((p) => (
          <div key={p.t} className="rounded-2xl border border-violet-soft bg-surface p-5">
            <h2 className="text-base font-semibold text-text">{p.t}</h2>
            <p className="mt-2 text-sm text-text-muted">{p.d}</p>
          </div>
        ))}
      </section>
      <p className="mx-auto max-w-3xl px-4 pb-6 text-center text-xs text-text-faint">
        {/* « market analysis », jamais « valuation » ni « appraisal » : ces mots
            sont réservés aux évaluateurs agréés en Thaïlande (backlog #36). */}
        {t("land_disclaimer")}
      </p>
      <p className="pb-10 text-center text-xs">
        <Link href="/beta/privacy" className="text-text-faint underline">
          {t("cookie_more")}
        </Link>
      </p>
    </div>
  );
}
