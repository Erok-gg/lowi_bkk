# Journal — Business model

> Qui paie, combien, pour quoi. Ajout seul : une décision remplacée reste
> écrite, suivie de celle qui la remplace.
> Retour au projet : [README](README.md).

## 2026-10-17 — v1 : particuliers payants, pros payants (remplacée le même jour)
- **Particulier** : bilan partiel gratuit ; bilan complet payé **à l'unité** ;
  ou **un pass de N jours** payé d'avance (bilans illimités pendant la
  période de recherche).
- **Professionnel** : paie pour afficher son annonce **avec le bilan en
  dessous** et la partager à ses clients ; abonnement mensuel, ou lot de 10
  bilans avec remise.

## 2026-10-17 — v2 : l'agent ne paie rien, il est apporteur (décision de l'utilisateur)
**Remplace le volet professionnel de la v1.** Le volet particulier est
inchangé.

- **L'agent ne paie rien.** Il oriente ses acheteurs vers le bilan avec un
  **code apporteur** personnel.
- Sur chaque achat (bilan unitaire ou pass) fait avec son code, il touche une
  **rétrocommission**.
- L'acheteur reste le **seul payeur**. Le revenu vient de l'acheteur, le
  canal de distribution vient de l'agent.

### Ce que la v2 change, et les risques à traiter
1. **Biais de sélection, quasi certain.** Un agent vendeur ne poussera le
   bilan que sur les annonces qu'il juge flatteuses. Sur une annonce
   sur-évaluée, il n'a aucun intérêt à le partager. Le canal agent va donc
   surtout amener des bilans favorables. Rien de grave pour le revenu, mais
   **la réputation de neutralité se joue sur les autres**.
2. **Neutralité : règle non négociable.** Le contenu du bilan ne dépend pas
   du code apporteur. Le bilan partagé porte la mention « recommandé par
   [agent] — Lowi ne perçoit rien du vendeur ». Sans cette règle, on devient
   un PropertyScout de plus (voir [benchmark](benchmark-plateformes.md),
   constat 3).
3. **Agent de l'acheteur contre agent du vendeur.** L'agent qui accompagne un
   acheteur (relocation, conseiller en gestion de patrimoine, agent acheteur)
   a un intérêt aligné : le bilan l'aide à négocier. **C'est la cible
   naturelle du programme apporteur.** Le réseau de conseillers (Equance)
   entre ici.
4. **Fraude au code** : un acheteur qui utilise le code d'un proche pour se
   rembourser une part. C'est un détail à faible volume : un plafond par code
   et une commission versée au-delà d'un seuil suffisent.
5. **Ce que la v2 abandonne** : un revenu récurrent côté pros (l'abonnement
   mensuel de la v1). Le revenu devient 100 % particulier, donc ponctuel : on
   achète un condo rarement. La rétention se construit sur le **pass de N
   jours**, pas sur l'abonnement.

### Paramètres à chiffrer (rien n'est fixé)
| Paramètre | Fourchette de départ | Comment trancher |
|---|---|---|
| Prix du bilan unitaire | 290 – 990 THB | Test réel (cf. marketing) |
| Pass | 7 j / 30 j, ~2 à 4 bilans unitaires | Nombre moyen d'annonces comparées par acheteur, inconnu |
| Rétrocommission | 20 – 40 % du payé | Assez pour motiver, assez bas pour rester rentable |
| Partiel gratuit | Blocs ✅ du [journal UI](journal-produit-ui.md) | Taux de conversion partiel → complet |
| Paiement | PromptPay / carte (Omise, Stripe TH) | Non étudié |

Ordre de grandeur, **non mesuré** : un agent acheteur facture 1 à 3 % d'un
achat de 5 à 15 M THB. Un bilan à 500 THB est sans commune mesure avec ce
qui est en jeu, donc le prix n'est pas le frein. La confiance l'est.

### Non fait
- Aucun prix fixé, aucun test de disposition à payer.
- Fiscalité et statut de la rétrocommission en Thaïlande (retenue à la
  source, facturation) non étudiés : voir [journal-juridique](journal-juridique.md).
- Le lien avec le projet de fonds n'est pas tranché. Le
  bilan comme porte d'entrée vers le fonds est une piste, pas une décision.
