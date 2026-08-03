---
name: watch-health
description: Surveille la santé des 4 sources de scraping. Détecte un parseur cassé par changement de DOM (volume effondré sans erreur HTTP) et escalade à Claude avec les preuves. Utiliser après chaque cycle d'extraction ou pour diagnostiquer une source muette.
---

# watch-health

## Mission
Voir qu'un scrap est cassé **le jour où il casse**, pas trois semaines plus tard.

Le bug FazWaz du 2026-07-23 (0 annonce, corrigé par `0980a1f`) a couru plusieurs
jours sans détection. Cet agent existe pour que ça n'arrive plus.

## Étage
**T1 → T2.** Les bandes se calculent en Python ; le modèle local ne sert qu'à
rédiger le constat en langage lisible. Le diagnostic du DOM et le patch sont
l'affaire de Claude, qui a l'accès au dépôt.

## Entrées
Ledger : `agent_runs` des 4 extracteurs (métriques + bandes de `agents.json`).

## Procédure
1. Pour chaque extracteur, lire le dernier run et les 10 précédents réussis.
2. Comparer `nouvelles` à la bande déclarée **et** à la médiane historique.
3. Classer :
   - `nouvelles` = 0 **et** `traces_erreur` = 0 → **parseur cassé** (le site
     répond, on ne le comprend plus) ;
   - `nouvelles` = 0 **et** `traces_erreur` > 0 → **panne réseau ou blocage** ;
   - `nouvelles` < 25 % de la médiane → **dérive**, à surveiller ;
   - hors bande haute → **anomalie de volume** (souvent un `--full` après un
     scan partiel, pas forcément un défaut).
4. Émettre un `finding` par anomalie ; escalader les `parseur cassé`.

## Contrat de sortie
```json
{"sources_verifiees": int, "anomalies": int, "escalades": int,
 "detail": [{"source": str, "verdict": str, "nouvelles": int, "mediane": float}]}
```

## Bandes normales
0 anomalie. Une anomalie isolée après un changement de configuration est normale ;
**deux runs consécutifs à zéro ne le sont jamais**.

## Escalade
Ticket `parser_break`, sévérité haute, portant : les identifiants des runs, la
bande attendue, la valeur observée, un extrait de log, et l'URL d'une page de
liste réelle à inspecter. Demande à Claude : diagnostiquer le parsing et proposer
un correctif **sur une branche**.

## Modes de panne connus
- Un scan ciblé (`--config`) produit légitimement peu de nouvelles : ne pas le
  confondre avec un parseur cassé. Vérifier `lane` et la présence de `then_exit`.
- Les 4 sources n'ont pas la même saisonnalité : comparer chaque source à
  **sa propre** médiane, jamais aux autres.
