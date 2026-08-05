---
name: extract-livinginsider
description: Extraction LivingInsider vers Supabase. Parsing ld+json (ItemList en liste, Product en fiche), filtre Bangkok au texte libre de l'adresse. Utiliser pour lancer, diagnostiquer ou réparer le scrap LivingInsider.
---

# extract-livinginsider

## Mission
Mettre à jour les annonces LivingInsider. **Source ajoutée le 2026-08-05**,
aucune donnée de référence encore mesurée — les bandes ci-dessous sont
provisoires, à recalibrer après les premiers runs réels.

## Étage
**T0 — déterministe.**

## Entrées
`scraper/config/livinginsider.json`

## Procédure
`run.py --source livinginsider --full --geocode --store supabase`

Une seule passe (sale + rent dans la même config, comme PropertyScout) —
pas de scrap ciblé par district pour l'instant.

## Contrat de sortie
```json
{"nouvelles": int, "changees": int, "retirees": int, "traces_erreur": int}
```

## Bandes normales
**Provisoires** (aucun run de production au 2026-08-05) : `nouvelles` 5–1500
sur le premier run, beaucoup plus bas ensuite (voir panne connue ci-dessous).
`traces_erreur` 0–5.

## Escalade
`nouvelles` = 0 ET `traces_erreur` = 0 sur un run où `max_pages` n'a pas
changé → ticket `parser_break` (le format d'adresse a pu changer, cf. panne
connue).

## Modes de panne connus
- **Aucune dédup incrémentale possible.** Contrairement à FazWaz/DDproperty/
  PropertyScout, la page de LISTE ne porte aucun prix (seulement des URLs
  nues) → `run.py` ne peut jamais sauter une fiche déjà connue au prix
  inchangé. **Chaque scan revisite TOUTES les fiches**, indéfiniment. Coût
  de scrape structurellement plus élevé, à surveiller sur la durée du run —
  si ça devient un problème, réduire `max_pages` avant d'envisager autre
  chose.
- **Flux national, filtrage Bangkok imparfait.** L'adresse n'est pas
  formatée de façon homogène : certaines fiches donnent proprement
  « ... District, Bangkok », d'autres du texte mêlé sans le mot "District"
  (adresse thaï/anglais mélangée). Le filtre retombe alors sur un motif
  « ... Bangkok 10xxx » (code postal) et devine le district avec les 2
  derniers mots avant le code postal — imprécis mais sans faux positif
  mesuré (17 fiches réelles testées le 2026-08-05, 3 hors Bangkok toutes
  correctement écartées). Le texte de secours ne canonise pas toujours vers
  un nom de khet officiel (ex. "Nuea Vadhana" au lieu de "Watthana
  District") ; `--geocode` rattrape via lat/lng quand Nominatim trouve le
  nom de condo (taux de hit condo thaï ~35-40%, cf. méthodo stats khet).
  Une fiche sans motif reconnaissable (ni forme propre, ni code postal
  Bangkok) est écartée plutôt que devinée à l'aveugle.
- **Pas de coordonnées serveur.** Comme Nestopa : la page ne porte que des
  marqueurs de POI proches (hôpitaux, transports), jamais le bien
  lui-même. `--geocode` est donc quasi indispensable ici, pas optionnel.
- **Pas de tenure/quota par fiche.** Seulement des filtres de RECHERCHE
  globaux (« Freehold/Leasehold », « Foreign Quota »), jamais un attribut
  affiché sur l'annonce elle-même. `tenure` posé à `freehold` par défaut
  (comme DDproperty quand `tenureCode` est absent), `quota` toujours None.
- **`posted_at`** ("Created DD/MM/YYYY") capturé mais À NE PAS traiter comme
  fiable sans le même contrôle qui a invalidé la substitution DDproperty
  (cf. journal technique 2026-08-02, écart `first_seen − posted_at` mesuré
  à −16 j sur DDproperty) — même prudence tant que non vérifié ici.
- **Vérifié indépendant** (2026-08-05) : contrairement à DotProperty (voir
  `agents/state/watch-sources/registre.json`), les images sont servies
  depuis `www.livinginsider.com` — pas de CDN FazWaz/DDproperty/
  PropertyScout détecté sur l'échantillon testé. Inventaire propre, pas une
  resyndication.
