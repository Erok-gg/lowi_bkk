-- 2026-10-17_index_bilan.sql — index du bilan acheteur sur la base de référence SQLite (PC2).
-- Rollback (écrit AVANT application, règle 7) : 2026-10-17_index_bilan_rollback.sql
--
-- POURQUOI. Mesuré le 2026-10-17 sur 195 832 annonces (4,6 Go) : un bilan prend
-- 10 s, dont ~90 % en lectures qui parcourent toute la table faute d'index adapté.
--   · noms d'un immeuble (trim(condo_name) in …)        1 516 ms, plan : SCAN listings
--   · ventes actives d'un district                       1 510 ms, via l'index de status seul
--   · date des données (max de last_seen)                1 621 ms
--   · annonce par identifiant (index existant)               0 ms — l'ordre de grandeur visé
--
-- `condo_norm` = nom d'immeuble normalisé par la règle de `unit_key`
-- (scraper/pipeline/normalize._norm_condo). SQLite ne sait pas appliquer cette
-- fonction Python : la colonne est remplie APRÈS chaque scrap par
-- bilan_RE/ops/repertorier-annonces.py (les stores l'ignorent : insert et
-- update y nomment leurs colonnes, elle n'est ni écrasée ni requise).
--
-- Additif uniquement : aucune donnée modifiée ni supprimée.
-- État avant application (relevé sur la base vivante) : idx_listings_dirty,
-- idx_listings_khet, idx_listings_source_url, idx_listings_status,
-- idx_listings_unit, sqlite_autoindex_listings_1 ; pas de colonne condo_norm.

ALTER TABLE listings ADD COLUMN condo_norm TEXT;

CREATE INDEX IF NOT EXISTS idx_listings_condo_norm ON listings (condo_norm);
-- ordre (deal_type, status, khet) : les trois filtres des comparables, du plus
-- grossier au plus fin ; l'index va droit aux « ventes actives de Khlong Toei »
CREATE INDEX IF NOT EXISTS idx_listings_vente_khet ON listings (deal_type, status, khet);
CREATE INDEX IF NOT EXISTS idx_listings_last_seen ON listings (last_seen);
