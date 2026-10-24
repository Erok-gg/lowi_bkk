-- Rollback de 2026-10-22_date_source.sql — retire la colonne `listed_at_source`.
-- ORDRE INVERSE : d'abord retirer `listed_at_source` de COLONNES_LOCALES
-- (store/base.py), du _migrate() de sqlite_store et de l'adaptateur PropertyScout,
-- sinon le scrap suivant tente d'écrire une colonne absente. Puis cette ligne.
-- Aucune donnée d'origine touchée : la date se relit dans `page_text` (« Date Listed »).
-- DROP COLUMN exige SQLite ≥ 3.35 (PC2 : 3.50.4). Après rollback, le bilan retombe
-- sur `first_seen` seul (règle d'ancienneté `min` désactivée dans rapport.py).
ALTER TABLE listings DROP COLUMN listed_at_source;
