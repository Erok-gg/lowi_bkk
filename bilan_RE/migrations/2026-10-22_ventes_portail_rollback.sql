-- Rollback de 2026-10-22_ventes_portail.sql.
-- ORDRE INVERSE : d'abord retirer l'appel `enregistrer_ventes_portail` de run.py,
-- la création des tables dans sqlite_store._migrate et la lecture dans
-- bilan_RE/tension/rapport.py, sinon elles sont recréées / interrogées.
-- Aucune donnée d'origine touchée : les ventes se relisent sur les pages d'immeuble
-- (et restent dans scraper/output/fazwaz-projets.json, clé « ventes »).
drop index if exists idx_ventes_portail_condo;
drop table if exists ventes_portail;
drop table if exists ventes_portail_projets;
