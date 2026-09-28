---
name: drain-tickets
description: Draine automatiquement, en fin de cycle sur PC2, les tickets organize/comparaison_deleguee — Haiku (claude -p) constate les 6 faits, decider() tranche. Utiliser pour diagnostiquer la file agents/queue/ ou un drainage en échec.
---

# drain-tickets

## Mission
Refermer la boucle T2 sans main. Jusqu'au 2026-09-28, la routine
`drain-agent-queue-lowi-bkk` vivait dans le profil PC1 et était désactivée
depuis le 25/08 : 33 tickets en attente, rien drainé depuis le 16/09.

## Étage
**T2 — Claude par ligne de commande** (`claude -p`, Haiku, même appel que
`social-leads`). Le modèle CONSTATE les six faits du contrat d'`organize`, il
ne rend pas de verdict : `organize.appliquer_reponses()` → `decider()` tranche,
exactement comme un ticket traité à la main.

## Entrées
`agents/queue/*-organize-comparaison_deleguee.json` + leur lot
`agents/state/organize/lots/<ticket>`. Au plus `DRAIN_MAX_TICKETS` (12) par
cycle, les plus anciens d'abord.

## Procédure
1. Lots de 15 paires → un appel Haiku (consigne = `organize.SYSTEM`).
2. Chaque réponse est recomparée aux faits recalculés **en code** depuis le
   texte de la paire (`verite_code`) : c'est la mesure permanente du modèle.
3. Réponses → `agents/state/organize/reponses/<ticket>.json` → `appliquer_reponses`.
4. Ticket refermé seulement si au moins une réponse est revenue.

Mesure sans rien écrire :
`scraper/.venv/Scripts/python.exe -m agents.bots.drain_tickets --mesure <ticket>`.

Les autres tickets (alertes, parser_break…) restent ouverts : ils sont
seulement comptés (`autres_par_nature`).

## Contrat de sortie
```json
{"tickets_draines": int, "tickets_restants": int, "paires": int, "reponses": int,
 "revue_ajoutee": int, "abstentions": int, "rejets": int, "paires_fausses": int,
 "echecs_appel": int, "cout_usd": float, "autres_tickets_ouverts": int,
 "autres_par_nature": {}, "detail": []}
```

## Bandes normales
Provisoires : `paires_fausses` ≤ 5 % des réponses ; `abstentions` majoritaires
(77 % mesuré en mode extraction le 2026-07-31).

## Escalade
- `extraction_degradee` (medium) : > 5 % des extractions contredites par le code.
- `haiku_injoignable` (medium) : tous les appels en échec — le plus souvent la
  session `claude` du poste a expiré (vu le 2026-09-28 : « OAuth session
  expired »), à reconnecter par `claude` puis `/login` dans un terminal.
- `drainage_echec` (medium) : un ticket n'a pas pu être traité, retenté au cycle suivant.

## Modes de panne connus
- Session `claude` expirée : aucun ticket drainé, les tickets restent ouverts
  (rien n'est perdu), `social-leads` tombe en même temps.
