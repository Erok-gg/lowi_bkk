/**
 * Essais de la couche comptes. `npm test`.
 *
 * Ce qu'ils gardent, et pourquoi chacun est là :
 *   1. le SCHÉMA RÉEL de la base correspond à la déclaration — l'équivalent de
 *      `agents/tests/test_stores_alignes.py` pour cette base. Sans lui, rien
 *      n'applique le point « exemplaire unique » : on écrirait dans une colonne
 *      absente et le scrap… pardon, la visite, échouerait en silence ;
 *   2. un champ AJOUTÉ à la déclaration arrive dans une base existante sans
 *      perdre une ligne (c'est toute la promesse « modulaire » du 2026-10-19) ;
 *   3. le mot de passe généré n'est jamais stocké en clair, et un mauvais mot de
 *      passe ne connecte pas ;
 *   4. une session expirée ne connecte plus ;
 *   5. deux fois la même adresse = un seul compte, et pas de mot de passe
 *      réinitialisé en silence.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";
import { TABLES, creationSQL } from "./comptes-schema";

/** Base jetable : jamais la vraie. Un test qui écrit dans comptes.db créerait
 *  de faux comptes en production, et on ne le verrait pas.
 *  Le nettoyage REFERME la base avant d'effacer : sous Windows le fichier reste
 *  verrouillé tant que la poignée vit (EPERM au `rm`). */
function baseJetable() {
  const dossier = mkdtempSync(path.join(tmpdir(), "lowi-comptes-"));
  process.env.LOWI_COMPTES_DB = path.join(dossier, "comptes.db");
  return async () => {
    try {
      const C = await import("./comptes");
      C.ferme();
    } catch {
      /* le module n'a pas été chargé : rien à refermer */
    }
    rmSync(dossier, { recursive: true, force: true, maxRetries: 5, retryDelay: 50 });
  };
}

/** Import frais : `comptes.ts` garde la base ouverte sur `globalThis`, il faut
 *  donc la relâcher entre deux essais qui visent des fichiers différents. */
async function neuf() {
  // La poignée est mise en cache sur globalThis : la refermer AVANT de recharger,
  // sinon chaque essai laisse un verrou ouvert sur sa base jetable.
  try {
    (await import("./comptes")).ferme();
  } catch {
    /* premier essai : rien à refermer */
  }
  return await import(`./comptes.ts?${Math.random()}`);
}

test("le schéma réel de la base correspond à la déclaration", async () => {
  const nettoie = baseJetable();
  try {
    const C = await neuf();
    const db = C.base();
    for (const t of TABLES) {
      const reelles = db
        .prepare(`PRAGMA table_info(${t.nom})`)
        .all()
        .map((r: Record<string, unknown>) => String(r.name));
      const declarees = t.champs.map((c) => c.nom);
      assert.deepEqual(
        [...reelles].sort(),
        [...declarees].sort(),
        `table ${t.nom} : la base et comptes-schema.ts ont divergé`,
      );
    }
  } finally {
    await nettoie();
  }
});

test("un champ ajouté à la déclaration arrive sans perdre de ligne", async () => {
  const nettoie = baseJetable();
  try {
    const chemin = process.env.LOWI_COMPTES_DB!;
    // Base « d'avant » : on la crée SANS le dernier champ de `comptes`.
    const avant = new DatabaseSync(chemin);
    const t = TABLES.find((x) => x.nom === "comptes")!;
    const ampute = { ...t, champs: t.champs.slice(0, -1) };
    avant.exec(creationSQL(ampute));
    avant.exec(
      "INSERT INTO comptes (id, email, cree_le) VALUES ('abc', 'a@b.co', '2026-10-19T00:00:00.000Z')",
    );
    avant.close();

    const C = await neuf();
    const db = C.base(); // c'est ici que le rattrapage doit avoir lieu
    const cols = db
      .prepare("PRAGMA table_info(comptes)")
      .all()
      .map((r: Record<string, unknown>) => String(r.name));
    assert.ok(cols.includes(t.champs.at(-1)!.nom), "le champ ajouté n'a pas été rattrapé");
    const n = db.prepare("SELECT count(*) AS n FROM comptes").get() as { n: number };
    assert.equal(n.n, 1, "une ligne a été perdue au passage");
  } finally {
    await nettoie();
  }
});

test("mot de passe : jamais en clair en base, et un faux ne passe pas", async () => {
  const nettoie = baseJetable();
  try {
    const C = await neuf();
    const { compte, motDePasse, nouveau } = C.creeCompte({ email: "  Jean@Exemple.CO " });
    assert.equal(nouveau, true);
    assert.equal(compte.email, "jean@exemple.co", "l'e-mail doit être normalisé");
    assert.ok(motDePasse && motDePasse.length >= 12);

    const ligne = C.base().prepare("SELECT mdp_hash FROM comptes WHERE id = ?").get(compte.id) as {
      mdp_hash: string;
    };
    assert.ok(!ligne.mdp_hash.includes(motDePasse!), "le mot de passe se retrouve en base");

    assert.ok(C.connecte("jean@exemple.co", motDePasse!), "le bon mot de passe doit connecter");
    assert.equal(C.connecte("jean@exemple.co", motDePasse! + "x"), null);
    assert.equal(C.connecte("inconnu@exemple.co", motDePasse!), null);
  } finally {
    await nettoie();
  }
});

test("une session expirée ne connecte plus", async () => {
  const nettoie = baseJetable();
  try {
    const C = await neuf();
    const { compte } = C.creeCompte({ email: "s@exemple.co" });
    const { jeton } = C.ouvreSession(compte.id);
    assert.ok(C.compteDeSession(jeton), "la session fraîche doit valoir");

    C.base()
      .prepare("UPDATE sessions SET expire_le = ? WHERE compte_id = ?")
      .run("2020-01-01T00:00:00.000Z", compte.id);
    assert.equal(C.compteDeSession(jeton), null, "une session expirée connecte encore");
    // et elle doit avoir été nettoyée au passage
    const reste = C.base().prepare("SELECT count(*) AS n FROM sessions").get() as { n: number };
    assert.equal(reste.n, 0);
  } finally {
    await nettoie();
  }
});

test("deux fois la même adresse : un seul compte, mot de passe intact", async () => {
  const nettoie = baseJetable();
  try {
    const C = await neuf();
    const a = C.creeCompte({ email: "double@exemple.co" });
    const b = C.creeCompte({ email: "DOUBLE@exemple.co" });
    assert.equal(b.nouveau, false);
    assert.equal(b.motDePasse, null, "un second passage ne doit pas réinitialiser le mot de passe");
    assert.equal(a.compte.id, b.compte.id);
    assert.ok(C.connecte("double@exemple.co", a.motDePasse!), "le premier mot de passe doit encore valoir");

    const n = C.base().prepare("SELECT count(*) AS n FROM comptes").get() as { n: number };
    assert.equal(n.n, 1);
  } finally {
    await nettoie();
  }
});

test("rapport lié : retrouvé, et le paiement ne redescend jamais", async () => {
  const nettoie = baseJetable();
  try {
    const C = await neuf();
    const { compte } = C.creeCompte({ email: "r@exemple.co" });
    C.lieRapport(compte.id, "0123456789abcdef", "https://x.test/a", "Condo · Khet", 1);
    C.lieRapport(compte.id, "0123456789abcdef", null, null, 0); // second passage gratuit
    assert.equal(C.possede(compte.id, "0123456789abcdef"), true);
    const l = C.rapportsDe(compte.id);
    assert.equal(l.length, 1, "le même rapport ne doit pas être listé deux fois");
    assert.equal(l[0].paye, 1, "un rapport payé ne doit pas repasser à gratuit");
    assert.equal(l[0].titre, "Condo · Khet", "le titre ne doit pas être écrasé par un null");
  } finally {
    await nettoie();
  }
});

test("effacement : plus de données personnelles, plus de session", async () => {
  const nettoie = baseJetable();
  try {
    const C = await neuf();
    const { compte } = C.creeCompte({ email: "part@exemple.co" });
    C.majProfil(compte.id, { nom: "Dupont", prenom: "Jean", nationalite: "FR" });
    C.ouvreSession(compte.id);
    C.effaceCompte(compte.id);

    const l = C.base()
      .prepare("SELECT email, nom, prenom, nationalite, supprime_le FROM comptes WHERE id = ?")
      .get(compte.id) as Record<string, unknown>;
    assert.equal(l.nom, null);
    assert.equal(l.prenom, null);
    assert.equal(l.nationalite, null);
    assert.ok(String(l.email).startsWith("efface-"), "l'adresse doit être neutralisée");
    assert.ok(l.supprime_le, "la date d'effacement doit être posée");
    const s = C.base().prepare("SELECT count(*) AS n FROM sessions WHERE compte_id = ?").get(compte.id) as {
      n: number;
    };
    assert.equal(s.n, 0);
  } finally {
    await nettoie();
  }
});

test("majProfil refuse un champ qui n'est pas déclaré", async () => {
  const nettoie = baseJetable();
  try {
    const C = await neuf();
    const { compte } = C.creeCompte({ email: "inj@exemple.co" });
    // Une clé inconnue venant du navigateur ne doit jamais atteindre le SQL.
    C.majProfil(compte.id, { "statut = 'bloque' -- ": "x", nom: "Ok" });
    const l = C.base().prepare("SELECT nom, statut FROM comptes WHERE id = ?").get(compte.id) as Record<
      string,
      unknown
    >;
    assert.equal(l.nom, "Ok");
    assert.equal(l.statut, "actif", "un champ non déclaré a été écrit");
  } finally {
    await nettoie();
  }
});
