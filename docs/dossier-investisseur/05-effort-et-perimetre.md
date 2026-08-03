# 05 — Ce que ça représente comme travail

> Ce document répond à une question de due diligence : **qu'est-ce qui a été
> construit, et que coûterait-il à reconstruire ?**
>
> Il sépare strictement ce qui est **mesuré** de ce qui est **estimé**. Les
> volumes viennent du dépôt et sont reproductibles ; l'effort équivalent est une
> estimation, personne n'a tenu de feuille d'heures.

---

## 1. Ce qui est mesuré

Relevé au 2026-08-02, hors fichiers de données (GeoJSON, JSON de configuration,
images, verrous de dépendances) :

| | lignes | part |
|---|---:|---:|
| Code | 11 246 | 55 % |
| Commentaires dans le code | 3 199 | 16 % |
| Lignes vides | 1 808 | 9 % |
| Documentation (`.md`) | 4 309 | 21 % |
| **Total écrit à la main** | **20 562** | |

**Un cinquième du code est du commentaire, et c'est délibéré.** Les commentaires
n'y décrivent pas ce que fait la ligne — ils consignent *pourquoi* elle est
écrite ainsi, et quel défaut mesuré l'a imposée. Exemple réel :

> « L'arrondi bancaire de Python divergeait de l'arrondi SQL : une surface de
> 42,5 m² recevait la tranche 40 si l'`unit_key` venait du scrape, 45 s'il venait
> du backfill. 263 annonces pile sur une frontière, dont 124 réellement
> divergentes. On adopte la convention SQL. »

Cette densité a un coût d'écriture et une valeur de reprise : un tiers qui
récupère la base n'a pas à redécouvrir les pièges par l'échec.

### Répartition par domaine

| Domaine | lignes | fichiers |
|---|---:|---:|
| Scraping — 4 adaptateurs + pipeline | 3 804 | 30 |
| Système d'agents — 12 bots, client IA durci, tests | 3 214 | 35 |
| Interface carte et tableaux | 3 685 | 35 |
| Statistiques et méthode | 2 957 | 19 |
| Exploitation — tableau de bord, superviseur, planification | 2 199 | 16 |
| Schéma et migrations | 751 | 9 |
| Documentation technique et dossier | 4 167 | 18 |

### Calendrier

**Du 21 juin au 2 août 2026 — six semaines.** 68 commits répartis sur 15 jours
distincts, plus le travail non encore commité de la dernière semaine
(agents, exploitation, dossier : 5 985 lignes).

---

## 2. Effort équivalent — estimation

**Méthode.** Décomposition par composant, chacun estimé en jours-homme pour un
développeur expérimenté **déjà familier de la pile** (TypeScript/Next.js,
Python, Postgres), en incluant conception, mise au point et vérification — pas
la seule frappe.

| Composant | j-h |
|---|---:|
| Pipeline de scraping et 4 adaptateurs | 12–15 |
| Application carte et tableaux | 10–12 |
| Statistiques et méthode | 8–10 |
| Système d'agents et client IA durci | 8–10 |
| Exploitation et résilience | 5–6 |
| Deux stores maintenus en parallèle + migrations | 3–4 |
| Documentation | 4–5 |
| Campagnes de mesure *(voir §3)* | 6–8 |
| **Total** | **56–70 j** |

Soit, à temps plein pour une personne, **onze à quatorze semaines**.

**Le calendrier réel est de six semaines.** L'écart tient à l'assistance IA sur
la production de code et de documentation. Il ne dit rien de la qualité : ce qui
a pris du temps, ce sont les mesures et les corrections, pas la frappe.

### Ce qui rend certains composants coûteux

Les lignes ne disent pas la difficulté. Trois exemples où le volume est faible et
l'effort élevé :

- **Le contournement Cloudflare de DDproperty.** Les pages de détail sont
  derrière un challenge. La solution — une session `requests` *réchauffée* en
  parcourant la liste d'abord pour obtenir le cookie `__cf_bm`, en-têtes de
  navigateur, et **sans brotli** parce que `requests` ne le décode pas — tient en
  quelques dizaines de lignes et représente une journée d'essais. Elle évite
  d'embarquer un navigateur headless.
- **Les couleurs officielles du métro.** Elles viennent des relations d'itinéraire
  OpenStreetMap, qui ne sont **pas** incluses par `out tags geom` — il faut
  `out body geom`. Un détail d'API qui coûte une demi-journée à trouver.
- **La double médiane par immeuble.** Trois lignes de SQL de plus qu'une moyenne,
  mais c'est le parti méthodologique qui distingue ces chiffres de ceux d'un
  agrégateur (cf. [02](02-methode-et-differenciation.md)).

### Ce que l'estimation ne couvre pas

- **La connaissance métier**, qui n'est pas du temps de développement : que la
  location courte durée est interdite en copropriété thaïlandaise (ce qui valide
  la durée de bail à 12 mois), qu'un propriétaire thaï peut détenir plus de cent
  lots (ce qui invalide un raisonnement sur les doublons), quels corridors de
  transport sont actés. Elle vient du porteur du projet.
- **Un développeur découvrant la pile** ou les portails thaïlandais mettrait
  sensiblement plus longtemps. L'estimation suppose la familiarité.
- **L'exploitation courante** : les scraps, la surveillance, les études
  récurrentes. C'est du fonctionnement, pas de la construction.

---

## 3. La part invisible : ce qui a été mesuré, pas écrit

Une fraction notable de l'effort ne produit **aucune ligne de code**. C'est
pourtant elle qui rend les chiffres opposables.

| | volume |
|---|---|
| Appels au modèle local, sur données réelles du dépôt | **650+** |
| Éléments étiquetés **à la main** pour servir de référence | **220** (120 paires de doublons + 100 descriptifs) |
| Descriptifs analysés pour concevoir les champs de détail | **500** |
| Descriptifs traités par l'extraction déterministe | **14 204** |

Ce travail a produit des résultats qui ont **contredit l'architecture prévue**, et
qui ont été retenus quand même :

- Le modèle local **n'apporte rien** à l'extraction depuis les descriptifs. Là où
  la règle déterministe parle, elle a raison 100 % du temps ; là où elle se tait,
  le modèle invente dans 76 à 94 % des cas. Mesuré deux fois, sur deux jeux
  indépendants.
- Le **mode extraction** (le modèle constate, le code décide) fait passer
  l'abstention de 0 % à 77 % sur les doublons, à justesse égale. C'est
  l'architecture qui a été retenue.
- Un **raisonnement verbeux dégrade** : règles brèves 92 %, procédure numérotée
  69 %. Vingt-trois points perdus en ajoutant des consignes.

Une revue de code menée le 28 juillet a trouvé **sept écarts** entre ce que la
documentation décrivait et ce que le code faisait — dont une vue qui plaçait en
tête des locations mal classées en vente, affichées à −100 % de décote. Trois
tâches Windows planifiées le 11 juillet **n'avaient jamais tourné** : des
guillemets échappés littéraux dans le XML enregistré. Personne ne l'avait vu
pendant dix-sept jours, parce que rien ne surveillait les surveillants.

**C'est le journal technique qui rend cet historique vérifiable** : registre en
ajout seul, jamais réécrit. Une décision qui s'est révélée fausse y reste,
suivie de l'entrée qui la corrige — y compris quand l'erreur venait de la mesure
et non du système mesuré, ce qui s'est produit quatre fois.

---

## 4. Ce que ça vaut, et ce que ça ne vaut pas

**Reconstruire l'outil** — le scraping, la carte, les tableaux, les statistiques —
coûterait l'ordre de grandeur indiqué ci-dessus.

**Reconstruire la connaissance** coûterait davantage, et surtout ne se
parallélise pas : les pièges de chaque source, les bornes de plausibilité, les
divergences entre les deux stores, le comportement réel du modèle local. Chacun
a été découvert par une mesure qui a échoué avant d'aboutir.

**Ce qui ne se reconstruit pas du tout, c'est l'historique.** Les séries par
cohorte, l'observation des délistages, l'évolution des prix : elles ne
s'achètent pas et ne se rattrapent pas — elles s'accumulent. Un concurrent qui
démarre aujourd'hui a l'outil dans deux mois et la profondeur d'historique
jamais.

Les limites de tout ceci sont dans un document dédié :
[04 — Limites connues](04-limites-connues.md). Elles ne sont pas en note de bas
de page, parce qu'elles comptent autant que le reste.
