import { writeFileSync, mkdirSync, existsSync, readFileSync } from "fs";
import { join } from "path";
import { CONFIG } from "../config.js";

function ensureOutputDir() {
  if (!existsSync(CONFIG.output.dir)) {
    mkdirSync(CONFIG.output.dir, { recursive: true });
  }
}

export function saveResults(source, posts, analysis, extra = {}) {
  ensureOutputDir();
  const now = new Date();
  const date = now.toISOString().split("T")[0];
  let filename = join(CONFIG.output.dir, `${source}_${date}.json`);
  // Jamais d'écrasement. La date est UTC : à Bangkok (UTC+7), deux collectes
  // de 08:07 et de 01:24 le lendemain tombent le même jour UTC. Mesuré le
  // 2026-10-04 : immo_2026-09-30.json (collecte de 08:14, retardée par la
  // veille) a été écrasé par celle de 01:24 le 01/10 avant d'être chargé,
  // soit une collecte perdue. Le suffixe horaire garde les deux ; social_leads
  // traite tout immo_*.json sans _charge.json, le suffixe ne le gêne pas.
  if (existsSync(filename)) {
    const hhmm = now.toISOString().slice(11, 16).replace(":", "");
    filename = join(CONFIG.output.dir, `${source}_${date}_${hhmm}.json`);
  }

  const data = {
    source,
    scraped_at: new Date().toISOString(),
    total_posts: posts.length,
    posts,
    analysis,
    ...extra,
  };

  writeFileSync(filename, JSON.stringify(data, null, 2), "utf-8");
  return filename;
}

export function loadPreviousResults(source) {
  ensureOutputDir();
  const date = new Date().toISOString().split("T")[0];
  const filename = join(CONFIG.output.dir, `${source}_${date}.json`);
  if (!existsSync(filename)) return null;
  return JSON.parse(readFileSync(filename, "utf-8"));
}
