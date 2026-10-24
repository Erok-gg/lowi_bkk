# Backlog du bilan acheteur — toutes les idées demandées, avec leur état

> **Liste unique** créée le 2026-10-19, parce que les idées étaient éparpillées
> dans les entrées datées des journaux et que rien ne disait ce qui restait à
> faire. À tenir à jour : une idée nouvelle s'ajoute ici (avec sa date), son
> détail va dans le journal du sous-projet concerné.
> Retour au projet : [README](README.md).

Légende : ✅ fait · 🟡 en partie · 📝 spécifié, pas codé · ⬜ seulement évoqué

## 1. Ce que montre le bilan

| # | Idée (demandée le) | État | Où c'est décrit | Ce qui manque |
|---|---|---|---|---|
| 1 | Page simple : on colle l'URL d'une annonce, bilan gratuit (17/10) | ✅ | regles §1 | — |
| 2 | Chargement qui fait défiler les items calculés (17/10) | ✅ | regles §5 | — |
| 3 | Mobile + PC Full HD, disposition différente (17/10) | ✅ | regles §2, §7, §8 | test sur un vrai téléphone |
| 4 | Gros bouton PDF avec toutes les explications et visuels (17/10) | ✅ | regles §6 | PDF généré côté serveur (aujourd'hui : impression du navigateur) |
| 5 | Prix/m² face à l'immeuble, puis mêmes chambres et même surface, en visuel (17/10) | ✅ | journal-produit-ui suite 6 | — |
| 6 | Lots comparables **sans lien** (17/10) | ✅ | journal-produit-ui v1 | — |
| 7 | Historique de l'annonce : ancienneté, baisses, republications, portails (17/10) | ✅ | regles §4 | variation de prix multi-portails à revoir (« +1 % » malgré une baisse) |
| 8 | **Score de tension sur 100 et son évolution** (17/10) | 🟡 | methodes-calculs §12 | score ✅ ; **courbe d'évolution** absente (série hebdomadaire non stockée) |
| 9 | Tension du **district**, puis du **condo comparé à l'annonce** (jours sur le marché) (17/10) | 🟡 | journal-produit-ui suite | jours de l'annonce ✅ ; **médiane de l'immeuble et du district à côté** non affichée |
| 10 | Chaque mesure **quantifiée** (nombre d'échantillons) (17/10) | ✅ | regles §3 | — |
| 11 | Infobulle à 3 niveaux : 2 ch. même surface ±15 % · 2 ch. depuis 2026 · Bangkok le mois dernier avec **courbe log** (17/10) | 📝 | journal-produit-ui suite 2 | rien de codé ; « depuis 2026 » = depuis le 14/09 faute d'historique |
| 12 | Jauge buyer's / seller's market **dépliable par une flèche** qui explique pourquoi (17/10) | 🟡 | journal-produit-ui suite 3 | dépliant « months of supply » (bandes < 3 / 4–6 / > 6 mois) ajouté le 19/10 ; **l'explication signal par signal** reste à faire |
| 13 | Barres des signaux visibles **au dépliage** sur mobile (17/10) | ✅ | regles §8 | — |
| 14 | **Comparer au khet, à la rue**, et au CBD si le bien y est (17/10) | 🟡 | journal-produit-ui suite 4 | rue remplacée par un rayon de 1 km (mesuré : 4 lots par rue) ; zone CBD ✅ |
| 15 | **Sélecteurs en haut** (où / chambres / surface) pour voir l'impact d'un filtre ; tout afficher dans le rapport envoyé (17/10) | 📝 | journal-produit-ui suite 5 | web : seulement les pastilles du bloc prix ; rapport : matrice non construite |
| 16 | **Indicateur de liquidité** : jours sur le marché comparés par segment et dans le temps → score ; âge du bâtiment ; travaux après X années ; revente au prix du marché (17/10) | 🟡 | methodes-calculs §12 | codé mais **non publiable** avant ~3 mois de données ; **jalons de travaux à sourcer** (config vide) |
| 17 | **Part des unités de l'immeuble en vente** → recenser le nombre d'unités (17/10) | 🟡 | journal-donnees | liste de 4 876 immeubles prête, 1 251 amorcés ; décider de **CondoMaps** (source officielle) |
| 18 | **Avis sur le condominium** (17/10) | 🟡 | journal-produit-ui v1 | fiche immeuble (année, charges, lots en vente) ✅ ; pas d'avis de résidents (choix : pas de reprise d'avis tiers) |
| 19 | **Perspectives patrimoniales / wealth management** : 3 scénarios de prix à 2, 3, 5 ans selon école, métro, date de construction, transactions, plans d'aménagement, événements du quartier, marque et entretien, **bruit (IA)**, trafic… (17/10) | 📝 | journal-produit-ui suite 6 | modèle hédonique + indice externe (REIC/BOT) à brancher ; **événements de quartier : aucune source** ; risque SEC (juridique) |
| 20 | **Hidden costs** : charges face à des immeubles à équipements comparables et selon l'âge, taxes annuelles, et **les différences** (étranger/Thaï, résidence principale, revente < 5 ans…) (17/10) | 📝 | journal-produit-ui suite 6 | charges : FazWaz seul (1 199 immeubles) ; barèmes **à valider par un fiscaliste** |
| 21 | **If you rent it** : frais d'agent, rendement net, etc. (17/10) | 📝 | journal-produit-ui suite 6 | délai de location à calculer sur les cohortes locatives |
| 22 | **Simulateur de location** (17/10) | 📝 | journal-produit-ui suite 6 | effet du loyer sur le délai à mesurer |
| 23 | **Simulateur de prix après rénovation** (17/10) | 📝 | journal-produit-ui suite 6 | « rénové » à extraire des descriptions et à valider à la main |
| 24 | Mention **« calcul mensuel »** (17/10) | ✅ | regles §3 | — |

## 2. Service et technique

| # | Idée (demandée le) | État | Où c'est décrit | Ce qui manque |
|---|---|---|---|---|
| 25 | Une page par demande ; à l'achat : rapport généré, **envoyé par mail**, page gardée dans l'app ou téléchargeable (17/10) | 🟡 | journal-produit-ui suite 7 | page + PDF ✅ ; **compte (e-mail seul, mot de passe généré), mail, « Mes rapports »** ✅ le 19/10 ; **paiement** et « Refresh » non faits |
| 26 | Plusieurs demandes simultanées : **6 max, sinon file**, avec nombre de requêtes traitées et temps estimé (17/10) | ✅ | regles §14–15 | file perdue au redémarrage du serveur |
| 27 | Vitesse : CPU/GPU, index (17/10) | ✅ | regles §16 | bilan 10 s → 1,4 s ; banc d'essai sur un autre PC non lancé |
| 28 | Script qui **répertorie les annonces après le scrap** (17/10) | ✅ | agent `repertorier-annonces` | premier cycle de nuit à vérifier |
| 29 | Le bilan en **service en ligne** (Vercel ne joint pas PC2) (17/10) | ⬜ | README, question ouverte 2 | choisir : pré-calcul nocturne remonté, ou file d'attente vers PC2 |
| 43 | **Landing publique** sans accès à la carte, nav réduite à connexion / inscription (19/10) | ✅ | journal-technique 19/10 (suite) | ouverture conditionnée à `LOWI_BETA_PUBLIQUE=1`, **non posée** : décision de posture |
| 44 | **Comptes** : on ne demande que l'e-mail, mot de passe aléatoire envoyé par mail (19/10) | ✅ | journal-technique 19/10 (suite) | changement de mot de passe : route faite, **pas d'écran** |
| 45 | **DB modulaire** avec les colonnes du paiement (nom / prénom / naissance / nationalité) (19/10) | ✅ | `bilan_RE/web/lib/comptes-schema.ts` | colonnes créées et **vides** : aucun paiement branché |
| 46 | **Encart RGPD / PDPA** et acceptation des cookies (19/10) | 🟡 | `/beta/privacy` | bandeau + preuve en base ✅ ; **notice non validée par un juriste** (régime et responsable de traitement dépendent de la forme sociale, §4) |
| 47 | **Anglais / thaï / chinois** (19/10) | 🟡 | `bilan_RE/web/i18n/` | landing, nav, comptes, bandeau, notice et e-mails ✅ ; **corps du bilan encore en anglais** ; traductions **non relues par un natif** |

## 3. Business model

| # | Idée (demandée le) | État | Où |
|---|---|---|---|
| 30 | Particulier : bilan **partiel gratuit**, complet **à l'unité**, ou **pass de N jours** (17/10) | 📝 | journal-business-model |
| 31 | **Agent : ne paie rien**, pousse l'acheteur avec un **code**, touche une **rétrocommission** (17/10) — remplace la v1 où les pros payaient | 📝 | journal-business-model v2 |
| 32 | Prix, durée du pass, taux de rétrocommission | ⬜ | à trancher |

## 4. Légal (session « légalisation » du 18/10, non reportée jusque-là)

| # | Point | État |
|---|---|---|
| 33 | Format de ta société thaïe : **qui détient la majorité du capital** décide de tout (Foreign Business Act, List 3) ; prête-noms = pénal | ⬜ 4 questions en attente de ta réponse (forme, capital, objet social, permis de travail) |
| 34 | Voies si le format ne va pas : promotion **BOI**, Foreign Business License, vrai associé thaï à 51 %, ou vente depuis HK/SG avec **TVA e-service** | ⬜ |
| 35 | **Marque « Lowi »** au DIP, classes 35/36/42 ; recherche d'antériorité (opérateur mobile espagnol) | ⬜ |
| 36 | Ne jamais dire **« valuation » / « appraisal »** (réservé aux évaluateurs agréés) : « market analysis » | ⬜ à vérifier dans les textes de la beta |
| 37 | **Permis de travail** si tu travailles dans la société thaïe | ⬜ |
| 38 | CGU des portails pour un usage commercial ; PDPA ; CGV ; retenue à la source sur la rétrocommission ; TVA au-delà de 1,8 M THB | ⬜ voir journal-juridique |

## 5. Défauts repérés en route, à corriger

| # | Défaut | Mesuré le |
|---|---|---|
| 39 | **Nestopa** stocke le titre de l'annonce comme nom d'immeuble (« The Address Siam Ratchathewi 31.5 sqm Condo in Bangkok ») : aucun rapprochement avec l'immeuble | 19/10 |
| 40 | **LivingInsider** bloqué par AWS WAF depuis le 16/09 : plus aucune annonce nouvelle | 17/10 |
| 41 | **Délistage DDproperty à l'arrêt** depuis le 13/10 : aucune fenêtre de score n'a encore DDproperty et FazWaz sains ensemble | 17/10 |
| 42 | Texte des réglettes trop grand dans le PDF | 17/10 |

## 6. Différenciateurs issus du relevé n°2 (22/10)

> Source : [benchmark-plateformes](benchmark-plateformes.md), relevé du 22/10
> (un lot suivi sur 5 portails). Retenus parce que **aucun portail ne les
> montre** et qu'ils ne reposent ni sur la neutralité, ni sur une formule
> propriétaire, ni sur la valeur du jeu agrégé. Ordre = priorité proposée.

| # | Idée (demandée le) | État | Ce qui existe | Ce qui manque |
|---|---|---|---|---|
| 48 | **Fiche « même bien, tous les portails »** : échelle des prix (ici 5,25 → 5,50 M, 4,8 %), qui vend (propriétaire / agents), lien vers l'annonce la moins chère, **capture datée** de chaque annonce (22/10) | 🟡 | histoire d'annonce multi-portails (#7), `repost_of`, `price_history` | **étage absent sur DDproperty et PropertyHub** → « même lot » seulement déduit pour 3 portails sur 5 ; captures d'écran archivées : rien ; DDproperty/LivingInsider fiches illisibles aujourd'hui ; couverture PropertyHub 14 / 326 |
| 49 | **« Ce que l'annonce ne dit pas »** : champs absents ou contradictoires (étage, quota, charges, surface mezzanine incluse ou non) → questions à poser à l'agent, message prêt EN/TH (22/10) | ⬜ | les colonnes `d_*` savent dire « absent » par portail | règle de détection des contradictions ; gabarits de message (EN, TH) ; relecture d'un natif |
| 50 | **Kit de négociation** : leviers factuels (ancienneté réelle, baisses, lots concurrents identiques, type d'annonceur) + message d'offre (22/10) | ⬜ | ancienneté et baisses déjà calculées | ~~règle d'ancienneté `min(first_seen, date source)`~~ **livrée le 22/10 pour PropertyScout seul** (colonne locale `listed_at_source`, 4 020 lignes rattrapées, `rapport.py`) ; reste à tester FazWaz, à regarder une date de 2018, et à afficher « ancienneté déclarée par le portail » dans le bilan (`premier_vu_declare_par` existe dans le JSON, pas dans l'UI) ; formulation à faire valider (ne pas promettre un rabais) |
| 51 | **Veille après achat du bilan** : alerte si le prix baisse sur un portail, si l'annonce disparaît, ou si un lot identique moins cher apparaît (22/10) | ⬜ | scraps quotidiens, `price_history`, délistage | abonnement par lot ; envoi (le mail passe par un dépôt dans `agents/queue/mail/`, minutes de latence) ; lien avec le **pass de N jours** (#30) |
| 52 | **Coût total à la signature et en détention, pour un étranger** (22/10) | 📝 | c'est le #20 | barèmes à **valider par un fiscaliste** ; charges connues pour 1 199 immeubles seulement |
| 53 | **Faits de vie courante** : ascenseurs par lot (ici 4 pour 726), parking (70 % de places, automatisé) (22/10) | ⬜ | FazWaz publie ces champs sur la page projet | collecte de ces champs (aujourd'hui non stockés) ; seuil « beaucoup / peu » à choisir sans prétendre à une norme |
| 54 | **Ventes conclues** des portails, **tenues à l'écart** des annonces et affichées « source faible » (22/10) | 🟡 | **FazWaz livré le 22/10** : tables locales `ventes_portail` + `ventes_portail_projets`, collecte dans le scrap (page d'immeuble déjà lue), bloc « Reported sales » étiqueté, médiane dès 5 ventes comparables / 36 mois, synthèse du portail citée (29 ventes, 715 j, −7 %) | **jamais tourné en production** ; rattrapage étalé (~15 runs) ; **Hipflat** (moyennes en prose, USD, pas de lignes de ventes sur 1 projet testé), **PropertyScout** (API Market stats non identifiée), DDproperty, LivingInsider : non faits ; origine des prix inconnue ; droits d'usage à valider (#38) ; affichage non vu dans un navigateur |
| 55 | **Mesure mensuelle de statistiques générales**, lancée une fois la liste des questions arrêtée — première question en attente : la rénovation fait-elle monter le loyer ? (22/10) | ⬜ | calcul par immeuble dans `rapport.py` (`_renovation`), bloc du bilan en « Coming soon » ; deux règles chiffrées au journal technique du 22/10 (≥ 3 rénovées / ≥ 5 autres, ou tirage au sort dans l'immeuble) | la liste complète des questions ; le choix de la règle ; un agent mensuel (comme `scores-tension`) |

**À éviter** : un verdict « sous/sur-évalué » ou une estimation de plus. FazWaz
et PropertyScout en ont déjà ; le relevé montre en plus que leurs références ne
se recoupent pas entre elles.
