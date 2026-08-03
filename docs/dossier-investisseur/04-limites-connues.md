# 04 — Limites connues

> Ce document existe pour être lu **avant** de s'engager. Il liste ce qui manque,
> ce qui est fragile, et ce qui ressemble à une mesure sans en être une.
>
> Un dossier de données sans ce document n'est pas incomplet : il est suspect.
> Tout ce qui suit est vérifiable sur la base en dix minutes.

---

## Bloquant pour une commercialisation

### La série n'a que six semaines
Première annonce observée le **2026-06-21**, 17 jours de collecte effective.
Aucune affirmation de tendance, de saisonnalité ou de cycle n'est soutenable à
cette profondeur. Ce qui est vendable aujourd'hui, c'est la méthode et l'outil ;
la série est une promesse documentée, pas un livrable.

### Les annonces brutes ne sont pas redistribuables
Conditions d'utilisation des sources, et posture écrite du projet depuis l'origine.
Traité en détail dans [03](03-valeur-et-monetisation.md).

### L'année de construction n'est renseignée nulle part
**0 immeuble sur 4 514.** Conséquence directe : impossible de comparer deux biens
à vétusté égale, et impossible de distinguer une décote « bonne affaire » d'une
décote « immeuble de 1998 ». La méthode par médiane interne à l'immeuble
(voir [02](02-methode-et-differenciation.md)) absorbe partiellement le problème
pour les agrégats, mais **pas** pour l'évaluation d'un bien isolé.

C'est le chantier le plus rentable à court terme.

---

## Couverture partielle

### Le quota étranger n'est connu que sur 1,2 % des annonces
197 sur 18 879. Or c'est un critère **décisif** pour un acheteur étranger : un lot
en quota thaï ne lui est pas accessible en pleine propriété. La donnée existe chez
une source seulement, et de façon inconstante.

### La provenance n'est disponible que sur une source
`agent_id`, `agency_id`, date de mise en ligne réelle et signalement de
republication : **1 294 annonces, DDproperty uniquement**. C'est ce qui rend la
question des doublons décidable — donc elle n'est décidable que sur 7 % du stock.
Les trois autres sources n'exposent pas l'information de façon exploitable ; l'une
d'elles n'a pas encore été sondée pour cela.

### Les descriptifs ne commencent qu'aujourd'hui
La capture du texte libre a été mise en place le **2026-07-31**. Elle **n'est pas
rétroactive** : les 35 813 annonces déjà en base resteront sans descriptif. Et une
source sur quatre n'expose rien d'exploitable (champ absent ou simple redite des
caractéristiques déjà structurées).

### Le géocodage plafonne
Le service de géocodage utilisé réussit sur environ 35 à 40 % des noms de
résidences thaïes. Les annonces dont la source ne fournit pas de coordonnées
restent donc souvent rattachées à leur quartier par le texte, moins fiable.

---

## Ce qui ressemble à une mesure sans en être une

### La durée d'annonce n'est pas un temps de commercialisation
La base donne une durée moyenne de **11,0 jours** entre première observation et
délistage. **Ce chiffre ne doit pas être présenté comme un time-on-market.**

Raison : la première observation n'est pas la mise en ligne, c'est le moment où
notre collecte a croisé l'annonce. Avec une cadence de quatre jours, la mesure est
bornée par notre propre rythme, pas par le marché. La date de mise en ligne réelle
est désormais collectée — mais sur une seule source, et depuis peu.

### Un délistage n'est pas une vente
Une annonce peut disparaître parce qu'elle est vendue, louée, retirée, expirée, ou
simplement republiée sous un autre identifiant. C'est précisément pour cela que
l'écoulement se mesure par cohorte plutôt que par disparition d'annonce
(voir [02](02-methode-et-differenciation.md)) — mais aucune de ces séries n'est
une série de transactions.

**Il n'existe pas, dans ce système, de donnée de prix de transaction.** Tout est
prix d'affichage.

---

## Fragilités techniques

### Le scraping casse, et cassera encore
Le 2026-07-23, une source a changé la structure de ses pages : le collecteur a
continué de tourner sans erreur en ramenant zéro annonce, plusieurs jours durant.
C'est structurel — un site tiers ne prévient pas.

Ce qui a changé : la panne est désormais détectée le jour même par comparaison à
l'historique de la même source, et escaladée automatiquement. Le risque n'est pas
supprimé, il est **rendu visible rapidement**.

### L'automatisation date du 2026-07-31
Avant cette date, tout était lancé à la main. Trois tâches planifiées existaient
depuis le 11/07 mais **n'avaient jamais fonctionné une seule fois** — une erreur
de guillemets dans leur enregistrement les faisait échouer avant la première
instruction, silencieusement. Elles sont remplacées par une tâche unique dont
l'installation vérifie ce qui a réellement été enregistré.

Conséquence honnête : **le dispositif automatisé n'a pas encore d'historique de
fiabilité.** Son premier cycle complet est à venir.

### Deux implémentations de la même logique
La normalisation des noms d'immeubles existe en deux versions (application et
collecte) qui **divergent encore**. Un agent le signale à chaque cycle ; ce n'est
pas corrigé. Concrètement : on ne peut pas comparer un regroupement calculé d'un
côté à un identifiant calculé de l'autre.

---

## Dépendances

| | |
|---|---|
| Sources | 4 sites tiers, aucun contrat, aucun accès API |
| Hébergement | Un fournisseur de base managée, un hébergeur applicatif |
| Exécution | **Une seule machine**, qui doit être allumée aux heures planifiées |
| Modèle local | Un modèle de 8 milliards de paramètres, tournant en local |

La dépendance à une machine unique est la plus concrète : une panne matérielle
interrompt la série, et une série interrompue ne se rattrape pas. Une archive
complète est répliquée localement chaque semaine, ce qui protège l'historique
**déjà acquis** mais pas la continuité de la collecte.
