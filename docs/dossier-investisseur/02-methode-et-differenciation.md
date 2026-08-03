# 02 — La méthode, et ce qui la différencie

> N'importe qui peut scraper 18 000 annonces. La valeur n'est pas là.
> Elle est dans cinq partis pris méthodologiques, chacun né d'une erreur mesurée.

---

## 1. L'immeuble est l'unité d'analyse, pas l'annonce

**Le problème.** Un quartier où un promoteur met 200 lots identiques en vente
verra sa médiane écrasée par ce seul immeuble. La statistique décrit alors la
stratégie commerciale d'un vendeur, pas le marché.

**Ce qu'on fait.** Médiane par immeuble d'abord, puis médiane des immeubles.
**Un immeuble = une voix**, quel que soit son nombre d'annonces.

**Ce que ça neutralise sans avoir la donnée** : la vétusté, l'étage, la vue,
l'orientation. Ces attributs varient énormément *dans* un immeuble et beaucoup
moins *entre* immeubles d'un même quartier. Passer par la médiane interne les
absorbe — c'est ce qui permet de produire un chiffre défendable alors que l'année
de construction n'est renseignée nulle part.

## 2. Le rendement se calcule dans le même bâtiment

**Le problème.** Le rendement affiché partout ailleurs est un ratio : loyer médian
du quartier ÷ prix médian du quartier. Or les biens en location et ceux en vente
ne sont pas le même parc. Dans un quartier où l'on vend surtout des grands et
loue surtout des studios, ce ratio ne décrit aucun bien réel.

**Ce qu'on fait.** On apparie vente et location **dans le même immeuble** —
1 308 immeubles y satisfont aujourd'hui — et on prend la médiane de ces
rendements internes. Quand l'appariement est trop mince, le chiffre est marqué
comme tel plutôt que lissé.

**Pourquoi c'est difficile à copier** : ça suppose de collecter les deux marchés
simultanément, avec une normalisation de nom d'immeuble assez bonne pour que les
deux côtés se retrouvent. La plupart des acteurs ne couvrent qu'un seul côté.

## 3. On suit des cohortes, pas des annonces

**Le problème.** Une annonce qui disparaît puis reparaît sous un nouvel
identifiant ressemble à une vente suivie d'une nouvelle mise en marché. Ce n'est
souvent qu'une **republication automatique** pour remonter dans les résultats.
Compter les disparitions comme des transactions surestime massivement l'écoulement.

**Ce qu'on fait.** On suit une *cohorte* — immeuble × chambres × tranche de 5 m² ×
type — plutôt qu'un identifiant d'annonce. Si le stock de cette cohorte reste
stable pendant qu'une annonce disparaît et qu'une autre apparaît, rien ne s'est
écoulé. 9 385 cohortes suivies, 80 126 observations.

## 4. Un périmètre de plausibilité unique, et vérifié

**Le problème constaté le 2026-07-28.** Les mêmes bornes existaient en trois
exemplaires qui s'ignoraient. Résultat : des biens exclus d'un tableau comptaient
toujours dans les médianes et les rendements. Pire, une liste d'« opportunités »
affichait en tête des **locations mal classées en vente**, donc à −100 % du prix
attendu — une aberration de source présentée comme la meilleure affaire du marché.

**Ce qu'on fait.** Les bornes sont définies à un seul endroit et appliquées
partout. Un agent vérifie **à chaque cycle** que l'implémentation applicative et
l'implémentation base de données disent exactement la même chose ; toute
divergence lève une alerte.

**Le principe** : un bien hors bornes n'est pas une affaire, c'est une donnée à
écarter. Et il reste consultable — on filtre les statistiques, on ne supprime rien.

## 5. On refuse de déduire ce qu'on ne peut pas prouver

C'est le parti pris le plus contre-intuitif, et le plus important.

**L'épisode fondateur.** Une requête avait identifié « 1 399 annonces actives en
doublon exact », soit 8,7 % du stock. La déduplication était prête à être écrite.
Avant de la lancer, inspection de dix lignes : les identifiants étaient
**consécutifs** chez la source (`u6548791` … `u6548800`) et les annonces
**simultanément actives**. Ce n'étaient pas des doublons : c'étaient des lots
distincts d'un immeuble neuf, versés en bloc par une agence, tous au même prix
parce qu'ils sont identiques.

**Dédupliquer aurait effacé de l'offre réelle** — c'est-à-dire exactement ce que
la pression vendeuse doit mesurer.

**Ce qui en découle, et qui structure tout le système :**

- Aucune fusion, aucune suppression automatique. Les cas douteux vont dans une
  **file de revue humaine** et n'influencent aucune statistique tant qu'ils ne
  sont pas validés.
- Ce qui rend la question décidable, c'est **qui publie**. Deux annonces
  identiques du même agent sont un doublon ; les mêmes venant d'agences
  concurrentes sont deux mises en marché. Ce champ est désormais collecté.
- Un compte agrégé ne dit pas ce qu'il compte. « 1 399 doublons » était une
  requête juste et une conclusion fausse.

---

## Le rôle de l'intelligence artificielle — mesuré, pas supposé

Le système emploie un modèle de langage local, mais **sur un périmètre étroit et
pour une raison précise**, établie par une campagne de mesure de 650+ appels sur
données réelles.

**Ce qui a été trouvé** : sur 38 355 paires d'annonces à arbitrer, une règle
déterministe en tranche **16 244 gratuitement et sans erreur**. Le modèle ne voit
que le reste.

**Et surtout** : à qui on demande un verdict, un modèle de 8 milliards de
paramètres répond toujours — y compris quand la question n'est pas tranchable.
Sur les cas indécidables, il rendait un avis dans **100 %** des cas.

La correction est architecturale : le modèle **ne juge plus**. Il constate des
faits élémentaires (« cette annonce est-elle active ? », « celle-ci est-elle
apparue après le retrait de l'autre ? ») et c'est du code déterministe qui décide.
Résultat mesuré : **99 % de justesse et 77 % d'abstention** là où le verdict
direct donnait 0 % d'abstention.

**Ce que ça change pour un tiers qui achète ces chiffres** : chaque décision est
attribuable à un fait vérifiable, pas à l'opinion d'un modèle. C'est auditable
ligne à ligne. Un seuil de non-régression gelé refuse toute dérive.

> **Formulation honnête pour un support commercial** : *« intelligence artificielle
> employée là où elle est mesurément meilleure que du code, et tenue à l'écart du
> reste »*. Pas *« piloté par l'IA »* — ce serait faux, et vérifiable comme tel.
