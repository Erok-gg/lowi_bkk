---
name: watch-sources
description: Tient le registre des sources immobilières candidates non encore couvertes, les sonde périodiquement, et escalade à Claude l'écriture d'un nouvel adaptateur quand une source devient intéressante.
---

# watch-sources

## Mission
Étendre la couverture au-delà des 4 sources actuelles, sans que ça repose sur le
fait que tu y penses.

## Étage
**T1 → T2.** La sonde est du HTTP ; l'écriture d'un adaptateur est du travail
Claude (accès dépôt, `scraper/adapters/base.py` à implémenter).

## Entrées
`agents/state/watch-sources/registre.json` — la liste des candidates, leur
dernier sondage, leur verdict.

## Procédure
1. Pour chaque candidate du registre : requête sur une page de liste Bangkok.
2. Relever : code HTTP, présence d'un blob structuré (`__NEXT_DATA__`, `ld+json`),
   ordre de grandeur du nombre d'annonces, présence d'un `robots.txt` permissif.
3. Marquer `prometteuse` si : HTTP 200, blob structuré présent, > 500 annonces
   Bangkok, robots.txt non interdisant.
4. Escalader l'écriture d'un adaptateur pour les nouvelles `prometteuses`.

## Contrat de sortie
```json
{"sondees": int, "prometteuses": int, "nouvelles_prometteuses": [str], "escalades": int}
```

## Bandes normales
Aucune escalade la plupart du temps. C'est un agent lent, cadence 14 jours.

## Escalade
Ticket `nouvelle_source`, sévérité basse. Porte : l'URL, le type de blob repéré,
le volume estimé, l'état du robots.txt. Demande à Claude : écrire
`scraper/adapters/<site>.py` + `scraper/config/<site>.json`, **sur une branche**.

## Modes de panne connus
- Respecter la posture du projet : usage perso non commercial, cadence ~hebdo,
  robots.txt respecté autant que possible. **Une source qui interdit
  explicitement le crawl ne doit pas être proposée.**
- Un site peut répondre 200 avec une page vide derrière un challenge : vérifier
  la présence du blob, pas seulement le code HTTP.
