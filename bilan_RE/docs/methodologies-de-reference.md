# Méthodologies de référence — ce que publient les acteurs établis

> **Pourquoi ce fichier.** Décider quoi divulguer dans un bilan payant sans
> livrer la recette. La réponse n'est pas à inventer : indices, estimateurs
> automatisés et évaluateurs agréés ont tous tranché, et leur arbitrage est
> public. Ce fichier stocke **ce qu'ils publient, ce qu'ils retiennent, et la
> source**, pour que l'annexe client s'y adosse.
>
> Relevé le **2026-10-20**. Un document de méthodologie est vivant : vérifier la
> date de l'édition courante avant de citer un chiffre.
>
> Annexe qui en découle : [annexe-methodologie-client.md](annexe-methodologie-client.md).
> Points juridiques ouverts : [journal-juridique.md](journal-juridique.md).

---

## 0. La ligne de partage, en une phrase

**Tous publient les intrants, la couverture, la date et les limites. Aucun ne
publie les pondérations, les seuils, ni de quoi répliquer le résultat.**

Ce n'est pas une tolérance de fait : c'est une position prise explicitement par
le régulateur des indices financiers (§1), et la structure imposée aux
évaluateurs agréés (§2) en donne le plan type.

---

## 1. IOSCO — *Principles for Financial Benchmarks* (l'ancrage réglementaire)

Dix-neuf principes publiés le **17 juillet 2013** par l'Organisation
internationale des commissions de valeurs, applicables aux administrateurs
d'indices financiers. Trois domaines, dont l'un est **la qualité de la
méthodologie** : fixer l'information minimale qu'une méthodologie doit couvrir.

**Le point décisif.** La version soumise à consultation a été attaquée
précisément sur la divulgation d'information propriétaire. IOSCO a répondu en
clarifiant que **le niveau de transparence exigé n'équivaut pas à une
divulgation complète de la méthodologie ni des données historiques**. Les
principes 4, 5 et 12 ont été amendés dans ce sens. Un projet antérieur
contenait l'exigence de pouvoir **répliquer** le niveau publié d'un indice :
l'industrie s'y est opposée, et cette formulation a disparu.

**Ce qu'on en retient pour le bilan :**
- La transparence attendue porte sur **la nature des intrants, le périmètre, la
  date, les limites et le régime de changement de méthode** — pas sur les
  coefficients.
- Le critère de non-réplicabilité est **légitime et reconnu**, pas une astuce.
- Corollaire à ne pas perdre : ce qui est exigé en échange, c'est de **publier
  tout changement de méthode** et de dire à quoi on se conforme. L'opacité
  s'achète par de la discipline de version, pas par du silence.

> ⚠ Relevé par recherche secondaire (risk.net, déclarations de conformité
> d'administrateurs). Le texte primaire (rapport final 2013) n'a **pas** été lu :
> `iosco.org` renvoie **403** à une récupération automatique. La formulation
> exacte des principes 4, 5, 10 et 12 reste **non vérifiée à la source**.

Sources : [IOSCO — library (403 en fetch)](https://www.iosco.org/library/pubdocs/pdf/IOSCOPD429.pdf) ·
[Risk.net — Iosco softens index approach on final benchmark principles](https://www.risk.net/derivatives/structured-products/indexes/2284444/iosco-softens-index-approach-final-benchmark) ·
[CanDeal — IOSCO Principles Analysis and Assessment Report 2026](https://candeal.com/sites/default/files/2026-06/DNA%20IOSCO%20Principles%20Analysis%20and%20Assessment%20Report_Final_2026.pdf)

---

## 2. RICS — *Red Book Global Standards* (le plan type de l'annexe)

Édition courante en vigueur depuis le **31 janvier 2022** ; cadres de rapport
publiés en version **2025**. Ce sont les standards des évaluateurs agréés : le
bilan **n'est pas** une expertise et ne doit pas s'en réclamer (voir
[journal-juridique.md](journal-juridique.md), point 12 — jamais « valuation »
ni « appraisal »). Mais la **structure de divulgation** imposée est exactement
ce qu'il nous manque.

Ce que le standard rend obligatoire :

| Élément | Référence | Traduction pour le bilan |
|---|---|---|
| Objet et destinataire | VPS 1 | à qui sert le bilan, pour quelle décision |
| **Étendue de l'investigation** | VPS 1 / VPS 3 | **ce qui a été examiné et ce qui ne l'a pas été** |
| **Sources de l'information** | VPS 1 | nature et origine des données |
| Base de valeur | VPS 1 | ici : **positionnement relatif**, pas une valeur |
| Date | VPS 1 | date de fin de fenêtre, affichée |
| **Hypothèses** | VPS 4 | ce qu'on admet sans vérifier |
| Hypothèses **spéciales** | VPS 4 | à énoncer explicitement, jamais implicites |

Deux exigences à reprendre dans l'esprit :
1. L'évaluateur **prend la responsabilité d'énoncer clairement l'étendue et la
   profondeur des investigations, ce qui n'a pas été vérifié, et les hypothèses
   qui en découlent.**
2. Lorsqu'il s'appuie sur une information qu'il n'a pas pu vérifier, le rapport
   le dit et précise qu'elle a été **supposée exacte**.

Le cadre recommande aussi de **recopier les termes de la mission dans le
rapport**, pour qu'il n'y ait aucune contradiction entre les deux documents.

> ⚠ Texte intégral du Red Book **non lu**. Le détail VPS 1/3/4 ci-dessus vient
> des cadres de rapport RICS 2025 et de résumés secondaires, dont un blog de
> conseil pour la liste VPS 1. À confirmer sur le texte officiel avant d'écrire
> « conforme » où que ce soit — et on n'a aucune raison de l'écrire.

Sources : [RICS — Valuation Report Framework 2025](https://www.rics.org/content/dam/ricsglobal/documents/standards/Valuation-Report-Framework-2025_060726.pdf) ·
[RICS — Terms of Engagement Framework 2025](https://www.rics.org/content/dam/ricsglobal/documents/standards/Terms-Of-Engagement-Framework-2025_060726.pdf) ·
[SCSI — Guide to compliance, Red Book residential valuations](https://scsi.ie/wp-content/uploads/2022/10/SCSI-Guide-Compliance-Red-Book-Residential-Valuations.pdf)

---

## 3. Zillow — *Zestimate* (le précédent le plus proche de notre cas)

Un modèle automatisé, propriétaire, vendu au grand public, sur des données de
marché. Le cas d'école de ce qu'on fait et ne fait pas.

**Ce que Zillow publie :**
- Un **taux d'erreur médian national**, séparément pour les biens **en vente**
  (~**1,83 %**) et **hors marché** (~**7,01 %**). L'écart d'un facteur ~4 entre
  les deux est lui-même publié — c'est l'aveu que le modèle est bien meilleur
  quand il connaît déjà un prix affiché.
- Des **tableaux par aire métropolitaine** : erreur médiane, et **part des
  estimations à moins de 5 %, 10 % et 20 %** du prix de vente.
- Le facteur limitant, nommé : **la précision dépend de la quantité de données
  disponibles dans la zone** du bien.

**Ce que Zillow ne publie pas :** le modèle, ses variables, leurs poids.

**La critique à connaître, parce qu'elle visera notre bilan aussi.** Une médiane
décrit le cas typique, pas la dispersion : par définition la moitié des biens
tombe au-delà, et Zillow ne détaille pas l'ampleur de ces écarts. Un chiffre
d'erreur publié sans sa queue de distribution est un argument commercial, pas
une mesure.

**Ce qu'on en retient :** publier un indicateur de qualité chiffré **par maille**
est le niveau de transparence attendu d'un modèle propriétaire grand public. On
ne l'a pas (validation prédictive impossible avant ~3 mois d'historique propre,
[methodes-calculs.md](../../docs/methodes-calculs.md) §12) — donc l'annexe doit
**dire que la précision n'est pas encore mesurée**, et non rester muette.

> ⚠ Chiffres **relevés par recherche**, page source **non lue**
> (`zillow.com/zestimate` renvoie 403 en fetch). Des sources secondaires citent
> encore 2,4 % / 7,49 % ou 1,9 % / 7,9 % : ces valeurs changent dans le temps. À
> revérifier sur la page avant toute citation dans un document client.

Sources : [Zillow — Zestimate (403 en fetch)](https://www.zillow.com/zestimate) ·
[Sacramento Appraisal Blog — two things to understand about Zillow's accuracy rate](https://sacramentoappraisalblog.com/2019/05/01/two-things-to-understand-about-zillows-accuracy-rate/) ·
[Legally Sociable — it might not matter how wrong Zillow's price estimates are](https://legallysociable.com/2024/12/20/it-might-not-matter-how-wrong-zillows-price-estimates-are/)

---

## 4. S&P CoreLogic Case-Shiller (le traitement du biais de composition)

Indice de prix immobiliers résidentiels américains, méthodologie publiée en PDF
par S&P Dow Jones Indices.

**Ce qui est public :** l'approche entière en **ventes répétées** — on suit le
même bien d'une transaction à l'autre au lieu de moyenner les ventes d'une
période ; chaque paire est **pondérée par la valeur de sa première
transaction** ; le périmètre est énoncé (transactions **de gré à gré** sur
maisons individuelles, **saisies et ventes entre parties liées exclues**) ;
l'agrégation nationale part de neuf divisions du recensement, pondérées par
l'estimation du parc.

**Les limites, publiées par l'administrateur lui-même :**
- **La révision est une propriété inhérente** aux méthodes de ventes répétées —
  l'indice d'hier change quand les données d'aujourd'hui arrivent.
- Entre deux ventes, **un bien a pu être amélioré ou se dégrader** : le modèle
  ne le sait pas.

**Ce qu'on en retient :** l'intérêt du dispositif n'est pas sa formule, c'est
qu'il **neutralise le biais de composition** — comparer le même objet à
lui-même plutôt que des paniers différents. C'est exactement la fonction de nos
cohortes `unit_key` et de la double médiane par condo. Et c'est le modèle à
suivre sur un autre point : **publier la règle de révision**. Un bilan dont les
chiffres bougent d'un mois à l'autre sans que la révision soit annoncée perd sa
crédibilité d'un coup.

> ⚠ Le PDF primaire de S&P DJI n'a **pas été ouvert** (lien connu seulement via
> un README tiers). Points ci-dessus issus de sources secondaires
> convergentes — à confirmer sur `spglobal.com` avant citation.

Sources : [Wikipedia — Case-Shiller index](https://en.wikipedia.org/wiki/Case-Shiller_index) ·
[Inman — Case-Shiller is a go-to source for prices, but know these blind spots](https://inman.com/2024/03/11/case-shiller-is-a-go-to-source-for-prices-but-know-these-blind-spots) ·
[St. Louis Fed — The differences between house price indexes](https://www.stlouisfed.org/on-the-economy/2015/january/the-differences-between-house-price-indexes)

---

## 5. MSCI — indices immobiliers privés (la discipline de version)

MSCI publie ses méthodologies d'indices immobiliers sur un **portail dédié** :
le document de méthodologie des indices de biens (édition **avril 2024** dans
les relevés), les *Global Methodology Standards for Real Estate Investment*
(**décembre 2024**), les *Index Policies*, et — ce qui compte ici — la **liste
des annonces de changement** et les **versions historiques**.

Le document de méthodologie couvre les **intrants**, la **composition** et les
mesures principales et secondaires. Les *Index Policies* traitent les
changements de composition, les **corrections**, les **changements de
méthodologie**, la consultation et la cessation, et posent que **la discrétion
est limitée** : l'indice est déterminé par la méthodologie publiée, pas par un
arbitrage de production, sauf cas extrêmes relevant d'un comité.

**Ce qu'on en retient — le plus actionnable de tout ce fichier :** la crédibilité
ne vient pas du détail livré, elle vient de **la traçabilité des versions**. Un
`config_version` figé, daté, avec un historique des changements publiés, vaut
plus qu'une formule divulguée. `bilan_RE/tension/config.json` porte déjà
`config_version` : c'est l'actif à exploiter.

Sources : [MSCI — Real Estate Methodology Documents](https://www.msci.com/indexes/private-asset-indexes/real-estate-methodology-documents) ·
[MSCI — Global Methodology Standards for Real Estate Investment](https://www.msci.com/documents/1296102/1311232/MSCI+Global+Methodology+Standards+for+Real+Estate+Investment.pdf) ·
[MSCI — Real Estate Index Policies](https://www.msci.com/documents/1296102/1311232/MSCI+Real+Estate+-+Index+Policies.pdf)

---

## 6. Synthèse — la grille appliquée au bilan

| | Divulgué par les acteurs | Retenu par les acteurs |
|---|---|---|
| **Données** | nature, origine, périmètre, exclusions | — |
| **Date** | date de référence, fréquence, règle de révision | — |
| **Méthode** | approche et **raison** du choix, familles de signaux | poids, seuils, bornes, ordre exact |
| **Qualité** | indicateur d'erreur chiffré, par maille | — |
| **Limites** | nommées une par une, par l'administrateur | — |
| **Version** | identifiant, historique des changements | — |
| **Réplicabilité** | — | explicitement **non exigée** (IOSCO) |

**Les trois obligations qu'on hérite en choisissant l'opacité de méthode :**
1. **Dire la date**, toujours, et la règle de révision.
2. **Dire ce qui n'est pas mesuré** — y compris que la précision du score n'est
   pas encore établie.
3. **Versionner et publier les changements de méthode.**

Manquer l'une des trois transforme un secret légitime en boîte noire.
