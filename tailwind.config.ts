import type { Config } from "tailwindcss";
import { theme, JETONS } from "./config/theme";

const c = theme.colors;

/**
 * Couleurs pilotées par variables CSS, pas par hex.
 *
 * `rgb(var(--c-x) / <alpha-value>)` garde les opacités Tailwind (`bg-gold/40`)
 * tout en laissant un sous-arbre redéfinir le jeu complet — c'est ce qui permet
 * à `.theme-ledger` (vert/or/blanc, pages du bilan acheteur) de coexister avec
 * le thème sombre de la carte sans dupliquer une classe. Les valeurs vivent
 * dans `config/theme.ts` (`cssTokens()`), injectées par le layout ; `:root`
 * porte exactement les hex d'avant, donc la carte et les tableaux ne bougent pas.
 */
const couleurs = Object.fromEntries(
  JETONS.map((j) => [j, `rgb(var(--c-${j}) / <alpha-value>)`]),
);

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./config/**/*.{ts,tsx}",
    "./bilan_RE/web/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: couleurs,
      boxShadow: {
        glow: `0 0 12px ${c.glow}, 0 0 4px ${c.glow}`,
        "violet-glow": `0 0 16px ${c.violetFluo}55`,
        // Halo de l'accent courant (vert en thème Ledger, violet en sombre).
        "brand-glow": "0 0 16px rgb(var(--c-brand) / 0.33)",
        "gold-glow": "0 0 24px rgb(var(--c-gold) / 0.45)",
      },
      fontFamily: {
        // Le Ledger impose UNE police de texte et UNE police de données.
        // Chargées par `app/beta/layout.tsx` (next/font, auto-hébergées) et
        // exposées en variables CSS pour ne pas dépendre d'un poste.
        sans: ["var(--police-texte)", "ui-sans-serif", "system-ui", "sans-serif"],
        data: ["var(--police-donnees)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
