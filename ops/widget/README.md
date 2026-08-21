# Widget de bureau — comptes à rebours

Trois lignes posées sur le bureau : dans combien de temps part le prochain
scrap, dans combien de temps part la prochaine veille, et ce qui attend d'être
réglé côté agents. Rafraîchi à l'ouverture de session, à chaque sortie de veille
ou déverrouillage, toutes les 10 minutes, et les compteurs descendent à la
minute.

```
Scrap Lowi                     2 j 7 h
Veille Equance                3 j 14 h
Agents          8 escalades · 4 problemes
```

Un compteur passe **en rouge** sous 24 h (`seuil_rouge_heures`). Si sa cible a
été renommée ou supprimée, il affiche **`introuvable`** en rouge — il ne se tait
jamais en silence.

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

Les lignes affichées sont **exactement** celles listées dans `compteurs`
(config.json), plus la ligne Agents. Chaque compteur déclare sa source :

| `source` | `ref` | Origine |
|---|---|---|
| `agents` | une **famille** d'agents | `agents.json` (cadence) + `ledger.db` (dernier succès) → l'échéance la plus proche de la famille |
| `claude` | l'**id** d'une routine | cron recopié dans `config.json`, échéance recalculée localement |
| `tache` | le **nom** d'une tâche Windows | `Get-ScheduledTaskInfo` en direct |

**« Prochain scrap » ≠ « prochain déclenchement de la tâche ».** `LowiBKK-Agents`
part **tous les jours** à 01:00, mais les extracteurs n'ont une cadence que de
**4 jours** : viser la tâche annoncerait un scrap chaque nuit, faux trois nuits
sur quatre. Le compteur vise donc la famille `Extraction` — le premier créneau
où `orchestrator.py --due` jugera réellement les extracteurs dus. Ce calcul tient
compte de la lane du jour (`weekly` un jour sur sept, sur l'ordinal **UTC** : à
01:00 heure de Bangkok on est encore la veille en UTC, donc la lane d'un cycle
n'est pas celle de sa date affichée).

**Les routines Claude vivent côté serveur Claude, pas sur ce PC.** Aucune API
locale ne les expose : le widget recalcule leurs échéances à partir du cron
recopié dans `config.json` (heure locale + le décalage fixe propre à chaque
routine, `jitter_s`). Vérifié le 2026-08-10 puis le 2026-08-13 : le calcul
retombe à la seconde sur ce qu'annonce le serveur. **Si tu ajoutes ou modifies
une routine Claude, reporte-la dans `config.json`** — sinon le widget affichera
l'ancienne échéance sans le savoir.

### La ligne Agents

`8 escalades · 4 problemes` — deux compteurs de nature différente :

- **escalades** = tickets ouverts dans `agents/queue/` en attente d'une décision
  (`escalations.status='open'`) ;
- **problèmes** = sujets **DISTINCTS** de sévérité haute sur 7 jours, regroupés
  par (agent, nature), et bornés aux agents encore au registre.

Le regroupement n'est pas cosmétique. Mesuré le 2026-08-13 : **29 constats de
sévérité haute ne recouvraient que 4 sujets réels** — `overseer/agent_muet`
s'était répété 22 fois, une par cycle. Afficher 29 aurait fait crier au loup et
le compteur aurait cessé d'être lu (règle 2 du CLAUDE.md). Le détail des sujets
est en infobulle. Rien à traiter → la ligne dit `rien a regler`, en gris.

Une quatrième ligne n'apparaît **que si la collecte elle-même échoue** : sans
elle, le panneau afficherait des chiffres périmés sans le dire.

## Réglages — `config.json`

Relu à chaud : modifier le fichier suffit, pas besoin de redémarrer le widget.

| Clé | Effet |
|---|---|
| `ancrage` | `arriere_plan` (défaut) ou `bureau` — voir plus bas |
| `position` | pixels physiques ; `x` négatif = distance au bord **droit** |
| `largeur`, `opacite` | apparence |
| `taille_police` | taille du texte des lignes (12,5) ; intitulés et alerte s'en déduisent (−2,5). Élargir `largeur` si tu montes beaucoup |
| `rafraichissement_minutes` | période de collecte (10 par défaut) |
| `compteurs` | **les lignes affichées** : `libelle` + `source` + `ref` (voir tableau plus haut) |
| `seuil_rouge_heures` | en deçà, le compteur passe en rouge (24) |
| `taches_windows` | motifs de noms, jokers acceptés — alimente les compteurs `tache` |
| `routines_claude` | l'instantané des crons — **à tenir à jour à la main** |
| `verifier_ollama`, `modele_local` | contrôle de présence du modèle local |

Ajouter un compteur = une ligne dans `compteurs`, aucun code à toucher :

```json
{ "libelle": "Drain file", "source": "claude", "ref": "drain-agent-queue-lowi-bkk" }
```

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

> Deux pièges rencontrés à l'écriture, à garder en tête pour toute reprise :
>
> **PowerShell ignore la casse des noms de variables.** `$C` (la palette) et un
> `$c` de boucle sont la même variable ; `$CFG` (un chemin) et `$cfg` (un objet)
> aussi. Trois pannes silencieuses venaient de là.
>
> **`[int]` sur un double ARRONDIT** (à l'entier pair, en prime), il ne tronque
> pas. Un délai de 3,61 jours s'affichait « 4 j 14 h » — un compte à rebours en
> avance d'un jour. Utiliser `[Math]::Floor`.
