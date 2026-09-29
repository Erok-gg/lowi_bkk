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
  const date = new Date().toISOString().split("T")[0];
  const filename = join(CONFIG.output.dir, `${source}_${date}.json`);

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
