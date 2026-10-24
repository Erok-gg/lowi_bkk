---
name: extract-dotproperty
description: Extraction DotProperty (dotproperty.co.th) vers la base SQLite locale, le SOIR (lane soir, 21:00) avec arrêt propre à 02:00. ld+json ItemList sur la liste, surface lue sur la fiche. Utiliser pour lancer, diagnostiquer ou réparer le scrap DotProperty.
---

# extract-dotproperty

## Mission
Rattraper puis suivre le stock DotProperty : 62 431 ventes + 119 610
locations annoncées sur Bangkok (2026-10-22). 85 % recoupent une autre source
(même immeuble, même prix), 15 % n'existent nulle part ailleurs chez nous.

## Étage
**T0 — déterministe.** Lane **`soir`** (tâche `LowiBKK-Soir`, 21:00), pas le
cycle de nuit.

## Procédure
`run.py --source dotproperty --full --jusqua 02:00 --store sqlite` — vente
puis location dans le même run, liste entière (pas de plafond de pagination),
au plus `max_nouvelles` (3 000) annonces inconnues par soir.

## Contrat de sortie
```json
{"nouvelles": int, "changees": int, "retirees": int, "traces_erreur": int}
```

## Bandes normales
`nouvelles` 1–6500 · `traces_erreur` 0–5 — provisoires, aucun run de production.

## Escalade
`[SONDE-ECHEC]` → ld+json `ItemList` absent de la page de liste.
`[ARRET-HORAIRE]` est **normal** pendant le rattrapage : scan partiel, aucun
délistage ce soir-là.

## Modes de panne connus
- **Arrêt à 02:00 obligatoire** : un scrap encore en vol à 02:30 fait reporter
  tout le cycle de nuit (`extraction_en_cours`). Ne pas retirer `--jusqua`.
- Tant que la liste n'est pas lue en entier avant 02:00, **aucun délistage** :
  le stock DotProperty ne baisse pas, il faut attendre que le rattrapage
  libère assez de temps pour une lecture complète.
- Les photos « img.fazwaz.com » sont l'hébergeur du groupe Lifull Connect, pas
  des annonces FazWaz (lecture erronée du 2026-08-05, corrigée le 2026-10-22).
- Exclue de la remontée Supabase et des scores de tension pendant le
  rattrapage (comme PropertyHub et Hipflat).
- `datePosted` = date de (re)publication déclarée : en raw_data seulement.
