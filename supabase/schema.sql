-- schema.sql — Schéma Postgres (Supabase) du projet Bangkok Map.
-- La partie LOCALE (scraper) utilise un SQLite qui reflète ce schéma
-- (scraper/store/sqlite_store.py). Demain : appliquer ce fichier sur Supabase.

-- ───────────────────────────── listings ─────────────────────────────
create table if not exists listings (
  id            text primary key,            -- ex: "fazwaz:6147844"
  source        text not null,               -- "fazwaz", "ddproperty", ...
  source_url    text not null,
  title         text,
  deal_type     text check (deal_type in ('sale','rent')),
  quota         text check (quota in ('foreigner','thai')),
  tenure        text default 'freehold',   -- freehold uniquement (leasehold écarté au scrape)
  price         numeric,
  currency      text default 'THB',
  area_sqm      numeric,
  price_per_sqm numeric,
  bedrooms      integer,
  bathrooms     integer,
  condo_name    text,
  address_raw   text,
  khet          text,                         -- quartier (district)
  khwaeng       text,                         -- sous-district
  street        text,
  lat           double precision,
  lng           double precision,
  status        text not null default 'active' check (status in ('active','inactive','sold')),
  first_seen    timestamptz not null default now(),
  last_seen     timestamptz not null default now(),
  delisted_at   timestamptz,                  -- date de passage inactive/sold (délistage)
  raw_data      jsonb
);
create index if not exists idx_listings_khet   on listings (khet);
create index if not exists idx_listings_status on listings (status);
create index if not exists idx_listings_source on listings (source);

-- ──────────────────────────── images ────────────────────────────────
create table if not exists listing_images (
  id           bigserial primary key,
  listing_id   text not null references listings(id) on delete cascade,
  storage_path text not null,                 -- chemin Supabase Storage / local
  width        integer,
  height       integer,
  ord          integer default 0
);
create index if not exists idx_images_listing on listing_images (listing_id);

-- ──────────────────────────── amenities ─────────────────────────────
create table if not exists listing_amenities (
  id         bigserial primary key,
  listing_id text not null references listings(id) on delete cascade,
  name       text not null
);
create index if not exists idx_amenities_listing on listing_amenities (listing_id);

-- ──────────────────────────── price_history ─────────────────────────
create table if not exists price_history (
  id          bigserial primary key,
  listing_id  text not null references listings(id) on delete cascade,
  price       numeric not null,
  observed_at timestamptz not null default now()
);
create index if not exists idx_pricehist_listing on price_history (listing_id);

-- ──────────────────────────── scan_runs ─────────────────────────────
create table if not exists scan_runs (
  id            bigserial primary key,
  started_at    timestamptz not null default now(),
  finished_at   timestamptz,
  source        text not null,
  scanned_count integer default 0,
  new_count     integer default 0,
  removed_count integer default 0,
  changed_count integer default 0,
  notes         text
);

-- ──────────────────────────── pois ──────────────────────────────────
create table if not exists pois (
  id        bigserial primary key,
  category  text not null,
  name_en   text,
  name_th   text,
  lat       double precision,
  lng       double precision,
  khet      text
);

-- ─────────────────────── vues agrégées (stats) ──────────────────────
create or replace view khet_stats as
select
  khet,
  count(*) filter (where status = 'active')                              as active_count,
  round(avg(price_per_sqm) filter (where status = 'active'))             as avg_price_per_sqm,
  percentile_cont(0.5) within group (order by price_per_sqm)
    filter (where status = 'active')                                     as median_price_per_sqm
from listings
where khet is not null
group by khet;

create or replace view street_stats as
select
  street,
  count(*) filter (where status = 'active')                  as active_count,
  round(avg(price_per_sqm) filter (where status = 'active')) as avg_price_per_sqm
from listings
where street is not null
group by street;

-- Doublons inter-plateformes (mêmes biens sur 2 sources) — paires candidates.
create or replace view cross_source_duplicates as
select
  a.id as id_a, a.source as source_a, a.condo_name as name_a,
  b.id as id_b, b.source as source_b, b.condo_name as name_b,
  a.bedrooms, a.area_sqm as area_a, b.area_sqm as area_b,
  a.price as price_a, b.price as price_b, a.khet,
  round((abs(a.lat - b.lat) + abs(a.lng - b.lng))::numeric, 5) as coord_delta
from listings a
join listings b
  on a.source < b.source
 and a.status = 'active' and b.status = 'active'
 and a.lat is not null and b.lat is not null
 and abs(a.lat - b.lat) < 0.0015 and abs(a.lng - b.lng) < 0.0015
 and coalesce(a.bedrooms, -1) = coalesce(b.bedrooms, -1)
 and (a.area_sqm is null or b.area_sqm is null
      or abs(a.area_sqm - b.area_sqm) <= greatest(a.area_sqm, b.area_sqm) * 0.15);

-- Snapshots par quartier (séries temporelles, comparaison par date).
-- deal_type sépare vente/location pour la carte de TENSION (lib/tension.ts).
create table if not exists khet_snapshots (
  id                   bigserial primary key,
  taken_at             timestamptz not null default now(),
  khet                 text not null,
  deal_type            text check (deal_type in ('sale','rent')),
  active_count         integer,
  avg_price_per_sqm    numeric,
  median_price_per_sqm numeric
);
-- Migration (bases déjà créées avant l'ajout de deal_type) :
--   alter table khet_snapshots add column if not exists deal_type text;
create index if not exists idx_khet_snapshots_khet on khet_snapshots (khet, deal_type);
