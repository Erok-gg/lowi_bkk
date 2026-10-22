"use client";
/**
 * AnalysisLoader — défilement des éléments calculés pendant la génération.
 * Chaque ligne correspond à un calcul réel du rapport (cf. rapport.py) : le
 * chargement explique ce qu'on obtient, il ne fait pas patienter avec du vide.
 */
import { useEffect, useState } from "react";

/** Ce que renvoie /api/beta/analyse (miroir de `Suivi` dans bilan_RE/web/lib/rapport.ts). */
export type Suivi = {
  id: string;
  etat: string;
  position: number | null;
  en_cours: number;
  en_attente: number;
  max_parallele: number;
  traites_total: number;
  traites_aujourdhui: number;
  restant_s: number | null;
};

const duree = (s: number) => (s < 1 ? "<1 s" : s < 60 ? `~${s} s` : `~${Math.round(s / 60)} min`);

const ETAPES = [
  // Les sources ne sont ni nommées ni comptées (demande utilisateur du
  // 2026-10-20) : elles l'étaient ici en clair, les cinq, sur l'écran d'attente.
  { t: "Finding the listing", d: "matched across the publicly available sources we aggregate" },
  { t: "Rebuilding the listing's history", d: "first seen, reposts, price cuts" },
  { t: "Collecting comparable units", d: "same building, same beds and size, within 1 km" },
  { t: "Pricing per m² against the building", d: "median, quartiles, rank" },
  { t: "Measuring market tension", d: "units clearing, time to sell, supply trend" },
  { t: "Checking how easily it resells", d: "time to sell at market price, by building age" },
  { t: "Counting sellers in the building", d: "distinct units for sale right now" },
  { t: "Looking for red flags", d: "quota, outlier price, conflicting building facts" },
];

export default function AnalysisLoader({ s }: { s?: Suivi }) {
  const [i, setI] = useState(0);
  const enFile = s?.etat === "queued";
  useEffect(() => {
    // en file, rien n'est encore calculé : le défilement attend son tour
    if (enFile) return;
    const h = setInterval(() => setI((x) => x + 1), 800);
    return () => clearInterval(h);
  }, [enFile]);
  const courant = i % ETAPES.length;
  const tours = Math.floor(i / ETAPES.length);
  const pct = Math.min(96, ((i + 1) / ETAPES.length) * 100);
  return (
    <div className="w-full rounded-2xl border border-rule bg-surface p-6" aria-live="polite">
      <div className="mb-6 flex flex-col items-center gap-1.5 text-center">
        <span className="font-logo text-3xl text-gold-ink">
          l<span className="logo-spin-o">o</span>wi
        </span>
        <span className="text-sm text-muted">
          {enFile
            ? `Waiting for a free slot… (${s?.position} of ${s?.en_attente})`
            : "Analysing the listing…"}
          {s?.restant_s != null && (
            <span className="font-semibold tabular-nums text-ink"> · {duree(s.restant_s)} left</span>
          )}
        </span>
      </div>
      {/* Les repères sont écrits dans la couleur du fond de la carte, posés PAR-DESSUS
          la piste : invisibles sur la piste claire, ils apparaissent quand la barre
          verte passe dessous. 0 % et 100 % ne sont pas affichés. */}
      <div className="relative h-5 w-full overflow-hidden rounded-full bg-sunken">
        <div
          className="absolute inset-y-0 left-0 bg-brand transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
        {[25, 50, 75].map((g) => (
          <span key={g} className="absolute inset-y-0 z-10 flex items-center" style={{ left: `${g}%` }}>
            <span className="h-full w-px bg-surface" />
            <span className="ml-1 text-[10px] font-semibold tabular-nums leading-none text-surface">{g}%</span>
          </span>
        ))}
      </div>
      <ul className="mt-5 space-y-3">
        {ETAPES.map((e, k) => {
          const fait = tours > 0 || k < courant;
          const actif = k === courant && tours === 0;
          return (
            <li
              key={e.t}
              className={`flex items-start gap-3 transition-opacity duration-500 ${
                fait || actif ? "opacity-100" : "opacity-35"
              }`}
            >
              <span
                className={`mt-1 inline-flex h-4 w-4 flex-none items-center justify-center rounded-full border ${
                  fait ? "border-pos bg-pos/20" : actif ? "border-brand" : "border-faint"
                }`}
                aria-hidden="true"
              >
                {fait && <span className="h-1.5 w-1.5 rounded-full bg-pos" />}
                {actif && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand" />}
              </span>
              <span>
                <span className="block text-sm text-ink">{e.t}</span>
                <span className="block text-xs text-faint">{e.d}</span>
              </span>
            </li>
          );
        })}
      </ul>
      {tours > 1 && (
        <p className="mt-5 text-xs text-faint">Taking longer than usual — still working on it.</p>
      )}
    </div>
  );
}
