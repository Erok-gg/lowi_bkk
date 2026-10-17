-- Rollback de 2026-10-17_index_bilan_2.sql : retire les deux index ajoutés, rien d'autre.
DROP INDEX IF EXISTS idx_listings_vente_lat;
DROP INDEX IF EXISTS idx_price_history_listing;
