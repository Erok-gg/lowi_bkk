# Annexe client — *Methodology & Limitations*

> **Mode d'emploi (interne, ne pas livrer).**
>
> Texte à joindre **identique à chaque bilan**, en dernière page. Il est en
> anglais, comme toute l'interface (`CLAUDE.md`, « Interface & navigation »).
>
> **Ce qu'il divulgue, et pourquoi exactement cela** : la grille vient de
> [methodologies-de-reference.md](methodologies-de-reference.md) — intrants,
> périmètre, date, limites et version sont publics chez tous les acteurs
> établis ; poids, seuils et bornes ne le sont chez aucun, et IOSCO a
> explicitement écarté l'exigence de réplicabilité.
>
> **Trois contraintes tenues dans le texte :**
> 1. **Aucune plateforme nommée, aucun décompte de sources** — « publicly
>    available sources » et rien de plus (demande utilisateur, 2026-10-20).
> 2. **Jamais « valuation » ni « appraisal »** — réservés aux évaluateurs
>    agréés ([journal-juridique.md](journal-juridique.md), point 12). Partout :
>    *market analysis*, *relative positioning*, *indicative*.
> 3. **Aucune constante chiffrée** : pas de bornes de plausibilité, pas de
>    poids, pas de minimum d'échantillon, pas de tolérance de surface. Le texte
>    dit que des seuils existent et que le rapport le signale quand ils ne sont
>    pas atteints — jamais leur valeur.
>
> **Trois champs à renseigner à chaque édition** (marqués `[...]`) : la date de
> fin de fenêtre, l'identifiant de version de méthode, la date de dernier
> changement de méthode. Les laisser vides vide l'annexe de sa fonction.
>
> **Deux arbitrages laissés à l'utilisateur**, signalés en commentaire dans le
> texte : (a) publier ou non la part chiffrée des retraits qui sont des
> republications ; (b) publier ou non la liste datée des changements de méthode
> en annexe du bilan plutôt que sur demande.
>
> **À reprendre dès qu'une de ces trois choses change** : une méthode (→ nouvelle
> version), la mesure de précision (la section la déclare absente — elle devra
> porter un chiffre dès ~3 mois d'historique propre), ou la santé des sources.

---

## Methodology & Limitations

*Version `[config_version]` — data as at `[date de fin de fenêtre]` — method last
changed `[date]`.*

### What this report is

A **market analysis**: it places one unit, and the building it sits in, against
the other units currently offered on the Bangkok condominium market. Every
figure is a **relative position** — is this unit priced above or below its
comparable set, is this district tightening or loosening — and none is an
estimate of what the unit is worth.

It is **not** a valuation, not an appraisal, not a survey, and not investment
advice. No figure in it is a recommendation to buy, to sell, or to hold.

### Where the numbers come from

All figures are derived from an **aggregate of publicly available sources**
reflecting **asking prices** — what sellers and landlords are currently asking.

This matters more than any other statement in this annex. **No public source in
Thailand discloses the price actually paid.** Every figure in this report
therefore measures **seller demand**, not concluded transactions. That is why
the report ranks and compares rather than estimating a value.

The report does not reproduce listings, photographs, descriptions or links. It
publishes only figures computed from them.

### Reference date, and revision

Figures are computed over a rolling window ending on the date shown above, and
recalculated **monthly**. Earlier figures **are expected to change** as later
data arrives: a window that looked complete can be revised once withdrawals and
re-listings are resolved. Comparisons across editions should always be read
against the method version, which is printed on every report.

### What was examined, and what was not

Examined: asking prices, asking rents, floor areas, bedroom and bathroom counts,
building identity and location, and the appearance and disappearance of offers
over time.

**Not examined, and assumed as stated by the source:**

- The unit itself. There has been **no inspection**, internal or external.
- **Title, ownership, encumbrances, and foreign-ownership quota.** None of these
  has been verified against any register.
- **Floor area.** Taken as published; not measured and not checked against title.
- **Building condition, management, sinking fund, or common-area charges.**
- **Any legal, tax or planning due diligence whatsoever.**

Where information could not be verified, it has been **assumed to be correct**.
A reader acting on this report should verify each of the points above
independently before committing.

### How the figures are built

Stated at the level of approach. The specific thresholds, weights and bounds are
proprietary and are not published — consistent with the practice of established
index and automated-estimate providers, which publish inputs, coverage, dates
and limitations while withholding the parameters that would allow a result to be
reproduced.

- **Sanitised perimeter.** Entries whose price, rent or area falls outside a
  plausible range are excluded before anything is computed — typically a rent
  filed as a sale, a daily rate, or a whole project's area entered against a
  single unit. Every figure in the report uses the same perimeter; none is
  re-filtered afterwards.
- **Like-for-like comparison.** Prices are compared **within the same building**
  and at the same bedroom count wherever the data allows, rather than across a
  district. This neutralises the effect of age, view, floor and finish without
  needing to observe them — the same reasoning behind repeat-sales property
  indices.
- **The unit of measurement is a cohort**, not a listing: the same building, the
  same bedroom count, the same narrow size band, the same offer type. A single
  flat advertised three times is one cohort, not three. This is the central
  correction in the method, because **an offer disappearing from the market is
  not a sale** — a large share of withdrawals are re-publications of the same
  unit. <!-- arbitrage (a) : remplacer par la part chiffrée si l'utilisateur le souhaite -->
- **Scores are expressed out of 100**, against the distribution of Bangkok
  districts over the preceding months, where **50 is a typical district**. They
  are positions in that distribution, not percentages of anything.
- **Small samples are pulled toward their broader context** — a building toward
  its neighbourhood, a neighbourhood toward its district — so that a thin
  sample cannot produce an extreme score on its own.
- **Each score carries a range, not just a value.** Where that range spans the
  boundary between two readings, the report says so instead of asserting one.
  Where it is too wide to mean anything, the report states **not enough data**
  and no score is given.
- **Minimum sample sizes apply** to every published figure. When they are not
  met, the figure is withheld rather than shown weak. Which reference set was
  used is stated on the figure itself.

### What this report does not measure, and why

| Not measured | Reason |
|---|---|
| Transaction prices | no public source discloses them |
| Age-related depreciation | construction year is not available in the source data |
| Statistics by foreign-ownership quota | stated on too few offers to support any figure |
| Listing history by agent | concerns an identifiable person; excluded by choice |
| Social-media offers | unverified and self-declared; held separately and **never** mixed into market figures |
| Transaction costs, taxes, and running charges | not derived from this data; any figures shown come from a separate, dated source and are indicative |

### Known limitations

1. **Asking prices, and withdrawals of offers — not sales.** Stated again here
   because it bounds everything above.
2. **Source composition varies between windows.** The mix of sources behind a
   figure is not constant over time. When a source behaves abnormally it is
   excluded from that window, and that exclusion changes what the window
   measures. **Figures from different editions are therefore not yet a
   comparable series**, and should not be read as a trend.
3. **Accuracy has not yet been measured.** The weights in the scores are
   starting assumptions, not calibrated values. They will be tested against
   what actually happens — does a score at one date anticipate the price
   reductions and selling times that follow — once enough clean history exists.
   **Until that test has been run, no claim is made about the predictive
   accuracy of any score in this report.**
4. **Coverage is uneven across the city.** Districts carrying few offers yield
   wider ranges and more withheld figures. This is visible on each figure rather
   than averaged away.
5. **Projections, where shown, are conditional scenarios** built on stated
   assumptions. They are not forecasts and carry no commitment.

### Method version and changes

Every report prints the method version it was produced under. The method is
frozen under that identifier: two reports bearing the same version were computed
the same way. Any change to the method takes a new version, with the date and
the nature of the change recorded. A record of changes is available on request.
<!-- arbitrage (b) : publier la liste datée en annexe plutôt que sur demande -->

### Important notice

This report is a market analysis derived from publicly available asking-price
data. It is not a valuation, an appraisal, a survey, a legal or tax opinion, or
investment advice, and it must not be relied upon as any of those. It contains
no recommendation to enter into any transaction. Figures are indicative, rest on
unverified source data, and will change. Any decision remains the reader's own,
and should be taken only after independent professional advice and verification
of title, area, ownership eligibility, building condition and all applicable
costs and taxes.
