/**
 * Tests de l'indice de tension.
 *
 * Lancer : `npm test`
 *
 * L'ancienne version de ce fichier importait `./tension.compiled.mjs`, un
 * artefact qu'il fallait produire à la main avec esbuild — absent du dépôt et
 * absent des dépendances. Le test ne pouvait donc plus tourner. Pire, il
 * imprimait « OK » ou « ÉCHEC » sans jamais sortir en code ≠ 0 : même réparé,
 * il n'aurait rien pu garder. Il utilise désormais `node:test`, exécuté par
 * `tsx` (déjà en devDependency), et un échec fait échouer la commande.
 */
import test from "node:test";
import assert from "node:assert/strict";
import {
  computeTensionByKhet,
  MIN_ACTIVE_TO_PUBLISH,
  DELISTING_FIX_DATE,
  type TensionInput,
} from "./tension";

const JOUR = 86_400_000;
const now = Date.now();

/** n annonces actives réparties sur `condos` immeubles. */
function annonces(
  khet: string,
  n: number,
  condos: number,
  dealType: TensionInput["dealType"] = "sale"
): TensionInput[] {
  return Array.from({ length: n }, (_, i) => ({
    khet,
    street: null,
    dealType,
    status: "active" as const,
    firstSeen: new Date(now - 30 * JOUR).toISOString(),
    delistedAt: null,
    condoName: `${khet}-immeuble-${i % condos}`,
  }));
}

/** n annonces délistées à `quandIso`, sur des immeubles qui leur sont propres. */
function delistees(khet: string, n: number, quandIso: string): TensionInput[] {
  return Array.from({ length: n }, (_, i) => ({
    khet,
    street: null,
    dealType: "sale" as const,
    status: "inactive" as const,
    firstSeen: new Date(now - 60 * JOUR).toISOString(),
    delistedAt: quandIso,
    condoName: `${khet}-immeuble-disparu-${i}`,
  }));
}

const parKhet = <T extends { khet: string }>(rows: T[], khet: string): T =>
  rows.find((r) => r.khet === khet)!;

test("un marché minuscule n'est pas publié plutôt que d'être dit tendu", () => {
  const rows = computeTensionByKhet(
    [...annonces("Centre", 300, 100), ...annonces("Peripherie", 3, 3)],
    [],
    "sale",
    now
  );
  assert.equal(parKhet(rows, "Peripherie").tensionScore, null);
  assert.notEqual(parKhet(rows, "Centre").tensionScore, null);
  assert.ok(3 < MIN_ACTIVE_TO_PUBLISH, "le cas de test doit rester sous le seuil");
});

test("beaucoup de vendeurs par immeuble = marché mou, donc moins tendu", () => {
  const rows = computeTensionByKhet(
    [...annonces("Centre", 300, 100), ...annonces("Mou", 120, 12)],
    [],
    "sale",
    now
  );
  const centre = parKhet(rows, "Centre");
  const mou = parKhet(rows, "Mou");
  assert.equal(centre.supplyPressure, 3);
  assert.equal(mou.supplyPressure, 10);
  assert.ok(
    mou.tensionScore! < centre.tensionScore!,
    `attendu mou (${mou.tensionScore}) < centre (${centre.tensionScore})`
  );
});

test("le dénominateur ignore les annonces délistées (régression 2026-07-28)", () => {
  // 100 actives sur 10 immeubles = 10 par immeuble. Les 40 délistées portent des
  // noms d'immeubles qui leur sont propres : les compter ferait tomber la
  // pression à 2, donc grimper la tension d'un quartier à fort churn.
  const rows = computeTensionByKhet(
    [
      ...annonces("Churn", 100, 10),
      ...delistees("Churn", 40, new Date(now - 5 * JOUR).toISOString()),
    ],
    [],
    "sale",
    now
  );
  const churn = parKhet(rows, "Churn");
  assert.equal(churn.nCondos, 10, "seuls les immeubles des actives comptent");
  assert.equal(churn.supplyPressure, 10);
});

test("un immeuble reste un immeuble quelle que soit l'écriture du nom", () => {
  const variantes = ["The Base Sukhumvit 77", "The Base Sukhumvit 77, Bangkok", "the base sukhumvit 77"];
  const inputs: TensionInput[] = Array.from({ length: 30 }, (_, i) => ({
    khet: "Test",
    street: null,
    dealType: "sale" as const,
    status: "active" as const,
    firstSeen: new Date(now - 10 * JOUR).toISOString(),
    delistedAt: null,
    condoName: variantes[i % variantes.length],
  }));
  const row = parKhet(computeTensionByKhet(inputs, [], "sale", now), "Test");
  assert.equal(row.nCondos, 1, "les trois écritures désignent le même immeuble");
});

test("le time-on-market écarte par défaut l'historique d'avant le correctif", () => {
  const avant = new Date(Date.parse(DELISTING_FIX_DATE) - 10 * JOUR).toISOString();
  const apres = new Date(Date.parse(DELISTING_FIX_DATE) + 10 * JOUR).toISOString();

  const contamine = parKhet(
    computeTensionByKhet(
      [...annonces("K", 50, 10), ...delistees("K", 12, avant)],
      [], "sale", now
    ),
    "K"
  );
  assert.equal(contamine.nDelisted, 0, "les disparitions pré-correctif sont ignorées");
  assert.equal(contamine.medianTomDays, null, "donc pas de time-on-market");

  const propre = parKhet(
    computeTensionByKhet(
      [...annonces("K", 50, 10), ...delistees("K", 12, apres)],
      [], "sale", now
    ),
    "K"
  );
  assert.equal(propre.nDelisted, 12);
  assert.ok(propre.medianTomDays! > 0, "le TOM revient dès que l'historique est propre");

  // L'appelant peut réintégrer explicitement l'historique contaminé.
  const force = parKhet(
    computeTensionByKhet(
      [...annonces("K", 50, 10), ...delistees("K", 12, avant)],
      [], "sale", now, { reliableDelistingSince: null }
    ),
    "K"
  );
  assert.equal(force.nDelisted, 12);
});

test("le momentum prix suit la médiane, pas la moyenne", () => {
  // Médiane stable, moyenne en forte hausse (un penthouse entre dans le stock) :
  // l'indice ne doit pas y voir un marché qui s'apprécie.
  const snaps = [0, 7, 14, 21].map((j) => ({
    takenAt: new Date(now - (21 - j) * JOUR).toISOString(),
    khet: "K",
    dealType: "sale" as const,
    activeCount: 50,
    avgPricePerSqm: 100_000 + j * 5_000,
    medianPricePerSqm: 100_000,
  }));
  const row = parKhet(computeTensionByKhet(annonces("K", 50, 10), snaps, "sale", now), "K");
  assert.equal(row.priceMomentum, 0, "médiane plate → momentum nul");

  const sansMediane = snaps.map((s) => ({ ...s, medianPricePerSqm: null }));
  const repli = parKhet(
    computeTensionByKhet(annonces("K", 50, 10), sansMediane, "sale", now), "K"
  );
  assert.ok(repli.priceMomentum! > 0, "sans médiane, repli sur la moyenne");
});
