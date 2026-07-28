# Journal technique — Lowi BKK

> **Registre append-only des décisions techniques, des méthodes retenues et des
> défauts découverts.** On n'y réécrit jamais le passé : une décision qui s'avère
> fausse reste consignée, avec l'entrée ultérieure qui la corrige. Le fichier
> complète l'historique git (qui porte le *quoi*) en portant le *pourquoi*, ce
> qui a été mesuré, et ce qui restait faux au moment de la décision.
>
> **Objet secondaire : traçabilité de propriété.** Le projet peut être présenté à
> des tiers (agences, chasseurs de biens). Ce journal documente qui a conçu quoi,
> avec quels outils, à partir de quelles sources — de quoi établir l'antériorité
> et l'origine des méthodes si la question se pose.
>
> Format d'une entrée : date · sujet · contexte · décision · mesure · limite connue.

---

## Provenance et outils

| Élément | Détail |
|---|---|
| Conception et arbitrages | Anthony Schoenauer |
| Assistance à l'implémentation | Claude (Anthropic), en pair-programming ; le code est revu et exécuté sur la machine d'Anthony |
| Modèle d'extraction (annonces réseaux sociaux) | qwen3:8b via Ollama, **exécution 100 % locale** — aucune donnée d'annonce n'est envoyée à un service tiers |
| Sources de données | Portails publics (FazWaz, DDproperty, PropertyScout, Nestopa) scrapés à usage personnel non commercial ; groupes Facebook publics ; OSM/Overpass pour la géographie ; REIC/BOT pour le contexte macro |
| Base de données | Supabase (Postgres) + réplique locale SQLite |

Les méthodes statistiques décrites ci-dessous (double médiane par condo, strates
de taille, rendement within-condo, délai de grâce au délistage) ont été conçues
pour ce projet et sont documentées ici à leur date d'adoption.

---

## 2026-06 → 2026-07-09 · Construction initiale

Reconstitué depuis `CLAUDE.md` et l'historique git ; voir ces sources pour le détail.

- **Choix d'architecture verrouillés** : MapLibre (carte vectorielle), Next.js,
  Supabase, scraping Python par adaptateurs. Principe directeur : tout est
  config-driven, un site = un adaptateur + un fichier de config.
- **Schéma normalisé unique** (`lib/types.ts` ↔ `supabase/schema.sql`) comme
  source de vérité, pour que l'ajout d'une source ne propage pas ses conventions.
- **Freehold uniquement, leasehold écarté à la source** ; `quota`
  (foreigner/thai) extrait quand le site l'expose.
- **Double médiane par condo (2026-07-04)** : prix/m² = médiane des annonces par
  condo, puis médiane des condos — un immeuble compte pour une voix. Neutralise
  la surreprésentation des grosses copropriétés sans disposer de l'année de
  construction. Rendement = médiane des rendements *within-condo* (loyer et prix
  du même immeuble), ≥5 condos appariés sinon repli marqué †.
  **Strate 0-1BR par défaut** pour garantir un panier constant.
- **Framework d'étude récurrente (2026-07-06)** : paramètres figés et versionnés
  dans `study/config.json` ; changer un paramètre impose d'incrémenter
  `config_version`, ce qui trace les ruptures de série.

---

## 2026-07-25 · Nouvelle source : annonces des groupes Facebook Bangkok

**Contexte.** Les portails ne publient presque jamais de vente en direct
propriétaire ni de loyer réel adossé à un prix de vente. Les groupes Facebook,
si — mais en texte libre, bilingue thaï/anglais, tronqué et redondant.

**Décisions.**

1. **Collecte réutilisant l'agent de veille prospection** (`agent2_scraper`)
   plutôt qu'un second scraper : Facebook change son DOM souvent, on ne veut
   qu'un seul endroit à réparer. Bascule par variables d'environnement
   (`FB_GROUPS_FILE`, `FB_SOURCE`, `FB_SKIP_ANALYSIS`, `FB_RICH_CONTENT`).

2. **Contournement du brouillage anti-scraping.** Facebook mélange les
   caractères dans le DOM et les remet en ordre par CSS. Le timestamp était
   illisible → aucune date → tous les posts rejetés (1 seul collecté sur
   5 groupes). *Méthode retenue :* relire le texte dans l'**ordre visuel**
   (tri des nœuds texte par position à l'écran), ce qui fait réapparaître la
   date en tête de chaîne. Résultat : 209 annonces.

3. **Extraction par modèle local sous schéma imposé**, une annonce par appel.
   *Types simples obligatoires* : les unions `["integer","null"]` produisent une
   grammaire de contrainte défaillante côté llama.cpp et la génération part en
   boucle infinie (constaté : processus `llama-server` orphelin). Convention
   `0` / `""` pour l'absence. Mode réflexion désactivé — l'extraction est de la
   transcription, pas du jugement.

4. **Le modèle extrait les faits, le code tranche les catégories.** Sans
   marqueur explicite, un 8B remplit une case obligatoire au hasard : il classait
   108 annonces sur 209 en « recherche » alors que ce sont des offres, et
   125 vendeurs en « propriétaire » alors qu'il s'agit d'agences. `seller_type`
   et `quota` sont donc décidés par règles déterministes (nom de l'auteur,
   marqueurs `เจ้าของ` / `no agent` / `โควตาต่างชาติ`).

5. **Table `social_leads` séparée de `listings`.** Ces données sont déclaratives
   et non vérifiées ; les injecter dans `listings` contaminerait `khet_stats`,
   les médianes par condo et les rendements — c'est-à-dire la valeur du projet.
   Promotion manuelle via `status` (new/reviewed/promoted/rejected/duplicate).

**Mesuré.** 209 annonces → 179 pistes uniques. 167 avec nom d'immeuble, 84
rapprochées du référentiel (50 %). 13 propriétaires directs, 69 agences.
**Quota étranger explicite : 1 annonce sur 209.**

**Limites connues.** « Voir plus » non déplié (annonces longues tronquées) ;
2 groupes à URL nommée ne rendent rien ; l'écart au marché n'est pas encore
calculé par strate de taille.

---

## 2026-07-25 · Le quota étranger est une question, pas une donnée

**Constat.** Sur l'ensemble du référentiel : 114 `foreigner` et 127 `thai` pour
24 549 non renseignés (1 %). Sur Facebook : 1 sur 209.

**Décision.** Le champ vaut `unknown` par défaut et **ne se déduit jamais d'une
absence**. C'est un champ à remplir manuellement après contact vendeur, pas une
donnée à collecter. Traité comme tel dans `social_leads` et dans la vue
`social_leads_opportunites`, qui priorise les rares annonces où il est explicite.

**Pourquoi ça compte.** Un étranger ne peut détenir en pleine propriété que dans
la limite de 49 % de la surface d'un immeuble. Sans quota étranger disponible, le
bien n'est pas achetable en direct — et il ne sera pas revendable à un étranger.

---

## 2026-07-28 · Le « -50 % » était un artefact de taille

**Contexte.** Le résolveur signalait une annonce Supalai Icon Sathorn à -57 % du
marché de son propre immeuble.

**Vérification.** La médiane d'un immeuble mélange les tailles. Comparé au bon
lot (44 m² à 238 900 ฿/m² dans le même immeuble), l'écart réel d'un 42 m² à
9 M฿ (214 300 ฿/m²) est de **-10 %**, pas -50 %. Deux annonces du même agent, même
immeuble, même jour, affichaient -57 % et -13 % : l'écart entre elles ne
reflétait que la surface.

**Décision.** Aucun écart n'est présenté comme une opportunité tant qu'il n'est
pas calculé **à strate de taille comparable**. La vue `social_leads_opportunites`
exige `area_sqm > 0` et porte l'avertissement en commentaire ; le calcul par
strate reste à brancher sur `lib/yields.ts`.

---

## 2026-07-28 · Défaut majeur : le délistage rendait la liquidité non mesurable

**Symptôme.** Durée de vie des annonces de vente : médiane **4,7 jours pour
toutes les strates** (studio comme 3BR+), p25 4,2 / p75 4,8. C'est la cadence de
scan, pas un signal de marché.

**Cause.** `mark_missing_inactive()` délistait dès la **première** absence. Or un
scan `--full` s'arrête à `max_pages` (150) : toute la queue de liste était
marquée disparue à tort, puis réactivée par la passe ciblée suivante. Le
garde-fou existant (annuler si le scan voit moins de 50 % des actives) ne
protégeait que de l'effondrement total, pas de la troncature.

**Conséquence.** Tension locative et liquidité de revente — deux des trois
leviers de la stratégie d'investissement — étaient **non mesurables**, et le
temps n'y aurait rien changé : une donnée biaisée s'accumule, elle ne se corrige
pas.

**Correctif (`supabase/migrations/delisting_grace.sql`).** Délai de grâce : une
annonce doit manquer à **2 scans consécutifs** avant délistage. Colonnes
`missed_count` et `first_missed_at` ; le délistage est daté de la *première*
absence, sinon la durée de vie serait surestimée d'un cycle complet. Compteur
remis à zéro dès réapparition. Appliqué aux deux stores (Supabase et SQLite).

**Portée.** Le correctif ne répare pas l'historique : les `delisted_at`
antérieurs restent contaminés. **La mesure fiable de la liquidité commence à
cette date.**

---

## 2026-07-28 · La réplication d'archive était en panne depuis 22 jours

**Symptôme.** L'archive locale s'arrêtait au 2026-07-06 (annonces, snapshots,
`scan_runs`), alors que le serveur contenait des données jusqu'au 24/07.

**Cause.** La tâche `LowiBKK-ArchiveSync` échouait avec le code `-196608` sans
produire de log — le dossier `ops/logs/` n'avait même pas été créé, donc le
script n'a jamais démarré. Cause exacte du non-démarrage non identifiée à ce
jour (piste : politique d'exécution PowerShell ou contexte de la tâche).

**Correctif immédiat.** Synchronisation relancée à la main, sans `--prune` par
prudence : 24 790 → **34 275 annonces**, snapshots 2 434 → 5 223.

**Enseignement.** Un échec silencieux d'une tâche planifiée est plus dangereux
qu'une erreur bruyante : pendant 22 jours, toutes les analyses locales portaient
sur des données périmées sans que rien ne l'indique. **À faire : rendre l'échec
visible** (le journal de tâche doit être écrit même quand le script ne démarre
pas, et une alerte doit se déclencher si l'archive a plus de 10 jours de retard).

**Ce que les données fraîches changent.** `price_history` contient enfin
602 annonces avec plusieurs observations de prix — un premier signal de
révision de prix, exploitable. Les snapshots passent à 15 journées distinctes.
La durée de vie se différencie enfin entre strates (9,3 j en studio-1BR contre
6,9 j en 2BR et 3BR+), mais **ces chiffres restent tirés du délistage
contaminé** : à ne pas interpréter avant d'avoir accumulé des données post-correctif.

---

## 2026-07-28 · Ce que les données disent de la stratégie d'investissement

Hypothèse de départ (Anthony) : *le premium 2BR+ se valorise plus vite ou plus
régulièrement*.

**Ce que mesure le référentiel :**

| Strate | Dispersion prix/m² (p25-p75 / médiane) | Rendement brut médian (within-condo) |
|---|---|---|
| Studio–1BR | 75,7 % | 4,89 % |
| 2BR | 82,8 % | 4,70 % |
| 3BR+ | 103,1 % | 4,36 % |

Sur les deux dimensions mesurables aujourd'hui, l'hypothèse **n'est pas
confirmée** : la dispersion des prix croît avec la taille (prix de revente plus
incertain) et le rendement décroît. Explication plausible, à confirmer : la
demande locative expatriée est dominée par les 1BR, et le bassin d'acheteurs à la
revente se rétrécit quand le ticket monte.

**Réserve.** La dispersion mesurée mélange les immeubles, donc une part reflète
la géographie ; le rendement, lui, est apparié au même immeuble et même nombre de
chambres, ce résultat est plus robuste. L'hypothèse ne pourra être tranchée
qu'avec l'âge du bâtiment et une série temporelle post-correctif.

**Angle mort assumé.** L'âge du bâtiment est absent du schéma. Pour une stratégie
d'achat-revente à 5-10 ans, la courbe de dépréciation est probablement le facteur
dominant. **Prochaine priorité.**

**Biais documenté.** Tous les rendements sont calculés sur des prix *affichés*,
pas transactés. Les prix de vente se négocient davantage que les loyers : le
rendement réel est vraisemblablement supérieur à celui affiché.

---

## 2026-07-28 · L'indice de tension mesurait la petitesse du marché

**Symptôme signalé par Anthony.** La périphérie ressortait plus tendue que le
centre, alors qu'elle compte très peu d'annonces.

**Cause.** La composante « rareté » de `lib/tension.ts` valait littéralement
`100 − rang(nombre d'annonces actives)` : **peu d'annonces = tendu, par
construction**. Or 25 des 55 quartiers ont moins de 20 annonces actives et
obtenaient donc mécaniquement le score maximal. Taling Chan affiche 2 annonces
sur 6 immeubles : ce n'est pas de la tension, c'est l'absence de marché. Le
compte brut confondait **taille** du marché et **tension**.

**Aggravant.** L'absorption — 40 % du poids — repose sur le time-on-market,
contaminé par le bug de délistage : 6,9 jours médians identiques à Vadhana,
Khlong Toei et Sathon, soit la cadence de scan, pas le marché. Et Pathum Wan
comptait 521 délistages pour 413 actives, signature des reposts. Autrement dit
40 % de l'indice reposait sur une donnée fausse et 15 % sur une définition
erronée.

**Corrections.**
1. « Rareté » remplacée par la **pression vendeuse** = actives / nombre
   d'immeubles du quartier (dénominateur issu du référentiel `condos`).
   Insensible à la taille du marché et interprétable : 9,6 annonces par immeuble
   à Bangkok Yai, ce sont des vendeurs en concurrence, donc un marché mou.
   Poids porté de 15 à 25.
2. **Rétrécissement** des petits échantillons vers la médiane du marché, poids
   `n/(n+20)` : à 5 annonces un quartier compte pour 20 % de son propre score.
3. **Seuil de publication** à 10 annonces actives : en dessous, `tensionScore`
   vaut `null`. Vingt-cinq quartiers passent en « données insuffisantes » — c'est
   simplement honnête.
4. Option `reliableDelistingSince` : ignore les disparitions antérieures au
   correctif du délistage pour le calcul du time-on-market. À régler sur
   `2026-07-28` une fois assez de données post-correctif accumulées.

**Vérifié** (`lib/tension.test.mjs`) : un quartier à 3 annonces n'est plus publié ;
un marché à 10 annonces par immeuble score plus bas qu'un marché à 3 ; la
pression vendeuse est correctement calculée.

**Limite assumée.** L'absorption reste dans l'indice avec 35 % du poids alors que
son historique est contaminé. Elle se nettoiera d'elle-même à mesure que les
délistages post-correctif s'accumulent ; d'ici là, le mécanisme de dégradation
gracieuse redistribue son poids quand elle est indisponible. À terme, la série
`cohort_snapshots` est le bon substitut : elle mesure l'écoulement du stock sans
être trompée par les republications.

---

## Doctrine de présentation (adoptée le 2026-07-28)

Le produit sert deux usages aux exigences opposées : un outil de décision
personnel (assumé, orienté) et une veille potentiellement vendable à des tiers
(qui doit être neutre et auditable). **Règle : séparer la couche de mesure de la
couche de jugement.**

- **Couche de mesure** — factuelle, auditable, c'est elle qui est vendable :
  prix/m² par strate, rendement apparié, taille d'échantillon, dispersion,
  distance au transport, fraîcheur de la donnée.
- **Couche de jugement** — la pondération de ces mesures pour produire un
  classement. Elle encode une stratégie et reste personnelle et paramétrable.

Règles de présentation qui en découlent :

1. Jamais une médiane sans son `n` ni sa dispersion (p25-p75).
2. Toute comparaison est explicitement *à périmètre comparable* (même strate,
   même quartier) et le périmètre est affiché.
3. Distinguer visuellement **mesuré** de **estimé** (le repli † existant).
4. Aucun classement sans exposer les poids qui le produisent.
5. Une anomalie s'annonce « à vérifier », jamais « opportunité » — cf. l'entrée
   du 2026-07-28 sur le -50 % qui n'était qu'un artefact de taille.
6. Afficher la date de dernière mise à jour des données sur chaque vue — le
   silence de 22 jours de juillet 2026 ne doit pas pouvoir se reproduire sans
   être visible.

---

## 2026-07-28 (soir) · Revue de code : ce que les descriptifs promettaient et ce que le code faisait

Revue de l'ensemble des révisions récentes, avec vérification systématique des
affirmations contre la base réelle plutôt que contre les commentaires. Sept
écarts trouvés, tous corrigés le jour même. Le fil commun : **plusieurs
descriptifs décrivaient l'intention, pas le code**, et une intention consignée
dans un commentaire finit par être lue comme un fait.

### 1. Le dénominateur de la pression vendeuse mélangeait deux périmètres

L'entrée de cet après-midi annonce un dénominateur « issu du référentiel
`condos` ». Vérification faite, c'était faux à deux titres, et le second
invalidait la mesure :

- le code comptait les `condo_name` distincts des **annonces**, pas la table ;
- il les comptait sur **toutes** les annonces du quartier, délistées comprises,
  alors que le numérateur ne compte que les actives.

Périmètres mélangés : un quartier à fort churn accumule des noms d'immeubles au
dénominateur, sa pression s'effondre, sa tension grimpe. C'est exactement Pathum
Wan et ses 521 délistages — le cas que la révision voulait corriger.

| Quartier | Pression, périmètre actif | Périmètre historique | Écart |
|---|---|---|---|
| Vadhana | 6,92 | 4,61 | −33 % |
| Khlong Toei | 5,52 | 3,32 | −40 % |
| Ratchathewi | 8,87 | 6,72 | −24 % |

Le biais n'est pas uniforme : il déforme le **classement**, pas seulement
l'échelle. Et la table `condos` n'aurait rien réglé — elle est peuplée depuis
toutes les annonces sans filtre de statut (754 immeubles à Vadhana contre 766 vus
dans l'historique des annonces), elle porte donc le même biais.

**Retenu :** immeubles distincts parmi les annonces **actives**, nom normalisé.
Se lit « parmi les immeubles où quelqu'un vend, combien de vendeurs
simultanés ? ». Même périmètre en haut et en bas de la fraction.

Corollaire : la normalisation du nom d'immeuble existait en double à l'identique
(`yields.ts`, `cross-match.ts`) et pas du tout dans `tension.ts`, qui comparait
donc des noms bruts et comptait deux immeubles pour « X » et « X, Bangkok ». Un
seul exemplaire désormais : `lib/condo-name.ts`. **Divergence connue et assumée**
avec `_norm_condo` de `normalize.py`, qui retire en plus les mots vides : les
aligner déplacerait toutes les médianes déjà publiées et mérite sa propre
décision datée.

### 2. `reliableDelistingSince` n'était branché nulle part

L'option avait été ajoutée et documentée, mais aucun appelant ne la passait :
l'absorption — 35 % du poids — tournait toujours sur l'historique contaminé que
l'entrée de l'après-midi décrit. Elle vaut désormais `DELISTING_FIX_DATE` **par
défaut**, l'appelant devant passer `null` pour réintégrer explicitement
l'historique douteux.

Effet immédiat, assumé : zéro disparition postérieure au correctif (le dernier
scan date du 24/07), donc le time-on-market est nul partout et l'absorption se
replie sur l'âge des annonces actives. C'est moins riche, mais ce n'est pas faux
— alors qu'un TOM de 6,9 jours identique à Vadhana, Khlong Toei et Sathon était,
lui, purement et simplement la cadence de scan. Le TOM revient tout seul dès que
les scraps post-correctif s'accumulent.

### 3. Le momentum prix suivait la moyenne alors que la médiane était à côté

`khet_snapshots` porte `avg_price_per_sqm` **et** `median_price_per_sqm`. Le
momentum régressait sur la moyenne. Mesuré sur 2 121 instantanés de vente : la
moyenne court **16 % au-dessus** de la médiane (137 750 contre 118 826 THB/m²),
tirée par les penthouses. Sa pente suit donc les entrées et sorties de biens
d'exception, pas le marché. Bascule sur la médiane, repli sur la moyenne quand
elle manque.

### 4. `median_price` contenait une moyenne en local, une médiane en ligne

SQLite n'a pas d'agrégat de médiane : `record_cohort_snapshots` y écrivait
`avg(price)` dans une colonne nommée `median_price`, quand Supabase y écrit
`percentile_cont(0.5)`. **Même colonne, deux définitions selon le backend** — le
genre d'écart qui fait douter d'une série temporelle un an plus tard sans qu'on
sache pourquoi. Médiane calculée en Python désormais (demi-somme des deux valeurs
centrales pour un effectif pair, exactement `percentile_cont`), vérifiée
identique des deux côtés.

Au passage : `median_price_per_sqm` était laissé à `NULL` dans les instantanés
locaux, alors que c'est précisément la colonne que le momentum consomme. La série
locale était muette sur sa composante la plus utile.

### 5. L'arrondi de la tranche de surface divergeait entre Python et SQL

`round()` de Python applique l'arrondi bancaire (`round(8.5) == 8`) ; ceux de
Postgres et SQLite arrondissent au plus loin de zéro (`round(8.5) == 9`). Une
surface de 42,5 m² recevait donc la tranche 40 si l'`unit_key` venait du scrape,
et 45 s'il venait du backfill SQL. **Deux cohortes pour un même lot, et la
republication qu'on cherche justement à rattraper passe au travers.** Relevé sur
l'archive : 263 annonces pile sur une frontière de tranche, dont 124 réellement
divergentes (0,4 % du stock).

Convention SQL adoptée (`floor(x + 0.5)`), parce que c'est elle qui a produit les
34 183 `unit_key` déjà en base. Aucun re-backfill nécessaire : aucun scrape n'a
tourné depuis la migration, tous les `unit_key` viennent donc du SQL.

### 6. Les « opportunités » étaient triées par la donnée la plus fausse

La vue `opportunites` n'avait aucun garde-fou de plausibilité. Ses premiers
résultats — ce qu'on regarde en premier — étaient des défauts de source :

    NOBLE STATE 39        sale   35 m²     27 000 THB    -100 %
    Ideo Q Sukhumvit 36   sale   46 m²     40 000 THB    -100 %
    The Tempo Ruamrudee   rent   3 757 m² pour 1 BR       -99 %

Les deux premières sont des **locations mal classées en vente** ; la troisième
porte la surface du projet dans le champ du lot. Sur le stock actif : 28 annonces
« vente » entre 5 k et 200 k THB, 60 surfaces > 500 m², 8 < 15 m². **Un écart de
−100 % ne désigne jamais une affaire, il désigne une donnée fausse.**

Aggravant : les bornes existaient déjà, en trois exemplaires qui ne se
connaissaient pas (`deals.ts`, `for-sale/page.tsx`, et rien en SQL). Les 114
annonces au-dessus de 100 M et les 68 en dessous de 800 k étaient donc exclues du
tableau de vente mais comptaient toujours dans la carte, les rendements et la
tension.

**Retenu :** `lib/market-bounds.ts` côté TypeScript, vue `listings_sane` côté
SQL, bornes commentées des deux côtés. On aurait pu ne les tenir qu'à un seul
endroit en filtrant côté application, mais les vues SQL sont consommées
directement (psql, exports, étude) : *une vue qui ne se protège pas elle-même
finit toujours par être lue sans son filtre.*

Résultat : 272 aberrations écartées (16 147 → 15 875 actives), le pire écart
passe de −100 % à −74 %, et les 1 307 opportunités restantes sont toutes
plausibles. Les extrêmes qui subsistent sont tous de niveau `rue` et de confiance
`faible` — SV City Rama 3 à 35 000 THB/m² contre une médiane de rue à 116 000,
ce sont deux classes d'immeubles différentes, pas une décote. La donnée est
désormais correctement étiquetée plutôt que fausse ; **durcir le niveau `rue`
reste une décision ouverte.**

### 7. Le test de tension ne pouvait pas tourner

Il importait `tension.compiled.mjs`, un artefact à produire à la main avec
`esbuild` — absent du dépôt et absent des dépendances. Et il imprimait
« OK / ÉCHEC » sans jamais sortir en code ≠ 0 : même réparé, il n'aurait rien
gardé. Passé à `node:test` exécuté par `tsx` (déjà installé), avec `npm test`.
Six cas, dont trois de non-régression sur les défauts ci-dessus : le
dénominateur ignore les délistées, trois écritures d'un nom d'immeuble comptent
pour un, le momentum ne bouge pas quand seule la moyenne monte.

Application de la règle 4 de la doctrine de présentation au passage : la pression
vendeuse pèse 25 % de l'indice et n'était affichée nulle part. Elle a désormais sa
colonne (« Sellers/bldg »), quartier et rue, et les descriptifs des deux vues
disent ce que l'indice calcule réellement.


### Contrôle après coup : la pression vendeuse encode ENCORE un tiers de la taille du marché

Classement recalculé sur la base réelle après correction (vente, 38 quartiers
notés, 19 en « données insuffisantes ») :

    tendus  : Wang Thonglang 65 (45 actives, 1,8 vend./imm.)
              Khan Na Yao    64 (15 actives, 1,07)
              Bueng Kum      61 (23 actives, 1,44)
    mous    : Sathon         26 (428 actives, 7,64)
              Thon Buri      27 (122 actives, 4,07)
              Bang Kho Laem  28 (156 actives, 6,00)

C'est cohérent et interprétable : Sathon, Vadhana et Pathum Wan, où sept vendeurs
se font concurrence dans le même immeuble, ressortent comme les marchés les plus
mous. Le renversement recherché a bien eu lieu.

**Mais le haut du classement reste la périphérie**, et ce n'est pas un hasard :
avec 15 annonces dispersées sur 14 immeubles, on obtient 1,07 vendeur par
immeuble **par construction**. Corrélation mesurée entre `log(nombre d'actives)`
et `annonces par immeuble`, sur les 38 quartiers publiés : **r = 0,55**, soit
30 % de variance partagée.

Autrement dit : l'ancienne « rareté » valait *littéralement* la taille du marché
(r = −1 par construction) ; la pression vendeuse en garde environ un tiers. Le
défaut est fortement atténué, **il n'est pas éliminé**. Le rétrécissement et le
seuil de publication limitent les dégâts, pas la cause.

Ce n'est corrigeable ni par une pondération ni par un seuil : il faut une mesure
qui ne dépende pas du comptage d'annonces. C'est exactement ce que fait la série
`cohort_snapshots` — la variation du stock d'une cohorte entre deux relevés,
insensible au nombre d'immeubles comme au nombre d'annonces. Un seul instantané
existe à ce jour (8 429 cohortes, le 2026-07-28) ; il en faut un second, donc un
scrap, pour que la série commence à parler. **Tant que ce n'est pas fait, le
score de tension se lit comme un indice relatif grossier, pas comme une mesure.**

### Reste ouvert (mesuré, non traité aujourd'hui)

- **1 399 annonces actives en doublon exact** (8,7 % du stock actif), sur les
  mêmes immeuble/type/chambres/surface/prix. **1 326 sont intra-source** — le
  même agent republie le même lot sur le même site, jusqu'à 28 fois. Ça gonfle
  mécaniquement la pression vendeuse qu'on vient de réparer. `unit_key` existe :
  il peut servir à ça.
- **L'empreinte photo est inerte** : `photo_sizes` compte 0 ligne, `est_doublon()`
  n'a aucun appelant, `repost_of` n'est jamais écrite. Et comme l'empreinte n'est
  relevée que pour les nouvelles annonces, les 16 147 actives n'en auront jamais :
  la détection ne pourra apparier que des annonces nées après aujourd'hui. Son
  test est par ailleurs laxiste — il conclut au doublon dès 2 poids concordants
  sur 8 quand les nombres de photos diffèrent, sans exiger de proportion.
- **Payload** : `/for-sale` sérialise vers le navigateur les 8 063 annonces de
  vente **plus** les 16 147 actives (`allListings`), sans cache, et rend jusqu'à
  8 000 lignes de tableau sans virtualisation. Les choix « on charge tout »
  datent de l'époque où la base comptait ~1 000 actives. Les données ne bougeant
  que tous les 4 jours, la mise en cache est le gain le plus élevé pour le moins
  d'effort.
- **`year_built` : 0 sur 4 514 condos.** `backfill_condo_years.py` écrit dans
  SQLite, pas sur le serveur. C'est la donnée la plus structurante pour une
  stratégie à 5-10 ans, et elle est vide.
- **Quota étranger : 197 annonces sur 16 147** (1,2 %). Critère éliminatoire pour
  un acheteur étranger — sans lui, aucune liste n'est actionnable.
- **Logique métier dupliquée TS ↔ Python** : `study/run_study.py` réimplémente
  `median`, `winsorize`, `norm_condo` et le rendement within-condo déjà présents
  dans `lib/yields.ts`. Deux implémentations, deux vérités possibles, et rien qui
  signale la divergence.

---

## 2026-07-28 (nuit) · Le doublon qui n'en était pas, et le poids des pages

### Ce que j'avais annoncé comme un défaut, et qui n'en est pas un

L'entrée précédente listait en tête des sujets ouverts : « 1 399 annonces actives
en doublon exact (8,7 % du stock), 1 326 intra-source, pire groupe 28 fois le
même lot ». Avant d'écrire la déduplication, inspection des groupes :

```
The Line Vibe, 1BR 37 m² à 22 000 THB   28 annonces, 28 identifiants DDproperty
Hampton Residence Thonglor, 1BR 32 m²   14 annonces, identifiants FazWaz
                                        CONSÉCUTIFS (u6548791 … u6548800)
```

Des identifiants d'unité **consécutifs** chez la source, ce sont des **lots
distincts** versés en lot par une agence : un immeuble neuf dont tous les 32 m²
se louent au même prix. Les fusionner aurait effacé de l'offre réelle —
c'est-à-dire exactement ce que la pression vendeuse doit compter. **La dédup
aurait détruit du signal.**

Second point que j'avais manqué : ces annonces sont **simultanément actives**. Ce
n'est donc pas le phénomène de republication séquentielle que les cohortes
traitent. J'avais confondu deux choses différentes sous le mot « doublon ».

**Leçon de méthode** : un compte agrégé ne dit pas ce qu'il compte. « 1 399
doublons exacts » était une requête SQL correcte et une conclusion fausse. Ce qui
l'a démasquée, c'est d'avoir regardé dix lignes.

### Ce qui rend la question décidable : l'agent

Deux annonces identiques du **même agent** sont un doublon. Les mêmes venant
d'agences concurrentes sont deux mises en marché, voire deux lots. Ce champ était
**déjà dans le blob `__NEXT_DATA__`** que l'adaptateur DDproperty parse — il
était simplement ignoré. Sonde sur une page réelle : `agent_id`, `agency_id`,
`posted_at` et `is_auto_repost` remplis **22/22**, 11 agences distinctes, et déjà
un doublon même-agent sur la page.

Vue `doublons_agent` fournie, **volontairement pas branchée** sur les
statistiques : vide tant qu'`agent_id` n'est pas collecté. Mieux vaut ne rien
fusionner que fusionner à tort.

### Le vrai gain était ailleurs : `posted_at`

DDproperty expose `postedOn.unix` — la **date de mise en ligne réelle**.
`first_seen` ne dit que le moment où *notre* scan a croisé l'annonce : tout
time-on-market qui en découle est borné par la cadence de scan. C'est le défaut
de fond derrière le délai de grâce, l'option `reliableDelistingSince` et la
contamination de l'absorption — **trois contournements d'un même problème**.
`posted_at` attaque la cause. Et le site signale lui-même ses republications
automatiques (`isAutoRepost`), vu à `true` dès le premier résultat testé.

### Poids des pages : mesuré, puis réduit de 80 %

Relevé sur le serveur de production local, authentifié :

| Page | Avant | Après | 1er appel | Après cache |
|---|---|---|---|---|
| `/for-sale` | 19,6 Mo | **3,9 Mo** | 3,7 s | **0,51 s** |
| `/to-rent` | 19,7 Mo | **4,0 Mo** | 0,60 s | 0,38 s |
| `/rendements` | 13,4 Mo | **3,2 Mo** | 0,38 s | 0,55 s |

Trois causes distinctes, trois correctifs :

1. **Requêtes rejouées à chaque chargement.** Les pages sont en `force-dynamic`
   — obligatoire, l'accès dépend d'un cookie — donc chaque navigation refaisait
   la requête de 16 000 lignes vers ap-southeast-1. Mémoïsation à durée de vie
   (`lib/cache.ts`, 1 h). **Pas `unstable_cache`** : il écrit dans le Data Cache,
   plafonné à 2 Mo par entrée sur Vercel ; nos lectures dépassent, l'entrée
   serait silencieusement rejetée. Un cache qui ne cache pas est pire que pas de
   cache, parce qu'on croit le problème réglé.

2. **L'appariement vente↔location tournait côté client.** Il a besoin des deux
   catégories, ce qui obligeait la page à expédier `allListings` — les 16 000
   actives — pour n'en tirer que deux nombres par ligne. Déporté sur le serveur
   (`buildUnitMatchesLite`), qui n'envoie que ces deux nombres.

3. **Les annonces partaient entières.** Le tableau affiche neuf colonnes ;
   images, amenities, `rawData`, proximité et adresse brute traversaient le
   réseau sans être lus. Projections `ListingRow` et `YieldInput` ; `applyFilters`
   et les fonctions de `yields.ts` rendues génériques sur un sous-ensemble
   structurel, **pour ne pas dupliquer la logique** — c'est le défaut qu'on
   vient de corriger ailleurs.

4. **8 000 lignes de tableau, soit 72 000 nœuds DOM.** Rendu par tranches de 200
   avec un bouton « Show 200 more ». Le filtrage et le tri portent toujours sur
   l'ensemble : seul l'affichage est borné.

### Reste ouvert

- **`/tension-table` : 8,6 Mo**, inchangé. Elle sérialise les 34 275 annonces
  (actives et délistées) pour un calcul client. Même remède que ci-dessus, non
  appliqué faute d'avoir été demandé.
- La dédup **même-agent** deviendra applicable au prochain scrape.
- **`posted_at` doit remplacer `first_seen`** dans le calcul du time-on-market
  dès qu'il sera peuplé. C'est la vraie sortie du problème d'absorption.
- Les trois autres adaptateurs n'exposent pas d'agent aussi clairement.
  PropertyScout mérite une sonde équivalente.
