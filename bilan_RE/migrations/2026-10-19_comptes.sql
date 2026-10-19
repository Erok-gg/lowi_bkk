-- 2026-10-19_comptes.sql — base des COMPTES de la beta (fichier SEPARE).
-- Rollback (ecrit AVANT application, regle 7) : 2026-10-19_comptes_rollback.sql
--
-- CE FICHIER N'EST PAS L'EXEMPLAIRE. Le schema vit dans
-- bilan_RE/web/lib/comptes-schema.ts, et `assureSchema()` l'applique au
-- demarrage du serveur (CREATE TABLE IF NOT EXISTS + ALTER TABLE ADD COLUMN
-- pour les champs ajoutes apres coup). Ce .sql est la trace ecrite : ce qui a
-- ete cree, quand, et comment le defaire. Modifier le .ts, jamais celui-ci
-- seul -- une liste de colonnes recopiee a deux endroits a deja coute cher ici
-- (SYNC_TABLES, TABLES_ATTENDUES).
--
-- POURQUOI UNE BASE A PART, et pas des tables dans bangkok.db :
--   · bangkok.db est repliquee (archive, fenetre Supabase servie au public) :
--     des donnees personnelles y seraient copiees hors de notre vue ;
--   · elle pese 1,19 Go et s'ecrit pendant les scraps ; les comptes s'ecrivent
--     a la milliseconde pendant une visite, deux regimes d'ecriture opposes ;
--   · un rollback des comptes doit pouvoir se faire sans toucher au marche.
--
-- ETAT AVANT APPLICATION (releve le 2026-10-19 sur PC2 / REMIZDABOSS) :
-- le fichier comptes.db N'EXISTE PAS. Aucune table, aucune ligne, 0 octet.
-- Il n'y avait aucune notion de compte dans le projet : la seule porte etait le
-- mot de passe partage de lib/auth.ts (un secret, zero utilisateur).
--
-- Emplacement : $LOWI_COMPTES_DB, sinon a cote de $LOWI_SQLITE_DB
-- (scraper/output/comptes.db sur PC2).

CREATE TABLE IF NOT EXISTS comptes (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  email_saisi TEXT,
  mdp_hash TEXT,
  mdp_sel TEXT,
  mdp_algo TEXT DEFAULT "scrypt-n16384-r8-p1",
  mdp_pose_le TEXT,
  mdp_a_renouveler INTEGER DEFAULT 1,
  cree_le TEXT NOT NULL,
  derniere_connexion TEXT,
  langue TEXT DEFAULT "en",
  origine TEXT,
  statut TEXT DEFAULT "actif",
  code_apporteur TEXT,
  nom TEXT,
  prenom TEXT,
  date_naissance TEXT,
  nationalite TEXT,
  supprime_le TEXT
);
CREATE INDEX IF NOT EXISTS idx_comptes_email ON comptes (email);

CREATE TABLE IF NOT EXISTS sessions (
  jeton_hash TEXT PRIMARY KEY,
  compte_id TEXT NOT NULL,
  cree_le TEXT NOT NULL,
  expire_le TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_compte ON sessions (compte_id);

CREATE TABLE IF NOT EXISTS rapports_compte (
  compte_id TEXT NOT NULL,
  rapport_id TEXT NOT NULL,
  url TEXT,
  titre TEXT,
  cree_le TEXT NOT NULL,
  paye INTEGER DEFAULT 0,
  paiement_ref TEXT,
  mail_envoye_le TEXT,
  PRIMARY KEY (compte_id, rapport_id)
);
CREATE INDEX IF NOT EXISTS idx_rapports_compte ON rapports_compte (compte_id);

CREATE TABLE IF NOT EXISTS consentements (
  id TEXT PRIMARY KEY,
  compte_id TEXT,
  visiteur TEXT,
  categories TEXT NOT NULL,
  version TEXT NOT NULL,
  cree_le TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_consentements_compte ON consentements (compte_id);

CREATE TABLE IF NOT EXISTS mails (
  id TEXT PRIMARY KEY,
  compte_id TEXT,
  genre TEXT NOT NULL,
  destinataire TEXT NOT NULL,
  sujet TEXT,
  cree_le TEXT NOT NULL,
  remis_le TEXT,
  erreur TEXT
);
CREATE INDEX IF NOT EXISTS idx_mails_compte ON mails (compte_id);
