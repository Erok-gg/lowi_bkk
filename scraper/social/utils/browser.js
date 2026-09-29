import { chromium } from "playwright";
import { CONFIG } from "../config.js";

/**
 * Connexion à Chrome existant via CDP (Remote Debugging Protocol).
 * Chrome doit être lancé avec : --remote-debugging-port=9222
 */
export async function connectToChrome() {
  const { host, debuggingPort } = CONFIG.chrome;
  const cdpUrl = `http://${host}:${debuggingPort}`;

  let browser;
  try {
    browser = await chromium.connectOverCDP(cdpUrl);
  } catch (err) {
    throw new Error(
      `Impossible de se connecter à Chrome (${cdpUrl}).\n` +
      `Lance Chrome avec ce flag :\n` +
      `"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=${debuggingPort}\n\n` +
      `Erreur originale : ${err.message}`
    );
  }

  const contexts = browser.contexts();
  const context = contexts[0] ?? await browser.newContext();
  return { browser, context };
}

/**
 * Délai aléatoire pour simuler un comportement humain.
 */
export async function humanDelay(page, min, max) {
  const [minMs, maxMs] = min !== undefined
    ? [min, max]
    : CONFIG.scraping.actionDelayMs;
  const delay = Math.floor(Math.random() * (maxMs - minMs)) + minMs;
  await page.waitForTimeout(delay);
}

/**
 * Scroll progressif d'une page (comme un humain qui lit).
 */
export async function humanScroll(page, steps = 5) {
  for (let i = 0; i < steps; i++) {
    await page.mouse.wheel(0, Math.floor(Math.random() * 400) + 200);
    await page.waitForTimeout(CONFIG.scraping.scrollPauseMs + Math.random() * 800);
  }
}

/**
 * Déplace la souris vers un point aléatoire de la fenêtre, en plusieurs étapes
 * (trajectoire non rectiligne) — juste pour laisser une trace d'activité
 * naturelle entre deux actions, sans cliquer sur rien.
 */
export async function humanMouseDrift(page) {
  const viewport = page.viewportSize() ?? { width: 1280, height: 800 };
  const x = 80 + Math.random() * (viewport.width - 160);
  const y = 80 + Math.random() * (viewport.height - 160);
  await page.mouse.move(x, y, { steps: 8 + Math.floor(Math.random() * 12) });
}

/**
 * Scroll avec petites imperfections humaines : vitesse irrégulière,
 * parfois un sur-scroll suivi d'une correction vers le haut, parfois
 * une pause "de lecture" plus longue, parfois un mouvement de souris
 * sans rapport entre deux scrolls.
 */
export async function humanScrollWithHesitation(page, steps = 5) {
  for (let i = 0; i < steps; i++) {
    const dist = Math.floor(Math.random() * 350) + 150;
    await page.mouse.wheel(0, dist);
    await page.waitForTimeout(800 + Math.random() * 1600);

    // ~15% de chance de sur-scroller puis se corriger un peu vers le haut
    if (Math.random() < 0.15) {
      await page.waitForTimeout(250 + Math.random() * 450);
      await page.mouse.wheel(0, -(Math.floor(Math.random() * 150) + 40));
      await page.waitForTimeout(400 + Math.random() * 700);
    }

    // ~30% de chance de bouger la souris sans raison entre deux scrolls
    if (Math.random() < 0.3) {
      await humanMouseDrift(page);
    }

    // ~10% de chance d'une pause "lecture" plus longue
    if (Math.random() < 0.1) {
      await page.waitForTimeout(1500 + Math.random() * 3000);
    }
  }
}

/**
 * Délai aléatoire "large" entre deux actions importantes (ex: changer de
 * profil), avec une petite chance de pause plus longue (distraction humaine).
 */
export async function humanLongDelay(minMs = 6000, maxMs = 15000) {
  const delay = Math.floor(Math.random() * (maxMs - minMs)) + minMs;
  await new Promise((r) => setTimeout(r, delay));
  if (Math.random() < 0.12) {
    const extra = 8000 + Math.random() * 20000;
    await new Promise((r) => setTimeout(r, extra));
  }
}
