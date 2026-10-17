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
import { existsSync, readFileSync, writeFileSync, mkdirSync, statSync } from "node:fs";
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

export type Etat = "ready" | "pending" | "not_found" | "error" | "unknown";

export function etat(id: string): Etat {
  if (!/^[0-9a-f]{16}$/.test(id) || !DOSSIER) return "unknown";
  if (existsSync(fichier(id))) {
    const r = lire(id);
    return r?.statut === "not_found" ? "not_found" : "ready";
  }
  if (existsSync(erreur(id))) return "error";
  if (existsSync(marqueur(id))) {
    // un calcul qui dépasse 5 min est mort (mesuré : ~10 s) — on le dit plutôt
    // que de laisser tourner le chargement indéfiniment
    if (Date.now() - statSync(marqueur(id)).mtimeMs > 5 * 60_000) return "error";
    return "pending";
  }
  return "unknown";
}

export function lire(id: string): Rapport | null {
  if (!/^[0-9a-f]{16}$/.test(id) || !DOSSIER || !existsSync(fichier(id))) return null;
  return JSON.parse(readFileSync(fichier(id), "utf-8")) as Rapport;
}

/** Lance la génération si elle n'est ni faite ni en cours. Arguments passés en
 *  tableau, sans shell : l'URL collée par l'utilisateur n'est jamais interprétée. */
export function lancer(url: string): string {
  const id = identifiant(url);
  const e = etat(id);
  if (e === "ready" || e === "pending" || e === "not_found") return id;
  mkdirSync(DOSSIER, { recursive: true });
  writeFileSync(marqueur(id), new Date().toISOString());
  const p = spawn(
    PYTHON,
    ["-m", "study.tension.rapport", "--url", url.trim(), "--db", DB, "--out", DOSSIER],
    { cwd: RACINE, windowsHide: true },
  );
  let sortie = "";
  p.stderr.on("data", (d) => (sortie += String(d)));
  p.on("close", (code) => {
    try {
      if (code !== 0) writeFileSync(erreur(id), sortie.slice(-4000) || `exit ${code}`);
      if (existsSync(marqueur(id))) writeFileSync(marqueur(id) + ".done", "");
    } catch {
      /* le marqueur périmé suffira à signaler l'échec */
    }
  });
  return id;
}
