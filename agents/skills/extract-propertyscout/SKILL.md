---
name: extract-propertyscout
description: Extraction PropertyScout vers Supabase. Parsing __NEXT_DATA__ Next.js, pagination /page-N/. Utiliser pour lancer, diagnostiquer ou réparer le scrap PropertyScout.
---

# extract-propertyscout

## Mission
Mettre à jour les annonces PropertyScout (~2 800 annonces, 1 500 actives).
Petite source : on la scrape entière, les deux `deal_type` en une passe.

## Étage
**T0 — déterministe.**

## Entrées
`scraper/config/propertyscout.json`

## Procédure
`run.py --source propertyscout --full --store supabase`

Pas de passe ciblée : le volume tient dans un scan complet.

## Contrat de sortie
```json
{"nouvelles": int, "changees": int, "retirees": int, "traces_erreur": int}
```

## Bandes normales
`nouvelles` 10–600 · `traces_erreur` 0–3

## Escalade
`nouvelles` = 0 avec `traces_erreur` = 0 → ticket `parser_break`.

## Modes de panne connus
- **`__NEXT_DATA__`** : la clé exacte du blob bouge d'une version Next à l'autre.
- Coordonnées natives présentes → pas de géocodage nécessaire.
- **Pas d'`agent_id`** : cette source ne permet pas la dédup même-agent.
  À sonder — c'est un chantier ouvert du journal technique.
