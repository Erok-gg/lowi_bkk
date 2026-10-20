/**
 * theme.ts — Source UNIQUE de vérité pour la palette.
 * Pour changer le look du site : modifier ici. Tailwind (tailwind.config.ts)
 * et le style de carte (map-style.json via getMapColors) lisent ces valeurs.
 *
 * Palette : anthracite (fond) + violet fluo (accents) + violet sombre (surfaces)
 * + touches de bleu ; jaune réservé au glow de survol des quartiers.
 */
export const theme = {
  colors: {
    // Fonds
    anthracite: "#15151c", // fond principal
    anthraciteDeep: "#0d0d12", // fond le plus sombre (carte, derrière tout)
    surface: "#1d1830", // surfaces / panneaux (violet sombre)
    surfaceRaised: "#272040", // cartes/éléments surélevés

    // Accents
    violet: "#7c3aed", // violet principal
    violetFluo: "#b026ff", // violet fluo (accents vifs, CTA)
    violetSoft: "#3b2a5c", // violet sombre désaturé (bordures discrètes)
    blue: "#3b82f6", // touches de bleu (liens, eau)
    blueDeep: "#1e3a5f", // bleu sombre (eau sur la carte)

    // Marque Lowi (accent premium sur fond sombre)
    gold: "#c9a84c",
    goldLight: "#e8c97a",

    // Interaction
    glow: "#ffd60a", // jaune — glow de survol quartier (réservé)

    // Texte
    text: "#ece9f5",
    textMuted: "#9b94b3",
    textFaint: "#6b6485",

    // États
    success: "#34d399",
    warning: "#fbbf24",
    danger: "#f87171",
  },
} as const;

/** Couleurs exposées au style MapLibre (eau, rues, quartiers, glow...). */
export function getMapColors() {
  const c = theme.colors;
  return {
    background: c.anthraciteDeep,
    water: c.blueDeep,
    road: "#2a2740",
    roadMajor: "#3a3656",
    building: "#1b1828",
    parkGreen: "#1c2a1f",
    districtFill: "rgba(124, 58, 237, 0.06)",
    districtFillHover: "rgba(176, 38, 255, 0.14)",
    districtLine: c.violetSoft,
    districtLineHover: c.glow,
    label: c.textMuted,
    labelHalo: c.anthraciteDeep,
    metro: c.violetFluo,
    poi: c.blue,
  };
}

export type Theme = typeof theme;

/* ───────────────────────────────────────────────────────────────────────────
   Thème « Ledger » — vert / or / blanc, pour le bilan acheteur
   ───────────────────────────────────────────────────────────────────────────

   Dérivé du système de design du pitch (`lowi-th/Design-ledger.md`, 2026-10-14) :
   mêmes RÔLES de jetons (fond / surface / creux / encre / filet / accent), même
   discipline « positif et négatif diffèrent aussi en luminosité ». Seules les
   teintes changent : l'accent violet devient VERT, et l'or quitte les surfaces
   pour ne tenir que les FILETS ET LES BORDS (demande du 2026-10-20).

   Pourquoi deux ors et pas un. `#C9A84C` est la couleur de marque : sur fond
   blanc il plafonne à 2,2:1 de contraste — illisible en texte. Il reste donc
   sur les bords et les fonds de bouton (où le texte est sombre, 8,9:1), et le
   texte or passe par `gold-ink` `#86681E` (5,0:1). Même raison pour `faint` :
   la valeur claire du Ledger (`#7A808C`, 3,9:1) ne passe pas en 11 px, d'où
   `#616E65` (4,8:1).

   Le mécanisme : les couleurs Tailwind ne sont plus des hex mais
   `rgb(var(--c-<jeton>) / <alpha-value>)`. `:root` porte les valeurs sombres
   (identiques à l'existant — la carte et les tableaux ne bougent pas), et la
   classe `.theme-ledger` les redéfinit en clair sur son sous-arbre. Changer de
   thème = poser ou retirer une classe (règle 7 : le chemin du retour).
*/

/** Jetons sémantiques — le vocabulaire du Ledger, indépendant de la teinte. */
const SOMBRE = {
  page: "#0d0d12", // fond de page
  sunken: "#15151c", // creux (pistes, en-têtes, placeholders)
  surface: "#1d1830", // carte / panneau
  "surface-raised": "#272040",
  rule: "#3b2a5c", // filet
  "rule-strong": "#4c3a70", // filet appuyé
  ink: "#ece9f5", // texte
  muted: "#9b94b3", // texte secondaire
  faint: "#6b6485", // texte tertiaire
  brand: "#b026ff", // accent vif (CTA, état actif)
  "brand-deep": "#7c3aed", // accent principal
  "brand-soft": "#3b2a5c", // fond d'accent
  gold: "#c9a84c", // marque — fonds de bouton, bords
  "gold-ink": "#c9a84c", // or en texte
  "gold-line": "#c9a84c", // or en filet
  // Encre posée SUR l'or (bouton PDF). Identique dans les deux thèmes : à
  // 8,9:1 sur #c9a84c elle passe, là où l'encre du thème ne passerait pas
  // (texte clair sur or = 2,4:1).
  "on-gold": "#16131f",
  pos: "#34d399",
  neg: "#f87171",
  warn: "#fbbf24",
  info: "#93c5fd",
} as const;

/** Les mêmes rôles en vert / or / blanc. */
const LEDGER = {
  page: "#fafaf6",
  sunken: "#f1f3ed",
  surface: "#ffffff",
  "surface-raised": "#f7f8f3",
  rule: "#e0d1a6", // or clair : le filet ordinaire
  "rule-strong": "#c9a84c", // or de marque : le bord appuyé
  ink: "#11201a", // encre verte très sombre (15,8:1 sur blanc)
  muted: "#4b584f", // 7,7:1
  faint: "#616e65", // 4,8:1 — tient en 11 px
  brand: "#1c6b47", // vert (5,3:1)
  "brand-deep": "#125036",
  "brand-soft": "#e7f0ea",
  gold: "#c9a84c",
  "gold-ink": "#86681e", // 5,0:1
  "gold-line": "#c9a84c",
  "on-gold": "#16131f",
  pos: "#1e6b57",
  neg: "#b0452e",
  warn: "#8a6b1f",
  info: "#1f5e7a",
} as const;

/** Jetons hérités (carte, tableaux) : mêmes noms qu'avant, repris sur le thème. */
function heritage(j: Record<string, string>, c: typeof theme.colors, sombre: boolean) {
  return {
    anthracite: j.sunken,
    "anthracite-deep": j.page,
    surface: j.surface,
    "surface-raised": j["surface-raised"],
    violet: j["brand-deep"],
    "violet-fluo": j.brand,
    "violet-soft": j.rule,
    blue: j.info,
    "blue-deep": c.blueDeep,
    "gold-light": c.goldLight,
    // Le glow jaune est reserve au survol des quartiers sur la carte (theme
    // sombre). En clair il n'a pas de role : il retombe sur l'or de marque.
    glow: sombre ? c.glow : j.gold,
    text: j.ink,
    "text-muted": j.muted,
    "text-faint": j.faint,
  };
}

/**
 * Noms de jetons exposés à Tailwind, dans l'ordre de déclaration.
 *
 * ⚠ Un nom de couleur ne doit JAMAIS coïncider avec un utilitaire Tailwind
 * existant. Défaut mesuré le 2026-10-20 : le jeton s'appelait `base`, Tailwind
 * émettait donc `.text-base{color:…}` À CÔTÉ de `.text-base{font-size:1rem}`,
 * et la couleur gagnait à l'ordre — tous les titres de bloc du bilan sont
 * passés en blanc sur blanc. Renommé `page`. Même vigilance pour toute échelle
 * de taille (`sm`, `lg`, `xl`…) ou de graisse.
 */
export const JETONS = Object.keys({ ...SOMBRE, ...heritage(SOMBRE, theme.colors, true) });

/** "#1d1830" → "29 24 48" (canaux, pour `rgb(var(--x) / <alpha>)`). */
function canaux(hex: string): string {
  const h = hex.replace("#", "");
  const n = h.length === 3 ? h.split("").map((x) => x + x).join("") : h;
  return [0, 2, 4].map((i) => parseInt(n.slice(i, i + 2), 16)).join(" ");
}

function bloc(selecteur: string, j: Record<string, string>, sombre: boolean): string {
  const tout = { ...j, ...heritage(j, theme.colors, sombre) };
  const lignes = Object.entries(tout).map(([k, v]) => `--c-${k}:${canaux(v)}`);
  return `${selecteur}{${lignes.join(";")}}`;
}

/**
 * Le CSS des jetons, injecté une fois par le layout.
 *
 * Il est GÉNÉRÉ ici plutôt que recopié dans `globals.css` : les deux jeux
 * auraient dérivé (ce dépôt a déjà payé une divergence fichiers↔serveur de
 * 4 vues le 2026-08-20). Coût mesurable : ~1,6 ko inline par page, ~0,5 ko
 * compressé — à comparer au risque d'un thème qui ne dit pas la vérité.
 */
export function cssTokens(): string {
  return [bloc(":root", SOMBRE, true), bloc(".theme-ledger", LEDGER, false)].join("");
}

export const palettes = { sombre: SOMBRE, ledger: LEDGER } as const;
