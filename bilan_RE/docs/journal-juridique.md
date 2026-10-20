# Journal — Juridique & conformité

> Ce qui doit être validé par un avocat thaï avant tout lancement payant.
> Ajout seul. Retour au projet : [README](README.md).

## 2026-10-17 — points ouverts (aucun n'est validé)

1. **Changement de posture.** Le dépôt est fondé sur un usage personnel non
   commercial (`CLAUDE.md`, « Posture scraping »). Un bilan payant y met fin :
   les conditions d'utilisation des portails s'appliquent à un usage
   commercial de données collectées chez eux.
2. **Pas de republication.** Ni photos, ni textes, ni liens vers les
   comparables. Le bilan ne livre que des chiffres dérivés, calculés à partir
   d'une annonce **que l'acheteur apporte lui-même**. À faire valider : ce
   périmètre suffit-il ?
3. **PDPA.** Nom et numéro de l'agent : ne pas les afficher. L'historique
   d'une annonce par agent (« cet agent republie ») porte sur une personne
   identifiable : à valider avant de l'afficher.
4. **Rétrocommission aux agents** : statut, facturation, retenue à la source,
   obligation d'information de l'acheteur. Mention prévue sur le bilan
   partagé : « recommandé par [agent] ».
5. **Sources publiques** : conditions d'utilisation de CondoMaps (Département
   des terres) pour une réutilisation commerciale, à lire avant toute
   collecte.
6. **Responsabilité** : le bilan n'est pas une expertise, et l'avertissement
   doit le dire (prix affichés et non vendus, pas un conseil en
   investissement).

### Non fait
Aucun avocat consulté.

## 2026-10-17 (suite) — projections de prix et barèmes fiscaux
7. **Scénarios de prix à 2, 3, 5 ans** dans un rapport payant vendu à un particulier : risque d'être assimilé à du conseil en investissement (SEC Thailand). À faire valider avant toute mise en ligne : formulation en scénarios conditionnels avec hypothèses affichées, aucune recommandation d'achat, avertissement.
8. **Hidden costs** : taux de taxe foncière, impôt sur les loyers et différences étranger/Thaï, résidence principale ou non, à faire valider par un fiscaliste. Aucun barème n'entre dans le code sans source datée.

## 2026-10-19 — report de la session « légalisation » du 2026-10-18
Points établis dans cette session et jamais reportés ici (aucun n'est validé par un avocat) :
9. **Format de la société thaïe** : c'est la **majorité du capital** qui décide. Avec des Thaïs majoritaires réels, il suffit d'ajuster l'objet social au DBD ; avec des **prête-noms**, c'est pénal (Foreign Business Act, art. 36) ; avec des étrangers majoritaires, le service relève de la List 3 et n'est pas autorisé tel quel. Questions en attente de l'utilisateur : forme (Co., Ltd ou partnership), répartition du capital, objet social actuel, permis de travail.
10. **Voies si le format ne convient pas** : promotion BOI (services numériques), Foreign Business License (≥ 3 M THB, long, incertain), vrai associé thaï à 51 %, ou vente depuis HK/SG avec TVA thaïe sur les services électroniques.
11. **Marque « Lowi »** : dépôt au DIP, classes 35, 36 et 42 ; recherche d'antériorité (nom d'un opérateur mobile en Espagne, risque surtout dans l'UE).
12. **Vocabulaire** : jamais « valuation » ni « appraisal » (réservés aux évaluateurs agréés) ; parler de « market analysis ». Vérifié le 2026-10-19 dans les textes de la beta (`bilan_RE/web`, `app/beta`) : aucune occurrence.
13. **Permis de travail** obligatoire si l'utilisateur travaille dans la société, même comme directeur (2 M THB de capital libéré et 4 salariés thaïs par permis, hors BOI).
14. Rétrocommission : facture et retenue à la source (3 % pour un service, à confirmer) ; TVA au-delà de 1,8 M THB de chiffre d'affaires par an ; CGV ; enregistrement du site au DBD.

## 2026-10-20 — transparence de la méthode : ligne arrêtée, annexe écrite
15. **Quoi divulguer d'une méthode qu'on vend.** Question posée par
    l'utilisateur. Ligne retenue, documentée dans
    [methodologies-de-reference.md](methodologies-de-reference.md) : **intrants,
    périmètre, date, limites et version sont publics ; poids, seuils et bornes
    ne le sont pas.** Ce n'est pas une tolérance de fait — IOSCO a amendé ses
    principes 4, 5 et 12 pour clarifier que la transparence exigée **n'équivaut
    pas** à une divulgation complète, et a retiré d'un projet antérieur
    l'exigence de pouvoir répliquer un niveau publié. Le plan de l'annexe suit
    la structure de divulgation RICS (étendue de l'investigation, sources,
    hypothèses, date) **sans se réclamer du standard** : le bilan n'est pas une
    expertise, et aucune mention de conformité ne doit apparaître.
16. **Annexe client livrée** : [annexe-methodologie-client.md](annexe-methodologie-client.md),
    à joindre identique à chaque bilan. Contraintes tenues et vérifiées par
    `grep` : aucune plateforme nommée, aucun décompte de sources, aucune
    constante chiffrée ; « valuation » et « appraisal » n'apparaissent qu'en
    négation (exigé par le point 6, interdit en affirmation par le point 12).
17. **Le vrai risque juridique n'est pas l'opacité de méthode, c'est la
    provenance** (point 1 ci-dessus). Le secret de méthode n'y change rien.
    Question à poser à l'avocat, formulée : *puis-je commercialiser des
    agrégats dérivés de données collectées sur des portails, et sous quelle
    entité ?*
18. **Trois obligations héritées du choix de l'opacité**, à tenir sinon le
    secret devient boîte noire : dire la date et la règle de révision ; dire ce
    qui n'est pas mesuré, **y compris que la précision des scores n'est pas
    encore établie** ; versionner et publier les changements de méthode.

### Non fait
- Textes primaires IOSCO et RICS **non lus** (403 sur `iosco.org`, Red Book non
  ouvert) : les formulations citées viennent de sources secondaires et sont
  marquées comme telles dans le fichier de référence.
- Deux arbitrages laissés à l'utilisateur, signalés en commentaire HTML dans
  l'annexe : publier ou non la part chiffrée des retraits qui sont des
  republications ; publier la liste datée des changements de méthode en annexe
  plutôt que sur demande.
- Aucun avocat consulté. Rien de ce qui précède n'est validé.

## 2026-10-20 (suite) — l'annexe est dans le produit
19. **Annexe branchée en fin de bilan**, écran et PDF (`bilan_RE/web/components/Annexe.tsx`). La version de méthode, la date des données et la fin de fenêtre y sont **résolues depuis la donnée**, plus des champs à remplir. L'avertissement final ferme le rapport.
20. **Les sources ne sont plus nommées nulle part dans le produit** — ni à l'écran, ni dans la charge utile de la page. Six endroits les nommaient, dont l'écran d'attente qui listait les cinq en clair, et la frise de l'historique qui les répétait ligne à ligne. Mesuré après correction : 0 occurrence sur les deux rendus.
21. **L'URL de l'annonce d'origine ne part plus vers le navigateur.** Elle était dans la charge utile alors que l'annexe affirme que le bilan ne reproduit « no listing, photograph, description or link ». Ce point rejoint le n° 2 (pas de republication) : il est désormais vrai dans le code, pas seulement dans le texte.

### Non fait
- **Aucun test ne garde ces contraintes.** Elles tiennent aujourd'hui par vérification manuelle (`grep`) ; une régression ne déclencherait rien. C'est le garde-fou à écrire avant toute mise en vente.
- `AnalyseForm.tsx` nomme encore un portail dans le `placeholder` du champ URL — laissé à l'arbitrage de l'utilisateur.
- Rien de ce qui précède n'est validé par un avocat.
