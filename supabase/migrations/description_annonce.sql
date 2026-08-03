-- description_annonce.sql — capture du descriptif libre des annonces
--
-- Constat du 2026-07-31 : aucune matière textuelle n'était stockée. Vérifié :
--     select count(*) filter (where raw_data ? 'description') from listings;  -- 0
-- sur les quatre sources. `raw_data` ne portait que des scalaires (prix,
-- chambres, nom d'immeuble, district).
--
-- Conséquence mesurée : l'étage d'analyse locale n'avait rien à lire. Un modèle
-- qui ne voit que des nombres ne fait que refaire du SQL, en moins fiable — la
-- campagne du 2026-07-31 a montré 92 % de justesse sur des paires que le SQL
-- tranche déjà gratuitement, et 0 % d'abstention sur celles qu'il ne tranche pas.
-- Le descriptif est ce qui donne au modèle local un travail que le SQL ne sait
-- pas faire : motif de vente, urgence, rénovation, vue, étage, meublé.
--
-- NON RÉTROACTIF : les ~35 800 annonces déjà en base resteront à NULL. Seuls les
-- scraps postérieurs à cette migration renseigneront la colonne.

alter table listings add column if not exists description text;

comment on column listings.description is
  'Descriptif libre de l''annonce, nettoyé et tronqué à 4000 caractères. '
  'Capturé depuis le 2026-07-31 — NULL sur tout l''historique antérieur. '
  'Source : blob structuré de la fiche, sinon ld+json, sinon meta description.';

-- Index de recherche plein texte : sert aux sondes de l'agent `organize` et aux
-- futures classifications (motif de vente, urgence). GIN sur to_tsvector plutôt
-- que trigram : on cherche des mots, pas des sous-chaînes.
create index if not exists idx_listings_description_fts
  on listings using gin (to_tsvector('simple', coalesce(description, '')));

-- Couverture : à surveiller après chaque scrape. Une source qui reste à 0 %
-- signale un extracteur muet, pas une absence de descriptif côté site.
create or replace view description_couverture as
select source,
       count(*)                                             as annonces,
       count(description)                                   as avec_description,
       round(100.0 * count(description) / nullif(count(*), 0), 1) as pct,
       round(avg(length(description))::numeric)             as longueur_moyenne
from listings
where status = 'active'
group by source
order by annonces desc;

comment on view description_couverture is
  'Taux de capture du descriptif par source. Un 0 % persistant après un scrape '
  'complet est une panne d''extraction, à traiter comme telle.';
