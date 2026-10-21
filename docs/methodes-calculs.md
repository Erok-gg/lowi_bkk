# Méthodes de calcul — référence

> **Ce que porte ce fichier** : chaque grandeur affichée par le site ou par les
> études, sa formule, la raison du choix, les constantes de réglage et leur
> justification chiffrée. Il répond à « pourquoi ce chiffre est calculé ainsi »
> — pas à « comment le code est écrit ».
>
> **Règle d'or de ce dépôt appliquée ici** : chaque méthode distingue ce qui est
> **mesuré** de ce qui est **supposé**. Quand une alternative a été écartée, la
> mesure qui l'a écartée figure. Quand une limite subsiste, elle est nommée.
>
> **Statut** : document vivant, mis à jour quand une méthode change. L'historique
> daté des changements de méthode reste au [journal technique](journal-technique.md).

---

## 0. Le préalable qui conditionne tout

**Les prix sont des prix AFFICHÉS, pas des prix de transaction.** Aucune source
publique thaïlandaise ne donne le prix réellement payé. Toutes les grandeurs
ci-dessous mesurent donc **la demande des vendeurs**, pas le marché conclu.

Conséquence méthodologique, assumée partout : **les valeurs servent au
classement relatif** (ce quartier est-il plus cher que celui-là ? ce bien est-il
sous le prix de son immeuble ?), **jamais à l'estimation absolue**. Un « prix/m²
médian de 118 826 THB » ne dit pas ce que vaut un bien : il dit où se situe le
milieu des demandes affichées.

---

## 1. Périmètre commun — bornes de plausibilité

**Toute** statistique se calcule sur le périmètre assaini. Aucun agrégat ne doit
refiltrer à la main.

| Grandeur | Min | Max |
|---|---|---|
| Prix de vente | 800 000 THB | 100 000 000 THB |
| Loyer mensuel | 3 000 THB | 500 000 THB |
| Surface | 15 m² | 500 m² |

**Justification de chaque borne** (`lib/market-bounds.ts`) :

- **Vente sous 800 k** : quasi toujours un loyer mal classé en vente, ou un prix
  « à partir de » tronqué.
- **Vente au-dessus de 100 M** : penthouses et villas hors marché comparable,
  qui écrasent la médiane de leur quartier.
- **Loyer sous 3 000** : prix journalier, ou chambre en colocation.
- **Loyer au-dessus de 500 000** : villa, ou prix de vente saisi dans le champ
  loyer.
- **Surface sous 15 m²** : saisie en `wah²`, ou zéro.
- **Surface au-dessus de 500 m²** : surface du **projet** saisie dans le champ du
  lot (relevé réel : un 1BR annoncé à 3 757 m² au Tempo Ruamrudee).

**Pourquoi une source unique.** Ces bornes ont existé en trois exemplaires qui
s'ignoraient. Mesuré le 2026-07-28 : les 114 annonces au-dessus de 100 M et les
68 sous 800 k étaient exclues du tableau de vente mais **comptaient toujours**
dans la carte, les rendements et la tension. La vue `opportunites` affichait en
tête des locations mal classées en vente, à −100 % de « décote ».

**Deux exemplaires à maintenir alignés**, et c'est structurel :
`lib/market-bounds.ts` (TypeScript) et la vue SQL `listings_sane`. Changer l'un
sans l'autre recrée exactement le défaut ci-dessus.

**Un bien hors bornes n'est pas supprimé** : il reste en base et reste
consultable. Il est seulement écarté des agrégats — une anomalie de source doit
rester visible.

**Surface inconnue ≠ aberrante** : une annonce sans surface reste dans les
statistiques de prix, elle est seulement privée de celles au m².

---

## 2. Normalisation du nom d'immeuble

Le condo est l'unité d'agrégation de presque tout ce qui suit. Il faut donc que
« The Line Sukhumvit 71 », « the line sukhumvit71 » et « The Line Sukhumvit 71 —
Building A » se regroupent.

`lib/condo-name.ts` est l'**exemplaire unique** côté TypeScript. Il était
auparavant dupliqué dans `yields.ts` et `cross-match.ts`, et **absent** de
`tension.ts` — trois regroupements différents pour la même notion.

> ⚠ **Il diverge de `_norm_condo` (Python)**, qui sert à fabriquer les
> `unit_key` des cohortes. **Ne jamais comparer un regroupement TS à un
> `unit_key`** : les deux ne partitionnent pas identiquement.

---

## 3. Prix/m² par quartier — double médiane par condo

### Le problème

On ne connaît ni l'année de construction, ni l'étage, ni la vue, ni le standing.
Une médiane simple des annonces d'un quartier mélange donc un immeuble de 1985
et une livraison 2025, et se fait dominer par l'immeuble qui a le plus
d'annonces (un immeuble à 80 lots pèse 80 fois un immeuble à 1 lot).

### La méthode

```
1. Pour CHAQUE condo    → médiane du prix/m² de ses annonces
                          (l'étage et la vue deviennent du bruit écrasé)
2. Pour CHAQUE quartier → médiane des médianes-condo
                          (1 immeuble = 1 voix)
```

**Ce que ça neutralise** : le condo *encapsule* vétusté, standing,
micro-localisation et amenities. Agréger par condo d'abord fait sortir ces
facteurs du calcul sans avoir à les mesurer — ce qui est heureux, puisque
`year_built` est renseigné **0 fois**.

### Réglages

| Constante | Valeur | Justification |
|---|---|---|
| Strate par défaut | **0–1BR** | Segment commun et liquide du marché BKK. Comparer les quartiers **à panier constant** évite qu'un quartier paraisse cher parce qu'il vend surtout des 3BR. Toggle Studio–1BR / 2BR / 3BR+ / All. |
| Winsorisation | **p5–p95**, si n ≥ 20 | Écrête les extrêmes résiduels sans supprimer d'observation. Sous 20 valeurs, écrêter retirerait de l'information réelle. |
| `LOW_SAMPLE_CONDOS` | **20** | Sous 20 condos distincts d'un côté, la ligne porte un badge « échantillon faible ». On affiche quand même : masquer priverait les quartiers périphériques de toute donnée. |

---

## 4. Rendement locatif brut

### Méthode retenue — « within-condo »

```
rendement d'un condo  = (loyer/m² médian DU MÊME immeuble × 12)
                        ÷ prix/m² médian DU MÊME immeuble

rendement du quartier = médiane de ces rendements within-condo
```

**Pourquoi le même immeuble des deux côtés.** L'âge, le standing et
l'emplacement apparaissent au numérateur **et** au dénominateur : ils se
simplifient dans la division. Comparer le loyer d'un immeuble neuf au prix d'un
immeuble ancien du même quartier produirait un rendement qui ne mesure que
l'écart de vétusté entre les deux.

**Ce qui rend la méthode applicable** : mesuré le 2026-07-04, **1 154 condos ont
vente ET location actives, soit 81 % du stock actif**. La base appariée n'est
pas marginale.

### Repli, et son marquage

| Constante | Valeur | Effet |
|---|---|---|
| `MIN_PAIRED_CONDOS` | **5** | Sous 5 immeubles appariés dans le groupe, le within-condo n'est pas fiable → repli sur le **ratio des médianes du quartier**, et la ligne est marquée **†** (`yieldMethod: "ratio"`). |

Le marquage n'est pas cosmétique : les deux méthodes ne mesurent pas la même
chose, et la seconde réintroduit précisément le biais de composition que la
première élimine.

---

## 5. Recoupement vente ↔ location de la même unité

Sert à afficher un **rendement annuel réel** sur une ligne de tableau (page
`/for-sale` : colonnes *Monthly rent* + *Annual yield* ; page `/to-rent` :
*Sale price* + *Annual yield*).

**Critère d'appariement** (`lib/cross-match.ts`) : même condo normalisé **+**
même khet **+** même nombre de chambres **+** surface à **±7 %** quand les deux
surfaces sont connues.

```
rendement annuel réel = loyer mensuel × 12 ÷ prix de vente
```

**Pas de fusion.** Les deux annonces restent deux annonces distinctes ; on ne
crée pas d'enregistrement combiné. Un appariement est une **hypothèse
d'identité**, pas un fait établi : le fusionner détruirait de l'information si
l'hypothèse est fausse.

**Pourquoi ±7 %** : les surfaces annoncées d'un même lot varient d'une source à
l'autre (arrondis, surface brute contre surface nette). Une tolérance nulle
raterait la plupart des vrais appariements ; une tolérance large apparierait des
lots voisins mais différents.

---

## 6. Décote et « bonnes affaires »

`lib/deals.ts` calcule, pour chaque bien en vente, trois grandeurs :

1. **Décote marché** — prix/m² sous la médiane des comparables.
2. **Décote temporelle** — baisse de prix depuis le premier relevé.
3. **Rendement estimé** — loyer médian comparable ÷ prix.

### La cascade de comparaison, et pourquoi le quartier en est exclu

```
1er choix : MÊME CONDO + même tranche de chambres
   ↓ si moins de MIN_COMPARABLES pairs
2e choix : MÊME RUE + même tranche de chambres
   ↓
(le KHET n'est PLUS un niveau de comparaison)
```

**Le khet a été retiré délibérément** : trop grossier. Un même quartier mélange
des rues et des immeubles de standings très différents — une « décote » calculée
sur cette base mesure surtout l'écart entre deux rues, pas une affaire.

| Constante | Valeur | Rôle |
|---|---|---|
| `MIN_COMPARABLES` | **3** | Sous 3 pairs (le bien lui-même exclu), le groupe est trop petit pour servir de référence → on descend d'un cran. |
| `BASELINE_N` | **10** | La référence est la **moyenne des ~10 valeurs médianes**, pas le point médian seul. |
| Tranches de chambres | 1, 2, 3, **4+** | Au-delà de 4, l'effectif ne permet plus de distinguer. |

### `medianAvg` — pourquoi pas la médiane simple

```
medianAvg(valeurs, n) = moyenne des ~n valeurs centrées sur la médiane
```

Un point médian isolé peut être lui-même aberrant, surtout sur de petits
groupes. Moyenner une fenêtre étroite autour du centre **lisse ce point unique**
tout en restant insensible aux extrêmes (contrairement à une moyenne complète).
La fenêtre se réduit naturellement à ce qui est disponible ; 0 valeur → `null`,
jamais 0.

---

## 7. Indice de tension par quartier

Indice composite **0–100** (plus haut = plus tendu). Les quatre signaux sont
normalisés par **rang centile entre quartiers** — robuste aux unités et aux
extrêmes, et seul moyen de combiner des grandeurs hétérogènes.

| Signal | Poids | Lecture |
|---|---|---|
| **Absorption** | **35** | Vitesse d'écoulement. Court = tendu. |
| **Pression vendeuse** | **25** | Actives **par immeuble**. Beaucoup = marché mou. |
| **Tendance stock** | **20** | Pente du nombre d'actives. En baisse = tendu. |
| **Momentum prix** | **20** | Pente du prix/m² médian. En hausse = tendu. |

### Le défaut fondateur : l'indice mesurait la petitesse du marché

La composante d'origine, « rareté », valait `100 − rang(nombre d'annonces
actives)` : **peu d'annonces = tendu, par construction**. Or 25 des 55 quartiers
ont moins de 20 annonces actives et obtenaient donc mécaniquement le score
maximal. La périphérie ressortait plus tendue que le centre alors qu'elle n'a
tout simplement presque pas de condos (Taling Chan : **2 annonces sur 6
immeubles**). L'indice confondait **taille** et **tension**.

Remplacée par la **pression vendeuse**, insensible à la taille du marché et
directement interprétable : *parmi les immeubles où quelqu'un vend, combien de
vendeurs simultanés ?*

### Le piège du dénominateur (corrigé le même jour)

Le dénominateur comptait les immeubles sur **toutes** les annonces, délistées
comprises, alors que le numérateur ne compte que les **actives**. Périmètres
mélangés : un quartier à fort churn accumule des noms d'immeubles au
dénominateur, sa pression s'effondre et sa tension grimpe.

**Mesuré** : Vadhana **6,92** sur périmètre actif contre **4,61** sur
l'historique (**−33 %**) ; Khlong Toei **5,52** contre **3,32** (**−40 %**). Le
biais n'est pas uniforme : il déforme le **classement**, pas seulement l'échelle.

> La table `condos` n'aurait rien réglé : elle est peuplée depuis toutes les
> annonces sans filtre de statut, elle porte donc le même biais.

**Dénominateur retenu** : immeubles distincts parmi les annonces **actives**,
nom normalisé.

### Garde-fous

| Constante | Valeur | Rôle |
|---|---|---|
| `SHRINK_K` | **20** | Rétrécissement vers la médiane du marché, poids `n/(n+K)`. Un quartier à 5 annonces ne flotte plus librement. |
| `MIN_ACTIVE_TO_PUBLISH` | **10** | Sous 10 actives, le score vaut **`null`**. Mieux vaut « données insuffisantes » qu'un chiffre dénué de sens. |
| `MIN_DELISTINGS` | **3** | Minimum de disparitions pour un time-on-market fiable. |
| `MIN_SNAPSHOTS` | **3** | Minimum de points pour une pente fiable. |
| `MIN_CONDOS` | **3** | Minimum d'immeubles pour une pression vendeuse interprétable. |

Formule du rétrécissement : `(n × score + K × médiane_marché) / (n + K)`.

### Absorption — pourquoi l'historique ancien est écarté

Jusqu'au **2026-07-28**, une annonce était délistée dès **la première absence**
d'un scan. Le time-on-market mesuré valait donc… **la cadence de scan** : 6,9 j
identiques à Vadhana, Khlong Toei et Sathon. Ce n'était pas une mesure du
marché, c'était une mesure de notre propre calendrier.

`DELISTING_FIX_DATE = "2026-07-28"` écarte cet historique **par défaut**. Tant
qu'il n'y a pas assez de disparitions postérieures, l'absorption se replie sur
**l'âge des annonces actives** — moins riche, mais pas faux. Le time-on-market
revient de lui-même à mesure que les scraps post-correctif s'accumulent.

### Momentum prix — médiane, jamais moyenne

Mesuré sur **2 121 instantanés** : la moyenne court **16 % au-dessus** de la
médiane (137 750 contre 118 826 THB/m²), tirée par les penthouses. Repli sur la
moyenne uniquement quand la médiane manque (instantanés SQLite hérités).

---

## 8. Cohortes `unit_key` — mesurer l'écoulement malgré les republications

**Le problème** : une annonce retirée puis republiée ressemble à une vente
suivie d'une nouvelle mise en marché. Un time-on-market naïf compte alors deux
courtes durées au lieu d'une longue, et conclut à un marché rapide.

**La parade** : suivre non pas l'annonce mais la **cohorte**.

```
unit_key = immeuble × chambres × tranche de 5 m² × type de transaction
```

`cohort_snapshots` enregistre le stock actif par cohorte à chaque scan. Une
republication reste dans **la même** cohorte : la série mesure l'écoulement réel.

> ⚠ **Piège d'arrondi, corrigé.** Python arrondissait la tranche en **arrondi
> bancaire**, SQL en **half-up** : un même lot tombait tranche 40 s'il venait du
> scrape et 45 s'il venait du backfill SQL — **deux cohortes pour une seule
> unité**. Convention SQL (half-up) adoptée des deux côtés.

---

## 9. Ce qu'on ne calcule PAS, et pourquoi

Cette section vaut autant que les précédentes : elle évite de refaire trois fois
la même enquête.

### `posted_at` n'est pas une date de mise en ligne — substitution ANNULÉE

Le champ existe (DDproperty), et il était tentant de l'utiliser à la place de
`first_seen` pour mesurer le temps sur le marché. **Mesuré le 2026-08-02 :
l'écart médian `first_seen − posted_at` vaut −16 jours** — l'annonce est vue
seize jours *avant* sa publication déclarée. Le champ se comporte comme une date
de **remontée en tête de liste**.

Le substituer **raccourcirait** artificiellement le time-on-market et mesurerait
**l'assiduité des agents à rafraîchir leurs annonces**, pas la liquidité.

S'y ajoute un biais de composition rédhibitoire : le champ n'existe que sur
DDproperty, dont la part du stock actif va de **3 % à 89 % selon le quartier**.
Une métrique mixte varierait avec la composition des sources, pas avec le marché.

**`first_seen` reste la base unique** : son biais est uniforme sur les cinq
sources, donc comparable entre quartiers. Le correctif de l'absorption reste les
cohortes.

### Les « 1 399 doublons » n'en étaient pas

Inspection : identifiants d'unité FazWaz **consécutifs** (u6548791…u6548800) =
lots distincts versés en lot par une agence, et **simultanément actifs**. Une
dédup aurait effacé de l'offre réelle. Rien à voir avec la republication
séquentielle que traitent les cohortes.

### Grandeurs non calculables faute de donnée

| Grandeur | Obstacle |
|---|---|
| Décote par vétusté | `year_built` renseigné **0 fois** |
| Statistiques par quota étranger | renseigné sur **1,2 %** des annonces |
| Prix de transaction | aucune source publique |

Les annonces de réseaux sociaux vivent dans `social_leads`, **table séparée à
dessein** : déclaratif non vérifié, qui ne doit pas contaminer les statistiques
de marché.

---

## 10. Récapitulatif des constantes

| Constante | Valeur | Fichier |
|---|---|---|
| `SALE_MIN` / `SALE_MAX` | 800 k / 100 M THB | `lib/market-bounds.ts` + vue `listings_sane` |
| `RENT_MIN` / `RENT_MAX` | 3 k / 500 k THB | idem |
| `AREA_MIN` / `AREA_MAX` | 15 / 500 m² | idem |
| `MIN_PAIRED_CONDOS` | 5 | `lib/yields.ts` |
| `LOW_SAMPLE_CONDOS` | 20 | `lib/yields.ts` |
| `WINSOR_MIN_N` | 20 | `lib/yields.ts` |
| `AREA_TOL` | 0,07 (±7 %) | `lib/cross-match.ts` |
| `BASELINE_N` | 10 | `lib/deals.ts` |
| `MIN_COMPARABLES` | 3 | `lib/deals.ts` |
| `WEIGHTS` | 35 / 25 / 20 / 20 | `lib/tension.ts` |
| `SHRINK_K` | 20 | `lib/tension.ts` |
| `MIN_ACTIVE_TO_PUBLISH` | 10 | `lib/tension.ts` |
| `MIN_DELISTINGS` / `MIN_SNAPSHOTS` / `MIN_CONDOS` | 3 / 3 / 3 | `lib/tension.ts` |
| `DELISTING_FIX_DATE` | 2026-07-28 | `lib/tension.ts` |

### Deux alignements à ne jamais rompre

1. **`lib/market-bounds.ts` ↔ vue `listings_sane`** — mêmes bornes des deux
   côtés, commentées des deux côtés.
2. **Arrondi de tranche Python ↔ SQL** — half-up partout.

### Une duplication connue, non résolue

La logique métier est **dupliquée** entre `study/run_study.py` (Python, pour les
études datées) et `lib/yields.ts` (TypeScript, pour le site). Les deux doivent
évoluer ensemble ; rien ne le vérifie automatiquement à ce jour.

## 11. Annonces Facebook — doublons, filtres, comparaison (ajouté le 2026-09-30)

Code : `scraper/social_calibrage.py`, lancé après chaque chargement par
`load_social_leads.py --sqlite`. Base séparée `social-leads.db` : ces
annonces n'entrent **jamais** dans les statistiques de marché (§ 1).

| Étape | Règle | Mesure qui la justifie (406 fiches, 30/09) |
|---|---|---|
| Doublon « même bien » | même immeuble × type × chambres, surface ±2 m², prix ±5 %, regroupement transitif ; la tête de groupe est la première vue | 119 lignes en trop (29,3 %). L'exact en donne 96 ; ±10 % en donnerait 132. Le plateau se situe vers ±2 m² / ±5 % |
| Hors bornes | bornes de § 1 (vente 800 k–100 M, loyer 3 k–500 k, surface 15–500) | 2 fiches |
| Loyer au m² aberrant | hors 150–2 000 THB/m² (médiane 657, p10–p90 392–1 029) | 3 fiches |
| Écart suspect | plus de ±40 % au marché de l'immeuble. **Drapeau seulement**, la fiche reste | 6 fiches |
| Sur les plateformes | même immeuble × chambres, surface ±7 % (tolérance de § 5), prix ±5 % | 183 / 230 (79,6 %). **Plafond** : deux unités jumelles se confondent. Selon la tolérance, de 144 à 202 sur 230 |
| Écart au marché | loyer au m² comparé à la médiane des annonces actives du même immeuble × chambres, dans les bornes, avec au moins 3 annonces | médiane 0,0 % (n = 183) ; exclusives −6,9 % (n = 18) |

Rien n'est supprimé : les lignes sont marquées (`dedup_of`,
`quality_flags`, `on_platforms`). Deux vues donnent le périmètre :
`social_leads_uniques` et `social_leads_exclusives`. Chaque exécution
archive ses paramètres, l'entonnoir du dernier chargement (motif de rejet
par fiche) et une **grille de sensibilité** des deux tolérances. Ces données
sont dans la table `calibration_runs` et dans
`scraper/output/social/calibrage/`. C'est là qu'on relit avant de changer
un seuil.

---

## 12. Scores de tension et de liquidité sur 100 — bilan acheteur (ajouté le 2026-10-17)

Code : `bilan_RE/tension/` (`coeur.py` pur et testé, `donnees.py` lecture SQLite, `liquidite.py`, `prix.py`). Config versionnée à part : `bilan_RE/tension/config.json` (`config_version` 1). Tests : `bilan_RE/tests/test_tension_score.py` (38 essais, données synthétiques). **Calcul mensuel** (décision utilisateur) : le rapport l'affiche, avec la date de fin de fenêtre.

### Pourquoi un score, et pas des « mois de stock »
Un nombre de mois de stock ne parle pas à un acheteur. En seuils absolus, il classerait de plus 35 districts sur 36 en « buyer's market » (mesuré le 2026-10-17). Le score se lit sur 100, avec **50 = un district typique de Bangkok sur 12 mois glissants**.

### L'unité : la cohorte
Groupe `unit_key` = même immeuble × chambres × tranche de 5 m² × type. Une cohorte **sort** quand elle est active en début de fenêtre, vide en fin de fenêtre, et que personne ne la repeuple dans les 14 jours suivants. Une republication devient invisible par construction : **72 % des retraits DDproperty sont des republications** (mesuré).

### Santé des sources, recalculée à chaque fenêtre
Une source est écartée si elle ne retire rien alors qu'elle a au moins 200 actives, si elle reste 5 jours ou plus sans retrait en fin de fenêtre, si son stock gonfle de plus de 50 % (recensement), ou par exclusion manuelle datée (LivingInsider depuis le 16/09, Nestopa). **Constat au 2026-10-17 : aucune fenêtre n'a ses deux grandes sources saines.** Au 12/10, FazWaz est écarté (stock +73 %, rattrapage du sitemap) ; au 15/10, c'est DDproperty (5 jours sans retrait). Tant que ça dure, la composition du score change d'une semaine à l'autre et la série n'est pas comparable.

**Mis à jour le 2026-10-20.** Remesuré avec les données à jour, les fenêtres finissant les 15, 17 et 19/10 gardent toutes deux grandes sources : DDproperty a délisté 2 529 annonces le 17/10. Cause des trous DDproperty, mesurée au ledger : chaque nuit sans retrait est un recensement arrêté au plafond `max_pages_recensement` (3 200 pages par flux, 6 400 lues), donc avant la fin du catalogue, ce qui interdit le délistage. **Décision de l'utilisateur** : la base est considérée saine depuis `fiable_depuis`. `sante_sources.saines_forcees` (config v2) garde DDproperty et FazWaz sur toutes les fenêtres jusqu'au 2026-10-20 ; au-delà, les règles automatiques reprennent. Le calcul devient **quotidien** en fin de cycle, et l'agent `scores-tension` alerte (constat haut → réparation) dès **3** jours sans retrait d'une grande source, deux jours avant l'exclusion.

### Tension : 6 signaux bruts, 5 familles pondérées
| Famille | Signal | Sens (+ = vendeur) | Poids |
|---|---|---|---|
| Écoulement | sorties ÷ cohortes à risque, par mois | + | 0,35 |
| Durée | âge médian de sortie, **Kaplan-Meier avec censure et troncature à gauche** | − | 0,20 |
| Offre | −ln(stock t ÷ stock t−90 j), **même périmètre aux deux dates** (v3, voir ci-dessous) | + | 0,15 |
| Prix | part des cohortes avec une baisse sur 30 j (−) et prix/m² à panier constant sur 90 j (+), moyennés | ± | 0,15 |
| Vendeurs | cohortes actives par immeuble | − | 0,15 |

### Liquidité : facilité de revente au prix du marché
Postulat de l'utilisateur : **on revend à la valeur de marché**. Seules comptent donc les cohortes affichées à ±10 % du prix/m² de leurs **pairs** (même immeuble et mêmes chambres, sinon mêmes chambres dans la maille). Comparer à tout l'immeuble mélangeait studios et grands lots, et écartait des lots normaux : défaut trouvé par un test le jour même. Signaux : vitesse (KM, −) 0,6 ; probabilité de partir en 90 j (+) 0,4. La profondeur, ln(1 + sorties/mois), est calculée et affichée **hors score** : elle grandit avec la taille de la maille (Bangkok ressortait à 83 face à une référence de districts). **Âge** : vitesse remesurée par tranche d'âge d'immeuble (0-5, 5-10, 10-15, 15-20, 20-30, 30+ ans) sur Bangkok à mêmes chambres. La projection à +5 / +10 ans applique le rapport « tranche future ÷ tranche actuelle ». **Jalons de travaux : liste vide à dessein**, à renseigner avec une source ; ils s'affichent sans modifier le score.

### Normalisation, petits échantillons, incertitude
- z robuste = (x − médiane) ÷ (1,4826 × MAD) face à la **distribution des districts publiables** (mêmes filtres, poolée sur les fenêtres de 28 j des 12 derniers mois), borné à ±3, puis **100 × Φ(z)**. Pas de rang : un rang est à somme nulle. Repli de la référence (mêmes chambres, puis tout le stock) quand les filtres laissent moins de la moitié des signaux ; la référence utilisée est affichée.
- Retour vers la moyenne hiérarchique : ŝ = (n·s + 20·parent) ÷ (n + 20), le long de Bangkok → zone → district → 1 km → immeuble.
- Bootstrap de 200 tirages sur les cohortes, graine fixe. Score = médiane, fourchette p10–p90. Le libellé n'est affirmé que si la fourchette reste d'un côté du seuil (35 / 65), sinon « leaning » ; fourchette de plus de 30 points → « not enough data ». Minimum : 30 cohortes et 10 sorties.

### Prix/m² face aux comparables
Stock actif en fin de fenêtre : immeuble tous lots, immeuble mêmes chambres et ±15 % de surface, puis 1 km et district. Médiane, p25–p75, part des comparables moins chers, verdict. Sous 5 comparables : pas de verdict.

### Date de naissance d'une annonce (config v3, 2026-10-21)
`first_seen` date notre **découverte**, pas la mise en ligne. Sur la fenêtre au 18/10, 10 % des annonces DDproperty et FazWaz ont été trouvées plus de 30 jours après leur création, et le stock en vente DDproperty passait de 3 996 à 40 562 entre t−90 j et t1, presque entièrement par rattrapage de couverture. Le signal offre lisait ça comme un marché qui s'effondre.

**Méthode.** Les identifiants de DDproperty, FazWaz, PropertyScout, PropertyHub et Nestopa sont des compteurs. La **frontière** d'une source à la date d est le plus grand identifiant vu jusqu'à d. Une annonce est née le premier jour où la frontière a dépassé son identifiant, jamais après sa première vue. Hipflat (identifiant haché) garde sa première vue. PropertyHub, suivi depuis le 2026-10-20 seulement, prend aussi son `createdAt` (distinct de `refreshed_at`, la remontée) : vérifié cohérent avec l'ordre des identifiants (4,4 % d'inversions entre voisins sur 4 000 annonces), il date des annonces depuis 2019, avec une médiane au 2026-09-09.

**Validation.** Sur 91 127 annonces DDproperty datables, **99,2 %** ont un `posted_at` (date de remontée, donc postérieure à la création) supérieur ou égal à la naissance estimée moins 2 j, avec un écart médian de **0 j**. PropertyScout : retard médian de découverte de 29 j, non expliqué, donc datation moins éprouvée.

**Usage.** (1) Offre : le stock passé compte les annonces qui **existaient** à t−90 j, même découvertes depuis, et les deux stocks ne retiennent que les sources déjà suivies à t−90 j (PropertyHub et Hipflat en sont exclues jusqu'au 2027-01-18). (2) Durée et liquidité : les âges partent de la naissance, et l'entrée sous observation est la première vue (troncature à gauche exacte). (3) Écoulement : inchangé, une sortie n'étant observable qu'après la découverte.

**Effet mesuré au 18/10.** Offre Bangkok −0,99 → **−0,15**. Étendue des districts −1,40…−0,69 → −0,24…−0,09. Corrélation de rang v2/v3 : 0,57, l'ancien classement suivait la couverture. Écoulement inchangé.

**Biais restant, non mesuré.** Une annonce née avant t−90 j et retirée avant qu'on la voie manque au stock passé. L'offre reste donc légèrement tirée vers « l'offre gonfle ».

### Ce que ces scores ne disent pas
Ce sont des **prix affichés** et des **retraits d'annonces**, pas des ventes. Les poids sont des hypothèses de départ, à recalibrer par validation prédictive (le score à t annonce-t-il les baisses et les délais à t + 1 mois ?) dès 3 mois d'historique.
