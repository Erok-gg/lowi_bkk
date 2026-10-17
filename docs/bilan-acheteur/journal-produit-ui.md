# Journal — Produit & UI

> Ce qu'on affiche dans le bilan, et comment. Ajout seul, entrées datées.
> Retour au projet : [README](README.md) · Données : [journal-donnees](journal-donnees.md)
> · Concurrence : [benchmark-plateformes](benchmark-plateformes.md).

## 2026-10-17 — v1 du contenu, revue après le benchmark

### Le principe, réécrit par le benchmark
La première liste (même jour, avant le benchmark) mettait en tête l'écart à la
médiane de l'immeuble et le rang parmi les comparables. **FazWaz le fait déjà**
(« Great Price », « −10,5 % sous la valeur de marché », estimation automatique)
et PropertyScout aussi (« GREAT DEAL »). Placé en tête, ce bloc nous rendrait
interchangeables.

Le bilan se construit donc sur ce que **personne n'affiche** (constats 3 à 6
du benchmark). Le reste est présent pour être complet, pas pour vendre :

> **Un avis neutre** (nous ne touchons rien du vendeur), **l'histoire de cette
> annonce sur tous les portails**, **la pression vendeuse dans l'immeuble**,
> et des **faits d'immeuble arbitrés avec leur niveau de confiance**.

### Ce qu'on affiche, bloc par bloc

Légende : 🟢 nous seuls (relevé du 17/10) · 🟡 existe ailleurs, on le fait
mieux ou en neutre · ⚪ existe ailleurs, présent pour être complet.
Gratuit = visible dans le bilan partiel.

| # | Bloc | Contenu | Différence | Gratuit |
|---|---|---|---|---|
| 0 | **Identification** | Immeuble, chambres, m², prix, source ; date des données ; niveau de confiance global | — | ✅ |
| 1 | **Verdict en une phrase** | « Prix dans la moitié haute des comparables, en ligne depuis 140 j, 2 baisses : marge de négociation probable » | 🟡 neutre | ✅ (sans chiffres) |
| 2 | **Histoire de l'annonce** | Ancienneté réelle tous portails confondus, baisses cumulées, republications, nombre de portails et d'agents qui la diffusent | 🟢 | ◐ (ancienneté seule) |
| 3 | **Le prix face aux comparables** | Écart à la médiane de l'immeuble ; rang parmi les lots comparables (mêmes chambres, ±7 % m²), **sans lien** ; nombre de comparables | 🟡 | ◐ (position, sans chiffres) |
| 4 | **Pression vendeuse dans l'immeuble** | Lots distincts en vente / nombre total de lots ; évolution sur 3 mois ; durée médiane avant retrait | 🟢 (bloqué par le recensement des unités) | ✅ (niveau faible / moyen / fort) |
| 5 | **Fiche immeuble arbitrée** | Année, lots, étages, promoteur, charges/m², fonds de travaux, avec **badge de concordance** (« 3 sources concordent », « en désaccord ») | 🟢 (la confiance) | ✅ |
| 6 | **Le marché autour** | Tension du quartier, tendance du prix/m² (immeuble, quartier) | 🟡 | ◐ |
| 7 | **Louer** | Loyer médian des comparables du même immeuble, rendement brut **calculé dans l'immeuble**, offre locative concurrente | 🟡 | — |
| 8 | **Drapeaux rouges** | Prix aberrant, quota thaï, leasehold, surface incohérente, faits d'immeuble contradictoires | 🟢 (assemblés) | ✅ (nombre de drapeaux) |
| 9 | **Coût total d'acquisition** | Frais de mutation, SBT si détention < 5 ans, fonds de travaux, FET | ⚪ | — |
| 10 | **Méthode et limites** | « Prix affichés, pas prix vendus » ; sources ; date | — | ✅ |

**Ce qu'on n'affiche pas, et pourquoi.**
- **Pas de prix vendus** : nous n'en avons pas. Un « délisté » n'est pas un
  « vendu ». On l'écrit noir sur blanc plutôt que de laisser croire le
  contraire.
- **Pas d'estimation automatique en un seul chiffre** (AVM) : avec des prix
  affichés et sans étage ni vue sur la plupart des lots, un chiffre unique
  aurait une précision que nous n'avons pas. Une **fourchette** avec le
  nombre de comparables, oui.
- **Pas de liens vers les comparables** : choix juridique (pas de
  republication) et produit (le bilan reste le point d'arrivée).

### Comment l'afficher
- **Une seule page, lisible sur téléphone d'abord.** L'acheteur lit le bilan
  pendant une visite ou dans un échange avec un agent.
- **En tête : le verdict et trois chiffres**, pas un tableau de bord. Par
  exemple « 140 jours en ligne · −8 % de baisses cumulées · 12 lots en vente
  sur 262 ».
- **Le prix sur une réglette** : un nuage de points des comparables (un point
  par lot comparable, sans lien) et le point de l'annonce mis en évidence.
  Plus parlant qu'un pourcentage, et lisible sans rien connaître au marché.
- **L'histoire de l'annonce en frise** : apparitions et baisses de prix, une
  ligne par portail.
- **La confiance à chaque bloc** : pastille « solide / indicatif / faible »
  avec la raison au survol ou au clic (« 4 comparables seulement »,
  « 2 sources en désaccord »). Le badge `lowSample` existe déjà dans `lib/yields.ts`.
- **Le partiel gratuit montre la forme, pas les chiffres** : réglette sans
  graduation, niveau de pression sans le ratio, nombre de drapeaux sans leur
  détail. Le bilan complet affiche les nombres.
- **Version partageable** (lien du bilan) : même page, avec mention du code
  apporteur s'il y en a un (voir [journal-business-model](journal-business-model.md)).
  **Le contenu du bilan ne dépend jamais du code** : c'est la condition de la
  neutralité.

### Entrée du parcours
On colle une URL d'annonce. Trois cas :
1. **URL reconnue** dans notre base (`source_url`) → bilan direct.
2. **Portail connu mais annonce inconnue** → on extrait l'identifiant et
   l'immeuble du slug de l'URL, puis on demande de confirmer chambres, m² et
   prix.
3. **Inconnu** (Facebook, agent, LINE) → formulaire immeuble + chambres + m² +
   prix.
⚠ **Le taux de correspondance du cas 1 n'est pas mesuré.** C'est la première
mesure à faire : il décide si le produit tient.

### Non fait
- Aucune maquette, aucun code d'interface.
- Taux de correspondance des URL non mesuré.
- Le bloc 4 attend le recensement des unités (voir le journal données) **et**
  un numérateur dédoublonné. Life Asoke-Rama 9 compte 887 annonces actives
  pour environ 2 000 lots : le nombre d'annonces n'est pas le nombre de lots
  en vente.
- Ce qui est servi depuis Vercel : Supabase n'a ni `cohort_snapshots` ni
  `listing_amenities`, et l'historique des délistées reste local. Les blocs 2,
  4 et 6 ne sont **pas** calculables en ligne aujourd'hui. Le choix
  d'architecture (calcul sur PC2 puis remontée, ou élargissement de la
  fenêtre Supabase) n'est pas fait.

## 2026-10-17 (suite) — bloc « Market tension » ajouté, maquette passée en anglais
Demande de l'utilisateur : la tension du **district**, puis une comparaison **condo ↔ annonce** du temps passé sur le marché. Nouveau bloc, placé après la réglette de prix :
- **District** : jauge à trois niveaux (seller's / balanced / buyer's market), mois de stock (stock actif ÷ retraits mensuels), variation du stock sur 3 mois. Source : `cohort_tension` (cohortes `unit_key`), déjà calculée en local.
- **Jours sur le marché, même nombre de chambres** : trois barres, cette annonce / médiane de l'immeuble / médiane du district, et une phrase (« 2.3× the building median »). Médiane de l'immeuble : à écrire à partir de `first_seen` et de la date de retrait, par cohorte.
- **Pastille** « indicative · delistings, not sales » : un retrait d'annonce n'est pas une vente confirmée.
- Le verdict de tête intègre désormais la tension.
L'interface est en **anglais uniquement**, comme le reste du site (`CLAUDE.md`, « Interface & navigation »).
**Non fait** : seuils de la jauge (mois de stock pour basculer d'un niveau à l'autre) non fixés, à trancher par l'utilisateur (règle 5). Les médianes par immeuble seront souvent fondées sur trop peu de lots : un seuil minimal reste à mesurer, faute de quoi la barre « building » sera masquée.

## 2026-10-17 (suite 2) — tension : effectifs visibles et infobulle dépliable (demande pour la version rapport)
Demande de l'utilisateur pour le **rapport livrable** : chaque mesure de tension affiche **son nombre d'échantillons** (stock et retraits nets), et une **infobulle** se déplie en trois niveaux :
1. **Même chambres, même surface à ±15 %** dans le district : la tension au plus près de l'annonce.
2. **Même chambres, depuis début 2026** : la tendance de fond.
3. **Tout Bangkok, mois écoulé**, avec une **petite courbe de l'évolution sur une échelle logarithmique**, pour qu'on lise les variations relatives (passer de 6 à 12 mois pèse autant que de 12 à 24).

Contraintes mesurées, à afficher plutôt qu'à cacher :
- **« Depuis 2026 » n'existe pas vraiment** : les retraits ne sont fiables que depuis le 2026-07-28 (correctif de délistage), et sur toutes les sources seulement depuis le 2026-09-14. Libellé honnête : « depuis le 14 sept. 2026 », jusqu'à ce que l'historique s'allonge.
- La maille « 2 chambres ±15 % dans un district » sera souvent **sous le minimum** (30 actives, 10 retraits nets) : afficher « données insuffisantes » avec l'effectif, jamais un chiffre nu.
- La courbe de Bangkok a besoin d'un **point par semaine**, recalculé à date. Ce n'est pas stocké aujourd'hui, et il faut l'ajouter aux snapshots d'étude (`study/run_study.py`).
**Non fait** : aucun calcul de ces trois niveaux (la maquette porte des chiffres d'exemple) ; série hebdomadaire non construite.

## 2026-10-17 (suite 3) — « buyer's / seller's market » dépliable par une flèche (version rapport)
Demande de l'utilisateur : la jauge garde les libellés **buyer's market / balanced / seller's market**, et une **flèche** déplie le bloc pour **expliquer pourquoi**.
Le dépliage reprend les quatre signaux de l'indice de tension existant (`docs/methodes-calculs.md` §7), chacun affiché avec sa valeur, sa référence Bangkok, son sens (vers acheteur ou vers vendeur) et son effectif :
1. **Écoulement** : mois de stock, net de republications, face à la médiane de Bangkok.
2. **Pression vendeuse** : vendeurs actifs par immeuble.
3. **Tendance du stock** sur 3 mois.
4. **Momentum prix** : pente du prix/m² médian, et part des annonces qui ont baissé leur prix.
Une phrase de synthèse conclut (« 3 signals of 4 point to buyers »).
⚠ **Écart avec la proposition du même jour** (libellés relatifs) : en seuils absolus, 35 districts sur 36 seraient « buyer's market ». Les libellés sont donc à lire **par rapport à Bangkok**, et l'explication dépliée doit le dire (« slower than 80 % of Bangkok districts »), sinon le libellé promet plus que ce que la donnée mesure. Arbitrage laissé à l'utilisateur (règle 5).
**Non fait** : signaux non calculés à la maille de l'annonce ; seuils non fixés.
