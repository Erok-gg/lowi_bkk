# Benchmark — ce que les plateformes affichent déjà (relevé du 2026-10-17)

> Journal du sous-projet **Concurrence**. Ajout seul : un relevé plus récent
> s'ajoute en dessous, il ne remplace pas celui-ci.
> Retour au projet : [README](README.md).

## Méthode — et ce qu'elle vaut

- **Échantillon** : 10 immeubles tirés au hasard (graine `20261017`) parmi les
  412 immeubles du CBD (Pathum Wan, Bang Rak, Sathon, Vadhana, Khlong Toei,
  Ratchathewi) qui ont au moins 10 annonces actives sur au moins 3 de nos
  sources : Langsuan Ville, The Lumpini 24, UP Ekamai, Park Origin
  Ratchathewi, Sathorn House, Maru Ekkamai 2, SCOPE Thonglor, GM Mansion,
  WIDEN by Sansiri, Oriental Towers.
- **Pages lues** : pour chaque plateforme, la fiche annonce **et** la fiche
  projet quand elle existe, lues ensemble (un acheteur passe de l'une à
  l'autre). Téléchargement en HTTP avec robots.txt respecté, une page toutes
  les 3 s, texte visible extrait du HTML rendu côté serveur.
- **Comptage** : présence d'un libellé par expression régulière, **puis
  relecture à la main des cas douteux**. Corrigé à la relecture : DDproperty
  « Estimated mortgage » n'est pas une estimation de valeur ; la distance au
  métro FazWaz est bien présente, mais sur deux lignes.
- **Limite** : un champ chargé en JavaScript après coup (graphique d'historique
  par exemple) peut manquer au relevé. Le tableau dit « affiché dans le HTML
  servi », pas « absent du site ».

## Couverture obtenue

| Plateforme | Pages lues | Accès |
|---|---|---|
| FazWaz | 10 annonces + 10 fiches projet | ok |
| Hipflat | 10 fiches projet | ok (session navigateur, sinon 401) |
| DDproperty | 10 annonces + 10 fiches projet | ok (session réchauffée Cloudflare, sinon 403) |
| PropertyScout | 6 annonces (4 immeubles absents de leur stock) | ok |
| Lazudi · Dot Property · Thailand-Property · CondoDee | 1 immeuble chacun | ok — **échantillon trop faible pour conclure** |
| LivingInsider | 0 | **bloqué par AWS WAF** (défi JavaScript), y compris pour notre extracteur |
| Nestopa | 0 | fiches en 403 (déjà connu) |
| RE/MAX Thailand | 0 | application JavaScript, aucune fiche Bangkok trouvée |

## Le tableau

`10/10` = présent sur 10 immeubles lus. ◐ = présent mais partiel.
— = absent du HTML servi. Les colonnes à un seul immeuble sont indicatives.

| Paramètre | FazWaz | Hipflat | DDproperty | PropertyScout | Lazudi¹ | Dot Property¹ | Thailand-Prop.¹ | CondoDee¹ |
|---|---|---|---|---|---|---|---|---|
| **Le lot** | | | | | | | | |
| Prix, m², chambres, SDB | 10/10 | 10/10 (liste) | 10/10 | 6/6 | ✓ | ✓ | ✓ | ✓ |
| Prix au m² du lot | 10/10 | 10/10 | 10/10 | 6/6 | ✓ | — | — | ✓ |
| Étage du lot | 10/10 | ◐ liste | — | 6/6 | — | ✓ | — | ✓ |
| Vue, ameublement | 10/10 | ◐ ventes passées | — | 6/6 | — | ✓ | — | — |
| Quota étranger / thaï **du lot** | 9/10 | 6/10 (ventes passées) | — | 6/6 (champ souvent vide) | — | ✓ | — | — |
| Tenure | 9/10 | 1/10 | 10/10 | 6/6 | — | — | — | — |
| **L'annonce** | | | | | | | | |
| Date de mise en ligne | 10/10 | — | 10/10 | 6/6 | — | ✓ | — | — |
| Dernière mise à jour / « confirmé disponible » | 10/10 | — | — | 6/6 | — | ✓ | — | — |
| Baisse de prix / ancien prix barré | 10/10 | — | — | 6/6 | — | — | — | ✓ |
| Annonce « vérifiée » | 3/10 | — | 10/10 | 6/6 | — | — | — | — |
| Agent / publieur | 10/10 | 10/10 | 10/10 | — (PropertyScout est l'agence) | ✓ | ✓ | — | — |
| **Le verdict prix** | | | | | | | | |
| Verdict sous/sur-évalué par annonce | **10/10** (« Great Price », « Overpriced », −10,5 % sous la valeur) | — | — | **6/6** (« GREAT DEAL », comparé à des annonces similaires) | — | — | — | — |
| Estimation de valeur (AVM) | **10/10** (« FazWaz Estimate », « Valuate now ») | — | — | — | — | — | — | — |
| Prix/m² moyen ou médian de l'immeuble | ◐ via la liste | **9/10** | 7/10 (fourchette PSM) | — | — | — | — | ✓ médiane |
| Immeuble comparé au quartier et à Bangkok | — | **10/10** (« 26,1 % sous Pathum Wan ») | — | — | — | — | — | — |
| Tendance sur 1 an (vente et loyer) | — | **10/10** | — | — | — | — | — | — |
| **Les transactions** | | | | | | | | |
| Ventes passées : date, prix vendu, m², étage, quota | **6/10** | **6/10** | — | — | — | ◐ « sold » | — | — |
| Délai moyen avant vente | — | **5/10** (« 970 jours ») | — | — | — | — | — | — |
| Décote obtenue à la vente | — | **5/10** (« 15 % sous le prix affiché ») | — | — | — | — | — | — |
| **Louer** | | | | | | | | |
| Rendement locatif | 7/10 (par annonce, « 5 % ») | — | — | — | — | — | — | ✓ médiane (3,26 %) |
| Stock disponible vente / location | 10/10 | 10/10 | 8/10 | — | ✓ | — | ✓ | — |
| **L'immeuble** | | | | | | | | |
| Année de livraison | 10/10 | 10/10 | 10/10 | 6/6 (⚠ « 2014 » par défaut) | ✓ | ✓ | — | ✓ |
| Nombre d'unités | 10/10 | ⚠ **faux ami²** | 10/10 | ◐ 3/6 | ✓ | ✓ | ✓ | ✓ |
| Étages, bâtiments | 10/10 | 10/10 | 9/10 | 6/6 | ✓ | ✓ | ✓ | ✓ |
| Promoteur | 10/10 | — | 8/10 | 2/6 | ✓ | ✓ | ✓ | ✓ |
| Charges de copropriété (CAM/m²) | 8/10 | — | ◐ dans la prose | 6/6 (souvent vide) | — | ✓ | — | ✓ |
| Fonds de travaux | 4/10 | — | — | — | — | — | — | ✓ |
| Ratio parking, ascenseurs | 5/10 | 5/10 | ◐ prose | — | — | — | — | — |
| Animaux | 10/10 | 9/10 | — | 6/6 | — | ✓ | — | — |
| Équipements | 9/10 | 9/10 | 5/10 | 6/6 | ✓ | ✓ | ✓ | ✓ |
| Plans | 10/10 | 4/10 | — | — | — | — | — | — |
| Avis de résidents | 10/10 (souvent 0 ou 1 avis) | — | 10/10 (section vide) | — | — | — | — | — |
| **Emplacement** | | | | | | | | |
| Distance au métro le plus proche | 10/10 | ◐ noms sans distance | 6/10 | 6/6 | ✓ | — | — | ✓ |
| Écoles, hôpital | 10/10 (dans la FAQ) | — | 3/10 | — | — | — | ✓ | ✓ |
| Projets voisins comparés (unités, prix, année, écart) | **10/10** | 10/10 | — | 6/6 (annonces similaires) | ✓ | — | ✓ | — |
| **Outils** | | | | | | | | |
| Simulateur de prêt | 10/10 | — | 10/10 | — | — | — | — | ✓ |

¹ Un seul immeuble lu (The Lumpini 24, Langsuan Ville pour CondoDee).
² Sur Hipflat, le chiffre affiché à côté de « Units » est le **nombre
d'annonces disponibles** (vente + location), pas le nombre de lots :
Langsuan Ville 158 = 57 à vendre + 101 à louer, alors que FazWaz et
DDproperty donnent 262 lots.

## Les faits d'immeuble ne concordent pas

Nombre de lots / année de livraison, tels qu'affichés :

| Immeuble | FazWaz | DDproperty | PropertyScout | Hipflat (annonces !) |
|---|---|---|---|---|
| Langsuan Ville | 262 / 2001 | 262 / 2001 | 262 / **2014** | 158 |
| The Lumpini 24 | 402 / 2016 | **393** / 2016 (426 dans sa propre prose) | 402 / **2014** | 948 |
| UP Ekamai | 259 / 2011 | 259 / **2014** | 259 / 2014 | 65 |
| SCOPE Thonglor | 18 / 2024 | **17** / **2025** | — | 42 |
| WIDEN by Sansiri | 215 / **1985** | 215 / 2027 | — | 20 (livraison oct. 2026) |
| Sathorn House | 396 / 1997 | 396 / 1997 | 396 / 2014 | 65 |

- FazWaz et DDproperty donnent **le même nombre de lots sur 8 immeubles
  sur 10**. C'est probablement une même origine recopiée, donc **une voix,
  pas deux** : la leçon de `ops/referentiel-condos.py` (2026-08-03)
  s'applique.
- Des erreurs grossières sont visibles : WIDEN « livré en 1985 » chez FazWaz
  alors qu'il est en construction, et PropertyScout affiche 2014 sur la
  plupart de ses fiches.
- **Conséquence** : aucun portail n'affiche son niveau de confiance. Une fiche
  immeuble qui dit « 3 sources concordent » ou « sources en désaccord » est
  une différence réelle.

## Ce que ça change pour nous (constats, pas encore décisions)

1. **Le verdict « sous/sur-évalué » existe déjà**, chez FazWaz (avec une
   estimation automatique de valeur) et chez PropertyScout. Afficher un écart
   à la médiane ne suffit pas à se différencier.
2. **FazWaz et Hipflat ont des prix de vente réels**, issus de leurs propres
   transactions : délai de vente, décote obtenue, ventes passées. **Nous n'en
   avons pas.** Nous observons des retraits d'annonce, pas des ventes. C'est
   leur avance la plus nette.
3. **Ils ne sont pas neutres.** FazWaz, Hipflat (qui affiche les mêmes champs
   de gestion que FazWaz — même groupe probable, *à vérifier*) et
   PropertyScout (« we earn our fee from the landlord ») sont payés par le
   vendeur ou l'agent. Leur verdict prix est rendu par une partie au deal.
4. **Personne ne montre l'histoire de l'annonce d'un portail à l'autre**
   (republications, baisses cumulées, ancienneté réelle). FazWaz montre une
   baisse sur sa propre annonce, rien de plus.
5. **Personne ne montre la pression vendeuse dans l'immeuble** en part des
   lots (« 12 lots en vente sur 262 ») ni l'écoulement du stock.
6. **Personne n'arbitre les faits d'immeuble** ni n'affiche de confiance.

Non vérifié : les graphiques chargés en JavaScript (historique de prix
Hipflat ou FazWaz, s'il existe) ; les plateformes à un seul immeuble lu ;
RE/MAX et LivingInsider (illisibles sans navigateur).

---

# Relevé n°2 — un seul bien suivi sur 5 portails (2026-10-22)

> Ajout seul. Là où le relevé du 17/10 comptait des libellés sur 10 immeubles,
> celui-ci suit **un lot** et compare les valeurs affichées.

## Le bien
Knightsbridge Prime Sathorn (Sathon), 1 chambre, **37,95 m², étage 30**,
meublé, freehold, livré 2019. Choisi parce que 5 de nos sources l'affichent au
même prix à ±5 % : FazWaz 5,50 M · PropertyScout 5,29 M · DDproperty 5,29 M ·
LivingInsider 5,29 M · PropertyHub 5,25 M. Hipflat : 0 annonce en base pour cet
immeuble, page projet non trouvée. Nestopa : absent.
**Même lot : certain pour FazWaz + PropertyScout** (étage 30, 37,95 m², meublé) ;
**déduit seulement** pour les trois autres (étage non affiché : « xx » chez
PropertyHub, absent chez DDproperty). DDproperty porte 7 annonces à 5,29 M /
38 m² de 7 agents différents : un même lot repris, ou 7 duplex identiques dans
une tour de 726 lots — l'étage manquant empêche de trancher.

## Écarts mesurés entre portails
- **Prix du même lot** : 5,25 → 5,50 M, soit 4,8 % (≈ 250 000 THB).
- **Prix/m²** : FazWaz arrondit (144 928), PropertyScout tronque (139 393),
  PropertyHub divise par 38 arrondi (138 158 au lieu de 138 340).
- **Date de mise en ligne** : PropertyScout affiche « 2 août 2025 » ; notre
  `first_seen` dit 2026-07-06 → l'ancienneté est **sous-estimée de ~11 mois**.
  Le prix y a baissé de 5,99 M à 5,29 M le 2026-10-05 (−11,7 %), visible dans
  notre historique, pas sur la page.
- **Charges** : FazWaz 55 THB/m² (2 087/mois = 55 × 37,95) = PropertyHub
  « Utility fee 55 » → concordent. Lots, étages, année : 726 / 43 / 2019 chez
  FazWaz, PropertyScout, PropertyHub (probable origine commune).
- **Rendement** : FazWaz « 5 % », ratio prix/loyer 18 → loyer implicite
  25 460 THB, soit 5,56 % **tronqué** à 5. Notre médiane 1 ch. 36–40 m² :
  27 000 (5,9 %) ; moyenne toutes surfaces 29 700 (6,5 %).
- **Position face à Bangkok** : PropertyScout « vente 1 ch. **23,4 % sous** la
  moyenne de Bangkok » ; notre base : médiane 1 ch. de l'immeuble **+51 %** en
  prix, **+42 %** au m² (n = 163 contre 36 834). Signes opposés ; définition
  PropertyScout non publiée.
- **Surface d'un duplex** : PropertyHub donne les types « Monoplex 24–30 m² » et
  « Duplex 25,5–30,5 m² » (emprise) alors que les annonces duplex affichent
  37–44 m² (mezzanine comprise, « 30,5 + 13,5 »). Le prix/m² mélange les deux.
- **Couverture de notre base pour cet immeuble** : FazWaz 31 ventes / 89
  affichées ; PropertyHub 14 / **326**. PropertyHub et Hipflat ont exactement
  **4 000** annonces actives en base : plafond probable, **non vérifié**.

## Non fait / non vérifié
Fiches DDproperty (403 malgré session réchauffée) et LivingInsider (défi WAF)
non lues ; Hipflat non lu ; un seul lot (anecdote, pas une mesure) ; l'existence
d'un verdict « Great Price » sur l'annonce FazWaz n'est pas confirmée (présent
sur la page projet, absent du HTML de la fiche).

## Précision du 2026-10-22 — le périmètre change le signe

Le « +42 % / +51 % » face à Bangkok ci-dessus comparait un immeuble du CBD à
toute la ville : périmètre trop large. Médianes 1 chambre, ventes actives,
bornes de plausibilité appliquées, immeuble = 163 ventes :

| Périmètre | Ventes (n) | Prix/m² médian | Écart immeuble | Prix médian | Écart | Loyer médian | Écart |
|---|---|---|---|---|---|---|---|
| Immeuble | 163 | 159 091 | — | 5,90 M | — | 29 000 | — |
| Rue (Naradhiwas, hors immeuble) | 89 (10 immeubles) | 119 462 | **+33 %** | 4,89 M | +21 % | 24 000 | +21 % |
| 1 km (hors immeuble) | 561 (50 immeubles) | 140 000 | **+14 %** | 6,50 M | **−9 %** | 26 000 | +12 % |
| Khet Sathon | 977 (54 immeubles) | 145 000 | **+10 %** | 5,90 M | 0 % | 28 000 | +4 % |
| Bangkok | 35 591 | 113 793 | +40 % | 3,97 M | +48 % | 23 000 | +26 % |

- L'écart au m² reste positif à toutes les échelles (+10 à +40 %) ; **PropertyScout
  (−23 % en prix) n'est retrouvé à aucune** ; le plus proche est le prix absolu
  à 1 km (−9 %), qui s'explique par la taille : l'immeuble vend des 38 m².
- À taille comparable (34–42 m²), 1 km : 140 476/m² (n = 165, 22 immeubles) ;
  khet : 140 135/m² (n = 318). Le lot à 139 393/m² est donc **au niveau du
  voisinage et ~12 % sous la médiane de son propre immeuble** (159 091).
- Lecture : la médiane de l'immeuble tire vers le haut parce que ses petits lots
  (< 36 m², 173 871/m²) sont plus chers au m². Le choix du périmètre et de la
  taille décide du signe → c'est précisément ce qu'un bilan doit afficher.
- Limites : le nom de rue est saisi différemment selon les annonces
  (« 599 Naradhiwas… », « Naradhiwas… », parfois vide : 193 lots) ; filtre par
  contenu du nom, 89 lots seulement. Rayon calculé à partir du centre moyen des
  annonces de l'immeuble, pas des coordonnées officielles.

## Précision du 2026-10-22 (suite) — suivre la date de publication d'une source ?

Question posée : quand un portail donne une date de publication plus ancienne
que notre `first_seen`, la suit-on ? **Aujourd'hui non** : `first_seen` est la
base unique (décision du 2026-08-02, parce que le `posted_at` de DDproperty se
comporte comme une date de remontée en tête de liste, écart médian −16 j).
**Mesuré pour PropertyScout** (10 fiches réparties sur toute la plage
d'identifiants) : « Date Listed » croît **strictement avec l'identifiant**
(291 909 → 2020-11 ; 1 338 562 → 2023-10 ; 2 376 987 → 2025-10 ; 3 427 589 →
2026-09), donc elle se comporte comme une vraie date de création, pas comme une
remontée. Notre `first_seen` en retarde de 2 semaines à 3 ans, borné par le
début de notre suivi (24/06/2026) et le délai de découverte (annonce du
14/08/2026 vue le 02/10).
Proposition, non appliquée : ancienneté = `min(first_seen, date de la source)`
**uniquement pour les sources dont la date a passé ce test** (PropertyScout oui ;
FazWaz plausible, 30/07 contre 01/08, non testé ; DDproperty non). Il manque une
colonne pour stocker la date source : PropertyScout ne la conserve pas.

## Correction du 2026-10-22 — les relevés n°1 et n°2 sous-lisaient les portails

Remarque de l'utilisateur : les sites donnent plus de données que ce qui a été
relevé (prix de vente conclus, moyennes en plus des médianes). **Exact** : les
deux relevés comptaient des libellés dans le texte visible ; or une partie des
chiffres vit dans le JSON embarqué des pages (`__NEXT_DATA__`, scripts) ou est
chargée après coup. Relu pour Knightsbridge Prime Sathorn :

| Portail | Ce qui était dans le HTML sans être affiché ni relevé |
|---|---|
| FazWaz (page projet) | **28 ventes conclues** : date, prix, surface, étage, ameublement (2019-10 → 2026-08) |
| PropertyScout | `medianSalePricePerSqm` / `medianRentPricePerSqm` par cluster (une seule valeur non nulle sur la page : 143 103 sur une annonce voisine) ; section « Market stats » **chargée en JavaScript, non lue** |
| PropertyHub | champ `averagePricePerSquareMeter` du projet : **null** |
| DDproperty, LivingInsider, Hipflat | non lus (403, WAF, introuvable) : on ne sait pas |

**Ventes conclues FazWaz (mesuré, 1 ch.)** : 36–40 m², 14 ventes, médiane
158 784/m², moyenne 159 760 ; depuis 05/2025 seulement 4 ventes (médiane 153 042,
moyenne 154 318, de 137 714 à 173 474) ; duplex ~44 m², 10 ventes, médiane
148 712. Annonces actives 36–40 m² dans notre base : médiane 151 351/m². Le prix
demandé aujourd'hui est donc **proche du conclu** pour cet immeuble.
**Prudence** : 28 ventes en 7 ans pour 726 lots ; l'origine (registre foncier,
saisie agent ?) n'est pas indiquée par la page ; un prix comme 4 911 967 ou
5 325 100 n'est pas un prix demandé, ce qui plaide pour un prix enregistré
(déduit, non prouvé) ; l'une des lignes a une surface 0.

**Limite des chiffres de portail** : ils décrivent leur propre base, avec des
définitions non publiées (PropertyScout « −23 % » introuvable à toute échelle).
Ce n'est pas une preuve d'erreur de leur part, c'est une raison de ne pas les
prendre comme référence.

**Sources publiques** : elles existent (REIC, BOT, Trésor, DOPA, BMA — voir
`study/official/sources.md`) mais donnent des indices régionaux ou par khet, pas
un prix par immeuble ; seul le registre foncier (prix de transfert) donnerait le
conclu par lot, et il n'est pas public ligne à ligne (à vérifier, non fait).

**Non fait** : lecture des API qui alimentent « Market stats » (PropertyScout) et
les graphiques Hipflat/FazWaz ; contrôle de l'origine des ventes FazWaz ; relevé
des 10 immeubles du 17/10 avec cette méthode.

## Relevé n°3 — ventes conclues FazWaz sur les 10 immeubles du 17/10 (2026-10-22)

Lecture du JSON embarqué de la **page projet** FazWaz (HTML servi, 2 pages par
immeuble, 3 s entre pages). **Non lus** : `/api/` et `/graphql` de FazWaz et
`/api/v1/projects/` de Hipflat (interdits par leur robots.txt, posture à
trancher par l'utilisateur) ; « Market stats » de PropertyScout (API non
identifiée : l'extension Chrome n'était pas connectée) ; pages projet Hipflat ;
DDproperty.

| Immeuble | Ventes conclues | Prix/m² vendu (médiane / moyenne) | Depuis 2025 | Demandé actif (médiane) | Rapprochées à une de nos annonces disparues |
|---|---|---|---|---|---|
| Langsuan Ville | 5 (2019–24) | 155 488 / 162 852 | 0 | 179 495 (n=68) | 0/5 |
| The Lumpini 24 | 15 (2019–26) | 173 077 / 207 781 | 8 : 214 734 | 197 368 (n=196) | 0/15 |
| UP Ekamai | 4 (2026) | 94 869 / 95 447 | 4 : 94 869 | 97 564 (n=63) | 3/4 |
| Sathorn House | 5 (2023–26) | 117 105 / 106 399 | 1 : 79 365 | 113 208 (n=17) | 0/5 |
| Maru Ekkamai 2 | 17 (2018–26) | 190 678 / 187 906 | 9 : 198 148 | 197 059 (n=95) | 4/17 |
| Oriental Towers | 7 (2018–26) | 77 904 / 71 253 | 3 : 80 692 | 99 558 (n=37) | 0/7 |
| Park Origin, SCOPE Thonglor, GM Mansion, WIDEN | **aucune** | — | — | — | — |

- **Couverture** : 6 immeubles sur 10, 53 ventes en tout, soit 4 à 17 par
  immeuble sur ~8 ans (≈ 2 par an et par immeuble). Trop mince pour une médiane
  fiable dans la plupart des cas ; les immeubles neufs (SCOPE, WIDEN) n'en ont pas.
- **Écart demandé → vendu depuis 2025** (n ≥ 3 seulement) : UP Ekamai −3 %, Maru
  Ekkamai +1 %, Lumpini 24 **+9 %** (vendu au-dessus du demandé actuel : mélange
  de tailles et d'étages), Oriental Towers **−19 %**. Pas de décote régulière à
  extraire.
- **Origine** : 7 ventes sur 53 se rapprochent d'une de nos annonces disparues
  (même immeuble, surface ±1,5 m², prix ±7 %, ±90 j). Notre historique ne
  commence qu'en 06/2026 : sur les ventes de 2026 seulement, UP Ekamai 3/4. Cela
  suggère des prix de sortie d'annonce déclarés par les agents, **sans le
  prouver** (4 cas).
