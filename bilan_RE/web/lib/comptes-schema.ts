/**
 * comptes-schema.ts — EXEMPLAIRE UNIQUE du schéma de la base des comptes.
 *
 * POURQUOI ici et pas dans un .sql. Le défaut qui a coûté le plus cher sur ce
 * dépôt est la liste de colonnes recopiée à deux endroits (`SYNC_TABLES`,
 * `TABLES_ATTENDUES`, `COLONNES_LISTING`) : l'une dérive, et le code écrit dans
 * une colonne que la base n'a pas. Ici la déclaration ci-dessous est la seule
 * vérité : `assureSchema()` en dérive le `CREATE TABLE`, les `ALTER TABLE ADD
 * COLUMN` de rattrapage et les index ; les fichiers de
 * `bilan_RE/migrations/2026-10-19_comptes*.sql` ne sont qu'une trace écrite,
 * pas un second exemplaire.
 *
 * MODULAIRE, concrètement (demande du 2026-10-19) : ajouter un champ = une
 * ligne dans `TABLES` ci-dessous. Au prochain démarrage, `assureSchema()`
 * l'ajoute aux bases existantes (SQLite sait le faire à chaud) sans migration
 * manuelle et sans perdre une ligne. Un champ RETIRÉ suit l'ordre inverse
 * (le code cesse d'écrire d'abord) — voir le skill lowi-couche-donnees §2.
 *
 * Cette base est SÉPARÉE de `bangkok.db` (la référence du marché) : des données
 * personnelles n'ont rien à faire dans une base dont des copies partent en
 * archive et dont une fenêtre est servie au public.
 */

export type Champ = {
  nom: string;
  type: "TEXT" | "INTEGER" | "REAL";
  /** Contraintes posées à la CRÉATION seulement : SQLite n'ajoute pas un UNIQUE
   *  par `ALTER TABLE`. Un champ ajouté plus tard ne peut donc pas être NOT NULL
   *  sans défaut — c'est volontairement interdit par `assureSchema()`. */
  contrainte?: string;
  /** Valeur posée sur les lignes existantes quand le champ est ajouté après coup. */
  defaut?: string | number | null;
  /** À quoi il sert. Affiché nulle part : c'est pour la personne qui reprend le code. */
  note?: string;
};

export type Table = {
  nom: string;
  champs: Champ[];
  /** Clé primaire composée, quand ce n'est pas `id`. */
  pk?: string[];
  index?: { nom: string; sur: string; unique?: boolean }[];
};

export const TABLES: Table[] = [
  {
    nom: "comptes",
    champs: [
      { nom: "id", type: "TEXT", contrainte: "PRIMARY KEY", note: "identifiant opaque (16 octets hex)" },
      { nom: "email", type: "TEXT", contrainte: "NOT NULL UNIQUE", note: "normalisé : minuscules, espaces coupés" },
      { nom: "email_saisi", type: "TEXT", note: "tel que tapé — pour l'afficher sans le déformer" },
      { nom: "mdp_hash", type: "TEXT", note: "scrypt ; jamais le mot de passe en clair" },
      { nom: "mdp_sel", type: "TEXT" },
      { nom: "mdp_algo", type: "TEXT", defaut: "scrypt-n16384-r8-p1", note: "tracé pour pouvoir changer de coût plus tard" },
      { nom: "mdp_pose_le", type: "TEXT" },
      { nom: "mdp_a_renouveler", type: "INTEGER", defaut: 1, note: "1 = mot de passe généré par nous, à changer" },
      { nom: "cree_le", type: "TEXT", contrainte: "NOT NULL" },
      { nom: "derniere_connexion", type: "TEXT" },
      { nom: "langue", type: "TEXT", defaut: "en", note: "en | th | zh" },
      { nom: "origine", type: "TEXT", note: "pdf | inscription — par où le compte est né" },
      { nom: "statut", type: "TEXT", defaut: "actif", note: "actif | bloque" },
      { nom: "code_apporteur", type: "TEXT", note: "code de l'agent qui a poussé l'acheteur (backlog #31)" },
      // Demandés AU PAIEMENT, pas à l'inscription (demande du 2026-10-19).
      // Vides jusque-là : un compte créé par le bouton PDF n'a que l'e-mail.
      { nom: "nom", type: "TEXT" },
      { nom: "prenom", type: "TEXT" },
      { nom: "date_naissance", type: "TEXT", note: "AAAA-MM-JJ" },
      { nom: "nationalite", type: "TEXT", note: "code ISO 3166-1 alpha-2" },
      // PDPA (Thaïlande) et RGPD : droit à l'effacement sans casser les lignes liées.
      { nom: "supprime_le", type: "TEXT", note: "effacement demandé : les champs personnels sont vidés, la ligne reste" },
    ],
    index: [{ nom: "idx_comptes_email", sur: "email" }],
  },
  {
    nom: "sessions",
    champs: [
      { nom: "jeton_hash", type: "TEXT", contrainte: "PRIMARY KEY", note: "sha256 du cookie ; le jeton lui-même n'est pas stocké" },
      { nom: "compte_id", type: "TEXT", contrainte: "NOT NULL" },
      { nom: "cree_le", type: "TEXT", contrainte: "NOT NULL" },
      { nom: "expire_le", type: "TEXT", contrainte: "NOT NULL" },
    ],
    index: [{ nom: "idx_sessions_compte", sur: "compte_id" }],
  },
  {
    nom: "rapports_compte",
    champs: [
      { nom: "compte_id", type: "TEXT", contrainte: "NOT NULL" },
      { nom: "rapport_id", type: "TEXT", contrainte: "NOT NULL", note: "même identifiant que bilan_RE/web/lib/rapport.ts" },
      { nom: "url", type: "TEXT", note: "l'annonce analysée" },
      { nom: "titre", type: "TEXT" },
      { nom: "cree_le", type: "TEXT", contrainte: "NOT NULL" },
      { nom: "paye", type: "INTEGER", defaut: 0, note: "0 = bilan gratuit consulté, 1 = rapport complet payé" },
      { nom: "paiement_ref", type: "TEXT", note: "référence du prestataire, quand le paiement sera branché" },
      { nom: "mail_envoye_le", type: "TEXT" },
    ],
    pk: ["compte_id", "rapport_id"],
    index: [{ nom: "idx_rapports_compte", sur: "compte_id" }],
  },
  {
    nom: "consentements",
    champs: [
      { nom: "id", type: "TEXT", contrainte: "PRIMARY KEY" },
      { nom: "compte_id", type: "TEXT", note: "nul pour un visiteur non inscrit" },
      { nom: "visiteur", type: "TEXT", note: "identifiant aléatoire du navigateur, sans lien avec une personne" },
      { nom: "categories", type: "TEXT", contrainte: "NOT NULL", note: "JSON : { necessaires, mesure, marketing }" },
      { nom: "version", type: "TEXT", contrainte: "NOT NULL", note: "version du texte accepté" },
      { nom: "cree_le", type: "TEXT", contrainte: "NOT NULL" },
    ],
    index: [{ nom: "idx_consentements_compte", sur: "compte_id" }],
  },
  {
    nom: "mails",
    champs: [
      { nom: "id", type: "TEXT", contrainte: "PRIMARY KEY" },
      { nom: "compte_id", type: "TEXT" },
      { nom: "genre", type: "TEXT", contrainte: "NOT NULL", note: "bienvenue | rapport | mot_de_passe" },
      { nom: "destinataire", type: "TEXT", contrainte: "NOT NULL" },
      { nom: "sujet", type: "TEXT" },
      { nom: "cree_le", type: "TEXT", contrainte: "NOT NULL" },
      { nom: "remis_le", type: "TEXT", note: "posé quand le fichier de la file a été pris en charge" },
      { nom: "erreur", type: "TEXT" },
    ],
    index: [{ nom: "idx_mails_compte", sur: "compte_id" }],
  },
];

// La version du texte de consentement vit dans son propre module (lu aussi par
// le bandeau, côté navigateur) : un seul exemplaire, pas deux.
export { VERSION_CONSENTEMENT } from "./consentement-version";

export function creationSQL(t: Table): string {
  const cols = t.champs.map((c) => `  ${c.nom} ${c.type}${c.contrainte ? " " + c.contrainte : ""}`);
  if (t.pk) cols.push(`  PRIMARY KEY (${t.pk.join(", ")})`);
  return `CREATE TABLE IF NOT EXISTS ${t.nom} (\n${cols.join(",\n")}\n)`;
}

export function indexSQL(t: Table): string[] {
  return (t.index ?? []).map(
    (i) => `CREATE ${i.unique ? "UNIQUE " : ""}INDEX IF NOT EXISTS ${i.nom} ON ${t.nom} (${i.sur})`,
  );
}
