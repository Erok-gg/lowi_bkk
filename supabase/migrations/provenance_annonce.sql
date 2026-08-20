-- provenance_annonce.sql — QUI publie une annonce, et QUAND, d'après la source.
--
-- POURQUOI. La revue du 2026-07-28 a relevé 1 399 annonces actives « en doublon
-- exact » (même immeuble, type, chambres, surface, prix). Inspectées une à une,
-- elles ne sont PAS ce que le compte laissait croire :
--
--   The Line Vibe, 1BR 37 m² à 22 000 THB  → 28 annonces, 28 identifiants DDproperty
--   Hampton Residence Thonglor, 1BR 32 m²  → 14 annonces, identifiants FazWaz
--                                             CONSÉCUTIFS (u6548791 … u6548800)
--
-- Des identifiants d'unité consécutifs chez la source, ce sont des LOTS
-- DISTINCTS versés en lot par une agence — un immeuble neuf dont tous les 32 m²
-- se louent au même prix. Les fusionner effacerait de l'offre réelle, c'est-à-dire
-- précisément ce que la pression vendeuse doit compter.
--
-- La question « plusieurs lots, ou plusieurs annonces du même lot ? » n'est donc
-- PAS décidable avec les champs qu'on collectait. Elle le devient avec l'agent :
-- deux annonces identiques du MÊME agent sont un doublon ; les mêmes venant
-- d'agences concurrentes sont deux mises en marché, voire deux lots.
--
-- Ces champs étaient déjà dans le blob `__NEXT_DATA__` que l'adaptateur parse —
-- ils étaient simplement ignorés.
--
-- BÉNÉFICE PRINCIPAL, INDÉPENDANT DE LA DÉDUP : `posted_at`. C'est la date de
-- mise en ligne annoncée par le site. `first_seen` ne dit que le moment où NOTRE
-- scan a croisé l'annonce : tout time-on-market qui en découle est borné par la
-- cadence de scan — le défaut de fond derrière le délai de grâce, l'option
-- `reliableDelistingSince` et la contamination de l'absorption. `posted_at`
-- attaque la cause plutôt que les symptômes.

alter table listings add column if not exists agent_id       text;
alter table listings add column if not exists agency_id      text;
alter table listings add column if not exists posted_at      timestamptz;
alter table listings add column if not exists is_auto_repost boolean;

create index if not exists idx_listings_agent  on listings (agent_id) where agent_id is not null;
create index if not exists idx_listings_posted on listings (posted_at) where posted_at is not null;

comment on column listings.agent_id is
  'Identifiant de l''agent chez la source. Rend décidable « doublon » contre « lots distincts » : '
  'même agent + mêmes caractéristiques = doublon ; agences différentes = deux mises en marché.';
comment on column listings.posted_at is
  'Date de mise en ligne annoncée par la SOURCE (DDproperty : postedOn.unix). '
  'Time-on-market réel, contrairement à first_seen qui est borné par la cadence de scan.';
comment on column listings.is_auto_repost is
  'Republication automatique signalée par le site lui-même (DDproperty : products.isAutoRepost).';

-- ── Doublons AVÉRÉS : même agent, mêmes caractéristiques ────────────────────
-- Vue de diagnostic, volontairement PAS branchée sur les statistiques : tant que
-- `agent_id` n'est pas rempli (au prochain scrape), elle est vide. C'est le
-- comportement voulu — mieux vaut ne rien fusionner que fusionner à tort.
create or replace view doublons_agent with (security_invoker = true) as
select
  agent_id, condo_name, deal_type, bedrooms, area_sqm, price,
  count(*)                        as n_annonces,
  min(coalesce(posted_at, first_seen)) as plus_ancienne,
  array_agg(id order by coalesce(posted_at, first_seen)) as ids
from listings
where status = 'active' and agent_id is not null and condo_name is not null
group by agent_id, condo_name, deal_type, bedrooms, area_sqm, price
having count(*) > 1;

comment on view doublons_agent is
  'Annonces actives strictement identiques publiées par LE MÊME agent : doublons avérés. '
  'Vide tant que agent_id n''est pas collecté. La plus ancienne est la canonique.';
