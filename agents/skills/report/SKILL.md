---
name: report
description: Produit l'étude de marché récurrente — snapshot daté, tables d'évolution, rapport markdown — puis escalade le narratif mensuel à Claude. Utiliser en fin de cycle location.
---

# report

## Mission
Faire tourner l'étude que personne ne lançait. `docs/etudes/` s'est arrêté au
2026-07-09 alors que les données étaient fraîches du 29/07 : `run_study.py`
n'était appelé que par une tâche Windows morte.

## Étage
**T0 → T2.** Le calcul est déterministe et figé. Seul le **narratif** mensuel
demande du raisonnement, et part donc à Claude.

## Entrées
`study/config.json` (paramètres FIGÉS, versionnés) · `study/context.md` (narratif
manuel) · snapshots antérieurs.

## Procédure
1. `study/run_study.py` — lit la config, calcule sur Supabase, écrit
   `study/snapshots/YYYY-MM-DD.json` puis `docs/etudes/etude-YYYY-MM-DD.md`.
2. Le **1er du mois** : escalader la note de conjoncture à Claude.

## Contrat de sortie
```json
{"snapshot": str, "rapport": str, "traces_erreur": int}
```

## Bandes normales
`traces_erreur` = 0 exactement. L'étude ne tolère aucune erreur : un snapshot
partiel casse la comparabilité de toute la série.

## Escalade
Ticket `narratif_mensuel`, sévérité basse, le 1er du mois. Demande à Claude :
lire les deux derniers snapshots, croiser avec une veille web (REIC, BOT,
transit), écrire `docs/etudes/mensuel-YYYY-MM.md`.

## Modes de panne connus
- **Ne jamais modifier `study/config.json` sans incrémenter `config_version`.**
  Tout changement de paramètre casse la comparabilité avec les snapshots
  antérieurs ; la version tracée est ce qui rend la rupture de série visible.
- Les tables d'évolution ne se construisent qu'à partir de 2 snapshots.
- Logique métier **dupliquée** entre `study/run_study.py` et `lib/yields.ts` :
  une correction dans l'un doit être reportée dans l'autre. Chantier ouvert.
