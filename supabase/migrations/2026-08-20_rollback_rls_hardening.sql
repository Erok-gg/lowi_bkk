-- 2026-08-20_rollback_rls_hardening.sql
-- ANNULE 2026-08-20_rls_hardening.sql — retour exact à l'état d'avant correctif.
--
-- Ce fichier n'est PAS écrit de mémoire : chaque instruction reproduit un état
-- relevé dans le catalogue live le 2026-08-20 AVANT d'appliquer le correctif.
-- Relevés de référence :
--   * pg_class.reloptions = NULL sur les 15 vues de public (aucune n'avait
--     security_invoker) → on RESET, ce qui rend exactement NULL.
--   * information_schema.role_table_grants : les 26 relations (11 tables +
--     15 vues) portaient TOUTES les 7 privilèges de table
--     (DELETE, INSERT, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE)
--     pour anon ET authenticated — uniformité vérifiée, d'où le GRANT ALL global.
--   * pg_default_acl (owner postgres, schema public, objtype 'r') =
--     anon=arwdDxtm, authenticated=arwdDxtm → c'est ce défaut qui reposait les
--     grants sur chaque nouvelle table créée par le pipeline.
--   * pg_proc.proacl de rls_auto_enable() = "=X/postgres,…" → EXECUTE ouvert à
--     PUBLIC (le "=X" sans rôle devant), plus anon/authenticated/service_role.
--   * pg_proc.proconfig de lowi_norm_condo(text) = NULL (aucun search_path).
--
-- ⚠ Ne jouer ce fichier que pour revenir en arrière : il ROUVRE la faille par
-- laquelle anon contournait le RLS deny-all via les vues SECURITY DEFINER.

begin;

-- 1. Vues : retour au comportement DEFINER (reloptions NULL)
alter view public.cohort_tension            reset (security_invoker);
alter view public.condos_age                reset (security_invoker);
alter view public.cross_source_duplicates   reset (security_invoker);
alter view public.description_couverture    reset (security_invoker);
alter view public.doublons_agent            reset (security_invoker);
alter view public.khet_stats                reset (security_invoker);
alter view public.listing_benchmarks        reset (security_invoker);
alter view public.listing_matches           reset (security_invoker);
alter view public.listings_sane             reset (security_invoker);
alter view public.opportunites              reset (security_invoker);
alter view public.rent_stats                reset (security_invoker);
alter view public.social_leads_opportunites reset (security_invoker);
alter view public.sold_and_rented           reset (security_invoker);
alter view public.street_stats              reset (security_invoker);
alter view public.yield_by_khet             reset (security_invoker);

-- 2. Grants sur les 26 relations existantes
grant all on all tables in schema public to anon, authenticated;

-- 3. Privilèges par défaut (re-posent les grants sur toute table future)
alter default privileges for role postgres in schema public
  grant all on tables to anon, authenticated;

-- 4. Fonction rls_auto_enable() : EXECUTE rouvert
grant execute on function public.rls_auto_enable() to public;

-- 5. lowi_norm_condo(text) : search_path re-rendu mutable
alter function public.lowi_norm_condo(text) reset search_path;

commit;
