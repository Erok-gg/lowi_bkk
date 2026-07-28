-- plausibilite.sql — BORNES DE PLAUSIBILITÉ côté SQL, et opportunités assainies.
--
-- PROBLÈME MESURÉ (2026-07-28). La vue `opportunites` n'avait aucun garde-fou
-- sur le prix ni sur la surface. Ses premiers résultats, c'est-à-dire ce qu'un
-- utilisateur regarde en premier, étaient donc des DÉFAUTS DE SOURCE :
--
--   NOBLE STATE 39        sale  35 m²   27 000 THB   écart -100 %
--   Ideo Q Sukhumvit 36   sale  46 m²   40 000 THB   écart -100 %
--   The Tempo Ruamrudee   rent  3 757 m² pour 1 BR   écart  -99 %
--
-- Les deux premières sont des LOCATIONS mal classées en vente ; la troisième
-- porte la surface du PROJET dans le champ du lot. Relevé sur le stock actif :
-- 28 annonces « vente » entre 5 k et 200 k THB, 60 surfaces > 500 m², 8 < 15 m².
-- Un écart de -100 % ne désigne jamais une affaire : il désigne une donnée fausse.
--
-- CHOIX DE CONCEPTION. Les bornes sont dupliquées ici et dans
-- lib/market-bounds.ts (TypeScript), et elles DOIVENT rester alignées. On aurait
-- pu ne les tenir qu'à un seul endroit en filtrant côté application, mais les
-- vues SQL sont consommées directement (psql, exports, étude) : une vue qui ne
-- se protège pas elle-même finit toujours par être lue sans son filtre.
--
--   vente  :   800 000 .. 100 000 000 THB
--   loyer  :     3 000 ..    500 000 THB
--   surface:        15 ..        500 m²

create or replace view listings_sane as
select *
from listings
where price is not null
  and (area_sqm is null or area_sqm between 15 and 500)
  and (
    (deal_type = 'sale' and price between 800000 and 100000000)
    or
    (deal_type = 'rent' and price between 3000 and 500000)
  );

comment on view listings_sane is
  'Annonces dont le prix et la surface sont plausibles. Périmètre de TOUTE statistique '
  '(médiane, décote, tension). Bornes alignées sur lib/market-bounds.ts — les modifier '
  'des deux côtés. Rien n''est supprimé : `listings` reste la donnée brute.';

-- ── Reconstruction de la cascade sur le périmètre assaini ───────────────────
-- Seul changement de fond : `listings` devient `listings_sane` des deux côtés
-- (l'annonce évaluée ET ses comparables). La logique de cascade, les seuils et
-- les niveaux sont inchangés — cf. opportunites.sql pour leur justification et
-- les dispersions mesurées qui les motivent.

create index if not exists idx_listings_street
  on listings (street, deal_type, status) where price_per_sqm > 0;

create or replace view listing_benchmarks as
select
  l.id, l.source_url, l.condo_name, l.khet, l.street, l.deal_type,
  l.bedrooms, l.area_sqm, l.price, l.price_per_sqm, l.quota, l.year_built,
  b.niveau, b.n_comparables, b.median_ppsqm, b.p25_ppsqm, b.p75_ppsqm,
  round((l.price_per_sqm / nullif(b.median_ppsqm, 0) - 1) * 100)::int as ecart_pct,
  case b.niveau when 'immeuble_chambres' then 15
                when 'immeuble'          then 15
                when 'rue'               then 30 end as seuil_pct,
  case when b.niveau = 'immeuble_chambres' and b.n_comparables >= 8 then 'forte'
       when b.niveau in ('immeuble_chambres', 'immeuble')           then 'moyenne'
       else 'faible' end as confiance
from listings_sane l
cross join lateral (
  select * from (
    -- 1. Même immeuble, mêmes chambres, surface à ±20 %
    select 1 as prio, 'immeuble_chambres' as niveau, count(*)::int as n_comparables,
           percentile_cont(0.5) within group (order by x.price_per_sqm) as median_ppsqm,
           percentile_cont(0.25) within group (order by x.price_per_sqm) as p25_ppsqm,
           percentile_cont(0.75) within group (order by x.price_per_sqm) as p75_ppsqm
    from listings_sane x
    where x.status = 'active' and x.price_per_sqm > 0 and x.id <> l.id
      and x.condo_name = l.condo_name and x.deal_type = l.deal_type
      and x.bedrooms is not distinct from l.bedrooms
      and l.area_sqm > 0 and x.area_sqm between l.area_sqm * 0.8 and l.area_sqm * 1.2
    having count(*) >= 5

    union all
    -- 2. Même immeuble, toutes tailles
    select 2, 'immeuble', count(*)::int,
           percentile_cont(0.5) within group (order by x.price_per_sqm),
           percentile_cont(0.25) within group (order by x.price_per_sqm),
           percentile_cont(0.75) within group (order by x.price_per_sqm)
    from listings_sane x
    where x.status = 'active' and x.price_per_sqm > 0 and x.id <> l.id
      and x.condo_name = l.condo_name and x.deal_type = l.deal_type
    having count(*) >= 5

    union all
    -- 3. Même rue — dernier recours, seuil durci et confiance dégradée
    select 3, 'rue', count(*)::int,
           percentile_cont(0.5) within group (order by x.price_per_sqm),
           percentile_cont(0.25) within group (order by x.price_per_sqm),
           percentile_cont(0.75) within group (order by x.price_per_sqm)
    from listings_sane x
    where x.status = 'active' and x.price_per_sqm > 0 and x.id <> l.id
      and l.street is not null and x.street = l.street and x.deal_type = l.deal_type
    having count(*) >= 5
  ) niveaux
  order by prio
  limit 1
) b
where l.status = 'active' and l.price_per_sqm > 0;

comment on view listing_benchmarks is
  'Chaque annonce active comparée au meilleur périmètre disponible (immeuble+chambres > '
  'immeuble > rue), sur le périmètre assaini `listings_sane`. Le niveau khet est '
  'volontairement absent : à 52 % de dispersion aucun écart n''y est interprétable.';

create or replace view opportunites as
select
  id, source_url, condo_name, khet, street, deal_type, bedrooms, area_sqm,
  price, price_per_sqm, quota, year_built,
  niveau, n_comparables, median_ppsqm, ecart_pct, seuil_pct, confiance,
  case when price_per_sqm <= p25_ppsqm then 'sous le 1er quartile'
       else 'sous la médiane' end as position
from listing_benchmarks
where ecart_pct <= -seuil_pct
  and price_per_sqm <= p25_ppsqm
order by
  case confiance when 'forte' then 1 when 'moyenne' then 2 else 3 end,
  ecart_pct;

comment on view opportunites is
  'Annonces sous leur marché de référence, prix et surfaces plausibles uniquement. '
  'Un écart n''est PAS une opportunité : il faut vérifier étage, vue, état et quota '
  'étranger. Le niveau et la confiance doivent toujours être affichés à côté du pourcentage.';
