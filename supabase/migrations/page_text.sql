-- page_text.sql — TEXTE INTÉGRAL de la page, compressé. La matière première.
--
-- POURQUOI. `description` est un produit FINI : tronqué à 4 000 caractères,
-- détagué, recadré. Quand un motif d'extraction se révèle faux, on ne peut pas
-- rejouer dessus — il faudrait re-scraper les 15 000 fiches, et les pages
-- auront changé entre-temps.
--
-- Ce n'est pas hypothétique : trois motifs ont dû être corrigés le 2026-08-02,
-- tous découverts APRÈS le scrape.
--   · « Thai Quota » en insensible à la casse attrapait la clause légale
--     présente sur TOUTES les fiches FazWaz — ~32 faux positifs.
--   · « Floor 72 sq.m. » rendait la SURFACE au lieu de l'étage, et
--     « Floor, 117 Units » le nombre de LOTS.
--   · « Building completed in 2027 » est un gabarit PropertyScout AU PASSÉ pour
--     une livraison à venir — 84 lots déclarés livrés pour 2027-2029.
-- Chacune de ces corrections a pu être rejouée sur `description`. La prochaine
-- portera peut-être sur un champ qu'elle a tronqué.
--
-- COMPRESSÉ. zlib niveau 6, appliqué à l'écriture par les deux stores
-- (`SqliteStore._valeur`). La fonction `compresser()` existait depuis le
-- 2026-07-31 mais n'était appelée nulle part : la colonne était déclarée `blob`
-- et recevait la chaîne telle quelle. Corrigé le 2026-08-02, ~78 % de gain sur
-- un texte de page réel.
--
-- NON RÉTROACTIF, et cette fois sans recours : on ne conserve pas le HTML.
-- La colonne se remplira au fur et à mesure des scrapes.

alter table listings
  add column if not exists page_text bytea;

comment on column listings.page_text is
  'Texte intégral de la page, compressé zlib. Matière première pour rejouer une '
  'extraction sans re-scraper. Lire via SqliteStore.decompresser(). Non rétroactif.';
