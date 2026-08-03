# Note de conjoncture — août 2026

*Édition du 2026-08-03. Étude complète : [etude-2026-08-03.md](etude-2026-08-03.md).
Corpus : 27 380 annonces actives, 3 011 immeubles.*

---

## ⚠ À lire avant les chiffres : cette édition ne mesure pas le marché

Le corpus est passé de **18 429 à 27 380 actives** entre les deux éditions, non
parce que l'offre a bondi de moitié, mais parce qu'un scrap complet effectué en
isolation les 2-3 août a été remonté vers la base de production. **19 904
annonces sont entrées d'un coup.**

Les écarts entre le 9 juillet et aujourd'hui mélangent donc mouvement réel et
changement de composition, et **rien ne permet de les séparer**. Ce qui reste
lisible : le sens et le classement relatif des quartiers. Ce qui ne l'est pas :
l'ampleur.

Le rapport porte cet avertissement en tête de sa section d'évolution, et il est
émis automatiquement — `ops/remonter-local.py` journalise chaque remontée, et
l'étude relit ce journal. La prochaine édition, sur corpus stable, donnera la
première évolution propre.

**Il faut ajouter que l'édition de juillet ne mesurait rien non plus** : les
instantanés du 6 et du 9 juillet étaient identiques au chiffre près — mêmes
totaux, 48 quartiers sur 48 égaux, aucun scrap entre les deux. Le rapport
affichait « Δ +0,0 % » partout, ce qui se lisait comme une stabilité du marché.
C'était la même mesure présentée deux fois. Le framework refuse désormais de
produire une table d'évolution quand les données n'ont pas bougé.

**Conséquence pratique : la première évolution exploitable de ce projet sera
celle de septembre.**

---

## Les mouvements, sous cette réserve

| quartier | grandeur | 09/07 | 03/08 | écart |
|---|---|---:|---:|---:|
| Wang Thonglang | prix/m² vente | 52 778 | 69 390 | **+31,5 %** |
| Bang Na | prix/m² vente | 82 115 | 63 309 | **−22,9 %** |
| Bang Khen | loyer/m² | 460 | 365 | −20,7 % |
| Bang Kho Laem | loyer/m² | 500 | 594 | +18,9 % |
| Bangkok Yai | loyer/m² | 386 | 453 | +17,4 % |

Ces amplitudes — ±20 à 30 % en trois semaines sur des médianes d'immeubles —
sont **invraisemblables pour un marché immobilier**. Elles mesurent l'arrivée de
nouveaux immeubles dans chaque panier, pas une revalorisation. Un marché de
condominiums ne bouge pas de 30 % en vingt-cinq jours ; l'invraisemblance est
elle-même l'indice que le chiffre est un artefact.

Aucune recommandation d'achat ne peut s'appuyer sur ce tableau ce mois-ci.

---

## Ce qui a réellement changé, et qui compte

**L'année de livraison des immeubles existe enfin.** Le champ `condos.year_built`
était à **zéro depuis le début du projet** — c'était le chantier n°1. Il porte
aujourd'hui **2 265 immeubles sur 4 514**, extraits des descriptifs et consolidés
au niveau du bâtiment.

Chaque valeur porte un **indicateur de confiance**, parce que toutes ne se valent
pas :

| | immeubles |
|---|---:|
| **validé** — 3 sources indépendantes ou plus concordent | 100 |
| **corroboré** — 2 sources | 578 |
| **source unique** — invérifiable, pas faux pour autant | 1 587 |
| **conflit** — sources divergentes, année laissée nulle | 505 |

Une source = un portail, et non une annonce : mesuré le 3 août, les annonces
d'un même portail s'accordent sur l'année dans **99 à 100 %** des cas — elles
lisent une fiche projet unique. Compter les annonces gonflait la confiance d'un
facteur égal à leur nombre. Entre portails, l'accord tombe à **57 %**.

**Ce que ça débloque.** La méthode actuelle — double médiane par immeuble — a été
choisie *parce que* l'âge du bâti était inconnu : elle le neutralisait sans
pouvoir le mesurer. Il devient contrôlable. Premier ordre de grandeur, à quartier
et typologie identiques (0-1BR) : le neuf (≥ 2015) se vend **+54 % au-dessus** de
l'ancien (≤ 2009), et cela dans 6 quartiers sur 6. C'est un **majorant** — les
tours neuves se regroupent près des stations récentes — et une coupe
transversale, pas une courbe de dépréciation.

C'est une décision de méthode, pas une mise à jour : elle sera proposée
séparément, chiffres à l'appui.

---

## Contexte externe

**Ligne Orange — aucun changement.** La veille confirme ce que `study/context.md`
retenait déjà : section Est en 2028, Ouest en 2030, mise en service complète
attendue en novembre 2030. Les travaux préliminaires de la section Ouest ont
commencé, le gros œuvre non. La fenêtre d'achat sur ces couloirs reste celle
décrite dans le contexte, sans avancer ni reculer.

**Prix nationaux : quasi étale.** L'indice REIC des condominiums neufs à Bangkok
progresse de 2 à 4 % en glissement annuel début 2026 ; l'indice de la Banque de
Thaïlande donne les prix de condominiums bangkokiens **plats à légèrement
négatifs** sur 2025. L'écart entre zones se creuse : Sukhumvit et Sathon
conservent 3 à 5 % d'appréciation, les districts périphériques en surstock
corrigent de 4 à 10 % sous leur pic.

**La surabondance reste le fait dominant** : près de 58 000 unités invendues à
Bangkok fin 2024, plus ~42 000 livraisons supplémentaires jusqu'à mi-2025. Nos
27 380 annonces actives sont cohérentes avec ce contexte.

*`study/context.md` et `study/official/bot-manual.json` n'ont pas été modifiés :
aucun fait majeur nouveau n'est acté ce mois-ci.*

---

## Recommandation

**Ne rien conclure du différentiel de ce mois.** La seule action utile est
d'attendre l'édition de septembre, qui reposera sur un corpus stable et
fournira la première comparaison réellement interprétable.

Deux points méritent d'être creusés d'ici là, tous deux indépendants du bruit
de corpus :

1. **L'âge du bâti comme variable de sélection.** Avec 2 265 immeubles datés, on
   peut pour la première fois chercher les immeubles anciens dans des quartiers
   chers — là où la décote d'âge peut être un point d'entrée plutôt qu'un défaut.
2. **Les 505 conflits d'année.** Ce sont des immeubles où les portails se
   contredisent. Chaque conflit tranché est un immeuble de plus dans l'analyse,
   et la contradiction elle-même peut signaler une rénovation ou une livraison
   par phases — deux choses qui intéressent un acheteur.

---

## Alertes

**Aucune donnée de tension ce mois-ci.** La section 7 est vide : le transfert
n'est pas un scan et ne déliste rien, et il a de plus effacé les dates de
délistage de 5 110 annonces revues actives — état incohérent hérité d'un `upsert`
qui remettait le statut sans nettoyer la date. Corrigé dans les deux stores, mais
la conséquence demeure : **la mesure de tension ne repartira qu'au prochain vrai
scan.**

**La cadence de scrap est à trancher.** Deux scraps complets ont eu lieu à
quinze heures d'intervalle les 1er et 2 août, alors que la posture documentée du
projet est « ~hebdo, pas de boucle serrée ». C'était justifié techniquement — il
fallait éprouver la capture du texte intégral et les 19 colonnes de détail — mais
la cadence relève d'un choix de posture, pas d'un arbitrage technique.

## Sources

- [Bangkok Post — Orange Line due to fully open in 2030](https://www.bangkokpost.com/thailand/general/2832487/orange-line-due-to-fully-open-in-2030)
- [Nation Thailand — Construction work on western section of Orange Line to start next year](https://www.nationthailand.com/news/general/40042902)
- [Global Property Guide — Thailand's Residential Property Market Analysis 2026](https://www.globalpropertyguide.com/asia/thailand/price-history)
- [Savills Thailand — Thailand Property Market 2026: Strategic Outlook & Emerging Trends](https://www.savills.co.th/blog/article/225734/singapore-articles/thailand-property-market-2026--strategic-outlook-and-emerging-trends.aspx)
- [Nation Thailand — Thailand's Property Market 2025: Navigating Crisis](https://www.nationthailand.com/business/property/40060756)
