---
name: social-leads
description: Aval automatique de la collecte Facebook immo — extraction structurée par Claude (Haiku, CLI), rapprochement avec les condos Lowi, chargement dans social-leads.db. Utiliser pour lancer, diagnostiquer ou réparer la chaîne social_leads.
---

# social-leads

## Mission
Transformer chaque `scraper/output/social/immo_YYYY-MM-DD.json` (collecte brute
de `LowiBKK-ScrapeImmoFacebook`) en lignes de `social_leads`, sans main.
Jusqu'au 2026-09-13, rien ne lisait ces fichiers : la « routine Claude/Haiku »
annoncée le 12/09 n'existait pas.

## Étage
**T2 — Claude par ligne de commande** (`claude -p`, Haiku, présent sur le
poste depuis le 2026-08-21), pour la seule étape qui exige un modèle : lire du
texte libre thaï/anglais. Tout le reste est du code : `vendeur` et `quota`
sont tranchés par regex (le modèle inventait un propriétaire par défaut),
le rapprochement est une distance d'édition, le chargement du SQL.

## Entrées
`scraper/output/social/immo_*.json` sans `_extrait_resolu.json` à côté —
l'état, c'est le disque. `scraper/social/immo-resolve.mjs`,
`scraper/load_social_leads.py --sqlite` (base `social-leads.db`, séparée de
la référence par décision du 2026-09-12).

## Procédure
1. Lots de 15 posts → un appel `claude -p --model haiku --tools "" --setting-sources ""`
   (contexte minimal : ~48 k tokens mis en cache au 1er appel, lus ensuite).
   Prompt et schéma = ceux de `immo-extract.mjs`.
2. Normalisation des types + décisions du code → `immo_..._extrait.json`.
3. `node immo-resolve.mjs` → `..._extrait_resolu.json`.
4. `load_social_leads.py --sqlite` (upsert par id de contenu).

Rejeu manuel : `scraper/.venv/Scripts/python.exe -m agents.bots.social_leads [fichier]`.

## Contrat de sortie
```json
{"fichiers": int, "posts": int, "extraites": int, "echecs_extraction": int,
 "annonces": int, "resolues": int, "chargees": int, "cout_usd": float,
 "detail": [{"fichier": str, "posts": int, "chargees": int}]}
```

## Bandes normales
Provisoires, à recalibrer après une semaine : `posts` 40–150 par collecte ;
`echecs_extraction` ≤ 10 % ; `chargees`/`posts` 10–40 % (le filtre
`collecte_solide` ne garde que les condos Bangkok avec nom, surface, prix et
chambres) ; `cout_usd` < 0,5 par collecte.

## Escalade
- `collecte_facebook_muette` (medium, pas de mail) : dernier `immo_*.json` de
  plus de 48 h → la tâche Windows ne produit plus (`ops/logs/facebook/`).
- `aval_social_echec` (medium) : un fichier n'a pas pu être traité — il sera
  retenté au cycle suivant tant que son `_extrait_resolu.json` manque.
- `extraction_degradee` (medium) : > 30 % des posts sans extraction
  exploitable → prompt ou modèle à revoir.

## Modes de panne connus
- `claude -p` exige une session connectée sur le poste ; hors session
  interactive (tâche planifiée sans logon) l'appel échoue → `aval_social_echec`.
- Réponse du modèle hors JSON ou tableau incomplet : les posts manquants
  comptent en `echecs_extraction`, le fichier est quand même écrit.
- `immo-resolve.mjs` lit `scraper/output/bangkok.db` en lecture seule ; un
  verrou d'écriture long peut le faire échouer → retenté au cycle suivant.
