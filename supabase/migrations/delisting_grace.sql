-- delisting_grace.sql — délai de grâce avant délistage.
--
-- PROBLÈME CORRIGÉ : mark_missing_inactive() délistait dès la PREMIÈRE absence
-- d'une annonce dans un scan. Or un scan --full s'arrête à max_pages (150) :
-- tout ce qui suit était marqué disparu à tort, puis réactivé par la passe
-- ciblée suivante. Conséquence mesurée sur l'archive : la durée de vie des
-- annonces était de 4,7 jours médians pour TOUTES les strates (studio comme
-- 3BR+) — c'est-à-dire la cadence de scan, pas un signal de marché. La tension
-- locative et la liquidité de revente étaient donc non mesurables.
--
-- CORRECTIF : une annonce doit être absente de N scans CONSÉCUTIFS (N=2) avant
-- d'être délistée. On mémorise la date de la première absence pour dater le
-- délistage au bon moment, sinon la durée de vie serait surestimée d'un cycle.

alter table listings add column if not exists missed_count integer not null default 0;
alter table listings add column if not exists first_missed_at timestamptz;

create index if not exists idx_listings_missed on listings (missed_count)
  where missed_count > 0;

comment on column listings.missed_count is
  'Nombre de scans consécutifs où l''annonce n''a pas été vue. Remis à 0 dès qu''elle réapparaît. Délistage au seuil (2).';
comment on column listings.first_missed_at is
  'Date de la première absence de la série en cours. Sert de delisted_at réel une fois le seuil atteint.';
