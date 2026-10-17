/**
 * rapport.ts — génération et lecture des rapports beta (côté serveur uniquement).
 *
 * Le calcul vit en Python (`study/tension/rapport.py`) parce qu'il lit la base de
 * référence SQLite de PC2 et le fichier mensuel des scores. Next se contente de
 * lancer ce calcul et de lire le JSON produit.
 *
 * ⚠ Ne fonctionne QUE sur le poste qui détient la base (PC2) : Vercel n'a ni
 * Python ni accès à PC2 (cf. CLAUDE.md, « Architecture des données »). Sur un
 * serveur sans base, `disponible()` renvoie false et la page le dit au lieu
 * d'échouer en silence.
 */
import "server-only";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync, writeFileSync, mkdirSync, statSync } from "node:fs";
import path from "node:path";
import type { Rapport } from "./types";

const RACINE = process.cwd();
const DB = process.env.LOWI_SQLITE_DB ? path.resolve(RACINE, process.env.LOWI_SQLITE_DB) : "";
const PYTHON =
  process.env.LOWI_PYTHON ||
  path.join(RACINE, "scraper", ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const DOSSIER = process.env.LOWI_RAPPORTS_DIR || (DB ? path.join(path.dirname(DB), "rapports") : "");

/** Portails dont nous lisons les annonces : une autre URL ne peut pas être reconnue. */
export const PORTAILS = ["ddproperty.com", "fazwaz.com", "propertyscout.co.th", "nestopa.com", "livinginsider.com"];

/** Même identifiant que `identifiant()` côté Python : même URL → même rapport. */
export function identifiant(url: string): string {
  return createHash("sha256").update(url.trim()).digest("hex").slice(0, 16);
}

export function urlAcceptee(url: string): { ok: true } | { ok: false; raison: string } {
  let u: URL;
  try {
    u = new URL(url.trim());
  } catch {
    return { ok: false, raison: "This does not look like a link. Paste the full address of the listing." };
  }
  if (!/^https?:$/.test(u.protocol)) return { ok: false, raison: "Only web links (https://…) are supported." };
  const hote = u.hostname.replace(/^www\./, "");
  if (!PORTAILS.some((p) => hote === p || hote.endsWith("." + p)))
    return {
      ok: false,
      raison: "This portal is not covered yet. Supported: DDproperty, FazWaz, PropertyScout, Nestopa, LivingInsider.",
    };
  return { ok: true };
}

export function disponible(): boolean {
  return Boolean(DB && existsSync(DB) && existsSync(PYTHON) && DOSSIER);
}

const fichier = (id: string) => path.join(DOSSIER, `${id}.json`);
const marqueur = (id: string) => path.join(DOSSIER, `${id}.pending`);
const erreur = (id: string) => path.join(DOSSIER, `${id}.error`);

/* ─────────────────────────── file et plafond ───────────────────────────────
 * Décision de l'utilisateur (2026-10-17) : au plus 6 calculs en même temps,
 * les suivants attendent dans une file. Mesuré le même jour sur PC2 (8 cœurs) :
 * 1 demande → 10,4 s ; 3 → 18,5 s ; 6 → 28,1 s. Sans plafond, 30 demandes
 * lanceraient 30 processus, y compris pendant le cycle de nuit.
 * La file vit en mémoire du serveur Next (sur `globalThis` pour survivre au
 * rechargement à chaud du mode dev) : un redémarrage la perd, et l'écran de
 * chargement le signale (état « unknown »). */
export const MAX_PARALLELE = 6;

/** Durée d'un calcul quand k tournent en parallèle, ajustée sur les 3 mesures :
 *  t(k) ≈ 6,5 + 3,6·k secondes (10,1 / 17,3 / 28,1 s pour k = 1 / 3 / 6). */
export const dureeEstimee = (k: number) => 6.5 + 3.6 * Math.max(1, k);

type Tache = { id: string; url: string; recu: number; debut?: number };
type FileEtat = { enCours: Map<string, Tache>; attente: Tache[] };
const G = globalThis as unknown as { __lowiFile?: FileEtat };
const F: FileEtat = (G.__lowiFile ??= { enCours: new Map(), attente: [] });

export type Etat = "ready" | "pending" | "queued" | "not_found" | "error" | "unknown";

export function etat(id: string): Etat {
  if (!/^[0-9a-f]{16}$/.test(id) || !DOSSIER) return "unknown";
  if (existsSync(fichier(id))) {
    const r = lire(id);
    return r?.statut === "not_found" ? "not_found" : "ready";
  }
  if (existsSync(erreur(id))) return "error";
  if (F.attente.some((t) => t.id === id)) return "queued";
  if (F.enCours.has(id)) return "pending";
  if (existsSync(marqueur(id))) {
    // un calcul qui dépasse 5 min est mort (mesuré : ~10 s, 28 s à 6 en parallèle)
    if (Date.now() - statSync(marqueur(id)).mtimeMs > 5 * 60_000) return "error";
    return "pending";
  }
  return "unknown";
}

/** Rapports déjà produits : au total et aujourd'hui (fichiers du dossier). */
function compteurs(): { total: number; aujourdhui: number } {
  if (!DOSSIER || !existsSync(DOSSIER)) return { total: 0, aujourdhui: 0 };
  const minuit = new Date();
  minuit.setHours(0, 0, 0, 0);
  let total = 0, aujourdhui = 0;
  for (const f of readdirSync(DOSSIER)) {
    if (!f.endsWith(".json")) continue;
    total++;
    if (statSync(path.join(DOSSIER, f)).mtimeMs >= minuit.getTime()) aujourdhui++;
  }
  return { total, aujourdhui };
}

export type Suivi = {
  id: string;
  etat: Etat;
  position: number | null;     // rang dans la file (1 = le prochain), null si pas en file
  en_cours: number;            // calculs en cours sur le serveur
  en_attente: number;          // demandes dans la file
  max_parallele: number;
  traites_total: number;
  traites_aujourdhui: number;
  restant_s: number | null;    // temps restant estimé pour CETTE demande
};

/** État complet d'une demande, pour l'écran de chargement. */
export function suivi(id: string): Suivi {
  const e = etat(id);
  const k = F.enCours.size;
  const pos = F.attente.findIndex((t) => t.id === id);
  let restant: number | null = null;
  if (e === "pending") {
    const t = F.enCours.get(id);
    const ecoule = t?.debut ? (Date.now() - t.debut) / 1000 : 0;
    restant = Math.max(1, dureeEstimee(k) - ecoule);
  } else if (e === "queued" && pos >= 0) {
    // Les calculs lancés ensemble finissent presque ensemble (mesuré : les 6
    // premiers à 31–34 s) : une place ne se libère qu'à la fin de l'un d'eux.
    // Une estimation par « débit moyen » annonçait 33 s pour un rapport livré à
    // 52 s (essai à 9 demandes, 2026-10-17). On attend donc la libération de SA
    // place, puis son propre calcul, mené avec ceux qui partent en même temps.
    const restants = [...F.enCours.values()]
      .map((t) => Math.max(1, dureeEstimee(k) - (Date.now() - (t.debut ?? Date.now())) / 1000))
      .sort((a, b) => a - b);
    const tour = Math.floor(pos / MAX_PARALLELE);
    const place = restants[pos % MAX_PARALLELE] ?? 0;
    const ensemble = Math.min(MAX_PARALLELE, F.attente.length - tour * MAX_PARALLELE);
    restant = place + tour * dureeEstimee(MAX_PARALLELE) + dureeEstimee(ensemble);
  }
  const c = compteurs();
  return {
    id, etat: e, position: pos >= 0 ? pos + 1 : null, en_cours: k, en_attente: F.attente.length,
    max_parallele: MAX_PARALLELE, traites_total: c.total, traites_aujourdhui: c.aujourdhui,
    restant_s: restant === null ? null : Math.round(restant),
  };
}

export function lire(id: string): Rapport | null {
  if (!/^[0-9a-f]{16}$/.test(id) || !DOSSIER || !existsSync(fichier(id))) return null;
  return JSON.parse(readFileSync(fichier(id), "utf-8")) as Rapport;
}

/** Démarre le calcul. Arguments passés en tableau, sans shell : l'URL collée
 *  par l'utilisateur n'est jamais interprétée. */
function demarrer(t: Tache): void {
  t.debut = Date.now();
  F.enCours.set(t.id, t);
  writeFileSync(marqueur(t.id), new Date().toISOString());
  const p = spawn(
    PYTHON,
    ["-m", "study.tension.rapport", "--url", t.url, "--db", DB, "--out", DOSSIER],
    { cwd: RACINE, windowsHide: true },
  );
  let sortie = "";
  p.stderr.on("data", (d) => (sortie += String(d)));
  const fin = (code: number | null) => {
    if (!F.enCours.delete(t.id)) return;     // "error" et "close" peuvent arriver tous les deux
    try {
      if (code !== 0) writeFileSync(erreur(t.id), sortie.slice(-4000) || `exit ${code}`);
      if (existsSync(marqueur(t.id))) writeFileSync(marqueur(t.id) + ".done", "");
    } catch {
      /* le marqueur périmé suffira à signaler l'échec */
    }
    suivant();
  };
  p.on("close", fin);
  p.on("error", () => fin(-1));
}

function suivant(): void {
  while (F.enCours.size < MAX_PARALLELE && F.attente.length) demarrer(F.attente.shift()!);
}

/** Lance (ou met en file) le calcul s'il n'est ni fait, ni en cours, ni en attente. */
export function lancer(url: string): string {
  const id = identifiant(url);
  const e = etat(id);
  if (e === "ready" || e === "pending" || e === "queued" || e === "not_found") return id;
  mkdirSync(DOSSIER, { recursive: true });
  F.attente.push({ id, url: url.trim(), recu: Date.now() });
  suivant();
  return id;
}
