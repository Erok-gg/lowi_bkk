-- unit_key_photo_sig.sql — suivre des COHORTES plutôt que des annonces,
-- et reconnaître les republications par l'empreinte photo.
--
-- PROBLÈME. Les agents suppriment et republient massivement leurs annonces
-- (mesuré sur l'archive : 7 470 paires « délistée → identique réapparue »,
-- dont 3 015 en moins de 7 jours). Au niveau de l'annonce, un repost est
-- indiscernable d'une vraie disparition suivie d'une vraie nouvelle offre :
-- l'ancienne URL est authentiquement morte. Les indicateurs bâtis sur la durée
-- de vie d'une annonce sont donc structurellement faux, et aucun réglage de
-- seuil de délistage n'y change quoi que ce soit.
--
-- SOLUTION. Changer d'unité d'analyse : la COHORTE
-- (immeuble × chambres × tranche de surface de 5 m² × type de transaction).
-- Un repost retombe dans la même cohorte → le stock ne bouge pas → correctement
-- lu comme « aucune absorption ». Une vraie absorption fait baisser le stock
-- durablement : c'est le signal de tension.
--
-- ⚠ Une cohorte peut contenir plusieurs lots réellement distincts (dix 45 m²
-- identiques dans une tour). Ce n'est PAS un compteur de biens uniques, mais la
-- bonne maille pour suivre l'écoulement de l'offre et comparer à périmètre égal.

alter table listings add column if not exists unit_key text;
alter table listings add column if not exists year_built integer;
-- Empreinte photo : poids des fichiers (octets) relevés par requête HEAD, sans
-- téléchargement ni stockage. Un agent qui republie réutilise les mêmes fichiers.
alter table listings add column if not exists photo_count integer;
alter table listings add column if not exists photo_sizes integer[];
alter table listings add column if not exists repost_of text;   -- id de l'annonce d'origine
alter table listings add column if not exists repost_reason text;

create index if not exists idx_listings_unit  on listings (unit_key);
create index if not exists idx_listings_repost on listings (repost_of) where repost_of is not null;

comment on column listings.unit_key is
  'Cohorte immeuble×chambres×tranche 5 m²×type. Unité d''analyse à la place de l''annonce : robuste aux republications.';
comment on column listings.photo_sizes is
  'Poids en octets des photos (HEAD, sans téléchargement). Deux annonces partageant ≥2 poids à 10 % près décrivent le même lot.';

-- ── Instantané du stock par cohorte ────────────────────────────────────────
-- C'est CETTE série qui mesure la tension, pas la durée de vie des annonces.
create table if not exists cohort_snapshots (
  id           bigserial primary key,
  taken_at     timestamptz not null default now(),
  unit_key     text not null,
  condo_name   text,
  khet         text,
  deal_type    text,
  bedrooms     integer,
  area_bucket  integer,
  active_count integer not null,          -- stock de la cohorte à cette date
  median_price numeric,
  min_price    numeric,
  max_price    numeric
);
create index if not exists idx_cohort_snap_key  on cohort_snapshots (unit_key, taken_at desc);
create index if not exists idx_cohort_snap_date on cohort_snapshots (taken_at desc);

comment on table cohort_snapshots is
  'Stock actif par cohorte à chaque scan. Un repost ne modifie pas le stock (une annonce meurt, une autre naît dans la même cohorte) : la variation mesure donc une vraie absorption.';

-- Variation du stock entre les deux derniers relevés d'une cohorte.
create or replace view cohort_tension as
with derniers as (
  select unit_key, condo_name, khet, deal_type, bedrooms, area_bucket,
         active_count, median_price, taken_at,
         row_number() over (partition by unit_key order by taken_at desc) rn
  from cohort_snapshots
)
select
  a.unit_key, a.condo_name, a.khet, a.deal_type, a.bedrooms, a.area_bucket,
  a.active_count            as stock_actuel,
  b.active_count            as stock_precedent,
  a.active_count - b.active_count as variation,
  a.median_price, a.taken_at
from derniers a
join derniers b on b.unit_key = a.unit_key and b.rn = 2
where a.rn = 1;
