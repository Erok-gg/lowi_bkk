-- backfill_unit_key.sql — calcule unit_key sur l'historique déjà en base.
--
-- unit_key se déduit de champs déjà présents (condo_name, bedrooms, area_sqm,
-- deal_type) : aucun re-scrape n'est nécessaire. Sans ce remplissage, les
-- instantanés de cohorte ne capteraient rien et la série temporelle de tension
-- ne démarrerait qu'au prochain scan.
--
-- La normalisation doit rester alignée sur pipeline/normalize.py (_norm_condo) :
-- minuscules, retrait des mots vides (bangkok/condo/project/residence),
-- ponctuation supprimée, espaces réduits ; puis chambres et tranche de 5 m².

update listings set unit_key =
  trim(regexp_replace(
    regexp_replace(
      regexp_replace(lower(condo_name),
        '\y(bangkok|condominium|condo|project|residences|residence)\y', ' ', 'g'),
      '[^[:alnum:][:space:]]', ' ', 'g'),
    '\s+', ' ', 'g'))
  || '|' || coalesce(bedrooms, -1)::text
  || '|' || coalesce((round(area_sqm / 5) * 5)::int, 0)::text
  || '|' || coalesce(deal_type, '?')
where condo_name is not null
  and trim(condo_name) <> ''
  and unit_key is null;
