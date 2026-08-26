---
name: lowi-cycle
description: Opérer et diagnostiquer la boucle d'agents Lowi BKK (orchestrateur, lanes, ledger, tickets T2). À utiliser dès qu'il s'agit de lancer ou relancer un cycle, comprendre pourquoi un agent n'a pas tourné, rattraper un cycle manqué, drainer la file de tickets, ou toucher à agents.json / la tâche planifiée. Triggers — 'lance le cycle', 'relance les agents', 'pourquoi X n'a pas tourné', 'cycle manqué', 'rattrapage', 'orchestrator', 'lane', 'ledger', 'ticket', 'LowiBKK-Agents'.
---

# lowi-cycle

Doc de fond : [agents/README.md](../../../agents/README.md) · un agent en
particulier : `agents/skills/<agent>/SKILL.md`.

## D'abord, toujours

```bash
scraper/.venv/Scripts/python.exe agents/orchestrator.py status
```

Il dit qui est dû, le dernier succès de chacun, et si T1 est déclaré absent.
**Ne rien lancer avant de l'avoir lu** : `is_due()` se calcule depuis le ledger,
pas depuis l'horloge, et un agent peut avoir déjà tourné cette nuit.

Puis **nommer le poste** — `$env:COMPUTERNAME`. `BB-12` = PC1, sauvegarde, ne
scrape plus. `REMIZDABOSS` = PC2, coureur. La même commande est juste sur l'un
et destructrice sur l'autre.

## Les commandes, et ce qu'elles engagent

| | |
|---|---|
| `status` / `due` | lecture seule |
| `run <agent> --dry-run` | montre sans faire — le réflexe par défaut |
| `run <agent>` | un agent, hors cadence |
| `run-lane sale\|rent\|weekly` | toute une lane (`--all` ignore la cadence) |
| `--due` | ce que la tâche planifiée appelle à 01:00 |
| `run-lane --skip-extraction` | rejoue analyse/organisation/rapport/backup/overseer **sans retoucher au scrap** |
| `--boot` | reprise au logon ; ne pose jamais `--veille-a-la-fin` |

**Un scrap complet dure des heures.** Ne jamais lancer un extracteur « pour
voir » : `--dry-run`, ou un agent d'aval, ou `--skip-extraction`.

## Diagnostiquer « il n'a pas tourné »

Dans cet ordre — chaque étage a déjà été la cause au moins une fois :

1. **La tâche s'est-elle déclenchée ?** `Get-ScheduledTaskInfo LowiBKK-Agents`
   (`LastRunTime`, `LastTaskResult` — `0x00041301` = en cours). Trois tâches sont
   restées mortes et invisibles trois semaines en juillet.
2. **La lane contenait-elle quelqu'un ?** Le 2026-08-24 le cycle est parti à vide :
   lane calculée en UTC alors que le cycle part à 01:00 Bangkok. Garde-fou :
   `agents/tests/test_lanes.py`.
3. **Le ledger le croit-il déjà fait ?** `status` donne le dernier succès. Un run
   tué reste `running` jusqu'à ce que `reap_stale()` le referme en `interrompu`.
4. **La machine s'est-elle endormie ?** `finding coupure_veille` = veille, pas
   panne. `garde-veille` doit avoir tourné en premier.
5. **La sonde de structure a-t-elle échoué ?** `[SONDE-ECHEC]` dans les logs →
   escalade `parser_break` directe, l'adaptateur est cassé côté site.

## Interdits

- **Aucune fusion, aucune suppression d'annonce.** Les « 1 399 doublons » de
  juillet étaient des lots réels d'une agence.
- **Jamais `--full` avec une config ciblée** : scan partiel → délistage massif.
- Claude écrit sur une **branche**, jamais `main`.
- Après un `Stop-ScheduledTask`, les petits-fils survivent : vérifier
  `Get-CimInstance Win32_Process -Filter "Name like 'python%'"` avant de conclure.

## T1 absent (PC2)

Le marqueur `agents/t1-absent` déclare une absence **délibérée** — sans lui,
`ask_safe` produit jusqu'à 6 constats de sévérité haute par cycle, tous les jours.
`organize` dépose alors des lots de 60 paires en ticket. Retour :

```bash
scraper/.venv/Scripts/python.exe -m agents.bots.organize --appliquer agents/state/organize/reponses/<ticket>.json
```

`paires-faites` = tranchée · `paires-en-ticket` = soumise. Ne pas confondre.

## Fin de séance

Entrée datée dans `docs/journal-technique.md`, **avec ce qui n'a PAS été fait**.
