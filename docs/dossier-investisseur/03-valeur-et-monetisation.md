# 03 — Valeur et monétisation

> Ce document distingue trois produits qu'on confond souvent sous le mot
> « data », et dit lequel est vendable. La distinction n'est pas un détail
> juridique : elle détermine ce qu'on peut mettre dans un contrat.

---

## L'avertissement qui doit venir en premier

**Les annonces brutes collectées ne sont pas revendables.** Il faut le dire avant
tout le reste, parce que c'est la première question que posera un acquéreur
sérieux ou son conseil.

Trois raisons cumulatives :

1. **Les conditions d'utilisation des sources** interdisent la réutilisation
   commerciale et la redistribution. Ce risque est assumé et documenté pour un
   usage personnel ; il change entièrement de nature dès qu'il y a revente.
2. **Un produit qui redistribue les annonces se substitue à la source.** C'est le
   cas de figure qui déclenche les contentieux, parce qu'il capte l'audience du
   site collecté.
3. **La posture du projet est écrite** dans sa documentation depuis le premier
   jour : usage non commercial, pas de redistribution, pas d'accès public. Un
   acquéreur qui découvre une contradiction entre le discours commercial et la
   documentation technique en tirera ses conclusions.

**Ce qui est vendable, en revanche, c'est ce qu'on en dérive** — à condition que
le produit soit *agrégé* et *non substituable*. Personne n'achète un indice de
rendement par quartier pour éviter d'aller sur un portail d'annonces : ce sont
deux usages différents. C'est cette non-substituabilité qui rend le produit
défendable, et elle doit être une contrainte de conception, pas un argument
rétrospectif.

---

## Trois produits distincts

### A. Les séries statistiques dérivées — le produit principal

Ce qui sort du système et qui ne ressemble à aucune annonce :

| Série | Granularité | Profondeur |
|---|---|---|
| Prix médian au m² | 40 quartiers × strate de chambres | 6 semaines |
| Loyer médian au m² | 28 quartiers × strate | 6 semaines |
| **Rendement brut apparié** | par immeuble, agrégé au quartier | 1 308 immeubles |
| Écoulement du stock | 9 385 cohortes | 80 126 observations |
| Mouvements de prix | 736 annonces, amplitude moyenne 8,9 % | datés |

**Pourquoi ça vaut quelque chose.** Le marché du condominium à Bangkok n'a pas
d'équivalent du registre de transactions qui existe en Europe. Les prix
d'affichage sont publics, les prix de transaction ne le sont pas, et les indices
officiels sont trimestriels et agrégés à la ville. Entre les deux, il n'existe
pratiquement rien à la maille **immeuble**.

C'est cet intervalle que le système occupe : plus fin que les publications
officielles, plus structuré que le scraping brut, et avec une méthode écrite.

### B. La méthode et l'outil — un produit à part entière

Le pipeline lui-même se licencie : quatre adaptateurs, un schéma normalisé, douze
agents orchestrés, une surveillance qui détecte une panne le jour même. Un acteur
qui voudrait la même chose sur Chiang Mai, Phuket ou Ho Chi Minh Ville achète du
temps de développement, pas de la donnée — et sur un périmètre où **il collecte
ses propres sources**, ce qui évacue entièrement la question précédente.

C'est, juridiquement, le produit le plus propre du dossier.

### C. Le service d'analyse — la marche la plus haute

Le système ne dit pas seulement combien coûte un m² : il repère les écarts
anormaux à périmètre comparable. C'est ce que consomme un acheteur — un family
office, un investisseur étranger — qui ne veut pas d'un tableur mais d'une
réponse : *ce bien est-il correctement prix ?*

C'est ce que fait déjà l'étude datée produite à chaque cycle. La différence avec
un rapport de conseil classique est que **le raisonnement est reproductible** :
paramètres gelés, versionnés, et un instantané conservé à chaque édition.

---

## Ce qui rend la position défendable dans le temps

**Le temps lui-même.** C'est le point le plus important, et il joue à double
tranchant.

Un concurrent qui démarre demain avec le même code obtient l'instantané du marché
demain. Il **n'obtient pas** l'historique : les annonces disparues ne sont plus
collectables, les prix d'hier ne sont plus affichés. Une série de prix ne se
rattrape pas rétroactivement.

Autrement dit : la valeur de l'actif est fonction de sa profondeur, et cette
profondeur ne s'achète pas. Elle s'accumule à raison d'un jour par jour.

**Le revers, qu'il faut énoncer** : la série n'a aujourd'hui que **six semaines**.
Ce n'est pas un actif de données, c'est le début d'un actif de données. À douze
mois, il devient possible de parler de saisonnalité et de tendance ; à
vingt-quatre, d'indice. Aujourd'hui, ce qui se vend honnêtement, c'est **l'outil
et la méthode** (produits B et C), et la série comme promesse documentée — pas
comme livrable.

**Ce qui est déjà rare, indépendamment de la profondeur** : la couverture
simultanée vente + location avec appariement dans le même bâtiment. Ce n'est pas
une question d'ancienneté mais de conception, et c'est disponible tout de suite.

---

## À qui ça s'adresse

| Acheteur | Ce qu'il cherche | Produit |
|---|---|---|
| Family office, investisseur étranger | Un prix défendable avant d'engager des fonds | C |
| Agence orientée expatriés | Un argumentaire chiffré face au client | A ou C |
| Promoteur en étude de faisabilité | Absorption réelle par typologie et micro-marché | A |
| Évaluateur, banque | Une comparable à la maille immeuble | A |
| Opérateur d'une autre ville | La chaîne complète pour son propre marché | B |

---

## Les conditions à remplir avant de commercialiser

Ce dossier serait malhonnête s'il présentait le système comme prêt à vendre.
Quatre conditions, par ordre de blocage :

1. **Trancher le périmètre juridique** avec un conseil thaï et un conseil du pays
   de l'acquéreur. Tant que ce n'est pas fait, seul le produit **B** est sûr.
2. **Atteindre une profondeur de série exploitable.** Six semaines ne suffisent à
   aucune affirmation de tendance.
3. **Combler les attributs manquants** — l'année de construction n'est renseignée
   nulle part, ce qui empêche toute comparaison à vétusté égale. Voir
   [04 — Limites connues](04-limites-connues.md).
4. **Documenter la provenance de bout en bout**, ce que le journal technique fait
   déjà : un acquéreur de données achète autant la traçabilité que les chiffres.

> **Ce qu'il ne faut pas dire à un investisseur** : que le système produit de la
> donnée « temps réel » (la cadence est de quatre jours, par choix), ou qu'il est
> « piloté par l'IA » (l'IA occupe un périmètre étroit et mesuré). Ces deux
> formulations sont vérifiables en dix minutes par quiconque regarde le dépôt, et
> les faire tomber détruirait la crédibilité du reste — qui, lui, tient.
