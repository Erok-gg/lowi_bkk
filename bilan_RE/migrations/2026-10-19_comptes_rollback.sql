-- Rollback de 2026-10-19_comptes.sql — ramene a l'etat releve avant
-- application : le fichier comptes.db n'existait pas du tout.
--
-- ORDRE INVERSE, et il compte (skill lowi-couche-donnees §2) : le CODE doit
-- cesser de lire ces tables AVANT qu'elles disparaissent, sinon la landing et
-- le bouton PDF tombent en erreur au prochain clic. Concretement :
--   1. retirer LOWI_BETA_PUBLIQUE et LOWI_COMPTES_DB de .env.local
--      (sans LOWI_COMPTES_DB *et* sans LOWI_SQLITE_DB, `comptesActives()` est
--      faux et plus une ligne de ce schema n'est lue — la beta retombe sur le
--      mot de passe partage, exactement comme avant le 2026-10-19) ;
--   2. redemarrer le serveur Next ;
--   3. seulement ensuite, jouer ce fichier.
--
-- ⚠ LA DONNEE PART AVEC. Ces tables portent les seuls comptes existants et la
-- PREUVE des consentements. Avant de jouer ceci, copier le fichier ailleurs et
-- VERIFIER la copie ligne a ligne (regle 8) :
--   sqlite3 comptes.db ".backup comptes-avant-rollback.db"
--   -- puis comparer les comptes des deux cotes :
--   sqlite3 comptes.db                  "select count(*) from comptes;"
--   sqlite3 comptes-avant-rollback.db   "select count(*) from comptes;"
-- Le bon test n'est pas le nombre de lignes seul : verifier qu'aucun id de la
-- source ne manque a la copie.
-- Le plus simple, et le plus sur, reste de SUPPRIMER le fichier comptes.db
-- apres l'avoir copie : la base est a part, rien d'autre ne vit dedans.

DROP INDEX IF EXISTS idx_mails_compte;
DROP TABLE IF EXISTS mails;

DROP INDEX IF EXISTS idx_consentements_compte;
DROP TABLE IF EXISTS consentements;

DROP INDEX IF EXISTS idx_rapports_compte;
DROP TABLE IF EXISTS rapports_compte;

DROP INDEX IF EXISTS idx_sessions_compte;
DROP TABLE IF EXISTS sessions;

DROP INDEX IF EXISTS idx_comptes_email;
DROP TABLE IF EXISTS comptes;
