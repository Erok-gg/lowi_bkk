# Migration vers le 2e poste

Deux scripts et une liste de ce qui ne se transfère pas.

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File ops\migration\exporte-poste.ps1 -AvecSecrets
```

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File ops\migration\importe-poste.ps1 -Colis D:\lowi-transfert-2026-08-21
```

L'export tourne sur l'ancien poste, l'import sur le nouveau **depuis le dépôt déjà cloné**.
Sans `-AvecSecrets` le colis pèse 2,8 Mo (mesuré le 2026-08-21) ; `-AvecArchive` y ajoute
les 708 Mo de `archive/lowi-archive.db`.

---

## Ce qui ne se transfère pas, et pourquoi

**Les connecteurs MCP : il n'y a rien à copier.** Vérifié le 2026-08-21 dans
`~/.claude.json` — `mcpServers` est **vide**, au niveau global comme au niveau du projet
Lowi_bkk. Les six connecteurs utilisés ici (Supabase, Gmail, Drive, Vercel, Agenda,
visualize) sont des connecteurs **de compte claude.ai**, hébergés côté serveur. Ils
reviennent seuls avec `claude login`. Le seul MCP réellement local sur cette machine est
`sui-knowledge-docs` dans `~/.claude/settings.json`, sans rapport avec Lowi — le colis
l'emporte quand même.

L'export en pose l'**inventaire** dans `inventaire.json` : ça sert à vérifier au bout que
rien ne manque, pas à restaurer.

**Les routines Claude planifiées** (`drain-agent-queue-lowi-bkk`, `rapport-mensuel-lowi-bkk`,
`veille-prospection-equance`, `rapport-matinal-koh-phangan`, `lowi-notif-lancement`) vivent
elles aussi côté serveur. Elles tournent **déjà**, indépendamment du poste. Le colis en
emporte les `SKILL.md` à titre de référence. **Ne pas les recréer** sur le 2e poste : ça
ferait doublon.

**`scraper/.venv` et `node_modules`** se reconstruisent (`pip install -r`, `npm ci`). Les
copier transporterait des binaires liés à l'ancienne machine.

**Les tâches Windows** sont exportées en XML *pour référence seulement*. La réinstallation
passe par `ops/install-agents-task.ps1` et `ops/install-boot-task.ps1`, qui dérivent leurs
chemins de leur propre emplacement. Réimporter le XML figerait les chemins de l'ancienne
machine — c'est exactement le défaut du 2026-07-11, où trois tâches n'ont jamais tourné
pendant vingt jours.

---

## Ce qui se transfère, et ce que ça coûte de l'oublier

| Élément | Conséquence de l'oubli |
|---|---|
| `agents/ledger.db` | `is_due()` croit que rien n'a jamais tourné → les 5 extracteurs repartent en `--full` dès le 1er cycle (mesuré le 2026-08-20 : **6 h 30**) |
| `agents/state/` | les journaux de reprise repartent de zéro → `organize` refait des paires déjà traitées |
| `agents/queue/` | les tickets T2 en attente sont perdus (13 au 2026-08-21) |
| `.env.local`, `scraper/.env` | **sans `SUPABASE_DB_URL`, le scrap n'écrit nulle part** |
| mémoire Claude | 7 fichiers ; le dossier porte le chemin du projet **dans son nom**, l'import le recalcule |
| `.claude/settings.local.json` | Claude redemande chaque permission déjà accordée |
| `ops/widget/config.json` | les crons Claude y sont recopiés **à la main** — rien ne signale la désynchronisation |
| cache Nominatim | 286 Ko ; le refaire coûte du 1 req/s |

Le nom du dossier de mémoire encode le chemin : `C:\Users\schoe\++FILES++\Lowi_bkk`
devient `C--Users-schoe---FILES---Lowi-bkk` (tout caractère non alphanumérique → tiret).
L'import le **recalcule pour la machine cible** : si l'utilisateur ou le chemin diffèrent,
réutiliser le nom d'origine déposerait la mémoire dans un dossier que Claude n'ouvrirait
jamais — panne muette.

---

## Le 2e poste n'a pas Ollama : ce que ça change vraiment

Trois modules appellent le modèle local. Ils ne pèsent pas du tout le même poids.

**`overseer` et `watch_health` : le modèle ne fait que RÉDIGER.** Il met en français un
constat que le code a déjà établi, et les deux appelants ont déjà leur repli
(`if red:` … sinon on garde le brut). Sans Ollama, ils dégradent proprement. **Aucune
modification de code nécessaire** pour la valeur produite.

**Mais `ask_safe` journalise chaque échec en constat de sévérité HAUTE** (`llm_panne`,
`local_llm.py:201`). Sans Ollama, c'est **jusqu'à 6 constats hauts par cycle, tous les
jours, indéfiniment** — 1 pour l'overseer, jusqu'à 5 pour watch-health. C'est précisément
le garde-fou qui crie au loup de la règle 2, et le compteur du widget virerait au rouge en
permanence sans jamais rien signaler de vrai. **Ce point doit être traité quelle que soit
l'option retenue** : il faut pouvoir déclarer T1 absent, pour que l'absence du modèle soit
un état normal et non une panne répétée.

**`organize` est le seul usage décisionnel.** Et son rendement mesuré est faible. Sur les
5 runs aboutis depuis le 2026-07-31, lus au ledger :

| Run | Paires soumises | Abstentions | Taux | **Ajoutées à la revue** | Reste ambigu |
|---|---|---|---|---|---|
| 31/07 | 40 | 34 | 0,85 | 6 | 22 071 |
| 06/08 | 300 | 300 | 1,00 | 0 | 23 566 |
| 11/08 | 300 | 27 | 0,09 | 1 | 25 848 |
| 12/08 | 40 | 40 | 1,00 | 0 | 26 108 |
| 17/08 | 300 | 295 | 0,983 | 0 | 28 306 |

**Sept entrées de revue en trois semaines**, pendant que le stock de paires ambiguës
montait de 22 071 à 28 306. Le tri SQL, lui, tranche 39 852 paires sur 68 458 (58 %) sans
aucun modèle. Autrement dit : perdre T1 sur `organize` coûte de l'ordre de **7 constats
par trois semaines**, pas la fonction.

> Le run du 11/08 (taux 0,09 au lieu de ~1,0) est l'anomalie déjà repérée par
> `agents/tests/echantillon_neuf.py`. Non élucidée.

`agents/tests/test_local_llm.py` ne peut pas tourner sans Ollama. Il doit être **sauté
explicitement**, jamais assoupli : ses seuils (≥ 90/100, ≥ 70 % d'abstention) sont le
garde-fou de la qualité T1 et devront resservir tels quels si un modèle local revient.

### Ce qui a été câblé (2026-08-21)

**Décision : la comparaison part en tickets, drainés par la routine
`drain-agent-queue-lowi-bkk`.** Pas de clé API sur la machine, pas d'Ollama distant.

Le déclencheur est un **marqueur par machine**, `agents/t1-absent` (gitignoré : le dépôt
est le même des deux côtés, le poste principal garde son modèle). `importe-poste.ps1`
**sonde** Ollama et ne pose le marqueur que s'il ne répond pas.

Ce que le marqueur change :

| Module | Sans marqueur | Avec marqueur |
|---|---|---|
| `overseer`, `watch_health` | le modèle rédige | texte brut, **et plus aucun constat `llm_panne`** |
| `organize` | 300 paires au modèle local | lot de **60** déposé en ticket |
| `orchestrator status` | `✓ qwen3:8b disponible` | `✓ T1 déclaré absent — délégué à Claude` |

**Le contrat de décision ne change pas.** Le ticket demande les **six mêmes faits**, et
c'est `decider()` qui tranche au retour. Déléguer la comparaison ne doit pas devenir
déléguer la décision : le verdict direct atteint 92 % de justesse mais **0 % d'abstention**
(0/30 sur les cas indécidables), l'extraction 91 % et **77 % d'abstention**. L'abstention
vient du code, c'est pour ça qu'elle est fiable.

Boucle de retour :

```bash
scraper/.venv/Scripts/python.exe -m agents.bots.organize --appliquer agents/state/organize/reponses/<ticket>.json
```

Deux journaux distincts, et c'est le point délicat : `paires-faites.txt` (**tranchée**)
et `paires-en-ticket.txt` (**soumise, en attente**). Une paire omise de la réponse
n'entre pas dans le premier — elle sera re-soumise. Les confondre reproduirait le défaut
du 2026-08-17, des paires en échec marquées « traitées » puis jamais re-tirées. Une paire
d'un ticket drainé sans réponse est libérée au dépôt suivant.

Vérifié par `agents/tests/test_tickets.py` (6 propriétés, dossier temporaire, ne touche
ni la vraie file ni le vrai journal) :

```bash
scraper/.venv/Scripts/python.exe agents/tests/test_tickets.py
```

**Défaut trouvé en testant, corrigé :** `escalation.create()` horodate à la seconde, donc
deux escalades du même agent et du même motif dans la même seconde portaient le même nom
et **la seconde écrasait la première sans bruit** — une escalade perdue, donc invisible.
Un suffixe numérique est désormais ajouté.

---

## Après l'import — à faire à la main

1. `claude login` — c'est ce qui ramène les connecteurs.
2. `scraper\.venv\Scripts\python.exe agents\orchestrator.py status` — vérifier les cadences et les escalades ouvertes.
3. **Éteindre les tâches `LowiBKK-*` de l'ancien poste**, sinon les deux machines scrapent la même chose en parallèle : doublons de requêtes vers les 5 sources, et risque de blocage côté sites.
4. Trancher la question T1 ci-dessus, et supprimer le colis s'il contenait les secrets.
