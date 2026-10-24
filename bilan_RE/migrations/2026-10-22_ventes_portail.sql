-- Ventes « conclues » publiées par un portail (FazWaz) — SOURCE FAIBLE, tables à part.
-- Locales (SQLite, PC2), jamais poussées vers Supabase, jamais jointes à `listings`.
-- État avant (relevé 2026-10-22, PC2) : ni `ventes_portail` ni `ventes_portail_projets`.
-- `SqliteStore._migrate()` crée les mêmes tables seule ; ce fichier documente et
-- permet l'application à la main. Rollback : 2026-10-22_ventes_portail_rollback.sql
create table if not exists ventes_portail (
  id text primary key, source text not null, projet_cle text not null,
  projet_url text, condo_name text, condo_norm text,
  deal_type text not null, sold_date text not null, sold_price real not null,
  area_sqm real, price_per_sqm real, floor integer, bedrooms integer,
  furniture integer, quota text,
  fiabilite text not null default 'faible',
  premier_vu text not null, dernier_vu text not null);
create index if not exists idx_ventes_portail_condo on ventes_portail (condo_norm, sold_date);
create table if not exists ventes_portail_projets (
  source text not null, projet_cle text not null, projet_url text,
  condo_name text, condo_norm text, n real, price_per_sqm real,
  jours_avant_vente real, decote_pct real, releve_le text not null,
  primary key (source, projet_cle));
