-- social_leads — annonces immobilières issues des réseaux sociaux (Facebook,
-- WhatsApp), collectées par agent2_scraper et extraites par le modèle local.
--
-- POURQUOI UNE TABLE SÉPARÉE DE `listings` :
-- ces données sont DÉCLARATIVES et NON VÉRIFIÉES (texte libre saisi par des
-- vendeurs, souvent tronqué, parfois faux, avec beaucoup de doublons). Les
-- injecter dans `listings` contaminerait khet_stats, les médianes par condo et
-- les rendements — c'est-à-dire précisément ce qui fait la valeur de Lowi.
-- Ici on constitue un vivier de PISTES à vérifier ; la promotion vers
-- `listings` reste un geste manuel, après contrôle.

create table if not exists social_leads (
  id              text primary key,        -- "facebook:<group_id>:<hash_contenu>"
  source          text not null,           -- 'facebook' | 'whatsapp'
  source_group    text,                    -- id ou nom du groupe
  source_url      text,                    -- lien vers le post
  posted_at       timestamptz,             -- date du post (décodée du timestamp)
  author          text,

  -- ── Données extraites de l'annonce ────────────────────────────────────────
  deal_type       text check (deal_type in ('sale','rent','sale_and_rent','wanted','other')),
  property_type   text check (property_type in ('condo','house','townhouse','land','commercial','unknown')),
  price           numeric,                 -- prix de vente THB
  rent_monthly    numeric,                 -- loyer mensuel THB
  area_sqm        numeric,
  bedrooms        integer,
  bathrooms       integer,
  condo_name_raw  text,                    -- nom tel qu'écrit dans l'annonce
  station         text,                    -- station BTS/MRT citée
  district_raw    text,
  furnished       boolean,

  -- ── Les deux critères décisifs pour un acheteur étranger ─────────────────
  -- seller_type : 'owner' = vente/location en direct propriétaire. C'est là que
  -- se trouvent les décotes ; les agences alignent leurs prix sur le marché.
  seller_type     text not null default 'unknown'
                  check (seller_type in ('owner','agent','unknown')),
  -- quota : un étranger ne peut détenir en pleine propriété que dans la limite
  -- de 49 % de la surface d'un immeuble. Sans quota étranger disponible, le
  -- bien n'est pas achetable en direct (il faut passer par un bail ou une
  -- structure). 'unknown' est la valeur honnête par défaut : la majorité des
  -- annonces ne le précisent pas, et on ne le déduit JAMAIS.
  quota           text not null default 'unknown'
                  check (quota in ('foreigner','thai','unknown')),

  -- ── Rapprochement avec le référentiel Lowi ───────────────────────────────
  condo_name      text,                    -- nom canonique dans `listings`
  match_score     numeric,                 -- 1 = exact, sinon similarité (≥0,86)
  khet            text,
  lat             double precision,
  lng             double precision,

  -- ── Signaux calculés ─────────────────────────────────────────────────────
  median_rent_condo numeric,               -- médiane du MÊME immeuble
  median_sale_condo numeric,
  deviation_pct     numeric,               -- écart au marché de l'immeuble (négatif = dessous)
  confidence        integer check (confidence between 1 and 5),

  raw_text        text,                    -- texte original, pour vérification
  status          text not null default 'new'
                  check (status in ('new','reviewed','promoted','rejected','duplicate')),
  first_seen      timestamptz not null default now(),
  last_seen       timestamptz not null default now()
);

create index if not exists idx_social_condo   on social_leads (condo_name);
create index if not exists idx_social_deal    on social_leads (deal_type);
create index if not exists idx_social_seller  on social_leads (seller_type);
create index if not exists idx_social_quota   on social_leads (quota);
create index if not exists idx_social_status  on social_leads (status);
create index if not exists idx_social_posted  on social_leads (posted_at desc);

-- ── Vue de travail : les pistes qui méritent un coup d'œil ──────────────────
-- Filtre volontairement conservateur : on ne remonte que ce qui est
-- rapproché d'un immeuble connu ET sous le marché de CE MÊME immeuble.
-- ⚠ La médiane par immeuble ne contrôle pas la taille du lot : un studio dans
-- une tour dont la médiane est tirée par des 2-3 chambres ressort à -60 % sans
-- être une affaire. D'où le tri par surface renseignée, et la comparaison par
-- strate (cf. lib/yields.ts) à appliquer avant toute conclusion.
create or replace view social_leads_opportunites as
select
  id, source_url, posted_at, author,
  deal_type, condo_name, khet, station,
  price, rent_monthly, area_sqm, bedrooms,
  median_sale_condo, median_rent_condo, deviation_pct,
  seller_type, quota, confidence,
  case
    when seller_type = 'owner' and quota = 'foreigner' then 'prioritaire'
    when seller_type = 'owner'                        then 'proprio direct'
    when quota = 'foreigner'                          then 'quota etranger'
    else 'standard'
  end as interet
from social_leads
where status = 'new'
  and condo_name is not null
  and deviation_pct is not null
  and deviation_pct < -15
  and area_sqm > 0            -- sans surface, l'écart n'est pas interprétable
order by
  (seller_type = 'owner') desc,
  (quota = 'foreigner') desc,
  deviation_pct asc;
