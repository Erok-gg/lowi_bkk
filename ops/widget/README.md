# Widget de bureau — prochaines échéances

Petit panneau posé sur le bureau : quand tourne la prochaine tâche Windows, la
prochaine routine Claude, le prochain cycle d'agents. Il se rafraîchit à
l'ouverture de session, à chaque sortie de veille ou déverrouillage, et toutes
les 10 minutes.

```
WINDOWS
Agents                    dem. 01:00
CLAUDE
Drain file agents         dem. 08:37
Veille prospection        17/08 08:04
Rapport mensuel           01/09 09:08
AGENTS
cycle                     dem. 01:00
dus au cycle                    4/15
7 escalade(s) · 28 constat(s) haut(s)
```

## Installation

```bash
pwsh -File "C:\Users\schoe\++FILES++\Lowi_bkk\ops\widget\installe.ps1"
```

Dépose un raccourci dans le dossier Démarrage et lance le widget. Aucun droit
administrateur, aucune tâche planifiée. Pour retirer :

```bash
pwsh -File "C:\Users\schoe\++FILES++\Lowi_bkk\ops\widget\installe.ps1" -Desinstalle
```

Clic droit sur le panneau : **Rafraîchir · Déplacer · Réglages · Quitter**.
« Déplacer » libère la fenêtre, on la fait glisser, on reclique « Fixer au
bureau » : la position est enregistrée dans `config.json`.

## Ce qu'il affiche, et d'où ça vient

| Bloc | Source | Fiabilité |
|---|---|---|
| **WINDOWS** | `Get-ScheduledTaskInfo` en direct | exacte |
| **CLAUDE** | cron recopié dans `config.json`, échéance recalculée localement | exacte tant que la config suit |
| **AGENTS** | `agents/agents.json` (cadence) + `agents/ledger.db` (dernier succès) | exacte |

**Les routines Claude vivent côté serveur Claude, pas sur ce PC.** Aucune API
locale ne les expose : le widget recalcule leurs échéances à partir du cron
recopié dans `config.json` (heure locale + le décalage fixe propre à chaque
routine, `jitter_s`). Les trois routines actives ont été vérifiées : le calcul
retombe à la seconde sur ce qu'annonce le serveur. **Si tu ajoutes ou modifies
une routine Claude, reporte-la dans `config.json`**, sinon le widget affichera
l'ancienne échéance sans le savoir.

**Un agent « dû » n'est pas un agent qui tourne.** Les agents ne partent que
lorsque la tâche `LowiBKK-Agents` se déclenche (quotidienne, 01:00) et
qu'`orchestrator.py --due` les juge dus. Le widget affiche donc le prochain
*créneau réel*, pas la date d'échéance théorique — en tenant compte de la lane
du jour (`weekly` un jour sur sept, calculée sur l'ordinal **UTC** : à 01:00
heure de Bangkok on est encore la veille en UTC, donc la lane d'un cycle n'est
pas celle de sa date affichée).

La dernière ligne n'apparaît **que s'il y a quelque chose à signaler** :
modèle local injoignable, escalades ouvertes, constats de sévérité haute sur
7 jours, erreurs de collecte (détail en infobulle).

## Réglages — `config.json`

Relu à chaud : modifier le fichier suffit, pas besoin de redémarrer le widget.

| Clé | Effet |
|---|---|
| `ancrage` | `arriere_plan` (défaut) ou `bureau` — voir plus bas |
| `position` | pixels physiques ; `x` négatif = distance au bord **droit** |
| `largeur`, `opacite` | apparence |
| `taille_police` | taille du texte des lignes (12,5) ; intitulés et alerte s'en déduisent (−2,5). Élargir `largeur` si tu montes beaucoup |
| `rafraichissement_minutes` | période de collecte (10 par défaut) |
| `taches_windows` | motifs de noms, jokers acceptés — ajoute ce que tu veux suivre |
| `masquer_taches_desactivees` | `true` par défaut |
| `prefixe_a_retirer` | préfixe ôté à l'affichage (`LowiBKK-`) |
| `routines_claude` | l'instantané des crons — **à tenir à jour à la main** |
| `agents_detail` | `false` = un compteur ; `true` = les 15 agents ligne par ligne |
| `verifier_ollama`, `modele_local` | contrôle de présence du modèle local |

## Les deux ancrages

- **`arriere_plan`** (défaut) — fenêtre de premier niveau maintenue au fond de
  la pile Z, sans activation ni entrée dans la barre des tâches. Derrière
  toutes les applications, réapparaît dès que le bureau est visible, **reste
  cliquable**, survit à un redémarrage d'Explorer.

- **`bureau`** — vraie fenêtre-fille du `WorkerW` d'Explorer, peinte dans le
  fond d'écran, derrière les icônes. Plus intégré, deux contreparties réelles :
  la couche des icônes couvre tout le bureau et **intercepte la souris**, donc
  le widget n'y est plus cliquable (le piloter par `config.json`) ; et un
  redémarrage d'Explorer détruit le parent, donc la fenêtre — c'est pour ça que
  `garde.vbs` le relance.

## Empreinte

Un processus `pwsh` avec une fenêtre WPF, ~50 Mo de jeu de pages, endormi entre
deux relevés. Ce qui a été fait pour le tenir bas :

- aucune dépendance à `System.Windows.Forms` ni `System.Drawing` (le menu est un
  `ContextMenu` WPF, pas une icône de zone de notification — deux assemblies en
  moins) ;
- la collecte tourne dans un **processus court et séparé** (`collecte.ps1`) qui
  écrit `etat.json` puis meurt : rien de lourd ne reste chargé, et l'interface
  ne gèle jamais ;
- l'interface n'est **reconstruite que si `etat.json` a changé** ;
- `EmptyWorkingSet` après chaque reconstruction rend les pages au système ;
- minuterie à 15 s (relève du drapeau de réveil), collecte toutes les 10 min.

## Fichiers

| | |
|---|---|
| `widget.ps1` | la fenêtre |
| `collecte.ps1` | relève les trois sources → `etat.json` (exécutable seul : `-Ecran`) |
| `etat_agents.py` | lit `ledger.db` en **lecture seule** (jamais de verrou sur un cycle en cours) |
| `garde.vbs` | lance sans fenêtre et relance si ça meurt |
| `installe.ps1` | raccourci Démarrage, `-Desinstalle` pour retirer |
| `config.json` | tous les réglages |
| `widget.log` | journal borné à 200 Ko |

## Dépannage

Vérifier la collecte seule, sans interface :

```bash
pwsh -File "C:\Users\schoe\++FILES++\Lowi_bkk\ops\widget\collecte.ps1" -Ecran
```

Le widget ne s'affiche pas → `widget.log`. Rien dedans → le gardien n'a pas
démarré : lancer `garde.vbs` à la main.

> Piège rencontré à l'écriture, à garder en tête pour toute reprise :
> **PowerShell ignore la casse des noms de variables.** `$C` (la palette) et un
> `$c` de boucle sont la même variable ; `$CFG` (un chemin) et `$cfg` (un objet)
> aussi. Trois pannes silencieuses venaient de là.
