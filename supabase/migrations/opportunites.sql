-- opportunites.sql — détection d'écart de prix par cascade de comparaison.
--
-- POURQUOI UNE CASCADE. Comparer une annonce à « la médiane de son immeuble »
-- sans précaution produit des artefacts : le 42 m² de Supalai Icon Sathorn
-- ressortait à -57 % alors que la médiane de l'immeuble reposait sur quatre lots
-- de 44 à 204 m². Il faut donc une base de comparaison à périmètre comparable,
-- et descendre d'un cran seulement quand elle manque.
--
-- DISPERSION MESURÉE (écart p25-p75 du prix/m², juillet 2026) :
--     même immeuble + mêmes chambres ....... 14,9 %   (383 groupes)
--     même immeuble, toutes tailles ........ 16,5 %   (493 immeubles)
--     même khet ............................ 52,2 %   (30 quartiers)
--
-- Deux enseignements qui dictent la conception :
--   1. Ce qui explique le prix, c'est le BÂTIMENT, pas la taille du lot : passer
--      de « mêmes chambres » à « toutes tailles » ne coûte que 1,6 point de
--      bruit, alors que quitter l'immeuble le triple. On épuise donc l'immeuble
--      avant de sortir. (Gradient mesuré 2BR vs 1BR dans un même immeuble :
--      +5,3 % seulement — négligé volontairement.)
--   2. Un seuil fixe n'a pas de sens à tous les niveaux : à 52 % de dispersion,
--      la moitié d'un quartier est mécaniquement « à -15 % ». Le seuil se durcit
--      donc en descendant, et le niveau khet ne déclenche AUCUN signal — il
--      reste du contexte affiché.
--
-- L'annonce évaluée est toujours EXCLUE de sa propre référence (sur 5
-- comparables elle pèserait 20 % de sa propre médiane).

create index if not exists idx_listings_bench
  on listings (condo_name, deal_type, status) where price_per_sqm > 0;

create or replace view listing_benchmarks as
select
  l.id, l.source_url, l.condo_name, l.khet, l.street, l.deal_type,
  l.bedrooms, l.area_sqm, l.price, l.price_per_sqm, l.quota, l.year_built,
  b.niveau, b.n_comparables, b.median_ppsqm, b.p25_ppsqm, b.p75_ppsqm,
  round((l.price_per_sqm / nullif(b.median_ppsqm, 0) - 1) * 100)::int as ecart_pct,
  -- Seuil de signalement, durci à mesure que la comparaison s'éloigne du bien.
  case b.niveau when 'immeuble_chambres' then 15
                when 'immeuble'          then 15
                when 'rue'               then 30 end as seuil_pct,
  -- Confiance : dérive de la proximité du comparable et de la taille d'échantillon.
  case when b.niveau = 'immeuble_chambres' and b.n_comparables >= 8 then 'forte'
       when b.niveau in ('immeuble_chambres', 'immeuble')           then 'moyenne'
       else 'faible' end as confiance
from listings l
cross join lateral (
  -- La cascade : on prend le PREMIER niveau disponible (ordre de priorité),
  -- chacun exigeant au moins 5 comparables pour que la médiane tienne debout.
  select * from (
    -- 1. Même immeuble, mêmes chambres, surface à ±20 %
    select 1 as prio, 'immeuble_chambres' as niveau, count(*)::int as n_comparables,
           percentile_cont(0.5) within group (order by x.price_per_sqm) as median_ppsqm,
           percentile_cont(0.25) within group (order by x.price_per_sqm) as p25_ppsqm,
           percentile_cont(0.75) within group (order by x.price_per_sqm) as p75_ppsqm
    from listings x
    where x.status = 'active' and x.price_per_sqm > 0 and x.id <> l.id
      and x.condo_name = l.condo_name and x.deal_type = l.deal_type
      and x.bedrooms is not distinct from l.bedrooms
      and l.area_sqm > 0 and x.area_sqm between l.area_sqm * 0.8 and l.area_sqm * 1.2
    having count(*) >= 5

    union all
    -- 2. Même immeuble, toutes tailles (ne coûte que 1,6 point de dispersion)
    select 2, 'immeuble', count(*)::int,
           percentile_cont(0.5) within group (order by x.price_per_sqm),
           percentile_cont(0.25) within group (order by x.price_per_sqm),
           percentile_cont(0.75) within group (order by x.price_per_sqm)
    from listings x
    where x.status = 'active' and x.price_per_sqm > 0 and x.id <> l.id
      and x.condo_name = l.condo_name and x.deal_type = l.deal_type
    having count(*) >= 5

    union all
    -- 3. Même rue — dernier recours, seuil durci et confiance dégradée
    select 3, 'rue', count(*)::int,
           percentile_cont(0.5) within group (order by x.price_per_sqm),
           percentile_cont(0.25) within group (order by x.price_per_sqm),
           percentile_cont(0.75) within group (order by x.price_per_sqm)
    from listings x
    where x.status = 'active' and x.price_per_sqm > 0 and x.id <> l.id
      and l.street is not null and x.street = l.street and x.deal_type = l.deal_type
    having count(*) >= 5
  ) niveaux
  order by prio
  limit 1
) b
where l.status = 'active' and l.price_per_sqm > 0;

comment on view listing_benchmarks is
  'Chaque annonce active comparée au meilleur périmètre disponible (immeuble+chambres > immeuble > rue). '
  'Le niveau khet est volontairement absent : à 52 % de dispersion aucun écart n''y est interprétable.';

-- ── Les annonces réellement sous leur marché ────────────────────────────────
-- Filtre : écart au-delà du seuil du niveau, ET sous le premier quartile de son
-- propre ensemble de comparaison (une décote qui reste dans la fourchette
-- normale n'est pas une décote).
create or replace view opportunites as
select
  id, source_url, condo_name, khet, street, deal_type, bedrooms, area_sqm,
  price, price_per_sqm, quota, year_built,
  niveau, n_comparables, median_ppsqm, ecart_pct, seuil_pct, confiance,
  -- Position dans l'ensemble de comparaison : plus lisible et plus auditable
  -- qu'un pourcentage brut, qui masque la taille d'échantillon et la dispersion.
  case when price_per_sqm <= p25_ppsqm then 'sous le 1er quartile'
       else 'sous la médiane' end as position
from listing_benchmarks
where ecart_pct <= -seuil_pct
  and price_per_sqm <= p25_ppsqm
order by
  case confiance when 'forte' then 1 when 'moyenne' then 2 else 3 end,
  ecart_pct;

comment on view opportunites is
  'Annonces sous leur marché de référence. Un écart n''est PAS une opportunité : '
  'il faut vérifier étage, vue, état et quota étranger. Le niveau et la confiance '
  'doivent toujours être affichés à côté du pourcentage.';
