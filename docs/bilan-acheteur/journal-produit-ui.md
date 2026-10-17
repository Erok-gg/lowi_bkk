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
