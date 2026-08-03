---
name: extract-nestopa
description: Extraction Nestopa vers Supabase. Parsing ld+json Product, géocodage obligatoire (pas de coordonnées serveur). Utiliser pour lancer, diagnostiquer ou réparer le scrap Nestopa.
---

# extract-nestopa

## Mission
Mettre à jour les annonces Nestopa (~1 700 annonces, 800 actives). La plus petite
source — donc la meilleure pour un test de fumée du pipeline complet.

## Étage
**T0 — déterministe.**

## Entrées
`scraper/config/nestopa.json`

## Procédure
`run.py --source nestopa --full --geocode --store supabase`

**`--geocode` est obligatoire ici** : Nestopa n'expose aucune coordonnée. Sans
géocodage, les annonces n'ont ni pinpoint ni khet fiable.

## Contrat de sortie
```json
{"nouvelles": int, "changees": int, "retirees": int, "traces_erreur": int}
```

## Bandes normales
`nouvelles` 5–400 · `traces_erreur` 0–3

## Escalade
`nouvelles` = 0 avec `traces_erreur` = 0 → ticket `parser_break`.

## Modes de panne connus
- **`ld+json` de type `Product`** sur le flux `/th-en/for-sale|for-rent` ;
  le filtre Bangkok passe par l'URL, pas par un champ.
- Champs déduits du slug et du nom → sensibles à un changement de format d'URL.
- **Nominatim plafonne à ~35-40 % de réussite** sur les noms de condos thaïs.
  Un taux de géocodage bas n'est donc PAS une panne : c'est la normale.
- **Pas de descriptif exploitable.** Sondé le 2026-07-31 : le champ `description`
  du `Product` ld+json est absent la plupart du temps, et quand il est là, c'est
  une redite des specs en thaï (« 134 ตรม., 3 ห้องนอน… ») sans information
  au-delà du structuré. Les pages détail répondent **403**. Une couverture
  proche de 0 % sur cette source est donc ATTENDUE, pas une panne d'extraction.
