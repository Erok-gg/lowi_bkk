-- 2026-10-07 — Supabase : retrait de 10 index jamais utilisés sur `listings`.
--
-- Pourquoi (mesuré le 2026-10-07, stats remises à zéro le 2026-09-28) :
--   · idx_scan = 0 sur 12 des 13 index ; seule listings_pkey sert (1 255 754 scans).
--   · 1,3 % de mises à jour HOT (227 / 16 841) : chaque UPDATE réécrivait 13 index.
--   · Instance Nano à court de budget IO (checkpoint d'1 bloc = 17–22 s, 476
--     statement timeouts en 24 h) → remonter-supabase échoue 5 nuits sur 12.
-- Lecteurs vérifiés : l'app (lib/listings-db.ts) ne filtre que sur
-- status='active' (~65 % des lignes) et khet is not null → scans séquentiels de
-- toute façon. Les vues (listing_benchmarks, opportunites…) ne sont pas lues
-- par l'app ; les agents d'analyse lisent le SQLite local.
-- Conservés : listings_pkey, idx_listings_sold_since et idx_listings_market_status
-- (partiels, 16 ko chacun, utiles à la requête market_status='sold' du store).
-- Ces index restent créés par schema.sql / migrations côté SQLite et dans le
-- dépôt : ne pas rejouer ces fichiers sur Supabase sans relire celui-ci.
-- Rollback : 2026-10-07_rollback_index_inutiles_listings.sql (généré depuis
-- pg_get_indexdef sur l'état live, pas depuis le dépôt).

drop index if exists public.idx_listings_agent;
drop index if exists public.idx_listings_bench;
drop index if exists public.idx_listings_khet;
drop index if exists public.idx_listings_missed;
drop index if exists public.idx_listings_posted;
drop index if exists public.idx_listings_repost;
drop index if exists public.idx_listings_source;
drop index if exists public.idx_listings_status;
drop index if exists public.idx_listings_street;
drop index if exists public.idx_listings_unit;

-- Pages remplies à 85 % au lieu de 100 % : la nouvelle version d'une annonce
-- mise à jour tient dans la même page → UPDATE « HOT », sans toucher aux index.
-- Coût : ~15 % de place en plus sur les pages écrites ensuite (progressif).
alter table public.listings set (fillfactor = 85);

-- À lancer SEUL (VACUUM refuse un bloc de transaction). Simple, PAS « full » :
-- 25 027 versions mortes (14 %), autovacuum annulé en boucle faute d'IO.
-- vacuum (analyze) public.listings;
