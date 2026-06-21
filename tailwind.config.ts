import type { Config } from "tailwindcss";
import { theme } from "./config/theme";

const c = theme.colors;

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./config/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        anthracite: c.anthracite,
        "anthracite-deep": c.anthraciteDeep,
        surface: c.surface,
        "surface-raised": c.surfaceRaised,
        violet: c.violet,
        "violet-fluo": c.violetFluo,
        "violet-soft": c.violetSoft,
        blue: c.blue,
        "blue-deep": c.blueDeep,
        gold: c.gold,
        "gold-light": c.goldLight,
        glow: c.glow,
        text: c.text,
        "text-muted": c.textMuted,
        "text-faint": c.textFaint,
      },
      boxShadow: {
        glow: `0 0 12px ${c.glow}, 0 0 4px ${c.glow}`,
        "violet-glow": `0 0 16px ${c.violetFluo}55`,
      },
    },
  },
  plugins: [],
};

export default config;
