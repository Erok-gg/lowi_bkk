/**
 * Extraction structurée des annonces immobilières Bangkok collectées sur Facebook.
 * Alimente le projet Lowi_bkk (recherche d'opportunités d'investissement).
 *
 * Principe (cf. cours 2) : le MODÈLE comprend le texte libre bilingue thaï/anglais
 * et remplit un schéma imposé ; le CODE décide ensuite quoi garder. Une annonce =
 * un appel (200-400 tokens) : c'est rapide et ça évite toute contamination entre
 * annonces, défaut constaté quand on groupe les posts.
 *
 * Usage : node immo-extract.mjs [fichier.json] [nbMax]
 */
import { readFileSync, writeFileSync } from "fs";
import { CONFIG } from "./config.js";

const file = process.argv[2] ?? "output/immo_facebook_2026-07-25.json";
const limit = parseInt(process.argv[3] ?? "0", 10);

// ─── Schéma imposé à Ollama ─────────────────────────────────────────────────
// TYPES SIMPLES UNIQUEMENT : les unions ["integer","null"] produisent une
// grammaire de contrainte défaillante côté llama.cpp — la génération part en
// boucle et ne s'arrête plus. Convention : 0 (nombres) et "" (texte) = absent.
// Montants demandés en BAHTS ENTIERS pour éviter que le modèle jongle entre
// "13.5 ล้าน", "60K" et "18,000".
const SCHEMA = {
  type: "object",
  properties: {
    est_une_annonce: { type: "boolean" },
    type_transaction: { type: "string", enum: ["vente", "location", "vente_et_location", "recherche", "autre"] },
    type_bien: { type: "string", enum: ["condo", "maison", "townhouse", "terrain", "commerce", "inconnu"] },
    prix_vente_thb: { type: "integer" },
    loyer_mensuel_thb: { type: "integer" },
    surface_sqm: { type: "integer" },
    chambres: { type: "integer" },
    salles_de_bain: { type: "integer" },
    nom_immeuble: { type: "string" },
    station_proche: { type: "string" },
    quartier: { type: "string" },
    meuble: { type: "boolean" },
    vendeur: { type: "string", enum: ["proprietaire", "agent", "inconnu"] },
    // Quota étranger : en Thaïlande un étranger ne peut détenir en pleine
    // propriété que dans la limite de 49 % de la surface d'un immeuble. Une
    // annonce sans quota étranger disponible est inachetable en direct.
    quota: { type: "string", enum: ["etranger", "thai", "inconnu"] },
    confiance: { type: "integer", minimum: 1, maximum: 5 },
  },
  required: [
    "est_une_annonce", "type_transaction", "type_bien",
    "prix_vente_thb", "loyer_mensuel_thb", "surface_sqm", "chambres",
    "salles_de_bain", "nom_immeuble", "station_proche", "quartier",
    "meuble", "vendeur", "quota", "confiance",
  ],
};

const PROMPT = (texte) => `Tu extrais les données d'une annonce immobilière publiée dans un groupe Facebook de Bangkok. Le texte est en thaï, en anglais ou les deux, souvent incomplet et mal structuré.

RÈGLES DE CONVERSION DES MONTANTS — tous les prix sont en bahts thaïlandais (THB), à convertir en ENTIER :
- "13.5 ล้าน" ou "13.5 million" ou "13.5M" = 13500000
- "60K" ou "60k" = 60000
- "18,000" = 18000
- "98,000บาท/เดือน" = loyer mensuel de 98000
- Un prix de VENTE est en millions ; un LOYER est en milliers par mois. Si un
  montant de 15 000 est annoncé sans précision, c'est un loyer mensuel.

VOCABULAIRE THAÏ UTILE :
- ขาย = vendre / à vendre · ให้เช่า ou เช่า = à louer · ขายหรือให้เช่า = vente OU location
- ราคาขาย = prix de vente · ราคาเช่า = prix de location · บาท = baht · เดือน = mois
- ห้องนอน = chambre · ห้องน้ำ = salle de bain · ตรม. ou ตร.ม. = m²
- เจ้าของขายเอง ou เจ้าของ = par le propriétaire directement
- คอนโด = condo · บ้านเดี่ยว = maison individuelle · ทาวน์เฮาส์ = townhouse
- โครงการ = nom du projet/résidence · ต้องการหา = recherche (demande, pas une offre)
- โควตาต่างชาติ ou โควต้าต่างชาติ = quota ÉTRANGER (foreign quota) · โควตาไทย = quota thaï

CONSIGNES :
- "est_une_annonce" est faux si le texte ne propose ni ne cherche un bien (discussion, publicité de service, question générale).
- "type_transaction" : par défaut une annonce est une OFFRE. Dès qu'un bien est DÉCRIT (nom d'immeuble, surface, prix, "For Rent", "ให้เช่า", "ขาย"), c'est "location" ou "vente" — JAMAIS "recherche", même si l'annonce est courte ou tronquée.
  N'utilise "recherche" QUE si l'auteur cherche un logement POUR LUI : "looking for", "I need a condo", "ต้องการหา", "budget around 20k", "wanted".
  Exemples :
  · "Skyrise Avenue Sukhumvit 64 [For Rent] ใกล้ BTS ปุณณวิถี" → location (c'est une offre)
  · "Q Chidlom 1 Bed 2 Bath 73 sq.m 48,000 B" → location (offre, loyer mensuel)
  · "ขายคอนโด Supalai Icon Sathorn 13.5 ล้านบาท" → vente
  · "Hello! I'm looking for an apartment for 2 people, budget around 17000" → recherche
- "nom_immeuble" : recopie le nom du projet tel qu'écrit, sans traduire (ex. "Noble Revolve Ratchada 2", "Supalai Icon Sathorn"). null si absent.
- "station_proche" : la station BTS/MRT citée (ex. "BTS Ekkamai", "MRT Lat Phrao"). "" si absente.
- "quota" : "etranger" si l'annonce mentionne un quota étranger (โควตาต่างชาติ, "foreign quota", "foreign freehold", "farang quota") ; "thai" si elle précise un quota thaï ; "inconnu" dans TOUS les autres cas. Ne déduis jamais le quota de l'absence d'information.
- N'INVENTE JAMAIS une valeur absente : mets 0 pour un nombre, "" pour un texte. Une annonce tronquée est normale.
- "confiance" : 5 = tout est explicite ; 1 = texte très pauvre ou ambigu.

ANNONCE :
${texte}

Réponds uniquement en JSON conforme au schéma.`;

async function extract(post) {
  const res = await fetch(`${CONFIG.ollama.baseUrl}/api/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: CONFIG.ollama.model,
      prompt: PROMPT(post.content),
      stream: false,
      format: SCHEMA,
      // Pas de mode réflexion : l'extraction est de la transcription, pas du
      // jugement. Le think n'apporte rien ici et multiplie le temps de calcul.
      think: false,
      options: { temperature: 0.2, num_ctx: 4096 },
    }),
    signal: AbortSignal.timeout(CONFIG.ollama.timeout),
  });
  if (!res.ok) throw new Error(`Ollama ${res.status}`);
  const data = await res.json();
  return JSON.parse(data.response);
}

// ─── Décision côté CODE : qui publie ? ──────────────────────────────────────
// Le modèle répondait "propriétaire" par défaut, y compris pour "Serenity
// Estate" ou "Happy Homes". Or ce champ a des marqueurs textuels nets : c'est
// donc au code de trancher, le modèle ne servant que de dernier recours.
const MARQ_PROPRIO = /เจ้าของ|owner\s*(post|direct)?|by\s*owner|ไม่ผ่านนายหน้า|no\s*agent|direct\s*from\s*owner/i;
const MARQ_AGENT = /\b(agent|agency|realty|real\s*estate|property|properties|estate|homes|broker)\b|นายหน้า|บริษัท/i;

// ─── Décision côté CODE : quota étranger ────────────────────────────────────
// Champ décisif pour un acheteur étranger (limite légale de 49 % de la surface
// d'un immeuble détenue par des non-Thaïs) et à marqueurs textuels nets : le
// code tranche, le modèle ne sert que de confirmation.
const MARQ_QUOTA_ETR = /โควต[า้]?\s*ต่างชาติ|foreign(er)?\s*quota|foreign\s*(free\s*hold|freehold)|farang\s*quota|quota\s*ét?ranger/i;
const MARQ_QUOTA_THAI = /โควต[า้]?\s*ไทย|thai\s*quota|thai\s*name|ชื่อคนไทย/i;

function deduireQuota(post, valeurModele) {
  const t = `${post.author ?? ""} ${post.content ?? ""}`;
  if (MARQ_QUOTA_ETR.test(t)) return "etranger";
  if (MARQ_QUOTA_THAI.test(t)) return "thai";
  // Sans marqueur, on n'invente pas : le modèle a pu halluciner un quota.
  return "inconnu";
}

function deduireVendeur(post, valeurModele) {
  const auteur = post.author ?? "";
  const texte = post.content ?? "";
  // Le nom de l'auteur est le signal le plus fiable : les agences se nomment
  // "… Property", "… Estate", "… Homes".
  if (MARQ_AGENT.test(auteur)) return "agent";
  if (MARQ_PROPRIO.test(texte)) return "proprietaire";
  if (MARQ_AGENT.test(texte)) return "agent";
  return valeurModele === "proprietaire" ? "inconnu" : valeurModele; // prudence
}

const posts = JSON.parse(readFileSync(file, "utf-8")).posts;
const cible = limit > 0 ? posts.slice(0, limit) : posts;
console.log(`${cible.length} annonce(s) à extraire (${CONFIG.ollama.model})\n`);

const out = [];
for (let i = 0; i < cible.length; i++) {
  const p = cible[i];
  process.stdout.write(`[${i + 1}/${cible.length}] ${p.author.slice(0, 20)}… `);
  try {
    const d = await extract(p);
    // Le code tranche sur les deux champs à marqueurs nets, pas le modèle
    d.vendeur = deduireVendeur(p, d.vendeur);
    d.quota = deduireQuota(p, d.quota);
    out.push({ ...d, auteur: p.author, date: p.date, lien: p.link, groupe: p.group, texte: p.content });
    const prix = d.prix_vente_thb ? `${(d.prix_vente_thb / 1e6).toFixed(2)}M฿` : d.loyer_mensuel_thb ? `${d.loyer_mensuel_thb}฿/m` : "—";
    const flags = [d.vendeur === "proprietaire" ? "PROPRIO" : null, d.quota === "etranger" ? "QUOTA-ÉTR" : null].filter(Boolean).join(" ");
    console.log(`${d.est_une_annonce ? d.type_transaction : "NON-ANNONCE"} | ${prix} | ${d.nom_immeuble ?? "?"} ${flags ? "| " + flags : ""}`);
  } catch (err) {
    console.log(`échec : ${err.message}`);
  }
}

const dest = file.replace(/\.json$/, "_extrait.json");
writeFileSync(dest, JSON.stringify(out, null, 2), "utf-8");
console.log(`\n✓ ${out.length} extraction(s) → ${dest}`);
