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
