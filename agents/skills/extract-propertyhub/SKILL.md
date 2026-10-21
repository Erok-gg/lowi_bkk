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
- ~35 % des couvertures renvoient 403 (S3 AccessDenied : fichier absent, le
  site affiche la même image cassée). L'annonce est écrite sans photo et
  **n'est pas retentée** (`image.retenter: false`).
- `contactInformation` (téléphone, e-mail) n'est jamais recopié.
- Pas de quota étranger exposé.

## Ce que les autres agents font de cette source (vérifié le 2026-10-20)
- **watch-health** : bandes `nouvelles` 1–4500 lues dans `agents.json`.
  Pendant le rattrapage, `nouvelles` plafonne au budget (≈ 4 000) ; une fois
  le stock rattrapé, le flux retombe et le verdict `derive` (medium, sans
  mail) peut sortir quelques runs, le temps que la médiane suive.
- **fraîcheur** (`ops/fraicheur.py`) : fenêtre de confirmation dérivée de
  `every_days` → 96 h pour une cadence de 3 j (48 h pour les quotidiennes).
- **remonter-supabase** : source **exclue** (`--exclure-sources`), décision
  utilisateur du 2026-10-20 ; ses lignes gardent `dirty_since`.
- **scores-tension** : exclusion manuelle « rattrapage » dans
  `bilan_RE/tension/config.json` — une source partie de 0 ne déclenche
  aucune règle automatique de santé.
- **study / bilan acheteur** : lisent la base locale sans filtre de source —
  la source entre dans les médianes dès la première nuit (rupture de série à
  arbitrer).
- **organize** : paires candidates formées **à l'intérieur** d'une source ; les
  doublons inter-sources ne sont pas traités.
- **watch-health, images** : bande `erreurs_images` 0–2500 (couvertures
  absentes du CDN : 29/82 = 35 % mesuré) ; `image.retenter: false` → une couverture en 403 n'est pas retentée.
