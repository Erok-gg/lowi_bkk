-- Rollback de 2026-10-07_index_inutiles_listings.sql.
-- Définitions recopiées de pg_get_indexdef() sur l'état LIVE du 2026-10-07.
-- Sur instance bridée, préférer CREATE INDEX CONCURRENTLY (hors transaction).

CREATE INDEX idx_listings_agent ON public.listings USING btree (agent_id) WHERE (agent_id IS NOT NULL);
CREATE INDEX idx_listings_bench ON public.listings USING btree (condo_name, deal_type, status) WHERE (price_per_sqm > (0)::numeric);
CREATE INDEX idx_listings_khet ON public.listings USING btree (khet);
CREATE INDEX idx_listings_missed ON public.listings USING btree (missed_count) WHERE (missed_count > 0);
CREATE INDEX idx_listings_posted ON public.listings USING btree (posted_at) WHERE (posted_at IS NOT NULL);
CREATE INDEX idx_listings_repost ON public.listings USING btree (repost_of) WHERE (repost_of IS NOT NULL);
CREATE INDEX idx_listings_source ON public.listings USING btree (source);
CREATE INDEX idx_listings_status ON public.listings USING btree (status);
CREATE INDEX idx_listings_street ON public.listings USING btree (street, deal_type, status) WHERE (price_per_sqm > (0)::numeric);
CREATE INDEX idx_listings_unit ON public.listings USING btree (unit_key);

ALTER TABLE public.listings RESET (fillfactor);
-- Le VACUUM n'a rien à défaire : il ne supprime que des versions déjà mortes.
