-- Rollback de 2026-10-17_index_bilan.sql — ramène la base à l'état relevé avant
-- application (5 index + l'autoindex de la clé primaire, pas de colonne condo_norm).
-- Aucune donnée d'origine n'est touchée : on retire seulement ce qui a été ajouté.
-- DROP COLUMN exige SQLite ≥ 3.35 (base de PC2 : 3.50.4, vérifié).
-- Après ce rollback, le bilan retombe sur la comparaison des noms bruts : plus
-- lent (~10 s) et il perd des immeubles d'un portail à l'autre.

DROP INDEX IF EXISTS idx_listings_condo_norm;
DROP INDEX IF EXISTS idx_listings_vente_khet;
DROP INDEX IF EXISTS idx_listings_last_seen;
ALTER TABLE listings DROP COLUMN condo_norm;
