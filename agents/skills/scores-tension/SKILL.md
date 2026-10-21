---
name: scores-tension
description: Calcule chaque jour, en fin de cycle, les scores de tension acheteur/vendeur et de liquidité (0-100) de chaque immeuble à annonce active, et les écrit dans un fichier ; surveille ce qui les nourrit et appelle la réparation sur défaut. Aucune remontée Supabase.
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
4. Écriture atomique de `scraper/output/scores-tension/scores-AAAA-MM-JJ.json` (un par jour depuis le 2026-10-20)
   et de `scores-latest.json`.

## Contrat de sortie
```json
{"fichier": str, "fin_fenetre": str, "immeubles": int, "erreurs": int,
 "sources_gardees": list, "lignes_notees_rayon": int, "duree_s": int, "calcule_le": str,
 "lignes": int, "part_tension_fine": float, "liquidite_publiees": int}
```

## Bandes normales
`erreurs` = 0. `immeubles` d'environ 4 000 (4 876 immeubles à annonce active au
2026-10-17, dont certains sans vente active). `duree_s` de l'ordre de 3 000.

## Escalade
Depuis le 2026-10-20 (« un défaut appelle la réparation ») : tous les constats
sont HAUTS, donc lus par la veille (`ops/veille-cycle.py`) qui appelle Opus.
- `delistage_a_l_arret` : DDproperty ou FazWaz, ≥ 200 actives, ≥ 3 jours sans
  retrait (le filtre écarte à 5). Première piste : le scan a-t-il lu le site
  entier ? Le 2026-10-20, les nuits sans retrait DDproperty étaient toutes des
  recensements arrêtés au plafond `max_pages_recensement` (6 400 pages lues).
- `source_ecartee` : une grande source écartée par le filtre de santé.
- `immeubles_en_erreur` : au moins un.
- `fenetre_perimee` : dernier retrait connu il y a plus de 2 jours.
- `regression_publication` : tension à maille fine en baisse de plus de
  15 points, ou scores de revente publiés divisés par deux, face au run
  précédent (silence au premier run).

## Modes de panne connus
- **Le score d'un immeuble seul n'atteint presque jamais le minimum** (30
  cohortes, 10 sorties) : c'est attendu, le rapport affiche alors le rayon de
  1 km ou le district.
- **Liquidité** : réputée non publiable avant ~3 mois (2026-10-17). Mesuré le
  2026-10-20 : le blocage venait de l'exclusion de DDproperty, d'où le forçage
  `saines_forcees` de la config v2 (fenêtres jusqu'au 2026-10-20).
- Tant qu'aucune fenêtre n'a DDproperty et FazWaz sains en même temps, la
  composition du score change d'un mois à l'autre : comparer deux mois demande
  de regarder `sources` dans le fichier.
- Ne jamais modifier `bilan_RE/tension/config.json` sans incrémenter
  `config_version`.
