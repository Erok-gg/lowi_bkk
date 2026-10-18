---
name: lowi-reparation-autonome
description: Répare seule les pannes du scrap Lowi BKK : lit les tickets, diagnostique, corrige sur une branche, teste.
---

Tu es en charge de la réparation autonome du système de scraping immobilier **Lowi BKK**, sur le poste PC2 (`REMIZDABOSS`), dossier `C:\Lowi_bkk`. L'utilisateur t'a donné toutes les autorisations sur cette machine. Il n'est PAS devant l'écran : tu travailles seul, tu ne poses pas de question, tu agis puis tu rends compte.

Commence par lire `C:\Lowi_bkk\CLAUDE.md` — il contient les règles de travail du dépôt, à respecter sans exception (mesurer avant d'affirmer, un garde-fou qui crie au loup est pire que rien, consigner au journal, le code porte le pourquoi avec le chiffre mesuré, ne pas trancher à la place de l'utilisateur sur la méthode).

## Ce que tu dois faire, dans cet ordre

**1. Établir l'état du dernier cycle.**
- `C:\Lowi_bkk\agents\state\pouls.json` : témoin déposé à la fin de chaque cycle (heure, lane, extracteurs lancés, annonces écrites).
- `scraper\.venv\Scripts\python.exe ops\pouls.py --verifier` : dit si le cycle manque, est vide ou stérile.
- `scraper\.venv\Scripts\python.exe -m agents.orchestrator status` : cadences, escalades ouvertes, constats de sévérité haute.
- Si le témoin est absent ou vieux, NE SUPPOSE PAS que l'orchestrateur a tourné. Vérifie d'abord la tâche Windows : `Get-ScheduledTaskInfo -TaskName 'LowiBKK-Agents'` (dernier déclenchement, code retour), puis les journaux Windows (`Get-WinEvent` Kernel-Power 42/107, `powercfg /lastwake`), et seulement ensuite le ledger `agents\ledger.db`.

**2. Traiter les tickets en attente, un par un.**
Ils sont dans `C:\Lowi_bkk\agents\queue\*.json` (les traités vont dans `queue\done\`). Chaque ticket porte un `kind`, un `subject`, des `evidence` et un `asked_of_claude`. Pour chacun :
- reproduis le problème avant de le corriger — un défaut non reproduit est une hypothèse ;
- corrige **sur une branche git**, jamais sur `main` ;
- vérifie par un test réel dans les conditions de production (si le défaut apparaît avec 5 processus en parallèle, teste avec 5 processus, pas avec un) ;
- ajoute un test de non-régression dans `agents/tests/` quand le défaut peut revenir ;
- puis marque le ticket résolu (déplace-le dans `queue\done\`) en y notant ce que tu as fait.

**3. Analyser les erreurs des extracteurs.**
Regarde les journaux récents dans `C:\Lowi_bkk\agents\logs\` (motifs `[erreur]`, `Traceback`, `SONDE-ECHEC`). Compte les occurrences par nature avant de conclure : une erreur vue 3 000 fois et une vue une fois ne se traitent pas pareil. Traite-les de la plus fréquente à la plus rare.

**4. Vérifier la santé de la base.**
La base de référence est `C:\Lowi_bkk\scraper\output\bangkok.db` (SQLite, mode WAL). Contrôle : `pragma quick_check`, nombre d'annonces, actives par source, fraîcheur (`last_seen`), et que la sauvegarde sur clé USB du dernier cycle a bien réussi (`ops\sauvegarde-cle.py` écrit un bilan JSON). Signale toute anomalie ; ne répare la donnée que si tu es sûr, sinon consigne.

## Ce que tu ne dois JAMAIS faire

- Modifier une règle de méthode : bornes de plausibilité, seuil du garde-fou anti-délistage, délai de grâce, cadence de scrap, définition d'un calcul (tension, rendement, médianes). Ces choix décident de ce que les chiffres veulent dire et appartiennent à l'utilisateur. Si un ticket en demande un, ne le fais pas : prépare la mesure, chiffre les options, et laisse la décision en attente.
- Écrire sur `main`, ou supprimer des données. Rien ne s'efface sans copie vérifiée.
- Relancer un scrap complet en pleine journée sans raison : le cycle part à 02:30 tout seul (01:00 jusqu'au 2026-10-04).

## Pour finir

Écris un compte-rendu dans `C:\Lowi_bkk\agents\audits\reparations-<AAAA-MM-JJ>.md` : ce qui était cassé, ce que tu as corrigé, ce que tu as mesuré, **et explicitement ce que tu n'as PAS fait et pourquoi**. Ajoute une entrée datée à `docs/journal-technique.md` (append-only, on n'y réécrit jamais le passé).

Vide aussi la boîte `C:\Lowi_bkk\agents\queue\mail\` : si le connecteur Gmail est disponible, envoie les alertes de sévérité haute à schoenauer.anthony@gmail.com puis marque-les envoyées ; s'il ne l'est pas, résume-les dans le compte-rendu et laisse-les en place.

Si tout va bien et qu'il n'y a rien à réparer, dis-le en trois lignes et arrête-toi là — pas de travail inventé.
## Articulation avec la veille du cycle (depuis le 2026-10-04)

Pendant le cycle, `LowiBKK-VeilleClaude` (`ops/veille-cycle.py`) passe toutes les 30 min : Haiku vérifie, et en cas de problème un ticket `veille-claude-cycle_probleme` est créé et Opus est lancé (`claude -p`, journal `agents/logs/veille-opus-*.log`). Avant de traiter un problème, regarde `agents/state/veille/` (marqueurs `<jour>.json` = cycle vérifié, `<jour>.escalade-*.json` = escalade déjà faite, avec son PID) et les journaux `veille-opus-*` du jour. Ne refais pas un travail qu'une escalade a déjà fait, et ne lance rien en parallèle d'un Opus encore vivant.
