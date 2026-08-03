---
name: storage
description: Réplique Supabase en archive locale puis purge du serveur les annonces délistées de plus de 90 jours, uniquement si leur copie est vérifiée. Utiliser une fois par semaine.
---

# storage

## Mission
Le local est la **référence historique complète** ; le serveur n'est qu'une
fenêtre chaude. Cet agent maintient cette asymétrie.

## Étage
**T0 — déterministe.** Aucun LLM n'a sa place près d'une opération de purge.

## Entrées
Toutes les tables Supabase · `archive/lowi-archive.db` (SQLite, gitignoré).

## Procédure
1. `ops/sync_supabase_local.py --prune`
2. Le script réplique toutes les tables (introspection de schéma → résiste aux
   évolutions), puis supprime du serveur les inactives délistées > 90 j
   **uniquement si leur copie est vérifiée identifiant par identifiant**.

## Contrat de sortie
```json
{"tables_repliquees": int, "lignes_archivees": int, "lignes_purgees": int, "traces_erreur": int}
```

## Bandes normales
`traces_erreur` = 0 exactement.

## Escalade
Purge refusée par un garde-fou → ticket `purge_refusee`, sévérité haute. Ce n'est
pas une panne, c'est le dispositif qui fonctionne — mais ça demande un regard.

## GARDE-FOUS (non négociables)
- **Archive plus petite que le serveur → purge interdite.**
- **Une seule candidate absente de l'archive → purge annulée en totalité.**
- L'orchestrateur refuse de lancer cet agent si le dernier run de
  `extract-fazwaz` ou `extract-ddproperty` n'est pas `ok` : jamais de purge
  derrière un cycle douteux. C'est déclaré dans `agents.json`
  (`requires_healthy`).

## Modes de panne connus
- 3,2 Go d'images (69 433 fichiers) + 49 Mo de base : la réplication est longue,
  ce n'est pas un blocage.
- Une purge ne se rattrape pas. En cas de doute, ne rien purger et escalader.
