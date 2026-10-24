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
 *
 * Refonte du 2026-10-22 : bloc club deal + FAQ à la place des quatre cartes,
 * pied de page à quatre éléments, trois menus de profil. Depuis le 2026-10-22,
 * « Nationality » et « Purpose » sont relus par AnalyseForm au moment de l'envoi et
 * gardés dans un cookie (bilan_RE/web/lib/profil.ts) : le profil investisseur
 * ajoute au rapport le loyer estimé et la rénovation. Rien n'est stocké côté serveur.
 */

// Textes en anglais seul : le bloc club deal et la FAQ n'ont pas de traduction relue.
const FAQ = [
  {
    q: "What does Lowi do?",
    a: "Lowi compares a listing with the rest of the market: same building, same bedrooms and size, within 1 km. It gives you the price gap, how long the unit has been listed, and who has the upper hand in negotiation.",
  },
  {
    q: "Where does the data come from?",
    a: "From publicly available property listings that we aggregate and clean. Copies of the same unit published more than once count once.",
  },
  {
    q: "Are these sold prices?",
    a: "No. They are asking prices and listings leaving the market, not confirmed sales. This is market analysis, not a valuation.",
  },
  {
    q: "Is it free?",
    a: "The summary is free. The full report is available as a PDF.",
  },
  {
    q: "Do you take anything from the seller?",
    a: "No. Lowi takes nothing from the seller, and does not sell your search to anyone.",
  },
  {
    q: "My link says the listing is not in the database.",
    a: "The database is updated every day. Come back tomorrow at the same time and it will work.",
  },
];

const SELECT =
  "h-11 w-full min-w-0 truncate rounded-xl border border-rule bg-surface px-3 text-sm text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/40";

export default async function BetaPage() {
  if (!(await accesProduit())) redirect("/login?next=/beta");
  const { t, langue } = await i18n();

  return (
    <div className="h-full overflow-y-auto">
      <section className="mx-auto flex max-w-3xl flex-col items-center px-4 pb-16 pt-14 text-center sm:pt-24">
        <h1 className="text-3xl font-semibold leading-tight text-ink sm:text-5xl">
          {t("land_title_a")}{" "}
          {/* La mise en valeur n'existe plus (titre du 2026-10-22) ; la clé reste
              pour ne pas casser les trois langues. */}
          {t("land_title_em") && <span className="text-brand">{t("land_title_em")}</span>}{" "}
          {t("land_title_b")}
        </h1>
        <p className="mt-5 max-w-xl text-base text-muted sm:text-lg">{t("land_sub")}</p>
        <div className="mt-10 w-full max-w-2xl text-left">
          {/* Une seule ligne, y compris sur mobile (3 colonnes égales, texte tronqué). */}
          <div className="mb-3 grid grid-cols-3 gap-2">
            <select id="profil-nat" aria-label="Nationality" defaultValue="foreigner" className={SELECT}>
              <option value="foreigner">I am a foreigner</option>
              <option value="thai">I am a Thai national</option>
            </select>
            <select id="profil-but" aria-label="Purpose" defaultValue="invest" className={SELECT}>
              <option value="invest">I invest in properties</option>
              <option value="live">I&apos;m looking for my new home</option>
              <option value="sell">I sell my property</option>
            </select>
            <select aria-label="Location" disabled defaultValue="bangkok" className={`${SELECT} cursor-not-allowed bg-sunken text-faint`}>
              <option value="bangkok">In Bangkok</option>
            </select>
          </div>
          <AnalyseForm langue={langue} />
          <p className="mt-3 text-center text-xs text-faint">{t("land_free")}</p>
        </div>
      </section>

      {/* Club deal — noir et blanc, comme www.lowi.asia */}
      <section className="mx-auto max-w-5xl px-4 pb-16">
        <div className="flex flex-col items-start justify-between gap-6 rounded-2xl bg-black px-8 py-10 text-white sm:flex-row sm:items-center">
          <h2 className="max-w-md text-2xl font-semibold leading-snug">
            Looking for investment in Bangkok?
            <span className="block text-white/70">Learn more about our club deal!</span>
          </h2>
          <a
            href="https://www.lowi.asia"
            target="_blank"
            rel="noopener"
            className="inline-flex h-12 shrink-0 items-center justify-center rounded-full bg-white px-7 text-sm font-semibold text-black transition hover:bg-white/85"
          >
            Learn more
          </a>
        </div>
      </section>

      <section className="mx-auto max-w-3xl px-4 pb-20">
        <h2 className="text-2xl font-semibold text-ink">FAQ</h2>
        <p className="mt-1 text-sm text-muted">Frequently asked questions &amp; answers</p>
        <div className="mt-6 divide-y divide-rule border-y border-rule">
          {FAQ.map((f) => (
            <details key={f.q} className="group py-4">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-base font-medium text-ink">
                {f.q}
                <span aria-hidden="true" className="text-muted transition group-open:rotate-45">+</span>
              </summary>
              <p className="mt-3 text-sm leading-relaxed text-muted">{f.a}</p>
            </details>
          ))}
        </div>
      </section>

      <footer className="border-t border-rule px-4 py-8">
        <div className="mx-auto flex max-w-5xl flex-col items-center gap-4 text-center text-xs text-faint md:flex-row md:justify-between md:text-left">
          <p>
            <span className="font-semibold text-neg">Private Beta</span> · For informational purposes only. Not financial
            or investment advice.
          </p>
          <div className="flex items-center gap-5">
            <a
              href="mailto:lowi.platform@gmail.com"
              className="rounded-full border border-rule px-4 py-1.5 font-medium text-ink transition hover:bg-sunken"
            >
              Contact
            </a>
            <Link href="/beta/privacy" className="underline">
              Privacy notice
            </Link>
            <span>© 2026 Lowi</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
