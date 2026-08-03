-- posted_at_history.sql — trace l'ÉVOLUTION de `posted_at` pour une même annonce.
--
-- POURQUOI. `CLAUDE.md` annonçait que `posted_at` devait remplacer `first_seen`
-- dans le time-on-market « dès qu'il est peuplé ». La mesure du 2026-08-02 sur
-- les 1 294 annonces qui le portent dit l'inverse :
--
--   écart first_seen - posted_at :  p25 -25 j | MÉDIANE -16 j | p75 +1 j | p90 +4 j
--
-- L'écart médian est NÉGATIF : l'annonce a été vue seize jours AVANT sa date de
-- publication déclarée. Une date de mise en ligne ne peut pas être postérieure
-- à notre propre observation — le champ avance donc dans le temps.
--
-- La coupure par `is_auto_repost` le confirme :
--   · republiées (675)     : posted_at du 02/07 au 29/07 — jamais plus d'un mois
--   · non republiées (619) : du 23/11/2025 au 29/07 — huit mois d'étalement
-- et dans les deux groupes ~70 % des lignes ont un posted_at postérieur à notre
-- premier passage. DDproperty y écrit selon toute vraisemblance la date de
-- dernière REMONTÉE en tête de liste, et `is_auto_repost` n'en signale qu'une
-- partie.
--
-- CE QUE CETTE TABLE TRANCHE. « Selon toute vraisemblance » n'est pas une
-- preuve : on écrasait la valeur à chaque scan, donc on ne pouvait pas voir un
-- identifiant donné changer. Cette table conserve chaque nouvelle valeur ; deux
-- lignes pour un même listing_id établissent le fait.
--
-- EN ATTENDANT, la substitution reste PROSCRITE, pour deux raisons distinctes :
--   1. elle RACCOURCIRAIT le time-on-market au lieu de l'allonger, et
--      mesurerait l'assiduité des agents à rafraîchir, pas l'absorption ;
--   2. le champ n'existe que sur DDproperty, dont la part du stock actif va de
--      3 % (Phra Khanong) à 89 % (Bangkok Noi) : une métrique mixte produirait
--      des écarts entre quartiers dus à la COMPOSITION DES SOURCES, pas au
--      marché — même famille d'erreur que le dénominateur de tension corrigé
--      le 2026-07-28.
-- `first_seen` reste donc la base unique : son biais est au moins UNIFORME sur
-- les quatre sources, et un biais partagé se compare.

create table if not exists posted_at_history (
  id          bigserial primary key,
  listing_id  text        not null references listings(id) on delete cascade,
  posted_at   timestamptz not null,
  observed_at timestamptz not null default now()
);

create index if not exists idx_posted_hist_listing on posted_at_history(listing_id);

-- Amorce : la valeur COURANTE de chaque annonce, pour disposer d'un point de
-- comparaison dès le prochain scan. Sans elle, il faudrait deux scans avant que
-- le premier changement soit détectable.
insert into posted_at_history (listing_id, posted_at, observed_at)
select id, posted_at::timestamptz, coalesce(last_seen::timestamptz, now())
from listings
where posted_at is not null
on conflict do nothing;
