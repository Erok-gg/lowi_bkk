# Journal — Données du bilan

> D'où vient chaque chiffre du bilan, ce qui manque, et le recensement des
> unités. Ajout seul. Retour au projet : [README](README.md).
> Le flux général du système reste décrit dans [docs/pipeline.md](../pipeline.md).

## 2026-10-17 — état des lieux et recensement des unités

### Mesuré dans `bangkok.db` (PC2, lecture seule)
- `condos` : 4 514 lignes, **`nb_lots` vide sur toutes**, `year_built`
  renseigné sur 2 265. La table n'est **plus rafraîchie depuis le
  2026-07-28**.
- En repartant des annonces actives (nom normalisé par `_norm_condo`) :
  **4 876 immeubles** portent 130 047 annonces actives. 1 680 en ont au
  moins 10, 1 713 une seule.
- Amorce `nb_lots` par la prose DDproperty (regex de
  `agents/tests/test_prose_ddproperty.py`) : **1 251 immeubles**, dont 22 en
  conflit. Le top 500 porte 69 % des annonces actives, et 297 de ces 500
  immeubles sont amorcés.

### Liste de travail
`ops/recensement-unites.py` → `study/referentiel/recensement-unites.csv`
(**hors dépôt** : le fichier liste une URL d'annonce par portail, et le dépôt
est public). Le fichier est trié par nombre d'annonces actives. Les colonnes
de relevé manuel (`nb_lots_retenu`, `source_retenue`, `url_preuve`,
`date_releve`, `statut`, `note`) sont **conservées à chaque relance**. Fusion
testée : une ligne déjà relevée est gardée, un immeuble disparu reste dans le
fichier avec 0 annonce active.

### Sources du nombre de lots — ce que le benchmark a appris
| Source | Couverture sur les 10 immeubles | Fiabilité observée |
|---|---|---|
| Fiche projet FazWaz | 10/10 | Concorde avec DDproperty sur 8/10, **même origine probable = une seule voix** ; erreurs d'année visibles (WIDEN « 1985 ») |
| Fiche projet DDproperty | 10/10 | Voir ci-dessus ; The Lumpini 24 : 393 en tête de fiche, 426 dans sa propre prose |
| PropertyScout | 3/6 renseignés | Année « 2014 » par défaut sur la plupart des fiches |
| Hipflat | ⚠ **inutilisable** | Le chiffre « Units » est le nombre d'**annonces** disponibles |
| Prose DDproperty (déjà en base) | 74 % des fiches | Sans erreur sur 100 fiches étiquetées à la main |
| **CondoMaps (Département des terres)** | non testé | **Source officielle**, au niveau du projet et du lot (`condomaps.dol.go.th` ; champs `roomsNo`, `floorsNo`, `juristic`, `register` dans le frontal) |
| Étude Chulalongkorn (registre DOL 1981–2017) | historique | 2 909 projets / 711 358 unités, publié dans *Sarasatr* |

**Proposition, non décidée** : pour un premier jet, FazWaz + DDproperty
comptent comme **une** source, la prose DDproperty comme **une deuxième**.
CondoMaps tranche en cas de désaccord, et devient la référence si son usage
est autorisé.

### Autres trous de données pour le bilan
- **Numérateur de la pression vendeuse** : il faut des lots distincts en
  vente, pas des annonces (cohortes `unit_key`, vente seule).
- **Charges de copropriété et fonds de travaux** : visibles chez FazWaz (8/10
  et 4/10), absents de notre base. Extractibles de la prose et des fiches
  projet.
- **Quota du lot** : FazWaz l'affiche sur 9/10 (souvent « Thai Quota »),
  alors que nous l'avons sur environ 1 % du stock.
- **Prix vendus** : aucun. FazWaz et Hipflat en ont, issus de leurs propres
  transactions.
- **LivingInsider est désormais derrière AWS WAF** (défi JavaScript, constaté
  le 2026-10-17). C'est probablement la cause de la péremption de cette
  source depuis le 16/09, à confirmer dans les logs de l'agent
  `extract-livinginsider`.

### Non fait
- L'API de CondoMaps n'a pas été interrogée (authentification, conditions
  d'utilisation et rythme acceptable non vérifiés). La collecte automatique
  depuis un système gouvernemental est une décision de posture qui revient à
  l'utilisateur.
- Les fiches projet FazWaz et DDproperty ne sont pas collectées en masse. Les
  10 du benchmark l'ont été à la main.
- `condos` n'est pas mis à jour ; rien n'est remonté sur Supabase.

## 2026-10-17 (suite) — mois de stock par district : mesure et proposition de seuils
**Définition** : stock vente actif au milieu de la fenêtre ÷ retraits mensualisés. Périmètre : bornes de plausibilité (800 k–100 M, 15–500 m²), sources DDproperty, FazWaz et PropertyScout, fenêtre **2026-09-14 → 2026-10-12** (28 j). Script : `ops/etudes/mois-de-stock.py`.

**Pourquoi cette fenêtre** (mesuré) : les retraits suivent nos changements de pipeline. DDproperty en compte **0 en août** et **12 982 en septembre** (recensement), puis le délistage est **à l'arrêt depuis le 13/10** ; Nestopa n'en a **aucun** pour 2 074 actives ; LivingInsider est cassé depuis le 16/09. FazWaz ne délistait de façon fiable qu'à partir du mode sitemap (14/09).

**Mesuré**
| | Stock | Retraits | Mois de stock |
|---|---|---|---|
| Brut, toutes sources | 49 669 | 11 021 | **4,2** |
| Net de republications¹ | 49 669 | 3 116 | **14,9** |
| DDproperty seul, brut | 36 504 | 10 088 | 3,4 (de 2,9 à 4,2 dans **presque tous** les districts) |
| FazWaz seul, brut | 12 438 | 476 | 24,4 |

¹ Un retrait ne compte pas si une annonce de la même cohorte `unit_key` apparaît entre 3 jours avant et 21 jours après. **72 % des retraits DDproperty sont des republications.**

- **Le brut ne mesure pas le marché.** Il est uniforme sur DDproperty, ce qui est la signature d'un artefact (cf. le time-on-market de 6,9 j du 2026-07-28). Sur 10 districts communs, la corrélation de rang DDproperty / FazWaz vaut **0,02**.
- **Le net** va de 5,7 à 28,9 mois (36 districts publiables, ≥ 30 actives et ≥ 10 retraits nets). Terciles : **10,8 et 14,9**, médiane 13,0. Le classement met la périphérie ouest et nord en tête (Bang Phlat 5,7, Bangkok Noi 6,3) et le CBD en queue (Ratchathewi 20,4, Pathum Wan 19,4, Sathon 18,9, Khlong Toei 18,0).
- **Stabilité** : refait sur deux demi-fenêtres (14–27/09 et 28/09–12/10), le classement net a une corrélation de rang de **0,70** (0,66 sur les districts ≥ 500 actives). Il est stable, mais les deux moitiés partagent les mêmes biais de source : **stable ne veut pas dire juste**.

**Proposition de seuils (non décidée, règle 5)** : terciles du net, arrondis, **< 11 · 11–15 · > 15 mois**, avec des libellés **relatifs** (« faster / typical / slower than most Bangkok districts ») et non « seller's / buyer's market ». En seuils absolus (repère classique : < 4 mois pour un marché vendeur, > 6 pour un marché acheteur, établi sur des **ventes**), 36 districts sur 36 seraient « buyer's market » : la jauge ne dirait rien.

**Avant de l'afficher** : (1) délistage DDproperty réparé ; (2) mesure refaite sur une seconde fenêtre de 28 jours, avec une corrélation de rang ≥ 0,6 entre les deux ; (3) « données insuffisantes » sous 30 actives ou 10 retraits nets (Bueng Kum, Rat Burana, Thung Khru, Bang Khun Thian aujourd'hui).

**Non fait** : aucune validation externe (REIC, rapports CBRE, Knight Frank) ; fenêtre de republication (−3 / +21 j) non calibrée ; pas de version par cohorte pour le stock (des annonces en double gonflent encore le numérateur).
