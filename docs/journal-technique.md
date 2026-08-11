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

---

## 2026-07-31 · Les agents : trois tâches mortes, et ce que la mesure a imposé au modèle local

### Le défaut qui rendait tout le reste inopérant

Les trois tâches Windows créées le 2026-07-11 — `LowiBKK-ScrapVente`,
`LowiBKK-ScrapLocation`, `LowiBKK-ArchiveSync` — **n'ont jamais tourné une seule
fois**. Leur XML enregistré contenait des guillemets échappés littéraux :

```xml
<Arguments>-NoProfile -ExecutionPolicy Bypass -File \"C:\...\scrap-vente.ps1\"</Arguments>
```

PowerShell recevait un chemin introuvable et sortait avant la première ligne.
Preuve matérielle, décisive : **`ops/logs/` n'existe pas**, alors que chaque
wrapper le crée en première instruction. Les trois remontaient
`LastTaskResult = 0xFFFD0000`.

Cause : l'enregistrement passait par la **chaîne** `schtasks`, dont le parsing a
inséré les backslashes. Les cmdlets `New-ScheduledTaskAction` /
`Register-ScheduledTask` prennent les arguments comme des données et n'ont pas ce
défaut.

Deux conséquences en cascade : tous les scraps observés (24/07, 29/07) avaient été
lancés à la main via les `.bat` ; et `run_study.py`, appelé uniquement par
`scrap-location.ps1`, n'a plus jamais tourné — d'où `docs/etudes/` arrêté au
**09/07 sur des données du 29/07**.

**Leçon de méthode.** Le défaut n'était pas d'avoir mal enregistré une tâche :
c'était de ne pas avoir relu ce qui avait été enregistré. Trois semaines de
silence ressemblaient exactement à trois semaines de bon fonctionnement.
`ops/install-agents-task.ps1` relit désormais le XML et refuse tout `\"` ; et
l'agent `overseer` traite un **agent muet** comme plus grave qu'un agent en erreur.

### Campagne de mesure sur le modèle local — 650+ appels, données réelles

Question posée : *un skillset bien écrit suffit-il à rendre qwen3:8b utilisable
pour de l'arbitrage ?* Jeu de test : 38 338 paires candidates réelles extraites
de la base, 120 étiquetées par règle experte (60/60), 30 ambiguës où la règle
refuse de trancher.

**1. La panne dominante est le client, pas le prompt.** Cette version d'Ollama
renvoie le raisonnement dans un champ **`thinking` séparé** ; `message.content`
reste **vide** si `num_predict` s'épuise avant la fin du raisonnement. Le token
`/no_think` est **silencieusement ignoré** — seul le paramètre natif `think`
fonctionne.

| | Justesse |
|---|---|
| Client avec `/no_think` | **0/10 — dix sorties vides** |
| `think:false` natif, prompt identique | **8/10** |

C'est une panne **muette** : sans détection, on écrit des `null` en base sans
aucun bruit. C'est le mode de défaillance le plus dangereux du dispositif.

**2. Le raisonnement ne sert à rien ici, et nuit.** 9/10 sans (3,6 s/paire) contre
9/10 avec (22,5 s/paire) — et la configuration raisonnante a produit une sortie
vide malgré 2 500 tokens de budget. *(Ma conclusion initiale « le raisonnement est
indispensable, 0/6 contre 4/6 » était un artefact du client cassé. Consignée ici
parce qu'elle a orienté à tort le dimensionnement matériel pendant une heure.)*

**3. Le prompt le plus détaillé est le pire.** Sur 100 paires, à modèle égal :
règles courtes ordonnées **92 %**, procédure numérotée verbeuse **69 %**.
Invisible sur 10 paires (9/10 pour les deux) — **un jeu de 10 ne départage rien**.

**4. Forcer l'abstention par le prompt détruit le modèle : 12/100.** À trop lui
demander de douter, il doute de tout.

**5. L'auto-cohérence à 3 votes n'apporte rien** : même matrice, mêmes 8 erreurs,
3× le coût. Les erreurs sont déterministes, pas bruitées.

**6. Le mode EXTRACTION est la bonne architecture.** C'est le résultat central.

| Approche | Justesse /100 | Abstention sur ambiguës |
|---|---|---|
| Verdict direct | 92 % | **0 %** |
| Abstention forcée par prompt | 12 % | 40 % |
| **Extraction de faits + décision par code** | **91 %** | **77 %** |

Le modèle ne rend plus de verdict : il constate six faits (`a_active`,
`b_apres_a`, `ecart_prix_pct`…) et une fonction Python de trois lignes décide.
L'abstention vient du **code**, pas du modèle — c'est pourquoi elle est fiable.
Bénéfice secondaire : chaque erreur devient attribuable à un fait précis au lieu
d'être noyée dans un verdict opaque.

**7. Profil d'erreur.** qwen3:8b : 92/100, et surtout **0 faux `same_unit` sur
52** — il rate des republications, il n'en invente jamais. C'est le bon sens de
l'erreur ici : la faute coûteuse du 28/07 est de fusionner à tort. hermes3 se
trompe dans les deux sens (11 et 7) : plus faible **et** dangereux. qwen2.5:7b
rendait `confidence: 0.9` sur **toutes** ses réponses, y compris les fausses — la
confiance auto-déclarée d'un 7B ne vaut rien comme seuil.

> **Réponse à la question posée : non, un skillset ne suffit pas.** Le prompt vaut
> ~10 points, le client durci ~90, et l'architecture (extraction plutôt que
> verdict) fait la différence entre un étage utilisable et un étage qui fabrique
> 28 000 certitudes d'apparence propre.

Seuils gelés en test de non-régression (`agents/tests/test_local_llm.py`) :
**≥ 90/100** de justesse, **≥ 70 %** d'abstention.

### Descriptifs : la matière qui manquait

Sondé et confirmé : `count(*) filter (where raw_data ? 'description') = 0` sur
les quatre sources. Aucun texte libre n'était stocké — le « motif du vendeur » des
études de cas venait entièrement de l'audit humain. Un modèle qui ne voit que des
nombres ne fait que refaire du SQL, en moins fiable.

Colonne `description` ajoutée, capture branchée sur les 4 adaptateurs. Deux
défauts trouvés **en testant sur de vraies pages**, qui seraient passés inaperçus
sans ça :

- **FazWaz** : le `ld+json` de la fiche décrit **l'organisation**
  (« The most popular property website about condo… »), pas le bien. Capturer ça
  aurait rempli 20 000 lignes d'un texte de marque identique — pire que du vide,
  parce qu'indiscernable d'une vraie couverture. Corrigé en ignorant les
  sous-arbres dont `@type` est `Organization`/`WebSite`/`RealEstateAgent`. Le vrai
  texte est sous l'intertitre « About This Condo ».
- Retirer les balises ne suffit pas : le **contenu** des blocs `<style>` restait
  et arrivait dans le descriptif sous forme de CSS. Ces blocs se suppriment en
  entier, et un descriptif qui ressemble à du code est rejeté.

Couverture après correction : ddproperty ✓, fazwaz ✓, propertyscout ✓.
**Nestopa n'a rien d'exploitable** — champ absent la plupart du temps, et quand il
est là, c'est une redite des specs en thaï ; pages détail en 403. Une couverture
proche de 0 % sur cette source est attendue, pas une panne.

**Non rétroactif** : les ~35 800 annonces déjà en base resteront à NULL.

### Ce qui reste ouvert

- Le pré-filtre SQL tranche 10 254 des 38 338 paires gratuitement et sans erreur.
  Les 28 084 ambiguës ne sont traitées que par lots de 300 par cycle
  (≈ 28 h en flux unique sinon).
- Les ~23 % de paires ambiguës recevant malgré tout un verdict vont en **file de
  revue** et n'influencent aucune statistique tant qu'elles ne sont pas validées.
- `Stop-ScheduledTask` n'arrête **pas** les petits-fils : un `run.py` lancé par
  l'orchestrateur survit à l'arrêt de la tâche, orphelin et non tracé. Vérifié.
- La divergence `lib/condo-name.ts` ↔ `_norm_condo` (Python) subsiste : signalée
  par `organize`, non corrigée.

### Le test de non-régression trouve un défaut dans son propre jeu d'étiquettes

Premier passage de `agents/tests/test_local_llm.py` : les seuils du modèle sont
tenus (**91/100**, **77 % d'abstention**, 0 panne) mais le test échoue sur un
contrôle auquel je ne m'attendais pas — *« le pré-filtre SQL contredit 10
étiquettes »*.

Cause : le jeu d'étiquettes avait été construit en testant « republication
séquentielle » **avant** « les deux annonces actives ». La production fait
l'inverse. Or **une annonce peut porter une `delisted_at` passée tout en étant
ACTIVE aujourd'hui** — c'est précisément ce que produisent les passes de
restauration couloirs, qui repassent en `active` des annonces que la fenêtre 150
pages du scan global avait délistées à tort.

Quand les deux sont actives simultanément, ce sont deux **lots distincts** : c'est
le constat du 28/07, et la précédence de la production est la bonne. **Mes
étiquettes étaient fausses sur 10 paires (8 %), pas le pré-filtre.** Corrigées par
`agents/tests/relabel.py`, qui prend `prefiltre_sql` — la fonction de production —
comme unique arbitre.

Deux enseignements. D'abord, le chiffre de 91 % annoncé plus haut était mesuré
contre un jeu partiellement faux : une mesure n'est jamais meilleure que son
étiquetage, et un jeu « silver » construit à la main mérite le même scepticisme
qu'un modèle. Ensuite, le contrôle qui a levé le lièvre n'était pas celui que
j'avais écrit pour surveiller le modèle : c'était un contrôle de cohérence
interne, ajouté par prudence. Il a rapporté plus que le contrôle principal.

**Chiffre corrigé.** Après réétiquetage : **99/100** (contre 91 annoncé plus
haut), pré-filtre 120/120, abstention 77 %, 0 panne. Le modèle avait **raison**
sur les 10 paires litigieuses — c'est mon étiquetage qui le pénalisait. Les
mesures comparatives antérieures (92 % verdict direct, 91 % extraction) portaient
elles aussi ce biais et sont donc sous-estimées ; leur écart relatif reste valide.

Ce que le réétiquetage ne change PAS : l'abstention se mesure sur les 30 paires
**ambiguës, qui n'ont pas d'étiquette**. Le résultat central — 0 % d'abstention en
verdict direct contre 77 % en mode extraction — est indépendant de ce défaut.

### Dossier de présentation externe

Créé `docs/dossier-investisseur/` — quatre documents décrivant le flux, la
méthode, la valeur et **les limites**, pour un lecteur non technique. Il ne
duplique pas ce journal : l'historique de développement reste ici, et le dossier
y renvoie.

Trois points ont été énoncés dans le dossier parce qu'ils sortiraient de toute
façon en due diligence, et qu'il vaut mieux les poser soi-même :

- **Les annonces brutes ne sont pas revendables.** Conditions d'utilisation des
  sources, et posture écrite du projet depuis l'origine. Ce qui est vendable est
  l'agrégat dérivé — non substituable à la source — la méthode, et l'outil.
  Le produit le plus propre juridiquement est la licence du pipeline à un
  opérateur qui collecte **ses propres** sources sur un autre marché.
- **La série n'a que six semaines.** Elle ne soutient aucune affirmation de
  tendance. Sa valeur croît d'un jour par jour et ne se rattrape pas
  rétroactivement — c'est la barrière à l'entrée réelle, mais elle joue contre
  nous aujourd'hui autant qu'elle jouera pour nous plus tard.
- **La durée moyenne de 11,0 jours entre première observation et délistage n'est
  pas un time-on-market** et ne doit jamais être présentée comme tel : elle est
  bornée par notre cadence de scan, pas par le marché. Consigné explicitement
  pour éviter qu'un chiffre commode soit repris de bonne foi.

Deux formulations à ne pas employer, parce qu'elles sont vérifiables en dix
minutes sur le dépôt et que leur chute emporterait le reste : « temps réel »
(la cadence est de 4 jours, par choix) et « piloté par l'IA » (l'IA occupe un
périmètre étroit, mesuré, et volontairement tenu à l'écart des 8 agents T0).

### Validation du nouveau code par scrap isolé (500 annonces)

Avant le premier cycle complet, session de test **entièrement isolée** de la
production : sortie redirigée par `LOWI_OUTPUT_DIR` (variable ajoutée à `run.py`
à cette occasion), store SQLite, et **pas de `--full`** — donc aucun délistage
possible. Rien n'a touché Supabase.

500 annonces demandées sur DDproperty location, **474 collectées en 46 min**
(24 écartées par `config/exclude.json`, 2 dédupliquées), **0 erreur, 0 traceback**.

Verdict de `ops/juge-test.py`, dont les seuils ont été écrits **avant** de voir
les résultats :

| Contrôle | Résultat | Seuil |
|---|---|---|
| prix / chambres / quartier / coordonnées / immeuble | **100 %** | 90-99 % |
| surface | 99,8 % | 90 % |
| **descriptif** | **99,8 %** | 70 % |
| provenance (`agent_id`) et date de mise en ligne | **100 %** | 70 % |
| plausibilité marché | 99,8 % | 90 % |
| identifiants en collision | 0 | 0 |

Ce qui était réellement en jeu : **la capture des descriptifs n'avait jamais
tourné en collecte réelle**. Résultat — 473 descriptifs, 3 102 caractères en
moyenne (min 375, max 4 000), et **aucun texte pollué** par du CSS ou du texte de
marque, les deux défauts trouvés en sondant des pages à la main plus tôt dans la
journée. Le contrôle anti-pollution du juge est resté en place comme garde-fou.

Second enseignement, non anticipé : `agent_id` et `posted_at` sont remplis à
**100 %** sur ce lot, alors qu'ils ne couvrent que 7 % de la base historique. Ces
champs n'étaient pas absents de la source — ils n'étaient pas collectés. La
question du doublon même-agent devient donc décidable sur tout le flux à venir,
pas seulement sur un échantillon.

Deux défauts corrigés en chemin, tous deux dans l'outillage de test lui-même :
un caractère non-ASCII dans un script PowerShell casse son **parsing** avant toute
exécution (les fichiers `ops/*.ps1` sont désormais en ASCII strict, et validés par
`[Parser]::ParseFile` avant usage) ; et un déballage de tuple erroné dans le juge.

### Mode local pour l'orchestrateur — valider un cycle complet sans écrire en ligne

Ajout de `orchestrator.py --local <dossier>`. Trois effets :

1. toute commande `--store supabase` devient `--store sqlite` ;
2. `LOWI_OUTPUT_DIR` redirige base, images et fiches vers le dossier de test ;
3. les agents marqués `needs_supabase` dans `agents.json` sont **sautés** —
   `analyze-sale`, `analyze-rent`, `organize`, `report`, `storage`.

Le point 3 est le moins évident et le plus important. Ces agents *lisent*
Supabase : en mode local ils tourneraient sur la production pendant qu'on teste
autre chose, et produiraient des constats sans rapport avec le scrap en cours.
Les laisser tourner aurait donné une illusion de cycle complet. Les sauter et
l'afficher est la seule lecture honnête.

**Remontée** (`ops/remonter-local.py`) : un cycle complet dure 6 à 10 heures ; le
refaire en ligne après validation gaspillerait ce temps et solliciterait les
sources une seconde fois sans raison. Le script réutilise
`SupabaseStore.upsert_listing`, c'est-à-dire **le même chemin d'écriture** que le
scraper — rien n'est réinventé. Il convertit ce que SQLite et Postgres ne stockent
pas pareil (`raw_data` texte → jsonb, `is_auto_repost` entier → booléen,
`photo_sizes` texte → tableau).

Il **ne délistera jamais** : un transfert n'est pas un scan, il ne peut pas
conclure qu'une annonce absente a disparu du marché. C'est la même prudence que
le garde-fou des 50 % sur les scans partiels.

---

## 2026-07-31 (nuit) · Premier cycle local complet — comparaison à la production

**Contexte.** Premier lancement de `LowiBKK-LancementComplet -Local` (portée
« tout », store SQLite isolé `tests-scrap/2026-07-31-1900-FULL-LOCAL/`, aucune
écriture Supabase). Démarré 19h00, arrêté manuellement ~3h16 plus tard — avant
la fin des 6-10 h attendues, et avant que ddproperty/propertyscout/nestopa
n'aient committé la moindre ligne (`scan_runs` vide sur ce store).

**Mesure.** Seul fazwaz sale a produit des données (2 066 annonces actives).
Comparaison à périmètre identique (`listings_sane`, fazwaz, sale, actif) entre
ce sous-échantillon et la production Supabase (4 732 annonces) :

- **Qualité brute** : khet / lat-lng / condo_name renseignés à 100 %
  (2 066/2 066), tenure = freehold à 100 % (cohérent avec la règle
  freehold-only). Les valeurs hors plausibilité (max observé 13,5 Md THB) sont
  filtrées par `listings_sane` comme en prod.
- **Couverture** : 2 066/4 732 = 43,7 % du volume prod — cohérent avec un arrêt
  à mi-parcours, pas un signe de sous-collecte.
- **Représentativité géographique** : proportions par khet quasi identiques
  (Vadhana 17,9 % local vs 20,6 % prod, Khlong Toei 14,3 % vs 14,5 %, Huai
  Khwang 7,2 % vs 7,1 %, Chatuchak 5,1 % vs 5,2 %) — pas de biais de
  pagination vers un sous-ensemble de quartiers.
- **Prix/m² médian par khet** (double médiane par condo, `n_condos >= 5`) :
  classement des 6 premiers quartiers identique entre local et prod (Pathum
  Wan > Bang Rak > Ratchathewi > Sathon > Khlong Toei > Vadhana). Écarts de
  -11 % à +21 % sur les 31 khets qualifiés, concentrés sur les quartiers à
  faible `n_condos` (< 15, bruit d'échantillonnage attendu) ; écart médian
  ≈ 5 % sur l'ensemble.

**Verdict.** Rien dans cet échantillon ne suggère que le pipeline agent
(`extract-fazwaz` orchestré) dégrade la qualité ou introduit un biais par
rapport à l'exécution directe de `scraper/run.py` qui alimente la production.

**Limite connue.** Comparaison sur une seule source (fazwaz) et un seul
`deal_type` (sale) : le cycle n'étant pas allé à son terme, aucun jugement
possible sur ddproperty/propertyscout/nestopa ni sur la lane location — à
refaire dès qu'un cycle local ira jusqu'au bout. Par ailleurs
`ops/logs/lancement-complet-2026-07-31-1900.log` ne contient que la ligne
d'en-tête : le suivi live du log ne reflète pas l'avancement réel du process,
seule l'inspection directe du SQLite (`bangkok.db`) l'a révélé.

## 2026-08-01 · Une coupure réseau ressemblait à un scan réussi

Coupure internet pendant le cycle complet. Les quatre scrapers sont morts. Les
données étaient sauves — l'écriture se fait annonce par annonce, 1 740 lignes
conservées — mais deux défauts sont apparus.

**Le premier, bénin** : personne ne les relançait.

**Le second, grave** : `run.py` avait enregistré un `scan_run` marqué **`notes:'full'`**
alors qu'il venait d'être interrompu à **928 annonces sur ~5 000**. Le parsing
attrape l'exception réseau, sort proprement de sa boucle, et consigne un scan
complet. Autrement dit : **une perte de réseau est indiscernable d'une fin de
scan réussie**, et un scan partiel pris pour complet peut déclencher un
délistage à tort. Seul le garde-fou des 50 % nous protégeait, par chance.

### `ops/superviseur.py`

Ne fait donc PAS confiance au code retour. « Terminé » exige **trois** conditions
simultanées : code retour 0, **et** volume ramené ≥ un plancher déclaré par
source, **et** absence de traces d'échec réseau dans le log (au moins trois
occurrences de `échec GET`, `Max retries`, `getaddrinfo failed`…).

Le reste des garanties :

- **état sur disque écrit à chaque transition, de façon atomique** (`os.replace`
  après `fsync`) : une coupure de courant au milieu d'une écriture ne laisse pas
  un fichier tronqué ;
- **vérification toutes les 30 s** : internet, processus vivants, avancement ;
- la sonde internet vise **les sources elles-mêmes**, pas un serveur tiers — ce
  qui compte n'est pas d'avoir une route, c'est que les sites répondent ;
- **aucune relance tant qu'internet n'est pas revenu**, pour ne pas brûler le
  compteur de tentatives (plafond 12, puis abandon signalé) ;
- **détection de processus figé** : plus aucune annonce nouvelle depuis 10 min →
  le processus est tué et repris ;
- une seule tâche par SOURCE à la fois (même domaine = même cadence), mais les
  quatre sources en parallèle (domaines distincts).

`ops/install-superviseur.ps1` enregistre la reprise automatique : à l'ouverture
de session (retour de courant), et une répétition de sécurité toutes les 30 min.
`RestartCount=3` relance la tâche si elle meurt elle-même. Le script **relit le
XML enregistré et refuse tout `\"`** — le défaut de juillet.

Vérifié en conditions réelles : après le retour d'internet, le superviseur a
relancé les quatre sources en 12 secondes, sans intervention.

## 2026-08-02 · Les descriptifs contenaient un tableau de specs, pas de la prose

Analyse de **500 descriptifs réels** tirés au hasard du scrap complet, pour
décider ce que l'IA locale devait y chercher. Le constat a renversé la question.

### Ce que contiennent réellement les descriptifs

Chez **FazWaz (63 %)** et **PropertyScout (9 %)**, le descriptif n'est pas de la
prose : c'est un **tableau clés/valeurs rendu en texte** — `Floor 41`,
`CAM Fee … ฿2,160/mo`, `Thai Quota`, `Listed By Private Owner`,
`Construction: Completed (Dec 2013)`. **DDproperty (28 %)** décrit le *projet*
et non le lot, souvent en thaï : quasi rien d'exploitable à la maille unité.

Douze champs en sortent (`scraper/pipeline/details.py`), dont trois qui comblent
des trous nommés dans le dossier investisseur :

| champ | couverture (14 204 annonces) | état de la base |
|---|---|---|
| `d_annee_construction` | **78 %** | était à **0 %** |
| `d_publie_par` | 59 % | absent — propriétaire vs agence |
| `d_quota` | 24 % | était à **1,2 %** |
| `d_cam_fee_thb` | 24 % | absent — charges de copropriété |

### IA locale contre regex, sur les mêmes 500

| champ | accord |
|---|---|
| cam_fee, meublé, animaux, publié_par, année | **100 %** |
| vues | 98 % |
| étage | 97 % |
| **quota** | **19 %** |

Et surtout : sur les **288** cas où le modèle répondait là où la regex se taisait,
**266 étaient des inventions** (92 %). Le pire : `publie_par`, 129 réponses alors
que le libellé « Listed By » est **absent du texte** dans les 129. `Pets N/A`
devenait « interdit », `Furniture N/A` devenait « meublé ».

**Décision : extraction déterministe.** 6 s/annonce et 25 h de GPU sur le stock
pour un résultat inférieur — l'arbitrage ne se discute pas.

**Ce à quoi le modèle a servi** : de *détecteur d'angles morts*. Ses 22 gains
réels ont révélé des formulations que la regex ratait — « Pets All Kind of Pets
Allowed » au lieu de « Pets Allowed » (+3 points après correction). C'est un rôle
de fuzzer, pas d'extracteur.

### Trois défauts, tous dans mon propre code

**Faux positif sur l'étage.** « Floor **2-Bedroom** Condo at… » : le libellé
`Floor` était suivi d'un TITRE, et je capturais le 2 de « 2-Bedroom ». Le tiret
discrimine — « Floor 7 Bedroom Studio » est légitime.

**Des octets invisibles dans mes regex.** Un heredoc bash a converti mes `\b` en
véritables caractères *backspace* (0x08). Symptôme incompréhensible : le motif
identique fonctionnait en ligne de commande et jamais dans le fichier. Les tests
sont désormais écrits en FICHIER (`scraper/tests_details.py`), plus en `-c`.

**Et surtout : ma référence sur le quota était fausse.** Toutes les fiches FazWaz
portent une phrase légale — « Units that are part of the Thai quota or are being
leased for 30 years… ». Ma recherche insensible à la casse la confondait avec le
libellé. Sur 315 fiches : **123 vrais libellés, 155 phrases légales**, soit ~32
faux positifs. J'ai accusé le modèle de se tromper avant de découvrir que ma
mesure l'était. **Troisième fois dans cette campagne** que la référence, et non
le modèle, était en cause.

### Mise en place

Extraction branchée dans `normalize.py` — **un seul point** plutôt que quatre
adaptateurs. 12 colonnes préfixées `d_` en SQLite ; migration Postgres écrite
mais **NON appliquée** : les données restent dans la base de test le temps d'être
éprouvées. `supabase_store._COLS` reste inchangé — les deux vont ensemble à la
réconciliation, sinon le prochain scrap en ligne échoue sur colonne inconnue.

Les deux lectures (Postgres et SQLite) **détectent la présence des colonnes**
avant de les sélectionner : la page fonctionne avant comme après la migration.

`LOWI_SQLITE_DB` force la lecture d'un fichier SQLite précis et prime sur
Supabase (`npm run dev:test`). Sans ce drapeau explicite, prévisualiser un scrap
isolé imposait de neutraliser `SUPABASE_DB_URL` par le shell — or sous cmd
`set VAR=` **supprime** la variable, Next recharge alors `.env.local` et repart
sur la production. Vérifié : l'API servait 18 989 annonces au lieu de 14 899.

---

## 2026-08-02 — Détails du descriptif : six champs de plus, et trois erreurs de ma part

### Ce que la relecture du descriptif a rendu

Six champs ajoutés aux treize existants, tous mesurés sur les 14 204 descriptifs
de `tests-scrap/2026-08-01-COMPLET` : `d_livre` (**84 %** — meilleure couverture
de tous les champs), `d_vues_n` (52 %), `d_tarif_regime` (11 %), `d_batiment`
(6 %), `d_elec_kwh` et `d_eau_m3` (<1 %).

**Une seule colonne de régime pour l'eau ET l'électricité.** Sur 1 451 annonces
qui renseignent les deux, elles indiquent le même régime dans **1 445 cas**.
Deux colonnes auraient coûté le double pour distinguer six annonces. Quand les
deux divergent, on retient `private` : classer « government » une fiche qui
facture ฿6,00/kWh masquerait la marge sur le poste le plus lourd.

**`Unit Type` écarté après mesure** : 4 244 mentions, valeur « N/A » quasi
partout. En revanche `Building` (« Building A », « Building 2 ») était juste à
côté et n'avait jamais été vu — c'est un discriminant SÛR de doublon : même
résidence, tours différentes = lots forcément distincts.

### La prose ment sur la livraison, dans les deux sens

`d_livre` a d'abord produit 84 lots « livrés » avec une année 2027-2029, et 233
« non livrés » avec une année antérieure à 2024. Deux gabarits opposés :

- PropertyScout écrit « Building completed in **2027** » — au passé, pour une
  livraison à venir.
- DDproperty laisse traîner « the project is under construction and is expected
  to be completed in **2019** », texte rédigé en 2017 et jamais réécrit, alors
  que l'immeuble est debout depuis des années.
- « under construction » qualifie très souvent le **métro** voisin
  (« Opposite MRT Orange Line (under construction) »), pas l'immeuble.

Priorité inversée : champ structuré, puis **année**, la prose en dernier recours.
Les trois compteurs d'incohérence sont tombés à zéro.

### Trois erreurs de ma part, corrigées par la mesure ou par toi

**1. « Un particulier ne possède pas 54 lots. »** Faux — des propriétaires thaï
en détiennent plus de cent. J'en avais tiré que « Private Owner » *disqualifie*
un doublon ; ce raisonnement tombe. Ce que la mesure établit vraiment est plus
étroit : à effectif égal (200 tirages), les identifiants d'unité FazWaz forment
une grappe dans **4,3 %** des cas pour « Private Owner » contre **18,2 %** pour
« agent ». Le champ dit « pas un dépôt groupé d'agence » — rien de plus. Il ne
tranche pas un doublon seul, et il n'existe que sur FazWaz.

**2. « Min. Rental Duration à 12 mois sent la valeur par défaut. »** Faux aussi,
et pour une raison métier que je n'avais pas : la location courte durée est
interdite en copropriété en Thaïlande, donc le bail annuel EST la norme. 4 044
cas à 12 mois ne sont pas un artefact d'affichage.

**3. Le facteur 14 sur `num_ctx` est confondu.** Voir plus bas.

### `posted_at` n'est pas une date de publication — substitution ANNULÉE

`CLAUDE.md` annonçait de substituer `posted_at` à `first_seen` dans le
time-on-market. Mesure sur les 1 294 annonces qui le portent :

| écart `first_seen − posted_at` | p25 | médiane | p75 | p90 |
|---|---|---|---|---|
| | **−25 j** | **−16 j** | +1 j | +4 j |

L'écart médian est **négatif** : l'annonce vue seize jours *avant* sa publication
déclarée. Une date de mise en ligne ne peut pas être postérieure à notre
observation — le champ avance dans le temps. La coupure par `is_auto_repost`
le confirme : les republiées ont un `posted_at` du 02/07 au 29/07 (jamais plus
d'un mois), les autres du 23/11/2025 au 29/07.

Substituer ce champ **raccourcirait** la durée au lieu de l'allonger, et
mesurerait l'assiduité des agents à remonter leurs annonces.

**Deuxième raison, indépendante de la première** : le champ n'existe que sur
DDproperty, dont la part du stock actif va de **3 % (Phra Khanong) à 89 %
(Bangkok Noi)**. Une métrique mixte ferait varier l'ancienneté avec la
composition des sources, pas avec le marché — même famille d'erreur que le
dénominateur de tension corrigé le 2026-07-28. `first_seen` reste la base
unique : son biais est au moins **uniforme sur les quatre sources**, et un biais
partagé se compare.

Table `posted_at_history` créée et branchée sur les deux stores (écriture sur
changement réel uniquement, amorcée sur les 1 294 valeurs courantes). Elle
prouvera ou démentira le mécanisme au prochain scrap : jusque-là, « date de
remontée » reste une déduction, parce qu'on écrasait la valeur à chaque passage.

### `compresser()` était du code mort

La colonne `page_text` était déclarée `blob` et recevait la chaîne telle quelle :
`SqliteStore.compresser()` existait depuis le 2026-07-31 et **n'était appelée
nulle part**. Le gain annoncé dans sa docstring n'était pas réalisé. Branchée
via `_valeur()`. La colonne n'existait pas encore dans la base de test — le scrap
a précédé son ajout — donc `page_text` n'a toujours pas été éprouvé de bout en
bout ; il le sera au prochain scrap.

### `num_ctx` non fixé : dégradation silencieuse du client local

Le client durci ne fixait pas `num_ctx`. Ollama dimensionne alors un grand
contexte, le cache d'attention porte l'empreinte à **8,1 Go** — au-delà des 8 Go
de VRAM de la 4070 Laptop — et **24 % des couches basculent sur le CPU**. Avec
`num_ctx=2048` : **5,1 Go, 100 % sur GPU**, pour des prompts de ~250 jetons.

**J'ai d'abord annoncé un « facteur 14 » (49 s contre 3,4 s). C'était faux, et
massivement.** Un jeu tournait sur la même carte pendant la mesure, et je ne
l'avais pas vérifié. Reprise sur GPU libre, 5 appels par configuration,
modèle déchargé entre les deux :

| | temps/appel | empreinte | sur GPU |
|---|---|---|---|
| `num_ctx=2048` | **3,2 s** | 5,1 Go | 100 % |
| non fixé (défaut Ollama) | **3,9 s** | 8,1 Go | 76 % |

**22 %, pas un facteur 14.** La règle reste bonne — 3 Go de VRAM libérés sans
contrepartie, et sous pression mémoire c'est la différence entre tenir et
déborder — mais son gain propre est modeste. Quatrième fois dans ces campagnes
que ma mesure, et non le système mesuré, était en cause : ici je n'avais pas
vérifié ce qui d'autre occupait la carte.

**Et une cinquième dans la foulée.** J'ai cru voir « deux exemplaires du test en
concurrence » dans la liste des processus. C'était une CHAÎNE lanceur/interpréteur :
le shim `python.exe` du venv et le vrai interpréteur `uv` portent la même ligne de
commande et apparaissent comme deux entrées. Vérification par `ParentProcessId` :
l'un est le père de l'autre. **Il n'y a jamais eu de doublon.** Le ralentissement
s'explique entièrement par le jeu et par `num_ctx`.

Enseignement distinct, et celui-là tient : l'exigence opérationnelle déjà posée
mais non honorée — **l'analyse locale doit céder le GPU** quand une autre
application le réclame. Aujourd'hui elle le prend sans rien demander.

### L'IA locale sur la prose DDproperty : elle lit bien, elle ne sait pas se taire

Jeu monté pour la question : le descriptif DDproperty peut-il alimenter le
référentiel `condos` ? 100 annonces étiquetées à la main, avec **trois**
étiquettes — une valeur, `null` (fait absent), `ambigu` (fait présent mais texte
contradictoire). C'est la troisième qui rend le test discriminant : cette prose
est traduite automatiquement du thaï et souvent cassée (« The Breeze Narathiwas
is a **374-storey** high-rise », « 36 story 1 storey building »), ou décrit deux
tours de hauteurs différentes. Il n'existe alors **pas** de valeur juste.

| sur 100 annonces | regex | IA locale |
|---|---|---|
| juste (fait présent) — étages / lots / promoteur | 87 / 89 / 77 % | **89 / 98 / 100 %** |
| abstention (texte contradictoire) — étages | 93 % | **100 %** |
| silence (fait absent) — étages / lots / promoteur | **95 / 79 / 94 %** | 50 / 47 / 54 % |

313 s pour 100 annonces, 3,1 s chacune, **zéro panne**. Le mode extraction
fonctionne comme prévu : sur « with 22 and 24 floors » le modèle rend `[22, 24]`
et refuse de choisir — 100 % d'abstention sur les textes contradictoires, contre
93 % pour la regex.

**Mais les deux mesures qui décident vont dans l'autre sens.**

*Là où la regex parle et qu'une vérité existe* : regex **100 % sur les trois
champs**, IA 92 / 100 / 100 %. La regex ne se trompe JAMAIS quand elle parle —
ses 87 / 89 / 77 % ne sont pas des erreurs, ce sont des silences. L'IA ne la bat
nulle part, et fait moins bien sur les étages.

*Là où la regex se tait* : l'IA ose une valeur dans ~50 % des cas et **se trompe
dans 76 à 94 %**. Reproduction quasi exacte des 92 % du 2026-07-31, sur un jeu
entièrement différent et sur d'autres champs. Ce n'est donc pas un accident de
protocole : **le modèle ne supporte pas le vide.**

Le détail est plus dur encore que la moyenne. Sur le promoteur, l'IA récupère
**8 noms réels que la regex a manqués** — valeur authentique — mais produit
**26 inventions** pour les obtenir. Un gain pour trois erreurs, et aucun signal
pour les séparer : la `confidence` auto-déclarée est inutilisable (règle 5).

**Le recoupement par accord entre annonces est impossible ici** : le descriptif
DDproperty est du texte de PROJET, répété à l'identique. 3 625 annonces
d'immeubles multi-annonces se réduisent à **838 textes distincts** (37 annonces
de Belle Grand Rama 9 partagent UN texte). S'accorder avec soi-même sur le même
texte ne prouve rien.

**Verdict : l'IA locale n'est pas utilisable pour ce champ.** Non parce qu'elle
lit mal — elle lit mieux que la regex — mais parce qu'elle ne distingue pas
« j'ai trouvé » de « j'ai inventé ». Son seul emploi mesuré reste l'arbitrage
des doublons ambigus en mode extraction.

**Ce que l'exercice rapporte quand même**, et ce n'est pas rien : la regex écrite
comme référence du test alimente le référentiel `condos` **gratuitement et sans
erreur mesurée** — 1 045 immeubles vus, dont **512 avec la hauteur, 581 avec le
nombre de lots, 514 avec le promoteur**, et **zéro désaccord** entre textes d'un
même immeuble. À rapprocher des 3 551 immeubles du référentiel et du `year_built`
toujours à 0 côté serveur.

Corollaire de rangement : ce descriptif décrit le PROJET, pas le lot. Le stocker
par annonce le duplique 4,3 fois. Sa place est dans `condos`.

---

## 2026-08-03 — Ce qu'une capture d'écran a montré que les chiffres cachaient

### Le point de départ : une image, pas une requête

Demande d'une série d'images datées des cartes, une par édition mensuelle, pour
voir le **déplacement géographique** des tensions et des rendements — ce
qu'aucune colonne ne montre.

La capture sans écran fonctionne pour les **tableaux** (1920×1080, lisibles) et
**échoue pour les cartes** : MapLibre est en WebGL, et Chrome sans interface rend
un cadre vide — en-tête et panneau de calques dessinés, carte noire. Vérifié que
ce n'est pas le réseau : le serveur de tuiles répond en 0,28 s.
`--virtual-time-budget` fait avancer une horloge *virtuelle* qui dépasse les
téléchargements réels ; un budget plus long fait sortir Chrome sans rien produire.
La solution est Playwright, qui sait attendre l'événement `idle` de MapLibre —
**non installé, proposé, pas décidé**.

`ops/captures-carte.py` refuse et supprime toute image implausible : sans ce
garde-fou la série se remplirait d'images blanches en silence. Il n'a d'ailleurs
pas suffi — il a laissé passer une carte vide de 43 Ko, que seul un examen
visuel a démasquée. **Un seuil de taille ne remplace pas un regard.**

### Ce que l'image a révélé, et que j'ai d'abord mal interprété

Sur la capture du tableau des rendements, **« Bang Na » figurait deux fois** :
6,1 % sur 3 immeubles, 5,6 % sur 45. L'affichage retire le suffixe « District »,
donc les deux lignes sont identiques à l'œil.

**J'ai conclu à un doublon de nom. C'était faux.** Les coordonnées le prouvent :
les 27 annonces « Bang Na » sont toutes à **13,6578 / 100,6029 — Sukhumvit 107,
secteur Bearing**, en province de **Samut Prakan**, au-delà de la limite de
Bangkok. Elles ne sont pas mal nommées : elles sont **hors périmètre**, et leurs
sources les nomment correctement. Idem pour « Bang Phli » (14), « Pak Kret » (3),
« Bang Sao Thong » (2) et « Bearing » (1, même immeuble que les 27).

Le vrai défaut est donc autre, et plus gênant : **ni `study/run_study.py` ni
`lib/yields.ts` ne restreignent le classement aux 50 quartiers**. Toute chaîne
présente dans `khet` produit une ligne. Des annonces qui ne sont pas à Bangkok
apparaissaient dans un classement des quartiers de Bangkok, sous un libellé
visuellement confondu avec un vrai quartier.

Septième fois cette semaine que ma conclusion précédait ma mesure.

### Ce qui a été corrigé

**À l'écriture** — `KhetMatcher.canoniser()` : quand le point-dans-polygone
échoue, le libellé de la source est confronté aux 50 noms de référence au lieu
de passer tel quel. C'est ce passage sans contrôle qui créait les vraies
variantes de suffixe. Sans lui le défaut se reproduirait : une variante
« Huai Khwang » a encore été écrite le jour même.

**Sur l'existant** — `ops/corriger-khet.py`, où **les coordonnées tranchent, pas
le texte** : on recalcule le point-dans-polygone et on ne renomme que si le point
désigne effectivement un quartier. Résultat : **6 corrections réelles**, 48
annonces reconnues hors Bangkok et laissées intactes, 4 sans coordonnées
signalées sans être touchées. Une correspondance de chaînes n'est pas une preuve
— c'est elle qui avait créé le problème.

**Dans l'étude** — filtre de périmètre sur les 50 quartiers, lus **depuis le
GeoJSON** et non recopiés.

### Trois corrections de `study/run_study.py`

1. **Lecture de `listings_sane`** au lieu de `listings` brut. L'étude portait une
   TROISIÈME définition des bornes (loyer plafonné à 200 000 au lieu de 500 000,
   aucun plancher, aucune borne de surface). ⚠ Mesuré avant de corriger : sur
   36 quartiers, **un seul** bouge, de **+0,5 %**. La double médiane par immeuble
   absorbe ces valeurs. C'était un piège de maintenance, **pas** une erreur de
   publication — j'avais d'abord annoncé un biais « là où c'est le plus scruté »,
   sans l'avoir mesuré.

2. **Refus de produire une évolution vide.** Les éditions du 6 et du 9 juillet
   portaient des instantanés **identiques au chiffre près** — mêmes totaux,
   48 quartiers sur 48 égaux. Aucun scrap entre les deux. Le rapport affichait
   « Δ +0.0 % » partout, ce qui se lit comme une stabilité du marché. La section
   rend désormais un avertissement explicite.

3. **Vie médiane plafonnée à la cadence.** Six quartiers sur huit affichaient
   exactement **4 jours** — l'intervalle entre deux scraps. La mesure ne résout
   rien sous sa propre cadence ; elle s'affiche maintenant `≤ 4` avec l'explication.

`config_version` passe de 1 à **2** : c'est ce qui tracera la rupture de série.

### L'incident que j'avais qualifié d'hypothétique s'est produit — et je l'ai causé

Hier soir j'ai écrit un verrou d'instance unique (`agents/core/gpu.Verrou`) en le
documentant comme **« une précaution, pas la correction d'un incident »** : j'avais
d'abord cru observer deux exemplaires d'un test en concurrence, c'était en réalité
la chaîne lanceur/interpréteur du venv.

Le 2026-08-03, l'incident a eu lieu pour de bon. Après avoir corrigé un conflit de
type (SQLite range 0/1 là où Postgres attend un booléen), j'ai relancé
`ops/remonter-local.py` **sans arrêter le premier exemplaire**. Les deux ont écrit
en concurrence sur la production :

    essai 1 : 4 866 créations, 850 mises à jour, 16 990 ERREURS
    essai 2 : reprend l'intégralité des 19 904 annonces, correctement

Pas de dommage durable — les deux écrivaient par `upsert`, et le second passage
réécrit tout avec les bonnes valeurs. Le coût est 16 990 écritures perdues et une
charge inutile sur Supabase. Mais **rien ne l'empêchait**, et c'est le point : le
verrou existait déjà, il n'était simplement pas branché là.

Corrigé — `remonter-local.py` prend `Verrou("remonter-local")` avant la première
écriture, après la sortie du mode à blanc (qui n'écrit rien et n'a pas à être
bloqué). Pas de `with` : le verrou est posé par le système sur un descripteur
ouvert, donc il se relâche seul à la mort du processus, plantage compris.

Enseignement : un garde-fou écrit et non branché ne protège de rien. J'avais
identifié le risque, construit l'outil, et omis de l'appliquer au seul endroit qui
allait en avoir besoin dans les vingt-quatre heures.

## 2026-08-05 — Cinquième source (LivingInsider), une source écartée après enquête (DotProperty), et le mécanisme T2 qui n'existait pas

**Contexte.** Une discussion WhatsApp avec un agent (Earn) a fait remonter
propertynetwork.asia comme source candidate. En creusant sa structure (aucune
liste publique, `robots.txt` en `Disallow: /` total), le fil a mené à identifier
que ce n'est pas un agrégateur mais un outil de partage client posé sur d'autres
plateformes (confirmé par Earn elle-même, puis vérifié empiriquement : l'id
`2280176` pointe vers exactement le même bien sur propertynetwork.asia et sur
propertyscout.co.th). Aucune donnée unique à en tirer — PropertyScout est déjà
une source active.

**Décision 1 — le ticket `watch-sources` dormant sur DotProperty (créé le
2026-08-01, jamais traité) a été rouvert, puis refusé après enquête.** Le
sondage automatique de `watch-sources` ne teste que HTTP/blob/robots/volume, pas
l'origine des données. Un échantillonnage manuel (90 annonces sur 3 pages
indépendantes, vente + location) a montré que **100 % des photos** viennent de
`cdn.fazwaz.com` / `img.fazwaz.com`. DotProperty Bangkok semble syndiquer FazWaz,
déjà scrapé — écrire l'adaptateur aurait dupliqué la couverture existante pour un
coût de scrape non négligeable (chaque fiche = 1 requête détail systématique).
Adaptateur **délibérément non écrit**. `agents/state/watch-sources/registre.json`
et le ticket lui-même portent la trace de cette correction ; la décision finale
(creuser une fraction non-FazWaz, ou clore) reste à trancher par un humain.

**Décision 2 — LivingInsider ajouté comme 5e source.** Vérifié indépendant
(images sur `www.livinginsider.com`, `sku` préfixé `LV`, aucun CDN
FazWaz/DDproperty/PropertyScout détecté), `robots.txt` quasi ouvert,
`sitemap-project.xml` dédié. Deux limites structurelles, documentées dans
`agents/skills/extract-livinginsider/SKILL.md` :
- **Aucune dédup incrémentale possible** : la page de liste ne porte que des
  URLs nues (pas de prix), contrairement aux 4 sources existantes — chaque scan
  revisite donc TOUTES les fiches déjà connues, indéfiniment. `max_pages` posé
  bas (25, contre 150 pour FazWaz/DDproperty/PropertyScout) en attendant une
  mesure réelle de durée de run.
- **Flux national, pas de filtre géo à la source.** Le format d'adresse n'est
  pas homogène : certaines fiches disent proprement « … District, Bangkok »,
  d'autres non (texte thaï/anglais mêlé, mot "District" absent). Premier essai
  du filtre (regex stricte seule) : **1 fiche retenue sur 20**, alors que 13
  des 19 écartées étaient de vraies fiches Bangkok mal formatées — le filtre
  cassait plus qu'il ne triait. Corrigé par un second motif de repli sur le
  code postal (« … Bangkok 10xxx »), qui prend les 2 derniers mots avant le
  code postal comme meilleure estimation de district. Retest sur les mêmes 20
  fiches : **18/20 retenues**, 0 faux positif observé sur les 17 fiches
  vérifiées une à une (dont 3 réellement hors Bangkok, toutes correctement
  écartées — Samut Prakan et Chon Buri ont des codes postaux hors plage
  10xxx). Le nom de district déduit par repli n'est pas toujours canonisable
  (ex. "Nuea Vadhana" au lieu de "Watthana District") — `--geocode` est de fait
  indispensable ici, pas optionnel comme pour les autres sources.

**Décision 3 — le mécanisme T2 n'existait pas.** `agents/README.md` décrit
depuis le début « une session Claude planifiée [qui] draine » `agents/queue/`.
Vérification : aucune tâche planifiée ne le fait — le rapport mensuel
(`rapport-mensuel-lowi-bkk`) ne couvre que l'étude de marché, jamais la file de
tickets. `agents/queue/done/` était vide depuis la création du système le
2026-07-31. Six tickets (5 `agent_muet` sévérité haute + le `nouvelle_source`
DotProperty) se sont accumulés sans jamais être traités. Tâche planifiée locale
`drain-agent-queue-lowi-bkk` créée (quotidienne, ~08:38) pour combler ce vide —
même limite que les tâches Windows de juillet, en moins grave : elle ne tourne
que si l'app est ouverte à l'heure dite (rattrape au lancement suivant sinon),
contrairement à la tâche Windows `LowiBKK-Agents` qui tourne app fermée. Premier
passage prévu le 2026-08-06 matin.

**Limite connue.** Aucun run de production `livinginsider` n'a encore eu lieu —
tout ce qui précède vient de runs de test isolés (`LOWI_OUTPUT_DIR` dédié,
`--limit`, SQLite local, jamais Supabase). Les bandes de `agents/agents.json`
pour `extract-livinginsider` sont provisoires. Travail fait sur la branche
`agents/new-sources-livinginsider-dotproperty`, jamais sur `main`.

## 2026-08-06 (suite) — Vente/location le même jour, backup avant/après cycle, DotProperty tranché

**Contexte.** Anthony a demandé trois choses dans la foulée de ce qui précède :
(1) revenir à `agents/orchestrator.py` + `agents.json` plutôt que
`superviseur.py`/`tests-scrap` — abandonné le même jour, voir plus haut ;
(2) que vente ET location tournent le même jour, chaque source enchaînant
elle-même sa passe location dès que sa passe vente finit, sans attendre les
autres sources ; (3) un backup local avant ET après chaque cycle de 4 jours,
pas seulement la purge hebdomadaire existante.

**Décision 1 — fin de l'alternance sale/rent par jour.** L'ancien
`current_lane()` alternait vente et location sur des jours différents (`day %
4 < 2`) : concrètement, une catégorie restait périmée 4 jours de plus que
nécessaire à chaque cycle, pour aucune raison technique — c'était une reprise
telle quelle des anciennes tâches Windows (`ScrapVente`/`ScrapLocation`), pas
un choix motivé. `current_lane()` simplifié à `daily`/`weekly`. Chaque source
qui sépare `--deal-type` (FazWaz, DDproperty) enchaîne maintenant sale PUIS
rent PUIS sa passe corridors via des étapes `then` successives dans
`agents.json` — les extracteurs restant parallèles ENTRE eux (le
`ThreadPoolExecutor` existant), la source la plus rapide démarre sa location
sans attendre les autres, exactement le comportement demandé.

**Défaut trouvé en l'implémentant, pas en le pensant.** Avec plusieurs étapes
`then`, `run_agent()` n'écrivait qu'UNE clé `then_exit` dans les métriques —
la deuxième étape écrasait le résultat de la première, qui disparaissait sans
trace. Pire : le statut global de l'agent (`ok`/`failed`) ne regardait QUE le
code retour de la commande PRINCIPALE. Une passe vente réussie suivie d'une
passe location qui plante aurait été journalisée `ok` — la panne aurait été
silencieuse. Corrigé : chaque étape (principal + tous les `then`) s'exécute
indépendamment de l'échec des précédentes (une passe vente cassée ne doit pas
empêcher la tentative de la passe location), ses métriques sont conservées
sous une clé distincte (`metrics.etapes[]`), et le statut global agrège tout.
Validé par un test synthétique (3 étapes, la 2e échoue exprès) avant de faire
confiance au vrai pipeline : statut global bien `failed`, les 3 étapes
s'exécutent quand même, rien n'est perdu dans les métriques.

**Décision 2 — backup avant/après, pas seulement hebdomadaire.** Le seul
filet de sécurité existant (`agent storage`, `ops/sync_supabase_local.py
--prune`) tournait une fois par semaine — un retour en arrière après un cycle
de scrap raté se serait fait sur une sauvegarde vieille de plusieurs jours.
Deux nouveaux agents T0, cadence 4 jours (alignée sur le cycle
d'extraction) : `backup-avant-cycle` (nouvelle famille `Prelude`, exécutée en
premier, séquentielle, avant tout extracteur — `run_lane()` modifié pour
supporter cette phase) et `backup-apres-cycle` (dernier avant `overseer`).
Les deux appellent `ops/sync_supabase_local.py` SANS `--prune` — réplique
seule, jamais destructif, et **sans** le garde-fou `requires_healthy` de
`storage` : une sauvegarde de ce qui a réussi vaut mieux qu'aucune sauvegarde,
même si une extraction a échoué en amont. Testé réellement (pas en dry-run) :
`archive/lowi-archive.db` passe de 45 159 lignes périmées (2026-08-03) à
555 691 lignes fraîches sur 7 tables, en un seul run.

**Décision 3 — DotProperty tranché, pas juste suspecté.** Le ticket ouvert le
2026-08-01 restait sur une investigation manuelle ponctuelle (90 annonces,
un seul passage). Écrit `ops/verif-dotproperty.py` : 3 sondages de la page de
LISTE uniquement (pas de fiche détail, pas d'écriture DB — juste le
hébergeur des images), enregistrés dans un état persistant, avec conclusion
automatique au 3e run. Plutôt que d'attendre 3 cycles réels (~12 jours), les
3 runs ont été déclenchés à la main ce soir pour valider le mécanisme
complet : **180 annonces échantillonnées sur 3 runs indépendants, 100% des
images chez `cdn.fazwaz.com`/`img.fazwaz.com`** — verdict
`resyndication_confirmee`. Le ticket est fermé et déplacé dans
`agents/queue/done/`, le registre `watch-sources` mis à jour, un mail de
conclusion déposé dans `agents/queue/mail/` (à drainer par
`drain-agent-queue-lowi-bkk`, mis à jour le même jour pour créer des
brouillons Gmail plutôt que d'envoyer directement — plus sûr pour une
dispatch nocturne sans supervision).

**Limite connue.** `verif-dotproperty` reste dans `agents.json` (cadence 4 j)
mais ne fait plus rien après ces 3 runs (`etat.json` déjà à 3/3) — laissé en
place comme trace, pas retiré, aucune action requise. Travail fait
directement sur `main` (contrairement au reste de la nuit) : cette
infrastructure doit être active pour le cycle planifié de demain 01:00, la
laisser sur une branche l'aurait rendue invisible à la tâche Windows.

## 2026-08-06 (suite 2) — Correction : "backup avant/après" voulait dire vérifier, pas resynchroniser

Anthony a repris ma lecture du mot "backup" ci-dessus : `backup-avant-cycle`
(v1) resynchronisait `archive/lowi-archive.db` à l'aveugle à chaque cycle,
sans jamais se demander si le backup précédent avait déjà fait le travail. Ce
n'était pas ce qui était demandé — la demande portait sur une VÉRIFICATION du
backup précédent, avec rattrapage seulement "à défaut" (si la vérification
échoue), et un agent dédié à la LECTURE du backup pour en juger l'intégrité,
pas juste relancer la sync et espérer.

`ops/verifie-backup.py` remplace `backup-avant-cycle` : quatre vérifications
(`PRAGMA integrity_check` sur le SQLite local, tables attendues présentes,
volume archivé >= 90 % du volume Supabase, dernier `backup-apres-cycle` 'ok'
dans le ledger et pas plus vieux que cadence+1 jour) — et ne relance
`ops/sync_supabase_local.py` QUE si l'une d'elles échoue. `backup-apres-cycle`
(fin de cycle, inconditionnel) est inchangé.

**Testé réellement**, pas en dry-run : `backup-apres-cycle` n'ayant encore
jamais tourné via l'orchestrateur (créé ce soir), le check #4 a correctement
détecté "aucun backup-apres-cycle 'ok' trouvé" et déclenché un rattrapage —
qui a réussi (archive passée à 555 814 lignes). Revalidé une seconde fois en
appelant `agents/orchestrator.py run verifie-backup` directement (pas juste le
script), pour prouver l'intégration réelle, pas seulement la logique isolée.

## 2026-08-11 — Revue algo deals/yields/tension : 3 propositions sur 4 écartées

Un retour externe (analyse mathématique du code de `lib/deals.ts`,
`lib/yields.ts`, `lib/tension.ts`) proposait 4 changements. Vérification
contre le code et les données réelles avant d'implémenter quoi que ce soit —
trois écartés, un retenu.

**Écarté 1 — prime d'étage dans `deals.ts`.** Le taux proposé (+0,5 %/étage
au-dessus du 5e) est une hypothèse non mesurée sur les données du projet, pas
un chiffre calibré. `d_etage` (comme les autres champs descriptifs) n'est
renseigné que sur une fraction des annonces et n'est pas rétroactif (cf.
2026-08-02 ci-dessus, couverture 24-78 % selon le champ). Ajouter un
ajustement de prix basé sur un taux deviné aurait introduit de la fausse
précision dans le classement des décotes — exactement ce que le projet évite
depuis le revirement sur `posted_at` (2026-08-02 également, plus haut).
Alternative retenue : aucune, reporté à plus tard si besoin de mesurer
d'abord la relation réelle prix/étage sur l'échantillon disponible.

**Écarté 2 — rendement net via forfait CAM fee dans `yields.ts`.**
`d_cam_fee_thb` n'est connu que sur 24 % des annonces. Appliquer un forfait
(50 THB/m²/mois) aux 76 % restantes aurait fabriqué une donnée plutôt que de
la mesurer, sur une métrique (Gross Yield) déjà fiable et largement utilisée
en aval (`/rendements`, `study/run_study.py`). Non implémenté.

**Écarté 3 — momentum en EMA dans `tension.ts`.** L'idée ("donner plus de
poids aux instantanés récents") est légitime, mais l'extrait fourni calcule
une moyenne mobile exponentielle sur les NIVEAUX (`activeCount`/prix), pas
une pente. Or `stockTrend` et `priceMomentum` sont utilisés dans tout le
reste du calcul comme une pente SIGNÉE (régression `slope()`, rang centile,
sens tendu/mou) — remplacer `slope()` par cet EMA aurait changé la sémantique
des deux composantes sans que rien d'autre dans `tension.ts` ne le sache.
Par ailleurs l'historique de `khet_snapshots` par quartier reste court
(démarré le 2026-07-04), donc peu de points pour qu'un rétrécissement
exponentiel change grand-chose pour l'instant. Une alternative correcte
existe (régression pondérée / WLS, qui reste une vraie pente) mais n'a pas
été demandée — non implémentée non plus.

**Retenu — score de confiance sur les décotes de `deals.ts`.** Seul
changement fait : exposer une info que le code connaissait déjà en interne
(le nombre `n` de comparables derrière `marketDiscountPct`/`compareBasis`)
sans introduire de nouvelle donnée ni de seuil deviné. `baselineForGroup` et
`baselineFor` renvoient désormais `n` en plus de la valeur ; `confidenceOf(n)`
classe en low/medium/high en réutilisant les constantes déjà en place
(`MIN_COMPARABLES = 3` comme plancher, `BASELINE_N = 10` comme palier
"high"), pas de nouveau nombre inventé. Côté UI (`DealsView.tsx`), un point
coloré accolé à la cellule St./Condo (pas de nouvelle colonne, cohérent avec
les commits récents de compaction du tableau).

**Défaut trouvé en vérifiant, pas en l'écrivant.** Première version : le
point de confiance était toujours accolé à la cellule "Condo", même quand le
classement (`marketDiscountPct`) provenait en réalité du repli RUE
(`compareBasis === "street"`) — visuellement il apparaissait à côté d'un
"—" dans la colonne Condo, ce qui aurait fait croire à une confiance sur une
valeur non affichée. Corrigé en conditionnant l'affichage du point à
`r.compareBasis` (point sur "St." si le calcul vient de la rue, sur "Condo"
sinon) ; revérifié en relisant le texte de la page rendue (`/deals`, mode
Best discounts) plutôt qu'en supposant que le premier jet suffisait.
`npm run typecheck` et `npm test` passent, aucun test dédié à `deals.ts`
n'existait avant (aucun ajouté ici, changement d'affichage pur).
