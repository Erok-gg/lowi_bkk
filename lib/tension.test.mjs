/**
 * Vérification de la révision du 2026-07-28 : la tension ne doit plus
 * récompenser les marchés minuscules.
 *
 * Lancer :
 *   npx esbuild lib/tension.ts --bundle --format=esm --outfile=lib/tension.compiled.mjs
 *   node lib/tension.test.mjs
 *   rm lib/tension.compiled.mjs
 */
import { computeTensionByKhet } from "./tension.compiled.mjs";

const jour = 86_400_000;
const now = Date.now();

/** Fabrique n annonces actives réparties sur `condos` immeubles. */
function annonces(khet, n, condos, dealType = "sale") {
  return Array.from({ length: n }, (_, i) => ({
    khet,
    street: null,
    dealType,
    status: "active",
    firstSeen: new Date(now - 30 * jour).toISOString(),
    delistedAt: null,
    condoName: `${khet}-immeuble-${i % condos}`,
  }));
}

// Centre : gros marché, 3 annonces par immeuble.
// Périphérie : marché minuscule (le cas qui faussait tout).
// Marché mou : beaucoup de vendeurs par immeuble.
const inputs = [
  ...annonces("Centre", 300, 100),
  ...annonces("Peripherie", 3, 3),
  ...annonces("Mou", 120, 12),
];

const rows = computeTensionByKhet(inputs, [], "sale", now);
for (const r of rows.sort((a, b) => (b.tensionScore ?? -1) - (a.tensionScore ?? -1))) {
  console.log(
    `${r.khet.padEnd(12)} actives=${String(r.nActive).padStart(4)} ` +
      `immeubles=${String(r.nCondos).padStart(3)} ` +
      `pression=${String(r.supplyPressure ?? "—").padStart(5)} ` +
      `score=${r.tensionScore ?? "non publié"}`
  );
}

const peri = rows.find((r) => r.khet === "Peripherie");
const mou = rows.find((r) => r.khet === "Mou");
const centre = rows.find((r) => r.khet === "Centre");

console.log("\nVérifications :");
console.log(
  `  périphérie (3 annonces) non publiée .......... ${peri.tensionScore === null ? "OK" : "ÉCHEC"}`
);
console.log(
  `  marché mou moins tendu que le centre ......... ${
    (mou.tensionScore ?? 0) < (centre.tensionScore ?? 0) ? "OK" : "ÉCHEC"
  }`
);
console.log(
  `  pression vendeuse calculée ................... ${
    centre.supplyPressure === 3 && mou.supplyPressure === 10 ? "OK" : "ÉCHEC"
  }`
);
