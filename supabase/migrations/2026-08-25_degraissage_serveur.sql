-- 2026-08-25 — Dégraissage du serveur : le local devient l'unique détenteur de
-- ce que l'app ne lit jamais.
--
-- POURQUOI
-- Mesure du jour : l'app lit ~22 Mo (listings colonnes utiles 18,6 + images 1,8
-- + price_history 0,6 + khet_snapshots 1,0) sur une base locale de 1,04 Go.
-- Vérifié fichier par fichier : aucun .ts/.tsx ne référence `page_text`,
-- `description`, `cohort_snapshots` ni `listing_amenities` — le seul résultat,
-- app/layout.tsx, est la balise meta HTML. `lib/listings-db.ts:95` renvoie même
-- `amenities: []` en dur.
--
-- Le serveur pesait 810 Mo pour un quota gratuit de 500 (162 %). Après :
--   page_text          −207 Mo
--   description         −83 Mo
--   cohort_snapshots   −218 Mo
--   listing_amenities   −70 Mo
--   → ~230 Mo, soit ~46 % du quota.
--
-- CE QUI A ÉTÉ VÉRIFIÉ AVANT (ops/verifie-avant-degraissage.py, sortie 0) :
--   listings.page_text      32 342 lignes serveur, toutes retrouvées en local
--   listings.description    46 060 lignes serveur, toutes retrouvées en local
--   listing_amenities      674 849 serveur / 715 706 local, aucune manquante
--   cohort_snapshots       842 738 serveur / 1 182 220 local, aucune manquante
--
-- Le test a d'abord REFUSÉ, deux fois, et il avait raison les deux fois :
--   1. 3 `page_text` et 4 `description` existaient sur le serveur et pas en
--      local — la dédup incrémentale (prix inchangé → fiche non revisitée)
--      n'avait jamais capturé leur texte côté local. Rapatriés par
--      ops/rapatrie-textes.py avant de continuer.
--   2. 842 738 lignes de cohort_snapshots annoncées « absentes » : artefact de
--      MESURE, pas un trou. `str(datetime)` rend « ...03:58:19+00 » côté
--      Postgres quand SQLite stocke « ...T03:58:19+00:00 ». Corrigé par une
--      normalisation ISO ; le local est en fait un surensemble.
--
-- ORDRE D'APPLICATION — l'inverse d'un ajout de colonne
-- Pour un AJOUT : schéma → migration → code. Pour un RETRAIT : le code cesse
-- d'écrire D'ABORD, la suppression vient ensuite. Sinon le scrap en cours meurt
-- sur « column ... does not exist ». Les stores ont donc été modifiés avant
-- (store/base.py : COLONNES_LOCALES ; supabase_store : amenities et cohortes en
-- no-op).
--
-- ROLLBACK : 2026-08-25_rollback_degraissage.sql (structures seules — les
-- DONNÉES se re-poussent depuis le local avec ops/remonter-local.py).

begin;

-- Deux vues d'ANALYSE en dépendent. Elles ne sont lues par aucune page ; leurs
-- définitions sont conservées dans le fichier de rollback. On les retire
-- EXPLICITEMENT plutôt que par `cascade` : un cascade silencieux est exactement
-- la façon dont on perd un objet sans s'en apercevoir.
drop view if exists cohort_tension;
drop view if exists description_couverture;

alter table listings drop column if exists page_text;
alter table listings drop column if exists description;

drop table if exists cohort_snapshots;
drop table if exists listing_amenities;

commit;

-- L'espace n'est PAS rendu par le simple drop : `alter table drop column` se
-- contente de marquer la colonne supprimée. Le `vacuum full` qui suit réécrit
-- la table — il prend un verrou exclusif, donc jamais pendant un scrap.
-- (à lancer hors transaction)
--   vacuum full listings;
