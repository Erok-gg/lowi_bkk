/**
 * Annexe — le « Methodology & Limitations » joint en fin de bilan, identique à
 * chaque rapport. Texte de référence et justification de chaque choix de
 * divulgation : bilan_RE/docs/annexe-methodologie-client.md, adossé à
 * bilan_RE/docs/methodologies-de-reference.md.
 *
 * Trois contraintes tenues ici, et vérifiées par agents/tests/test_annexe.py :
 *
 *   1. AUCUNE SOURCE NOMMÉE, AUCUN DÉCOMPTE DE SOURCES. Demande utilisateur du
 *      2026-10-20 : « un agrégat de données provenant de sources publiques
 *      disponibles représentant des offres de prix », et rien de plus. C'est
 *      aussi ce qui a fait retirer `h.portails` de l'identité du rapport et
 *      `calc.sources_gardees` du bloc méthode : les deux les nommaient.
 *   2. JAMAIS « valuation » NI « appraisal » EN AFFIRMATION — termes réservés
 *      aux évaluateurs agréés (docs/journal-juridique.md, point 12). Ils ne
 *      figurent qu'en négation, ce qu'exige le point 6 du même journal.
 *   3. AUCUNE CONSTANTE CHIFFRÉE de la méthode : ni borne de plausibilité, ni
 *      poids, ni minimum d'échantillon, ni tolérance de surface. Le texte dit
 *      que des seuils existent et que le rapport se taît quand ils ne sont pas
 *      atteints — jamais leur valeur. C'est la ligne que tiennent tous les
 *      acteurs établis : IOSCO a amendé ses principes 4, 5 et 12 pour
 *      clarifier que la transparence exigée n'équivaut PAS à une divulgation
 *      complète, et a retiré l'exigence de pouvoir répliquer un niveau publié.
 *
 * En échange de cette opacité, trois choses se disent sans détour, et ce sont
 * elles qui font la différence entre un secret légitime et une boîte noire :
 * la DATE des données et la règle de révision, ce qui n'est PAS mesuré (dont
 * le fait que la précision des scores n'est pas encore établie), et la VERSION
 * de méthode. Les trois sont dans le texte ci-dessous ; les retirer vide
 * l'annexe de sa fonction.
 */
import type { Rapport } from "@/bilan_RE/web/lib/types";

/**
 * Date du dernier changement de méthode, tenue À LA MAIN.
 *
 * `config_version` vit dans `bilan_RE/tension/config.json` mais ne porte pas sa
 * date : rien ne la déduit. À reporter ici à chaque incrément de version, comme
 * les crons du widget de bureau — et avec le même défaut connu, rien ne signale
 * la désynchronisation. Valeur actuelle : version 1, posée le 2026-10-17
 * (docs/methodes-calculs.md §12).
 */
export const METHODE_CHANGEE_LE = "2026-10-17";

const jour = (s: string) =>
  new Date(s + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

/** Une date affichable, ou « — » : jamais une date inventée ni la date du jour. */
const ou = (s: string | null | undefined) => (s ? jour(s.slice(0, 10)) : "—");

function Titre({ children }: { children: React.ReactNode }) {
  return <h3 className="mt-4 text-[13px] font-semibold leading-snug first:mt-0">{children}</h3>;
}

export default function Annexe({ r, doux, faible }: { r: Rapport; doux: string; faible: string }) {
  const calc = r.scores_calcul;

  return (
    <div className={`space-y-1 text-[11px] leading-relaxed ${doux}`}>
      <p className={`font-data text-[10px] uppercase tracking-[0.14em] ${faible}`}>
        Method version {calc?.config_version ?? "—"} · listing data as at {ou(r.donnees_du)} · market scores to{" "}
        {ou(calc?.fin_fenetre)} · method last changed {jour(METHODE_CHANGEE_LE)}
      </p>

      <Titre>What this report is</Titre>
      <p>
        A <strong>market analysis</strong>: it places this unit, and the building it sits in, against the other units
        currently offered on the Bangkok condominium market. Every figure is a <strong>relative position</strong> — is
        this unit priced above or below its comparable set, is this district tightening or loosening — and none is an
        estimate of what the unit is worth. It is <strong>not</strong> a valuation, not an appraisal, not a survey, and
        not investment advice. No figure in it is a recommendation to buy, to sell, or to hold.
      </p>

      <Titre>Where the numbers come from</Titre>
      <p>
        All figures are derived from an <strong>aggregate of publicly available sources</strong> reflecting{" "}
        <strong>asking prices</strong> — what sellers and landlords are currently asking. This matters more than any
        other statement in this annex. <strong>No public source in Thailand discloses the price actually paid.</strong>{" "}
        Every figure therefore measures seller demand, not concluded transactions, which is why this report ranks and
        compares rather than estimating a value. It reproduces no listing, photograph, description or link: only figures
        computed from them.
      </p>

      <Titre>Reference date, and revision</Titre>
      <p>
        Figures are computed over a rolling window ending on the dates shown above, and market scores are recalculated{" "}
        {calc?.frequence_calcul === "mensuelle" ? "monthly" : "periodically"}. Earlier figures{" "}
        <strong>are expected to change</strong> as later data arrives: a window that looked complete can be revised once
        withdrawals and re-listings are resolved. Comparisons between reports should always be read against the method
        version, printed above.
      </p>

      <Titre>What was examined, and what was not</Titre>
      <p>
        Examined: asking prices, asking rents, floor areas, bedroom and bathroom counts, building identity and location,
        and the appearance and disappearance of offers over time.
      </p>
      <p>
        <strong>Not examined, and assumed as stated by the source:</strong> the unit itself — there has been{" "}
        <strong>no inspection</strong>, internal or external; <strong>title, ownership, encumbrances and
        foreign-ownership quota</strong>, none of which has been verified against any register;{" "}
        <strong>floor area</strong>, taken as published, not measured and not checked against title; building condition,
        management, sinking fund and common-area charges; and <strong>any legal, tax or planning due diligence
        whatsoever</strong>. Where information could not be verified, it has been <strong>assumed to be correct</strong>.
        Verify each of these points independently before committing.
      </p>

      <Titre>How the figures are built</Titre>
      <p>
        Stated at the level of approach. The specific thresholds, weights and bounds are proprietary and are not
        published — consistent with the practice of established index and automated-estimate providers, which publish
        inputs, coverage, dates and limitations while withholding the parameters that would allow a result to be
        reproduced.
      </p>
      <ul className="ml-4 list-disc space-y-1">
        <li>
          <strong>Sanitised perimeter.</strong> Entries whose price, rent or area falls outside a plausible range are
          excluded before anything is computed — typically a rent filed as a sale, a daily rate, or a whole project's
          area entered against a single unit. Every figure uses the same perimeter; none is re-filtered afterwards.
        </li>
        <li>
          <strong>Like-for-like comparison.</strong> Prices are compared within the same building and at the same
          bedroom count wherever the data allows, rather than across a district. This neutralises the effect of age,
          view, floor and finish without needing to observe them — the reasoning behind repeat-sales property indices.
        </li>
        <li>
          <strong>The unit of measurement is a group of comparable units</strong>, not a listing: same building, same
          bedroom count, same narrow size band, same offer type. One flat advertised three times is one group, not
          three. This is the central correction in the method, because{" "}
          <strong>an offer leaving the market is not a sale</strong> — a large share of withdrawals are re-publications
          of the same unit.
        </li>
        <li>
          <strong>Scores are positions out of 100</strong> against the distribution of Bangkok districts over the
          preceding months, where 50 is a typical district. They are not percentages of anything.
        </li>
        <li>
          <strong>Small samples are pulled toward their broader context</strong> — a building toward its neighbourhood,
          a neighbourhood toward its district — so a thin sample cannot produce an extreme score on its own.
        </li>
        <li>
          <strong>Each score carries a range, not just a value.</strong> Where that range spans the boundary between two
          readings, the report says so instead of asserting one; where it is too wide to mean anything, it states{" "}
          <strong>not enough data</strong> and no score is given.
        </li>
        <li>
          <strong>Minimum sample sizes apply</strong> to every published figure. When they are not met the figure is
          withheld rather than shown weak, and the reference set actually used is stated on the figure itself.
        </li>
      </ul>

      <Titre>What this report does not measure, and why</Titre>
      <ul className="ml-4 list-disc space-y-1">
        <li>
          <strong>Transaction prices</strong> — no public source discloses them.
        </li>
        <li>
          <strong>Age-related depreciation</strong> — construction year is not reliably available in the source data.
        </li>
        <li>
          <strong>Statistics by foreign-ownership quota</strong> — stated on too few offers to support any figure.
        </li>
        <li>
          <strong>Listing history by agent</strong> — concerns an identifiable person; excluded by choice.
        </li>
        <li>
          <strong>Social-media offers</strong> — unverified and self-declared; held separately and never mixed into
          market figures.
        </li>
        <li>
          <strong>Transaction costs, taxes and running charges</strong> — not derived from this data; any figures shown
          come from a separate, dated source and are indicative.
        </li>
      </ul>

      <Titre>Known limitations</Titre>
      <ol className="ml-4 list-decimal space-y-1">
        <li>
          <strong>Asking prices, and withdrawals of offers — not sales.</strong> Stated again here because it bounds
          everything above.
        </li>
        <li>
          <strong>Source composition varies between windows.</strong> The mix behind a figure is not constant over
          time: a source behaving abnormally is excluded from that window, and that exclusion changes what the window
          measures. <strong>Figures from different reports are therefore not yet a comparable series</strong> and should
          not be read as a trend.
        </li>
        <li>
          <strong>Accuracy has not yet been measured.</strong> The weights in the scores are starting assumptions, not
          calibrated values. They will be tested against what actually happens — does a score at one date anticipate
          the price reductions and selling times that follow — once enough clean history exists.{" "}
          <strong>Until that test has been run, no claim is made about the predictive accuracy of any score here.</strong>
        </li>
        <li>
          <strong>Coverage is uneven across the city.</strong> Districts carrying few offers yield wider ranges and more
          withheld figures. This is visible on each figure rather than averaged away.
        </li>
        <li>
          <strong>Projections, where shown, are conditional scenarios</strong> built on stated assumptions. They are not
          forecasts and carry no commitment.
        </li>
      </ol>

      <Titre>Method version and changes</Titre>
      <p>
        Every report prints the method version it was produced under. The method is frozen under that identifier: two
        reports bearing the same version were computed the same way. Any change takes a new version, with the date and
        the nature of the change recorded. A record of changes is available on request.
      </p>

      <Titre>Important notice</Titre>
      <p className={faible}>
        This report is a market analysis derived from publicly available asking-price data. It is not a valuation, an
        appraisal, a survey, a legal or tax opinion, or investment advice, and it must not be relied upon as any of
        those. It contains no recommendation to enter into any transaction. Figures are indicative, rest on unverified
        source data, and will change. Any decision remains the reader's own, and should be taken only after independent
        professional advice and verification of title, area, ownership eligibility, building condition and all
        applicable costs and taxes.
      </p>
      <p className={faible}>
        Report generated on {ou(r.genere_le)} · reference {r.id}
      </p>
    </div>
  );
}
