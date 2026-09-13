/**
 * Agent Facebook — scrape les posts des 7 derniers jours sur les groupes configurés.
 * Prérequis : Chrome lancé avec --remote-debugging-port=9222 et connecté à Facebook.
 */

import chalk from "chalk";
import { readFileSync, writeFileSync, mkdirSync } from "fs";
import { subDays, subHours, subWeeks, subMonths, isAfter } from "date-fns";
import { connectToChrome, humanDelay, humanScroll } from "../utils/browser.js";
import { analyzePosts } from "../utils/analyzer.js";
import { saveResults } from "../utils/storage.js";
import { keepAwake } from "../utils/keep-awake.js";
import { CONFIG } from "../config.js";

// ─── Surcharges par variables d'environnement ────────────────────────────────
// Permettent de réutiliser EXACTEMENT la même logique DOM pour une autre veille
// (ex. annonces immobilières Bangkok) sans dupliquer le code : quand Facebook
// change sa structure, il n'y a qu'un seul endroit à corriger.
//   FB_GROUPS_FILE  chemin d'un JSON { "groups": ["url", ...] }
//   FB_SOURCE       préfixe des fichiers de sortie (défaut "facebook")
//   FB_SKIP_ANALYSIS=1  collecte brute, sans qualification prospection
//   FB_DAYS_BACK    fenêtre temporelle en jours (défaut CONFIG.scraping.daysBack)
//   FB_RICH_CONTENT=1   contenu intégral en ordre visuel (annonces immo)
const GROUPS_FILE = process.env.FB_GROUPS_FILE || null;
const SOURCE = process.env.FB_SOURCE || "facebook";
const SKIP_ANALYSIS = process.env.FB_SKIP_ANALYSIS === "1";
const RICH_CONTENT = process.env.FB_RICH_CONTENT === "1";
const DAYS_BACK = parseInt(process.env.FB_DAYS_BACK || CONFIG.scraping.daysBack, 10);

const CUTOFF_DATE = subDays(new Date(), DAYS_BACK);

function loadGroups() {
  if (!GROUPS_FILE) return CONFIG.facebook.groups;
  const raw = JSON.parse(readFileSync(GROUPS_FILE, "utf-8"));
  return (raw.groups ?? [])
    .map((g) => (typeof g === "string" ? g : g.url))
    .filter(Boolean);
}

// ─── Parsing de la date Facebook ─────────────────────────────────────────────
// Facebook affiche des dates relatives ("il y a 3 jours") ou absolues ("15 juin 2024")

function parseFacebookDate(text) {
  if (!text) return null;
  const t = text.toLowerCase().trim();
  // Un libellé de date est court — évite de matcher des phrases de contenu
  if (t.length > 40) return null;
  const now = new Date();
  const OLD = new Date("2000-01-01"); // sentinelle « clairement hors fenêtre »

  // Unix timestamp brut (data-utime)
  if (/^\d{10}$/.test(t)) return new Date(parseInt(t) * 1000);

  // Années relatives : "il y a 1 an", "2 ans", "un an", "a year ago", "3 y"
  if (/(^|il y a )\s*(un|\d+)\s*ans?\b/.test(t)) return OLD;
  if (/\b(a|\d+)\s*y(ear)?s?(\s*ago)?$/.test(t)) return OLD;

  // Année calendaire visible ("15 juin 2025") → vieux si antérieure à l'année courante
  const yearMatch = t.match(/\b(20\d{2})\b/);
  if (yearMatch && parseInt(yearMatch[1]) < now.getFullYear()) return OLD;

  // Français : "il y a X heure(s)/jour(s)/semaine(s)/mois" (chiffre ou "un/une")
  let m = t.match(/il y a (une?|\d+)\s*(heure|jour|semaine|mois)/);
  if (m) {
    const n = /^une?$/.test(m[1]) ? 1 : parseInt(m[1]);
    if (m[2].startsWith("heure"))   return subHours(now, n);
    if (m[2].startsWith("jour"))    return subDays(now, n);
    if (m[2].startsWith("semaine")) return subWeeks(now, n);
    if (m[2].startsWith("mois"))    return subMonths(now, n);
  }

  // Anglais : "X hour(s)/day(s)/week(s)/month(s) ago" (chiffre ou "a/an")
  m = t.match(/(an?|\d+)\s*(hour|day|week|month)s?\s*ago/);
  if (m) {
    const n = /^an?$/.test(m[1]) ? 1 : parseInt(m[1]);
    if (m[2] === "hour")  return subHours(now, n);
    if (m[2] === "day")   return subDays(now, n);
    if (m[2] === "week")  return subWeeks(now, n);
    if (m[2] === "month") return subMonths(now, n);
  }

  // Formats courts : "45 min", "5 h", "3 j", "2 sem" (FR) / "5m", "2h", "3d", "1w" (EN)
  m = t.match(/^(\d+)\s*(min|h|j|sem|m|d|w)\.?$/);
  if (m) {
    const n = parseInt(m[1]);
    if (m[2] === "min" || m[2] === "m") return now;
    if (m[2] === "h")                   return subHours(now, n);
    if (m[2] === "j" || m[2] === "d")   return subDays(now, n);
    if (m[2] === "sem" || m[2] === "w") return subWeeks(now, n);
  }

  // Timestamp brouillé relu en ordre visuel : la vraie date est en TÊTE, collée
  // aux caractères leurres sans séparateur ("1minnotpsdreoSmu4hh…"). On ne tente
  // ce parsing qu'après avoir épuisé les formats propres, et jamais si un nom de
  // mois apparaît — sinon "15 juin 2026" serait lu comme "15 j".
  if (!/janv|févr|fevr|mars|avril|juin|juil|août|aout|sept|octo|nove|déce|dece|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec/i.test(t)) {
    m = t.match(/^(\d+)\s*(min|sem|ans?|[hjdwm])/);
    if (m) {
      const n = parseInt(m[1]);
      const u = m[2];
      if (u === "ans" || u === "an")  return new Date("2000-01-01"); // hors fenêtre
      if (u === "min" || u === "m")   return now;
      if (u === "h")                  return subHours(now, n);
      if (u === "j" || u === "d")     return subDays(now, n);
      if (u === "sem" || u === "w")   return subWeeks(now, n);
    }
  }

  // "hier" / "yesterday"
  if (t === "hier" || t === "yesterday") return subDays(now, 1);

  // Jour de la semaine seul ("lundi", "mardi à 14:30"…) → dans la semaine.
  // Longueur limitée pour ne pas matcher une phrase qui commence par un jour.
  const joursFr = ["lundi","mardi","mercredi","jeudi","vendredi","samedi","dimanche"];
  const joursEn = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"];
  if (t.length <= 25 && (joursFr.some((j) => t.startsWith(j)) || joursEn.some((j) => t.startsWith(j)))) {
    return subDays(now, 3); // approximation : dans la semaine
  }

  // "X min" / "just now" / "à l'instant"
  if (/\d+\s*min/.test(t) || t.includes("just now") || t.includes("instant")) {
    return now;
  }

  return null; // format inconnu → laisse les autres stratégies chercher
}

// ─── Extraction d'un post individuel ────────────────────────────────────────

async function extractPost(element, groupName, groupUrl) {
  try {
    // Lien permanent — clé de déduplication. Depuis le changement de DOM
    // Facebook (juil. 2026), le TEXTE de ce lien est aussi le timestamp du
    // post ("10 h", "3 j", "il y a 2 jours"…). On ignore les liens de
    // commentaires (comment_id) pour ne dater que l'en-tête du post.
    // Facebook brouille le texte des timestamps : les caractères sont mélangés
    // dans le DOM et remis en ordre visuellement par CSS (des leurres sont
    // intercalés). On relit donc chaque lien de date dans l'ORDRE VISUEL
    // (ligne, puis colonne) : la vraie date réapparaît en TÊTE de chaîne,
    // suivie des caractères leurres — d'où le parsing sur le début seulement.
    const dateLinks = await element.evaluate((el) => {
      function visualText(root) {
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        const parts = [];
        let n;
        while ((n = walker.nextNode())) {
          const t = n.textContent;
          if (!t || !t.trim()) continue;
          const r = document.createRange();
          r.selectNodeContents(n);
          const box = r.getBoundingClientRect();
          if (box.width === 0 && box.height === 0) continue; // caché
          parts.push({ t, top: Math.round(box.top), left: box.left });
        }
        // même ligne (±4 px) → tri par abscisse, sinon par ordonnée
        parts.sort((a, b) => (Math.abs(a.top - b.top) > 4 ? a.top - b.top : a.left - b.left));
        return parts.map((p) => p.t).join("");
      }

      const links = [...el.querySelectorAll("a")].filter((a) => {
        const h = a.getAttribute("href") || "";
        return (
          h.startsWith("?__cft__") ||
          /\/(posts|permalink)\//.test(h) ||
          h.includes("story_fbid=")
        );
      });

      // Certains groupes n'exposent plus de permalink : l'id du post se
      // retrouve alors dans les liens photo (set=pcb.<id>) → on reconstruit.
      let pcb = null;
      for (const a of el.querySelectorAll('a[href*="set=pcb."]')) {
        const m = (a.getAttribute("href") || "").match(/set=pcb\.(\d+)/);
        if (m) { pcb = m[1]; break; }
      }

      return {
        pcb,
        links: links.map((a) => ({
          href: a.getAttribute("href") || "",
          dom: (a.textContent || "").trim().slice(0, 40),
          visual: visualText(a).slice(0, 40),
        })),
      };
    });

    let href = null;
    let postDate = null;
    let dateText = "";
    for (const l of dateLinks.links) {
      // Vrai permalink seulement (le lien de date peut n'être qu'un tracker)
      if (!href && /\/(posts|permalink)\//.test(l.href)) href = l.href.split("?")[0];
      // Date du post = le PLUS ANCIEN des timestamps affichés : un post est
      // toujours antérieur à ses commentaires, et un vieux post remonté par
      // un commentaire récent affiche "1 an" quelque part → rejeté.
      const parsed = parseFacebookDate(l.visual) ?? parseFacebookDate(l.dom);
      if (parsed && (!postDate || parsed < postDate)) { postDate = parsed; dateText = "permalink"; }
    }
    if (!href && dateLinks.pcb) href = `/groups/${groupName}/posts/${dateLinks.pcb}/`;

    const link = href
      ? href.startsWith("http") ? href : `https://www.facebook.com${href}`
      : null;

    // Auteur — premier lien de profil avec un texte non vide (le premier
    // match du sélecteur est souvent un lien vide dans le nouveau DOM)
    let author = "Inconnu";
    for (const sel of ["h2 a", "h3 a", "strong > a", 'a[href*="/user/"]']) {
      for (const el of await element.$$(sel)) {
        const t = (await el.textContent()).trim();
        if (t.length > 1 && t.length < 60) { author = t; break; }
      }
      if (author !== "Inconnu") break;
    }

    // Date (stratégies de secours si le permalink n'a rien donné)

    // Stratégie 1 : data-utime (Unix timestamp, le plus fiable)
    if (!postDate) {
      const abbrEl = await element.$("abbr[data-utime]");
      if (abbrEl) {
        const utime = await abbrEl.getAttribute("data-utime");
        postDate = new Date(parseInt(utime) * 1000);
        dateText = utime;
      }
    }

    // Stratégie 2 : aria-label sur les liens de date
    if (!postDate) {
      const dateLinks = await element.$$("a[aria-label], span[aria-label]");
      for (const el of dateLinks) {
        const label = await el.getAttribute("aria-label");
        if (!label) continue;
        const parsed = parseFacebookDate(label);
        if (parsed) { postDate = parsed; dateText = label; break; }
      }
    }

    // Stratégie 3 : texte visible du lien de date (souvent "il y a 3 jours")
    if (!postDate) {
      const spanLinks = await element.$$('a > span, span[id]');
      for (const el of spanLinks) {
        const txt = (await el.textContent()).trim();
        const parsed = parseFacebookDate(txt);
        if (parsed) { postDate = parsed; dateText = txt; break; }
      }
    }

    // Si la date est clairement hors des 7 jours → on skip
    if (postDate && !isAfter(postDate, CUTOFF_DATE)) return null;

    // 2026-09-12 : Facebook a de nouveau changé son DOM — plus aucun élément
    // de date/permalien n'est détectable sur certains groupes (les 3 stratégies
    // ci-dessus échouent toutes), y compris sur du contenu manifestement réel et
    // récent (vérifié en inspectant le DOM en direct). Rejeter systématiquement
    // par prudence revient à tout jeter. On n'exclut donc plus ici : on marque
    // la date comme inconnue et on tranche plus bas, une fois le contenu lu,
    // sur la présence d'un signal immobilier fort — pas d'invention de date.
    const dateInconnue = !postDate && !dateText;

    // Contenu — extrait tout le texte de l'article et supprime le bruit UI
    const rawText = await element.evaluate((el, rich) => {
      const cloned = el.cloneNode(true);
      cloned.querySelectorAll("svg, img, button, [role='button'], [aria-hidden='true']").forEach((n) => n.remove());
      if (!rich) return cloned.innerText ?? cloned.textContent ?? "";

      // Mode riche (annonces) : on lit le texte dans l'ORDRE VISUEL sur
      // l'élément d'origine. Le brouillage anti-scraping se démêle tout seul,
      // sans avoir à supprimer des jetons — ce qui détruisait au passage des
      // données réelles collées ("35000THB", "Sukhumvit48").
      const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      const parts = [];
      let n;
      while ((n = w.nextNode())) {
        const t = n.textContent;
        if (!t || !t.trim()) continue;
        const p = n.parentElement;
        if (p && (p.closest('[aria-hidden="true"]') || p.closest('[role="button"]'))) continue;
        const r = document.createRange();
        r.selectNodeContents(n);
        const b = r.getBoundingClientRect();
        if (b.width === 0 && b.height === 0) continue;
        parts.push({ t, top: Math.round(b.top), left: b.left });
      }
      parts.sort((a, b) => (Math.abs(a.top - b.top) > 4 ? a.top - b.top : a.left - b.left));
      // Nouvelle ligne à chaque changement de ligne visuelle
      let out = "", lastTop = null;
      for (const p of parts) {
        if (lastTop !== null && Math.abs(p.top - lastTop) > 4) out += "\n";
        out += p.t;
        lastTop = p.top;
      }
      return out;
    }, RICH_CONTENT);

    let content;
    if (RICH_CONTENT) {
      // Dans une annonce, l'information est souvent dans des lignes COURTES
      // ("2 Bedrooms", "65 sqm", "35,000 THB/month") : on ne filtre donc plus
      // par longueur, mais sur les libellés d'interface connus.
      const UI = /^(facebook|j'aime|jaime|like|comment|commenter|partager|share|voir plus|see more|voir la traduction|see translation|répondre|reply|meilleur contributeur\(ice\)|\d+\s*(commentaires?|comments?|partages?|shares?)|tout voir|see all|\+\d+|·|…)$/i;
      // Ligne-leurre du brouillage anti-scraping : un seul bloc sans espace,
      // long, mêlant lettres et chiffres ("poeSdotnsrla26t8991l3lit64g197h08…").
      // Les vraies données ("35,000THB") sont bien plus courtes ; on épargne
      // aussi les URLs et identifiants (@, ., /).
      const isDecoy = (l) =>
        !/[\s@./]/.test(l) && l.length >= 16 && /[A-Za-z]/.test(l) && /\d/.test(l);
      content = rawText
        .split("\n")
        .map((l) => l.replace(/\s{2,}/g, " ").trim())
        .filter((l) => l.length >= 2 && !UI.test(l) && !isDecoy(l))
        .filter((l, i, arr) => arr.indexOf(l) === i)
        .join("\n")
        .trim();
    } else {
      // Nettoie le texte : supprime les lignes courtes (UI Facebook) et déduplique.
      // Retire aussi les jetons brouillés anti-scraping de Facebook : des mots
      // mêlant lettres et chiffres ("poodStresn6ha6g51683…") injectés dans les
      // en-têtes — aucun mot réel ne mélange ainsi lettres et chiffres sur ≥6 car.
      content = rawText
        .split("\n")
        .map((l) => l.trim())
        .map((l) =>
          l.replace(/(?=[^\s]*[A-Za-zÀ-ÿ])(?=[^\s]*\d)[A-Za-zÀ-ÿ0-9:,]{6,}/g, "")
            .replace(/\s{2,}/g, " ")
            .trim()
        )
        .filter((l) => l.length > 20) // ignore les labels courts (J'aime, Commenter…)
        .filter((l, i, arr) => arr.indexOf(l) === i)
        .join("\n")
        .trim();
    }
    if (!content || content.length < 30) return null;

    // Sans date fiable, on ne garde que si le contenu porte un signal
    // immobilier fort (prix, surface, chambres, station) — évite de collecter
    // du bruit de groupe (discussion, pub) sous prétexte que la date manque.
    const SIGNAL_IMMO = /\d\s?(sq\.?\s?m|sqm|ตร\.?\s?ม)|ห้องนอน|bedroom|BTS|MRT|บาท\b|THB|for\s?(rent|sale)|ขาย|เช่า|condo|studio/i;
    if (dateInconnue && !SIGNAL_IMMO.test(content)) return null;

    return {
      platform: "facebook",
      group: groupName,
      group_url: groupUrl,
      author,
      date: postDate ? postDate.toISOString() : (dateText || null), // null = date inconnue, jamais devinée
      date_inconnue: dateInconnue,
      link: link ?? groupUrl,
      content: content.slice(0, 2000), // cap à 2000 chars pour Hermes
    };
  } catch {
    return null;
  }
}

// ─── Scraping d'un groupe ────────────────────────────────────────────────────

async function scrapeGroup(page, groupUrl) {
  // Force le tri chronologique via paramètre URL — plus fiable que cliquer un bouton
  const url = new URL(groupUrl);
  url.searchParams.set("sorting_setting", "CHRONOLOGICAL");
  const sortedUrl = url.toString();

  console.log(chalk.cyan(`\n→ Groupe : ${groupUrl}`));
  await page.goto(sortedUrl, { waitUntil: "domcontentloaded", timeout: 30000 });

  // Attend que les posts se chargent
  await page.waitForSelector('div[role="article"]', { timeout: 15000 }).catch(() => {});
  await humanDelay(page, 2000, 3500);

  const posts = [];
  let scrollRounds = 0;
  let hitCutoff = false;
  let roundsWithNoNewPost = 0;
  let containersScanned = 0; // pour la sonde de structure (cf. fin de run())
  // Profondeur de défilement proportionnelle à la fenêtre demandée : 15 tours
  // suffisent pour 7 jours, il en faut bien plus pour remonter un mois.
  const maxScrollRounds = Math.min(80, Math.max(15, Math.round(DAYS_BACK * 2)));
  const maxIdleRounds = 2;          // arrête si rien de nouveau 2 scrolls de suite

  while (!hitCutoff && scrollRounds < maxScrollRounds && roundsWithNoNewPost < maxIdleRounds) {
    // Déplie les "Voir plus" avant d'extraire : un tiers des annonces sont
    // tronquées sinon, et c'est justement dans la partie masquée que se
    // trouvent le plus souvent le prix, la surface et le nom de l'immeuble.
    // On marque les boutons dans la page, puis on clique avec Playwright :
    // un el.click() synthétique ne déclenche pas le gestionnaire React de
    // Facebook, il faut un vrai événement de pointage.
    await page.evaluate(() => {
      const label = /^(voir plus|afficher la suite|see more|ดูเพิ่มเติม|เพิ่มเติม)$/i;
      document.querySelectorAll("[data-expand]").forEach((e) => e.removeAttribute("data-expand"));
      for (const el of document.querySelectorAll('div[role="button"], span[role="button"]')) {
        if (label.test((el.textContent || "").trim())) el.setAttribute("data-expand", "1");
      }
    }).catch(() => {});
    const expandBtns = await page.$$("[data-expand]");
    for (const btn of expandBtns.slice(0, 25)) {
      await btn.click({ timeout: 2000 }).catch(() => {});
    }
    if (expandBtns.length > 0) await humanDelay(page, 800, 1600);

    // Conteneurs de posts. Depuis juil. 2026 les posts ne sont plus des
    // div[role="article"] mais des enfants directs du feed (contenu hydraté
    // au scroll — seuls les posts proches du viewport sont remplis, d'où
    // l'extraction à chaque tour de scroll). role="article" reste en secours.
    let articles = await page.$$('div[role="feed"] > div');
    if (articles.length === 0) articles = await page.$$('div[role="article"]');
    if (scrollRounds === 0) {
      console.log(chalk.gray(`  Conteneurs détectés sur la page : ${articles.length}`));
    }
    containersScanned += articles.length;

    const countBefore = posts.length;

    for (const article of articles) {
      const post = await extractPost(article, extractGroupName(groupUrl), groupUrl);
      if (!post) continue;

      // Vérifie si ce post est déjà dans la liste — par lien, ou à défaut
      // par auteur+début de contenu (les posts sans permalink ont link=groupUrl,
      // qui n'est pas discriminant).
      const keyOf = (p) => (p.link && p.link !== p.group_url) ? p.link : `${p.author}::${p.content.slice(0, 80)}`;
      const alreadyAdded = posts.some((p) => keyOf(p) === keyOf(post));
      if (!alreadyAdded) {
        posts.push(post);
        process.stdout.write(chalk.green("."));
        if (process.env.DEBUG) {
          console.log(chalk.gray(`\n  [DEBUG] ${post.author} | ${post.date} | ${post.content.slice(0, 60)}…`));
        }
      }

      // Tri chronologique → dès qu'un post est trop vieux, tout ce qui suit l'est aussi
      if (post.date) {
        const postDate = new Date(post.date);
        if (!isNaN(postDate) && !isAfter(postDate, CUTOFF_DATE)) {
          hitCutoff = true;
          console.log(chalk.gray(`\n  Limite 7j atteinte (${post.date.slice(0, 10)}), arrêt du scroll`));
          break;
        }
      }
    }

    if (hitCutoff) break;

    roundsWithNoNewPost = posts.length === countBefore ? roundsWithNoNewPost + 1 : 0;

    await humanScroll(page, 3);
    scrollRounds++;
  }

  console.log(chalk.green(`\n  ${posts.length} posts extraits`));
  return { posts, containersScanned };
}

function extractGroupName(url) {
  const match = url.match(/groups\/([^/]+)/);
  return match ? decodeURIComponent(match[1]) : url;
}

// ─── Main ────────────────────────────────────────────────────────────────────

async function main() {
  console.log(chalk.bold.blue("\n╔══════════════════════════════╗"));
  console.log(chalk.bold.blue("║   Agent Facebook Scraper     ║"));
  console.log(chalk.bold.blue("╚══════════════════════════════╝\n"));
  const releaseAwake = keepAwake();
  try {
    await run();
  } finally {
    releaseAwake();
  }
}

async function run() {
  const configuredGroups = loadGroups();
  if (configuredGroups.length === 0) {
    console.log(chalk.red("⚠  Aucun groupe configuré (config.js → CONFIG.facebook.groups, ou FB_GROUPS_FILE)"));
    console.log(chalk.yellow("   Ajoute tes URLs de groupes et relance."));
    process.exit(1);
  }
  console.log(chalk.gray(`  ${configuredGroups.length} groupe(s) · fenêtre ${DAYS_BACK} j · source "${SOURCE}"${SKIP_ANALYSIS ? " · collecte brute" : ""}`));

  let browser, context;
  try {
    ({ browser, context } = await connectToChrome());
    console.log(chalk.green("✓ Connecté à Chrome"));
  } catch (err) {
    console.error(chalk.red(err.message));
    process.exit(1);
  }

  // Scrape plusieurs groupes en parallèle (onglets séparés) pour réduire le temps total
  const CONCURRENCY = 3;
  const allPosts = [];
  const sondeParGroupe = []; // { group, containers, posts } — pour détecter une casse DOM (cf. fin de run())
  const groups = [...configuredGroups];

  async function worker() {
    const page = await context.newPage();
    // Ferme silencieusement tout dialogue JS inattendu (popup, beforeunload) —
    // non géré, un dialogue fait crasher tout le processus (ProtocolError).
    page.on("dialog", (d) => d.dismiss().catch(() => {}));
    while (groups.length > 0) {
      const groupUrl = groups.shift();
      if (!groupUrl) break;
      try {
        const { posts, containersScanned } = await scrapeGroup(page, groupUrl);
        allPosts.push(...posts);
        sondeParGroupe.push({ group: groupUrl, containers: containersScanned, posts: posts.length });
        await humanDelay(page, 1500, 3000); // pause entre groupes
      } catch (err) {
        console.error(chalk.red(`  Erreur sur ${groupUrl}: ${err.message}`));
        sondeParGroupe.push({ group: groupUrl, containers: 0, posts: 0, erreur: err.message });
      }
    }
    await page.close();
  }

  await Promise.all(Array.from({ length: CONCURRENCY }, () => worker()));

  // ─── Sonde de structure (sur le modèle Lowi_bkk : détecter la casse DOM,
  // pas la réparer) ────────────────────────────────────────────────────────
  // Signal net : des conteneurs sont détectés mais 0 post n'en sort — c'est
  // exactement ce qui s'est produit le 2026-09-12 (Facebook a retiré tout
  // élément de date exploitable) et qui passait inaperçu jusqu'ici : le run
  // se terminait "normalement" avec 0 post, sans jamais alerter personne.
  const groupesEnPanne = sondeParGroupe.filter((g) => g.containers >= 3 && g.posts === 0);
  const sonde = {
    horodatage: new Date().toISOString(),
    source: SOURCE,
    groupes: sondeParGroupe,
    ok: groupesEnPanne.length === 0,
    groupes_en_panne: groupesEnPanne.map((g) => g.group),
  };
  mkdirSync("logs", { recursive: true });
  writeFileSync(`logs/sonde-${SOURCE}.json`, JSON.stringify(sonde, null, 2));
  if (!sonde.ok) {
    console.log(chalk.bold.red(`\n⚠ SONDE : ${groupesEnPanne.length} groupe(s) avec conteneurs détectés mais 0 post extrait — probable casse DOM Facebook, pas juste un groupe silencieux.`));
  }

  if (allPosts.length === 0) {
    console.log(chalk.yellow("\nAucun post collecté."));
    process.exit(0);
  }

  console.log(chalk.bold(`\n📊 Total : ${allPosts.length} posts sur ${DAYS_BACK} jours`));

  let analysis = null;
  if (SKIP_ANALYSIS) {
    // Collecte brute : la qualification est faite en aval par un autre pipeline
    // (ex. extraction d'annonces immobilières). Aucun appel à Ollama ici.
    console.log(chalk.gray("  Collecte brute — pas de qualification prospection"));
  } else {
    console.log(chalk.cyan("\n🤖 Analyse avec Hermes..."));
    try {
      analysis = await analyzePosts(allPosts, "facebook");
      const relevant = analysis.relevant ?? [];
      console.log(chalk.green(`✓ ${relevant.length} posts pertinents identifiés`));

      if (relevant.length > 0) {
        console.log(chalk.bold.yellow("\n── Posts pertinents ──────────────────"));
        for (const r of relevant) {
          const post = allPosts[r.index - 1];
          console.log(chalk.yellow(`\n[Score ${r.score}/10] ${post?.author} dans ${post?.group}`));
          console.log(chalk.white(`Raison : ${r.reason}`));
          console.log(chalk.cyan(`Action : ${r.action}`));
          console.log(chalk.gray(`Lien : ${post?.link}`));
        }
      }
    } catch (err) {
      console.error(chalk.red(`Erreur analyse Hermes : ${err.message}`));
    }
  }

  const outputFile = saveResults(SOURCE, allPosts, analysis);
  console.log(chalk.bold.green(`\n✓ Résultats sauvegardés → ${outputFile}`));
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error(chalk.red(`\nErreur fatale : ${err.message}`));
    process.exit(1);
  });
