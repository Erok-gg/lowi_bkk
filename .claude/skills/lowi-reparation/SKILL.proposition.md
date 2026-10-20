---
name: lowi-reparation-autonome
description: Répare seule les pannes du scrap Lowi BKK : lit les tickets, diagnostique, corrige sur une branche, teste. (PROPOSITION du 2026-10-18 — non appliquée)
---

> Proposition issue de `docs/audit-reparateur-2026-10-18.md`. Les passages ajoutés sont marqués **[nouveau]**, ceux
> modifiés **[modifié]** ; tout le reste est le texte actuel.

## Règle 0 — ne rien dégrader **[nouveau]**
Aucune action qui risque de perdre, corrompre ou délister à tort une donnée, même pour réparer. Un doute = on
consigne et on s'arrête. Le ledger, `bangkok.db` et les tâches planifiées se lisent en **lecture seule**
(`sqlite3 …?mode=ro`) : `orchestrator status` et `Ledger()` referment des runs « orphelins » et ont déjà marqué
`interrompu` un run vivant (2026-09-08).

## Ordre de priorité — aussi l'ordre de sacrifice si le quota est court **[nouveau]**
1. le cycle part et finit (veille, coupure secteur/réseau, reprise) ;
2. les extracteurs ramènent des données ;
3. les garde-fous disent vrai (une fausse alerte se corrige **avant** toute enquête qu'elle motive) ;
4. performance et quota de la base.
Passe partielle : n'entamer 3 ou 4 qu'après avoir *vérifié* 1 et 2, et écrire dans le compte-rendu ce qui n'a pas été vu.

## Méthode **[nouveau]**
- Avant de diagnostiquer : chercher le symptôme dans `docs/journal-technique.md` — déjà connu ? déjà corrigé sur une
  autre branche ?
- Un ticket « cycle bloqué / manquant / vide / long » est **faux jusqu'à preuve du contraire** : contrôler PID vivant,
  mtime du log, tâche Windows (`Get-ScheduledTaskInfo`), puis ledger. Six cas au tableau de l'audit (lignes 1-6) étaient des fausses alertes ou des alertes mal nommées.
- Ne jamais écrire « cause établie » sans l'épreuve du correctif (passer par la nuit suivante ou un rejeu réel).
- Une fois un défaut corrigé, **chercher les autres appelants du même motif** (ex. `claude -p` sans
  `--strict-mcp-config`, `reap_stale`) avant de clore.
- Une seule branche de réparation continue, rebasée sur la précédente **non mergée** ; ne pas en créer une par jour.
  Le merge appartient à l'utilisateur.
- Un constat de sécurité de sévérité haute déjà au journal passe avant le reste.

## Ce que tu ne dois JAMAIS faire **[modifié]**
- Changer une **règle de méthode** : bornes de plausibilité, seuil anti-délistage, délai de grâce, cadence de scrap,
  définition d'un calcul. **Reclasser une cause** (une fausse alerte nommée correctement, comme `sitemap_non_regenere`
  au lieu de `parseur_casse`) n'est pas un changement de seuil : c'est permis, avec test et retour arrière.
- Écrire sur `main`, supprimer des données, relancer un scrap complet en pleine journée (cycle à 02:30).
- Lancer les tests T1/Ollama sur PC2 (`agents/t1-absent` : échec attendu, 28 min perdues le 2026-08-29).

## Tout le reste : inchangé
Étapes 1 à 4, compte-rendu, journal, boîte `queue/mail/`, articulation avec la veille (texte actuel).
Une précision **[modifié]** à l'étape « mail » : une alerte de sévérité haute qui n'a produit ni mail ni ticket est
elle-même un défaut à signaler (garde-fou muet).
