-- 2026-10-17_index_bilan_2.sql — second lot d'index, après remesure du bilan.
-- Rollback : 2026-10-17_index_bilan_2_rollback.sql. Additif uniquement.
--
-- POURQUOI. Après le premier lot (10 s → 6 s par bilan), le profil montrait encore
-- deux parcours complets :
--   · le rayon de 1 km (`lat between …` hors du district) : aucun index sur lat ;
--   · l'historique de prix d'une annonce : price_history n'a d'index que sur id,
--     `listing_id in (…)` parcourt ses ~200 000 lignes (plan : SCAN price_history).
-- État avant application (relevé) : price_history n'a que sqlite_autoindex_price_history_1.

CREATE INDEX IF NOT EXISTS idx_listings_vente_lat ON listings (deal_type, status, lat);
CREATE INDEX IF NOT EXISTS idx_price_history_listing ON price_history (listing_id);
