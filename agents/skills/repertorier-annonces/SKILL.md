---
name: repertorier-annonces
description: Après chaque scrap, remplit condo_norm (nom d'immeuble normalisé, indexé) pour que le bilan acheteur retrouve un immeuble sur tous les portails en quelques millisecondes.
---

# repertorier-annonces

## Mission
Les extracteurs ne connaissent pas `condo_norm` (ils nomment leurs colonnes à
l'écriture). Sans ce passage, une nouvelle annonce reste introuvable par son
immeuble dans le bilan, et l'index `idx_listings_condo_norm` vieillit.

## Étage
**T0.** Déterministe (`bilan_RE/ops/repertorier-annonces.py`).

## Entrées
`scraper/output/bangkok.db` ; état du dernier passage :
`scraper/output/repertorier-annonces.etat`.

## Procédure
1. Si la colonne ou les index manquent (base restaurée) : applique les migrations
   `bilan_RE/migrations/2026-10-17_index_bilan*.sql` (additives ; rollbacks à côté).
2. Normalise le nom des annonces vues depuis le dernier passage et de celles
   jamais répertoriées, n'écrit que ce qui change, par lots de 5 000.

## Contrat de sortie
```json
{"lignes_examinees": int, "lignes_mises_a_jour": int, "lignes_nulles_restantes": int,
 "migration_appliquee": bool, "passage": str, "duree_s": float}
```

## Bandes normales
`lignes_nulles_restantes` = 0. `duree_s` de quelques secondes (mesuré : 1,9 s au
passage incrémental, 12 s en complet sans migration, 131 s au premier passage).

## Escalade
Aucune vers Claude. Constat moyen `annonces_non_repertoriees` si le compte reste > 0.

## Modes de panne connus
- Base restaurée d'une sauvegarde antérieure au 2026-10-17 : la migration se
  rejoue d'elle-même (`migration_appliquee: true`), passage complet.
- Changement de la règle `_norm_condo` (scraper/pipeline/normalize.py) : lancer
  une fois `--tout`, sinon les anciennes lignes gardent l'ancienne forme.
