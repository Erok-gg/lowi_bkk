---
name: extract-ddproperty
description: Extraction DDproperty (vente et location) vers Supabase. Parsing __NEXT_DATA__ derrière un challenge Cloudflare, avec géocodage. Utiliser pour lancer, diagnostiquer ou réparer le scrap DDproperty.
---

# extract-ddproperty

## Mission
Mettre à jour les annonces DDproperty (~11 700 annonces, 6 700 actives).
**Seule source qui expose `agent_id`, `agency_id`, `posted_at` et `is_auto_repost`** —
elle porte donc la vérité terrain qui rend la question des doublons décidable.

## Étage
**T0 — déterministe.**

## Entrées
`scraper/config/ddproperty.json` · `scraper/config/targets/ddproperty-corridors.json`

## Procédure
1. `run.py --source ddproperty --deal-type <deal> --full --geocode --store supabase`
2. **Puis** passe ciblée couloirs (même raison que FazWaz : restauration).

## Contrat de sortie
```json
{"nouvelles": int, "changees": int, "retirees": int, "traces_erreur": int, "then_exit": int}
```

## Bandes normales
`nouvelles` 30–1500 · `traces_erreur` 0–3

## Escalade
- `nouvelles` = 0 avec `traces_erreur` = 0 → ticket `parser_break`.
- Beaucoup d'erreurs HTTP 403 → ticket `cloudflare` : la session réchauffée ne
  prend plus, il faut revoir la stratégie d'en-têtes.

## Modes de panne connus
- **Challenge Cloudflare** sur les pages détail. Contourné sans Chrome par une
  session `requests` réchauffée (parcourir la liste d'abord → cookie `__cf_bm`)
  avec en-têtes navigateur et **sans brotli** (requests ne le décode pas).
  C'est fragile par nature : c'est la panne à surveiller en priorité.
- `robots.txt` illisible derrière le challenge → accès autorisé par défaut (RFC).
- `tenureCode='F'` → freehold gardé, leasehold écarté. Quota non exposé (None).
