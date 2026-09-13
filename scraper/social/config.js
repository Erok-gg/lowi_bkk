// Configuration du collecteur Facebook immo — copie DÉGRAISSÉE de
// C:\agentic\agents\agent2_scraper\config.js (2026-09-13). Ce qui a été
// retiré : les groupes Facebook de la veille Equance, WhatsApp, LinkedIn —
// ils vivent dans l'autre projet. La liste des groupes immo est dans
// immo-groups.json (FB_GROUPS_FILE), pas ici.

export const CONFIG = {
  // Ollama — référencé par utils/analyzer.js mais JAMAIS appelé ici :
  // scrape-immo-facebook.ps1 pose FB_SKIP_ANALYSIS=1 (collecte brute, pas
  // d'Ollama sur PC2 — marqueur agents/t1-absent).
  ollama: {
    baseUrl: "http://localhost:11434",
    model: "qwen3:8b",
    timeout: 480000,
  },

  // Chrome CDP — lancé par scrape-immo-facebook.ps1 avec
  // --remote-debugging-port=9222 sur un profil dédié (ChromeAutomationProfile).
  chrome: {
    debuggingPort: 9222,
    host: "localhost",
  },

  scraping: {
    daysBack: 7,
    scrollPauseMs: 1800,        // délai entre scrolls (comportement humain)
    actionDelayMs: [800, 2200], // délai min/max entre actions [ms]
  },

  // Groupes : vide à dessein — agent.js exige FB_GROUPS_FILE (immo-groups.json).
  facebook: { groups: [] },

  // Sortie : scraper/output/social/ (gitignoré via scraper/output/), relatif
  // au cwd = scraper/social, posé par le .ps1.
  output: {
    dir: process.env.FB_OUTPUT_DIR || "../output/social",
    format: "json",
  },
};
