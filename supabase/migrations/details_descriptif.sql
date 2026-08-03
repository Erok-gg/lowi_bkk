-- details_descriptif.sql — 19 attributs extraits du DESCRIPTIF des annonces.
--
-- ⚠ NON APPLIQUÉE au 2026-08-02. Les données vivent d'abord dans la base de test
--   (tests-scrap/2026-08-01-COMPLET/bangkok.db) le temps d'être éprouvées.
--   À la réconciliation, appliquer CE fichier ET ajouter les 19 colonnes à
--   `_COLS` dans scraper/store/supabase_store.py — les deux vont ensemble,
--   sinon le prochain scrap en ligne échoue sur une colonne inconnue.
--
-- ORIGINE. Analyse de 500 descriptifs réels le 2026-08-02 : chez FazWaz (63 %)
-- et PropertyScout (9 %), le descriptif n'est pas de la prose mais un TABLEAU
-- DE SPECS rendu en texte. Les valeurs s'y lisent par motif (scraper/pipeline/
-- details.py), sans interprétation.
--
-- Comparé à qwen3:8b sur les mêmes 500 : 7 champs sur 8 à 97-100 % d'accord,
-- pour 6 s/annonce contre un temps nul. Et sur les 288 cas où le modèle
-- répondait là où la regex se taisait, 266 étaient des inventions (92 %).
-- L'extraction reste donc déterministe.
--
-- CE QUE ÇA DÉBLOQUE, mesuré sur l'échantillon :
--   d_annee_construction  77 % — la base est à 0 %, c'était le chantier n°1
--   d_quota               25 % — la base est à 1,2 %
--   d_cam_fee_thb         24 % — charges de copropriété, absentes de la base
--   d_publie_par          59 % — propriétaire direct vs agence. FazWaz SEUL.
--                                Vérifié le 2026-08-02 : les identifiants d'unité
--                                des annonces « Private Owner » ne forment une
--                                grappe que dans 4,3 % des cas, contre 18,2 %
--                                pour « agent » à effectif égal (200 tirages).
--                                Le champ dit donc « pas un dépôt groupé
--                                d'agence » — il ne dit RIEN du nombre de lots
--                                détenus : un propriétaire thaï peut en avoir
--                                plus de cent. Il n'écarte donc pas un doublon
--                                à lui seul.
--   d_livre               84 % — meilleure couverture de tous les champs.
--   d_batiment             6 % — tour au sein de la résidence (A, B, 2). Rare,
--                                mais c'est un discriminant SÛR de doublon.
--   d_tarif_regime        11 % — électricité/eau au tarif public ou à celui du
--                                bailleur. Une seule colonne pour les deux
--                                fluides : régimes identiques dans 1 445 cas
--                                sur 1 451.

alter table listings
  add column if not exists d_etage              integer,
  add column if not exists d_cam_fee_thb        numeric,
  add column if not exists d_meuble             text,
  add column if not exists d_vues               jsonb,
  -- Nombre de vues DÉGAGÉES. « Blocked View » (284 annonces) reste dans d_vues
  -- pour l'information mais ne compte pas : ce serait une anti-vue comptée
  -- comme un atout.
  add column if not exists d_vues_n             integer,
  add column if not exists d_batiment           text,
  add column if not exists d_elec_kwh           numeric,
  add column if not exists d_eau_m3             numeric,
  add column if not exists d_tarif_regime       text,
  add column if not exists d_quota              text,
  add column if not exists d_proprietaire       text,
  add column if not exists d_animaux_ok         boolean,
  add column if not exists d_publie_par         text,
  add column if not exists d_annee_construction integer,
  -- Immeuble LIVRÉ ou non. L'année seule ne suffit pas : un « 2028 » nu se lit
  -- comme une construction passée.
  add column if not exists d_livre              boolean,
  add column if not exists d_promoteur          text,
  add column if not exists d_duree_min_mois     integer,
  add column if not exists d_landmark           jsonb,
  add column if not exists d_unite_ref          text;

comment on column listings.d_etage is
  'Etage du lot, lu dans le descriptif. Piege connu : "Floor 2-Bedroom Condo" est
   un TITRE, pas un etage — le tiret discrimine.';
comment on column listings.d_quota is
  'Quota foreigner/thai. Lu sur le LIBELLE exact ("Thai Quota" suivi du champ
   suivant), jamais sur la phrase legale generique presente sur toutes les fiches
   ("Units that are part of the Thai quota or are being leased...") : la confondre
   produisait ~32 faux positifs sur 315 fiches FazWaz.';
comment on column listings.d_proprietaire is
  'NATIONALITE / structure du VENDEUR (thai | foreigner | company), lue chez
   PropertyScout sous "Property Ownership". A NE PAS CONFONDRE AVEC d_quota :
   un proprietaire thai peut detenir un lot en quota etranger. Les fusionner
   produisait de faux quotas (correction metier du 2026-08-02).';
comment on column listings.d_publie_par is
  'private owner | agent | agency | developer. Complement a agent_id, qui
   n''existe que sur DDproperty.';
comment on column listings.d_annee_construction is
  'Annee de livraison du batiment. Propriete de l''IMMEUBLE : a terme, alimenter
   la table condos plutot que de la repeter sur chaque annonce.';

-- Couverture par source — à surveiller après chaque scrape. Une source qui
-- tombe à 0 signale un changement de gabarit chez elle, pas une absence de donnée.
create or replace view details_couverture as
select source,
       count(*)                                                  as annonces,
       round(100.0 * count(d_etage)              / nullif(count(*),0), 1) as pct_etage,
       round(100.0 * count(d_annee_construction) / nullif(count(*),0), 1) as pct_annee,
       round(100.0 * count(d_meuble)             / nullif(count(*),0), 1) as pct_meuble,
       round(100.0 * count(d_quota)              / nullif(count(*),0), 1) as pct_quota,
       round(100.0 * count(d_cam_fee_thb)        / nullif(count(*),0), 1) as pct_cam_fee,
       round(100.0 * count(d_publie_par)         / nullif(count(*),0), 1) as pct_publie_par
from listings
where status = 'active'
group by source
order by annonces desc;
