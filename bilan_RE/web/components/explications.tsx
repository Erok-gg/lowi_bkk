/**
 * explications — le « How is this computed? » de chaque bloc, en anglais (règle du
 * site). Repliées à l'écran, imprimées en entier dans le PDF. Elles décrivent ce
 * que fait réellement le code (bilan_RE/tension/, methodes-calculs.md §12) : toute
 * modification de méthode se reporte ici.
 */
export const EXPLICATIONS = {
  prix:
    "We compare this listing's asking price per m² with other units currently for sale: first the whole building, then the " +
    "same building with the same number of bedrooms and a size within ±15%, then within 1 km, then the district. Copies of " +
    "the same unit published by several agents or portals count once. Each dot is one comparable unit; the dashed line is " +
    "the median. With fewer than 5 comparables we show no verdict. These are asking prices, not sold prices.",
  histoire:
    "We follow the same unit across five portals. Two listings are treated as the same unit when they share the floor (when " +
    "known), the size within 1 m² and the price within 5%, and appear within 14 days of each other. Reposts by agents are " +
    "therefore part of one history, and 'listed for' counts from the first time the unit was seen.",
  tension:
    "A score out of 100 that says who has the upper hand: 50 is a typical Bangkok district over the last 12 months, lower " +
    "favours buyers, higher favours sellers. It combines five signals measured on groups of comparable units (same " +
    "building, bedrooms and 5 m² size band): how many leave the market each month, how long they take to go, whether supply " +
    "is growing, how often prices are cut, and how many sellers compete in the same buildings. A unit relisted by an agent " +
    "does not count as sold. The range shows the uncertainty (bootstrap); the label is only stated when the whole range " +
    "sits on one side of a threshold. Calculated monthly.",
  liquidite:
    "How easily a unit like this one resells at market price. We only time units listed close to the price of similar " +
    "units in their own building (±10%), because an overpriced listing stays online because of its price, not the market. " +
    "Signals: median time to leave the market (survival analysis, which accounts for units still for sale) and the chance " +
    "of leaving within 90 days, compared with the rest of Bangkok and by building age.",
  immeuble:
    "Building facts come from the listings themselves and are aggregated per building. Completion year is the most frequent " +
    "value across portals; common fees are the median of the fees stated on listings, per m² per month. Units for sale " +
    "counts distinct units, not listings.",
  drapeaux:
    "Automatic checks: a price per m² more than 40% below the building (often an error, leasehold or a bait listing); a " +
    "unit in the Thai quota, which a foreigner cannot own freehold in their own name; a quota not stated; portals that " +
    "disagree on the completion year; an area that is very small for the number of bedrooms.",
  limites:
    "This report uses asking prices and listing exits observed on public portals, not land-office transactions. A listing " +
    "that leaves a portal may have sold, been rented out or been withdrawn. Market scores are recalculated monthly and a " +
    "portal whose data looks broken for the period is left out automatically. This is not investment advice.",
} as const;
