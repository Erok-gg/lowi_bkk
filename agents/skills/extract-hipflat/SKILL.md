---
name: extract-hipflat
description: Extraction Hipflat (hipflat.co.th) vers la base SQLite locale. SERP HTML serveur, prix en THB par cookie, pagination plafonnée à 167 pages découpée par district/chambres/prix, annonces FazWaz syndiquées écartées. Utiliser pour lancer, diagnostiquer ou réparer le scrap Hipflat.
---

# extract-hipflat

## Mission
Mettre à jour les annonces Hipflat (groupe Lifull Connect, comme DotProperty) :
62 233 ventes + 118 991 locations annoncées sur Bangkok (2026-10-20).

## Étage
**T0 — déterministe.**

## Entrées
`scraper/config/hipflat.json` · cache `scraper/output/hipflat-ecartees.json`

## Procédure
`run.py --source hipflat --deal-type sale --full --store sqlite`, puis `rent`.
50 districts ; un segment > 5 010 annonces est redécoupé par chambres, puis
lu par les deux bouts (`price_asc`, `price_desc`). Au plus `max_nouvelles`
(2 000) annonces inconnues par run, chacune ouvre sa fiche.

## Contrat de sortie
```json
{"nouvelles": int, "changees": int, "retirees": int, "traces_erreur": int}
```

## Bandes normales
`nouvelles` 1–4500 · `traces_erreur` 0–5 — provisoires, aucun run de production.

## Escalade
`[SONDE-ECHEC]` « prix pas en ฿ » → le cookie `_wl_currency` ne suffit plus
(voir `POST /api/currency`). `[COUVERTURE]` est informatif, pas une panne.

## Modes de panne connus
- **Syndication FazWaz** : référence d'unité `U1234567` dans le fil d'Ariane
  → écartée (déjà scrapée à la source). 7/28 sur l'échantillon du 2026-10-20,
  10/10 en tête de Watthana-vente : la part réelle se lira dans les logs
  (`[syndiquee-fazwaz]`).
- **Tranches non vues** : au milieu d'un segment > 10 020 annonces, une
  tranche de prix n'est jamais affichée. `ids_hors_couverture` la protège du
  délistage ; ses annonces ne sont ni confirmées ni délistées.
- ~1 carte sur 3 sans photo (placeholder) : drapeau `_sans_image`, pas de
  réouverture de fiche.
- Nom d'immeuble absent si la fiche n'a pas de lien `/en/projects/`.

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
- **watch-health, images** : seuil par défaut (10) ; les cartes sans photo
  portent `_sans_image` et ne sont jamais téléchargées.
