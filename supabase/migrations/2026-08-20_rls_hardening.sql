-- 2026-08-20_rls_hardening.sql
-- Ferme la porte dérobée par laquelle `anon` contournait le RLS des tables.
--
-- LE DÉFAUT, MESURÉ (et non déduit du linter) :
--   Les 15 vues de `public` avaient reloptions = NULL, donc le comportement
--   SECURITY DEFINER par défaut ; elles appartiennent à `postgres`, dont
--   pg_roles.rolbypassrls = true. Une requête `anon` sur une vue s'exécutait
--   donc avec les droits de postgres et ignorait le RLS deny-all des tables.
--   Trois d'entre elles sont en plus auto-updatable (simples SELECT sur une
--   table unique) et anon détenait INSERT/UPDATE/DELETE dessus :
--   listings_sane→listings, condos_age→condos, social_leads_opportunites→social_leads.
--
--   Preuve exécutée le 2026-08-20, en transaction annulée, écriture no-op :
--     set local role anon;
--     update listings_sane set title=title where id='fazwaz:sale:5995772';  -- 1 ligne
--     update listings      set title=title where id='fazwaz:sale:5995772';  -- 0 ligne
--   Même rôle, même ligne, même transaction : la vue laissait passer, la table
--   bloquait. Côté REST, GET /rest/v1/listings renvoyait [] quand
--   GET /rest/v1/listings_sane renvoyait les annonces.
--
-- CE QUI N'EST PAS TOUCHÉ, VOLONTAIREMENT :
--   Les 11 alertes « RLS enabled, no policy » restent après cette migration.
--   C'est le deny-all voulu : l'app et le pipeline se connectent en `postgres`
--   (BYPASSRLS) par la connexion Postgres directe, jamais par PostgREST.
--   Aucune policy n'est donc créée ici — en ajouter une rouvrirait l'accès.
--
-- Retour arrière : 2026-08-20_rollback_rls_hardening.sql (généré depuis l'état
-- live d'avant migration). Aucune donnée n'est modifiée par ce fichier.

begin;

-- 1. LE correctif de fond : chaque vue s'exécute désormais avec les droits de
--    l'APPELANT. anon retombe sur le RLS deny-all ; `postgres` (BYPASSRLS)
--    n'est pas affecté, donc l'app et les agents ne voient aucune différence.
--    Sans cette étape, révoquer les grants ne suffirait pas : la lecture
--    resterait ouverte à quiconque détient la clé anon.
alter view public.cohort_tension            set (security_invoker = true);
alter view public.condos_age                set (security_invoker = true);
alter view public.cross_source_duplicates   set (security_invoker = true);
alter view public.description_couverture    set (security_invoker = true);
alter view public.doublons_agent            set (security_invoker = true);
alter view public.khet_stats                set (security_invoker = true);
alter view public.listing_benchmarks        set (security_invoker = true);
alter view public.listing_matches           set (security_invoker = true);
alter view public.listings_sane             set (security_invoker = true);
alter view public.opportunites              set (security_invoker = true);
alter view public.rent_stats                set (security_invoker = true);
alter view public.social_leads_opportunites set (security_invoker = true);
alter view public.sold_and_rented           set (security_invoker = true);
alter view public.street_stats              set (security_invoker = true);
alter view public.yield_by_khet             set (security_invoker = true);

-- 2. Ceinture ET bretelles : plus aucun droit pour les rôles de l'API REST.
--    Mesuré avant de trancher : la clé anon n'est utilisée NULLE PART dans le
--    code (0 occurrence de supabase-js ou /rest/v1 hors Storage), elle n'est
--    pas déployée sur Vercel, et auth.users = 0 — `authenticated` est un rôle
--    purement théorique ici. Révoquer ne casse donc rien, et met l'API hors
--    d'atteinte même si une policy permissive était ajoutée par erreur un jour.
revoke all on all tables in schema public from anon, authenticated;

-- 3. Sans ceci le trou se rouvre en silence : pg_default_acl accordait
--    anon=arwdDxtm et authenticated=arwdDxtm sur toute table créée par
--    `postgres` dans public — c'est ce défaut qui avait posé les grants de
--    l'étape 2 sur les 26 relations. La prochaine table du pipeline les
--    recevrait à son tour.
alter default privileges for role postgres in schema public
  revoke all on tables from anon, authenticated;

-- 4. Trigger d'événement SECURITY DEFINER : inoffensif en appel direct
--    (Postgres refuse d'exécuter une fonction event_trigger hors contexte),
--    mais exposé sur /rest/v1/rpc/ sans raison.
revoke execute on function public.rls_auto_enable() from public, anon, authenticated;

-- 5. Hygiène. La fonction n'est SECURITY DEFINER ni référencée nulle part
--    (vérifié : aucun index, colonne générée ni vue ne l'utilise), donc
--    risque nul — mais un search_path mutable n'a aucune raison de rester.
alter function public.lowi_norm_condo(text) set search_path = public, pg_temp;

commit;
