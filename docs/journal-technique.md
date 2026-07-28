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
