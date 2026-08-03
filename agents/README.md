# Système d'agents — Lowi BKK

**Ce que le pitch deck promet, et ce qui tourne vraiment.**

Le deck (slide 14) annonce « The Agent Pipeline — 12 Bots ». Avant le 2026-07-31,
tout le code existait mais **rien ne se déclenchait seul** : les trois tâches
Windows créées le 11/07 n'ont jamais tourné une seule fois, et l'étude de marché
s'était arrêtée au 09/07 sur des données du 29/07.

## Démarrage

```bash
scraper/.venv/Scripts/python.exe agents/orchestrator.py status
```

| Commande | Effet |
|---|---|
| `status` | Les 12 agents, leur cadence, leur dernier succès, ce qui est dû |
| `due` | Uniquement ce qui est dû |
| `run <agent>` | Un agent, maintenant (`--dry-run` pour voir sans faire) |
| `run-lane sale\|rent\|weekly` | Toute une lane (`--all` ignore la cadence) |
| `--due` | Ce que la tâche planifiée appelle |

## Les 12 agents

| Agent | Famille (deck) | Étage | Cadence |
|---|---|---|---|
| `extract-fazwaz` `extract-ddproperty` `extract-propertyscout` `extract-nestopa` | Extraction ×4 | T0 | 4 j |
| `watch-health` | Surveillance | T1→T2 | 1 j |
| `watch-sources` | Surveillance | T1→T2 | 14 j |
| `analyze-sale` `analyze-rent` | Analyse ×2 | T1 | 4 j |
| `organize` | Data organizing | T0+T1 | 4 j |
| `report` | Data reporting | T0→T2 | 4 j |
| `storage` | Security & storage | T0 | 7 j |
| `overseer` | Overseeing | T1 | 1 j |

Chacun a son dossier `skills/<agent>/SKILL.md` : mission, entrées, procédure,
**contrat de sortie** (que l'overseer vérifie), bandes normales, règles
d'escalade, modes de panne connus.

## Les trois étages, et pourquoi

**T0 — déterministe (8 agents).** Aucun LLM. Ce qui leur manquait n'était pas de
l'intelligence, c'était l'orchestration et une trace. Y mettre un modèle
ajouterait du non-déterminisme à du code qui marche.

**T1 — local `qwen3:8b`, en MODE EXTRACTION uniquement.** Le modèle constate des
faits ; c'est du code qui décide. Voir plus bas.

**T2 — Claude, par file de tickets.** Il n'y a ni CLI `claude` ni clé API sur la
machine : les agents déposent des tickets dans `queue/`, qu'une session Claude
planifiée draine — elle a l'accès au dépôt et peut vraiment réparer un adaptateur.

## Ce que la mesure a imposé (2026-07-31)

650+ appels sur des paires réelles du dépôt. Les résultats ont dicté
l'architecture, pas l'inverse.

| Constat | Conséquence dans le code |
|---|---|
| `/no_think` est **silencieusement ignoré** ; le raisonnement part dans `message.thinking` et `content` reste **vide** → 0/10 | `local_llm.py` pilote le raisonnement par le paramètre **natif `think`** |
| Une sortie vide s'écrit `null` en base **sans aucun bruit** | Toute réponse vide est une **panne**, jamais un résultat |
| Prompt bref **92 %** vs procédure verbeuse **69 %** — écart invisible sur 10 paires (9/10 pour les deux) | Les SKILL.md restent **courts** ; et **un jeu de 10 ne départage rien** |
| Forcer l'abstention par le prompt → **12/100** | On ne demande jamais au modèle de douter |
| Verdict direct : 92 % mais **0 %** d'abstention | **Mode extraction** : le modèle constate, `decider()` tranche → **99 %** et **77 %** d'abstention |
| 3 votes = mêmes 8 erreurs, 3× le coût | Pas d'auto-cohérence |
| qwen2.5 rendait `confidence: 0.9` sur ses réponses fausses | La confiance auto-déclarée n'est **jamais** un seuil |

Garde-fou permanent :

```bash
scraper/.venv/Scripts/python.exe agents/tests/test_local_llm.py
```

Seuils : **≥ 90/100** de justesse, **≥ 70 %** d'abstention. Ne pas les relâcher
pour faire passer le test — ils viennent d'une mesure. Dernier passage :
**99/100**, pré-filtre 120/120, abstention 77 %, 0 panne.

> Ce test a déjà servi : à son premier passage il a trouvé un défaut non pas dans
> le modèle, mais dans **son propre jeu d'étiquettes** — 10 paires sur 120
> étiquetées avec la mauvaise précédence (« séquentiel » testé avant « les deux
> actives », alors qu'une annonce peut porter une `delisted_at` passée tout en
> étant active). Corrigé par `agents/tests/relabel.py`. Le modèle avait raison ;
> la mesure était fausse.

## Interdits

- **Aucune fusion, aucune suppression d'annonce.** Le 28/07, « 1 399 doublons
  exacts » s'est révélé être des lots distincts versés en lot par une agence.
  Une dédup aurait effacé de l'offre réelle.
- Les verdicts sur paires ambiguës vont en **file de revue**
  (`state/organize/revue.jsonl`) et n'influencent **aucune** statistique.
- Claude écrit sur une **branche**, jamais sur `main`.

## Alertes

- `audits/CHANGELOG.md` — journal exhaustif, append-only.
- **E-mail** — sévérité haute uniquement. Déposé dans `queue/mail/`, envoyé par
  la session Claude planifiée via le connecteur Gmail (pas de mot de passe SMTP
  stocké sur la machine).

## Planification

**Une seule** tâche Windows : `LowiBKK-Agents`, quotidienne à 08:00 →
`orchestrator.py --due`. L'orchestrateur lit le ledger et décide ce qui est dû ;
le rattrapage vient de la base, pas de `StartWhenAvailable`.

Réinstaller / vérifier :

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File ops/install-agents-task.ps1
```

Le script **vérifie le XML réellement enregistré** et refuse tout `\"` — c'est
ce contrôle qui manquait en juillet et qui a laissé trois tâches mortes invisibles
pendant trois semaines.

> ⚠ `Stop-ScheduledTask` arrête la tâche **mais pas ses petits-fils** : un
> `run.py` lancé par l'orchestrateur survit à l'arrêt et continue de scraper,
> orphelin et non tracé. Vérifié le 2026-07-31. Après un arrêt manuel :
> `Get-CimInstance Win32_Process -Filter "Name like 'python%'"` puis
> `taskkill /PID <id> /T /F`.

Les runs restés en `running` après un processus tué sont refermés en `interrompu`
par `Ledger.reap_stale()` au démarrage suivant — sinon l'agent paraîtrait
éternellement en cours et ne serait jamais relancé.

## Sur le deck

« 12 bots » et « auditable from a human perspective » sont désormais exacts.
**« Real-time extraction » et « continuously » restent faux** : la cadence est de
4 jours, choix anti-ban assumé. Formulation défendable — *« Automated
multi-source extraction on a 4-day cycle, with per-source health monitoring and
audited runs »*.
