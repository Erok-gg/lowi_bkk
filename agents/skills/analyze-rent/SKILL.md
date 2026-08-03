---
name: analyze-rent
description: Analyse du marché LOCATION puis recoupement vente↔location par immeuble pour calculer les rendements réels. Utiliser après un cycle d'extraction location.
---

# analyze-rent

## Mission
Suivre le côté location, puis apparier les deux marchés **par immeuble** pour
obtenir un rendement réel plutôt qu'un ratio de médianes indépendantes.

## Étage
**T1.**

## Entrées
Vues `listings_sane`, `rent_stats`, `listing_matches`, `yield_by_khet`.
Bornes : loyer 3 k–500 k THB/mois.

## Procédure
1. Médianes de loyer/m² par khet sur périmètre assaini.
2. Recoupement même-unité : même condo normalisé + khet + chambres + surface ±7 %.
3. Rendement **within-condo** : loyer et prix du MÊME immeuble, ≥ 5 condos
   appariés, sinon repli sur le ratio, marqué `†`.
4. Comparer au snapshot précédent → mouvements notables.

## Contrat de sortie
```json
{"khets_analyses": int, "condos_apparies": int, "mouvements": int,
 "detail": [{"khet": str, "median_rent_sqm": float, "yield_pct": float, "n_condos": int}]}
```

## Bandes normales
Rendement brut de quartier : 3–8 %. Au-delà de 9,5 %, suspecter un défaut de
donnée avant de crier à l'affaire.

## Escalade
Rendement > 10 % sur un khet entier → ticket `rendement_suspect`, sévérité
moyenne.

## Modes de panne connus
- **Le recoupement n'est PAS une fusion** : on associe vente et location, on ne
  confond pas les deux annonces.
- `lib/condo-name.ts` (TS) **diverge encore** de `_norm_condo` (Python) : ne
  jamais comparer un regroupement TS à un `unit_key` calculé en Python.
- Le badge `lowSample` (< 20 condos d'un côté) doit rester visible : un rendement
  sur 4 immeubles n'est pas un rendement de quartier.
