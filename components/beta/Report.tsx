"use client";
/**
 * Report — le bilan d'une annonce, en trois rendus à partir des mêmes données :
 *   · mobile (< 1024 px) : une colonne, blocs repliables, barres des signaux au
 *     dépliage seulement, bouton PDF collé en bas ;
 *   · PC (≥ 1024 px, pensé pour 1920 × 1080) : colonne gauche collante
 *     (identité, verdict, chiffres clés, bouton PDF), blocs en deux colonnes ;
 *   · PDF (mode="pdf") : fond clair, tout déplié, explications imprimées.
 * Règles : docs/bilan-acheteur/regles-construction-ui.md.
 */
import { useState } from "react";
import type { Chaine, Comparaison, Niveau, Rapport } from "@/lib/beta/types";
import { EXPLICATIONS } from "./explications";

type Mode = "web" | "pdf";
const thb = (v: number) => "THB " + (v >= 1e6 ? (v / 1e6).toFixed(2) + "M" : Math.round(v).toLocaleString("en-US"));
const k = (v: number) => Math.round(v / 1000).toLocaleString("en-US") + "k";
const pct = (v: number) => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(Math.round(v * 100)) + "%";
const date = (s: string) =>
  new Date(s + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

/** Palette par rendu : sombre à l'écran (thème du site), claire sur papier. */
function palette(mode: Mode) {
  return mode === "pdf"
    ? { page: "bg-white text-[#16131f]", carte: "bg-white border border-[#ddd8ea]", doux: "text-[#5b5470]",
        faible: "text-[#8a849c]", piste: "#ece9f3", point: "#9a93ad", accent: "#6d28d9", fond2: "bg-[#f6f4fb]" }
    : { page: "text-text", carte: "bg-surface border border-violet-soft", doux: "text-text-muted",
        faible: "text-text-faint", piste: "#272040", point: "#6b6485", accent: "#b026ff", fond2: "bg-anthracite" };
}

function couleurLibelle(l: string) {
  if (l.includes("buyer") || l.includes("hard")) return "bg-[#fbbf24]/15 text-[#fbbf24]";
  if (l.includes("seller") || l.includes("easy")) return "bg-[#34d399]/15 text-[#34d399]";
  if (l.includes("not enough") || l.includes("no reference")) return "bg-[#6b6485]/20 text-[#9b94b3]";
  return "bg-[#3b82f6]/15 text-[#93c5fd]";
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
        <span className="font-serif text-5xl tabular-nums">{n.score}</span>
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
      <rect x="4" y="12" width="108" height="6" rx="3" fill="#fbbf24" opacity="0.25" />
      <rect x="113" y="12" width="94" height="6" fill={P.piste} />
      <rect x="208" y="12" width="108" height="6" rx="3" fill="#34d399" opacity="0.25" />
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
      {Object.entries(chaine).map(([nom, v]) => (
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
      ))}
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
      <circle cx={x(prix)} cy="24" r="7" fill={P.accent} stroke="#fff" strokeWidth="2" />
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

export default function Report({ r, mode = "web" }: { r: Rapport; mode?: Mode }) {
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
      <p className={`text-xs uppercase tracking-[0.14em] ${P.faible}`}>Buyer report · beta</p>
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

  const boutonPdf = !pdf && (
    <a href={`/beta/r/${r.id}/pdf`} target="_blank" rel="noopener"
      className="flex h-14 w-full items-center justify-center gap-2 rounded-xl bg-gold text-base font-bold text-[#16131f] shadow-[0_0_24px_rgba(201,168,76,0.45)] transition hover:brightness-110 active:scale-[0.98]">
      <span aria-hidden="true">⬇</span> Get the full PDF report
    </a>
  );

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
                  ? "border-violet-fluo bg-violet-fluo/15 text-text" : "border-violet-soft " + P.doux}
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
                <span className={d.niveau === "high" ? "text-[#f87171]" : d.niveau === "medium" ? "text-[#fbbf24]" : P.doux}
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
        <div className="flex items-start justify-between gap-6 border-b border-[#ddd8ea] pb-4">
          {identite}
          <span className="font-logo text-3xl text-[#a8871f]">lowi</span>
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
      <div className="fixed inset-x-0 bottom-0 z-20 border-t border-violet-soft bg-anthracite-deep/95 p-3 backdrop-blur lg:hidden">
        {boutonPdf}
      </div>
    </div>
  );
}
