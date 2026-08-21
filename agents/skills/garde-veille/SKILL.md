---
name: garde-veille
description: Empêche Windows de mettre la machine en veille moderne pendant un cycle de scrap, et distingue une interruption par veille d'une vraie panne. Utiliser pour diagnostiquer un run 'interrompu' ou comprendre pourquoi un extracteur s'est arrêté sans erreur.
---

# garde-veille

## Mission
Poser la demande d'éveil Windows (`SetThreadExecutionState`) pour tout le
process orchestrateur, avant que le premier agent long ne démarre — et
étiqueter correctement les runs `interrompu` causés par une mise en veille,
pour que watch-health/overseer ne les traitent pas comme des pannes de code.

## Étage
**T0 — déterministe.** Famille `Supervision` : tourne en tout premier, avant
même le Prelude (voir `agents/orchestrator.py:run_lane`). Marqué
`always_run: true` dans `agents.json` — il s'exécute à CHAQUE invocation de
l'orchestrateur, même si son dernier succès date de moins d'un jour, parce
que le verrou est propre au *process* : un succès d'hier ne protège en rien
le process lancé aujourd'hui.

## Pourquoi cet agent existe (2026-08-16)
Deux cycles d'affilée, `extract-ddproperty` tué en pleine extraction par
`Kernel-Power` (motif « Idle Timeout », journal Système Windows) —
`powercfg /requests` vide au moment du constat : aucun process ne tenait de
demande d'éveil. Ce portable ne supporte que l'état S0 (`powercfg /a`), sur
lequel Windows suspend le réseau des process d'arrière-plan dès l'inactivité
souris/clavier, scrap en cours ou non.

## Procédure
1. `agents/core/wake_lock.py:acquire()` — pose `ES_CONTINUOUS | ES_SYSTEM_REQUIRED`.
   C'est une demande **système**, pas liée à un process précis : tant qu'un
   thread la maintient, la machine ne part pas en veille idle. Pas de
   `release()` explicite en usage normal — Windows la relâche à la sortie du
   process (comportement documenté de l'API), et l'orchestrateur vit du
   premier au dernier agent de la lane.
2. Cherche dans le ledger les runs `status='interrompu'` des dernières 30 h
   (`FENETRE_HEURES` — un peu plus large qu'un cycle mesuré, 2 h à 6,2 h).
3. Pour chacun, interroge le journal Système
   (`Microsoft-Windows-Kernel-Power`, Id 506=veille/507=réveil) sur la
   fenêtre couvrant tous les runs interrompus trouvés, via PowerShell
   `Get-WinEvent` (~1-2 s, appelé une fois par cycle).
4. Si un événement 506 tombe entre le début et la fin du run interrompu →
   `finding` sévérité `low`, kind `coupure_veille` : ce n'est pas une panne,
   l'agent repartira de lui-même au prochain passage de la lane (voir
   ci-dessous).

## Ce que cet agent NE fait PAS
**Il ne relance rien lui-même.** Inutile : `orchestrator.is_due()` se fonde
sur le dernier run *réussi*, jamais sur le dernier run tout court — un
`interrompu` n'est jamais un succès, donc l'agent concerné est déjà « dû » et
repart tout seul dans la même lane, juste après `garde-veille`. La seule
vraie correction ici est le verrou d'éveil (étape 1) ; la détection (étapes
2-4) sert uniquement à ne pas crier au loup sur une coupure déjà
auto-corrigée par la cadence.

## Contrat de sortie
```json
{"verrou_veille_pose": bool,
 "runs_interrompus_examines": int,
 "coupures_veille_detectees": int}
```

## Bandes normales
`verrou_veille_pose` = `true` presque toujours (l'API échoue seulement dans
des cas anormaux — process sans droits, `kernel32` inaccessible). `false` =
alerte : le cycle qui suit n'est plus protégé, exactement le défaut d'origine.

`coupures_veille_detectees` > 0 est **normal** après une nuit où la machine a
somnolé — ce n'est un problème que si ça devient systématique malgré le
verrou posé (signe que `acquire()` échoue silencieusement, ou qu'une autre
cause de coupure existe : perte réseau, mise à jour Windows forcée, arrêt de
la tâche par `Arrêter la tâche après X heures`).

## Modes de panne connus
- **PowerShell absent ou journal Système inaccessible** (droits, GPO) :
  `_evenements_veille()` rentre une liste vide, aucune `coupure_veille` ne
  sera détectée même si la cause en était une — les runs `interrompu` restent
  alors muets, à diagnostiquer à la main (`Get-WinEvent` en direct).
- **`SetThreadExecutionState` réussit mais le portable repart quand même en
  veille** : à vérifier avec `powercfg /requests` PENDANT le cycle (pas
  après — la demande disparaît à la sortie du process). Cause possible :
  GPO ou pilote qui ignore la demande applicative (rare, mais existe sur
  certains portables en mode « veille moderne connectée » agressif).
- **Le format `/Date(ms)/`** vient de Windows PowerShell 5.1 (`ConvertTo-Json`
  legacy), pas de l'ISO 8601 qu'on pourrait attendre — si la machine passe un
  jour à PowerShell 7 par défaut, vérifier que le format n'a pas changé
  avant de faire confiance à `_parse_date_ps`.
