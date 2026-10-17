# Bilan acheteur — projet

> **Master du sous-projet.** Il présente le projet et pointe vers les journaux
> spécialisés, où vit le détail. Il se tient à jour ; les journaux, eux,
> s'écrivent en ajout seul.

## En une phrase
Un acheteur colle le lien de l'annonce qu'il convoite et reçoit un **bilan
neutre** : la place du prix face aux lots comparables, l'histoire de
l'annonce sur tous les portails, la pression vendeuse dans l'immeuble, la
tension du quartier, une fiche immeuble arbitrée et les drapeaux rouges. Le
bilan partiel est gratuit, le bilan complet payant.

## Pourquoi maintenant, et pourquoi nous
- **Le fonds est prématuré** ; le bilan exploite la donnée déjà collectée
  (5 sources, dédoublonnage, cohortes, rendement calculé dans l'immeuble) et
  construit une audience et une crédibilité qui pourront servir plus tard.
- **Différence retenue après le benchmark du 2026-10-17** : FazWaz, Hipflat
  et PropertyScout affichent déjà un verdict prix, et FazWaz et Hipflat des
  ventes réelles. Nous ne gagnons pas sur « l'écart à la médiane ». Nous
  gagnons sur **la neutralité** (ils sont payés par le vendeur), **l'histoire
  de l'annonce d'un portail à l'autre**, **la pression vendeuse en part des
  lots** et **des faits d'immeuble arbitrés avec leur niveau de confiance**.
  Détail : [benchmark-plateformes](benchmark-plateformes.md).

## Business model (état actuel)
- **Particulier** : partiel gratuit · bilan complet **à l'unité** · ou
  **pass de N jours** payé d'avance.
- **Agent** : ne paie rien ; **code apporteur** → **rétrocommission** sur les
  achats de ses acheteurs (v2, remplace la v1 où les pros payaient).
- **Règle de neutralité** : le contenu du bilan ne dépend jamais du code
  apporteur.
Détail et risques : [journal-business-model](journal-business-model.md).

## Journaux par sous-projet
| Journal | Porte sur |
|---|---|
| [benchmark-plateformes](benchmark-plateformes.md) | Concurrence : ce que 8 plateformes affichent, sur 10 immeubles du CBD |
| [journal-produit-ui](journal-produit-ui.md) | Contenu du bilan, bloc par bloc ; ce qui est gratuit ; comment l'afficher |
| [journal-business-model](journal-business-model.md) | Qui paie, combien ; programme apporteur ; risques |
| [journal-marketing](journal-marketing.md) | Cible, message, canaux, test des 20 bilans |
| [journal-donnees](journal-donnees.md) | Origine de chaque chiffre ; trous ; recensement des unités |
| [journal-juridique](journal-juridique.md) | Points à faire valider par un avocat thaï |

Le journal technique du dépôt ([docs/journal-technique.md](../journal-technique.md))
garde les entrées qui touchent au système (scripts, bases, agents).

## Code et données livrés
- `ops/recensement-unites.py` : liste de travail du recensement des unités
  (lecture seule de `bangkok.db`). La sortie
  `study/referentiel/recensement-unites.csv` est **hors dépôt** (dépôt
  public, le fichier contient des URL d'annonces).

## État
| | |
|---|---|
| Benchmark concurrence | ✅ v1 (2026-10-17) |
| Contenu du bilan | ✅ v1 sur le papier |
| Recensement des unités | 🟡 liste prête, 1 251 / 4 876 amorcés, aucun relevé manuel |
| Test de disposition à payer | ⬜ |
| Avis juridique | ⬜ |
| Interface | ⬜ |

## Questions ouvertes, à trancher par l'utilisateur
1. Collecter CondoMaps (source officielle) automatiquement, ou à la main ?
2. Où se calcule le bilan : sur PC2 puis remonté, ou en élargissant la
   fenêtre Supabase ? Aujourd'hui les blocs « histoire » et « pression » ne
   sont pas calculables depuis Vercel.
3. Prix du bilan, durée du pass, taux de rétrocommission.
4. Ordre : test manuel des 20 bilans **avant** l'interface (recommandé), ou
   l'inverse ?
