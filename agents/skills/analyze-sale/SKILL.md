---
name: analyze-sale
description: Analyse du marché VENTE — médianes par khet et par immeuble, cascade de décote, mouvements par rapport au snapshot précédent. Utiliser après un cycle d'extraction vente.
---

# analyze-sale

## Mission
Suivre le côté vente et signaler ce qui bouge, sans attendre l'étude mensuelle.

## Étage
**T1.** Les calculs sont du SQL sur les vues existantes. Le modèle local n'entre
en jeu que pour les descriptifs (dès qu'ils seront capturés — cf. chantier D).

## Entrées
Vues `listings_sane`, `listing_benchmarks`, `opportunites`, `khet_stats`.
Bornes : `lib/market-bounds.ts` ↔ `listings_sane` (vente 800 k–100 M, 15–500 m²).

## Procédure
1. Médianes de prix/m² par khet sur **périmètre assaini uniquement**.
2. Comparer au snapshot précédent (`study/snapshots/`) → mouvements > 5 %.
3. Relever les décotes de la vue `opportunites` au-delà du seuil de config.
4. Émettre un `finding` par mouvement notable et par décote suspecte.

## Contrat de sortie
```json
{"khets_analyses": int, "mouvements": int, "decotes_signalees": int,
 "detail": [{"khet": str, "median_ppsqm": float, "delta_pct": float}]}
```

## Bandes normales
Mouvements de quartier : ±5 % entre deux cycles de 4 jours. Au-delà, c'est
presque toujours un effet de composition (un lot d'annonces neuves), pas le marché.

## Escalade
Mouvement > 15 % sur un khet expat → ticket `mouvement_anormal`, sévérité
moyenne : demander à Claude de vérifier s'il s'agit du marché ou d'un artefact.

## Modes de panne connus
- **Ne jamais refiltrer à la main** : toute statistique se calcule sur
  `listings_sane`. Un filtre local diverge fatalement des bornes centrales.
- La double médiane par condo (1 immeuble = 1 voix) neutralise la vétusté et la
  vue. Une médiane simple sur les annonces donne un chiffre différent et faux.
- Une décote > 40 % est presque toujours une erreur de classement, pas une
  affaire — c'est ce qui avait mis des locations en tête des opportunités.
