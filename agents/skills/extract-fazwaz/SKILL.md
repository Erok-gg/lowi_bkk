---
name: extract-fazwaz
description: Extraction FazWaz (vente et location) vers SQLite local. Découverte par le sitemap du site (lastmod par annonce), fiche de détail pour chaque annonce visitée. Utiliser pour lancer, diagnostiquer ou réparer le scrap FazWaz.
---

# extract-fazwaz

## Mission
Mettre à jour les annonces FazWaz (la plus grosse source : 84 534 condos
Bangkok dans son sitemap le 2026-09-13, 10 915 actives en base ce jour-là).

## Étage
**T0 — déterministe.** Aucun LLM. Ce qui manquait n'était pas de l'intelligence
mais l'orchestration et une trace.

## Entrées
`scraper/config/fazwaz.json` (`discovery: "sitemap"`) — `pipeline/sitemap.py`
porte les mesures et la règle de tri.

## Procédure
1. Vente : `run.py --source fazwaz --deal-type sale --full --store sqlite`
2. **Puis** location (`--deal-type rent`), même commande.

**Depuis le 2026-09-13, plus de passe ciblée couloirs.** robots.txt interdit
`order_by=` depuis le 2026-09-12 ; le mode sitemap lit `sitemap-listings.xml`
(déclaré par ce même robots.txt : 27 fichiers, un `<lastmod>` par annonce) et
énumère le catalogue ENTIER, tous districts — il n'y a plus de fenêtre de
150 pages qui délistait à tort, donc plus rien à réactiver.

Ce que fait un run (ligne `sitemap :` du résumé) :
- **confirmées par lastmod** : présentes dans le sitemap, rien de neuf depuis
  notre dernier passage → `touch`, fiche non rouverte. C'est le gros du volume.
- **fiches visitées** (≤ `max_detail_visits`, fraîcheur d'abord) : nouvelles,
  mises à jour (`lastmod` > `last_seen`), délistées à tort à réactiver.
- **reportées** : budget épuisé, visitées un prochain run. Doit décroître
  jour après jour pendant la reprise du retard, puis rester ≈ 0.
- **hors fenêtre** (`sitemap_max_age_days`, 60 j) : inconnues ou délistées
  trop anciennes, pas suivies — définition de série conservée des 150 pages.
- **indisponibles** : fiche injoignable sans prix connu → ni écrite, ni
  comptée vue.

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
- **Sitemap** : index sans `<loc>`, fichier sans `<lastmod>`, ou un des 27
  fichiers injoignable (le run s'arrête, `RuntimeError`, plutôt que de
  délister un pan du catalogue). `sonder()` nomme le marqueur manquant.
- **Fiche de détail** : `<meta name="title">` (prix, nom, chambres),
  `<meta name="description">` (SqM, SDB) et `:lat=`/`:lng=` — sondés avant
  scan. Sans eux, on écrirait des annonces sans prix.
- **JSON-LD des pages de liste** (mode `list`, historique) : structure déjà
  cassée une fois (07/2026). Ne sert plus qu'en repli `discovery: "list"`.
- **Snapshot Livewire inconstant** : le quota étranger vient d'un code `ownership`
  souvent absent → `quota` à None dans la majorité des cas. Normal, pas une panne.
- Freehold uniquement : le leasehold est écarté à la source.
