---
name: extract-fazwaz
description: Extraction FazWaz (vente et location) vers Supabase. Parsing JSON-LD des pages de liste, puis passe ciblée sur les couloirs de développement. Utiliser pour lancer, diagnostiquer ou réparer le scrap FazWaz.
---

# extract-fazwaz

## Mission
Mettre à jour les annonces FazWaz (la plus grosse source : ~19 500 annonces, 9 800 actives).

## Étage
**T0 — déterministe.** Aucun LLM. Ce qui manquait n'était pas de l'intelligence
mais l'orchestration et une trace.

## Entrées
`scraper/config/fazwaz.json` · `scraper/config/targets/fazwaz-corridors.json`

## Procédure
1. Scan global : `run.py --source fazwaz --deal-type <deal> --full --store supabase`
2. **Puis** passe ciblée couloirs (`--config config/targets/fazwaz-corridors.json`).

L'ordre n'est pas négociable : la fenêtre 150 pages du scan global délisterait à
tort les annonces des districts ciblés ; la passe ciblée qui suit les réactive
(touch/upsert les repasse en `active`).

## Contrat de sortie
```json
{"nouvelles": int, "changees": int, "retirees": int, "traces_erreur": int, "then_exit": int}
```

## Bandes normales
`nouvelles` 50–2000 · `traces_erreur` 0–3 · `then_exit` 0

**Signature de parseur cassé : `nouvelles` ≈ 0 avec `traces_erreur` ≈ 0.**
Le site répond, on ne comprend plus sa réponse. C'est exactement le bug du
2026-07-23 (0 annonce pendant plusieurs jours, corrigé par `0980a1f`).

## Escalade
`nouvelles` = 0 sur deux runs consécutifs → ticket `parser_break` vers Claude,
avec l'extrait de log et un lien vers une page de liste réelle.

## Modes de panne connus
- **JSON-LD des pages de liste** : structure déjà cassée une fois (07/2026). C'est
  le point de rupture le plus probable.
- **Snapshot Livewire inconstant** : le quota étranger vient d'un code `ownership`
  souvent absent → `quota` à None dans la majorité des cas. Normal, pas une panne.
- Freehold uniquement : le leasehold est écarté à la source.
