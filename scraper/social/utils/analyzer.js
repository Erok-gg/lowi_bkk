import fetch from "node-fetch";
import chalk from "chalk";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import { CONFIG } from "../config.js";

const __dir = dirname(fileURLToPath(import.meta.url));
const keywordsPath = join(__dir, "../keywords.json");

function loadKeywords() {
  try {
    return JSON.parse(readFileSync(keywordsPath, "utf-8"));
  } catch {
    return { keywords: [], topics: [], signals_high_priority: [], exclude: [] };
  }
}

// Budget de tokens par batch : 16 384 de contexte − prompt/instructions (~2 500) − réponse (~1 500).
// Le découpage se fait au poids réel des posts, pas à un nombre fixe : aucun post
// n'est silencieusement tronqué par la limite de contexte du modèle.
// Batches volontairement petits : un 8B analyse bien 10-15 posts à la fois ;
// au-delà il dégénère en réponses répétitives.
const BATCH_TOKEN_BUDGET = 6000;
const MAX_POSTS_PER_BATCH = 15;
const NUM_CTX = 16384;

// Schéma imposé à Ollama (structured outputs) : la réponse est contrainte
// token par token — plus aucune sortie non parseable, thèmes limités à la
// taxonomie d'Anthony, scores bornés. "reasoning" en premier force le modèle
// à réfléchir avant de scorer.
const RESPONSE_SCHEMA = {
  type: "object",
  properties: {
    relevant: {
      type: "array",
      items: {
        type: "object",
        properties: {
          index: { type: "integer" },
          reasoning: { type: "string" },
          statut: {
            type: "string",
            enum: ["resident_expatrie", "futur_resident_explicite", "touriste_de_passage", "indetermine"],
          },
          besoin: {
            type: "string",
            enum: ["demande_personnelle", "avis_ou_reponse_donnee", "annonce_ou_promotion", "autre"],
          },
          score: { type: "integer", minimum: 1, maximum: 10 },
          theme: {
            type: "string",
            enum: [
              "fiscalite_expatrie", "investissement_epargne", "retraite",
              "succession_protection", "mariage_regime_matrimonial",
              "evenement_de_vie", "sante_prevoyance", "immobilier_france",
              "transfert_change",
            ],
          },
          reason: { type: "string" },
          action: { type: "string" },
        },
        required: ["index", "reasoning", "statut", "besoin", "score", "theme", "reason", "action"],
      },
    },
    summary: { type: "string" },
  },
  required: ["relevant", "summary"],
};

// Estimation grossière : ~3,5 caractères par token en français
function estimateTokens(text) {
  return Math.ceil((text?.length ?? 0) / 3.5);
}

function buildBatches(posts) {
  const batches = [];
  let current = [], used = 0, offset = 0;
  for (const p of posts) {
    const t = estimateTokens(p.content) + estimateTokens(p.author) + 30;
    if (current.length && (used + t > BATCH_TOKEN_BUDGET || current.length >= MAX_POSTS_PER_BATCH)) {
      batches.push({ chunk: current, offset });
      offset += current.length;
      current = [];
      used = 0;
    }
    current.push(p);
    used += t;
  }
  if (current.length) batches.push({ chunk: current, offset });
  return batches;
}

/**
 * Envoie un batch de posts à Hermes pour analyse.
 * Retourne uniquement les posts pertinents avec un score et un résumé.
 */
async function analyzeChunk(posts, source, offset = 0) {
  const { semantic_clusters, signals_high_priority, exclude } = loadKeywords();

  const clustersText = (semantic_clusters ?? []).map((c) =>
    `• ${c.theme} : ${c.intent}\n  Exemples de formulations : ${c.synonyms_and_paraphrases.join(", ")}`
  ).join("\n\n");

  const signals = signals_high_priority?.length > 0 ? signals_high_priority.join(", ") : "";
  const excl = exclude?.length > 0 ? exclude.join(", ") : "";

  const postsText = posts
    .map((p, i) => `[${offset + i + 1}] Auteur: ${p.author} | Groupe: ${p.group}\nContenu: ${p.content}`)
    .join("\n\n---\n\n");

  const prompt = `Tu es un assistant d'intelligence commerciale pour Anthony Schoenauer, consultant en gestion de patrimoine internationale chez Equance Vietnam.

Son activité : conseiller les expatriés français en Asie du Sud-Est (Vietnam, Thaïlande) sur la fiscalité non-résident, les investissements (SCPI, assurance-vie luxembourgeoise, private equity, produits structurés), la succession internationale, la protection du conjoint et la retraite.

Source des posts : ${source}

THÈMES À DÉTECTER — utilise ta compréhension sémantique, pas uniquement les mots exacts :

${clustersText}

Signaux prioritaires (score ≥ 8) : ${signals}

À IGNORER absolument : ${excl}

AMBIGUÏTÉS À TRANCHER :
- TOURISTE ≠ RÉSIDENT : Anthony ne cible que les expatriés qui VIVENT (ou vont vivre) en Asie. Un voyageur de passage (vacances, road trip, excursions, itinéraire, croisière, "je repars 3 semaines") n'est JAMAIS pertinent, quel que soit son besoin.
- LA DURÉE DU SÉJOUR NE PROUVE RIEN : "3 semaines" ou "un mois" ne veut pas dire installation — un itinéraire structuré ville par ville (ex: "Hanoï puis Sapa, Ha Giang, Cat Ba, Ninh Binh, avis sur ce circuit ?") est un voyage touristique classique, même long. Seule une phrase qui dit explicitement rester vivre sur place compte.
- "assurance" n'est pertinent que pour la santé, la prévoyance ou l'assurance-vie — JAMAIS pour un véhicule (moto, scooter, voiture), l'habitation ou un voyage.
- "banque" n'est pertinent que pour le placement, l'épargne ou les transferts internationaux — pas pour l'ouverture d'un simple compte courant local.
- Le permis de conduire, les visas et les démarches administratives locales ne concernent jamais Anthony. Une question de visa n'est un signal (faible, score 5-6) que si elle révèle une INSTALLATION durable ou une RETRAITE en Asie.
- "futur_resident_explicite" exige que le post DISE l'installation ("je m'installe", "on déménage à Bangkok", "je prends ma retraite au Vietnam"). "Pourrait indiquer une installation" n'existe pas : dans le doute, statut = "indetermine".
- Ne recopie pas les actions des exemples : rédige une action spécifique au post.

INSTRUCTIONS :
- Raisonne sur le SENS du post, pas sur les mots exacts. Une personne qui écrit "je sais pas quoi faire avec mes économies" exprime le même besoin que "j'ai du cash à placer".
- Ne retiens que les posts où une personne réelle exprime un besoin, une question, un événement de vie ou une préoccupation en lien avec un des thèmes ci-dessus.
- Ignore les posts purement informatifs, les articles partagés, les annonces générales sans signal personnel.
- Pour les signaux forts, score ≥ 8.
- "action" = ce qu'Anthony devrait faire concrètement (ex: "Répondre en privé pour proposer un point patrimonial", "Commenter avec un conseil fiscal", "Contacter en MP"). Anthony est DÉJÀ membre de tous ces groupes : "rejoindre le groupe" n'est JAMAIS une action valide. Trois formes possibles : MP (avec quel angle), commentaire (avec quel conseil), ou veille sans contact.
- Si aucun post n'est pertinent, retourne "relevant": [].

EXEMPLES DE QUALIFICATION — calibre tes scores sur ces cas :

Post : "Bonjour, on arrive à Saigon en septembre avec ma femme et nos deux enfants, je serai en contrat local. Des conseils pour s'installer ?"
→ PERTINENT, score 9 : arrivée imminente = fenêtre idéale pour un bilan patrimonial (résidence fiscale, CFE, scolarité). Action : "MP de bienvenue + proposer un point installation".

Post : "Je vise un visa retraite O-A en Thaïlande pour 2027, quelqu'un a des retours ?"
→ PERTINENT, score 5 : signal FAIBLE — la question porte sur le visa (pas le métier d'Anthony) mais révèle un projet de retraite en Asie, prospect potentiel à moyen terme. Action : "Veille : noter le profil, pas de contact direct".

Post : "Quel visa pour rester 5 mois ? Touriste ou autre ?"
→ NON PERTINENT : question de visa pure, aucun signal patrimonial.

Post : "Salut ! J'ai 23 ans, je repars en Thaïlande 3 semaines en août pour un road trip, des conseils d'itinéraire ?"
→ NON PERTINENT : touriste de passage, pas un résident expatrié.

Post : "Mieux vaut investir dans le S&P 500, la location ici n'est pas rentable une fois les frais payés."
→ NON PERTINENT : cette personne DONNE un avis, elle n'exprime aucun besoin. Un prospect est celui qui DEMANDE, pas celui qui répond.

Post : "Quelqu'un connaît une bonne assurance pas chère pour mon scooter à Saigon ?"
→ NON PERTINENT : assurance véhicule — seules la santé, la prévoyance et l'assurance-vie comptent.

Post : "Nous partons 3 semaines au Vietnam de mi-août à début septembre. Nous atterrissons à Hanoï et y restons 3 jours. Nous pensions aller à Sapa - Ha Giang - Cat Ba - Ninh Binh puis retour à Hanoï. Avis sur ce circuit ?"
→ NON PERTINENT : itinéraire touristique structuré ville par ville pour un séjour de quelques semaines = touriste de passage, même si la durée semble longue. Ne pas confondre "voyage de plusieurs semaines" et "projet de résidence durable".

RÈGLE DE SCORE : 9-10 = événement de vie imminent avec besoin exprimé ; 7-8 = question patrimoniale directe et personnelle ; 5-6 = signal indirect ou projet lointain ; en dessous, ne pas retenir. Ne donne PAS 8 par défaut — la plupart des posts pertinents méritent 5 à 7.

POSTS À ANALYSER :
${postsText}

Réponds UNIQUEMENT en JSON valide, EN FRANÇAIS, sans texte avant ou après :
{
  "relevant": [
    {
      "index": ${offset + 1},
      "reasoning": "ton raisonnement : résident ou touriste ? besoin exprimé ou avis donné ?",
      "statut": "resident_expatrie | futur_resident_explicite | touriste_de_passage | indetermine",
      "besoin": "demande_personnelle | avis_ou_reponse_donnee | annonce_ou_promotion | autre",
      "score": 7,
      "theme": "un thème de la taxonomie",
      "reason": "...",
      "action": "..."
    }
  ],
  "summary": "..."
}`;

  const response = await fetch(`${CONFIG.ollama.baseUrl}/api/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: CONFIG.ollama.model,
      prompt,
      stream: false,
      format: RESPONSE_SCHEMA, // sortie structurée : JSON garanti conforme
      think: true, // qwen3 réfléchit librement AVANT la réponse contrainte — sans ça il régurgite des patterns
      options: { temperature: 0.6, num_ctx: NUM_CTX },
    }),
    signal: AbortSignal.timeout(CONFIG.ollama.timeout),
  });

  if (!response.ok) {
    throw new Error(`Ollama error: ${response.status} ${response.statusText}`);
  }

  const data = await response.json();
  // Avec `format` (sortie structurée), la réponse est du JSON valide garanti.
  const result = JSON.parse(data.response);

  if (process.env.DEBUG_ANALYZER) {
    console.log("\n[DEBUG] relevant brut :", JSON.stringify(result.relevant, null, 2));
  }

  // Filtre déterministe : le modèle CLASSIFIE (statut, besoin), le code DÉCIDE.
  // Un petit modèle contourne les règles en prose ("pourrait indiquer une
  // installation…") ; il ne contourne pas un filtre.
  const kept = (result.relevant ?? []).filter(
    (r) =>
      (r.statut === "resident_expatrie" || r.statut === "futur_resident_explicite") &&
      r.besoin === "demande_personnelle" &&
      r.score >= 5
  );
  const dropped = (result.relevant ?? []).length - kept.length;
  if (dropped > 0) {
    process.stdout.write(chalk.gray(` [${dropped} écarté(s) par le filtre statut/besoin] `));
  }
  result.relevant = kept;
  return result;
}

/**
 * Analyse des profils LinkedIn — contrairement à analyzePosts (qui filtre les
 * posts pertinents), ici on veut un commentaire sur CHAQUE profil : comment
 * l'approcher, et ce qu'il peut apporter (réseau, client potentiel, etc.).
 */
async function analyzeLinkedInChunk(profiles, offset = 0) {
  const profilesText = profiles
    .map((p, i) => `[${offset + i + 1}] ${p.name}\nPoste : ${p.title}\nLieu : ${p.location}\n${p.about ? `Bio : ${p.about}` : ""}`)
    .join("\n\n---\n\n");

  const prompt = `Tu es un assistant d'intelligence commerciale pour Anthony Schoenauer, consultant en gestion de patrimoine internationale chez Equance Vietnam (CIF, courtier assurance, SCPI, assurance-vie Luxembourg, succession, fiscalité non-résident).

Il cible les expatriés français en Asie du Sud-Est (Vietnam, Thaïlande). Pour chaque profil LinkedIn ci-dessous, donne un commentaire concret et réaliste sur :
- comment l'approcher (ex: invitation avec message personnalisé, like + commentaire d'abord, ou prudence si peu pertinent)
- ce que ce contact peut apporter : client potentiel direct, apporteur d'affaires, accès à un réseau d'expatriés, ou faible intérêt

Sois honnête : tous les profils ne sont pas intéressants, certains sont juste "réseau neutre" ou "faible intérêt" — ne survends pas.

PROFILS :
${profilesText}

Réponds UNIQUEMENT en JSON valide, sans texte avant ou après, avec UNE entrée par profil (même les peu intéressants) :
{
  "profiles": [
    {
      "index": ${offset + 1},
      "score": 0,
      "approche": "...",
      "valeur": "..."
    }
  ]
}`;

  const response = await fetch(`${CONFIG.ollama.baseUrl}/api/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: CONFIG.ollama.model,
      prompt,
      stream: false,
      options: { temperature: 0.4, num_ctx: NUM_CTX },
    }),
    signal: AbortSignal.timeout(CONFIG.ollama.timeout),
  });

  if (!response.ok) throw new Error(`Ollama error: ${response.status} ${response.statusText}`);

  const data = await response.json();
  const raw = data.response ?? "";
  const jsonMatch = raw.match(/\{[\s\S]*\}/);
  if (!jsonMatch) return { profiles: [] };

  try {
    return JSON.parse(jsonMatch[0]);
  } catch {
    return { profiles: [] };
  }
}

export async function analyzeLinkedInProfiles(profiles) {
  if (profiles.length === 0) return { profiles: [] };

  const CHUNK = 6;
  const batches = [];
  for (let i = 0; i < profiles.length; i += CHUNK) {
    batches.push({ chunk: profiles.slice(i, i + CHUNK), offset: i });
  }

  const all = [];
  for (let b = 0; b < batches.length; b++) {
    const { chunk, offset } = batches[b];
    process.stdout.write(chalk.cyan(`  Lot ${b + 1}/${batches.length}...`));
    let result = null;
    for (let attempt = 1; attempt <= 2 && !result; attempt++) {
      try {
        result = await analyzeLinkedInChunk(chunk, offset);
      } catch (err) {
        if (attempt === 1) {
          process.stdout.write(chalk.yellow(` erreur (${err.message}), nouvelle tentative...`));
        } else {
          process.stdout.write(chalk.red(` échec définitif: ${err.message}\n`));
        }
      }
    }
    if (result) {
      all.push(...(result.profiles ?? []));
      process.stdout.write(chalk.green(` ${result.profiles?.length ?? 0} commentés\n`));
    }
  }

  return { profiles: all };
}

const GROUP_MATCH_SCHEMA = {
  type: "object",
  properties: {
    match_index: { type: "integer" },
    confidence: { type: "string", enum: ["haute", "moyenne", "faible", "aucune"] },
    reasoning: { type: "string" },
  },
  required: ["match_index", "confidence", "reasoning"],
};

/**
 * Fail-safe de repointage WhatsApp : quand un groupe configuré n'est plus
 * trouvable ni par JID ni par nom exact/partiel (renommage, groupe déplacé ou
 * recréé), demande à qwen de repérer le candidat le plus probable parmi les
 * conversations actuellement visibles — pour ne pas perdre le groupe en
 * silence à chaque run tant qu'Anthony n'a pas corrigé groups.json à la main.
 */
export async function resolveGroupCandidate(candidateNames, configName, lastKnownName) {
  if (candidateNames.length === 0) {
    return { match_index: -1, confidence: "aucune", reasoning: "Aucun candidat visible." };
  }

  const list = candidateNames.map((n, i) => `${i + 1}. ${n}`).join("\n");

  const prompt = `Tu aides à retrouver un groupe WhatsApp qui a probablement été renommé, déplacé ou recréé.

Nom configuré à l'origine : "${configName}"
Dernier nom connu du groupe : "${lastKnownName || configName}"

Conversations actuellement visibles dans WhatsApp Web :
${list}

Un groupe WhatsApp peut changer de nom (emoji ajoutés/retirés, mots réordonnés, traduction, abréviation) sans être un autre groupe. Ta tâche : identifier, parmi la liste, le SEUL candidat qui est probablement LE MÊME groupe que "${lastKnownName || configName}" — pas juste un groupe thématiquement proche (ex: un autre groupe d'expatriés sans lien).

En cas de doute réel entre plusieurs candidats plausibles, ou si aucun ne ressemble vraiment, préfère "faible"/"aucune" plutôt que de deviner.

Réponds UNIQUEMENT en JSON valide :
{
  "match_index": 0,
  "confidence": "haute | moyenne | faible | aucune",
  "reasoning": "..."
}
Utilise match_index = -1 si aucun candidat n'est plausible.`;

  const response = await fetch(`${CONFIG.ollama.baseUrl}/api/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: CONFIG.ollama.model,
      prompt,
      stream: false,
      format: GROUP_MATCH_SCHEMA,
      think: true,
      options: { temperature: 0.3, num_ctx: NUM_CTX },
    }),
    signal: AbortSignal.timeout(CONFIG.ollama.timeout),
  });

  if (!response.ok) throw new Error(`Ollama error: ${response.status} ${response.statusText}`);

  const data = await response.json();
  return JSON.parse(data.response);
}

export async function analyzePosts(posts, source = "facebook") {
  if (posts.length === 0) return { relevant: [], total_analyzed: 0, summary: "Aucun post." };

  const batches = buildBatches(posts);

  console.log(chalk.gray(`  ${posts.length} posts → ${batches.length} batch(es), budget ${BATCH_TOKEN_BUDGET} tokens/batch`));

  const allRelevant = [];
  let totalSummaries = [];

  for (let b = 0; b < batches.length; b++) {
    const { chunk, offset } = batches[b];
    process.stdout.write(chalk.cyan(`  Batch ${b + 1}/${batches.length}...`));

    // Un petit modèle local à température 0.6 est bruyant sur les cas limites :
    // un même post pertinent peut être retenu ou raté selon le tirage (constaté
    // en pratique : des prospects réels absents un run sur deux). Deux passes
    // indépendantes fusionnées par union (max du score en cas de doublon)
    // récupèrent la plupart de ces posts qui "clignotent" — coût nul, le
    // modèle tourne en local.
    const merged = new Map();
    for (let pass = 1; pass <= 2; pass++) {
      // Deux tentatives par passe : les timeouts du modèle local sont souvent
      // transitoires, et un batch perdu = des prospects perdus en silence.
      let result = null;
      for (let attempt = 1; attempt <= 2 && !result; attempt++) {
        try {
          result = await analyzeChunk(chunk, source, offset);
        } catch (err) {
          if (attempt === 1) {
            process.stdout.write(chalk.yellow(` erreur (${err.message}), nouvelle tentative...`));
          } else {
            process.stdout.write(chalk.red(` échec définitif: ${err.message}\n`));
          }
        }
      }
      if (result) {
        for (const r of result.relevant ?? []) {
          const prior = merged.get(r.index);
          if (!prior || prior.score < r.score) merged.set(r.index, r);
        }
        if (result.summary) totalSummaries.push(result.summary);
      }
    }
    const relevant = [...merged.values()];
    allRelevant.push(...relevant);
    process.stdout.write(chalk.green(` ${relevant.length} pertinents (2 passes fusionnées)\n`));
  }

  return {
    relevant: allRelevant,
    total_analyzed: posts.length,
    summary: totalSummaries.join(" | "),
  };
}
