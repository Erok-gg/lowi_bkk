---
name: extract-propertyhub
description: Extraction PropertyHub (propertyhub.in.th) vers la base SQLite locale. Parsing __NEXT_DATA__ Next.js, pagination /<page>, coordonnées du projet cachées par project_id. Utiliser pour lancer, diagnostiquer ou réparer le scrap PropertyHub.
---

# extract-propertyhub

## Mission
Mettre à jour les annonces PropertyHub. Source la plus volumineuse du projet :
151 117 locations + 64 158 ventes annoncées sur la zone Bangkok (2026-10-20).

## Étage
**T0 — déterministe.**

## Entrées
`scraper/config/propertyhub.json` · cache `scraper/output/propertyhub-projets.json`

## Procédure
`run.py --source propertyhub --deal-type sale --full --store sqlite`, puis la
même chose en `rent`. Liste entière (pas de tri par fraîcheur côté site).
Au plus `max_nouvelles` (2 000) annonces inconnues ingérées par run.

## Contrat de sortie
```json
{"nouvelles": int, "changees": int, "retirees": int, "traces_erreur": int}
```

## Bandes normales
`nouvelles` 1–4500 · `traces_erreur` 0–5 — provisoires, aucun run de production.

## Escalade
`nouvelles` = 0 avec `traces_erreur` = 0 → ticket `parser_break`.
`[SONDE-ECHEC]` → `pageProps.listings.listings` introuvable.

## Modes de panne connus
- La zone « Bangkok » est la province **métropolitaine** : filtre sur l'adresse
  du projet (finit par « Bangkok »), sinon Samut Prakan entre dans les stats.
- 60 annonces sponsorisées répétées sur chaque page : dédupliquées dans l'adaptateur.
- ~1 couverture sur 4 renvoie 403 (fichier supprimé côté CDN) : l'annonce est
  écrite sans photo et retentée au run suivant (1 GET, pas de fiche).
- `contactInformation` (téléphone, e-mail) n'est jamais recopié.
- Pas de quota étranger exposé.
