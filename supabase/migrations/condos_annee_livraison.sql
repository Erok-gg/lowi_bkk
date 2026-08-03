-- condos_annee_livraison.sql — remplit `condos.year_built`, à 0 depuis le début.
--
-- C'était le chantier n°1 du projet, et l'information existait déjà : elle est
-- extraite du descriptif (`d_annee_construction`) depuis le 2026-08-02. Il ne
-- manquait que de la remonter à la maille du BÂTIMENT — une année de livraison
-- est une propriété de l'immeuble, pas de l'annonce.
--
-- ═══ ON COMPTE LES SOURCES, PAS LES ANNONCES ═══
--
-- Mesuré le 2026-08-03, et c'est ce qui gouverne tout ce fichier : au sein d'UNE
-- MÊME source, les annonces d'un immeuble s'accordent sur l'année dans **99 à
-- 100 %** des cas (FazWaz 908 immeubles sur 909). Chaque portail lit donc une
-- FICHE PROJET unique : ses N annonces ne sont pas N confirmations, c'est UNE
-- voix répétée. Compter les annonces gonflait la confiance d'un facteur égal au
-- nombre d'annonces — dix-neuf annonces d'une agence pesaient dix-neuf voix.
--
-- Entre sources différentes, l'accord tombe à **57 %**. C'est là qu'est
-- l'information : FazWaz donne 2018 pour Ashton Silom, PropertyScout 2016.
--
-- ═══ INDICATEUR DE CONFIANCE ═══
-- `year_source` ne dit pas d'où vient la valeur, il dit CE QU'ELLE VAUT :
--
--   valide N sources     >= 3 sources concordantes
--   corrobore 2 sources     2 sources concordantes
--   source_unique           1 seule source — invérifiable, pas faux pour autant
--   conflit ...             sources divergentes, aucune majorité de 3 -> NULL
--
-- Une année vue par une seule source n'est pas fausse ; elle est INVÉRIFIABLE,
-- et le référentiel doit le dire plutôt que le taire. C'est la raison d'être de
-- cette colonne : la valeur et sa solidité se lisent séparément.
--
-- ═══ REGROUPEMENT PAR NOM NORMALISÉ ═══
-- Sans lui, « Modiz Vault Kaset Sripatum », « Modiz Vault Kaset-Sripatum, Bangkok »
-- et la variante à espace initial sont TROIS immeubles à une source chacun, et
-- rien ne se corrobore jamais. Normaliser fait passer les immeubles vus par
-- >= 3 sources de 47 à 457.
--
-- ⚠ La normalisation ci-dessous reproduit `normalize._norm_condo` (Python), celui
-- qui produit déjà les `unit_key`. Vérifié le 2026-08-03 sur les **4 731 noms
-- distincts** de la base : **zéro divergence**. Toute modification de l'un des
-- deux DOIT être répercutée sur l'autre et re-vérifiée — une divergence
-- silencieuse créerait des immeubles fantômes.

alter table condos
  add column if not exists nb_etages integer,
  add column if not exists nb_lots   integer,
  add column if not exists promoteur text,
  add column if not exists livre     boolean;

comment on column condos.year_source is
  'INDICATEUR DE CONFIANCE, pas une provenance : valide N sources / corrobore 2 '
  'sources / source_unique / conflit. Une source = un portail, car les annonces '
  'd''un meme portail lisent une fiche projet unique (99-100 % d''accord interne).';

create or replace function lowi_norm_condo(nom text) returns text
language sql immutable as $$
  select trim(regexp_replace(regexp_replace(regexp_replace(
           lower(replace(nom, ',', ' ')),
           '\m(bangkok|condominium|condo|project|residences|residence)\M', ' ', 'g'),
           '[^[:alnum:][:space:]_]', ' ', 'g'), '\s+', ' ', 'g'));
$$;

comment on function lowi_norm_condo is
  'Reproduit normalize._norm_condo (Python). Verifie sur 4731 noms : 0 divergence. '
  'Modifier l''un impose de modifier l''autre ET de re-verifier.';

with par_valeur as (
  -- une ligne par (immeuble, année, nombre de SOURCES qui l''affirment)
  select lowi_norm_condo(condo_name) as k,
         d_annee_construction        as an,
         count(distinct source)      as n_src
  from listings
  where condo_name is not null and d_annee_construction is not null
  group by 1, 2
),
par_immeuble as (
  select lowi_norm_condo(condo_name) as k, count(distinct source) as n_src_tot
  from listings
  where condo_name is not null and d_annee_construction is not null
  group by 1
),
classe as (
  select v.k, v.an, v.n_src, i.n_src_tot,
         count(*)      over (partition by v.k) as n_valeurs,
         row_number()  over (partition by v.k order by v.n_src desc, v.an) as rang,
         -- ex aequo en tête : aucune valeur ne l''emporte, on s''abstient
         count(*) filter (where true) over (partition by v.k, v.n_src) as ex_aequo,
         max(v.n_src)  over (partition by v.k) as tete
  from par_valeur v join par_immeuble i using (k)
),
retenu as (
  select k, an, n_src, n_src_tot, n_valeurs,
         case
           when n_valeurs = 1 and n_src_tot >= 3 then 'valide ' || n_src_tot || ' sources'
           when n_valeurs = 1 and n_src_tot = 2  then 'corrobore 2 sources'
           when n_valeurs = 1                    then 'source_unique'
           when n_src >= 3 and ex_aequo = 1      then 'valide ' || n_src || '/' || n_src_tot || ' sources'
           else 'conflit ' || n_valeurs || ' valeurs / ' || n_src_tot || ' sources'
         end as confiance
  from classe
  where rang = 1 and n_src = tete
)
update condos c
   set year_built  = case when r.confiance like 'conflit%' then null else r.an end,
       year_source = r.confiance,
       year_seen_at = now()
  from retenu r
 where lowi_norm_condo(c.name) = r.k;
