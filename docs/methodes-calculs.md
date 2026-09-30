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
