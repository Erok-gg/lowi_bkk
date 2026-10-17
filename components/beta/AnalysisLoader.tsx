"use client";
/**
 * AnalysisLoader — défilement des éléments calculés pendant la génération.
 * Chaque ligne correspond à un calcul réel du rapport (cf. rapport.py) : le
 * chargement explique ce qu'on obtient, il ne fait pas patienter avec du vide.
 */
import { useEffect, useState } from "react";

/** Ce que renvoie /api/beta/analyse (miroir de `Suivi` dans lib/beta/rapport.ts). */
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

const duree = (s: number) => (s < 60 ? `~${s} s` : `~${Math.round(s / 60)} min`);

const ETAPES = [
  { t: "Finding the listing in 5 portals", d: "DDproperty · FazWaz · PropertyScout · Nestopa · LivingInsider" },
  { t: "Rebuilding the listing's history", d: "first seen, reposts, price cuts across portals" },
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
  return (
    <div className="w-full rounded-2xl border border-violet-soft bg-surface p-6" aria-live="polite">
      <div className="mb-5 flex items-center gap-3">
        <span className="font-logo text-2xl text-gold">
          l<span className="logo-spin-o">o</span>wi
        </span>
        <span className="text-sm text-text-muted">
          {enFile ? "Waiting for a free slot…" : "Analysing the listing…"}
        </span>
        {s?.restant_s != null && (
          <span className="ml-auto text-sm font-semibold tabular-nums text-text">{duree(s.restant_s)} left</span>
        )}
      </div>
      {s && (
        <div className="mb-4 grid grid-cols-3 gap-2 text-center">
          <div className="rounded-lg bg-anthracite p-2">
            <p className="text-[11px] text-text-faint">{enFile ? "Your place in line" : "Status"}</p>
            <p className="text-sm font-semibold tabular-nums text-text">
              {enFile ? `${s.position} of ${s.en_attente}` : "computing"}
            </p>
          </div>
          <div className="rounded-lg bg-anthracite p-2">
            <p className="text-[11px] text-text-faint">Reports running</p>
            <p className="text-sm font-semibold tabular-nums text-text">
              {s.en_cours} / {s.max_parallele}
            </p>
          </div>
          <div className="rounded-lg bg-anthracite p-2">
            <p className="text-[11px] text-text-faint">Reports processed</p>
            <p className="text-sm font-semibold tabular-nums text-text">
              {s.traites_total.toLocaleString("en-US")}
              <span className="font-normal text-text-faint"> · {s.traites_aujourdhui} today</span>
            </p>
          </div>
        </div>
      )}
      <div className="h-1 w-full overflow-hidden rounded bg-anthracite">
        <div
          className="h-1 bg-violet-fluo transition-all duration-700"
          style={{ width: `${Math.min(96, ((i + 1) / ETAPES.length) * 100)}%` }}
        />
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
                  fait ? "border-[#34d399] bg-[#34d399]/20" : actif ? "border-violet-fluo" : "border-text-faint"
                }`}
                aria-hidden="true"
              >
                {fait && <span className="h-1.5 w-1.5 rounded-full bg-[#34d399]" />}
                {actif && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-violet-fluo" />}
              </span>
              <span>
                <span className="block text-sm text-text">{e.t}</span>
                <span className="block text-xs text-text-faint">{e.d}</span>
              </span>
            </li>
          );
        })}
      </ul>
      {tours > 1 && (
        <p className="mt-5 text-xs text-text-faint">Taking longer than usual — still working on it.</p>
      )}
    </div>
  );
}
