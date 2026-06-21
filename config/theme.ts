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
