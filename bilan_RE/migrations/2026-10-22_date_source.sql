-- Date de création de l'annonce déclarée par le portail (aujourd'hui PropertyScout).
-- Colonne LOCALE (SQLite, PC2) : non poussée vers Supabase, aucune migration serveur.
-- Pourquoi : `first_seen` ne dit que notre premier passage ; sur PropertyScout il
-- retarde de 2 semaines à 3 ans (suivi commencé le 24/06/2026, découverte tardive).
-- La date du portail croît strictement avec l'identifiant (10 fiches, 2026-10-22) :
-- c'est une création, pas une remontée comme le `posted_at` de DDproperty.
-- État avant (relevé 2026-10-22, PC2) : 62 colonnes, 220 007 lignes dans `listings`.
-- `_migrate()` de sqlite_store ajoute la même colonne seule ; ce fichier sert à
-- l'appliquer à la main ou à la documenter. Rollback : 2026-10-22_date_source_rollback.sql
ALTER TABLE listings ADD COLUMN listed_at_source TEXT;
