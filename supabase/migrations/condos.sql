-- condos.sql — référentiel des IMMEUBLES, distinct des annonces.
--
-- POURQUOI : l'année de livraison, les coordonnées, le nombre d'étages sont des
-- propriétés du BÂTIMENT, pas de l'annonce. Les stocker sur `listings` obligerait
-- à les redécouvrir à chaque nouvelle annonce et produirait des valeurs
-- divergentes pour un même immeuble. Une table dédiée = une recherche par condo
-- (≈3 700) au lieu d'une par annonce (≈34 000), et l'information vaut ensuite
-- pour toutes les annonces passées et futures du même bâtiment.
--
-- L'année de livraison est la donnée manquante la plus structurante pour une
-- stratégie d'achat-revente à 5-10 ans : la courbe de dépréciation d'un condo
-- thaï est raide sur la première décennie, et sans l'âge aucun modèle de
-- valorisation n'est credible.

create table if not exists condos (
  name           text primary key,        -- nom canonique, = listings.condo_name
  name_normalized text,                   -- forme normalisée (rapprochement social_leads)
  khet           text,
  lat            double precision,
  lng            double precision,

  -- ── Caractéristiques du bâtiment ─────────────────────────────────────────
  year_built     integer check (year_built between 1970 and 2040),
  year_source    text check (year_source in ('ddproperty','fazwaz','propertyscout','nestopa','manual')),
  year_seen_at   timestamptz,             -- quand l'année a été relevée

  -- ── Agrégats recalculables (confort de lecture, pas source de vérité) ─────
  n_listings     integer default 0,
  n_sale         integer default 0,
  n_rent         integer default 0,
  first_seen     timestamptz default now(),
  last_seen      timestamptz default now()
);

create index if not exists idx_condos_khet on condos (khet);
create index if not exists idx_condos_year on condos (year_built);
create index if not exists idx_condos_norm on condos (name_normalized);

comment on table condos is
  'Référentiel des immeubles. Une ligne par projet, alimentée par les annonces. '
  'L''année de livraison vient des fiches (DDproperty: project.metaByType.verified.completionYear ; '
  'FazWaz: "Completed (Mois AAAA)") et ne se redécouvre pas à chaque annonce.';

-- Amorçage depuis les annonces existantes : on crée la ligne de chaque immeuble
-- connu, avec ses coordonnées moyennes. year_built reste NULL tant qu'il n'a pas
-- été relevé (par le scrape courant ou le backfill).
insert into condos (name, khet, lat, lng, n_listings, n_sale, n_rent)
select
  condo_name,
  (array_agg(khet order by last_seen desc) filter (where khet is not null))[1],
  avg(lat), avg(lng),
  count(*),
  count(*) filter (where deal_type = 'sale'),
  count(*) filter (where deal_type = 'rent')
from listings
where condo_name is not null and trim(condo_name) <> ''
group by condo_name
on conflict (name) do update set
  n_listings = excluded.n_listings,
  n_sale     = excluded.n_sale,
  n_rent     = excluded.n_rent,
  lat        = coalesce(condos.lat, excluded.lat),
  lng        = coalesce(condos.lng, excluded.lng),
  khet       = coalesce(condos.khet, excluded.khet),
  last_seen  = now();

-- Âge du bâtiment au moment de la lecture : une vue plutôt qu'une colonne,
-- pour qu'il ne se périme jamais.
create or replace view condos_age as
select
  name, khet, year_built,
  case when year_built is not null
       then extract(year from now())::int - year_built end as age_ans,
  n_listings, n_sale, n_rent, lat, lng
from condos;
