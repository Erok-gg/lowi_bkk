/**
 * comptes.ts — comptes, sessions et rapports possédés (serveur uniquement).
 *
 * Base SQLite SÉPARÉE (`comptes.db`), pas `bangkok.db` : voir comptes-schema.ts.
 * Elle s'écrit, elle : contrairement à `listings-db.ts` qui n'ouvre la base de
 * référence qu'en lecture seule.
 *
 * Ce que ce module ne fait PAS, volontairement :
 *   · aucun paiement (les colonnes nom/prénom/naissance/nationalité existent et
 *     restent vides jusqu'à ce que le prestataire soit choisi) ;
 *   · aucun envoi direct d'e-mail (voir mail.ts : on dépose dans la file que la
 *     session Claude planifiée vide par le connecteur Gmail — il n'y a pas de
 *     SMTP sur ce poste, et en ajouter un voudrait dire stocker un mot de passe
 *     applicatif en clair, ce que `agents/core/alert.py` a déjà refusé).
 */
// Pas de `import "server-only"` ici, à la différence de session.ts et mail.ts :
// ce module doit pouvoir tourner hors de Next pour être testé
// (`bilan_RE/web/lib/comptes.test.ts`, lancé par `npm test`). Il n'est de toute
// façon importable que côté serveur en pratique — il ouvre `node:sqlite`, ce
// qu'un composant navigateur ne sait pas faire, et l'erreur serait immédiate.
// C'est session.ts (cookies) qui porte la barrière.
import { randomBytes, createHash, scryptSync, timingSafeEqual } from "node:crypto";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { TABLES, creationSQL, indexSQL, VERSION_CONSENTEMENT } from "./comptes-schema";

export const COOKIE_SESSION = "lowi_compte";
export const COOKIE_CONSENT = "lowi_consent";
export const COOKIE_VISITEUR = "lowi_v";
export const JOURS_SESSION = 60;

/* ─────────────────────────────── la base ─────────────────────────────────── */

function chemin(): string {
  if (process.env.LOWI_COMPTES_DB) return path.resolve(process.cwd(), process.env.LOWI_COMPTES_DB);
  // À côté de la base de référence quand elle est connue : même disque, mêmes
  // sauvegardes. Sinon dans scraper/output (ce que fait déjà le reste du projet).
  const ref = process.env.LOWI_SQLITE_DB;
  const dossier = ref ? path.dirname(path.resolve(process.cwd(), ref)) : path.join(process.cwd(), "scraper", "output");
  return path.join(dossier, "comptes.db");
}

type DB = {
  exec(sql: string): void;
  prepare(sql: string): {
    run(...p: unknown[]): unknown;
    get(...p: unknown[]): Record<string, unknown> | undefined;
    all(...p: unknown[]): Record<string, unknown>[];
  };
};

const G = globalThis as unknown as { __lowiComptes?: DB };

/** Ouvre (et crée au besoin) la base, puis met le schéma à niveau.
 *  Synchrone : `node:sqlite` l'est, et ces écritures sont des unités. */
export function base(): DB {
  if (G.__lowiComptes) return G.__lowiComptes;
  // require et non import() : ce module est appelé depuis des fonctions
  // synchrones (vérification de session dans un server component).
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { DatabaseSync } = require("node:sqlite") as { DatabaseSync: new (p: string) => DB };
  const p = chemin();
  mkdirSync(path.dirname(p), { recursive: true });
  const db = new DatabaseSync(p);
  db.exec("PRAGMA journal_mode = WAL");
  assureSchema(db);
  G.__lowiComptes = db;
  return db;
}

/** Crée ce qui manque, à partir du seul exemplaire (comptes-schema.ts).
 *  Rattrape aussi une base existante : un champ ajouté à la déclaration arrive
 *  ici par `ALTER TABLE ADD COLUMN`. SQLite se répare à chaud ; Postgres non —
 *  si cette base passe un jour en Postgres, il faudra une vraie migration. */
export function assureSchema(db: DB): void {
  for (const t of TABLES) {
    db.exec(creationSQL(t));
    const presentes = new Set(db.prepare(`PRAGMA table_info(${t.nom})`).all().map((r) => String(r.name)));
    for (const c of t.champs) {
      if (presentes.has(c.nom)) continue;
      // Pas de NOT NULL en ajout : SQLite refuse sans défaut, et un défaut
      // inventé sur des lignes existantes serait une donnée fausse.
      const def = c.defaut === undefined || c.defaut === null ? "" : ` DEFAULT ${JSON.stringify(c.defaut)}`;
      db.exec(`ALTER TABLE ${t.nom} ADD COLUMN ${c.nom} ${c.type}${def}`);
    }
    for (const sql of indexSQL(t)) db.exec(sql);
  }
}

/** Les comptes ne vivent que là où il y a un disque qui s'écrit : PC2.
 *  La condition est une VARIABLE, pas une tentative d'ouverture : sur Vercel le
 *  système de fichiers est en lecture seule, et essayer à chaque requête
 *  coûterait une exception par visite (règle 9 : on ne gaspille pas une
 *  invocation). `LOWI_COMPTES_DB` suffit à l'activer ailleurs. */
/** Referme la base et relâche la poignée. Windows garde le fichier verrouillé
 *  tant qu'elle est ouverte (le WAL avec) : sans ça, un essai ne peut pas
 *  supprimer sa base jetable — constaté à l'écriture des tests, EPERM. */
export function ferme(): void {
  const db = G.__lowiComptes as (DB & { close?: () => void }) | undefined;
  try {
    db?.close?.();
  } finally {
    delete G.__lowiComptes;
  }
}

export function comptesActives(): boolean {
  return Boolean(process.env.LOWI_COMPTES_DB || process.env.LOWI_SQLITE_DB);
}

export function disponibleComptes(): boolean {
  if (!comptesActives()) return false;
  try {
    base();
    return true;
  } catch {
    return false;
  }
}

const maintenant = () => new Date().toISOString();
const jeton = (n = 16) => randomBytes(n).toString("hex");

/* ───────────────────────────── mots de passe ─────────────────────────────── */

/** Mot de passe lisible au téléphone : pas de O/0/I/l/1 confondus. */
export function motDePasseAleatoire(longueur = 12): string {
  const alpha = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
  const o = randomBytes(longueur);
  let s = "";
  for (let i = 0; i < longueur; i++) s += alpha[o[i] % alpha.length];
  return s;
}

function hache(mdp: string, sel: string): string {
  return scryptSync(mdp.normalize("NFKC"), sel, 64, { N: 16384, r: 8, p: 1 }).toString("hex");
}

export function verifieMotDePasse(mdp: string, hash: string, sel: string): boolean {
  if (!hash || !sel) return false;
  const a = Buffer.from(hache(mdp, sel), "hex");
  const b = Buffer.from(hash, "hex");
  return a.length === b.length && timingSafeEqual(a, b);
}

/* ──────────────────────────────── comptes ────────────────────────────────── */

export type Compte = {
  id: string;
  email: string;
  email_saisi: string | null;
  langue: string | null;
  statut: string | null;
  mdp_a_renouveler: number | null;
  nom: string | null;
  prenom: string | null;
};

const CHAMPS_LUS =
  "id, email, email_saisi, langue, statut, mdp_a_renouveler, nom, prenom";

export function normaliseEmail(email: string): string {
  return email.trim().toLowerCase();
}

/** Forme seulement : on ne vérifie pas que la boîte existe (ça, c'est l'e-mail
 *  envoyé qui le dit). Volontairement permissif : un faux refus coûte un client. */
export function emailPlausible(email: string): boolean {
  const e = normaliseEmail(email);
  return e.length >= 6 && e.length <= 254 && /^[^\s@]+@[^\s@.]+(\.[^\s@.]+)+$/.test(e);
}

export function trouveParEmail(email: string): Compte | null {
  const r = base()
    .prepare(`SELECT ${CHAMPS_LUS} FROM comptes WHERE email = ?`)
    .get(normaliseEmail(email));
  return (r as Compte | undefined) ?? null;
}

export function trouveParId(id: string): Compte | null {
  const r = base().prepare(`SELECT ${CHAMPS_LUS} FROM comptes WHERE id = ?`).get(id);
  return (r as Compte | undefined) ?? null;
}

/**
 * Crée le compte s'il n'existe pas, et renvoie le mot de passe EN CLAIR une
 * seule fois (celui qu'on envoie par e-mail ; la base n'en garde que le scrypt).
 * Si le compte existe déjà, `motDePasse` est null : on ne réinitialise pas en
 * silence un mot de passe que la personne a peut-être choisi.
 */
export function creeCompte(opts: {
  email: string;
  langue?: string;
  origine?: string;
  codeApporteur?: string | null;
}): { compte: Compte; motDePasse: string | null; nouveau: boolean } {
  const db = base();
  const email = normaliseEmail(opts.email);
  const deja = trouveParEmail(email);
  if (deja) return { compte: deja, motDePasse: null, nouveau: false };

  const mdp = motDePasseAleatoire();
  const sel = jeton(16);
  const id = jeton(16);
  db.prepare(
    `INSERT INTO comptes (id, email, email_saisi, mdp_hash, mdp_sel, mdp_algo, mdp_pose_le,
       mdp_a_renouveler, cree_le, langue, origine, statut, code_apporteur)
     VALUES (?, ?, ?, ?, ?, 'scrypt-n16384-r8-p1', ?, 1, ?, ?, ?, 'actif', ?)`,
  ).run(
    id,
    email,
    opts.email.trim(),
    hache(mdp, sel),
    sel,
    maintenant(),
    maintenant(),
    opts.langue ?? "en",
    opts.origine ?? "inscription",
    opts.codeApporteur ?? null,
  );
  return { compte: trouveParId(id)!, motDePasse: mdp, nouveau: true };
}

/** Mot de passe choisi par la personne : lève le drapeau « à renouveler ». */
export function poseMotDePasse(compteId: string, mdp: string): void {
  const sel = jeton(16);
  base()
    .prepare("UPDATE comptes SET mdp_hash = ?, mdp_sel = ?, mdp_pose_le = ?, mdp_a_renouveler = 0 WHERE id = ?")
    .run(hache(mdp, sel), sel, maintenant(), compteId);
}

/** Régénère un mot de passe (mot de passe oublié). Renvoie le clair une fois. */
export function regenereMotDePasse(compteId: string): string {
  const mdp = motDePasseAleatoire();
  const sel = jeton(16);
  base()
    .prepare("UPDATE comptes SET mdp_hash = ?, mdp_sel = ?, mdp_pose_le = ?, mdp_a_renouveler = 1 WHERE id = ?")
    .run(hache(mdp, sel), sel, maintenant(), compteId);
  return mdp;
}

export function connecte(email: string, mdp: string): Compte | null {
  const r = base()
    .prepare("SELECT id, mdp_hash, mdp_sel, statut FROM comptes WHERE email = ? AND supprime_le IS NULL")
    .get(normaliseEmail(email));
  if (!r || r.statut !== "actif") return null;
  if (!verifieMotDePasse(mdp, String(r.mdp_hash ?? ""), String(r.mdp_sel ?? ""))) return null;
  base().prepare("UPDATE comptes SET derniere_connexion = ? WHERE id = ?").run(maintenant(), String(r.id));
  return trouveParId(String(r.id));
}

/** Champs demandés au paiement. Modulaire : on passe ce qu'on a, le reste reste
 *  en place. Seuls les champs déclarés ici sont acceptés — une clé inconnue
 *  venant du navigateur ne doit jamais atteindre le SQL. */
const CHAMPS_PROFIL = ["nom", "prenom", "date_naissance", "nationalite", "langue", "code_apporteur"] as const;

export function majProfil(compteId: string, valeurs: Record<string, string | null>): void {
  const paires = Object.entries(valeurs).filter(
    ([k, v]) => (CHAMPS_PROFIL as readonly string[]).includes(k) && v !== undefined,
  );
  if (!paires.length) return;
  base()
    .prepare(`UPDATE comptes SET ${paires.map(([k]) => `${k} = ?`).join(", ")} WHERE id = ?`)
    .run(...paires.map(([, v]) => v), compteId);
}

/* ──────────────────────────────── sessions ───────────────────────────────── */

export function ouvreSession(compteId: string): { jeton: string; expire: Date } {
  const brut = randomBytes(32).toString("hex");
  const expire = new Date(Date.now() + JOURS_SESSION * 86400_000);
  base()
    .prepare("INSERT INTO sessions (jeton_hash, compte_id, cree_le, expire_le) VALUES (?, ?, ?, ?)")
    .run(createHash("sha256").update(brut).digest("hex"), compteId, maintenant(), expire.toISOString());
  return { jeton: brut, expire };
}

export function compteDeSession(brut: string | undefined): Compte | null {
  if (!brut) return null;
  const h = createHash("sha256").update(brut).digest("hex");
  const s = base().prepare("SELECT compte_id, expire_le FROM sessions WHERE jeton_hash = ?").get(h);
  if (!s) return null;
  if (new Date(String(s.expire_le)).getTime() < Date.now()) {
    base().prepare("DELETE FROM sessions WHERE jeton_hash = ?").run(h);
    return null;
  }
  return trouveParId(String(s.compte_id));
}

export function fermeSession(brut: string | undefined): void {
  if (!brut) return;
  base()
    .prepare("DELETE FROM sessions WHERE jeton_hash = ?")
    .run(createHash("sha256").update(brut).digest("hex"));
}

/* ───────────────────────── rapports gardés dans l'app ────────────────────── */

export type RapportCompte = {
  rapport_id: string;
  url: string | null;
  titre: string | null;
  cree_le: string;
  paye: number;
  mail_envoye_le: string | null;
};

export function lieRapport(
  compteId: string,
  rapportId: string,
  url?: string | null,
  titre?: string | null,
  paye = 0,
): void {
  base()
    .prepare(
      `INSERT INTO rapports_compte (compte_id, rapport_id, url, titre, cree_le, paye)
       VALUES (?, ?, ?, ?, ?, ?)
       ON CONFLICT(compte_id, rapport_id) DO UPDATE SET
         paye = MAX(paye, excluded.paye),
         url = COALESCE(excluded.url, url),
         titre = COALESCE(excluded.titre, titre)`,
    )
    .run(compteId, rapportId, url ?? null, titre ?? null, maintenant(), paye);
}

export function marqueMailEnvoye(compteId: string, rapportId: string): void {
  base()
    .prepare("UPDATE rapports_compte SET mail_envoye_le = ? WHERE compte_id = ? AND rapport_id = ?")
    .run(maintenant(), compteId, rapportId);
}

export function rapportsDe(compteId: string): RapportCompte[] {
  return base()
    .prepare(
      "SELECT rapport_id, url, titre, cree_le, paye, mail_envoye_le FROM rapports_compte WHERE compte_id = ? ORDER BY cree_le DESC",
    )
    .all(compteId) as unknown as RapportCompte[];
}

export function possede(compteId: string, rapportId: string): boolean {
  return Boolean(
    base().prepare("SELECT 1 FROM rapports_compte WHERE compte_id = ? AND rapport_id = ?").get(compteId, rapportId),
  );
}

/* ───────────────────────────── consentements ─────────────────────────────── */

export type Categories = { necessaires: true; mesure: boolean; marketing: boolean };

/** Garde la preuve du consentement : sans trace, « on a demandé » ne se prouve
 *  pas. Pas d'IP ni d'agent : on n'en a pas besoin pour ça (minimisation). */
export function enregistreConsentement(cats: Categories, compteId: string | null, visiteur: string): void {
  base()
    .prepare(
      "INSERT INTO consentements (id, compte_id, visiteur, categories, version, cree_le) VALUES (?, ?, ?, ?, ?, ?)",
    )
    .run(jeton(12), compteId, visiteur, JSON.stringify(cats), VERSION_CONSENTEMENT, maintenant());
}

/* ──────────────────────────── trace des e-mails ──────────────────────────── */

export function traceMail(opts: {
  compteId: string | null;
  genre: string;
  destinataire: string;
  sujet: string;
  erreur?: string | null;
}): void {
  base()
    .prepare(
      "INSERT INTO mails (id, compte_id, genre, destinataire, sujet, cree_le, erreur) VALUES (?, ?, ?, ?, ?, ?, ?)",
    )
    .run(jeton(12), opts.compteId, opts.genre, opts.destinataire, opts.sujet, maintenant(), opts.erreur ?? null);
}

/* ─────────────────────── droit à l'effacement (PDPA/RGPD) ────────────────── */

/** Vide les champs personnels et coupe les sessions ; garde la ligne et les
 *  liens de rapports (sans quoi la trace d'un achat disparaîtrait). */
export function effaceCompte(compteId: string): void {
  const db = base();
  db.prepare(
    `UPDATE comptes SET email = 'efface-' || id || '@invalide', email_saisi = NULL, mdp_hash = NULL,
       mdp_sel = NULL, nom = NULL, prenom = NULL, date_naissance = NULL, nationalite = NULL,
       statut = 'bloque', supprime_le = ? WHERE id = ?`,
  ).run(maintenant(), compteId);
  db.prepare("DELETE FROM sessions WHERE compte_id = ?").run(compteId);
}

export { VERSION_CONSENTEMENT };
