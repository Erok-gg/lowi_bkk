"use client";
/**
 * Report — le bilan d'une annonce, en trois rendus à partir des mêmes données :
 *   · mobile (< 1024 px) : une colonne, blocs repliables, UNE barre par bloc de
 *     comparaison (pastilles pour changer de niveau), bouton PDF sous le titre ;
 *   · PC (≥ 1024 px, pensé pour 1920 × 1080) : en-tête pleine largeur, puis blocs
 *     en colonnes CSS (2 à partir de 1280 px) — la hauteur suit le contenu, il n'y
 *     a plus de ligne de grille qui laisse un trou sous le bloc le plus court ;
 *   · PDF (mode="pdf") : une colonne, tout déplié, explications imprimées, sans le
 *     dépliant « mois de stock ».
 * Refonte du 2026-10-22. Règles : bilan_RE/docs/regles-construction-ui.md.
 */
import { useState } from "react";
import type { Bande, Chaine, Comparaison, FraisAchat, LoyerEstime, MoisDeStock, Niveau, Profil, Rapport, Renovation,
  SortiesPrix } from "@/bilan_RE/web/lib/types";
import { EXPLICATIONS } from "./explications";
import Annexe from "./Annexe";
import PdfGate from "./PdfGate";
import type { Langue } from "@/bilan_RE/web/i18n";
import { palettes } from "@/config/theme";

type Mode = "web" | "pdf";
const thb = (v: number) => "THB " + (v >= 1e6 ? (v / 1e6).toFixed(2) + "M" : Math.round(v).toLocaleString("en-US"));
const k = (v: number) => Math.round(v / 1000).toLocaleString("en-US") + "k";
const pct = (v: number) => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(Math.round(v * 100)) + "%";
const date = (s: string) =>
  new Date(s + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
const court = (nom: string) => nom.replace(", Bangkok", "").replace(" District", "");

/** Rouge foncé des prix demandés (demande du 2026-10-22) : lisible sur blanc, 8,6:1. */
const ROUGE = "text-[#8e1b1b]";

/**
 * Palette par rendu. Les couleurs de classe passent par les jetons et suivent le
 * thème ; les couleurs SVG sont lues dans `palettes.ledger` (`var()` n'est pas
 * interprété dans un attribut de présentation SVG).
 */
function palette(mode: Mode) {
  const L = palettes.ledger;
  const svg = { piste: L.sunken, point: L.faint, accent: L.brand };
  // En PDF, NI la page NI les cartes ne portent de fond : un aplat blanc masquait
  // le filigrane (constaté le 2026-10-20). Les cartes gardent leur filet or.
  return mode === "pdf"
    ? { page: "text-ink", carte: "border border-rule", doux: "text-muted",
        faible: "text-faint", fond2: "bg-sunken", ...svg }
    : { page: "text-ink", carte: "bg-surface border border-rule", doux: "text-muted",
        faible: "text-faint", fond2: "bg-sunken", ...svg };
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
    <section className={`${P.carte} mb-4 block w-full break-inside-avoid rounded-2xl p-5`}>
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

/** Loyer que le futur propriétaire peut demander (profil investisseur). */
function LoyerBloc({ l, mode }: { l: LoyerEstime; mode: Mode }) {
  const P = palette(mode);
  if (l.statut !== "ok")
    return <p className={`text-sm ${P.doux}`}>Not enough comparable rentals around this unit to estimate a rent.</p>;
  return (
    <>
      <p className="text-2xl font-semibold tabular-nums">
        {thb(l.loyer)} <span className={`text-sm font-normal ${P.doux}`}>/ month</span>
      </p>
      <p className={`mt-1 text-sm ${P.doux}`}>
        Likely range {thb(l.fourchette[0])} – {thb(l.fourchette[1])} · {Math.round(l.loyer_m2).toLocaleString("en-US")} THB/m²
        {l.rendement_brut !== null && <> · gross yield <span className="font-semibold text-ink">{(l.rendement_brut * 100).toFixed(1)}%</span></>}
      </p>
      <p className={`mt-1 text-xs ${P.faible}`}>
        Based on {l.n} rentals: {l.libelle.toLowerCase()}
        {l.confiance === "low" ? " (low confidence: no rentals of this type in the building)" : ""}.
      </p>
      {l.par_etage.some((e) => e.loyer !== null) && (
        <table className="mt-3 w-full text-sm">
          <thead><tr className={P.doux}><th className="text-left font-normal">Floor</th>
            <th className="text-right font-normal">Rent for this size</th><th className="text-right font-normal">Rentals</th></tr></thead>
          <tbody>
            {l.par_etage.map((e) => (
              <tr key={e.tranche}>
                <td>{e.tranche}</td>
                <td className="text-right tabular-nums">{e.loyer !== null ? thb(e.loyer) : "—"}</td>
                <td className={`text-right ${P.faible}`}>{e.n}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className={`mt-2 text-[11px] ${P.faible}`}>{l.note}</p>
    </>
  );
}

/** Rénovation : part des annonces comparables « rénovées » et effet sur le loyer.
 *  EN ATTENTE (2026-10-22, décision utilisateur) : le bloc affiche « Coming soon ».
 *  Mesure qui l'a motivé : avec 2 rénovées contre 3 autres par immeuble, le verdict
 *  « augmente le loyer » sort presque aussi souvent au hasard (24 % contre 31 % à
 *  +10 %). La règle reste à choisir ; le calcul tourne toujours côté moteur.
 *  Exporté pour rester compilé tant qu'il n'est pas rebranché. */
export function RenovationBloc({ v, mode }: { v: Renovation; mode: Mode }) {
  const P = palette(mode);
  return (
    <>
      <p className="text-sm">
        <span className="text-xl font-semibold tabular-nums">{v.n_renovees}</span> of {v.n} comparable rentals
        ({Math.round(v.part * 100)}%) say the unit was renovated · {v.libelle.toLowerCase()}.
      </p>
      <p className="mt-2 text-sm font-medium">
        {v.prime !== null ? <>{v.verdict[0].toUpperCase() + v.verdict.slice(1)}: {pct(v.prime)} rent per m²
          {v.niveau === "radius" ? ` (median over ${v.n_immeubles} buildings)` : ""}.</> :
          <span className={P.doux}>Too few renovated units to measure the effect on rent here.</span>}
      </p>
    </>
  );
}

/** Frais d'achat — tous profils. Les lignes « étranger » ne sortent que pour un étranger (ou sans profil). */
function FraisBloc({ f, profil, mode }: { f: FraisAchat; profil?: Profil; mode: Mode }) {
  const P = palette(mode);
  const lignes = f.lignes.filter((l) => !(l.etrangers_seulement && profil?.nat === "thai"));
  const montant = (l: FraisAchat["lignes"][number]) =>
    l.montant !== null ? thb(l.montant)
      : l.montant_min ? `${thb(l.montant_min)} – ${thb(l.montant_max ?? l.montant_min)}` : "varies";
  return (
    <>
      <p className="text-sm">
        Usually paid by the buyer: <span className="text-xl font-semibold tabular-nums">{thb(f.total_acheteur)}</span>{" "}
        <span className={P.doux}>({(f.total_acheteur_pct * 100).toFixed(1)}% of the asking price), at most.</span>
      </p>
      <table className="mt-3 w-full text-sm">
        <thead><tr className={P.doux}><th className="text-left font-normal">Item</th>
          <th className="text-right font-normal">Amount</th><th className="text-right font-normal">Usually paid by</th></tr></thead>
        <tbody>
          {lignes.map((l) => (
            <tr key={l.poste} className="align-top">
              <td className="py-1 pr-2">{l.poste}{l.taux !== null ? ` · ${(l.taux * 100).toFixed(1)}%` : ""}
                {l.note && <span className={`block text-[11px] ${P.faible}`}>{l.note}</span>}</td>
              <td className="py-1 text-right tabular-nums">{montant(l)}</td>
              <td className="py-1 text-right">{l.payeur}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className={`mt-2 text-[11px] ${P.faible}`}>{f.avertissement}</p>
    </>
  );
}

/** Pastilles de choix du niveau — mobile seulement (une barre à la fois). */
function Pastilles({ noms, choix, set, mode, off = [] }: {
  noms: string[]; choix: string; set: (n: string) => void; mode: Mode; off?: string[];
}) {
  const P = palette(mode);
  return (
    <div className="mb-3 flex flex-wrap gap-1.5 lg:hidden">
      {noms.map((n) => (
        <button key={n} type="button" onClick={() => set(n)} disabled={off.includes(n)}
          className={`rounded-full border px-3 py-1 text-xs ${n === choix ? "border-brand bg-brand/15 text-ink" : "border-rule " + P.doux}
            ${off.includes(n) ? "opacity-40" : ""}`}>
          {n}
        </button>
      ))}
    </div>
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
      </div>
      <Echelle n={n} mode={mode} />
      <p className={`mt-1 text-xs ${P.faible}`}>
        Likely range {n.p10}–{n.p90}{n.niveau ? ` · ${court(n.niveau)}` : ""} · based on{" "}
        {n.n_cohortes.toLocaleString("en-US")} groups of comparable units, {n.n_sorties.toLocaleString("en-US")} of
        which left the market
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

function Ligne({ nom, brut, mode }: { nom: string; brut: Niveau; mode: Mode }) {
  const P = palette(mode);
  // fourchette trop large = pas de chiffre affiché, même si le calcul en a un
  const v = brut.libelle === "not enough data" ? { ...brut, score: null } : brut;
  return (
    <div className="grid grid-cols-[minmax(0,9rem)_1fr_2.5rem] items-center gap-2 text-xs">
      <span className="truncate">{court(nom)}</span>
      <div className="h-2 rounded" style={{ background: P.piste }}>
        {v.score !== null && <div className="h-2 rounded" style={{ width: `${v.score}%`, background: P.accent }} />}
      </div>
      <span className={`text-right tabular-nums ${v.score === null ? P.faible : ""}`}>{v.score ?? "—"}</span>
      <span className={`col-span-3 -mt-1 ${P.faible}`}>
        {v.score === null ? "not enough data · " : ""}{v.n_cohortes.toLocaleString("en-US")} groups of comparable units
      </span>
    </div>
  );
}

/** Tous les niveaux sur PC et en PDF ; un seul, choisi par pastille, sur mobile. */
function Chaines({ chaine, mode }: { chaine: Chaine | null | undefined; mode: Mode }) {
  const P = palette(mode);
  const noms = chaine ? Object.keys(chaine) : [];
  const [sel, setSel] = useState(() => [...noms].reverse().find((n) => chaine![n].score !== null) ?? noms[noms.length - 1]);
  if (!chaine) return null;
  const tous = (
    <div className="space-y-2">
      {noms.map((n) => <Ligne key={n} nom={n} brut={chaine[n]} mode={mode} />)}
    </div>
  );
  return (
    <div className="mt-4">
      <p className={`mb-2 text-xs ${P.doux}`}>Compared at every level</p>
      {mode === "pdf" ? tous : (
        <>
          <Pastilles noms={noms.map(court)} choix={court(sel)} set={(n) => setSel(noms.find((x) => court(x) === n)!)} mode={mode} />
          <div className="lg:hidden"><Ligne nom={sel} brut={chaine[sel]} mode={mode} /></div>
          <div className="hidden lg:block">{tous}</div>
        </>
      )}
    </div>
  );
}

/**
 * Bande d'échantillon : un carré translucide (30 %) par unité — les chevauchements
 * foncent, donc la densité se lit —, la médiane en tirets AU-DESSUS de
 * l'échantillon mais SOUS le losange du bien analysé, les extrêmes à gauche et à
 * droite de la barre (demande du 2026-10-22).
 */
function Strip({ points, mediane, valeur, fmt, aria, mode }: {
  points: number[]; mediane?: number | null; valeur: number | null; fmt: (v: number) => string;
  aria: string; mode: Mode;
}) {
  const P = palette(mode);
  const tous = valeur === null ? points : [...points, valeur];
  const lo = Math.min(...tous), hi = Math.max(...tous);
  const X0 = 46, X1 = 274;
  const x = (v: number) => X0 + ((v - lo) / Math.max(1e-9, hi - lo)) * (X1 - X0);
  const cy = 40;
  return (
    <svg viewBox="0 0 320 62" className="w-full" role="img" aria-label={aria}>
      <line x1={X0} y1={cy} x2={X1} y2={cy} stroke={P.piste} strokeWidth="2" />
      {points.map((v, i) => (
        <rect key={i} x={x(v) - 3} y={cy - 3 + ((i % 3) - 1) * 6} width="6" height="6" fill={P.accent} opacity="0.3" />
      ))}
      {mediane != null && (
        <>
          <line x1={x(mediane)} y1="12" x2={x(mediane)} y2="30" stroke={P.point} strokeWidth="1.2" strokeDasharray="3 3" />
          <text x={x(mediane)} y="9" fontSize="9" fill={P.point} textAnchor="middle">median</text>
        </>
      )}
      <text x={X0 - 6} y={cy + 3} fontSize="9" fill={P.point} textAnchor="end">{fmt(lo)}</text>
      <text x={X1 + 6} y={cy + 3} fontSize="9" fill={P.point}>{fmt(hi)}</text>
      {valeur !== null && (
        <rect x={x(valeur) - 6} y={cy - 6} width="12" height="12" transform={`rotate(45 ${x(valeur)} ${cy})`}
          fill="#ffffff" stroke={P.accent} strokeWidth="2" />
      )}
    </svg>
  );
}

function NiveauPrix({ c, prix, mode }: { c: Comparaison; prix: number; mode: Mode }) {
  const P = palette(mode);
  return (
    <div className="mb-4">
      <p className="mb-1 text-sm font-semibold">{c.niveau} <span className={`font-normal ${P.faible}`}>· n = {c.n}</span></p>
      {c.mediane && c.points && c.points.length >= 5 ? (
        <>
          <Strip points={c.points} mediane={c.mediane} valeur={prix} fmt={(v) => k(v)}
            aria={`${c.n} comparable units from ${k(c.points[0])} to ${k(c.points[c.points.length - 1])} THB per m², this listing at ${k(prix)}`}
            mode={mode} />
          <p className={`text-xs ${P.doux}`}>
            Median {k(c.mediane)}/m² · middle half {k(c.p25!)}–{k(c.p75!)} · this listing {k(prix)} ({pct(c.ecart!)})
            {c.exclus ? ` · ${c.exclus} extreme value${c.exclus > 1 ? "s" : ""} left out` : ""}
          </p>
        </>
      ) : (
        <p className={`text-xs ${P.faible}`}>Not enough comparable units ({c.n}).</p>
      )}
    </div>
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
  if (t) morceaux.push(`in a ${t.libelle.replace(" market", "")} market (${court(t.niveau)})`);
  const s = morceaux.join(", ");
  return s.charAt(0).toUpperCase() + s.slice(1) + ".";
}

/** Sorties d'annonces au même prix : « parties », jamais « vendues » (on ne sait pas). */
function Sorties({ s, mode }: { s: SortiesPrix | null | undefined; mode: Mode }) {
  const P = palette(mode);
  if (!s) return null;
  return (
    <div className={`mt-4 rounded-lg ${P.fond2} p-3 text-xs leading-relaxed ${P.doux}`}>
      <p className="mb-1 font-semibold">Units at a similar price per m² (±{Math.round(s.tolerance * 100)}%), within {s.rayon_km} km</p>
      {s.n_parties > 0 ? (
        <p>
          In the last {s.jours} days, <strong>{s.n_parties}</strong> such listings left the market and{" "}
          <strong>{s.n_actives}</strong> are still online. Median time online before leaving:{" "}
          <strong>{s.mediane_jours} days</strong>; {Math.round((s.part_30j ?? 0) * 100)}% left within 30 days.
        </p>
      ) : (
        <p>No comparable listing left the market in the last {s.jours} days; {s.n_actives} are online.</p>
      )}
      <p className={`mt-1 ${P.faible}`}>
        “Left” means sold or withdrawn: no source says which. Time online counts from the day we first saw the listing.
      </p>
    </div>
  );
}

/**
 * MoisDeStock — le dépliant pédagogique (2026-10-19) et, depuis le 2026-10-22, un
 * petit graphique : mois de stock de Bangkok et de l'immeuble, avec un intervalle
 * d'imprécision, et le repère officiel REIC. Absent du PDF (demande du 2026-10-22).
 * Les trois bandes (< 3 / 4–6 / > 6 mois) sont un repère de LECTURE du métier, pas
 * notre mesure (règle 1) : nos mois de stock se calculent sur des retraits
 * d'annonces, pas sur des ventes notariées.
 */
function MoisDeStockBloc({ m, mode }: { m: MoisDeStock | undefined; mode: Mode }) {
  const P = palette(mode);
  const BANDES = [
    { t: "High tension", m: "under 3 months", d: "Very little on offer. Buyers move fast, and several can end up on the same unit." },
    { t: "Balanced", m: "4 to 6 months", d: "A healthy market. There is room to negotiate, without having to rush." },
    { t: "Low tension", m: "over 6 months", d: "More on offer than buyers. Sellers wait, and the leverage is on your side." },
  ];
  return (
    <details className={`mt-4 rounded-lg ${P.fond2} p-3`}>
      <summary className={`cursor-pointer text-xs font-semibold ${P.doux}`}>
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
      {m && <GrapheStock m={m} mode={mode} />}
    </details>
  );
}

function GrapheStock({ m, mode }: { m: MoisDeStock; mode: Mode }) {
  const P = palette(mode);
  const pts = m.points;
  const W = 320, H = 130, X0 = 30, X1 = 312, Y0 = 12, Y1 = 104;
  const plafond = Math.max(45, ...pts.flatMap((p) => [p.bangkok?.haut ?? 0, p.immeuble?.haut ?? 0]), m.immeuble_periode?.haut ?? 0);
  const y = (v: number) => Y1 - (Math.min(v, plafond) / plafond) * (Y1 - Y0);
  const x = (i: number) => X0 + (pts.length < 2 ? 0.5 : i / (pts.length - 1)) * (X1 - X0);
  const bang = pts.flatMap((p, i) => (p.bangkok ? [{ i, ...p.bangkok }] : []));
  const ligne = bang.map((p) => `${x(p.i)},${y(p.mois)}`).join(" ");
  const bande = bang.length
    ? bang.map((p) => `${x(p.i)},${y(p.haut)}`).join(" ") + " " + [...bang].reverse().map((p) => `${x(p.i)},${y(p.bas)}`).join(" ")
    : "";
  const off = m.officiel, imm = m.immeuble_periode;
  const dernier = bang[bang.length - 1];
  return (
    <div className="mt-3">
      <p className={`mb-1 text-xs font-semibold ${P.doux}`}>Months of supply, Bangkok vs this building</p>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
        aria-label={`Months of supply: Bangkok about ${dernier ? Math.round(dernier.mois) : "n/a"} months on our data, official reference ${off.mois} months`}>
        {[0, 15, 30, 45].filter((v) => v <= plafond).map((v) => (
          <g key={v}>
            <line x1={X0} y1={y(v)} x2={X1} y2={y(v)} stroke={P.piste} strokeWidth="1" />
            <text x={X0 - 4} y={y(v) + 3} fontSize="8" fill={P.point} textAnchor="end">{v}</text>
          </g>
        ))}
        {bande && <polygon points={bande} fill={P.accent} opacity="0.2" />}
        {ligne && <polyline points={ligne} fill="none" stroke={P.accent} strokeWidth="2" />}
        {imm && (
          <>
            <rect x={X0} y={y(imm.haut)} width={X1 - X0} height={Math.max(1, y(imm.bas) - y(imm.haut))} fill={palettes.ledger.warn} opacity="0.2" />
            <line x1={X0} y1={y(imm.mois)} x2={X1} y2={y(imm.mois)} stroke={palettes.ledger.warn} strokeWidth="2" strokeDasharray="5 3" />
          </>
        )}
        <line x1={X0} y1={y(off.mois)} x2={X1} y2={y(off.mois)} stroke={P.point} strokeWidth="1.2" strokeDasharray="1 3" />
        <text x={X1} y={y(off.mois) - 3} fontSize="8" fill={P.point} textAnchor="end">REIC {off.periode} · {off.mois}</text>
        {pts.length > 0 && <text x={X0} y={H - 4} fontSize="8" fill={P.point}>{date(pts[0].fin)}</text>}
        {pts.length > 1 && <text x={X1} y={H - 4} fontSize="8" fill={P.point} textAnchor="end">{date(pts[pts.length - 1].fin)}</text>}
      </svg>
      <ul className={`mt-1 space-y-0.5 text-[11px] leading-relaxed ${P.doux}`}>
        <li><span className="font-semibold" style={{ color: P.accent }}>━</span> Bangkok, our data
          {dernier ? ` — about ${Math.round(dernier.mois)} months (range ${Math.round(dernier.bas)}–${Math.round(dernier.haut)})` : ""}</li>
        <li><span className="font-semibold" style={{ color: palettes.ledger.warn }}>╍</span> This building
          {imm ? ` — about ${Math.round(imm.mois)} months (range ${Math.round(imm.bas)}–${Math.round(imm.haut)}, ${imm.retraits} exits)`
            : " — too few exits to give a figure"}</li>
        <li><span className="font-semibold">┈</span> Official: {off.source}, {off.perimetre}, {off.mois} months</li>
      </ul>
      <p className={`mt-2 text-[11px] leading-relaxed ${P.faible}`}>
        Our figure counts listings leaving the market, not recorded sales, and only covers the weeks since 14 September,
        when removals became reliable: there is no two-year history yet. The shaded band is an 80% range given the number of
        exits; it is wide for one building. The official figure also counts unsold new-build stock, so the two are not
        directly comparable.{" "}
        <a href={off.url} target="_blank" rel="noopener noreferrer" className="underline">Source</a>.
      </p>
    </div>
  );
}

/** Bande de charges : un bâtiment face à des bâtiments comparables. */
function GraphiqueCharges({ titre, b, propre, mode }: { titre: string; b: Bande | null; propre: number | null; mode: Mode }) {
  const P = palette(mode);
  return (
    <div className="mt-3">
      <p className="mb-1 text-xs font-semibold">{titre}</p>
      {b ? (
        <>
          <Strip points={b.points} mediane={b.mediane} valeur={propre} fmt={(v) => String(Math.round(v))} mode={mode}
            aria={`Common fee of ${b.n} comparable buildings, median ${Math.round(b.mediane)} THB per m² per month`} />
          <p className={`text-xs ${P.doux}`}>
            THB/m²/month · {b.n} buildings · median {Math.round(b.mediane)} · middle half {Math.round(b.p25)}–{Math.round(b.p75)}
            {propre !== null ? ` · this building ${Math.round(propre)}` : " · this building: fee unknown"}
          </p>
        </>
      ) : (
        <p className={`text-xs ${P.faible}`}>Not enough comparable buildings with a known fee (10 needed).</p>
      )}
    </div>
  );
}

function Favicon({ cle }: { cle?: string }) {
  const f: Record<string, string> = {
    ddproperty: "ddproperty.com", fazwaz: "fazwaz.com", propertyscout: "propertyscout.co.th", nestopa: "nestopa.com",
    livinginsider: "livinginsider.com", propertyhub: "propertyhub.in.th", hipflat: "hipflat.com",
  };
  if (!cle || !f[cle]) return null;
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={`/beta/favicons/${f[cle]}.png`} alt="" width={16} height={16} className="mr-1 inline-block align-[-3px]" />;
}

/**
 * `acces` : l'état du compte, résolu par la page serveur (le composant est côté
 * navigateur et ne peut pas lire les cookies). Absent → bouton PDF ouvert comme
 * avant, ce qui garde la version imprimable et les tests inchangés.
 */
export default function Report({
  r,
  mode = "web",
  acces,
  profil,
}: {
  r: Rapport;
  mode?: Mode;
  acces?: { langue: Langue; connecte: boolean; possede: boolean };
  /** Menus de la page d'accueil. Absent = profil inconnu : pas de blocs investisseur. */
  profil?: Profil;
}) {
  const P = palette(mode);
  const pdf = mode === "pdf";
  const a = r.annonce!, h = r.histoire!;
  const meilleure = r.prix?.find((x) => x.cle === "building_same" && x.mediane) ??
    r.prix?.find((x) => x.cle === "radius_same" && x.mediane) ?? r.prix?.find((x) => x.mediane);
  const [niveauPrix, setNiveauPrix] = useState(meilleure?.cle ?? "building");
  const choisie = r.prix?.find((x) => x.cle === niveauPrix) ?? meilleure;
  const calc = r.scores_calcul;
  const imm = r.immeuble;
  const age = imm?.annee ? new Date().getFullYear() - imm.annee : null;
  const lotsRecenses = Math.max(imm?.lots_recenses ?? 0, imm?.lots_en_vente ?? 0);

  const boutonPdf =
    !pdf &&
    (acces ? (
      <PdfGate rapportId={r.id} langue={acces.langue} connecte={acces.connecte} possede={acces.possede} />
    ) : (
      <a href={`/beta/r/${r.id}/pdf`} target="_blank" rel="noopener"
        className="flex h-14 w-full items-center justify-center gap-2 rounded-xl bg-gold text-base font-bold text-on-gold shadow-gold-glow transition hover:brightness-110 active:scale-[0.98]">
        <span aria-hidden="true">⬇</span> Save the report as PDF
      </a>
    ));

  const entete = (
    <header className={pdf ? "border-b border-rule pb-4" : "mb-6"}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <h1 className="min-w-0 text-2xl font-semibold leading-tight 2xl:text-3xl">
          Analysis report: {court(a.condo)}
        </h1>
        {pdf ? <span className="font-logo text-3xl text-gold-ink">lowi</span> : <div className="w-full sm:w-72">{boutonPdf}</div>}
      </div>
      {imm?.adresse && <p className={`mt-2 text-sm ${P.doux}`}>{imm.adresse}</p>}
      <p className={`mt-3 text-2xl font-semibold tabular-nums ${ROUGE}`}>
        <span className="mr-2 text-sm font-normal">Asking price</span>{thb(a.prix)}
      </p>
      <p className={`mt-1 text-sm ${P.doux}`}>
        {a.chambres ?? "?"} bed · {a.sdb ?? "?"} bath · {a.surface} m²{a.etage ? ` · floor ${a.etage}` : ""} ·{" "}
        {court(a.khet)}
      </p>
      <p className={`mt-1 text-xs ${P.faible}`}>
        Requested {r.demande_le ?? r.genere_le}. Market scores use a {calc?.frequence_calcul === "mensuelle" ? "monthly" : "28-day"}{" "}
        window, refreshed {calc?.frequence_calcul === "quotidienne" ? "daily" : "regularly"}; exits are compared over the last 90 days.
      </p>
      <p className="mt-3 max-w-3xl text-base font-medium leading-snug">{verdict(r)}</p>
    </header>
  );

  const mentions = (
    <p className={`text-xs ${P.faible}`}>
      Asking prices, not sold prices. Listing data as of {r.donnees_du ? date(r.donnees_du) : "—"}. Market scores:{" "}
      {calc?.frequence_calcul === "quotidienne" ? "daily calculation" :
        calc?.frequence_calcul === "mensuelle" ? "monthly calculation" : "calculation"}
      {calc?.fin_fenetre ? `, window ending ${date(calc.fin_fenetre)}` : " — not computed yet"}. Lowi takes nothing from
      the seller. Not investment advice.
    </p>
  );

  /**
   * L'annexe ne passe PAS par `Bloc` : celui-ci colle à chaque section un encart
   * « How is this computed? » tiré d'`EXPLICATIONS[id]`, qui ferait doublon avec
   * l'annexe elle-même. Même carte, même titre, sans l'encart.
   */
  const annexe = (
    <section className={`${P.carte} mb-4 block w-full break-inside-avoid rounded-2xl p-5`}>
      <h2 className="text-base font-semibold">Methodology &amp; limitations</h2>
      <div className="mt-3">
        <Annexe r={r} doux={P.doux} faible={P.faible} />
      </div>
    </section>
  );

  const chiffres = (
    <div className="mb-4 grid grid-cols-3 gap-3">
      {[
        { l: "Listed for", v: `${h.jours_en_ligne} days` },
        { l: "Price since first seen", v: h.variation === null ? "—" : pct(h.variation) },
        { l: "For sale in building", v: `${imm?.lots_en_vente ?? "—"} / ${lotsRecenses || "—"}` },
      ].map((x) => (
        <div key={x.l}>
          <p className={`text-[11px] ${P.doux}`}>{x.l}</p>
          <p className="text-xl font-semibold tabular-nums">{x.v}</p>
        </div>
      ))}
    </div>
  );

  const blocs = (
    <>
      <Bloc titre="Price vs comparable units" id="prix" mode={mode} ouvert
        resume={
          <p className={`text-sm ${P.doux}`}>
            Price per m²: <span className={`font-semibold ${ROUGE}`}>{k(a.prix_m2)} THB</span>
            {choisie?.ecart !== undefined && (
              <> · {pct(choisie.ecart)} vs {choisie.niveau.toLowerCase()} · cheaper than {100 - (choisie.rang_pct ?? 0)}% of them</>
            )}
          </p>
        }>
        {!pdf && (
          <Pastilles
            noms={(r.prix ?? []).map((c) => c.niveau.replace("The building, ", "Building · "))}
            choix={(choisie?.niveau ?? "").replace("The building, ", "Building · ")}
            set={(n) => setNiveauPrix(r.prix?.find((c) => c.niveau.replace("The building, ", "Building · ") === n)?.cle ?? niveauPrix)}
            off={(r.prix ?? []).filter((c) => !c.mediane).map((c) => c.niveau.replace("The building, ", "Building · "))}
            mode={mode} />
        )}
        {pdf ? (r.prix ?? []).map((c) => <NiveauPrix key={c.cle} c={c} prix={a.prix_m2} mode={mode} />) : (
          <>
            <div className="lg:hidden">{choisie && <NiveauPrix c={choisie} prix={a.prix_m2} mode={mode} />}</div>
            <div className="hidden lg:block">
              {(r.prix ?? []).map((c) => <NiveauPrix key={c.cle} c={c} prix={a.prix_m2} mode={mode} />)}
            </div>
          </>
        )}
      </Bloc>

      {profil?.but === "invest" && r.loyer_estime && (
        <Bloc titre="Rent you can ask" id="loyer" mode={mode} ouvert
>
          <LoyerBloc l={r.loyer_estime} mode={mode} />
        </Bloc>
      )}
      {profil?.but === "invest" && r.renovation && (
        <Bloc titre="Renovation" id="renovation" mode={mode} ouvert={pdf}>
          <p className={`text-sm ${P.doux}`}>
            Coming soon: how many similar units are advertised as renovated, and whether renovation lets you ask a
            noticeably higher rent.
          </p>
        </Bloc>
      )}

      <Bloc titre="The listing's history" id="histoire" mode={mode} ouvert={pdf}
        resume={<p className={`text-sm ${P.doux}`}>First seen on {date(h.premier_vu)}</p>}>
        {chiffres}
        <ol className="space-y-1.5 border-l-2 pl-4 text-sm" style={{ borderColor: P.piste }}>
          {h.evenements.slice(-12).map((e, i) => (
            <li key={i} className={e.type === "price_cut" ? "" : P.doux}>
              <span className="tabular-nums">{date(e.date)}</span> ·{" "}
              {e.source && (
                <span className="whitespace-nowrap">
                  <Favicon cle={e.cle} />
                  {e.url ? (
                    <a href={e.url} target="_blank" rel="noopener noreferrer nofollow" className="underline">{e.source}</a>
                  ) : e.source}
                  {" · "}
                </span>
              )}
              {e.type === "listed" ? "listed" :
                `${e.type === "price_cut" ? "price cut" : "price rise"} ${thb(e.from!)} → ${thb(e.to!)}`}
            </li>
          ))}
        </ol>
        {h.evenements.length > 12 && (
          <p className={`mt-2 text-xs ${P.faible}`}>{h.evenements.length - 12} earlier events not shown.</p>
        )}
      </Bloc>

      {r.ventes_portail && (
        <Bloc titre="Reported sales" id="ventes" mode={mode} ouvert={pdf}
          resume={<span className="inline-block rounded-full border px-2 py-0.5 text-xs font-medium text-warn"
            style={{ borderColor: "currentColor" }}>{r.ventes_portail.etiquette}</span>}>
          <p className={`mb-3 text-xs ${P.faible}`}>{r.ventes_portail.note}</p>
          {r.ventes_portail.mediane_m2 != null ? (
            <p className="mb-3 text-sm">
              Median of {r.ventes_portail.n_comparables} reported sales of similar units (last{" "}
              {r.ventes_portail.fenetre_mois} months): THB {Math.round(r.ventes_portail.mediane_m2).toLocaleString("en-US")}/m²
              {r.ventes_portail.ecart != null && (
                <> — this listing asks {Math.abs(Math.round(r.ventes_portail.ecart * 100))}%{" "}
                  {r.ventes_portail.ecart >= 0 ? "above" : "below"}</>)}
            </p>
          ) : (
            <p className={`mb-3 text-sm ${P.doux}`}>Not enough reported sales of similar units
              ({r.ventes_portail.n_comparables} in the last {r.ventes_portail.fenetre_mois} months; at least 5 needed
              for a median). {r.ventes_portail.n_immeuble} reported in this building overall.</p>
          )}
          {r.ventes_portail.ventes.length > 0 && (
            <ul className="space-y-1 text-sm">
              {r.ventes_portail.ventes.map((v, i) => (
                <li key={i} className={P.doux}>
                  <span className="tabular-nums">{v.mois}</span> · {v.surface ? `${v.surface} m²` : "size n/a"}
                  {v.etage ? ` · floor ${v.etage}` : ""} · THB {Math.round(v.prix_m2).toLocaleString("en-US")}/m²
                </li>
              ))}
            </ul>
          )}
          {r.ventes_portail.resume && (
            <p className={`mt-3 text-xs ${P.faible}`}>
              Portal's own summary ({r.ventes_portail.resume.releve_le}):
              {r.ventes_portail.resume.n != null && ` ${r.ventes_portail.resume.n} sales`}
              {r.ventes_portail.resume.jours_avant_vente != null && `, listed ${r.ventes_portail.resume.jours_avant_vente} days on average`}
              {r.ventes_portail.resume.decote_pct != null && `, sold ${Math.abs(r.ventes_portail.resume.decote_pct)}% ${r.ventes_portail.resume.decote_pct >= 0 ? "below" : "above"} the listed price`}.
            </p>
          )}
        </Bloc>
      )}

      <Bloc titre="Market tension" id="tension" mode={mode} ouvert={pdf}
        resume={<Score n={r.tension?.retenu} mode={mode} />}>
        <p className={`mt-3 text-xs leading-relaxed ${P.doux}`}>
          Compared with: {a.chambres ?? "same-size"}-bedroom condos for sale of a similar size, in each area below. A group
          of comparable units is one building, one bedroom count and one size band. 50 is a typical Bangkok district;
          lower means more leverage for the buyer.
        </p>
        <Chaines chaine={r.tension?.chaine} mode={mode} />
        <Sorties s={r.sorties_prix} mode={mode} />
        {!pdf && <MoisDeStockBloc m={r.mois_de_stock} mode={mode} />}
      </Bloc>

      <Bloc titre="Ease of resale" id="liquidite" mode={mode} ouvert={pdf}
        resume={r.liquidite?.retenu ? <Score n={r.liquidite.retenu} mode={mode} /> :
          <p className={`text-sm ${P.doux}`}>Not enough resales observed around this unit yet to give a reliable
            score. It will appear here automatically as data builds up.</p>}>
        <Chaines chaine={r.liquidite?.chaine} mode={mode} />
        <Sorties s={r.sorties_prix} mode={mode} />
      </Bloc>

      <Bloc titre="The building" id="immeuble" mode={mode} ouvert={pdf}>
        <dl className="grid grid-cols-2 gap-y-2 text-sm">
          <dt className={P.doux}>Completed</dt>
          <dd>{imm?.annee ? `${imm.annee}${age !== null ? ` (${age} years old)` : ""}` : "unknown"}</dd>
          <dt className={P.doux}>Common fee</dt>
          <dd>{imm?.charges_thb_m2 ? `THB ${Math.round(imm.charges_thb_m2)}/m²/month` : "unknown"}</dd>
          <dt className={P.doux}>For sale now</dt>
          <dd>{imm?.lots_en_vente ?? "—"} of {lotsRecenses || "—"} units recorded</dd>
          <dt className={P.doux}>Sales, last 2 years</dt>
          <dd>
            {r.ventes_portail ? `${r.ventes_portail.n_24_mois ?? 0} reported` : "none reported"}{" "}
            <span className={P.faible}>(weak source)</span>
          </dd>
          <dt className={P.doux}>Quota of this unit</dt><dd>{a.quota ?? "not stated"}</dd>
        </dl>
        {imm?.charges?.equipements?.length ? (
          <p className={`mt-3 text-sm ${P.doux}`}>
            <span className="font-semibold text-ink">Amenities</span> · {imm.charges.equipements.join(" · ")}
          </p>
        ) : null}
        {imm?.charges && (
          <>
            <GraphiqueCharges titre="Common fee vs buildings at a similar price per m² (±15%)"
              b={imm.charges.meme_prix} propre={imm.charges.propre} mode={mode} />
            <GraphiqueCharges titre="Common fee vs buildings with the same or similar amenities"
              b={imm.charges.memes_equipements} propre={imm.charges.propre} mode={mode} />
            <p className={`mt-2 text-[11px] ${P.faible}`}>
              A fee that is low for the amenities offered can mean maintenance is underfunded. The fee is known for{" "}
              {imm.charges.n_immeubles_avec_charges.toLocaleString("en-US")} buildings only.
            </p>
          </>
        )}
      </Bloc>

      {r.frais_achat && (
        <Bloc titre="Buying costs" id="frais" mode={mode} ouvert={pdf}>
          <FraisBloc f={r.frais_achat} profil={profil} mode={mode} />
        </Bloc>
      )}

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
        {entete}
        <div>{blocs}</div>
        {annexe}
        {mentions}
      </div>
    );

  return (
    <div className="h-full overflow-y-auto overflow-x-hidden">
      <div className={`${P.page} mx-auto max-w-[1880px] px-4 pb-10 pt-6 lg:px-8`}>
        {entete}
        {/* Colonnes CSS, pas une grille : la hauteur de chaque bloc suit son contenu et
            les blocs s'empilent sans trou (demande du 2026-10-22). */}
        <div className="columns-1 gap-4 xl:columns-2">
          {blocs}
          {annexe}
        </div>
        <div className="mt-2">{mentions}</div>
      </div>
    </div>
  );
}
