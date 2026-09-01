# Note de conjoncture — septembre 2026

*Édition du 2026-09-01. Étude complète : [etude-2026-09-01.md](etude-2026-09-01.md).
Corpus : 67 478 annonces actives (34 374 ventes / 33 104 locations), 3 682 immeubles.
Rapport généré automatiquement (tâche planifiée `rapport-mensuel-lowi-bkk`), exécuté depuis PC1 (`BB-12`).*

---

## ⚠ À lire avant les chiffres

**Deux réserves de méthode, distinctes l'une de l'autre.**

**1. Le corpus a encore bondi (+50 % en 10 jours, 44 960 → 67 478 actives).**
Ce n'est pas une envolée de l'offre : `scan_runs` n'a plus une seule ligne écrite
depuis le 2026-08-22 (vérifié en base — la table de journalisation des scans
n'est simplement plus alimentée depuis la bascule vers le système d'agents), mais
la table `listings` elle-même montre une activité continue jusqu'au 31/08, avec un
pic massif ce jour-là (54 903 lignes DDproperty touchées en une fois). C'est un
grand scan de rattrapage, pas une hausse de la demande. Le tableau « à panier
constant » (immeubles présents aux deux dates) neutralise en partie l'effet —
c'est la table à lire ci-dessous, pas les totaux bruts — mais elle ne neutralise
pas une composition différente d'annonces *au sein* d'un même immeuble déjà connu
(l'August scan a pu remonter d'autres étages/unités du même bâtiment). Les
amplitudes ci-dessous doivent donc être lues comme des tendances, pas des mesures
précises — l'édition d'octobre, sur un corpus qui aura eu le temps de se
stabiliser, tranchera.

**2. `scan_runs` est un indicateur de fraîcheur mort, et personne ne le savait.**
Voir la section Alertes : c'est le fait technique le plus important de cette
édition, indépendamment du marché.

---

## Les 5 mouvements les plus significatifs (panier constant, 2026-08-22 → 2026-09-01)

*Immeubles présents aux deux dates uniquement — insensible à l'arrivée de nouveaux
immeubles. n = nombre d'immeubles appariés.*

| # | Quartier | Grandeur | Δ | n immeubles | Lecture |
|---|---|---|---:|---:|---|
| 1 | **Rive ouest (Thon Buri, Bang Kho Laem, Bang Phlat)** | prix/m² vente | **+6,0 à +6,9 %** | 24–42 | Trois quartiers contigus, même sens, loyer qui suit (+2,6 à +3,2 %) — le motif le plus cohérent de l'édition |
| 2 | **Corridor sud-est (Yan Nawa, Bang Na, Suan Luang)** | prix/m² vente | **+4,2 à +5,3 %** | 48–69 | Même lecture : vente et loyer montent ensemble (loyer +4,9 à +6,2 %), échantillons larges (≥48 immeubles) |
| 3 | **Carte de tension — refroidissement généralisé** | score composite | Bang Kapi 64→25, Suan Luang 68→52, Prawet 57→41, Bang Phlat 51→26, Bang Khae 61→48 | — | Vraisemblablement un artefact du même afflux d'annonces (la pression vendeuse est un ratio annonces/immeuble — plus d'annonces la dilue mécaniquement) plutôt qu'un vrai relâchement de la demande. Voir captures ci-dessous. |
| 4 | **Carte des rendements — périphérie qui se resserre** | rendement WC | Prawet 8,7 %→6,4 %, Khan Na Yao 8,3 %→5,9 %, Lat Phrao 7,6 %→10,5 % (sens inverse) | — | Les rendements extrêmes des quartiers *low sample* de l'édition d'août se rapprochent de la médiane à mesure que l'échantillon grossit — régression vers la moyenne attendue, pas un mouvement de marché |
| 5 | **Nuea Vadhana — délistage** | churn (3 j) | 41,4 %→48,2 % (+6,8 pt) | — | Seul mouvement de tension qui *monte* nettement ; sous-secteur de Vadhana, à suivre mais échantillon restreint |

**Aucune recommandation d'achat ne doit s'appuyer seule sur les lignes 3 et 4** :
la lecture la plus probable est méthodologique (composition du corpus), pas de
marché. Les lignes 1 et 2 sont plus solides — même sens vente/loyer, échantillons
≥24 immeubles — mais restent à confirmer sur un cycle où le corpus n'aura pas
bougé de moitié entre deux mesures.

### Captures — déplacement géographique

Comparées à l'édition d'août ([docs/etudes/captures/2026-08/](captures/2026-08/)),
les cartes de septembre ([docs/etudes/captures/2026-09/](captures/2026-09/))
montrent :
- **Tension** : la quasi-totalité de la carte se refroidit (orange→bleu-gris),
  Bang Kapi et Suan Luang en tête — cf. réserve ci-dessus.
- **Rendements** : le couloir est (Lat Krabang, Min Buri) reste la zone la plus
  rémunératrice mais se resserre ; Lat Phrao (nouvellement bien peuplé en
  annonces) passe à 10,5 %, le point le plus haut de la carte — à vérifier au
  prochain cycle avant d'y voir un signal.

---

## Contexte externe (veille du 2026-09-01)

**Lignes MRT — aucun changement acté.** Orange Est toujours ciblée 2028 (gros
œuvre achevé), Orange Ouest juillet 2030 ; Purple Sud proche de son calendrier.
Rien qui modifie la fenêtre d'achat décrite dans `study/context.md`.

**4e révision du plan d'urbanisme — calendrier précisé, rien de nouveau acté.**
L'enquête publique de 90 jours a démarré en juin 2026 (après l'approbation du
comité en avril, déjà connue) ; la promulgation est désormais visée fin 2027
(~septembre 2027) plutôt qu'un vague « 2027 ». Mis à jour dans `study/context.md`
(entrée datée 2026-09-01).

**HSR 3 aéroports — le blocage s'est aggravé, à suivre de près.** Le groupe CP a
formellement demandé la résiliation du contrat le 09/07/2026 (défaut d'agrément
BOI) et l'a réitéré le 27/08/2026. Le dossier est devant le comité de politique
EEC (présidé par le PM Anutin), arbitrage attendu depuis août — issue inconnue à
ce jour. Si résiliation actée, la gestion de l'Airport Rail Link est liée au même
contrat. Mis à jour dans `study/context.md`. **Aucun couloir de la carte n'en
dépend** (déjà classé « options longues, cible 2032+ »), donc pas d'impact sur la
méthode de sélection des opportunités — seulement sur le narratif de contexte.

**Indice officiel — pas de nouvelle publication trimestrielle confirmée.**
`study/official/bot-manual.json` reste à l'entrée unique 2025-Q1 (163,3, +3,6 %
y/y). Une recherche web fait apparaître un chiffre de 204,1 (mai 2026, +3,6 %
y/y) mais sur une base/série non identifiée avec certitude comme la même que
163,3 — **non ajouté au fichier officiel** faute de pouvoir vérifier qu'il s'agit
de la même définition d'indice (règle n°1 : ne pas mélanger une mesure vérifiée
et une donnée non recoupée). Point utile trouvé en revanche : les transferts de
condos ont progressé de +9,3 % en volume au T1 2026 (23 837 unités) pour une
valeur quasi stable (+0,8 %) — cohérent avec un marché qui écoule du stock à prix
plat plutôt qu'en hausse, et cohérent avec la lecture prudente ci-dessus sur les
mouvements de prix.

---

## Recommandation

**Ne pas sur-interpréter cette édition.** Le corpus a encore doublé de taille
entre deux mesures consécutives — deuxième fois en trois mois (juillet, puis
maintenant). La vraie contribution méthodologique de septembre est d'avoir
confirmé que le panier constant absorbe l'essentiel du bruit (lignes 1-2
crédibles), mais pas tout (lignes 3-4 probablement artefactuelles).

Deux actions concrètes :
1. **Attendre l'édition d'octobre** pour juger si la rive ouest et le corridor
   sud-est (ligne 1-2) confirment leur hausse sur un corpus stable — c'est la
   première vraie candidate à un signal de marché depuis le lancement du
   framework.
2. **Vérifier côté PC2 pourquoi `scan_runs` ne s'écrit plus** (voir Alertes) —
   indépendant du marché, mais ça prive toute mesure de fraîcheur future d'un
   signal fiable si ça n'est pas corrigé.

---

## Alertes

**`scan_runs` ne s'écrit plus depuis le 2026-08-22 — la table de fraîcheur du
projet est un garde-fou éteint.** Le protocole de cette tâche vérifie
normalement la fraîcheur des données via `MAX(scan_runs.started_at)` ; il aurait
dû déclencher un scrap complet aujourd'hui (dernière ligne il y a 10 jours). Il
ne l'a pas fait : une lecture directe de `listings.last_seen` montre une activité
réelle jusqu'au 31/08, y compris un scan complet ce jour-là. Le pipeline
fonctionne, seule sa table de journalisation historique ne suit plus — vraisemblablement
parce que le système d'agents (bascule du 2026-08-22, voir CLAUDE.md « Système
d'agents ») écrit dans `listings` sans repasser par le `scan_runs` de l'ancien
`run.py`. **Aucun scrap n'a donc été relancé par cette édition** — l'aurait été
à tort, PC1 ne devant plus scraper (voir ci-dessous) et les données étant en
réalité fraîches. Non corrigé : la table `scan_runs` elle-même, qui reste un
angle mort pour toute future vérification automatique de fraîcheur tant qu'elle
n'est pas rebranchée ou remplacée par une requête sur `listings`/le ledger des
agents.

**Cette édition tourne sur PC1 (`BB-12`), qui ne scrape plus depuis le
2026-08-22** (`CLAUDE.md` § « Les deux postes » — tâches `LowiBKK-*` `Disabled`,
confirmé par `Get-ScheduledTask` en début de run). Étape 1 du protocole
(lancement de scraps si données périmées) a donc été **volontairement sautée** :
lancer un scrap complet depuis PC1 aurait fait tourner deux machines en
parallèle sur les mêmes sources, exactement le risque documenté dans
`ops/menage-a-refaire-sur-pc2.md`. Les données étant par ailleurs fraîches
(ci-dessus), ce n'était de toute façon pas nécessaire ce mois-ci — mais si
`scan_runs` reste mort, une prochaine édition pourrait se fier à tort à ce signal
et lancer un scrap depuis le mauvais poste. À corriger avant l'édition d'octobre.

**Branche `menage/grappe-supervision-pre-agents` en écart avec `origin/main`,
non fusionnée.** Trois commits de nettoyage faits sur PC1 le 22/08 (retrait de
lanceurs Windows, coupure des fiches HTML) restent sur une branche locale non
poussée ; entre-temps, PC2 a poussé 9 commits sur `main` le même jour, dont un
ménage de sa propre grappe de supervision qui pourrait recouper — ou contredire —
le travail de PC1. Cette édition n'a pas touché à cette branche (hors périmètre
du rapport mensuel) ; elle a travaillé sur `main` synchronisé avec `origin`. **À
arbitrer par l'utilisateur** : comparer les deux ménages avant de fusionner ou
d'abandonner la branche PC1.

**Purge archive : rien à purger.** `ops/sync_supabase_local.py --prune` n'a
trouvé aucune candidate (délistée >90 j vérifiée en archive) — cohérent avec un
projet dont l'essentiel du stock inactif date de moins de 3 mois.

**Étude générée avec `run.py` non lancé, mais toutes les autres étapes (étude,
captures, archive) sur des données réelles et fraîches.**

---

## Sources

- [Bangkok Post — Orange Line due to fully open in 2030](https://www.bangkokpost.com/thailand/general/2832487/orange-line-due-to-fully-open-in-2030)
- [Nation Thailand — Bangkok fast-tracks 4th city plan revision](https://www.nationthailand.com/news/general/40062056)
- [Lexology — Proposed 4th Revision of the Bangkok Unitary Town Plan](https://www.lexology.com/library/detail.aspx?g=a644876b-604e-4201-9e52-5c5887b80652)
- [Nation Thailand — Airport rail deal faces July 15 review](https://www.nationthailand.com/business/investment/40068498)
- [Khaosod English — CP reaffirms to terminate 3-airport high-speed rail contract (27/08/2026)](https://www.khaosodenglish.com/politics/2026/08/27/cp-reaffirms-to-terminate-3-airport-high-speed-rail-contract-and-operation-of-the-airport-rail-link/amp/)
- [The Star — CP Group seeks termination of contract (09/07/2026)](https://www.thestar.com.my/aseanplus/aseanplus-news/2026/07/09/thailand039s-cp-group-seeks-termination-of-three-airport-high-speed-rail-contract)
- [Global Property Guide — Thailand's Residential Property Market Analysis 2026](https://www.globalpropertyguide.com/asia/thailand/price-history)
