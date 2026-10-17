---
name: scores-tension
description: Calcule une fois par mois les scores de tension acheteur/vendeur et de liquidité (0-100) de chaque immeuble à annonce active, et les écrit dans un fichier. Aucune remontée Supabase.
---

# scores-tension

## Mission
Produire la matière du bilan acheteur sans recalculer à chaque demande : le
calcul complet d'une annonce prend 1 min 30. Le lot partage les niveaux larges
(Bangkok, zone, district) entre tous les immeubles.

## Étage
**T0.** Entièrement déterministe (`bilan_RE/tension/`) : aucune IA, aucun ticket.

## Entrées
`scraper/output/bangkok.db` (lecture seule) · `bilan_RE/tension/config.json`
(versionnée, méthode `docs/methodes-calculs.md` §12).

## Procédure
1. Fin de fenêtre = dernier jour de retrait connu en base.
2. Santé des sources sur la fenêtre (règles de la config), puis cohortes.
3. Pour chaque immeuble × chambres (et toutes chambres) : tension et liquidité
   à chaque niveau (Bangkok → zone → district → 1 km → immeuble).
4. Écriture atomique de `scraper/output/scores-tension/scores-AAAA-MM.json`
   et de `scores-latest.json`.

## Contrat de sortie
```json
{"fichier": str, "fin_fenetre": str, "immeubles": int, "erreurs": int,
 "sources_gardees": list, "lignes_notees_rayon": int, "duree_s": int, "calcule_le": str}
```

## Bandes normales
`erreurs` = 0. `immeubles` d'environ 4 000 (4 876 immeubles à annonce active au
2026-10-17, dont certains sans vente active). `duree_s` de l'ordre de 3 000.

## Escalade
Aucune vers Claude. Constats : `source_ecartee` (bas, informatif),
`score_sans_grande_source` (moyen : ne pas servir ce mois-ci),
`immeubles_en_erreur` (moyen).

## Modes de panne connus
- **Le score d'un immeuble seul n'atteint presque jamais le minimum** (30
  cohortes, 10 sorties) : c'est attendu, le rapport affiche alors le rayon de
  1 km ou le district.
- **Liquidité non publiable** avant environ 3 mois de données propres :
  fourchettes trop larges, courbe d'âge vide.
- Tant qu'aucune fenêtre n'a DDproperty et FazWaz sains en même temps, la
  composition du score change d'un mois à l'autre : comparer deux mois demande
  de regarder `sources` dans le fichier.
- Ne jamais modifier `bilan_RE/tension/config.json` sans incrémenter
  `config_version`.
