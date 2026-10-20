"use client";
/**
 * Report — le bilan d'une annonce, en trois rendus à partir des mêmes données :
 *   · mobile (< 1024 px) : une colonne, blocs repliables, barres des signaux au
 *     dépliage seulement, bouton PDF collé en bas ;
 *   · PC (≥ 1024 px, pensé pour 1920 × 1080) : colonne gauche collante
 *     (identité, verdict, chiffres clés, bouton PDF), blocs en deux colonnes ;
 *   · PDF (mode="pdf") : fond clair, tout déplié, explications imprimées.
 * Règles : bilan_RE/docs/regles-construction-ui.md.
 */
import { useState } from "react";
import type { Chaine, Comparaison, Niveau, Rapport } from "@/bilan_RE/web/lib/types";
import { EXPLICATIONS } from "./explications";
import PdfGate from "./PdfGate";
import type { Langue } from "@/bilan_RE/web/i18n";
import { palettes } from "@/config/theme";

type Mode = "web" | "pdf";
const thb = (v: number) => "THB " + (v >= 1e6 ? (v / 1e6).toFixed(2) + "M" : Math.round(v).toLocaleString("en-US"));
const k = (v: number) => Math.round(v / 1000).toLocaleString("en-US") + "k";
const pct = (v: number) => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(Math.round(v * 100)) + "%";
const date = (s: string) =>
  new Date(s + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

/**
 * Palette par rendu. Depuis le thème « Ledger » (vert/or/blanc) les DEUX rendus
 * sont clairs : l'écran et le papier ne diffèrent plus que par le fond (blanc
 * franc à l'impression) et par ce qui est déplié.
 *
 * Les couleurs de classe passent par les jetons (`bg-surface`, `text-muted`…)
 * et suivent donc le thème. Les trois couleurs SVG, elles, sont lues dans
 * `palettes.ledger` : `var()` n'est pas interprété dans un attribut de
 * présentation SVG (`fill="rgb(var(--x))"` ne peint rien), et recopier les hex
 * ici les aurait fait dériver de `config/theme.ts`.
 */
function palette(mode: Mode) {
  const L = palettes.ledger;
  const svg = { piste: L.sunken, point: L.faint, accent: L.brand };
  return mode === "pdf"
    ? { page: "bg-white text-ink", carte: "bg-white border border-rule", doux: "text-muted",
        faible: "text-faint", fond2: "bg-sunken", ...svg }
    : { page: "text-ink", carte: "bg-surface border border-rule", doux: "text-muted",
        faible: "text-faint", fond2: "bg-sunken", ...svg };
}

/** Pastille d'un libellé de score — en jetons, donc juste dans les deux thèmes. */
function couleurLibelle(l: string) {
  if (l.includes("buyer") || l.includes("hard")) return "bg-warn/15 text-warn";
  if (l.includes("seller") || l.includes("easy")) return "bg-pos/15 text-pos";
  if (l.includes("not enough") || l.includes("no reference")) return "bg-faint/15 text-faint";
  return "bg-info/15 text-info";
}

function Bloc({ titre, id, mode, ouvert = false, children, resume }: {
  titre: string; id: keyof typeof EXPLICATIONS; mode: Mode; ouvert?: boolean;
  children: React.ReactNode; resume?: React.ReactNode;
}) {
  const [open, setOpen] = useState(ouvert);
  const [aide, setAide] = useState(false);
  const P = palette(mode);
  const pdf = mode === "pdf";
  return (
    <section className={`${P.carte} break-inside-avoid rounded-2xl p-5`}>
      <button type="button" onClick={() => setOpen(!open)} disabled={pdf} aria-expanded={pdf || open}
        className="flex w-full items-center justify-between gap-3 text-left lg:pointer-events-none">
        <h2 className="text-base font-semibold">{titre}</h2>
        {!pdf && <span className={`${P.doux} text-lg lg:hidden`} aria-hidden="true">{open ? "▴" : "▾"}</span>}
      </button>
      {resume && <div className="mt-2">{resume}</div>}
      <div className={pdf ? "mt-3" : `${open ? "" : "hidden"} mt-3 lg:block`}>
        {children}
        {pdf ? (
          <div className={`mt-4 rounded-lg ${P.fond2} p-3 text-xs leading-relaxed ${P.doux}`}>
            <p className="mb-1 font-semibold">How is this computed?</p>
            {EXPLICATIONS[id]}
          </div>
        ) : (
          <div className="mt-3">
            <button type="button" onClick={() => setAide(!aide)} className={`text-xs underline ${P.faible}`}>
              {aide ? "Hide method" : "How is this computed?"}
            </button>
            {aide && <p className={`mt-2 text-xs leading-relaxed ${P.doux}`}>{EXPLICATIONS[id]}</p>}
          </div>
        )}
      </div>
    </section>
  );
}

function Score({ n, mode }: { n: (Niveau & { niveau?: string }) | null | undefined; mode: Mode }) {
  const P = palette(mode);
  if (!n || n.score === null)
    return <p className={`text-sm ${P.doux}`}>Not enough data yet for a reliable score at this level.</p>;
  return (
    <div>
      <div className="flex items-baseline gap-2">
        <span className="font-data text-5xl">{n.score}</span>
        <span className={P.doux}>/ 100</span>
        <span className={`ml-auto rounded-md px-2.5 py-1 text-xs ${couleurLibelle(n.libelle)}`}>{n.libelle}</span>
      </div>
      <Echelle n={n} mode={mode} />
      <p className={`mt-1 text-xs ${P.faible}`}>
        Likely range {n.p10}–{n.p90} · {n.niveau ? `${n.niveau} · ` : ""}n = {n.n_cohortes.toLocaleString("en-US")} unit
        groups, {n.n_sorties} exits
      </p>
    </div>
  );
}

function Echelle({ n, mode }: { n: Niveau; mode: Mode }) {
  const P = palette(mode);
  const x = (v: number) => 4 + (v / 100) * 312;
  return (
    <svg viewBox="0 0 320 30" className="mt-3 w-full" role="img"
      aria-label={`Score ${n.score} on a 0 to 100 scale, likely range ${n.p10} to ${n.p90}`}>
      <rect x="4" y="12" width="108" height="6" rx="3" fill={palettes.ledger.warn} opacity="0.25" />
      <rect x="113" y="12" width="94" height="6" fill={P.piste} />
      <rect x="208" y="12" width="108" height="6" rx="3" fill={palettes.ledger.pos} opacity="0.25" />
      <rect x={x(n.p10 ?? 0)} y="8" width={Math.max(2, x(n.p90 ?? 0) - x(n.p10 ?? 0))} height="14" rx="4"
        fill="none" stroke={P.accent} strokeWidth="1.5" />
      <circle cx={x(n.score ?? 0)} cy="15" r="5.5" fill={P.accent} />
      <text x="4" y="29" fontSize="9" fill={P.point}>buyer's</text>
      <text x="160" y="29" fontSize="9" fill={P.point} textAnchor="middle">balanced</text>
      <text x="316" y="29" fontSize="9" fill={P.point} textAnchor="end">seller's</text>
    </svg>
  );
}

function Chaines({ chaine, mode }: { chaine: Chaine | null | undefined; mode: Mode }) {
  const P = palette(mode);
  if (!chaine) return null;
  return (
    <div className="mt-4 space-y-2">
      <p className={`text-xs ${P.doux}`}>Compared at every level</p>
      {Object.entries(chaine).map(([nom, brut]) => {
        // fourchette trop large = pas de chiffre affiché, même si le calcul en a un
        const v = brut.libelle === "not enough data" ? { ...brut, score: null } : brut;
        return (
        <div key={nom} className="grid grid-cols-[minmax(0,9rem)_1fr_2.5rem] items-center gap-2 text-xs">
          <span className="truncate">{nom.replace(", Bangkok", "").replace(" District", "")}</span>
          <div className="h-2 rounded" style={{ background: P.piste }}>
            {v.score !== null && (
              <div className="h-2 rounded" style={{ width: `${v.score}%`, background: P.accent }} />
            )}
          </div>
          <span className={`text-right tabular-nums ${v.score === null ? P.faible : ""}`}>{v.score ?? "—"}</span>
          <span className={`col-span-3 -mt-1 ${P.faible}`}>
            {v.score === null ? "not enough data · " : `${v.libelle} · `}n = {v.n_cohortes}
          </span>
        </div>
        );
      })}
    </div>
  );
}

function Reglette({ c, prix, mode }: { c: Comparaison; prix: number; mode: Mode }) {
  const P = palette(mode);
  if (!c.points || c.points.length < 5) return null;
  const lo = Math.min(c.points[0], prix), hi = Math.max(c.points[c.points.length - 1], prix);
  const x = (v: number) => 8 + ((v - lo) / Math.max(1, hi - lo)) * 304;
  return (
    <svg viewBox="0 0 320 52" className="w-full" role="img"
      aria-label={`${c.n} comparable units from ${k(c.points[0])} to ${k(c.points[c.points.length - 1])} THB per m², this listing at ${k(prix)}`}>
      <line x1="8" y1="24" x2="312" y2="24" stroke={P.piste} strokeWidth="2" />
      {c.points.map((v, i) => (
        <circle key={i} cx={x(v)} cy={24 + ((i % 3) - 1) * 5} r="3.2" fill={P.point} opacity="0.75" />
      ))}
      {c.mediane && <line x1={x(c.mediane)} y1="8" x2={x(c.mediane)} y2="40" stroke={P.point} strokeDasharray="3 3" />}
      <circle cx={x(prix)} cy="24" r="7" fill={P.accent} stroke={palettes.ledger.surface} strokeWidth="2" />
      <text x="8" y="50" fontSize="9" fill={P.point}>{k(lo)}/m²</text>
      {c.mediane && <text x={x(c.mediane)} y="6" fontSize="9" fill={P.point} textAnchor="middle">median</text>}
      <text x="312" y="50" fontSize="9" fill={P.point} textAnchor="end">{k(hi)}/m²</text>
    </svg>
  );
}

/** Phrase de tête, par gabarit (aucune IA) : prix, ancienneté, tension. */
function verdict(r: Rapport): string {
  const c = r.prix?.find((x) => x.cle === "building_same" && x.mediane) ??
    r.prix?.find((x) => x.cle === "radius_same" && x.mediane) ?? r.prix?.find((x) => x.mediane);
  const h = r.histoire!;
  const morceaux: string[] = [];
  if (c?.ecart !== undefined)
    morceaux.push(Math.abs(c.ecart) < 0.03 ? `Priced in line with ${c.niveau.toLowerCase()}`
      : `Priced ${pct(c.ecart).replace("−", "")} ${c.ecart < 0 ? "below" : "above"} ${c.niveau.toLowerCase()}`);
  morceaux.push(`listed for ${h.jours_en_ligne} days${h.baisses ? ` with ${h.baisses} price cut${h.baisses > 1 ? "s" : ""}` : ""}`);
  const t = r.tension?.retenu;
  if (t) morceaux.push(`in a ${t.libelle.replace(" market", "")} market (${t.niveau.replace(", Bangkok", "")})`);
  const s = morceaux.join(", ");
  return s.charAt(0).toUpperCase() + s.slice(1) + ".";
}

/**
 * `acces` : l'état du compte, résolu par la page serveur (le composant est côté
 * navigateur et ne peut pas lire les cookies). Absent → bouton PDF ouvert comme
 * avant, ce qui garde la version imprimable et les tests inchangés.
 */
/**
 * MoisDeStock — « le marché en mois de stock », le dépliant pédagogique de la
 * tension (demandé le 2026-10-19 : « je trouve cela facile à comprendre »).
 *
 * Les trois bandes (< 3 / 4–6 / > 6 mois) sont le repère classique du métier,
 * et il est donné comme tel : c'est une grille de LECTURE, pas notre mesure.
 * Nous ne pouvons pas encore l'afficher sur l'annonce, et le dire est plus
 * utile que de l'inventer (règle 1, mesuré le 2026-10-17, journal-donnees) :
 *   · nos mois de stock se calculent sur des RETRAITS d'annonces, pas sur des
 *     ventes notariées comme le repère d'origine ;
 *   · net des republications, les 36 districts publiables vont de 5,7 à 28,9
 *     mois, médiane 13,0 : avec la grille absolue, 35 sur 36 seraient « buyer's
 *     market » et la jauge ne dirait plus rien ;
 *   · le délistage DDproperty est à l'arrêt depuis le 13/10, donc aucune
 *     fenêtre n'a encore ses deux grandes sources saines en même temps.
 * D'où un score RELATIF de 0 à 100, et cette explication pour le relier à la
 * grille que tout le monde connaît.
 */
function MoisDeStock({ mode }: { mode: Mode }) {
  const P = palette(mode);
  const pdf = mode === "pdf";
  const BANDES = [
    {
      t: "High tension",
      m: "under 3 months",
      d: "Very little on offer. Buyers move fast, units go almost as soon as they appear, and several buyers can end up on the same one.",
    },
    {
      t: "Balanced",
      m: "4 to 6 months",
      d: "A healthy market. There is room to negotiate, without having to rush.",
    },
    {
      t: "Low tension",
      m: "over 6 months",
      d: "More on offer than buyers. Sellers wait, and the leverage is on your side.",
    },
  ];
  return (
    <details open={pdf} className={`mt-4 rounded-lg ${P.fond2} p-3`}>
      <summary className={`cursor-pointer text-xs font-semibold ${P.doux} ${pdf ? "list-none" : ""}`}>
        Another way to read a market: months of supply
      </summary>
      <p className={`mt-2 text-xs leading-relaxed ${P.doux}`}>
        Months of supply is how long it would take to sell everything on the market at the current pace. It is the
        plainest way to say who has the upper hand:
      </p>
      <ul className="mt-2 space-y-1.5">
        {BANDES.map((b) => (
          <li key={b.t} className={`text-xs leading-relaxed ${P.doux}`}>
            <span className="font-semibold">{b.t}</span> ({b.m}) — {b.d}
          </li>
        ))}
      </ul>
      <p className={`mt-2 text-xs leading-relaxed ${P.faible}`}>
        We do not put a month figure on this listing yet, and we would rather say so. That scale was built on recorded
        sales; what we can see are listings leaving the portals, and one portal has been publishing no removals since 13
        October. Measured across Bangkok on 17 October, once agent reposts are removed, districts ranged from 5.7 to
        28.9 months — on that scale almost every district in the city reads as a buyer&apos;s market, which tells you
        nothing about where you actually have leverage. So the score above is relative instead: 50 is a typical Bangkok
        district over the last 12 months, lower means more leverage for you than usual, higher means less. The months
        figure appears here as soon as removals are reliable across portals.
      </p>
    </details>
  );
}

export default function Report({
  r,
  mode = "web",
  acces,
}: {
  r: Rapport;
  mode?: Mode;
  acces?: { langue: Langue; connecte: boolean; possede: boolean };
}) {
  const P = palette(mode);
  const pdf = mode === "pdf";
  const a = r.annonce!, h = r.histoire!;
  const meilleure = r.prix?.find((x) => x.cle === "building_same" && x.mediane) ??
    r.prix?.find((x) => x.cle === "radius_same" && x.mediane) ?? r.prix?.find((x) => x.mediane);
  const [niveauPrix, setNiveauPrix] = useState(meilleure?.cle ?? "building");
  const choisie = r.prix?.find((x) => x.cle === niveauPrix) ?? meilleure;
  const calc = r.scores_calcul;

  const identite = (
    <div>
      <p className={`font-data text-xs uppercase tracking-[0.14em] ${P.faible}`}>Buyer report · beta</p>
      <h1 className="mt-1 text-2xl font-semibold leading-tight 2xl:text-3xl">{a.condo.replace(", Bangkok", "")}</h1>
      <p className={`mt-1 text-sm ${P.doux}`}>
        {a.chambres ?? "?"} bed · {a.sdb ?? "?"} bath · {a.surface} m²{a.etage ? ` · floor ${a.etage}` : ""} ·{" "}
        {a.khet.replace(" District", "")}
      </p>
      <p className="mt-3 text-3xl font-semibold tabular-nums">{thb(a.prix)}</p>
      <p className={`text-sm ${P.doux}`}>{k(a.prix_m2)} THB / m² · listed on {h.portails.join(", ")}</p>
    </div>
  );

  const chiffres = (
    <div className="grid grid-cols-3 gap-2">
      {[
        { l: "Listed for", v: `${h.jours_en_ligne} d` },
        { l: "Since first seen", v: h.variation === null ? "—" : pct(h.variation) },
        { l: "For sale in building", v: String(r.immeuble?.lots_en_vente ?? "—") },
      ].map((x) => (
        <div key={x.l} className={`rounded-xl ${P.fond2} p-3`}>
          <p className={`text-[11px] ${P.doux}`}>{x.l}</p>
          <p className="text-xl font-semibold tabular-nums">{x.v}</p>
        </div>
      ))}
    </div>
  );

  const boutonPdf =
    !pdf &&
    (acces ? (
      <PdfGate rapportId={r.id} langue={acces.langue} connecte={acces.connecte} possede={acces.possede} />
    ) : (
      <a href={`/beta/r/${r.id}/pdf`} target="_blank" rel="noopener"
        className="flex h-14 w-full items-center justify-center gap-2 rounded-xl bg-gold text-base font-bold text-on-gold shadow-gold-glow transition hover:brightness-110 active:scale-[0.98]">
        <span aria-hidden="true">⬇</span> Get the full PDF report
      </a>
    ));

  const mentions = (
    <p className={`text-xs ${P.faible}`}>
      Asking prices, not sold prices. Listing data as of {r.donnees_du ? date(r.donnees_du) : "—"}. Market scores:{" "}
      {calc?.frequence_calcul === "mensuelle" ? "monthly calculation" : "calculation"}
      {calc?.fin_fenetre ? `, window ending ${date(calc.fin_fenetre)}` : " — not computed yet"}. Lowi takes nothing from
      the seller. Not investment advice.
    </p>
  );

  const blocs = (
    <>
      <Bloc titre="Price vs comparable units" id="prix" mode={mode} ouvert
        resume={choisie?.ecart !== undefined && (
          <p className={`text-sm ${P.doux}`}>
            <span className="font-semibold text-inherit">{pct(choisie.ecart)}</span> vs {choisie.niveau.toLowerCase()} ·
            cheaper than {100 - (choisie.rang_pct ?? 0)}% of them
          </p>
        )}>
        {!pdf && (
          <div className="mb-3 flex flex-wrap gap-1.5">
            {r.prix?.map((c) => (
              <button key={c.cle} type="button" onClick={() => setNiveauPrix(c.cle)} disabled={!c.mediane}
                className={`rounded-full border px-3 py-1 text-xs ${c.cle === niveauPrix
                  ? "border-brand bg-brand/15 text-ink" : "border-rule " + P.doux}
                  ${!c.mediane ? "opacity-40" : ""}`}>
                {c.niveau.replace("The building, ", "Building · ")} ({c.n})
              </button>
            ))}
          </div>
        )}
        {(pdf ? r.prix ?? [] : choisie ? [choisie] : []).map((c) => (
          <div key={c.cle} className="mb-3">
            {pdf && <p className="mb-1 text-sm font-semibold">{c.niveau} · n = {c.n}</p>}
            {c.mediane ? (
              <>
                <Reglette c={c} prix={a.prix_m2} mode={mode} />
                <p className={`text-xs ${P.doux}`}>
                  Median {k(c.mediane)}/m² · middle half {k(c.p25!)}–{k(c.p75!)} · this listing {k(a.prix_m2)} ({pct(c.ecart!)})
                  · {c.verdict} · n = {c.n}
                </p>
              </>
            ) : (
              <p className={`text-xs ${P.faible}`}>Not enough comparable units ({c.n}).</p>
            )}
          </div>
        ))}
      </Bloc>

      <Bloc titre="The listing's history" id="histoire" mode={mode} ouvert={pdf}
        resume={<p className={`text-sm ${P.doux}`}>First seen {date(h.premier_vu)} · {h.annonces} listing
          {h.annonces > 1 ? "s" : ""} for this unit on {h.portails.length} portal{h.portails.length > 1 ? "s" : ""}</p>}>
        <ol className="space-y-1.5 border-l-2 pl-4 text-sm" style={{ borderColor: P.piste }}>
          {h.evenements.slice(-12).map((e, i) => (
            <li key={i} className={e.type === "price_cut" ? "" : P.doux}>
              <span className="tabular-nums">{date(e.date)}</span> ·{" "}
              {e.type === "listed" ? `listed on ${e.source}` :
                `${e.type === "price_cut" ? "price cut" : "price rise"} ${thb(e.from!)} → ${thb(e.to!)} (${e.source})`}
            </li>
          ))}
        </ol>
        {h.evenements.length > 12 && (
          <p className={`mt-2 text-xs ${P.faible}`}>{h.evenements.length - 12} earlier events not shown.</p>
        )}
      </Bloc>

      <Bloc titre="Market tension" id="tension" mode={mode} ouvert={pdf}
        resume={<Score n={r.tension?.retenu} mode={mode} />}>
        <Chaines chaine={r.tension?.chaine} mode={mode} />
        <MoisDeStock mode={mode} />
      </Bloc>

      <Bloc titre="Ease of resale" id="liquidite" mode={mode} ouvert={pdf}
        resume={r.liquidite?.retenu ? <Score n={r.liquidite.retenu} mode={mode} /> :
          <p className={`text-sm ${P.doux}`}>Not published yet: it needs about three months of clean market data to be
            reliable. It will appear here automatically.</p>}>
        <Chaines chaine={r.liquidite?.chaine} mode={mode} />
      </Bloc>

      <Bloc titre="The building" id="immeuble" mode={mode} ouvert={pdf}>
        <dl className="grid grid-cols-2 gap-y-2 text-sm">
          <dt className={P.doux}>Completed</dt><dd>{r.immeuble?.annee ?? "unknown"}</dd>
          <dt className={P.doux}>Common fee</dt>
          <dd>{r.immeuble?.charges_thb_m2 ? `THB ${Math.round(r.immeuble.charges_thb_m2)}/m²/month` : "unknown"}</dd>
          <dt className={P.doux}>Units for sale now</dt><dd>{r.immeuble?.lots_en_vente ?? "—"} (distinct units)</dd>
          <dt className={P.doux}>Quota of this unit</dt><dd>{a.quota ?? "not stated"}</dd>
        </dl>
      </Bloc>

      <Bloc titre={`Red flags (${r.drapeaux?.length ?? 0})`} id="drapeaux" mode={mode} ouvert>
        {r.drapeaux?.length ? (
          <ul className="space-y-2 text-sm">
            {r.drapeaux.map((d, i) => (
              <li key={i} className="flex gap-2">
                <span className={d.niveau === "high" ? "text-neg" : d.niveau === "medium" ? "text-warn" : P.doux}
                  aria-hidden="true">●</span>
                <span>{d.texte}</span>
              </li>
            ))}
          </ul>
        ) : <p className={`text-sm ${P.doux}`}>None found.</p>}
      </Bloc>
    </>
  );

  if (pdf)
    return (
      <div className={`${P.page} mx-auto max-w-[190mm] space-y-4 p-6 text-[13px]`}>
        <div className="flex items-start justify-between gap-6 border-b border-rule pb-4">
          {identite}
          <span className="font-logo text-3xl text-gold-ink">lowi</span>
        </div>
        <p className="text-base font-medium">{verdict(r)}</p>
        {chiffres}
        <div className="space-y-4">{blocs}</div>
        <Bloc titre="Method and limits" id="limites" mode={mode} ouvert>
          <p className={`text-sm ${P.doux}`}>Report generated on {date(r.genere_le)} · reference {r.id} · sources used for
            market scores: {calc?.sources_gardees?.join(", ") ?? "—"}.</p>
        </Bloc>
        {mentions}
      </div>
    );

  return (
    <div className="h-full overflow-y-auto overflow-x-hidden">
      <div className={`${P.page} mx-auto max-w-[1880px] px-4 pb-28 pt-6 lg:grid lg:grid-cols-12 lg:gap-6 lg:px-8 lg:pb-10`}>
        <aside className="min-w-0 space-y-5 lg:sticky lg:top-6 lg:col-span-4 lg:self-start">
          {identite}
          <p className="text-base font-medium leading-snug">{verdict(r)}</p>
          {chiffres}
          <div className="hidden lg:block">{boutonPdf}</div>
          <div className="hidden lg:block">{mentions}</div>
        </aside>
        <div className="mt-6 grid min-w-0 gap-4 lg:col-span-8 lg:mt-0 xl:grid-cols-2">{blocs}</div>
        <div className="mt-6 lg:hidden">{mentions}</div>
      </div>
      <div className="fixed inset-x-0 bottom-0 z-20 border-t border-rule bg-page/95 p-3 backdrop-blur lg:hidden">
        {boutonPdf}
      </div>
    </div>
  );
}
