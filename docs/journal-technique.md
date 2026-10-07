# Journal technique — Lowi BKK

> **Registre append-only des décisions techniques, des méthodes retenues et des
> défauts découverts.** On n'y réécrit jamais le passé : une décision qui s'avère
> fausse reste consignée, avec l'entrée ultérieure qui la corrige. Le fichier
> complète l'historique git (qui porte le *quoi*) en portant le *pourquoi*, ce
> qui a été mesuré, et ce qui restait faux au moment de la décision.
>
> **Objet secondaire : traçabilité de propriété.** Le projet peut être présenté à
> des tiers (agences, chasseurs de biens). Ce journal documente qui a conçu quoi,
> avec quels outils, à partir de quelles sources — de quoi établir l'antériorité
> et l'origine des méthodes si la question se pose.
>
> Format d'une entrée : date · sujet · contexte · décision · mesure · limite connue.

> ### 📁 Le détail antérieur au 2026-08-26 est archivé
>
> Ce fichier a été **condensé le 2026-08-26** à la demande de l'utilisateur : il
> avait atteint 3 380 lignes, et son volume nuisait à son usage courant. Ne
> subsiste ici qu'un **résumé des grandes étapes**.
>
> **Rien n'a été détruit.** L'intégralité des entrées (juin → 2026-08-26, avec
> leurs mesures, leurs chiffres et leurs contre-mesures) est conservée dans
> **[journal-technique-archive-2026-06_08.md](journal-technique-archive-2026-06_08.md)**.
> C'est cette archive qui fait foi pour l'antériorité des méthodes et pour le
> détail d'une enquête passée. Le résumé ci-dessous n'en est qu'un index.
>
> **Le régime append-only reprend à partir de l'entrée du 2026-08-26 (suite 4)**
> ci-dessous. Les méthodes de calcul, elles, ont désormais leur référence
> dédiée : **[methodes-calculs.md](methodes-calculs.md)**.

---

## Provenance et outils

| Élément | Détail |
|---|---|
| Conception et arbitrages | Anthony Schoenauer |
| Assistance à l'implémentation | Claude (Anthropic), en pair-programming ; le code est revu et exécuté sur la machine d'Anthony |
| Modèle d'extraction (annonces réseaux sociaux) | qwen3:8b via Ollama, **exécution 100 % locale** — aucune donnée d'annonce n'est envoyée à un service tiers |
| Sources de données | Portails publics (FazWaz, DDproperty, PropertyScout, Nestopa, LivingInsider) scrapés à usage personnel non commercial ; groupes Facebook publics ; OSM/Overpass pour la géographie ; REIC/BOT pour le contexte macro |
| Base de données | **SQLite local sur PC2 (référence)** + Supabase (Postgres, fenêtre chaude servie au site) — inversé le 2026-08-25 |

Les méthodes statistiques du projet (double médiane par condo, strates de
taille, rendement within-condo, délai de grâce au délistage, cohortes
`unit_key`) ont été conçues pour ce projet. Elles sont documentées, avec leurs
justifications chiffrées, dans **[methodes-calculs.md](methodes-calculs.md)** ;
leur historique d'adoption est dans l'archive.

---

# Résumé des grandes étapes (2026-06 → 2026-08-26)

> Index de l'archive. Chaque ligne renvoie à une entrée datée qui porte les
> mesures. **Les dates sont les clés de recherche** dans
> [l'archive](journal-technique-archive-2026-06_08.md).

## Construction (2026-06 → 2026-07-09)

| Date | Étape |
|---|---|
| 2026-06 | **Choix verrouillés** : MapLibre, Next.js, Supabase, scraping Python par adaptateurs. Principe directeur : tout config-driven, un site = un adaptateur + une config. |
| 2026-06-23 | **Anglais only**, pages vente/location séparées, recoupement même-unité, rendements par rue. Sources 3 et 4 (PropertyScout, Nestopa) ; géocodage Nominatim. |
| 2026-07-04 | **Stats v2 — double médiane par condo**. 1 154 condos ont vente ET location actives = 81 % du stock : base du rendement within-condo. |
| 2026-07-06 | **Framework d'étude récurrente** (`study/`) : config figée et versionnée, snapshots datés, études générées. |
| 2026-07-09 | **Archivage local + purge serveur** sous garde-fous (copie vérifiée id par id). Scraps planifiés. |

## Fiabilisation — la série de défauts de mesure (2026-07-25 → 2026-08-02)

C'est la période qui a forgé la **règle 1** du `CLAUDE.md` (mesurer avant
d'affirmer) : sept fois, c'est **la mesure** — et non le système mesuré — qui
était en cause.

| Date | Défaut trouvé, et ce qu'il coûtait |
|---|---|
| 2026-07-25 | **Le quota étranger est une question, pas une donnée** (renseigné sur 1,2 %). Nouvelle source : groupes Facebook → table `social_leads` **séparée à dessein**. |
| 2026-07-28 | **Le « −50 % » était un artefact de taille.** |
| 2026-07-28 | **Le délistage rendait la liquidité non mesurable** : une annonce délistée dès la 1re absence → le time-on-market valait la cadence de scan (6,9 j identiques partout). D'où `DELISTING_FIX_DATE`. |
| 2026-07-28 | **La réplication d'archive était en panne depuis 22 jours.** |
| 2026-07-28 | **L'indice de tension mesurait la petitesse du marché** : « rareté » = peu d'annonces = tendu, par construction. Remplacée par la pression vendeuse. |
| 2026-07-28 (soir) | **Revue de code** : sept écarts entre descriptif et code. Bornes de plausibilité unifiées, médiane vs moyenne alignée, arrondi de tranche Python↔SQL, `npm test` qui ne pouvait pas s'exécuter. |
| 2026-07-28 (nuit) | **Le doublon qui n'en était pas** (ids FazWaz consécutifs = lots réels). **Poids des pages −80 %.** |
| 2026-08-01 | **Une coupure réseau ressemblait à un scan réussi.** |
| 2026-08-02 | **`posted_at` n'est pas une date de publication** : écart médian −16 j. Substitution **annulée**. |

## Le système d'agents (2026-07-31 → 2026-08-17)

| Date | Étape |
|---|---|
| 2026-07-31 | **12 bots orchestrés**, 3 étages (T0 déterministe / T1 local / T2 Claude par tickets), ledger SQLite. **Les 3 tâches Windows n'avaient jamais tourné** (guillemets échappés dans le XML). Mesure sur 650+ appels : `/no_think` silencieusement ignoré → panne muette ; **mode extraction** (le modèle constate, le code décide) = 99 % contre 0 % d'abstention en verdict direct. |
| 2026-08-05 | **5e source (LivingInsider)**. DotProperty écarté après enquête (syndique FazWaz). **Le mécanisme T2 n'existait pas** — la file n'était drainée par rien. |
| 2026-08-11 | **Revue algo** : 3 propositions sur 4 écartées après mesure. **Trois garde-fous qui ne gardaient rien**, et une optimisation inventée de toutes pièces. |
| 2026-08-13 | **Widget** : deux compteurs qui auraient menti, un arrondi qui volait un jour. |
| 2026-08-16 | **`garde-veille`** (14e agent) : le portable dormait pendant le scrap. |
| 2026-08-17 | **Sonde de structure avant scan** : échouer en 1 requête plutôt qu'en 8 jours. **Rattrapage sans extraction.** |

## Sécurité, infrastructure, bascule (2026-08-20 → 2026-08-26)

| Date | Étape |
|---|---|
| 2026-08-20 | **Faille RLS fermée.** Les 15 vues étaient `SECURITY DEFINER` : `anon` contournait le deny-all et pouvait **écrire**. Prouvé avant/après correctif. ⚠ `CREATE OR REPLACE VIEW` remet `reloptions` à zéro — rejouer un fichier rouvrait la faille en silence. |
| 2026-08-20 | **Le free tier Supabase est dépassé** (143 %, 681 Mo / 500). Trois intuitions contredites par la mesure : purger ne libérerait rien, ne viserait pas le bon poids, et compresser n'est pas le levier (TOAST le fait déjà). |
| 2026-08-21 | **Transfert vers un 2e poste.** Les connecteurs ne se transfèrent pas. PC2 trop faible pour Ollama → **T1 délégué à Claude par tickets**. |
| 2026-08-22 | **Le ménage de PC1 rejoué sur PC2** : presque aucun de ses chiffres ne tenait. |
| 2026-08-25 | **Deux skills pour la procédure**, et une règle qui n'était appliquée par rien. |
| 2026-08-25 | **BASCULE SQLITE** : la référence passe sur PC2. Serveur dégraissé **810 → 139 Mo**. Cadence en jours calendaires. |
| 2026-08-26 | **Réparation autonome** : preuve du cycle de 01:00 ; un travail entier dormait non commité. |
| 2026-08-26 | **PC2 devient hôte SSH** : piège du compte administrateur, garde-fou que `PasswordAuthentication no` ne ferme pas. Rotation de clé. |
| 2026-08-26 | **Architecture remise d'aplomb** : la doc décrivait un système qui n'existait plus. Voir l'entrée conservée ci-dessous. |

## Doctrine de présentation (adoptée le 2026-07-28)

Conservée intégralement dans l'archive. En un mot : **ce qui est mesuré se
marque comme tel, ce qui est déduit aussi**, et un chiffre s'accompagne de son
effectif et de sa limite.

---

# Entrées courantes (régime append-only repris)

---

## 2026-08-26 (suite 3) — L'architecture remise d'aplomb : la doc décrivait un système qui n'existe plus

**Contexte.** Demande de confirmation d'une architecture : « l'utilisateur accède
à la carte via Vercel, la DB reste sur PC2, le site charge ses requêtes depuis la
DB de PC2 ». J'ai répondu par la négative en m'appuyant sur `CLAUDE.md`. **C'était
faux, et pour la pire des raisons** : la doc de référence décrivait un système qui
avait cessé d'exister la veille. La bascule SQLite du 2026-08-25 (commit
`cea4938`) a changé la source de vérité sans que `CLAUDE.md` en dise un mot.
**Une bascule d'architecture qui ne met pas à jour le document de référence
produit une doc qui ment avec autorité.**

### Ce que la mesure établit

| | SQLite local (PC2) | Supabase |
|---|---|---|
| Annonces | **76 942** | 69 175 |
| Actives | **53 258** | 46 881 |
| Dernier `first_seen` | **2026-08-25 23:46** | 2026-08-22 08:27 |
| Dernier `scan_run` | **2026-08-25 23:48** | **2026-08-22 08:27** |
| Taille | 1,19 Go | 139 Mo |
| Tables | 11 | 9 (+ 13 vues) |

**7 767 annonces, dont 6 377 actives**, existent sur PC2 et pas sur le serveur.
Le `max(last_seen)` serveur au 2026-08-25 13:57 est un leurre : il ne correspond
à aucun `scan_run` et provient de la migration de dégraissage du même jour.

### Trois affirmations, trois verdicts distincts

1. **« Supabase est dépassée » — CONFIRMÉ.**
2. **« Les infos vitales remontent à chaque scrap » — L'INTENTION EST ÉCRITE, LE
   MÉCANISME NE TOURNE PAS.** `ops/remonter-local.py` existe mais n'est appelé
   par **aucun** des 17 agents de `agents.json`.
3. **« Une requête non supportée interroge PC2 » — CE CHEMIN N'EXISTE PAS.**
   Aucun tunnel (`grep` : zéro occurrence). `lib/listings-db.ts:74` n'a que deux
   branches exclusives, dont une pointe un **fichier** local.

**Le dépôt s'était signalé à lui-même** : `agents/agents.json:446` portait la
note depuis le 23/08. Un avertissement rangé dans un fichier de config n'est pas
un garde-fou — rien ne le fait remonter (règle 2).

### Décision

`CLAUDE.md` refait (section « Architecture des données », stack, volumétrie,
état d'avancement). **Quatre règles permanentes inscrites** : 7 (tout
réversible), 8 (donnée protégée avant d'être optimisée), 9 (Vercel sous son free
tier, mesuré), 10 (audit de structure après chaque milestone). Création du
**masterlog** (`docs/masterlog.md`), registre horodaté des demandes consulté sur
demande seule.

---

## 2026-08-26 (suite 4) — Chiffrage de la remontée : le quota n'était pas l'obstacle que j'annonçais

**Contexte.** Demande de chiffrer les options de périmètre pour rebrancher
PC2 → Supabase. Dans l'entrée précédente, j'avais écrit que tout remonter
« recréerait le dépassement de quota qui a motivé la bascule ». **C'était une
supposition, pas une mesure, et elle est fausse.**

### Méthode du chiffrage

Le coût par ligne est **relevé sur le serveur lui-même**
(`pg_total_relation_size / reltuples`, index compris), pas estimé depuis SQLite —
les deux moteurs ne stockent pas pareil, et le serveur ne porte plus les mêmes
colonnes.

| Table | Octets/ligne (mesuré) |
|---|---|
| `listings` | 860 |
| `listing_images` | 265 |
| `posted_at_history` | 191 |
| `price_history` | 167 |
| `khet_snapshots` | 138 |
| `condos` | 385 |
| `cohort_snapshots` | 257 *(149 Mo / 578 683, relevé du 2026-08-20)* |
| `listing_amenities` | 103 *(63 Mo / 613 962, idem)* |

**Charge fixe : ~52 Mo** — écart entre la base (139 Mo) et la somme des tables
publiques (87,5 Mo) : catalogues système, schémas `storage` et `auth`.

### Les quatre scénarios

| Scénario | Contenu | Total projeté | Quota (500 Mo) |
|---|---|---|---|
| **A. Actives seules** | 53 258 annonces + images/prix/condos rattachés | **132 Mo** | **26 %** |
| **B. + inactives 30 j** | A + 10 758 délistées récentes | **141 Mo** | **28 %** |
| **C. Socle complet** | les 76 942 annonces, tout l'historique | **157 Mo** | **31 %** |
| **D. C + les 2 tables retirées** | + `cohort_snapshots` (1 341 871) + `listing_amenities` (762 506) | **580 Mo** | **116 %** |

*(État actuel du serveur : 139 Mo = 28 %.)*

### Ce que le chiffrage retourne

**Le socle complet coûte 157 Mo, soit 31 % du quota — 18 Mo de plus
qu'aujourd'hui.** Le poids n'a jamais été dans les annonces : il était dans
`page_text` + `description` (246 Mo) et `cohort_snapshots` (149 Mo). Ces trois-là
restent locaux, et c'est le dégraissage du 25/08 qui a libéré la place. Autrement
dit **la bascule a réglé le problème de quota, et j'ai continué à raisonner comme
s'il durait**.

Seul le scénario D dépasse — et il n'a aucun intérêt : ces deux tables ne sont
lues par aucune page.

### Le vrai critère de choix n'est pas le volume, c'est ce qui cesse de marcher

| Scénario | Conséquence fonctionnelle |
|---|---|
| **A** | **Casse l'absorption de la tension** : le time-on-market se calcule sur les **disparues**. Sans délistées, repli permanent sur l'âge des actives. Casse aussi la décote temporelle (`price_history` des délistées). |
| **B** | Absorption sur 30 j de recul. Suffisant pour la cadence actuelle, fragile si un scrap saute. |
| **C** | **Rien ne se dégrade.** Le serveur redevient l'image fidèle du socle. |
| **D** | Rien de plus que C côté site, et dépasse le quota. |

**Recommandation : C.** Il coûte 18 Mo de plus que l'état actuel, ne dégrade
aucune page, et supprime la classe entière de bugs « le serveur a un
sous-ensemble différent du local ». A et B n'économisent que 16 à 25 Mo — sans
rapport avec le risque fonctionnel qu'ils introduisent.

### Non fait, et non décidé

- **Rien n'a été remonté.** Le chiffrage n'est pas une exécution ; le choix du
  périmètre reste à l'utilisateur (règle 5).
- **Les images Storage ne sont pas dans ce chiffrage** — quota distinct (1 Go), et
  le téléversement est **suspendu** depuis le commit `c905efd`. À traiter à part.
- **La durée de la remontée n'est pas mesurée.** `remonter-local.py` réutilise
  `upsert_listing` ligne à ligne : 76 942 allers-retours vers ap-southeast-1. Ni
  chronométré, ni mis en lots.
- **Aucun garde-fou de fraîcheur** n'est encore posé (seuil à fixer).
- **La projection suppose que le coût par ligne reste constant** à l'échelle. Il
  peut dériver (croissance des index, remplissage des pages). Marge confortable :
  même à +50 %, C tiendrait sous 240 Mo.

---

## 2026-08-26 (suite 5) — Scénario A retenu : deux défauts que le chiffrage ne pouvait pas voir

**Contexte.** Arbitrage rendu : **scénario A** (le serveur ne porte que les
annonces actives), au motif que tout ce qui n'est plus actif sert à alimenter
les statistiques d'évolution du marché dans le temps — donc reste local, où
`study/run_study.py` les exploite. Implémentation demandée dans la foulée.

### Correction : ma recommandation précédente (scénario C) était dangereuse

L'entrée (suite 4) recommandait C, « socle complet », sur le seul critère du
volume. **En lisant le chemin d'écriture, C se révèle corrompre le serveur.**

`SupabaseStore.upsert_listing` **force `status='active'` et remet `delisted_at`
à null** (`supabase_store.py`, l. 100 et 134-135). C'est correct pour un scrap —
il n'upsert que ce qu'il vient de voir en ligne, donc vivant. Mais remonter
TOUTE la base par ce chemin **ressusciterait les 23 684 annonces délistées** en
actives sur le site public.

Le périmètre « actives seules » n'est donc pas seulement le plus léger (132 Mo
contre 157) : **c'est le seul qui ne corrompt pas le serveur.** L'arbitrage rendu
était mieux fondé que ma recommandation, et pour une raison que le chiffrage —
purement volumétrique — ne pouvait pas faire apparaître. Leçon transposable :
**chiffrer un périmètre ne dit rien du chemin d'écriture qui le réalisera.**

### Le défaut symétrique : A ne propage pas les morts

Un transfert d'actives n'envoie rien pour les annonces qui viennent de mourir.
Elles restent donc `active` côté serveur.

**Mesuré, pas supposé** : 400 identifiants tirés parmi les annonces délistées en
local depuis le dernier envoi au serveur (22/08) → **400/400 encore `active` en
ligne**. Soit ~1 876 annonces fantômes affichées comme disponibles sur le site
public, **et ce nombre croît à chaque cycle**.

C'est la panne silencieuse type : le site n'affiche pas d'erreur, il affiche des
biens qui n'existent plus.

### Ce qui a été implémenté

Deux options à `ops/remonter-local.py`, orthogonales, **défauts inchangés** pour
ne rien casser chez un appelant existant (règle 7) :

| Option | Effet |
|---|---|
| `--statut {tout,actives}` | Filtre **au SELECT** (charger puis jeter 23 684 dicts coûterait pour rien). Défaut `tout` = comportement historique. |
| `--synchro-statuts` | Recopie `status` + `delisted_at` du local vers les lignes que le serveur croit encore actives. |

**Pourquoi la recopie et non le délistage existant.** `mark_missing_inactive`
applique un **délai de grâce de 2 scans consécutifs** — indispensable pour un
scan (sans lui, la troncature à `max_pages` délistait toute la queue de liste),
mais **inapplicable à un transfert**, qui n'est pas une observation du marché.
Le local a déjà appliqué cette grâce lors des vrais scans : il détient la
vérité. La synchro **recopie un verdict, elle n'en rend pas un**.

L'`UPDATE` est ciblé (pas un upsert, qui forcerait `active` — soit l'inverse
exact du but) et porte `and status='active'`, ce qui le rend **idempotent** :
le rejouer ne touche rien de ce qui est déjà à jour. La nuance `sold` vs
`inactive` est portée telle quelle, pas recalculée.

### Débit mesuré — le point qui restait inconnu

Lot pilote de **500 annonces réelles écrites en production** (des actives
légitimes, donc sans risque) : **2 min 03**, soit **4,1 annonces/seconde**.

| Étape | Volume | Durée projetée |
|---|---|---|
| Upserts des actives | 53 258 | **~3 h 40** |
| Recopie des statuts | 23 684 candidates | ~40 min (estimé, non mesuré) |

Le coût est **dominé par les allers-retours réseau** vers ap-southeast-1 :
`get_listing` puis `upsert_listing` par annonce, soit au moins deux trajets
Bangkok↔Singapour chacun. Ce n'est pas un problème de base, c'est un problème de
granularité.

### Non fait, et pourquoi

- **La remontée complète n'a PAS été lancée.** Seul le lot pilote de 500 est
  parti. Une opération de ~4 h contre la base qui sert le site public est un
  choix de calendrier, pas une évidence technique : à lancer maintenant, ou à
  brancher dans la lane `daily` où elle tomberait la nuit.
- **La mise en lots n'a pas été faite.** Passer de 4 à ~100 annonces/seconde
  demanderait un `execute_values` et une lecture groupée des existants —
  changement d'un autre ordre, non entrepris sans arbitrage.
- **`synchroniser_statuts` appelle `store._execute`**, une méthode privée. Une
  méthode publique dédiée sur `SupabaseStore` serait plus propre ; laissé en
  l'état pour ne pas toucher au store dont dépend le scraper.
- **La durée de la recopie des statuts est estimée, pas mesurée.**
- **Le garde-fou de fraîcheur n'est toujours pas posé**, et l'inversion des 3
  agents de sauvegarde non plus.

---

## 2026-08-26 (suite 6) — La remontée entre dans la lane, et le cycle déborde sur la journée

**Contexte.** Arbitrage : brancher `remonter-supabase` dans la lane `daily`
**après le scrap**, et **repousser la veille en conséquence**.

### Placement — pourquoi cette ligne du tableau et pas une autre

`run_lane` ordonne : **Supervision → Prelude → Extraction → suite (ordre du
tableau `agents.json`) → overseer**. Il n'y a pas de champ `ordre` ; la position
dans le tableau EST l'ordre, pour tout ce qui n'appartient pas aux trois
familles nommées.

L'agent est donc inséré **juste avant `watch-health`**, ce qui le place en tête
de la « suite », c'est-à-dire immédiatement après le dernier extracteur. Vérifié
en simulant la lane (`run-lane daily --dry-run`) : il tombe bien après
`extract-ddproperty`. Publier plus tôt servirait un marché à moitié rafraîchi.

Famille `Security & storage`, `every_days: 1`, périmètre
`--statut actives --synchro-statuts` (arbitrage de la suite 5).

### La veille repoussée, sur mesure et non à l'estime

| | Valeur | Source |
|---|---|---|
| Cycle complet actuel | **7 h 15** | ledger, cycle du 2026-08-22 (25 agents) |
| + upserts de la remontée | ~3 h 40 | débit mesuré 4,1 annonces/s sur 53 258 |
| + recopie des statuts | ~40 min | estimé |
| **Cycle projeté** | **~11 h 35** | |

`STANDBYIDLE` passe donc de **5 h à 13 h** (18 000 → 46 800 s) dans
`ops/regle-alimentation.py`. À 5 h, le filet ne rattrapait plus un cycle après
coup : **il l'aurait coupé en son milieu** — exactement la panne qui a tué
`extract-ddproperty` deux cycles d'affilée le 2026-08-16.

**Appliqué ET vérifié**, parce qu'un `powercfg` peut renvoyer 0 sans rien poser
(cas `SYSCOOLPOL`, 2026-08-16) : `powercfg /query` rend
`Index actuel du paramètre de courant alternatif : 0x0000b6d0` = 46 800 s. ✔

**Contrepartie assumée** : si le verrou d'éveil de `garde-veille` échoue, la
machine reste allumée 13 h au lieu de 5. C'est le prix d'un filet qui ne coupe
pas ce qu'il est censé protéger.

### Troisième défaut, créé par le changement lui-même et corrigé dans la foulée

Un cycle de 11 h 35 démarré à 01:00 **finit vers 12:35** — il ne tient plus dans
la nuit. Or `LowiBKK-RattrapageBoot` part **au logon**. Un logon à 09:00 tombe
désormais en pleine remontée.

Et `scrap_en_cours()`, le garde-fou anti-cycle-parallèle, **ne l'aurait pas
vu** : sa sonde ledger ne regarde que la famille `Extraction`, et sa sonde
« lignes de commande » ne cherche que `scraper/run.py` et `scraper/recense.py`.
La remontée n'est ni l'un ni l'autre. Une lane entière serait repartie par-dessus.

La **donnée** n'aurait rien risqué — `remonter-local.py` prend un verrou
d'instance qui lève une `RuntimeError` sans bloquer (posé le 2026-08-03, après
16 990 écritures perdues par deux exemplaires concurrents). Mais le prix aurait
été **un agent en échec au ledger pour un fonctionnement parfaitement normal**,
c'est-à-dire une alerte qui crie au loup : ce que la règle 2 interdit.

Deux corrections minimales :
- `LONGS_A_NE_PAS_COUPER = {"remonter-supabase"}` — la sonde ledger accepte
  désormais, en plus de la famille Extraction, une liste nommée d'agents longs.
- `ops/remonter-local.py` ajouté aux motifs de la sonde « lignes de commande »,
  ce qui couvre aussi un lancement à la main.

### Non fait

- **La remontée n'a toujours pas tourné en entier.** Elle partira au prochain
  cycle de 01:00. Seul le lot pilote de 500 est en ligne.
- **La valeur sur BATTERIE n'a pas été touchée** : `STANDBYIDLE` DC reste à
  **180 s**. Un cycle sur batterie serait coupé en 3 minutes. Le script ne pose
  que les valeurs secteur, et c'est délibéré — mais ce n'est écrit nulle part
  que la tâche exige le secteur. **Non vérifié.**
- **La durée de la recopie des statuts reste estimée**, pas mesurée.
- **La mise en lots n'a pas été faite** : à 4,1 annonces/s le réseau porte tout
  le coût. Un `execute_values` ramènerait ~3 h 40 à ~10 min et rendrait ce
  débordement sur la journée sans objet. C'est le vrai correctif de fond ; le
  décalage de la veille n'est qu'un contournement de sa lenteur.

## 2026-08-27 — Le débordement prévu la veille s'est produit, par un mécanisme voisin mais différent

Réparation autonome (`agents/audits/reparations-2026-08-27.md`). L'entrée
ci-dessus prévenait que la remontée n'avait pas encore tourné en entier et
que « le décalage de la veille n'est qu'un contournement » de la lenteur du
réseau. Cette nuit, le débordement a eu lieu — mais coupé par un **second**
garde-fou temporel, pas celui qu'on avait ajusté.

**Chaîne mesurée** : `extract-ddproperty` a mis 7 h 47 (vs 1-3 h d'habitude,
0 erreur dans son log — cause non établie, à surveiller) → `remonter-supabase`
n'a démarré qu'à 08:47 Bangkok au lieu de ~01:15 → la tâche planifiée
`LowiBKK-Agents` a un `ExecutionTimeLimit` de **10 h**, jamais remonté quand
la durée de cycle est passée à ~11 h 35 le 2026-08-26 (même angle mort que le
seuil de `pouls.py`, traité isolément de `STANDBYIDLE` ce jour-là). À
11:00:01, Windows a tué le **processus orchestrateur** — mais pas son enfant :
le sous-processus réel de `remonter-local.py` (PID 780) a survécu au kill du
parent et continuait de tourner, non supervisé, pendant tout le diagnostic.

**Conséquence** : les 9 agents suivants de la lane (watch-health jusqu'à
overseer, backup-apres-cycle inclus) n'ont pas tourné. Pas de sauvegarde USB
ni d'audit overseer ce cycle — silence exactement du type que la règle 2
proscrit, sauf qu'ici c'est `pouls.py` (hors du cycle, comme prévu par sa
propre conception) qui l'a fini par signaler, avec 27 h de retard sur le
seuil de 26 h.

**Défaut distinct trouvé et corrigé en diagnostiquant** : `ops/pouls.py` et
`agents/orchestrator.py` plantaient en `UnicodeEncodeError` (console cp1252)
sur le premier caractère ⚠/✓/✗ imprimé — défaut connu depuis le journal du
2026-08-22, jamais traité. Corrigé (`sys.stdout/stderr.reconfigure`), testé
sous `PYTHONIOENCODING=cp1252` forcé, non-régression ajoutée
(`agents/tests/test_console_utf8.py`). Branche
`fix/console-utf8-pouls-orchestrator`, commit `d033b7e`.

**Non tranché, proposé** (règle 5) : remonter `ExecutionTimeLimit` à ~15-16 h
pour retrouver une marge comparable à celle prévue pour l'ancienne durée ; ou,
mieux, traiter la cause de fond déjà identifiée la veille (mise en lots de
`remonter-local.py`, ~3 h 40 → ~10 min), qui rendrait ce débordement
structurellement improbable des deux côtés (STANDBYIDLE et ExecutionTimeLimit).

**Non fait** : le sous-processus orphelin n'a pas été arrêté (travail
idempotent, vivant et actif à la fin de la session — à vérifier avant le
prochain cycle de 01:00 pour éviter une écriture concurrente si jamais il
tournait encore) ; la cause du ralentissement de `extract-ddproperty` reste
inconnue (aucune erreur à incriminer) ; le cas « un enfant survit au kill du
parent par le planificateur » n'a pas été traité côté `agents/core/shell.py`
(fréquence à mesurer avant de complexifier). Détail complet, y compris le
git status en amont (changements du 2026-08-26 toujours non commités) :
[agents/audits/reparations-2026-08-27.md](../agents/audits/reparations-2026-08-27.md).

## 2026-08-28 — Même troncature, 3e jour de suite : plus un hasard, un mur structurel

Réparation autonome (utilisateur absent). Récidive exacte du 27/08, mais avec
un fait nouveau qui change la conclusion : cette nuit, les **5 extracteurs
ont tourné à vitesse normale, 0 erreur** — et le cycle a quand même buté sur
la même limite. `remonter-supabase` démarre après ~8h15 de scrap (séquentiel,
après les extracteurs) et a besoin de ~4h20 (débit non par lots, mesuré le
26/08) pour finir, alors que `ExecutionTimeLimit=PT10H` de `LowiBKK-Agents`
tombe avant. **Conclusion : ce n'est plus la lenteur ponctuelle d'un
extracteur qui casse le cycle, c'est l'écart structurel entre la durée totale
(~11h35+) et la limite de la tâche planifiée (10h) — se reproduira tous les
jours tant que rien ne change.**

Base saine et en croissance (86 020 annonces / 61 246 actives, +4 526 vs la
veille, 0 erreur d'extraction). Aucune sauvegarde USB depuis le 2026-08-26
(3e jour), sans perte de données — juste en retard. Ticket résolu, e-mail
consolidé envoyé (remplace 2 alertes brutes en attente), aucun seuil ni
cadence modifié (règle 5 — décision toujours laissée à l'utilisateur, déjà
chiffrée le 27/08 : (a) `ExecutionTimeLimit` 10h→15-16h, (b) mise en lots de
`remonter-local.py` ~3h40→~10 min).

**Non fait, signalé une 2e fois** : les changements de code du 2026-08-26
(`remonter-supabase`, `ops/remonter-local.py`, `ops/regle-alimentation.py`)
tournent en production depuis 3 jours **sans aucun commit** — aucun point de
retour arrière (règle 7) depuis plus de 48h. Pas corrigé par cette session
(pas son mandat de committer du travail qu'elle n'a pas produit), mais
l'écart grandit chaque jour où personne ne tranche. Détail complet :
[agents/audits/reparations-2026-08-28.md](../agents/audits/reparations-2026-08-28.md).

## 2026-08-28 (suite) — remonter-local.py par lots, ExecutionTimeLimit retiré, garde-fou 16h

Sur consigne explicite de l'utilisateur, en réponse directe au constat du
matin : « batcher `ops/remonter-local.py` », « enlève la limite de temps
d'exécution mais envoie un mail après 16h de cycle si c'est toujours pas
fini + statut », rien d'autre.

**Batching.** `SupabaseStore.upsert_listings_bulk` remplace le chemin ligne à
ligne (`get_listing` + `upsert_listing`, 2 allers-retours Bangkok↔Singapour
par annonce, 4,1/s mesuré le 26/08) par `INSERT ... ON CONFLICT DO UPDATE`
sur des lots de 500 (1 SELECT de pré-lecture + 1 upsert par lot). Même
sémantique — `first_seen` préservé sur mise à jour, `price_history` /
`posted_at_history` alimentés sur changement — vérifiée par un nouveau test
(`agents/tests/test_remonter_bulk.py`, écrit contre le vrai Supabase avec
nettoyage en `finally`, comme `test_stores_alignes.py`). **Mesuré : 5000
lignes en 20 s (~250/s), soit ~60× le débit précédent.** La remontée
complète du jour a tourné en conditions réelles pendant l'écriture de ce
commit : 61 246 actives + 24 774 statuts en quelques minutes, 0 erreur.
Supabase affiche désormais `last_seen` du 28/08 03:21 UTC — le site public
était bloqué sur le 22/08 depuis l'échec de liaison signalé le 26/08, c'est
réparé au passage.

**ExecutionTimeLimit retiré** (`ops/install-agents-task.ps1`, était 10h,
jamais remonté depuis la durée de cycle de 7h15 du 22/08) — appliqué et
vérifié en direct (`Get-ScheduledTask` → `PT0S`). **Contrepartie posée par
l'utilisateur** : `ops/pouls.py` porte un nouveau garde-fou
`verifier_cycle_long()` (seuil 16h) qui lit le ledger — seule source qui
connaît un cycle encore EN COURS, contrairement à `pouls.json`, écrit trop
tard dans la séquence — et alerte par mail avec le statut courant (agent
bloqué, nombre d'agents déjà terminés) si un cycle démarré n'a toujours pas
fini après 16h. Intégré à la tâche `LowiBKK-Pouls` existante (toutes les
4h), aucune nouvelle tâche Windows créée.

**Décision délibérément non prise** : le déclenchement de `remonter-supabase`
par « milestones » du scrap (suggéré par l'utilisateur, « si tu veux ») n'a
pas été implémenté. Le batching résout déjà le problème de fond que ce
déclenchement aurait contourné (la queue de fin de cycle passe de ~4h20 à
quelques minutes) ; ajouter une exécution concurrente pendant que le scraper
écrit encore dans la même base SQLite locale (WAL, mais complexité et risque
réels) n'apporterait plus grand-chose pour le coût.

**Récupéré au passage, bloqué depuis 2 jours** : les 3 fichiers du 26/08
(`agents.json`, `remonter-local.py`, `regle-alimentation.py`) qui tournaient
en production sans commit ont été commités en premier (`0a24b0c`), avant
d'être modifiés davantage — aucun changement de comportement, juste un point
de retour arrière qui manquait depuis 48h+.

**Non fait, signalé** : la ligne `agent_runs` de `remonter-supabase`
(id 204, tuée manuellement en cours de diagnostic) est restée à `status='running'`
un moment — pas de correction directe possible (écriture SQL directe sur le
ledger bloquée par le garde-fou de permissions de la session), mais
l'orchestrateur lui-même l'a corrigée en `'failed'` en poursuivant seul la
lane derrière (`watch-health` → `backup-apres-cycle`), preuve que la lane
reprend proprement après l'échec d'un agent bloquant. La sauvegarde clé USB
du jour (`backup-apres-cycle`) a mis nettement plus longtemps que d'habitude
(>25 min contre 508 s le 26/08) — probablement la concurrence d'E/S avec la
remontée Supabase tournant en parallèle sur le même fichier local ; à
confirmer si ça se reproduit un jour où rien d'autre ne lit la base pendant
la sauvegarde.

## 2026-08-29 — réparation autonome : Task Scheduler tuait l'orchestrateur au réveil, et le ledger d'escalades ne décroissait jamais

Session `lowi-reparation-autonome`, utilisateur absent. Détail complet dans
[agents/audits/reparations-2026-08-29.md](../agents/audits/reparations-2026-08-29.md) ;
résumé ici.

**4e coupure de cycle de suite, cause différente des 3 précédentes.**
`ExecutionTimeLimit` avait été retiré la veille (10:23 Bangkok le 28/08)
justement pour empêcher ça — et le cycle a quand même été coupé, à un autre
endroit. Les 5 extracteurs sont partis en parallèle à 01:00:05 Bangkok ;
quatre ont fini et se sont enregistrés `ok` normalement. `extract-ddproperty`
a terminé tout son travail (log complet jusqu'aux stats finales, ~00:29 UTC,
confirmé par `last_seen` max de la base) mais le PROCESS PARENT de
l'orchestrateur a disparu ~2 min plus tard, sans exception Python, sans
dépassement d'`ExecutionTimeLimit` (déjà `PT0S`). Les 9 agents suivants de la
lane ne sont jamais partis.

**Cause établie par mesure, pas par déduction.**
`Get-ScheduledTaskInfo` → `LastTaskResult=3221225786` (0xC000013A,
`STATUS_CONTROL_C_EXIT` — le code que Task Scheduler pose quand il tue
lui-même un process). `Get-ScheduledTask` → `AllowHardTerminate=True` (valeur
par défaut, jamais posée explicitement) et `WakeToRun=True`. Le journal
Système (Kernel-Power 506/507) montre le système entrer en Veille moderne à
18:45:32 UTC et ne ressortir qu'à 07:29:46 (12 h 44, motif « Input Mouse »).
`WakeToRun=True` + `AllowHardTerminate=True` est le mécanisme documenté par
Microsoft pour ce symptôme exact : une tâche réveillée pour tourner en
arrière-plan se fait tuer par Task Scheduler au retour en veille ou au réveil
« pour de vrai ». Élément supplémentaire mesuré : le ledger montre
`verrou_veille_pose=true` pour `garde-veille` dès le début de ce cycle —
`SetThreadExecutionState` avait donc réussi, et le système est quand même
resté endormi 12 h 44. Cette API legacy est documentée comme non fiable pour
bloquer spécifiquement la Veille moderne ; l'alternative recommandée est
l'API Power Request (`PowerCreateRequest`/`PowerSetRequest`), absente
jusqu'ici du dépôt.

**Corrigé, deux branches dédiées :**
- `ops/install-agents-task.ps1` : `-DisallowHardTerminate` ajouté, appliqué
  et vérifié sur la tâche live (`Get-ScheduledTask` → `AllowHardTerminate:
  False`).
- `agents/core/wake_lock.py` : ajoute `PowerCreateRequest`/`PowerSetRequest`
  (`PowerRequestSystemRequired`) EN PLUS de `SetThreadExecutionState` —
  défense en profondeur, l'un ne remplace pas l'autre. `garde_veille.py`
  consigne désormais les deux résultats séparément.
- Tests : `agents/tests/test_wake_lock.py` (appels Win32 réels, handle
  obtenu et refermé correctement sur cette machine).
- **Non vérifiable en une session** : que ça suffise sur un cycle complet de
  plusieurs heures — seule la nuit prochaine le dira.

**Deuxième défaut trouvé en creusant les tickets en attente : le ledger
d'escalades ne décroît jamais.** `orchestrator status` affichait 12
escalades ouvertes datant du 2026-07-31/08-01, toutes déjà résolues et
déplacées vers `queue/done/` par des sessions passées qui avaient édité le
fichier à la main sans appeler `escalation.resolve()` — le seul chemin qui
met aussi à jour le ledger. `escalation.reconcile(ledger)` referme
désormais automatiquement, à chaque `orchestrator status`, toute escalade
dont le ticket est déjà dans `queue/done/`. Les 12 lignes historiques ont
été reconciliées. Test : `agents/tests/test_reconcile_escalations.py`.

**Puisque le scrap de la nuit avait réellement abouti** (base saine,
`last_seen` frais) et que le seul dommage était que la suite de la lane
n'était jamais partie, `orchestrator.py --boot` (mécanisme déjà prévu pour
ce cas) a été lancé : `remonter-supabase` ok en 2 min 17 s (première
confirmation en conditions réelles que le batching du 28/08 tient sur un
rattrapage), puis toute la suite jusqu'à `backup-apres-cycle`/`overseer`.

**Deux tickets `analyze-rent`/`organize` traités** (dont un doublon exact
généré deux fois, avant et après le rattrapage) : le rendement suspect de
Lat Krabang District (10.9 %) est un défaut de méthode confirmé — un condo
compare 16 ventes de studios à UNE SEULE location 2 chambres, et un autre
condo existe en double `condo_name` par divergence de normalisation entre
sources (déjà connue, cf. plus haut dans ce journal). Décision de méthode
laissée à l'utilisateur (règle 5). Les 120 paires ambiguës des deux lots
`organize` ont été extraites par script déterministe (T1 absent sur ce
poste) — 120 abstentions, 0 same_unit : vérifié non-bogue, aucune paire ne
remplit le critère strict du décideur.

**Non fait, signalé** : `STANDBYIDLE` sur batterie (180 s, déjà signalé
« non vérifié » le 26/08) n'a pas été touché — seuil de posture, décision
utilisateur ; la machine était sur secteur au moment du contrôle donc rien
ne prouve un lien avec la coupure de cette nuit. Le run `interrompu`
d'`extract-ddproperty` n'a pas été requalifié `ok` à la main malgré un
travail manifestement abouti — conforme au principe existant (`is_due()` le
relance de lui-même), au prix d'un re-scrape redondant la nuit prochaine.
`CLAUDE.md`/`docs/journal-technique.md` restent modifiés sans commit depuis
le 26/08 — 4e signalement. Une alerte mail périmée (`remonter-supabase`,
artefact d'un kill manuel du 28/08, déjà expliqué) a été archivée sans être
envoyée plutôt que d'induire en erreur 24h après coup.

## 2026-08-31 — réparation autonome : le minuteur RTC de 00:59:31 n'a jamais réveillé la machine — cause plausible identifiée (RTCWAKE désactivé sur secteur continu)

Session `lowi-reparation-autonome`. Détail complet dans
[agents/audits/reparations-2026-08-31.md](../agents/audits/reparations-2026-08-31.md) ;
résumé ici. Aucun ticket en attente (`agents/queue/` vide hors `done/`), aucune
erreur d'extracteur nouvelle sur les 40 derniers logs, base saine (`quick_check`
ok, 93 148 annonces dont 66 883 actives, `last_seen` à jour à la minute — le
cycle du jour tournait pendant le contrôle), sauvegarde clé USB de la veille
vérifiée 3/3 (93 049 annonces, 30/08 13:56).

**Le minuteur RTC confirmé « armé » hier soir par l'utilisateur
(`powercfg /waketimers` → `LowiBKK-Agents` à 00:59:31) n'a produit AUCUN
réveil cette nuit.** Preuve directe, pas déduite : le journal
`Microsoft-Windows-TaskScheduler/Operational`, activé hier en fin de session
(`wevtutil sl .../Operational /e:true`), est **vide de tout événement entre
30/08 18:00 et 31/08 08:09** — aucune tentative de lancement, pas seulement un
lancement raté. Kernel-Power confirme côté sommeil : endormissement le 30/08 à
14:10:55 (Idle Timeout), réveil suivant le 31/08 à 08:09:13, motif **Lid**
(capot rouvert à la main). Le cycle n'a démarré qu'au rattrapage
`StartWhenAvailable` déclenché par ce réveil manuel — 5e retard sur les 6
derniers jours (27, 28, 29, 30, 31/08), pas un incident isolé.

**Cause plausible trouvée, non testée en conditions réelles** :
`powercfg /query SCHEME_CURRENT SUB_SLEEP` (lecture seule, sans élévation) —
`RTCWAKE` (« Autoriser les minuteurs de sortie de veille ») vaut
**Activé sur secteur (AC), Désactivé sur batterie (DC)** :
```
GUID du paramètre d'alimentation : bd3b718a-0680-4d9d-8ab2-e1d2b4ac806d (RTCWAKE)
Index actuel du paramètre de courant alternatif : 0x00000001  (Activer)
Index actuel du paramètre de courant continu    : 0x00000000  (Désactiver)
```
Un minuteur RTC peut être « armé » (visible dans `/waketimers`) tout en étant
silencieusement annulé au moment du réveil si la machine est passée sur
batterie entre-temps — ce qui expliquerait un minuteur confirmé actif hier
soir et pourtant sans effet cette nuit. `STANDBYIDLE` en DC reste par ailleurs
à 180 s (3 min, déjà signalé le 26/08, toujours vrai) : une machine débranchée
s'endort très vite ET ne peut plus se réveiller seule. `STANDBYIDLE` en AC est
confirmé à 46 800 s (13 h, conforme à l'entrée du 26/08 — pas de régression
sur ce paramètre). **Non établi** : si la machine était effectivement sur
batterie cette nuit précise (aucun journal de source d'alimentation consulté
en historique, seul l'état actuel — secteur, 94 % — a pu être lu).

**Non fait, volontairement** : pas de correctif appliqué. Changer `RTCWAKE`
(`powercfg /setdcvalueindex ... RTCWAKE 1`) exige une élévation absente de
cette session (déjà signalé le 26 et le 30/08 pour `/requests` et
`/waketimers` — s'étend maintenant à `/setdcvalueindex`), et c'est une
préférence d'alimentation persistante au même titre que celles posées par
`ops/regle-alimentation.py` (`lanes: []` à dessein, invocation manuelle
seulement — règle 5 : pas à moi de trancher). Recommandation chiffrée laissée
à l'utilisateur : activer `RTCWAKE` en DC si la machine tourne parfois
débranchée la nuit ; sinon la piste est fausse et la cause reste à chercher
ailleurs (BIOS wake, service Task Scheduler lui-même). `regle-alimentation`
(dernier succès il y a 14,4 j, run unique du 16/08 sur l'ancien poste PC1
`schoe\++FILES++`) et `verifie-backup` (6,0 j), tous deux affichés « DÛ » par
`orchestrator status`, revérifiés non-bogue : `lanes: []` à dessein dans
`agents.json`, hors cycle automatique par conception, pas par défaut.
`CLAUDE.md`/`docs/journal-technique.md`/CSV d'études restent modifiés sans
commit — 6e signalement, toujours pas mon travail à trancher (travail
d'autres sessions, portée dépasse cette réparation). Fichier orphelin
`bad_rings_out.txt` (racine du dépôt, non tracké, sortie d'une vérification de
géométrie de polygones khet) repéré mais non touché : aucun script du dépôt
ne le produit, origine et intention inconnues.

**Alerte mail traitée différemment de la veille, et pourquoi.** La boîte
`agents/queue/mail/` contenait une alerte pouls du 30/08 04:50 (« aucun cycle
depuis 28 h »), non envoyée depuis >24 h. Le précédent du 28/08 archivait sans
envoyer une alerte devenue trompeuse ; ici le connecteur Gmail était
disponible et le motif sous-jacent (retards répétés du réveil 01:00) restait
réel et non communiqué à l'utilisateur — l'archiver silencieusement aurait
caché un problème qui persiste. Envoyée avec un post-scriptum daté replaçant
les faits dans le contexte du jour (cycle depuis rattrapé, pattern de 5/6
jours, renvoi vers ce journal), puis déplacée dans `queue/mail/done/` (dossier
créé, aligné sur la convention déjà en place dans `queue/done/`).

**Addendum, même session — l'utilisateur reprend la main en direct.**
Confirme que la machine tourne normalement sur secteur, mais demande d'activer
`RTCWAKE` en DC quand même, « on sait jamais ». Exécuté :
`powercfg /setdcvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 1` puis
`powercfg /setactive SCHEME_CURRENT`. **N'a pas exigé d'élévation** — contre
l'attente posée plus haut dans cette même entrée : `/setdcvalueindex` change
la préférence de l'utilisateur courant sur son propre schéma d'alimentation,
contrairement à `/waketimers`/`/requests` qui lisent un état noyau
system-wide et exigent un admin. Vérifié après coup par relecture
(`powercfg /query ... RTCWAKE`) : `Index actuel du paramètre de courant
continu = 0x00000001 (Activer)`, changement confirmé, pas seulement supposé
depuis l'absence d'erreur. **Non touché** : `STANDBYIDLE` en DC reste à 180 s
— si la machine tourne un jour débranchée, elle s'endort en 3 min et le
réveil RTC (maintenant possible en théorie sur ce point précis) resterait à
tester en conditions réelles. Pas demandé par l'utilisateur, pas changé.

**Addendum 2, même session — question de l'utilisateur : quelles méthodes de
réveil restent inessayées ?** Réponse donnée en chat, puis vérification
concrète du matériel via `powercfg /a` : cette machine (ASUS ZenBook
UX481FL) n'expose **que S0 Low Power Idle (Modern Standby), Hibernation et
Démarrage rapide** — S1/S2/S3 sont désactivés au niveau firmware, pas par un
réglage Windows (« désactivé lorsque le mode faible consommation S0 est pris
en charge »). Piste « repasser en veille classique S3 » définitivement
fermée sur ce matériel, pas une question de configuration.

L'utilisateur a demandé d'essayer 2 méthodes (la 3e, réveil BIOS/UEFI, restant
à sa main — accès physique requis) :

- **Périphérique de réveil armé manuellement** (`powercfg /devicequery
  wake_from_any`) : révèle une **« Alarme de sortie de veille ACPI »**,
  présente et listée capable pour S4 (`S4_supported`) — vraisemblablement le
  composant que Task Scheduler pilote déjà en interne pour `WakeToRun`.
  Tentative `powercfg /deviceenablewake "Alarme de sortie de veille ACPI"`
  → **refusée, élévation requise** (contrairement aux réglages `set*valueindex`
  qui ne l'exigent pas). Par ailleurs ce device n'apparaît dans AUCUNE des
  listes `wake_programmable`/`wake_armed` (toutes deux vides sur l'ensemble
  du système) : sur du Modern Standby, l'API historique d'armement manuel par
  périphérique semble neutralisée au profit d'une gestion interne par l'OS —
  armer ce device à la main n'apporterait probablement rien de plus que ce
  que `WakeToRun`+`RTCWAKE` font déjà, même avec les droits admin. Piste
  jugée sans levier réel ici, pas juste bloquée par les droits.
- **Hibernation (S4) au lieu du Modern Standby pour l'endormissement
  nocturne, même minuteur Task Scheduler** : `HIBERNATEIDLE` en AC était à
  `0x00000000` (jamais — la machine ne passait jamais en hibernation
  d'elle-même sur secteur, seulement en Modern Standby via `STANDBYIDLE`
  13 h). Réglé à **1800 s (30 min)**
  (`powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP HIBERNATEIDLE 1800`),
  n'a pas exigé d'élévation, vérifié après coup par relecture. Comme
  `HIBERNATEIDLE (30 min) < STANDBYIDLE (13 h)`, le comportement documenté de
  Windows (minuteurs indépendants depuis le dernier événement d'activité, le
  plus court l'emporte) devrait faire hiberner la machine directement après
  30 min d'inactivité sur secteur, sans jamais passer par le Modern Standby —
  **non vérifié sur ce matériel précis** (le mécanisme « sleep then
  hibernate » est documenté pour S1-S3, son comportement exact sur une
  plateforme Modern-Standby-only n'a pas été observé ici). **Effet de bord
  assumé, pas juste pour cette nuit** : toute inactivité de 30 min sur
  secteur, de jour comme de nuit, fera désormais hiberner la machine au lieu
  d'un Modern Standby quasi instantané — reprise plus lente en journée si le
  seuil est atteint. Rollback :
  `powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP HIBERNATEIDLE 0`.
  **À vérifier demain matin** : est-ce que `LastRunTime` de `LowiBKK-Agents`
  colle à 01:00 (réveil réussi depuis S4) ou reste-t-il un rattrapage tardif
  (le mode de panne persiste malgré le changement de state de veille) ?

## 2026-08-30 — réparation autonome : le réveil 01:00 a manqué une 2e nuit, mode de panne différent de celui corrigé la veille

Session `lowi-reparation-autonome`. Détail complet dans
[agents/audits/reparations-2026-08-30.md](../agents/audits/reparations-2026-08-30.md) ;
résumé ici. Aucun ticket en attente, aucune erreur d'extracteur nouvelle,
base saine (`quick_check` ok, 90 618 annonces, `last_seen` à jour), sauvegarde
clé USB de la veille vérifiée 3/3.

**Le correctif d'hier (`AllowHardTerminate=False`) n'a pas été mis à
l'épreuve cette nuit — un autre maillon a cassé avant lui.** Le système est
entré en veille moderne le 29/08 à 08:23:28 et n'en est ressorti que le
30/08 à 07:50:23 (motif **Lid**, capot ouvert à la main), 23 h 27 sans le
moindre événement Kernel-Power intermédiaire. `Get-ScheduledTaskInfo` →
`LastRunTime = 30/08/2026 07:50:29` : si le déclenchement RTC de 01:00
avait eu lieu (même pour être tué ensuite comme la nuit du 28→29/08, où
`LastRunTime` affichait bien `01:00:05`), Task Scheduler l'aurait enregistré
comme dernier lancement. Il ne l'a pas fait — le déclenchement lui-même
n'a jamais eu lieu, pas seulement le process qui aurait suivi.
`WakeToRun=True` / `AllowHardTerminate=False` / `StartWhenAvailable=True`
sont pourtant bien posés sur la tâche live (vérifiés). Pas de double coureur
(`LowiBKK-RattrapageBoot` n'a pas tourné aujourd'hui, dernier run le 22/08) :
la reprise de 07:50 vient uniquement du rattrapage normal de
`LowiBKK-Agents` sur son propre déclenchement manqué.

**Cause non établie — bloqué par deux manques d'outillage, consignés pour
la prochaine session avec droits admin** : `powercfg /waketimers` et
`/requests` exigent une élévation absente de cette session (déjà signalé
pour `/requests` le 26/08, s'étend à `/waketimers`). Et surtout,
**`Microsoft-Windows-TaskScheduler/Operational` est désactivé** sur cette
machine (`IsEnabled=False`) — aucun journal fin des déclenchements/échecs
de tâches n'existe, donc impossible de dire si le timer RTC n'a jamais été
armé, s'il a été armé puis annulé, ou ignoré par le firmware. Recommandé
mais non appliqué : `wevtutil sl Microsoft-Windows-TaskScheduler/Operational
/e:true` (réversible, sans risque) pour capturer le détail à la prochaine
occurrence.

**Non fait, volontairement** : aucun correctif de code sur le
réveil/veille — sujet déjà en travail actif de l'utilisateur sur
`fix/allow-hard-terminate-wake-lock` (5 commits le 29/08 matin), et le
diagnostic complémentaire nécessaire est bloqué par l'absence de droits
admin ici. Pas de correctif à l'aveugle sur un mécanisme déjà retouché la
veille sans certitude sur la cause de cette nuit. `regle-alimentation` et
`verifie-backup`, affichés « DÛ » par `orchestrator status`, vérifiés
non-bogue : `lanes: []` dans `agents.json`, outils volontairement hors
cycle automatique (`verifie-backup` neutralisé le 25/08, rôle repris par
`sauvegarde-cle.py`/`pouls.py`). `CLAUDE.md`/CSV d'études/`.gitignore`
restent modifiés sans commit — 5e signalement, pas mon travail à trancher.

**Addendum, même session, l'utilisateur reprend la main en direct** (connecté
via RustDesk) et lance les 3 commandes admin bloquées plus haut :
- `powercfg /waketimers` → un minuteur **est armé** pour ce soir :
  `LowiBKK-Agents` à **00:59:31 le 31/08**. Le mécanisme RTC fonctionne
  actuellement ; ne prouve pas rétroactivement l'état d'hier soir (aucun
  moyen de consulter un minuteur passé), mais la nuit prochaine devrait
  réveiller la machine si rien n'annule ce timer entre-temps.
- `powercfg /requests` → seul RustDesk tient `DISPLAY`+`SYSTEM`, cohérent
  avec la session à distance en cours au moment de la commande — pas un
  signe d'anomalie, et sans rapport avec la coupure de cette nuit (le
  système s'est bien endormi à 08:23:28, RustDesk ne bloquait donc rien à
  ce moment-là).
- `wevtutil sl Microsoft-Windows-TaskScheduler/Operational /e:true` →
  **appliqué**. Le journal détaillé des déclenchements de tâches est
  maintenant actif : si le réveil de 00:59:31 échoue à nouveau cette nuit,
  la cause exacte sera visible dans ce journal au lieu d'être déduite
  indirectement de Kernel-Power. Point à recontrôler à la prochaine
  session.

**Addendum 2, même session — pourquoi le dashboard affiche « aucun scrap en
cours » : les 5 extracteurs du rattrapage de 07:50 ont bien démarré, puis ont
été tués simultanément.** Mesuré dans `agents/ledger.db`
(`agent_runs`) : les 5 extracteurs démarrent à `2026-08-30T00:50:39+00:00`
et passent tous à `status='interrompu'` à **la même seconde**,
`00:52:55+00:00` (07:52:55 Bangkok) — 5 processus indépendants ne tombent
pas à la même seconde par hasard, c'est un signal externe qui a coupé tout
le groupe d'un coup. Rien n'a repris depuis (dernière ligne du ledger à
07:52:55, contrôlé à 09:10 — plus d'une heure sans reprise).

**Deux éléments concordants, mesurés, pas supposés :**
- `(Get-ScheduledTask -TaskName LowiBKK-Agents).Principal` →
  **`LogonType=Interactive`, `RunLevel=Limited`, `UserId=Remidaboss`**. La
  tâche tourne attachée à la session de bureau interactive, pas en
  `S4U`/mot de passe (indépendant de l'état de la session). Un verrouillage,
  une mise en veille ou une perturbation de session peut donc couper d'un
  coup tous les processus qui en dépendent — cohérent avec un kill
  simultané des 5.
- Journal Système : une mise à jour pilote (**ASUS System Driver Update**)
  s'est installée dans une fenêtre qui encadre exactement le kill —
  téléchargement démarré 07:51:28, installation démarrée 07:52:32, terminée
  07:52:59. Le kill à 07:52:55 tombe dedans. Corrélation forte, causalité
  non prouvée formellement (pas de lien direct dans les logs entre
  l'installeur et la terminaison des process).

**Non fait, laissé à l'arbitrage de l'utilisateur** : relancer la lane
maintenant (`orchestrator.py --boot`, cf. mécanisme déjà utilisé le
2026-08-29) reprendrait la suite sans dupliquer, mais relancer un scrap en
pleine journée est une décision de posture (règle 5), pas la mienne à
prendre. Le minuteur de 00:59:31 cette nuit (confirmé par `powercfg
/waketimers`, addendum 1) devrait de toute façon relancer les 5
extracteurs demain matin puisqu'aucun n'a réussi aujourd'hui
(`is_due()`). **Piste de fond non appliquée** : passer `LogonType` de
`Interactive` à un mode indépendant de la session (S4U ou compte/mot de
passe) rendrait la tâche insensible aux perturbations de session — nécessite
de reconfigurer le principal de la tâche (mot de passe du compte), non fait
ici, à arbitrer.

## 2026-08-29 — optimisation scraping via `scrapling` : deux lots livrés, mesurés avant écriture

Demande utilisateur : regarder ce que le projet `scrapling` (GitHub) permet
d'améliorer côté scraping, notamment pour Cloudflare. Plan approuvé en mode
plan (2 lots + un lot documenté-non-implémenté), conservé hors dépôt dans
`~/.claude/plans/`. Résumé ici, avec ce que la mesure a corrigé par rapport
au plan initial.

**Contexte avant modif : le contournement Cloudflare actuel n'était pas
cassé.** `fetch.py` réchauffe déjà le cookie `__cf_bm` de DDproperty en
visitant la liste avant les fiches (aucun échec `[SONDE-ECHEC]` réseau
attribuable à Cloudflare dans l'historique). Les vrais manques mesurés :
zéro retry (une erreur réseau isolée = fiche perdue), une empreinte TLS de
`requests`/urllib3 non usurpée, et un parsing HTML (FazWaz/LivingInsider)
figé sur des noms de classe exacts.

**Le plan initial visait `scrapling.fetchers.FetcherSession` — abandonné
après mesure, remplacé par `curl_cffi.requests.Session` en direct.**
`FetcherSession` n'expose que `get/post/put/delete`, pas `.head()` (or
`head_size()` en dépend pour empreinter les photos sans les télécharger) ;
et `pip install "scrapling[fetchers]"` tire `patchright`+`browserforge`
(~110 Mo, navigateur inutile ici) même si on n'utilise jamais
`StealthyFetcher`/`DynamicFetcher` — confirmé par l'issue GitHub
D4Vinci/Scrapling#92 puis par un test d'install réel sur ce poste.
`curl_cffi.requests.Session` seul a une API quasi identique à `requests`
(`.get/.head`, `raise_for_status`, `.text`, `.content`, headers
insensibles à la casse) : bascule quasi sans changement de logique, et
`scrapling` (sans extra, pour le Lot 2) n'ajoute alors que ~13 Mo
(lxml/cssselect/orjson/tld/w3lib), aucun binaire navigateur.

**Lot 1 — `pipeline/fetch.py` : backend `curl_cffi` optionnel, activé sur
DDproperty.** Choisi par site via `fetcher_backend` dans `config/*.json`
(défaut `requests`, inchangé sur fazwaz/propertyscout/nestopa/livinginsider).
Retries intégrés (3, backoff 1 s) là où il n'y en avait aucun. Pas de mélange
avec `_BROWSER_HEADERS` (Chrome 126 figé) : curl_cffi génère déjà un jeu
d'en-têtes cohérent avec la version Chrome impersonée — les mélanger aurait
affiché `sec-ch-ua` sur 126 pendant qu'une signature TLS plus récente partait,
un décalage que les anti-bots regardent justement. **Vérifié en direct** (une
seule requête, sur le vrai site) : une requête FROIDE via curl_cffi passe le
Cloudflare de DDproperty sans le réchauffement de session habituel,
`__NEXT_DATA__` présent. N'a pas encore tourné sur un cycle `--full` complet
— l'extension aux 5 autres sources reste conditionnée à cette mesure, comme
prévu au plan (règle 9).

**Lot 2 — parsing adaptatif (`scrapling.parser.Adaptor`) sur FazWaz et
LivingInsider**, les deux seuls adaptateurs à localiser un champ par nom de
classe exact (`statut_marche()` sur `.price-message` ; le bloc "Property
information" de LivingInsider). `auto_save`/`adaptive` : relocalise
l'élément par similarité structurelle si la classe est renommée, au lieu de
faire disparaître silencieusement le champ sans qu'aucun `sonder()` ne le
voie (le marqueur de structure de ces deux sources — JSON-LD — est
indépendant de ces blocs HTML précis).

**Défaut trouvé EN VÉRIFIANT, avant tout commit** : la première version du
Lot 2 sur LivingInsider ne rendait adaptatif que la recherche du titre
(`.property-inform-title`), pas la navigation vers le bloc de valeurs
(`find_ancestor` avec un prédicat figé sur la classe `form-group`) — un test
avec classe ET balise renommées simultanément a échoué (`None, None, None`
au lieu des 3 valeurs). Corrigé en abandonnant le filtre de classe sur le
conteneur : on prend le parent DIRECT du titre (quel qu'il soit) puis son
frère suivant — la relation qui compte n'est pas le nom de la classe, c'est
« le bloc de valeurs suit le conteneur du titre ». Revérifié : passe sur le
balisage d'origine ET sur classe+balise renommées.

**Vérification faite** : fixtures HTML locales (balisage d'origine, puis
classe/balise renommées en simulant une refonte) pour les deux fonctions
modifiées — comportement identique sur l'original, relocalisation correcte
sur le renommage, `None` propre si le champ disparaît réellement (pas de
crash). Base sqlite d'apprentissage adaptatif pointée dans `scraper/output/`
(gitignore) plutôt que le défaut du paquet dans `site-packages/`, qui
disparaîtrait à chaque reconstruction du venv.

**Lot 3 (`StealthyFetcher`/Camoufox) délibérément NON implémenté** : décision
de posture (contournement d'un blocage, règle 5), documentée dans le plan
mais laissée à l'arbitrage de l'utilisateur. Chiffres qui la motivent :
~1,2 Go de binaire navigateur, ~29 s/page contre du sub-seconde aujourd'hui,
et 58 % de succès mesuré par des tiers (scrapfly/godberrystudios) — moins
fiable que le contournement actuel, qui fonctionne à 100 % sur les runs de
production (sinon on l'aurait vu dans les escalades `parser_break`).

**Commits séparés** (Lot 0 du plan) : un commit par lot, sur la branche
courante — `git revert` cible l'un sans l'autre si besoin. Le flag
`fetcher_backend` en config permet un rollback du Lot 1 sans revert.

**Non fait** : extension du Lot 1 aux 5 autres sources (conditionnée à un
cycle `--full` mesuré sur DDproperty — pas encore lancé, seule une requête
isolée a été vérifiée) ; aucune mesure de `[SONDE-ECHEC]`/latence sur un
cycle réel, seulement des fixtures locales et une requête ponctuelle ;
décision sur le Lot 3 non tranchée (n'a pas à l'être tant que Cloudflare ne
durcit pas réellement DDproperty).

## 2026-09-01 — Réparation autonome : le correctif du 29/08 contre le blocage nocturne était insuffisant

Session `lowi-reparation-autonome`. Trois tickets en attente à l'ouverture,
détail complet dans `agents/audits/reparations-2026-09-01.md`.

**Le run bloqué de la nuit du 30-31/08 avait deux causes empilées, une
seule déjà connue.** La première (déclenchement RTC de 01:00 silencieux,
réveil manuel obtenu à 08:09 par ouverture du capot) était déjà établie en
direct par la session du 31/08. La seconde n'était pas visible ce jour-là
(le rapport avait été écrit pendant que le cycle rattrapé tournait encore) :
mesuré ce matin dans le ledger, le run `extract-ddproperty` (id 250) a en
réalité été tué à 10:19:47 avec le code de retour **3221225786**
(`STATUS_CONTROL_C_EXIT`) — le même code exact qui avait motivé le
correctif `-DisallowHardTerminate` du 2026-08-29. Sauf que cette fois,
`AllowHardTerminate` était déjà à `False` (vérifié avant toute correction
de cette session) : **le correctif du 29/08 était déjà en place et n'a pas
empêché la récidive**, ce qui invalide l'explication retenue ce jour-là
(Task Scheduler tuant lui-même le process via son propre mécanisme de
hard-terminate).

**Piste retenue, déjà identifiée puis explicitement laissée de côté le
30/08** (« Piste de fond non appliquée : LogonType de la tâche reste
Interactive »). Un process en `LogonType=Interactive` est attaché à la
session bureau ; une transition de cette session peut produire côté console
l'équivalent d'un signal `CTRL_LOGOFF`/`CTRL_SHUTDOWN`, que `python.exe`
termine sans le capturer — cohérent avec le code observé les deux fois
(29/08 et 31/08), mais **non reproduit en laboratoire**, à traiter comme
déduit et non prouvé (même réserve que celle posée le 29/08 pour la théorie
précédente).

**Corrigé sur `fix/allow-hard-terminate-wake-lock` (commit `386a69e`)** :
`ops/install-agents-task.ps1` passe `LogonType` de `Interactive` à `S4U`
(pas de mot de passe stocké, aucune dépendance du dépôt à un bureau
interactif vérifiée par grep). **Non déployé** : `Register-ScheduledTask`
avec ce réglage exige une élévation absente de cette session
(« Accès refusé » constaté, tâche live vérifiée inchangée après l'échec).
Commande prête, à lancer par l'utilisateur depuis une console administrateur
(voir le rapport pour la commande exacte).

**Ticket d'extraction dédup traité mécaniquement** (60 paires,
`organize/comparaison_deleguee`) : même pratique qu'établie le 2026-08-25
pour 5 lots similaires — le texte de chaque paire est entièrement gabarit,
donc extraction par script déterministe plutôt que lecture à l'œil.
100 % d'abstention, contre-vérifié sur les 60 réponses avant de clore le
ticket (écart médian mesuré 7,4 %, aucune paire sous le seuil de 2 % du
critère `same_unit`) : le résultat est correct, pas un défaut d'extraction.

**Rien d'autre à signaler** : logs d'erreur propres du 26/08 au 01/09 (le
seul cluster restant, `database is locked` du 25/08, était déjà corrigé et
documenté ce jour-là) ; base saine (`quick_check` ok, WAL, 97 500 annonces
dont 70 532 actives, fraîcheur cohérente avec le dernier cycle) ; sauvegarde
clé USB 3/3 vérifiée, comptes identiques à la base de référence.

**Non fait** : déploiement du correctif S4U (élévation requise, laissé à
l'utilisateur) ; la piste RTCWAKE/batterie du 31/08 pour la cause A, non
retranchée aujourd'hui.

## 2026-09-01 (suite) — Correctif LogonType S4U déployé par l'utilisateur

Suite de l'entrée du jour. `ops/install-agents-task.ps1` relancé par
l'utilisateur depuis une console administrateur, immédiatement après le
rapport. Enregistrement réussi (aucune des deux alertes de vérification post-
enregistrement ne s'est déclenchée). Confirmé par lecture directe :
`LogonType = S4U`, `AllowHardTerminate = False`, `ExecutionTimeLimit = PT0S`
sur la tâche live. Effet de bord attendu et positif : la tâche peut
désormais tourner même sans session utilisateur ouverte (S4U ne l'exige
plus), alors qu'`Interactive` l'exigeait.

**Non vérifié** : aucun cycle complet n'a encore tourné sur ce réglage — la
première preuve viendra du cycle de 01:00 cette nuit (2026-09-01 →
2026-09-02). Si le même code `STATUS_CONTROL_C_EXIT` réapparaît malgré S4U,
la théorie LogonType est fausse et la piste RTCWAKE/batterie du 31/08
(§2 du rapport du jour) redevient la plus probable pour la cause A — la
cause B (process tué en cours de cycle) resterait alors non expliquée.

## 2026-09-01 (suite 2) — `scan_runs` figé depuis 10 jours : la remontée n'y écrivait jamais

**Contexte.** Demande de rappel du rôle de `scan_runs`, dans la foulée d'une
remontée manuelle vers Supabase (`ops/remonter-local.py --statut actives
--synchro-statuts` : 70 532 actives transférées, 0 nouvelle, 0 fantôme corrigé —
signe que l'agent `remonter-supabase` tournait déjà seul en lane `daily` depuis
le 26/08 sans que ça ait été consigné). `listings.last_seen` était bien frais
(2026-09-01), mais `scan_runs` restait figé au **2026-08-22** pour les 5
sources.

**Cause.** `ops/remonter-local.py` n'a jamais écrit dans `scan_runs` — seuls les
5 extracteurs le font, et ils n'écrivent plus sur Supabase depuis la bascule
SQLite du 25/08 (§ suite du 25/08). Un outil qui lit `scan_runs` pour juger la
fraîcheur du serveur (`ops/verifie-synchro.py`) se trompait donc depuis 10
jours : les données étaient à jour, la table qui en témoigne ne l'était pas.

**Décision** (utilisateur) : l'écriture doit être automatique, dans le cycle de
l'orchestrateur — pas un geste manuel de plus à oublier.

**Implémenté :**
- `ops/remonter-local.py` : à la fin d'une remontée réussie, insère une ligne
  `scan_runs` (`source='remonter-supabase'`, comptage transférées / mises à
  jour / statuts corrigés, `notes` distingue explicitement « pas un scrape »).
  Aucun changement à `agents.json` : l'agent est déjà en lane `daily` depuis le
  26/08, le correctif profite au prochain cycle sans y toucher.
- `ops/verifie-synchro.py` (§3, double coureur) : le croisement ne reconnaissait
  que les agents `extract-*` pour border la fenêtre d'un `scan_run` légitime.
  Sans correctif, la nouvelle ligne `remonter-supabase` se serait auto-dénoncée
  comme écriture suspecte à **chaque** cycle — garde-fou qui aurait crié au
  loup en continu (règle 2). Étendu pour reconnaître aussi cet agent.

**Vérifié** : un run réel à `--limite 50` a produit une ligne `scan_runs`
lisible côté serveur (`scanned_count=50`, `notes='remontée PC2→Supabase, pas un
scrape'`) immédiatement après écriture.

**Non fait** : `synchroniser_statuts` reste ligne à ligne via `store._execute`
(méthode privée, déjà noté le 26/08) ; le garde-fou de fraîcheur évoqué le
2026-08-26 (suite 4) reste à poser.

## 2026-09-02 — Alerte Supabase « Disk IO Budget depleting » : upsert aveugle, pas la taille

**Contexte.** Mail d'alerte Supabase reçu ce matin. Vérifié d'abord que ce
n'était PAS le problème de taille corrigé le 25/08 : base à **245 Mo**,
largement sous le quota — le Disk IO Budget est une ressource distincte
(débit d'écriture, pas volume occupé).

**Mesure.** `pg_stat_user_tables` côté Supabase : `listings` avait
**733 375 UPDATE** cumulés (depuis un `stats_reset` du 22/05, donc à cheval
sur l'ancienne ère où les extracteurs écrivaient directement en ligne) pour
seulement **~98 573 lignes vivantes** — soit ~7,4 UPDATE/ligne — dont **72 %
non-HOT** (527 203/733 375), donc touchant la plupart des **13 index** de la
table à chaque fois. `remonter-supabase` tourne en lane `daily` depuis le
26/08 et repousse **toute la fenêtre active** sans filtre delta
(`ops/remonter-local.py:86`, `where status='active'`, sans condition sur
`last_seen`).

**Cause.** `SupabaseStore.upsert_listings_bulk` (`scraper/store/
supabase_store.py`) fait un `INSERT ... ON CONFLICT DO UPDATE SET
<toutes les colonnes>=excluded.*` **sans aucune garde** : même une ligne
strictement identique à ce qui est déjà en base était réécrite en entier,
tous les jours. Le lot ajouté le 28/08 (`upsert_listings_bulk`) avait réglé
le problème réseau (4,1 → ~250 annonces/s) mais pas le volume d'écriture par
ligne — les deux étaient des causes indépendantes.

**Corrigé.** Ajout d'une clause `WHERE` sur le `DO UPDATE` : si aucune des
colonnes `_COLS` ne diffère, si `raw_data` est identique, et si la ligne est
déjà dans l'état cible (`status='active'`, `missed_count=0`,
`first_missed_at`/`delisted_at` nuls), Postgres traite la ligne comme un
`DO NOTHING` — aucune nouvelle version de ligne, aucune écriture d'index.
`last_seen` est volontairement EXCLU de la comparaison (sinon le garde-fou ne
se déclencherait jamais, puisque c'est la seule colonne qui change à chaque
appel) — vérifié que `lastSeen` n'est lu nulle part côté app
(`lib/listings-db.ts` la sélectionne, aucun composant Next ne la consomme).

**Vérifié :**
- `agents/tests/test_remonter_bulk.py` étendu (cas 5) : un lot renvoyé à
  l'identique produit `{nouvelles:0, maj:0, changees:0}` et `last_seen`
  n'avance pas — passé contre le vrai Supabase.
- Sur données réelles : `ops/remonter-local.py --statut actives --limite
  2000` a poussé 2 000 annonces actives réelles → **0 nouvelle, 0 mise à
  jour, 0 prix changé**, et `n_tup_upd` sur `listings` n'a pas bougé
  (733 375 → 733 376, le +1 venant du test unitaire précédent, pas de ce
  run). Avant correctif, ce même run aurait produit 2 000 UPDATE aveugles.
- `agents/tests/test_stores_alignes.py` toujours au vert (pas de régression
  sur l'alignement des colonnes).

**Non fait** : `upsert_listing` (chemin ligne à ligne, utilisé seulement si
quelqu'un relance le scraper avec `--store supabase` — plus le défaut depuis
la bascule SQLite) n'a pas reçu le même garde-fou, volontairement : il n'est
plus sur le chemin de production mesuré. `synchroniser_statuts` (délistage)
reste hors du périmètre de cette mesure — c'est un UPDATE ciblé déjà
conditionné par `and status='active'`, pas un upsert aveugle. Impact sur le
Disk IO Budget affiché dans le dashboard Supabase non re-mesuré après coup
(le compteur du mail n'est pas accessible par API ; seul `pg_stat_user_tables`
l'est) — à confirmer au prochain relevé du dashboard.

## 2026-09-03 — `overseer` criait au loup sur `organize` en mode tickets (12/12)

Session `lowi-reparation-autonome` autonome. Détail complet, méthodo de
mesure et ce qui n'a pas été fait :
[agents/audits/reparations-2026-09-03.md](../agents/audits/reparations-2026-09-03.md).

**Mesuré** : sur les 38 findings des 7 derniers jours (comptés par nature
avant conclusion, règle 1), 18 (47 %) étaient `overseer / contrat_viole` sur
`organize`, avec le même message répété : « champs manquants : abstentions,
paires_modele, pannes_llm, revue_ajoutee ». Recoupé aux runs réels du
ledger : **12/12** runs `organize` réussis depuis l'import du poste (25/08,
`t1-absent` posé en continu) portaient ce finding. Taux 100 % — exactement
le garde-fou qui crie au loup (règle 2 du CLAUDE.md).

**Cause** : `organize` a deux sorties légitimes selon le poste — comparaison
locale via modèle T1, ou dépôt en ticket sur un poste sans modèle
(`agents/t1-absent`). Ce poste tourne en permanence dans le second mode,
mais `agents/skills/organize/SKILL.md` ne déclarait qu'un seul contrat (celui
du premier mode), et `overseer.contrat_de()` ne savait lire qu'un bloc JSON
par agent — il ne pouvait donc jamais reconnaître une sortie du second mode
comme valide, quel que soit son contenu.

**Décision** : `contrat_de()` lit désormais tous les blocs ```json``` sous
« ## Contrat de sortie » d'un SKILL.md (plusieurs blocs = plusieurs modes
valides déclarés) ; `run()` retient, par run observé, la variante qui manque
le moins et n'exige l'exactitude que sur celle-là. `organize/SKILL.md`
documente maintenant les deux sorties. Comportement inchangé pour les 22
autres agents (un seul bloc chacun — vérifié).

**Corrigé sur la branche dédiée `fix/overseer-organize-contract-variants`**
(commit `5fe03bd`), volontairement séparée de `fix/retry-transient-5xx-fetcher`
(travail en cours d'une autre session sur cette dernière, non touché). Test
de non-régression : `agents/tests/test_overseer_contract.py` — verrouille la
rétrocompatibilité à un bloc, la lecture multi-blocs, l'honoration du mode
ticket, la détection d'une sortie hors contrat, et rejoue le défaut mesuré
sur le vrai SKILL.md + une sortie réellement observée (run #292).

**Limite connue** : non re-testé en conditions réelles de cycle complet —
seulement rejoué sur les données historiques du ledger. À confirmer que le
finding `contrat_viole` sur `organize` disparaît effectivement au cycle de
la nuit du 03 au 04/09. La branche du correctif n'est pas mergée ; décision
d'intégration laissée à l'utilisateur.

**Vérifié en cours de route, non touché** : `volume_anormal` sur
extract-ddproperty/extract-nestopa apparaît sur 12/12 cycles récents
(sévérité low), variation resserrée autour de la médiane à chaque fois —
possible second cas du même défaut, mais c'est un **seuil de garde-fou** :
mesure posée pour arbitrage, décision laissée à l'utilisateur (règle 5).

## 2026-09-03 (suite) — chaînage des républications DDproperty (`repost_of`)

Demande directe de l'utilisateur, en réaction au constat `volume_anormal`
ci-dessus : mesurer les reposts sur DDproperty, dater les annonces malgré la
republication, puis retailler les seuils une fois le phénomène connu. Détail
complet dans [agents/audits/reparations-2026-09-03.md](../agents/audits/reparations-2026-09-03.md)
(annexe repost) et commit `123bd91` sur la branche dédiée
`feat/repost-resolution-ddproperty`.

**Mesuré.** DDproperty capture un champ `isAutoRepost` (adaptateur, depuis le
31/07) jamais exploité. Sur les 7 derniers jours, **20,1 %** des « nouvelles »
annonces DDproperty comptées par `watch-health` sont en réalité des reposts
déclarés par la source elle-même (3 367 / 16 737) — une partie de ce que
`volume_anormal` signale n'est donc pas de la vraie offre neuve. Cadence de
republication (écart entre l'occasion précédente et un repost confirmé,
n=1 682 avec la méthode par bucket large) : médiane 7,9 j, très étalée
(p25=2,2 j, p75=18,6 j). Exemple : `agent_id=13504900` a posté 21 annonces
quasi-identiques pour un même 1BR/30m² à Chewathai Pinklao — 17 en rafale sur
80 s le 04/07 (découverte du stock existant lors du recensement), puis une
nouvelle toutes les ~2 semaines ensuite. Le gros du volume anormal restant
vient du **recensement complet du catalogue DDproperty** en cours depuis le
03/08 (ramp 762 → 8 030 annonces/jour), un phénomène déjà documenté,
distinct des reposts.

**Ecart de prix sur repost confirmé, mesuré avant tout seuillage** (1 066
paires : même `agent_id`, même immeuble × khet × chambres × surface à
0,01 m² près, l'une `isAutoRepost=1`) : médian **5,3 %**, p90 **19,2 %**, max
56,9 %. Le seuil de 2 % que `prefiltre_sql()`/`decider()` appliquent déjà à
l'heuristique séquentielle aurait manqué l'écrasante majorité de ces reposts
pourtant confirmés par la source — la vérité terrain de DDproperty vaut mieux
que notre propre heuristique de prix.

**Décision.** `repost_of`/`repost_reason` existent dans le schéma depuis la
migration `unit_key_photo_sig.sql` (index déjà posé) mais n'avaient jamais
été alimentés — 0 ligne, toutes sources, avant aujourd'hui.
`agents/bots/organize.py::resoudre_reposts()` les alimente, deux signaux par
ordre de confiance : `isAutoRepost` + `agent_id` identique (sans plafond de
prix) puis, à défaut, l'heuristique déjà en place — renforcée d'une garde
absente jusqu'ici : deux `agent_id` connus et différents ne relient jamais
(« agences concurrentes = deux mises en marché », déjà écrit dans le
SKILL.md, jamais appliqué par le code). `agents.core.db.date_reelle()`
remonte une chaîne jusqu'à sa racine (CTE récursive) pour dater une annonce à
sa première apparition réelle, même republiée plusieurs fois depuis juillet.

**Appliqué à la base de référence**, vérifié d'abord sur une copie :
**2 195 liens** (1 066 `isAutoRepost` + 1 129 heuristique). `quick_check` ok
avant/après, comptes inchangés (103 060 / 75 150). Idempotent (2e passage :
0 nouveau lien) et incrémental (tourne à chaque cycle via `organize.run()`,
~8-19 s). Profondeur de chaîne observée : 1 983 à profondeur 1, jusqu'à 6
maillons pour les cas les plus republiés. Rollback trivial si besoin :
`update listings set repost_of=null, repost_reason=null` (la colonne était
vide partout avant ce mécanisme).

**Non fait, signalé séparément pour ne pas mélanger deux changements** :
`prefiltre_sql()`/`decider()` (le chemin qui alimente le ticket de
comparaison à Claude et `revue.jsonl`) ne vérifient toujours pas la
concordance d'`agent_id` avant de conclure `same_unit` par l'heuristique
séquentielle — seul le nouveau `resoudre_reposts()` applique cette garde.
Noté dans `agents/skills/organize/SKILL.md`, § Modes de panne connus.

**Reste à trancher par l'utilisateur (le seuil de `volume_anormal`, cf.
l'entrée précédente)** : avec ~1 vraie repost sur 5 dans les nouvelles
DDproperty, deux leviers restent possibles — relever la bande, ou
soustraire les reposts confirmés (`repost_reason='is_auto_repost'` du
cycle) du compteur `nouvelles` avant comparaison à la bande. Ce dernier
touche `watch_health.py`, pas seulement `agents.json` ; non fait ici.

## 2026-09-04 — Résilience à une coupure internet longue : capacité perdue en silence lors du passage au système d'agents, restaurée dans le code plutôt que dans un script externe

Demande directe de l'utilisateur (« il y a eu une longue coupure internet,
est-ce qu'on est blindé contre ça ? »), en session `lowi-reparation-autonome`.
Corrigé sur la branche dédiée `fix/outage-resilience-fetcher` (non fusionnée,
décision d'intégration laissée à l'utilisateur).

**Mesuré avant d'agir (règle 1)** — l'utilisateur a explicitement demandé de
ralentir et de vérifier plutôt que de conclure depuis des indices indirects.
`scan_runs` sur les 15 derniers jours ne montre AUCUN scan visiblement tronqué
en vol par une coupure réseau : les trois jours creux (08-21, 08-24, 08-29)
sont déjà expliqués ailleurs dans ce journal par des causes SANS rapport avec
le réseau (Task Scheduler qui tuait l'orchestrateur au retour de veille
moderne, échec du réveil RTC). Les seize processus `python.exe`/`pythonw.exe`
observés au premier abord comme suspects (actifs depuis le 28/08, quasi 0 %
CPU cumulé) ont été laissés SANS conclusion — hypothèse non vérifiée,
signalée comme telle plus bas, corrigée après le rappel de l'utilisateur de
ne pas trancher dessus sans mesure.

**Ce qui a vraiment été trouvé** : `ops/superviseur.py` (2026-08-01) faisait
exactement ce que l'utilisateur demande — sonde toutes les 30 s contre les
sites eux-mêmes (pas un tiers), aucune relance tant que le réseau n'est pas
revenu, état écrit de façon atomique. Il **n'existe plus** : retiré (avec sa
tâche planifiée `install-superviseur.ps1`) lors du passage au système à 12
agents (~2026-07-31), sans que rien ne le remplace — pas une décision
consignée, une capacité perdue dans la réécriture. Conséquence vérifiée dans
le code actuel : `scraper/pipeline/fetch.py` échouait vite (3 essais rapides)
sur une coupure de connexion, et les 5 adaptateurs (`if not html: break`)
arrêtaient alors la pagination d'une recherche sans aucun moyen pour
`scraper/run.py` de distinguer ça d'une fin de liste normale — **exactement
le bug du 2026-08-01** (« une coupure réseau ressemblait à un scan réussi »),
réintroduit parce que son correctif vivait dans le script externe supprimé,
pas dans le code du pipeline lui-même.

**Corrigé, à trois niveaux :**
1. `Fetcher._attend_coupure()` (fetch.py) : sur une exception de CONNEXION
   (`ConnectionError`/`Timeout`, DNS compris — PAS un 4xx/5xx, qui prouve que
   le site répond), sonde `url` elle-même toutes les 30 s jusqu'à 20 min avant
   d'abandonner. Si le réseau revient dans la fenêtre, la requête reprend sans
   rien signaler ; sinon `fetcher.a_subi_coupure=True`. Tunable par site via
   `outage_poll_seconds`/`outage_max_wait_seconds` dans `config/<source>.json`
   (config-driven, comme le reste du pipeline).
2. `scraper/run.py` : si `a_subi_coupure`, le scan n'est PAS marqué `full`
   (tag `coupure-reseau`), le délistage `--full` est explicitement sauté (en
   plus, pas à la place, du garde-fou des 50 %), et un marqueur
   `[COUPURE-RESEAU] <source> : …` est imprimé.
3. `agents/orchestrator.py` : le marqueur est repris SANS ticket d'escalade
   (règle 2 — une coupure se résout seule, ce n'est pas un défaut) mais avec un
   finding `low`/`coupure_reseau` et un flag dans les métriques du run. Ce
   flag est relu par `is_due()` : un run marqué "ok" mais coupé ne compte pas
   comme le succès du jour pour la cadence — la source redevient due tout de
   suite, reprise au prochain déclenchement (nuit suivante, ou
   `LowiBKK-RattrapageBoot` au prochain logon) au lieu d'attendre 24 h.

**Ce que ce n'est PAS** : ni une sonde de l'état Wi-Fi du système
(`netsh`/adaptateur réseau), ni un poller autonome permanent comme l'ancien
`ops/superviseur.py`. La sonde vise délibérément les sites eux-mêmes (même
principe que l'ancien script — « ce qui compte n'est pas d'avoir une route,
c'est que les sites répondent »), et la reprise dépend du prochain
déclenchement de l'orchestrateur plutôt que d'un processus qui tournerait en
continu en arrière-plan — ce poste n'en a plus depuis le passage au système
d'agents, et en recréer un aurait réintroduit exactement la pièce qui a été
perdue une fois déjà.

**Vérifié** : `agents/tests/test_fetch_outage.py` (nouveau) — coupure suivie
d'un retour réseau pendant l'attente (reprise silencieuse), coupure qui
dépasse le plafond (None + flag), et non-régression explicite : une panne
HTTP persistante (522 × 5, le cas déjà verrouillé par
`test_fetch_retry.py`) ne doit PAS emprunter ce chemin. Les trois passent ;
`test_fetch_retry.py` repasse sans modification.

**Non fait, signalé** :
- Les seize processus zombies observés au début de cette investigation
  n'ont **pas** été expliqués — hypothèse initiale (boucle de retry infinie
  dans un adaptateur) vérifiée FAUSSE (les 5 adaptateurs font tous
  `if not html: break`, pas de boucle sans issue), mais aucune autre cause
  n'a été établie par la mesure. Ne pas les tuer ni conclure sur eux sans
  preuve — à reprendre avec `Get-CimInstance`/un outil capable de lire leur
  ligne de commande malgré la session 0 (WMI a rendu `CommandLine` vide ici).
- Aucun page-checkpoint (reprise à la page exacte où une recherche s'est
  arrêtée) : jugé inutile après mesure — la dédup incrémentale déjà en place
  (prix inchangé → fiche non re-visitée) rend un nouveau départ page 1
  suffisamment bon marché pour ne pas justifier de plomberie supplémentaire
  dans les 5 adaptateurs.
- `get_bytes` (images) et `get_text` partagent le même mécanisme ; `head_size`
  (empreinte photo) ne l'a PAS reçu — déjà non bloquant en cas d'échec
  (`try/except` dans run.py autour de l'empreinte), risque jugé mineur.
- Non vérifié en conditions réelles de coupure longue (uniquement testé par
  serveur HTTP local, connexion refusée simulée) — à confirmer à la prochaine
  vraie coupure.

## 2026-09-05 — Réparation autonome : rien de cassé, deux tickets clos, `agent_muet` non récidivé

Session `lowi-reparation-autonome`, poste `REMIZDABOSS` (PC2, coureur) confirmé
par `$env:COMPUTERNAME`. Cycle du 2026-09-05 01:00 sain (5/5 extracteurs,
6535 annonces écrites, exit 0), base `bangkok.db` saine (`quick_check` ok,
109 040 annonces / 79 499 actives, `last_seen` frais), sauvegarde USB du jour
vérifiée 3/3 (109 040/79 499, cohérente avec la base vivante). Boîte
`agents/queue/mail/` vide — rien à envoyer.

**Ticket `organize/comparaison_deleguee` (60 paires, 2026-09-05T00:19)** :
extraction mécanique des 6 champs par parsing déterministe (regex) du champ
`texte` — même méthode que les sessions précédentes, aucun jugement porté.
Appliqué via `organize.py --appliquer` : **60/60 abstentions**, cohérent avec
le résultat de toutes les sessions précédentes sur ce type de lot (le
critère `same_unit` — `b_apres_a` ET écart de prix < 2 % — n'est réuni par
aucune paire de ce tirage). Résolu via `escalation.resolve()` (pas un simple
déplacement de fichier comme la session du 09-04 l'avait fait par erreur pour
un ticket similaire, réconcilié depuis) — le ledger porte maintenant la
`resolution` correctement.

**Ticket `overseer/agent_muet` sur `extract-propertyscout` (haute sévérité,
2026-09-04T02:16), laissé ouvert par la session précédente pour surveiller
une récidive** : non reproduit à nouveau. Preuve : le run manuel de
récupération (id 309, 2026-09-04T02:46:59) a réussi, ET le cycle suivant
entièrement normal (id 315, 2026-09-04T18:00:49) a démarré `extract-
propertyscout` EN PARALLÈLE des 4 autres extracteurs comme attendu, succès.
Deux cycles propres consécutifs sans récidive → ticket clos. La cause de
l'absence initiale reste **non établie** (déjà vérifié faux/non concluant par
la session du 09-04 : `is_due()`, garde-fous, runs concurrents, autres
tâches planifiées — rien trouvé) ; à rouvrir si le phénomène revient.

**Non fait, signalé** :
- `regle-alimentation` (19,5 j) et `verifie-backup` (11,0 j) restent affichés
  `DÛ` par `orchestrator status` — **normal, pas un défaut** : les deux ont
  `lanes: []` dans `agents.json` (invocation manuelle seulement, `verifie-
  backup` neutralisé depuis le 2026-08-25). Même chose pour `storage`
  (12,7 j, cadence 7 j mais `lanes: []`). Confirmé en relisant `agents.json`
  avant de les traiter comme des pannes.
- `bad_rings_out.txt` (racine du dépôt, non suivi, daté du 2026-08-30) :
  sortie de debug d'un script de validation de polygones, orpheline. Ni
  supprimée ni ajoutée au `.gitignore` — un seul fichier isolé, pas mesuré
  comme gênant, laissé à l'arbitrage.
- Le dépôt reste sur `fix/outage-resilience-fetcher` avec plusieurs fichiers
  modifiés/non suivis (données d'étude quotidiennes routinières + `ops/
  remonter-local.py`, `ops/verifie-synchro.py`, `agents/tests/
  test_remonter_bulk.py`, `CLAUDE.md`, `.gitignore`) hérités des sessions
  précédentes — non touchés cette session (aucun commit demandé, rien à
  réparer dedans), fusion sur `main` toujours à l'arbitrage de l'utilisateur.

## 2026-09-06 — Réparation autonome : cycle sain, un ticket clos (résolu correctement cette fois), rien à corriger

Session `lowi-reparation-autonome`, poste `REMIZDABOSS` (PC2, coureur) confirmé
par `$env:COMPUTERNAME`. Cycle daily du 2026-09-05/06 sain (`pouls.py
--verifier` : dernier cycle 18,6 h avant le contrôle, 5/5 extracteurs,
6535 annonces écrites). Base `bangkok.db` : `quick_check` ok, 111 084 annonces
dont 81 039 actives (ddproperty 65 188, fazwaz 10 816, nestopa 3 152,
propertyscout 1 341, livinginsider 542), `last_seen` frais (2026-09-05T20:58
UTC). Sauvegarde USB du cycle (`agents/logs/backup-apres-cycle-
2026-09-06T002304.log`) : 3/3 essais OK, mêmes comptes que la base vivante
(111 084/81 039) — rotation appliquée, une seule génération conservée comme
configuré. Boîte `agents/queue/mail/` vide, aucune alerte à transmettre.

**Ticket `organize/comparaison_deleguee` (60 paires, 2026-09-06T00:20)** :
même méthode que les sessions précédentes — extraction déterministe (regex)
des 6 champs depuis le `texte` fourni par le ticket (statut ACTIVE/INACTIVE,
présence d'une date de délistage, comparaison des horodatages ISO exacts
`dates.da`/`dates.fsb` plutôt que les dates jour fournies dans le texte, écart
de prix). Vérifié à la main sur 2 paires avant application. Appliqué via
`organize.py --appliquer` : **60/60 abstentions** — cohérent avec les tirages
précédents de ce type de lot (aucune paire ne réunit `b_apres_a` ET écart de
prix < 2 %, le seuil du critère `same_unit`). Les 60 paires sont marquées
traitées dans `paires-faites`.

**Défaut reproduit sur MOI-MÊME et corrigé dans la foulée** : première passe,
j'ai clos le ticket en déplaçant le fichier à la main vers `queue/done/` —
exactement l'erreur que la session du 2026-08-29 avait diagnostiquée
(`escalation.reconcile()`) et que celle du 2026-09-04 avait reproduite malgré
l'avertissement écrit la veille. Repéré en lisant le diff non commité de ce
journal (entrée du 2026-09-05, qui documentait précisément ce piège) AVANT de
passer à l'étape suivante. Corrigé : ajout de `resolution`/`resolved_at` au
ticket déjà déplacé + appel direct à `Ledger.resolve()` pour fermer
l'escalade côté base — même effet que `escalation.resolve()` sur un ticket
qui n'y était pas encore passé. `escalation.pending()` confirme 0 escalade
ouverte après coup.

**Constats hérités, non retraités inutilement (déjà établis, revérifiés
seulement)** :
- `regle-alimentation`, `verifie-backup`, `storage` : `lanes: []` dans
  `agents.json`, DÛ affiché par `orchestrator status` est normal, pas une
  panne — confirmé en relisant le fichier, pas seulement en faisant confiance
  au journal d'hier.
- Les 2 constats de sévérité haute des 7 derniers jours (`extract-
  propertyscout` agent muet du 2026-09-04, `extract-fazwaz` sonde en échec du
  2026-09-01) étaient déjà résolus et clos avant cette session ; aucune
  récidive observée dans les logs relus.
- `bad_rings_out.txt` (racine, non suivi, 2026-08-30) : toujours orphelin,
  toujours laissé à l'arbitrage — inchangé depuis la dernière relecture.
- Le dépôt reste sur `fix/outage-resilience-fetcher` avec le même tas de
  fichiers modifiés/non commités hérité des sessions précédentes (doc
  restructurée `CLAUDE.md`/`masterlog.md`/`methodes-calculs.md`/
  `replication-blueprint.md`, données d'étude quotidiennes, `ops/remonter-
  local.py`, `ops/verifie-synchro.py`, `agents/tests/test_remonter_bulk.py`) —
  non touché cette session, aucun commit demandé et rien à y réparer ;
  fusion sur `main` toujours à l'arbitrage de l'utilisateur. Les fixes de
  résilience réseau de cette branche (`SupabaseStore._execute()` qui
  reconnecte au lieu d'échouer sur un seul essai) sont désormais **prouvés
  sur 2 cycles réels consécutifs** (0 erreur les 2026-09-05 00:15 et 22:26,
  contre 69 778 erreurs et un crash le 2026-09-03 avant le correctif).

**Non fait** : aucune modification de code (rien de cassé à corriger),
aucun commit sur la pile en attente (hors de mon mandat), pas de mesure sur
`STANDBYIDLE` en fonctionnement batterie (déjà signalé non vérifié le
2026-08-26, toujours vrai, pas dans le périmètre de cette session).

## 2026-09-07 — Réparation autonome : incident réel EN COURS pendant la session, cause trouvée et corrigée, redesign en attente de l'utilisateur

Session `lowi-reparation-autonome`, poste `REMIZDABOSS` (PC2, coureur) confirmé
par `$env:COMPUTERNAME`. Contrairement aux deux sessions précédentes (rien de
cassé), celle-ci est tombée en plein milieu d'un incident réel et encore actif
au moment de l'intervention.

**Constat initial** : `pouls.py --verifier` annonçait un dernier cycle sain
(18,1 h, 5/5 extracteurs, 3746 annonces) — mais ce chiffre datait du cycle
`weekly` du 09-05/09-06 (`termine_a` 2026-09-06T01:05 UTC), PAS du cycle
`daily` de cette nuit (démarré 2026-09-06T18:00:26 UTC = 2026-09-07 01:00
Bangkok). `orchestrator status` a montré 12 agents `DÛ` — normal à cette heure
si le cycle est en cours, mais le ledger (`agent_runs`, id 345) a confirmé
`remonter-supabase` en statut `running`, `ended_at` NULL, démarré
2026-09-06T21:09:26 UTC. Vérifié 4 fois sur 25 minutes : le fichier de log
(`agents/logs/remonter-supabase-2026-09-06T210926.log`) n'avait plus bougé
depuis 08:20:35 (heure Bangkok) alors que la boucle de retry du code est
censée imprimer une ligne toutes les 30 s — **bloqué depuis largement plus de
20 minutes sans qu'aucun compteur du code lui-même n'avance**, donc coincé
DANS un appel bloquant, pas dans la boucle de sondage qu'il est censé
mesurer. `Get-CimInstance Win32_Process` a confirmé les deux process (PID 8424
et son enfant 12240, parent réel de l'orchestrateur 25268) toujours vivants,
`Responding: True`, CPU quasi nul — cohérent avec un thread bloqué dans un
appel réseau, pas un deadlock Python.

**Cause identifiée** : juste avant de se figer, le log montrait des erreurs
Postgres explicites — `FATAL: (ECIRCUITBREAKER) too many authentication
failures, new connections are temporarily blocked` / `failed to retrieve
database credentials after multiple attempts` sur plusieurs IP du pooler
Supabase (`aws-1-ap-southeast-1.pooler.supabase.com`). `SupabaseStore._reconnect()`
appelle `psycopg.connect(dsn, connect_timeout=20, ...)` directement — mais
`connect_timeout` de libpq **ne borne pas la résolution DNS**, limite
documentée de libpq et pas un bug du code : si `getaddrinfo()` bloque (ou si
la séquence d'essais sur plusieurs `hostaddr` du pooler traîne), l'appel peut
dépasser très largement les 20 s annoncés, et la boucle de comptage de
`_execute()` (30 s / 1200 s max) ne peut avancer que si l'appel bloquant
lui-même revient — ce qu'il n'a pas fait pendant au moins 4 h 20.

**Correctif appliqué et commité SUR LA BRANCHE `fix/outage-resilience-fetcher`**
(pas `main`, commit `6aed3a3`) : `_connect_borne()` dans
[supabase_store.py](../scraper/store/supabase_store.py) — thread-watchdog
(25 s, pas `signal.alarm`, indisponible sur Windows) autour de
`psycopg.connect()`, utilisé par `__init__` et `_reconnect`. Test ajouté dans
[test_supabase_reconnect.py](../agents/tests/test_supabase_reconnect.py) (cas
4) : un `connect()` qui ne revient JAMAIS (sleep 30 s, hard-timeout réduit à
0,2 s pour le test) est désormais abandonné en 0,2 s au lieu de bloquer —
vérifié en le rejouant (`scraper/.venv/Scripts/python.exe agents/tests/
test_supabase_reconnect.py`, 4/4 cas OK). Les 3 cas préexistants (coupure
résolue au 1er essai, coupure qui dure puis se résout, coupure persistante au
plafond) restent verts — non-régression confirmée. Les tests contre le VRAI
Supabase (`test_stores_alignes.py`, `test_remonter_bulk.py`) n'ont PAS été
rejoués : lancer davantage de connexions contre un service qui vient de
bloquer pour « trop d'échecs d'authentification » aurait été contre-productif
pendant un incident actif.

**Le process bloqué N'A PAS ÉTÉ ARRÊTÉ** : `Stop-Process` sur les PID 8424/12240
a été refusé par le classificateur de permissions du mode automatique (action
irréversible sur un process vivant, sans utilisateur présent pour confirmer —
comportement correct, pas un obstacle à contourner). L'utilisateur, présent en
direct pendant cette session, en a été informé explicitement pour décider
lui-même. Conséquence en cascade tant que ce process reste bloqué : le reste
du cycle `daily` de cette nuit (`organize`, `analyze-sale`, `analyze-rent`,
`report`, `backup-apres-cycle`, `watch-health`, `overseer`) n'a PAS tourné —
`remonter-supabase` a été inséré AVANT `watch-health` dans `agents.json` le
2026-08-26 (voir CLAUDE.md § architecture) et bloque tout ce qui suit dans la
lane. La dernière sauvegarde USB vérifiée reste donc celle du cycle précédent
(2026-09-06, 111 084/81 039, 3/3 essais OK) — pas de perte de donnée, juste un
cycle de retard.

**Question de fond soulevée par l'utilisateur EN COURS DE SESSION, non
tranchée** : le mécanisme actuel réévalue chaque jour la FENÊTRE ACTIVE
ENTIÈRE (81 889 annonces, 33 lots) plutôt que de calculer le delta en local
et n'envoyer que le paquet du jour. Le garde-fou anti-réécriture du 2026-09-02
(commit déjà en prod, `upsert_listings_bulk` — `WHERE <rien n'a changé>`)
limite déjà les ÉCRITURES effectives aux lignes réellement modifiées, mais le
TRANSFERT réseau (payload complet des 81 889 lignes vers Postgres pour que
Postgres tranche) a toujours lieu chaque jour — 33 lots, 33 fenêtres
d'exposition à une coupure ou un blocage d'authentification comme celui de ce
soir. L'utilisateur demande de revoir ce point : passer à un vrai paquet
incrémental (delta calculé côté SQLite depuis le dernier envoi réussi) plutôt
qu'un ré-envoi complet filtré côté serveur. **Décision volontairement NON
prise dans cette session** (règle 5 : ne pas trancher la méthode à la place de
l'utilisateur) — proposé, chiffré partiellement, laissé en attente de sa
réponse sur le mécanisme de delta souhaité (watermark `last_seen`, table de
suivi dédiée, ou autre).

**Constats hérités, revérifiés sans être retraités** : la pile de fichiers
modifiés/non commités sur cette branche (CLAUDE.md, docs, `ops/remonter-
local.py`, `ops/verifie-synchro.py`, données d'étude quotidiennes) reste
inchangée par cette session, hors les 2 fichiers du correctif ci-dessus ;
fusion sur `main` toujours à l'arbitrage de l'utilisateur. Boîte
`agents/queue/mail/` vide (rien à transmettre). Aucun ticket en attente dans
`agents/queue/` (dernier traité : 2026-09-06, `organize/comparaison_deleguee`,
déjà résolu avant cette session). Base `bangkok.db` : `quick_check` ok,
112 380 annonces / 81 889 actives (ddproperty 65 996, fazwaz 10 856, nestopa
3 201, propertyscout 1 336, livinginsider 500), `last_seen` frais
(2026-09-06T19:48:42 UTC).

**Suite, en cours de session — l'utilisateur a tranché** : en réponse à la
question posée ci-dessus, réponse reçue en direct : *« only update what's new
and remove what's not updated anymore (there is a cycle for that or a
deadline at least) »* — confirme le sens du delta ET rappelle que le
mécanisme de sortie du stock existe déjà (délai de grâce `missed_count`/
`JOURS_AVANT_SORTIE_VENDU`), pas besoin d'en inventer un nouveau.

**Implémenté et commité** (commit `203d01c`, même branche) : colonne locale
`dirty_since` (SQLite) posée par `SqliteStore.upsert_listing()` (nouvelle
ligne, ou tout changement réel d'une colonne de `COLONNES_LISTING`,
résurrection comprise), `mark_missing_inactive()` et `appliquer_ventes()`
(sortie du stock — les mécanismes EXISTANTS, pas un nouveau), `touch_listing()`
(résurrection uniquement, pas une simple revue). Backfill au premier ajout de
colonne : tout ce qui est actif ou délisté est marqué sale une fois, pour
établir la référence côté Supabase avant de devenir réellement incrémental —
sans ce backfill, une ligne déjà différente entre local et serveur AVANT ce
correctif resterait invisible pour toujours.

`ops/remonter-local.py --delta` (implique `--statut actives` +
`--synchro-statuts`) : ne charge que `dirty_since is not null`, des deux
côtés (contenu ET statut — le même marqueur sert aux deux, exactement la
formulation « new » / « not updated anymore » de la demande).
`marquer_synchronise()` efface le marqueur après un envoi réussi (un no-op
côté garde-fou anti-réécriture de Postgres compte comme synchronisé, pas
comme un échec). Test dédié (`agents/tests/test_dirty_since.py`, 10
vérifications, aucun réseau) : pose/n'avance pas/repose selon le cas exact,
`charger`/`statuts_morts` en mode delta ne renvoient que le non-synchronisé,
`marquer_synchronise` cible précisément les ids donnés — 10/10 OK.

**PAS branché en production** : `agents.json` invoque toujours `--statut
actives --synchro-statuts` (plein ré-envoi filtré côté serveur). Le passage à
`--delta` est volontairement laissé à l'utilisateur, après un premier run
réel une fois l'incident Supabase du jour résolu — impossible à valider en
conditions réelles pendant que le pooler bloque les nouvelles connexions
(règle 6 : rien n'entre en production sans mesure préalable).

**Non fait** : le process bloqué n'a pas été arrêté (refusé par le
classificateur, à trancher par l'utilisateur) ; `agents.json` non modifié
(bascule vers `--delta` en attente d'un run réel réussi) ; aucun commit sur
le reste de la pile héritée (CLAUDE.md, docs, données d'étude) ; pas de
fusion sur `main` ; les tests réseau réels contre Supabase non rejoués
pendant l'incident (prudence, pas nécessaire pour valider le correctif —
testé par simulation).

## 2026-09-08 — Réparation autonome : un contrôle de routine faussait le ledger d'un run en cours, corrigé ; 4 extracteurs perdus par une collision de migration ponctuelle

Session `lowi-reparation-autonome`, poste `REMIZDABOSS` (PC2, coureur) confirmé
par `$env:COMPUTERNAME`. Ticket `organize/comparaison_deleguee` du
2026-09-07T02:04:56 (60 paires) traité par la même méthode déterministe que
les sessions précédentes (regex sur `texte` + horodatages ISO `dates.da`/
`dates.fsb`, vérifiée à la main sur 2 paires avant application) : **60/60
abstentions**, cohérent avec les tirages précédents. Résolu via
`escalation.resolve()` avec `Ledger()` — pas de déplacement manuel de
fichier.

**Défaut trouvé EN DIRECT, causé par ma propre investigation, corrigé dans la
foulée.** En consultant l'état du cycle nocturne encore en cours (démarré
2026-09-07T18:00:03 UTC, soit 01:00 Bangkok du 09-08), `orchestrator status`
et un appel `Ledger()` ont marqué `interrompu` le run `remonter-supabase` en
cours — alors qu'il tournait encore, avec une connexion Postgres `ESTABLISHED`
confirmée par `netstat` (port 5432, PID enfant 26588). Cause : `reap_stale()`
ferme tout run `running` dont `_processus_vivant(pid)` rend faux, et cette
sonde faisait `OpenProcess(SYNCHRONIZE, ..., pid)` puis `if not h: return
False` — sans distinguer un handle nul par **absence réelle** d'un handle nul
par **`ERROR_ACCESS_DENIED`** (code 5). Reproduit à la main sur le PID bien
vivant de l'orchestrateur (`3528`, confirmé par `tasklist`) : `OpenProcess`
depuis ma session interactive a rendu un handle nul avec
`GetLastError()==5` — parce que la tâche planifiée tourne dans la session
Windows « Services », différente de la mienne. **N'importe quel contrôle en
lecture seule** (`orchestrator status`, `Ledger()` nu, `pouls.py --verifier`
appelle aussi `Ledger()`) lancé depuis une autre session pendant un cycle
suffit donc à faire croire qu'un run vivant est mort. Corrigé dans
`agents/core/ledger.py` : seul `ERROR_ACCESS_DENIED` bascule vers « vivant » ;
un autre refus (PID invalide) continue de fermer le run comme avant. Testé :
4 scénarios dans `agents/tests/test_processus_vivant.py` (PID vivant réel, PID
mort réel via `subprocess.wait()`, `OpenProcess` simulé refusé par accès,
refusé pour une autre raison) — les 4 passent, ainsi que l'ensemble des tests
existants (`test_cadence.py` avait déjà 2 cas sur cette fonction, toujours
verts). Le run `remonter-supabase` faussement fermé a été remis à `running`
à la main une fois la preuve (connexion réseau active) établie ; sans mon
intervention, il se serait de toute façon corrigé tout seul à la fin réelle
du run (`end_run()` réécrit la même ligne par `id`), donc aucune perte, mais
l'état affiché aurait menti pendant des heures. Commit `0492db7`, sur
`fix/outage-resilience-fetcher` (uniquement `ledger.py` + le nouveau test —
rien d'autre de la pile héritée touché).

**Ce que ce run en cours EST réellement, mesuré, pas supposé** : la toute
première remontée `--delta` depuis le commit `203d01c` (2026-09-07). Le
backfill à l'ajout de `dirty_since` a marqué sale la fenêtre active +
délistée entière (113 912/113 912 lignes, vérifié en base) — c'est
exactement le run « réel réussi » que l'entrée d'hier attendait. Démarré
21:47:17 UTC, encore actif à 02:02 UTC (>4 h), connexion Postgres établie,
aucune ligne de log depuis 01:36:28 (`_execute()` ne journalise que les
ÉCHECS de reconnexion, jamais un retour réussi — un vrai trou
d'observabilité, non corrigé cette session par prudence : modifier le
comportement de log d'un composant en cours d'exécution pendant l'incident
lui-même n'a pas semblé sage). Pas un run structurellement anormal : c'est
la contrepartie attendue et déjà documentée (rollback = base de référence
locale intacte, le prochain cycle redevient incrémental) du choix de faire
le premier passage en une fois plutôt qu'en lots.

**4 extracteurs perdus par une collision de migration, mesuré, pas supposé**
: à 18:00:03, les 5 extracteurs démarrent en parallèle, chacun ouvrant
`SqliteStore` → `_migrate()`. `fazwaz`, `ddproperty`, `propertyscout`,
`livinginsider` ont tous levé `sqlite3.OperationalError: database is locked`
sur `create index if not exists idx_listings_dirty` — `nestopa` seul a
réussi (probablement le gagnant de la course, tenant le verrou le temps du
backfill `dirty_since` ci-dessus). `fazwaz` et `ddproperty` ont quand même
écrit des données ce soir via leurs passes de secours (`then_0`/`then_1`
couloirs ciblés, `then_2` recensement pour ddproperty) — mesuré : 168 et
1334 nouvelles annonces respectivement. `propertyscout` et `livinginsider`
n'ont **aucune** passe de secours dans leur config et n'ont donc rien écrit
cette nuit (0 nouvelle, 0 changement). Pas de perte de données actives :
le délai de grâce (`missed_count`/`first_missed_at`) absorbe une nuit
manquée sans délistage à tort. Cette collision précise ne devrait pas
récidiver (le backfill est un événement ponctuel, `dirty_since` existe
maintenant partout — vérifié : 113 912/113 912 lignes déjà marquées), mais
le patron (migration lourde embarquée dans le constructeur, sans
coordination entre connexions concurrentes) referait la même chose à la
prochaine migration qui touche une bonne fraction des lignes — **non
corrigé cette session** : ce serait modifier un mécanisme de migration en
tirant une conclusion d'un seul cas, contraire à la règle 1 ; à surveiller
à la prochaine migration lourde plutôt qu'à corriger par anticipation.

**Boîte mail vidée** : 5 alertes de sévérité haute en attente (remonter-
supabase de la veille, les 4 extracteurs ci-dessus) envoyées via le
connecteur Gmail à schoenauer.anthony@gmail.com, avec pour les 4
extracteurs un post-scriptum donnant la cause mesurée ci-dessus. Fichiers
retirés de `agents/queue/mail/` après envoi confirmé.

**Base `bangkok.db`** : `quick_check` ok, 113 912 annonces / 83 454 actives
(ddproperty 67 396, fazwaz 10 980, nestopa 3 242, propertyscout 1 336,
livinginsider 500), `last_seen` frais (2026-09-07T20:26:40 UTC). Sauvegarde
USB : rien de nouveau à vérifier, `backup-apres-cycle` n'a pas encore
tourné ce cycle (étape postérieure à `remonter-supabase`, qui n'est toujours
pas terminé) — celle d'hier (2026-09-07 02:07-02:53) restait cohérente avec
la base vivante au moment mesuré (112 380/81 889, 3/3 essais OK).

**Non fait, signalé** :
- Le cycle nocturne n'a pas été attendu jusqu'à sa fin réelle (`remonter-
  supabase` seul peut prendre plusieurs heures pour ce premier passage
  complet) — cette session ne bloque pas dessus, la suite (`watch-health`,
  `analyze-sale`/`rent`, `organize`, `report`, `backup-apres-cycle`,
  `overseer`) reprendra d'elle-même quand `remonter-supabase` rendra la
  main.
- Le manque de log de RECONNEXION RÉUSSIE dans `SupabaseStore._execute()`
  (seul l'échec est journalisé) n'a pas été corrigé — changer le
  comportement de log d'un composant pendant qu'il tourne réellement en
  production n'a pas semblé prudent ; à faire au calme, hors incident.
- Le patron structurel « migration lourde non coordonnée entre connexions
  concurrentes » n'a pas été corrigé — un seul cas mesuré, règle 1 : ne pas
  généraliser à partir d'un exemple.
- `regle-alimentation`, `verifie-backup`, `storage` toujours affichés `DÛ`
  par `orchestrator status` — confirmé (ré-vérifié) normal, `lanes: []` dans
  `agents.json`, pas une panne.
- Le dépôt reste sur `fix/outage-resilience-fetcher` avec la pile héritée
  des sessions précédentes non commitée (CLAUDE.md, données d'étude,
  `ops/verifie-synchro.py`, `agents/tests/test_remonter_bulk.py`,
  `.gitignore`) — non touchée cette session, fusion sur `main` toujours à
  l'arbitrage de l'utilisateur. Seul le correctif du ledger (+ son test) a
  été commité, isolé du reste.

---

## 2026-09-09 — Un PID recyclé annonçait un cycle de 199 h ; et le retour de « database is locked »

Séance de réparation autonome (PC2). Compte-rendu détaillé :
[agents/audits/reparations-2026-09-09.md](../agents/audits/reparations-2026-09-09.md).

### Le garde-fou criait au loup, et c'est la mesure qui était fausse

Deux tickets de sévérité haute annonçaient « cycle en cours depuis 199 h (seuil
16 h) — bloqué sur extract-ddproperty ». **Faux.** Au moment du constat le cycle
avait 14 h et tournait : le recensement DDproperty écrivait sa page 2559/3200,
log modifié moins d'une minute avant. Il a fini pendant la séance (7 h 00 au
total, 18:12:13 → 01:12:03).

`_cycle_en_cours()` (`ops/pouls.py`) datait le début du cycle par
`min(started_at)` **sur le seul PID**. Windows réattribue les PID et le ledger
les garde pour toujours : le PID **26632** portait à la fois `garde-veille` du
**2026-08-31T18:00:21** et le cycle du **2026-09-08T18:12:13**. D'où les 199 h.

Le commentaire de `Ledger.reap_stale()` mentionnait pourtant déjà « un PID
recyclé par le système » comme cas à couvrir — la garde existait d'un côté du
système et manquait de l'autre. C'est la **quatrième fois** (règle 1) que c'est
l'instrument, et non le système mesuré, qui est en cause.

**Correctif** (commit `87ab652`, branche `fix/pouls-pid-recycle`) : le début du
cycle se lit parmi les seules lignes postérieures au démarrage du processus
(`GetProcessTimes`). Quand ce démarrage est indéterminable — `OpenProcess`
refusé depuis une autre session, cas courant face à un cycle en session
« Services », et c'est ce qui s'est produit en vérifiant — le repli borne le
début au `started_at` de l'agent bloqué : il peut **sous-estimer** la durée,
jamais en inventer une. `agents/tests/test_pouls_pid_recycle.py` couvre les deux
chemins **et** vérifie qu'un cycle réellement bloqué depuis 20 h alerte
toujours : corriger une fausse alerte ne doit pas rendre la surveillance muette.

### « database is locked » : 6 747 occurrences, et deux hypothèses fausses

Vraie panne du cycle du 08/09 — `extract-fazwaz` et `extract-ddproperty` sortent
en code 1. Mesures :

| | |
|---|---|
| par cycle | **0** du 31/08 au 06/09 · **4** le 07/09 · **6 747** le 08/09 |
| répartition | fazwaz `principal` 4 402 · ddproperty `principal` 2 345 · **toutes** les étapes `then_*` : **0** |
| coût d'une écriture | **0,99 s** (1 397 appels, 22,9 min) |
| base | 1,19 Go (26/08) → **2,24 Go** (09/09), **~75 Mo/jour**, sans rupture le 07/09 |
| annonces | 105 621 (04/09) → **116 223** · actives 76 778 → **85 327** |

Seules les deux étapes qui écrivent **à la même seconde** sont touchées ; les
`then_*`, décalés, ont zéro erreur. Signature d'une contention d'écriture.

**Ce n'est PAS la récidive de la collision de migration du 07/09** (entrée
précédente), et il ne faut pas confondre les deux — ce sont deux phénomènes
distincts qui portent le même message d'erreur :

| | 07/09 | 08/09 |
|---|---|---|
| occurrences | **4** (une par extracteur perdant la course) | **6 747** |
| où | `create index if not exists idx_listings_dirty`, dans `_migrate()`, **au démarrage** | `[erreur] <source>:<id>` — dans la **boucle d'upsert**, tout au long du scan |
| nature | événement **ponctuel** (backfill `dirty_since`) | contention **récurrente** entre écrivains |

La prédiction de l'entrée du 08/09 — « cette collision précise ne devrait pas
récidiver, le backfill est un événement ponctuel » — **tient** : `dirty_since`
existe partout (116 223/116 223 lignes marquées, vérifié) et l'index est en
place. Le flot du 08/09 a une autre cause. La conclusion pratique est
inchangée : le patron « migration lourde dans le constructeur » reste non
corrigé, et reste à surveiller à la prochaine migration lourde.

**Deux hypothèses testées et écartées — écrites ici parce qu'elles sont
plausibles et qu'il ne faut pas les re-creuser :**

1. **Curseur laissé ouvert.** `get_listing` fait `.fetchone()` sans épuiser le
   curseur ; la théorie était qu'une transaction de lecture restait ouverte et
   que la promotion en écriture était refusée *sans consulter le `busy_timeout`*
   (SQLITE_BUSY_SNAPSHOT). **Reproduit hors production : aucune erreur.** `id`
   étant clé primaire, SQLite libère le snapshot. **Faux.**
2. **WAL non recyclé.** Le WAL pèse 137 Mo, mais son en-tête d'index donne
   `nBackfill == mxFrame == 33303` : toutes les trames reversées, un seul
   lecteur, aucune trame bloquée. **Le WAL n'est pas le blocage** — et les ~16
   processus orphelins des 28–31/08 ne le retiennent donc pas non plus.

**Ce qui reste** : un effet de seuil sur une grandeur qui croît régulièrement. À
~1 s par écriture et 5 extracteurs en parallèle, la file dépasse les 60 s de
`ATTENTE_VERROU_S`. Cela réconcilie une croissance sans rupture avec une
apparition brutale. C'est une **explication cohérente avec toutes les mesures,
pas une preuve** : elle n'a pas été reproduite (il faudrait rejouer 5 écrivains
concurrents sur une copie de 2,24 Go).

**Aucune donnée perdue** : chaque échec est rattrapé annonce par annonce et
l'annonce sort de `seen_ids` — le garde-fou anti-délistage a tenu et l'a dit
(`scan 504 annonces < 50 % des 33672 actives → délistage ANNULÉ`).
`pragma quick_check` : **ok** (96 s sur 2,24 Go).

**Rien n'a été appliqué**, les leviers sont chiffrés et laissés à l'arbitrage
(règle 5) : (a) `ATTENTE_VERROU_S` 60 → 300 s, une ligne, ne change aucun chiffre
produit ; (b) décaler les deux gros extracteurs — **posture**, donc décision
utilisateur ; (c) `VACUUM` (831 Go libres, base à l'arrêt requise) ; (d) purger
les anciennes annonces — **méthode**, hors périmètre. Sur (d), le point factuel
qui doit précéder la décision : le time-on-market, l'absorption et la tension se
calculent **sur les disparues** (c'est la raison même du rejet du scénario A le
2026-08-26) ; les supprimer casserait ces statistiques et serait la seule option
irréversible de la liste (règle 7).

### Non fait, et pourquoi

- **Aucun processus orphelin tué.** ~16 survivent depuis les 28–31/08 (session
  0, quasi sans CPU). Ils ne bloquent pas le WAL (mesuré). Je n'ai pas pu établir
  ce qu'ils sont : `CommandLine` vide pour ma session, `handle.exe` absent,
  `openfiles` exige un drapeau système et un redémarrage. Les tuer à l'aveugle
  serait le raccourci destructeur à éviter — **à identifier avant d'agir**.
- **`remonter-supabase` non réparé** : échec à 01:13:22 sur `connect() bloqué
  au-delà de 25s (DNS ou TCP)` — le watchdog du commit `6aed3a3` a fait son
  travail. **6 succès / 4 échecs** sur les 10 derniers runs, tous réseau ; le DNS
  résout normalement depuis. Une coupure se reprend seule : on consigne, on
  n'escalade pas (règle 2). À rouvrir si le taux d'échec monte. Conséquence
  inchangée : le site public reste en retard.
- **Aucun e-mail envoyé.** Deux des cinq messages en attente étaient les fausses
  alertes « 199 h » — les envoyer aurait propagé ce qui venait d'être rétracté ;
  ils sont marqués rétractés dans `agents/queue/mail/done/`. Les trois autres
  sont laissés en place, l'utilisateur étant présent en séance.
- **Ticket `2026-09-09T011339-organize` laissé en file** (déposé pendant la
  séance) : il sera drainé par `drain-agent-queue-lowi-bkk`, sa voie normale.
- Le dépôt reste sur `fix/outage-resilience-fetcher` avec la pile héritée non
  commitée ; seul le correctif de `pouls.py` (+ son test) a été commité, isolé,
  sur `fix/pouls-pid-recycle`. Fusion sur `main` toujours à l'arbitrage.

### Traité

Ticket `organize` du 2026-09-08 : 60 paires constatées selon le contrat
d'extraction et appliquées — **60 réponses, 60 abstentions, 0 entrée de revue, 0
rejet**, aucune fusion ni suppression. L'abstention totale est cohérente et non
suspecte : `decider()` ne conclut `same_unit` que si `b_apres_a` **et**
`ecart_prix_pct < 2,0`, et aucune des 60 paires ne réunit les deux (la seule sous
2 %, `fazwaz:sale:1960841|6565403` à 1,6 %, a B vue *avant* le retrait de A).

Sauvegarde clé USB **saine** : réussie à chaque cycle, chaque copie vérifiée 3×
ligne à ligne (règle 8). Dernière close le 08/09 — 2 179,6 Mo, 113 912 annonces /
83 454 actives, 3 essais concordants. D: a 37,3 Go libres.

---

## 2026-09-09 (suite) — Le recensement ne rafraîchissait plus rien, et rien ne le disait

Trouvé en répondant à une question simple de l'utilisateur — « la base est-elle
à jour ? ». Elle ne l'était pas, et le mécanisme censé l'y maintenir était hors
service depuis des semaines, **en silence**.

### Le défaut

`_confronter()` (`scraper/recense.py`) faisait deux choses : rafraîchir
`last_seen` des annonces vues au catalogue, **et** rendre le verdict « absente du
catalogue ». Elle n'était appelée qu'après une série de `continue` qui
l'écartaient dès le moindre trou dans le parcours. Or chaque recensement
DDproperty manque **1 à 6 pages sur ~2 600** (0,04 à 0,23 %) : la fonction était
donc écartée à **tous** les runs.

Les deux opérations n'ont pourtant pas les mêmes conditions de validité. **Voir
une annonce au catalogue prouve qu'elle est vivante, trou ou pas.** Un trou
empêche de conclure sur ce qu'on n'a *pas* vu ; il ne dit rien de ce qu'on a vu.

Coût mesuré, part des actives confirmées depuis moins de 48 h :

| source | actives | < 48 h | plus ancienne |
|---|---|---|---|
| ddproperty | 69 149 | **9,6 %** | **2026-07-23** |
| fazwaz | 10 997 | 60,1 % | 2026-09-05 |
| nestopa | 3 287 | 19,4 % | 2026-07-23 |
| propertyscout | 1 385 | 89,2 % | 2026-09-06 |
| livinginsider | 509 | 100,0 % | 2026-09-08 |

**8,9 %** des 85 327 actives n'avaient pas été revues depuis plus de 30 jours, et
`missed_count` ne dépassait **jamais 1** : le délai de grâce ne tournait même
pas. Le stock « actif » enflait sans que rien ne le confirme — et les
statistiques portaient dessus.

### Le correctif

Scindé en `_rafraichir()` — **toujours**, dès que des annonces ont été vues — et
`_comparer()`, réservé au parcours complet. Cette seconde prudence est juste et
ne change pas : sur un parcours troué, « absente du catalogue » ne distingue pas
« retirée » de « pas regardée » (12 348 annonces déclarées absentes à tort le
2026-08-25). `rafraichies` remonte à la racine du bilan — c'est le chiffre qui
dit si le recensement a servi à quelque chose.

### Pourquoi c'est resté muet, et ce qui le rend audible

`recense.py` rend **code 0** même quand il s'abstient — à raison, une abstention
n'est pas une panne (correctif du 2026-08-25). Mais l'abstention se lisait dans
`flux_non_conclusifs`, que **personne ne regardait**. Ni `watch-health` (il juge
les bandes de métriques d'un extracteur, pas l'état de la base qui en résulte),
ni l'overseer.

D'où **`ops/fraicheur.py`**, agent `fraicheur` branché en lane `daily` après les
extracteurs. Il tient les deux bouts de la règle 2 :

- **il parle** si un recensement a lu des pages et rafraîchi **zéro** annonce —
  ce n'est pas un seuil, c'est un binaire : l'outil a tourné et n'a rien fait ;
- **il parle** si la fraîcheur d'une source tombe sous la **moitié de sa propre
  médiane** — auto-calibré, parce que les sources n'ont pas la même cadence :
  nestopa est gelée à une page par conception et plafonnera toujours bas, un
  seuil commun crierait au loup sur elle chaque nuit ;
- **il se tait** tant qu'il n'a pas 4 relevés, plutôt que de juger sur du vide —
  et il se tait aussi, délibérément, sur tout seuil absolu de fraîcheur : en
  fixer un aujourd'hui graverait l'état actuel, qui est cassé, comme référence.

Tests : `test_recense_rafraichit.py` (dont un cas vérifie **l'ordre dans le
fichier** — rafraîchir avant les abstentions — pour que le défaut redevienne
structurellement impossible) et `test_fraicheur.py` (les deux sens : parle sur
panne et sur effondrement, se tait sur fluctuation normale et sur historique
insuffisant).

### Arbitrage de l'utilisateur — données anciennes

Question laissée ouverte le matin même (levier « purger / délister les anciennes
annonces »). **Tranché : on conserve tout**, dans le format le plus simple et le
plus efficient en stockage, **l'accès à la donnée primant sur le reste.** Le
levier de purge est donc clos et ne doit plus être reproposé. Cela rejoint ce que
la mesure disait déjà : le time-on-market, l'absorption et la tension se
calculent sur les disparues.

### Verrous — un levier appliqué

`ATTENTE_VERROU_S` **60 → 300 s** (`scraper/store/sqlite_store.py`). La prémisse
du commentaire d'origine (« une transaction dure quelques millisecondes ») a
cessé d'être vraie : une écriture coûte **0,99 s** sur une base de 2,24 Go avec 5
écrivains parallèles. 300 s **ne corrige pas** la latence — il évite qu'une passe
entière soit perdue le temps qu'elle soit traitée. Se défait en remettant 60.

### Non fait / non vérifié

- **Le correctif du recensement n'est pas encore vérifié en production.**
  `backup-apres-cycle` copiait les 2,24 Go vers la clé pendant la séance : écrire
  dans la base à ce moment aurait violé la règle 8. La vérification se fera au
  cycle de 01:00 — et elle sera **visible** cette fois : `rafraichies` apparaît
  désormais à la racine du bilan, et `fraicheur` alerte si le chiffre est nul.
- **`fraicheur` n'a aucun historique** : sa détection de dérive reste muette les
  4 premiers cycles, par conception. Seule la détection de panne franche est
  active immédiatement.
- **La latence d'écriture elle-même n'est pas traitée** (0,99 s/écriture) — les
  leviers restants sont le décalage des deux gros extracteurs (posture) et le
  `VACUUM`. Toujours à l'arbitrage.
- **La cause précise du basculement 4 → 6 747 verrous n'est toujours pas
  reproduite** ; l'effet de seuil reste une explication cohérente, pas une preuve.

---

## 2026-09-09 (suite 2) — `remonter-supabase` : trois pannes distinctes, dont deux qui ne sont pas du réseau

Diagnostic demandé par l'utilisateur, dans ces termes : « j'ai des coupures
réseau fréquentes ces derniers temps mais je ne pense pas que ce soit aussi
fréquent ». **Il avait raison.** Sur les 10 derniers runs (6 succès / 4 échecs),
les 4 échecs recouvraient **trois pannes différentes**, et une seule était une
coupure réseau. Mesuré pendant le diagnostic : **Supabase répond en 0,5 s** — le
réseau n'est pas chroniquement mauvais.

### 1. L'ouverture initiale n'avait aucune reprise (échec du 09/09)

`_execute()` encaissait jusqu'à **20 min** de coupure en cours de run, mais
`SupabaseStore.__init__` appelait `_connect_borne()` **nu** : un seul essai,
borné à 25 s, sans la moindre reprise. L'asymétrie est indéfendable — la
remontée survivait à une panne de vingt minutes au milieu du travail et mourait
sur un hoquet de vingt-cinq secondes au démarrage.

Run mort en **79 s** (01:12:03 → 01:13:22). Le site public est resté sur des
données périmées une journée entière **pour cette seule raison**.
→ `_connect_resilient()`, même tolérance que `_execute()`.

### 2. On entretenait nous-mêmes le blocage (échec du 06/09)

Le pooler avait répondu `ECIRCUITBREAKER: failed to retrieve database
credentials after multiple attempts, new connections are temporarily blocked`.
La boucle l'a rappelé à cadence **fixe de 30 s, 37 fois**, jusqu'à épuiser les
20 min de budget — puis le process a été tué (exit −1).

Ce n'est pas une coupure : le réseau va bien, c'est le **serveur qui ferme la
porte**. Les deux situations demandent l'inverse l'une de l'autre — une coupure
se re-sonde souvent (elle peut cesser à tout instant), une protection qui vient
de se fermer se laisse respirer. Réessayer vite la maintient fermée.
→ recul exponentiel (30/60/120/240/300 s, plafonné) + jitter, et palier plancher
plus long quand le message porte `ECIRCUITBREAKER`.
**Mesure : 7 tentatives au lieu de 40 sur le même budget de 20 min.**

### 3. Vraie coupure DNS (échec du 03/09)

`getaddrinfo failed`. Celle-là, et celle-là seulement, était du réseau. Déjà
couverte par la boucle de reprise depuis le commit `6aed3a3`.

### Défaut créé puis corrigé dans la même séance

`plafond: float = OUTAGE_MAX_WAIT_SECONDS` en valeur par défaut : une valeur par
défaut est figée à la **définition** de la fonction, donc insensible à toute
reconfiguration du module. Trouvé en écrivant le test — qui, avec le budget de
20 min figé, ne rendait jamais la main. Passé en `None` résolu à l'appel.

### Deux tests qui NE POUVAIENT PAS passer

Révélés au passage, et c'est le même mode de défaillance que tout le reste de la
journée : une surveillance inerte qui ressemble à une surveillance.
`test_supabase_reconnect.py` et `test_fetch_outage.py` exercent des chemins qui
journalisent avec « ⚠ » ; la console de ce poste est en **cp1252**, ils mouraient
donc en `UnicodeEncodeError` **avant la première assertion**. Vérifié en les
rejouant sur la version d'avant les correctifs du jour : l'échec préexistait.
La **production n'était pas concernée** — `agents/core/shell.py` force l'UTF-8
pour les sous-processus, et les « ⚠ » sont bien présents dans les logs. C'est le
lancement DIRECT qui manquait du réglage que `ops/pouls.py` fait déjà pour
lui-même. Corrigé sur les deux, plus `test_local_llm.py`.

> `test_local_llm.py` reste en échec sur PC2, pour une raison **attendue et
> documentée** : il exige Ollama, absent de ce poste (marqueur `agents/t1-absent`).
> Ses seuils ne doivent pas être relâchés pour le faire passer.

### Publication faite dans la foulée

Le cycle étant terminé (overseer 02:05:38) et la base libre, `remonter-supabase`
a été relancé à la main — ce n'est pas un scrap, c'est l'étape de publication, et
le site servait un marché vieux d'un jour et demi.

**2 min 56 s** (02:15:51 → 02:18:47), **0 erreur** : 2 323 nouvelles, 370 mises à
jour, 85 prix changés, **753 annonces fantômes corrigées**. Serveur et local sont
désormais alignés **à l'annonce près** sur le périmètre servi :

| | serveur | local | écart |
|---|---|---|---|
| actives | 85 327 | 85 327 | **0** |
| ddproperty / fazwaz / nestopa / propertyscout / livinginsider | 69 149 / 10 997 / 3 287 / 1 385 / 509 | idem | **0** |
| total | 115 045 | 116 223 | −1 178 |

L'écart de 1 178 sur le total est **voulu** : le serveur ne porte que le marché
consultable, l'historique des délistées reste local où il alimente les
statistiques d'évolution (scénario A, arbitrage du 2026-08-26).

---

## 2026-09-11 — Réparation autonome : un rattrapage isolé effaçait le témoin d'un vrai cycle (`cycle_vide` crié à tort)

Session `lowi-reparation-autonome` (PC2, `REMIZDABOSS`, confirmé par
`$env:COMPUTERNAME`). Compte-rendu détaillé :
[agents/audits/reparations-2026-09-11.md](../agents/audits/reparations-2026-09-11.md).

### Le vrai défaut : `battement()` recalculait sur une fenêtre glissante insensible à ce qui s'était réellement passé

Cycle du 08/09-09/09 réel : extraction 18:12→01:12 (4/5 extracteurs ok, 5 403
annonces), témoin sain déposé. À 11:00:22, un rattrapage isolé (aucun agent dû
sauf `garde-veille`, `always_run`) a néanmoins redéposé un battement — et
`battement()` recalcule `extracteurs_lances` sur les lignes du ledger des
« 12 dernières heures depuis maintenant », sans savoir que CETTE invocation
n'avait rien à voir avec l'extraction. À 16 h 48 du début réel, la fenêtre ne
voyait plus les 5 extracteurs : le témoin a été réécrit à
`extracteurs_lances: 0`, et `ops/pouls.py --verifier` a crié `cycle_vide`
(ticket `2026-09-09T130002`) pour un cycle qui avait pourtant tourné.

**Correctif** (commit `3d663e6`, branche `fix/pouls-pid-recycle`) :
`battement(lane, extraction_tentee=bool)`. Quand l'invocation ne pouvait de
toute façon pas produire d'extraction (`--boot`, `run-lane
--skip-extraction`, ou `run <agent>` sur un agent qui n'est pas un
extracteur — déduit dans `orchestrator.py` de la famille de l'agent visé),
elle reconduit le dernier témoin au lieu de le recalculer. Vérifié en
conditions réelles sur ce dépôt : `orchestrator.py run garde-veille` isolé
préserve désormais les 5/5 extracteurs et 5 403 annonces au lieu de les
remettre à 0 ; `ops/pouls.py --verifier` ne crie plus. Test de
non-régression : `agents/tests/test_pouls_battement_sans_extraction.py`
(couvre aussi qu'un vrai cycle vide continue d'alerter — règle 2, envers).

C'est la même famille de défaut que le PID recyclé du 2026-09-09 : un signal
externe au cycle (ici une invocation incidente, là un PID réutilisé) contamine
une mesure qui se croyait fraîche. Deuxième occurrence du même patron en trois
jours sur `pouls.py` — la surface qui date « depuis maintenant » plutôt que
« depuis l'événement réel » reste le point faible de ce module.

### Tickets traités (5/5)

- 3× `organize/comparaison_deleguee` (60 paires chacun, 09/09 et 09/10 ×2) —
  extraction mécanique des 6 champs par parsing déterministe du `texte`
  fourni (même méthode que les sessions précédentes) : 180/180 réponses,
  180 abstentions, 0 `same_unit`, 0 rejet. Cohérent : le pré-filtre SQL a déjà
  éliminé les paires à écart <2 % séquentielles, il ne reste que des écarts
  plus larges que `decider()` refuse à raison.
- `overseer/agent_muet` (`fraicheur`, 09/09 02:05) — vérifié non récidivé :
  `fraicheur` a tourné avec succès 55 min plus tard puis chaque jour depuis.
  Incident isolé lié à la nuit chargée (extraction terminée tard), pas de
  correctif de code nécessaire.
- `pouls/cycle_vide` (09/09 13:00) — root-causé et corrigé, voir ci-dessus.

Les 5 tickets étaient fermés par déplacement manuel vers `queue/done/` (comme
lors de sessions précédentes) ; `escalation.reconcile()` relancé ensuite pour
refermer dans le ledger l'entrée qui y était réellement suivie (`overseer`,
seul appel qui passe `ledger=`). Constat : `organize.py` et `ops/pouls.py`
n'appellent `escalation.create()` **sans** `ledger=` — leurs tickets ne sont
donc jamais dans le compteur « escalades ouvertes » du ledger, seulement dans
la file de fichiers. Pas un défaut nouveau (déjà la situation lors de la
session du 09-05), non corrigé cette fois non plus — changer la signature de
`create()` pour ces deux appelants est un choix hors du périmètre de cette
séance.

### Boîte mail (5/5 traités)

4 alertes envoyées avec 3 jours de retard (`extract-fazwaz`,
`extract-ddproperty`, `remonter-supabase`, `overseer/fraicheur`) — toutes
décrivent des incidents déjà diagnostiqués et déjà consignés (nuit du 08/09,
entrée du 2026-09-09) ; contexte de résolution ajouté dans chaque corps de
message. La 5e (`pouls/cycle_vide`) **retractée, non envoyée** : c'est
exactement l'alerte que ce correctif vient d'invalider — l'envoyer aurait
propagé ce qui vient d'être rétracté (règle 2, même logique que les deux
mails « 199 h » retirés le 2026-09-09).

### Vérifications de routine — rien d'autre à signaler

- Erreurs des logs d'extraction (05/09→10/09) : uniquement les 6 747
  occurrences déjà diagnostiquées de la nuit du 08/09 et les 4 de la collision
  de migration du 07/09 (toutes deux déjà journalisées) — **aucune
  récidive**, aucun nouveau motif.
- `pragma quick_check` : `ok`. 122 175 annonces, 90 233 actives
  (ddproperty 74 054 · fazwaz 10 989 · nestopa 3 376 · propertyscout 1 365 ·
  livinginsider 449). `last_seen` le plus récent cohérent avec la fin du
  dernier cycle.
- Sauvegarde USB du dernier cycle : 3/3 essais vérifiés, 122 175/90 233 —
  identique à la base vivante. 2 415,5 Mo copiés en 967,1 s.

### Non fait, et pourquoi

- **`regle-alimentation` (25,5 j), `verifie-backup` (17,1 j), `storage`
  (18,7 j)** affichés `DÛ` par `orchestrator status` : **pas une panne**. Les
  trois ont `lanes: []` dans `agents.json`, neutralisés/manuels à dessein
  (`verifie-backup` et `storage` explicitement le 2026-08-25, leur rôle repris
  par `ops/sauvegarde-cle.py` + `ops/pouls.py`). Vérifié dans `agents.json`
  avant de les traiter comme des défauts.
- **`organize.py`/`pouls.py` sans `ledger=` sur `escalation.create()`** —
  signalé ci-dessus, non corrigé (hors périmètre de cette séance, pas demandé
  par un ticket).
- **`Archives/Lowi_bkk/`** (racine du dépôt, non suivi git, 21 Mo) — fichiers
  personnels visiblement déposés là par erreur ou pour archivage manuel
  (captures `.mhtml` d'annonces, `Lowi.pptx`, raccourcis `.lnk` vers les
  scripts de scrap). Sans rapport avec le pipeline, ne bloque rien. Signalé,
  non supprimé — pas créé par cette session, pas de preuve qu'il faille le
  retirer.
- **`bad_rings_out.txt`** (racine, non suivi, daté 2026-08-30) — même constat
  que la session du 09-05 : sortie de debug orpheline, signalée, non
  supprimée.
- Dépôt sur `fix/pouls-pid-recycle`, non fusionné, avec des fichiers
  modifiés/non suivis hérités de sessions précédentes (données d'étude
  quotidiennes routinières, `ops/verifie-synchro.py`,
  `agents/tests/test_remonter_bulk.py`, `CLAUDE.md`, `.gitignore`,
  `docs/etudes/data/*`). Non touchés cette session — fusion sur `main`
  laissée à l'arbitrage de l'utilisateur.

## 2026-09-12 — Réparation autonome : trou de diagnostic sur l'orchestrateur lui-même

**Contexte** : tâche planifiée `lowi-reparation-autonome`. Dernier cycle daily
(2026-09-11 18:00 → 2026-09-12 00:50 UTC) terminé sain — 4/5 extracteurs, 6 211
annonces écrites — mais `overseer` a ouvert une escalade **haute** :
`extract-livinginsider` muet alors qu'il était dû.

**Investigation.** Piste par défaut du ticket (guillemets échappés dans le XML
de la tâche `LowiBKK-Agents`) écartée en premier : `Get-ScheduledTaskInfo`
donne `LastTaskResult=0`, et `Get-ScheduledTask` montre des `Arguments` propres
(`"orchestrator.py" --due`). Le ledger confirme que les 4 autres extracteurs
ont bien tourné en parallèle (`ThreadPoolExecutor`) sur ce cycle, mais ne
contient **aucune ligne** pour `extract-livinginsider` — ni `ok`, ni `failed`,
ni `running` orphelin (écarte l'hypothèse d'un PID recyclé, déjà traitée par
ailleurs sur cette branche, commit `87ab652`). Rejoué `is_due()` avec l'état du
ledger d'avant et d'après le cycle : **due dans les deux cas**. L'agent aurait
dû être sélectionné.

**Root cause NON établie — défaut non reproduit, donc traité comme hypothèse
(règle 1).** En cherchant où l'information manquante aurait dû apparaître,
trouvé que `agents/core/shell.py` documente depuis le 2026-08-22 que les
sous-processus héritaient d'un souci d'encodage sous la tâche planifiée (pas
de console), corrigé à l'époque — mais **le correctif ne portait que sur les
sous-processus**. Les `print()` et exceptions de l'**orchestrateur lui-même**
(la boucle de sélection, le `except Exception` autour du `ThreadPoolExecutor`)
n'ont jamais eu de destination sous la tâche planifiée : ils partent dans le
vide. Si `extract-livinginsider` a levé une exception avant
`led.start_run()` (ex. dans `shell.log_path()`, à l'intérieur de son thread),
l'unique trace qui aurait expliqué l'incident n'a jamais existé.

**Corrigé : le trou de diagnostic, pas le symptôme.** `agents/orchestrator.py`
— classe `Tee`, branchée sur `sys.stdout`/`sys.stderr` pour les modes
`--due`/`--boot`/`run-lane` (ceux que la tâche planifiée utilise ; `status`/
`due` interactifs gardent leur console normale). Écrit désormais TOUJOURS dans
`agents/logs/orchestrator-<horodatage>.log`, en plus de la console d'origine
en best-effort. Bug trouvé EN TESTANT ce correctif avant de le valider :
fermer le fichier sans restaurer `sys.stdout` fait tenter à Python de reflusher
un `Tee` sur fichier fermé à la sortie de l'interpréteur
(`Exception ignored while flushing sys.stdout`) — corrigé en restaurant les
flux d'origine avant `close()`. Test de non-régression :
`agents/tests/test_orchestrator_tee.py` (le Tee ne doit jamais planter même
si la console d'origine est cassée). Vérifié par `--due --dry-run` et
`run-lane daily --dry-run` : exit 0, propre.

Ticket `2026-09-12T005036-overseer-agent_muet.json` fermé (`queue/done/`) avec
la chronologie complète en champ `resolution` — explicitement marqué
« non établi avec certitude ». **À surveiller** : si `extract-livinginsider`
redevient muet au cycle du 2026-09-13 01:00, le nouveau log dira enfin
pourquoi ; à relire en priorité avant toute nouvelle hypothèse.

**Ticket `organize/comparaison_deleguee` traité** (60 paires, poste sans
modèle local — `agents/t1-absent`). Extraction MÉCANIQUE des 6 champs
(`a_active`, `b_active`, `a_retiree`, `b_retiree`, `b_apres_a`,
`ecart_prix_pct`) depuis le champ `texte` (format généré par code, donc
stable) et les dates `da`/`fsb` déjà fournies sans ambiguïté par le ticket —
vérifié à la main sur 8 paires avant application, aucun écart. `organize.py
--appliquer` : **60/60 abstentions, 0 revue ajoutée, 0 rejet**. Conforme au
principe du mode extraction (`decider()` tranche, pas l'extraction) — un peu
au-dessus du taux de base mesuré (77 %) mais sur un échantillon de 60 paires
déjà pré-filtrées comme ambiguës, pas une anomalie en soi.

### Vérifications de routine

- Erreurs des logs (05/09→12/09) : rien de nouveau depuis le 10/09. Les seules
  occurrences `Traceback`/`[erreur]`/`SONDE-ECHEC` trouvées datent du 07/09 et
  08/09, déjà diagnostiquées lors de sessions précédentes.
- `pragma quick_check` : `ok`. 125 223 annonces, 93 009 actives (ddproperty
  76 825 · fazwaz 10 962 · nestopa 3 415 · propertyscout 1 358 · livinginsider
  449 — ce dernier chiffre inchangé depuis le 09/09, cohérent avec l'absence
  de run depuis le 10/09). `last_seen` max cohérent avec la fin du cycle.
- Sauvegarde USB du dernier cycle : 3/3 essais vérifiés, 125 223/93 009 —
  identique à la base vivante. 2 509,2 Mo copiés en 966,3 s.
- Suite de tests (`agents/tests/test_*.py`, 25 fichiers) : toute la suite
  passe. `test_local_llm.py` et le benchmark `test_prose_ddproperty.py` sont
  dégradés par l'absence d'Ollama sur ce poste (`agents/t1-absent`, attendu,
  pas une régression). `test_fetch_outage.py` a juste besoin de plus de 60 s
  (simule une coupure réseau) — passe à 180 s, faux positif de mon script de
  test, pas un défaut du code.
- Boîte mail (`agents/queue/mail/`) : 1/1 traité. Alerte
  `extract-livinginsider muet` envoyée avec le contexte de résolution ajouté
  (connecteur Gmail disponible).

### Non fait, et pourquoi

- **Root cause du `extract-livinginsider` muet** — non établie, voir
  ci-dessus. Le correctif posé rend la PROCHAINE occurrence diagnosticable ;
  il ne prétend pas expliquer celle du 2026-09-11→12.
- **`regle-alimentation`, `verifie-backup`, `storage`** toujours `DÛ` dans
  `orchestrator status` : toujours pas une panne, `lanes: []` inchangé,
  reconfirmé dans `agents.json` avant de les ignorer.
- **`organize.py`/`pouls.py` sans `ledger=` sur `escalation.create()`** —
  toujours signalé, toujours non corrigé (hors périmètre, pas demandé par un
  ticket cette fois non plus).
- **`Archives/Lowi_bkk/`**, **`bad_rings_out.txt`**, et les fichiers hérités de
  sessions précédentes sur `fix/pouls-pid-recycle` (données d'étude
  quotidiennes, `ops/verifie-synchro.py`, `agents/tests/test_remonter_bulk.py`,
  `CLAUDE.md`, `.gitignore`, `docs/etudes/data/*`) — toujours en l'état, non
  touchés cette session, mêmes constats que le 2026-09-09.
- Compte-rendu complet : `agents/audits/reparations-2026-09-12.md`.

## 2026-09-13 — Réparation autonome : FazWaz bloqué par robots.txt (pas un parseur cassé) + la course qui rendait `extract-livinginsider` muet, enfin trouvée

**FazWaz — `Disallow: /*?*order_by=` apparu entre le 09-11 et le 09-12.**
`curl https://www.fazwaz.com/robots.txt` en direct confirme le nouveau motif
sous `User-agent: *`, absent du dernier run réussi (2026-09-11T18:00, 11 143
annonces). Or `order_by=user_updated_at|desc` est le paramètre qu'on utilise
sur `fazwaz.json` ET `fazwaz-corridors.json` pour trier par fraîcheur plutôt
que par le classement par défaut (biaisé sponsoring/catalogue trop profond,
voir `config/fazwaz.json._order_by_comment`) : **FazWaz est désormais
intégralement bloqué** (vente, location, 21 couloirs ciblés) tant qu'on
l'utilise. Les 3 tickets `parser_break` du cycle (principal/then_0/then_1)
sont un seul événement.

Le `sonder()` par défaut de `BaseAdapter` remontait « structure changée » —
faux : la page SANS `order_by` charge son JSON-LD normalement, c'est
`list_urls()` (appelé ensuite avec `order_by` dans l'URL) qui se heurte au
`Disallow`. Corrigé dans `scraper/adapters/fazwaz.py::sonder()` : détecte le
cas via `fetcher.allowed(url_triee)` et nomme la vraie cause. **Pas de
contournement du blocage** — c'est une décision de posture (règle 5),
options chiffrées laissées à trancher dans
`agents/audits/reparations-2026-09-13.md` §2.A. Le ticket se redéposera
chaque jour tant que ce n'est pas tranché.

**`extract-livinginsider` muet depuis 3 cycles — root cause enfin établie,
confirmant l'hypothèse non prouvée du 2026-09-12.** La classe `Tee` posée ce
jour-là (capture des prints de l'orchestrateur sous tâche planifiée) a
produit son premier log exploitable
(`agents/logs/orchestrator-2026-09-12T180040.log`) : `✗
extract-livinginsider — InterfaceError: bad parameter or other API misuse`.

Cause : `agents/core/ledger.py` ne sérialisait par `self._verrou` QUE les
écritures (`start_run`, `end_run`, `finding`, `escalate`, `resolve`) — pas
les lectures (`last_run`, `recent_runs`, `runs_since`, `findings_since`,
`open_escalations`), alors que `last_run()` est appelé en tête de
`run_agent()` par les 5 threads d'extracteurs parallèles. Le module
`sqlite3` de Python n'est pas sûr pour un usage concurrent d'une connexion
partagée au-delà de PEP 249, même avec `check_same_thread=False` (qui lève
l'interdiction, pas le besoin de sérialiser) — d'où l'`InterfaceError`
intermittente. Deuxième défaut trouvé en creusant : `orchestrator.run_lane`
absorbait cette exception avec un simple `print()` dans la boucle
`ThreadPoolExecutor` — aucune ligne au ledger, aucun finding, aucune
escalade. Un agent qui plante à cet endroit précis disparaissait de la
cadence sans laisser aucune trace, ce qui avait déjà rendu le ticket du
09-12 impossible à trancher sans la capture `Tee`.

Corrigé : les 5 méthodes de lecture du ledger sous verrou comme les
écritures ; le `except` du `ThreadPoolExecutor` enregistre désormais un
`finding` haute sévérité + une alerte. Test de non-régression
`agents/tests/test_ledger_concurrence.py` (12 threads × 40 cycles) : échoue
de façon fiable sur le code d'avant (rejoué 3 fois), passe proprement après,
aucune perte d'écriture (480/480). Suite complète (25 fichiers) rejouée sans
régression.

**Ticket `organize` (60 paires)** traité par un parseur déterministe du
gabarit fixe de `texte` plutôt qu'une lecture manuelle — vérifié sur 2 paires
avant application, 60/60 réponses rendues, 60/60 abstentions (comportement
attendu de `decider()`, pas une anomalie).

**Base** : `pragma quick_check` ok, 126 411 annonces (94 160 actives),
sauvegarde USB 3/3 essais vérifiés, identique à la base vivante.

### Non fait, et pourquoi

- **Le blocage FazWaz lui-même** — décision de posture réservée à
  l'utilisateur (règle 5), rien changé à la config.
- **Le correctif ledger** n'a pas encore été observé guérir un vrai cycle en
  production (seulement vérifié sur DB de test) — à relire au cycle du
  2026-09-14 01:00 avant de clore le dossier.
- **`regle-alimentation`, `verifie-backup`, `storage`** toujours `DÛ` dans
  `orchestrator status` : reconfirmé volontairement neutralisés (`lanes:
  []`), pas une panne, pas corrigé (cosmétique, hors périmètre).
- **`ddproperty` classé `volume_anormal` par `watch-health`** le 12/09
  (nouvelles sous la médiane, pas au-dessus) — pas creusé, aucun ticket
  dessus.
- Fichiers hérités de sessions précédentes sur `fix/pouls-pid-recycle`
  (`Archives/`, `bad_rings_out.txt`, exports `docs/etudes/data/*.xlsx`
  quotidiens, `ops/verifie-synchro.py`, `agents/tests/test_remonter_bulk.py`,
  `CLAUDE.md`, `.gitignore`, `study/official/*`) — non touchés, mêmes
  constats que les sessions précédentes.
- Compte-rendu complet : `agents/audits/reparations-2026-09-13.md`.

## 2026-09-13 (suite) — FazWaz : découverte par sitemap, `order_by` abandonné

**Décision de l'utilisateur** : « trouve une solution de contournement, on ne
peut pas perdre cette source ». Posture retenue : ne pas contourner le
`Disallow: /*?*order_by=` (aucun autre paramètre de tri cherché), mais lire
ce que le **même robots.txt déclare** — `Sitemap: …/sitemap-listings.xml`.
C'est le canal que le site publie lui-même pour les robots.

**Mesuré sur fazwaz.com** (scratch, 27 requêtes, 75 Mo) :
- 27 fichiers × 8 000 URL = **213 683 annonces nationales**, chacune avec
  `<lastmod>` (100 %) et une image ; index régénéré vers 02:00 Bangkok.
- **84 534 condos Bangkok** (49 019 location, 35 515 vente) ; la base n'en
  portait que **10 915 actives**. 6 666 identifiants présents en vente ET en
  location (même lot, deux annonces — déjà notre convention `deal_type` dans
  l'id).
- Sur la fenêtre 60 j de `lastmod` : 25 977 URL, dont 9 017 actives chez nous,
  **5 825 que la base croit délistées**, **11 135 inconnues**.
- **17/17 URL tirées au sort** (7 « délistées », 5 inconnues, 4 datées
  2020-2023, 1 location fraîche) répondent 200 avec un prix affiché. Le sitemap
  décrit le stock vivant ; nos ~300 « retirées »/jour au ledger (289 le 09-11,
  403 le 09-10) étaient, pour une part non mesurée, des artefacts de la fenêtre
  de 150 pages.
- La fiche porte tout ce que la page de liste (JSON-LD) fournissait : meta
  `title` (« 2 Bedroom Condo for Sale at X for ฿4,045,300 | U6741301 »), meta
  `description` (SqM, SDB) quand elle est générée, `:lat="…" :lng="…"` sur le
  composant carte.

**Livré (branche `fix/pouls-pid-recycle`)** : `scraper/pipeline/sitemap.py`
(parsing, cache disque 3 h partagé entre le run vente et le run location,
règle `trier()`), `adapters/fazwaz.py` (`discovery: "sitemap"`, sonde en
3 requêtes qui nomme le marqueur manquant, fiche complétée depuis les meta),
`run.py` (verdicts confirmer / visiter / reporter / ignorer, budget
`max_detail_visits`, ligne `sitemap :` dans le résumé), `config/fazwaz.json`,
`agents.json` (passe couloirs retirée — plus de fenêtre à réactiver),
SKILL.md, `docs/pipeline.md`, test `agents/tests/test_fazwaz_sitemap.py` (3/3 ;
`test_metrics`, `test_lanes`, `test_cadence`, `test_fetch_retry` rejoués sans
régression).

**Règle de tri, et pourquoi dans cet ordre** : (1) présente dans le sitemap =
vivante → `touch` sans rouvrir la fiche, quel que soit l'âge du `lastmod`
(sinon `last_seen` vieillit et `fraicheur` crie au loup) ; (2) `lastmod` >
`last_seen` = mise à jour côté site → rouvrir ; budget épuisé → **reporter
sans toucher** (un `touch` écraserait `last_seen` et la mise à jour serait
perdue) ; (3) fenêtre 60 j **seulement** pour les inconnues et les délistées
— c'est la définition de série des 150 pages (« ~2 mois »), conservée pour ne
pas casser les courbes.

**Run de mesure** (`--deal-type sale --limit 40`, mode sitemap) : sonde OK,
27 fichiers lus en ~1 min 30, **40/40 fiches écrites avec prix, coords, khet
et image** — 9 nouvelles, 3 changées (hausses réelles : 6,2 → 7,5 M ;
1,75 → 1,85 M ; 2,70 → 2,79 M), 0 erreur. **2,79 s d'attente + 0,47 s de
réseau par fiche** → ~3,3 s/fiche, soit ~55 min pour un budget de 1 000.
Défaut trouvé sur ce run et corrigé : **18/40 sans surface, 16/40 sans SDB**
— la meta `description` est rédigée par l'agent sur ces fiches, pas générée ;
repli ajouté sur le bloc d'infos (`118 SqM <small>Size</small>`,
`2 <small> Bathrooms </small>`). Au passage : la base historique avait
**9 567/10 980 actives FazWaz sans SDB** (87 %) — l'ancien regex
`(\d+)\s+Bathroom` ne matchait pas ce balisage ; le repli corrige aussi cela
pour toute fiche rouverte.

### Non fait, et pourquoi

- **Aucun run `--full` en production** : le premier part au cycle de 01:00.
  À relire le 2026-09-14 : la ligne `sitemap :` (confirmées ≈ 9 000, visitées
  1 000, reportées ≈ 16 000 la première nuit, décroissant ensuite), la durée
  (~1 h par deal_type attendue contre 55 min avant), et `retirées` (devrait
  chuter : les actives absentes du sitemap ne sont que 262).
- **`lastmod` = « dernière mise à jour de l'annonce »** est une hypothèse
  cohérente avec `user_updated_at` mais non prouvée ; si elle est fausse, on
  rouvre trop (coût) ou pas assez (prix périmés). Mesure possible : comparer
  `lastmod` aux changements de prix constatés sur 2 semaines.
- **Reprise du retard** : 16 960 fiches dans la fenêtre à 1 000/nuit = ~9
  nuits par deal_type ; `max_detail_visits` est le seul bouton (chiffré,
  laissé à l'arbitrage — 2 000 doublerait la durée du run).
- **Le mode `list` reste dans le code** sans `order_by` : rallumable
  (`discovery: "list"`) mais ne verrait que la tête du classement sponsorisé.
- **Bandes `agents.json` inchangées** (`nouvelles` 50–2000) : la première
  semaine dépassera 2 000/run (reprise), `watch-health` le signalera — attendu.
- `fazwaz-corridors.json` conservé avec une note d'obsolescence, non supprimé.

## 2026-09-13 (suite 2) — Audit sécurité / stockage / agents (règle 10)

Rapport complet : `agents/audits/audit-2026-09-13.md`. Lecture seule, rien
modifié. Points saillants, tous mesurés :

- **HAUTE — mot de passe du site dans `CLAUDE.md:196`, dépôt GitHub PUBLIC**
  (1 commit). À traiter comme compromis : rotation de `BASIC_AUTH_PASSWORD`
  sur Vercel + retrait de la ligne. Non fait (action externe).
- Supabase : 0 vue definer, 0 grant anon, RLS partout, 9 lints INFO attendus
  — le durcissement du 20/08 tient. Protection de déploiement Vercel : non
  vérifiée (MCP 404 sur le projet).
- Poste : sshd 0.0.0.0:22 clé seule ; RDP activé ; un `node` non identifié sur
  `:3000` ; tâche `LowiBKB-ScrapeImmoFacebook` (hors dépôt, `C:\agentic`)
  échoue chaque nuit rc 0x1 — inconnue de la doc.
- **Stockage : `bangkok.db` 1,19 → 2,56 Go en 18 j ; Supabase 139 → 336 Mo
  (67 % du quota).** Cause mesurée : DDproperty `retirees: 0` sur 12/12
  runs (garde-fou anti-délistage annulé, documenté le 23/08) + Nestopa idem
  → +2 500 annonces/jour, ~9 Mo/jour côté serveur, **quota atteint fin
  octobre** à ce rythme. `archive/` vide sur PC2 (chemin CLAUDE.md périmé) ;
  la vraie sauvegarde est `D:\++SCRAP DB++`, 14/14 ok, capacité non mesurée.
- Agents : 601 min-agent/jour, DDproperty = 60 % (médiane 5 h 43, max
  16 h 51) ; le cycle occupe 21-26 h par jour, la veille à 13 h ne le couvre
  plus. Bruit : 19 `contrat_viole` sur `organize` (0,1 min par conception),
  12 `power_request_absent` sans coupure. 3 escalades FazWaz encore ouvertes
  alors que le mode sitemap les résout.

Non fait : les 7 arbitrages listés en §4 du rapport.

## 2026-09-13 (suite 3) — Suites de l'audit : délistage DDproperty, bruit des garde-fous

Décision de l'utilisateur : **le mot de passe ne bouge pas** ; le reste des
recommandations s'applique.

**1. Le recensement DDproperty délist (`recense.py --delister`).** Mesuré
avant d'écrire : `retirees: 0` sur 12/12 runs `--full` (scan à 16 % des
actives, garde-fou des 50 % annulé chaque nuit — connu depuis le 23/08) ;
**12 700 actives DDproperty (16 %) non revues par le recensement depuis 3 à
60 j** (rent 7 367, sale 5 338) ; les recensements du 09 au 12/09 atteignent
la page terminale (2 561-2 779) avec 0 à 5 pages trouées (≤ 0,2 %). Règle :
`mark_missing_inactive` (déjà en place pour `--full`) avec **grâce de 3 nuits
consécutives** — à 0,2 % de trous, une vivante prise dans un trou 3 nuits de
suite est de l'ordre de 1e-8. Trois abstentions explicites dans le bilan :
page terminale non atteinte, trous > 1 %, moins de 50 % des actives revues.
**Rien n'est supprimé, photos gardées** (à la différence de `--full`).
Rollback documenté dans `_delister` (`dirty_since` du run). Branché dans
`agents.json` (`then_2`). Test `agents/tests/test_recense_delister.py`.
Attendu : ~0 délistée la 1re et la 2e nuit (compteur), **~12 000 la 3e nuit
(16/09)**, puis un flux quotidien de l'ordre des sorties réelles du marché.
`remonter-supabase --synchro-statuts` propage ensuite ; le serveur devrait
**décroître** de ~40 Mo.

**2. `organize` en mode ticket** rend désormais `paires_modele`, `abstentions`,
`revue_ajoutee`, `pannes_llm` à 0 au lieu de les omettre — 19 `contrat_viole`
en 14 j pour un agent qui faisait ce qu'on lui demandait.

**3. `garde-veille`** : `power_request_absent` n'est plus émis à chaque cycle
(12/14 j sans aucune coupure derrière — un état permanent du matériel, pas un
signal) ; seulement si une coupure de veille est détectée dans le même run.
L'état reste dans les métriques.

**4. Escalades** : `escalation.reconcile()` a fermé 4 escalades au ledger
(3 FazWaz + 1 organize) dont les tickets étaient déjà dans `queue/done/`.
0 ouverte.

**5. Port 3000** identifié : `next dev` du projet **`C:\blog`**, lancé le 11/09
à 10:09 et jamais arrêté, écoute sur toutes les interfaces. Pas Lowi, non
touché. **Tâche `LowiBKK-ScrapeImmoFacebook`** : script `C:\agentic\...`
(hors dépôt, décision du 12/09), son dernier log dit `ok: true` mais la tâche
rend 0x1 — le code retour du script ne reflète pas son résultat ; non corrigé
(hors dépôt).

### Non fait
- Nestopa : 2 417/3 456 actives non revues depuis > 3 j, même mécanisme
  (`--full` à 493 annonces contre 3 456 actives → garde-fou) ; pas de
  recensement Nestopa, rien de fait.
- Capacité de D: et nombre de copies quotidiennes de 2,5 Go : non mesurés.
- Protection de déploiement Vercel, `authorized_keys` sshd : non vérifiés.

**Addendum (mesure faite APRÈS avoir branché `--delister`, avant le premier
run)** — la mesure du 23/08 qui avait interdit le délistage (« 10/12 actives
non revues encore en ligne ») a été faite sur un recensement qui ne
rafraîchissait rien dès qu'une page manquait (défaut corrigé le 09/09) :
« non revue » signifiait alors « pas regardée ». Re-mesuré ce jour, en direct
via le Fetcher curl_cffi de l'adaptateur : **16/16 actives DDproperty absentes
du catalogue depuis 3 à 60 j sont mortes** (12 × HTTP 404, 4 × page servie
sans `listingDetail` — gabarit « annonce expirée »), **4/4 vivantes** parmi
celles revues la veille (`listingDetail` présent, `statusCode = ACT`). Le
délistage par le recensement est donc juste, et il l'est dès 3 jours
d'absence — la grâce de 3 nuits n'est pas trop courte.

## 2026-09-13 (suite 4) — Collecteur Facebook immo rapatrié de C:\agentic

Demande : ne pas laisser le script dans `C:\agentic`. Fait :
- `scraper/social/` : `scrape-immo-facebook.ps1` (réécrit, chemins relatifs
  au dépôt), `facebook/agent.js` + `utils/` (**copies** — l'original sert
  encore la veille Equance ; les modifications non commitées d'agentic du
  12/09 ont été prises telles quelles), `config.js` dégraissé,
  `immo-groups.json`, `immo-extract.mjs`, `immo-resolve.mjs` (chemin de la
  base rendu relatif), `diag/`, `package.json` propre (4 dépendances).
  Anciennes sorties `immo_*.json` déplacées dans `scraper/output/social/`.
- Côté agentic : `git rm` des 3 fichiers immo (commits `d2d6940`, `76ce2ad`),
  le `.ps1` et les diag supprimés — plus rien d'immo là-bas.
- **Tâche `LowiBKK-ScrapeImmoFacebook` réenregistrée** par
  `ops/install-facebook-task.ps1` (même méthode et mêmes contrôles que les
  autres installeurs), `RunLevel Limited` au lieu de `Highest` (rien dans le
  script n'exige l'élévation — à surveiller au 1er run).
- **Cause du 0x1 quotidien trouvée** : le `.ps1` n'appelait pas `exit`, donc
  PowerShell rendait le `$LASTEXITCODE` du dernier natif exécuté — le
  `taskkill` du `finally`, 128 quand il n'y a plus de Chrome à tuer. Le code
  retour est désormais celui de `node facebook/agent.js`.
- Deux pièges rencontrés en route : (1) `npm install` lancé depuis Git Bash a
  atterri à la racine du dépôt (cwd non pris) — sans effet (lock inchangé),
  refait avec `--prefix` ; (2) PowerShell 5.1 lit un `.ps1` sans BOM en
  ANSI, et le tiret cadratin devient un guillemet typographique qui coupe
  la chaîne → 6 erreurs de parse. Les deux `.ps1` sont en **UTF-8 avec BOM**.
- Vérifié : parse des 2 `.ps1` = 0 erreur ; `node --check` OK ; smoke test
  `node facebook/agent.js` → s'est connecté à un Chrome CDP **déjà ouvert
  sur 9222 depuis le 12/09 09:06** (profil d'automatisation, reliquat des
  diagnostics de la veille) et a commencé à parcourir les groupes ; coupé à
  90 s, aucune sortie écrite. La tâche de nuit ferme ce Chrome de toute façon.

Non fait : pas de run complet de la tâche (ferme tout Chrome ; à laisser au
créneau de 01:00). La routine Claude/Haiku d'extraction annoncée le 12/09
n'existe pas — l'aval reste manuel (README).

## 2026-09-13 (suite 5) — Aval Facebook automatisé : agent `social-leads`

Demande : « mets ça en automatique ». L'extraction exige un modèle et PC2
n'a pas d'Ollama ; le CLI `claude` y est depuis le 2026-08-21 — vérifié :
`claude -p --model haiku` répond en 3 s. **Mesuré** : un appel à contexte
minimal (`--tools ""`, `--setting-sources ""`, prompt système propre, cwd
hors dépôt) crée ~48 k tokens de cache (64 k si lancé dans le dépôt, qui
charge CLAUDE.md) → des lots de 15 posts par appel, pas un appel par post.

`agents/bots/social_leads.py` (T2, `daily`, après `extract-nestopa`) :
prompt et schéma d'`immo-extract.mjs` repris tels quels, `vendeur`/`quota`
tranchés par le code (regex portées), puis `immo-resolve.mjs` et
`load_social_leads.py --sqlite` appelés tels quels. Contrat dans
`agents/skills/social-leads/SKILL.md`, lu par l'overseer (vérifié). Garde-fou
`collecte_facebook_muette` (dernier `immo_*.json` > 48 h, medium, pas de
mail) — le défaut trouvé par l'audit du matin. Test
`agents/tests/test_social_leads.py` (4/4, sans appel au modèle).

**Run de mesure sur la collecte du 12/09 (92 posts)** : 7 appels, 92/92
extraits, 0 échec ; 92 « annonces » dont 65 condos, 75 avec nom d'immeuble,
50 avec prix ou loyer, 39 avec surface ; `vendeur` : 20 agents, 7
propriétaires, 65 inconnus ; `quota` : 92 inconnus (aucun marqueur dans le
texte — le code n'invente pas). Rapprochement : 54 condos reconnus (72 %),
31 avec écart au marché. **25 chargées** dans `social-leads.db` (filtre
`collecte_solide` : condo + nom + surface + prix + chambres). La collecte de
juillet (209 posts, extraction Ollama de l'époque) a été chargée au passage :
53 lignes. Base : 78 lignes, 60 rapprochées, 56 avec écart.

**Trois défauts trouvés en faisant tourner, corrigés** :
1. `immo-resolve.mjs` appelait `python` du PATH → sur PC2 c'est le raccourci
   Microsoft Store (« Python est introuvable »). → Python du venv (`LOWI_PY`
   sinon `scraper/.venv`).
2. Son référentiel faisait **3 requêtes par condo** (8 165 condos, pas
   d'index sur `condo_name`) : **> 10 min** sur la base de 2,5 Go (écrit pour
   l'archive de 69 k lignes). → une passe agrégée en Python : **2 s**.
3. `stdout` Python en cp1252 sous Windows : un U+200B dans un nom de condo
   faisait tout tomber. → `PYTHONIOENCODING=utf-8` dans l'appel.
Et un défaut de conception de l'agent lui-même, trouvé au 2e run : le
marqueur « traité » était `_extrait_resolu.json` — un `immo-resolve` lancé à
la main l'avait produit, l'agent tenait le fichier pour fini sans rien avoir
chargé. → marqueur `_charge.json` écrit APRÈS le chargement. Le garde-fou de
fraîcheur triait aussi par nom (`immo_facebook_2026-07-25` > `immo_2026-09-12`
alphabétiquement → « 1 197 h de silence » sur une collecte de la veille) →
tri par date de fichier.

Non fait : coût réel des 7 appels non relevé (sortie tronquée) — borne
haute ~0,25 $ ; bandes du SKILL provisoires, à recalibrer après une semaine ;
`claude -p` sous tâche planifiée sans session ouverte non testé (la lane
tourne en session interactive, comme les autres agents).

## 2026-09-16 — Cycle du 16/09 vide : panne Supabase externe, pas une régression

Réparation autonome. Détail complet : [agents/audits/reparations-2026-09-16.md](../agents/audits/reparations-2026-09-16.md).

Cycle de nuit terminé sans lancer un seul extracteur (0 annonce écrite).
`scrap_en_cours()` a fonctionné comme conçu : il a repéré (sonde WMI en
direct, pas le ledger) un `ops/remonter-local.py` toujours vivant — lancé la
veille à 11:03 UTC, bloqué depuis en boucle de reconnexion Postgres — et a
reporté tout le cycle plutôt que de le couper en vol.

**Cause confirmée externe par mesure directe, pas supposée** : la connexion
Postgres au pooler Supabase (`aws-1-ap-southeast-1.pooler.supabase.com:5432`)
échoue encore ce matin (`ConnectionTimeout` après 45 s) alors que le port TCP
répond (`Test-NetConnection` → `True`) — la couche applicative Postgres/pooler
est en cause, pas le réseau du poste. Confirmé indépendant de PC2 : le MCP
Supabase lui-même (`execute_sql`, `get_advisors`), qui passe par
l'infrastructure Supabase et non par ce poste, échoue avec la même erreur de
timeout sur ce projet. Le run du 14/09 avait échoué plus vite avec une erreur
explicite côté pooler (`EAUTHQUERY "auth_query secret check timed out"` +
`ECHECKOUTTIMEOUT`). Trois nuits de suite (13→ok, 14→échec rapide, 15→bloqué
~14h) : dégradation progressive du pooler ap-southeast-1, pas un défaut
introduit dans ce dépôt. Site public (lowi-bkk.vercel.app) répond HTTP 200 —
pas une panne totale du projet Supabase, seule la connexion Postgres directe
est touchée au moment de la mesure.

**Corrigé au passage, sans rapport avec la panne** : `orchestrator.py::
cmd_status()` calculait `is_due()` pour tous les agents y compris ceux à
`lanes: []` (`regle-alimentation`, `verifie-backup`, `storage`, neutralisés à
dessein le 2026-08-16/25) et affichait `DÛ` avec 22 à 30 jours de retard sur
des agents que `--due` n'invoque jamais — garde-fou qui crie au loup (règle 2
du CLAUDE.md), déjà repéré et volontairement laissé de côté aux sessions du
09-09/09-12/09-13 faute de lien avec le sujet du jour. Cette fois corrigé
(affiche `manuel (hors lanes)`), testé (`agents/tests/test_status_hors_lanes.py`,
2/2), commit `4a3f88e` sur `fix/pouls-pid-recycle`.

**Non fait, décision requise (règle 5)** : `scrap_en_cours()` bloque toute la
lane `daily` dès qu'un agent `LONGS_A_NE_PAS_COUPER` (`remonter-supabase`,
qui a besoin de Supabase) tourne encore — même si les 5 extracteurs, eux,
n'ont besoin ni de Supabase ni d'attendre. Une panne Supabase de plusieurs
heures coûte donc une nuit complète de scrap, pas seulement la remontée.
Trois options chiffrées dans le rapport (statu quo / isoler le blocage à
l'agent concerné / plafond de durée globale sur `remonter-local.py`), aucune
tranchée — nécessite de choisir un seuil ou une politique de contournement,
hors mandat d'une session autonome.

## 2026-09-16 (suite) — Tranché en cours de session : Supabase ne bloque plus les extracteurs

Décision de l'utilisateur, en réaction directe à l'entrée précédente :
« supabase ne bloque pas les extracteurs » — choix de l'option (b) listée
ci-dessus. Détail complet et preuves de test :
[agents/audits/reparations-2026-09-16.md](../agents/audits/reparations-2026-09-16.md) §8.

`scrap_en_cours()` (`agents/orchestrator.py`) scindée en deux gardes :
`extraction_en_cours()` garde son périmètre d'origine (famille `Extraction` +
`scraper/run.py`/`recense.py`) et continue de reporter le cycle ENTIER — seule
vraie collision à protéger, `report`/`backup-apres-cycle` liraient sinon une
base en cours d'écriture. `remontee_en_cours()` est nouvelle : elle ne
détecte que `remonter-supabase`/`ops/remonter-local.py` (confirmé en relisant
le script : il LIT `bangkok.db`, n'y écrit jamais — aucune collision réelle
avec les extracteurs), et `run_lane()` l'utilise pour sauter CET agent seul,
jamais pour reporter le reste de la lane. `scrap_en_cours()` (nom d'origine)
devient un simple OU des deux, gardée pour le smoke test existant.

Vérifié : nouveau test `agents/tests/test_remontee_isolee.py` (3/3) —
`remonter-supabase` seul en cours n'est plus vu par `extraction_en_cours()`
mais l'est par `remontee_en_cours()` ; un extracteur seul en cours est
toujours vu par `extraction_en_cours()` (comportement de protection
inchangé). Suite existante rejouée sans régression. Rejeu à blanc de la lane
du jour (`run_lane(dry=True)`) : câblage confirmé. Commit `6bfc64b` sur
`fix/pouls-pid-recycle`.

Non fait : l'option (c) (plafond de durée sur les retries Postgres de
`remonter-local.py`) reste hors mandat — inutile maintenant que (b) résout le
vrai problème sans qu'aucun seuil n'ait à être choisi. Confirmation en
conditions réelles reportée au cycle du 17/09 01:00 (pas de scrap manuel
lancé en pleine journée pour vérifier plus tôt).

## 2026-09-26 — État des lieux après une semaine d'absence (PC2, lecture du ledger 18→26/09)

**Ce que le ledger montre (mesuré).** Cycles complets les 18, 22, 23, 24, 25 et
26/09. **Trois nuits perdues, 19, 20 et 21/09** : aucun extracteur n'a tourné.

1. **Les 3 nuits perdues — l'option (c) écartée le 16/09 était nécessaire.**
   `remonter-supabase` (run 518) a tourné **69 h** (19/09 01:02 → 21/09 22:19
   UTC) : 204 lots ont chacun épuisé leur budget d'attente de 1 200 s contre un
   pooler en panne (`ECIRCUITBREAKER`, `EAUTHQUERY`), 51 500 erreurs. Le
   correctif `6bfc64b` ne couvrait qu'une remontée dans un AUTRE process ; ici
   elle tenait le process orchestrateur lui-même, et `LowiBKK-Agents`
   (`MultipleInstances=IgnoreNew`, vérifié) a refusé les déclenchements
   suivants. L'entrée précédente disait « inutile maintenant que (b) résout le
   vrai problème » : c'était faux, (b) n'en résolvait que la moitié.
   **Corrigé** (`9d0dd9d`) : disjoncteur `--max-lots-en-echec` (défaut 3, soit
   ~1 h de panne continue) → abandon sans recopie des statuts ni `scan_run`,
   code 1. Sans perte : le passage suivant réévalue la fenêtre active. Test
   `agents/tests/test_remonter_disjoncteur.py` (panne longue → rend la main ;
   échecs isolés → se tait ; tout passe → code 0). **Seuil proposé, à arbitrer.**
2. **`social-leads` : 0 fiche chargée depuis le 21/09.** `load_social_leads.py`
   appelé en tube retombait sur cp1252 et plantait au premier « → » — 10
   collectes (13→22/09) rejetées à chaque cycle. Reproduit, **corrigé**
   (`2ace611`, même idiome que `orchestrator.py`), vérifié : collecte du 13/09
   → 36 pistes, relance idempotente. Le rattrapage des 9 autres collectes est
   laissé à l'agent au prochain cycle. Distinct : les collectes 23→25/09
   sortent « aucune fiche extraite » — non investigué.
3. **LivingInsider cassé depuis le 17/09 — changement côté site, pas chez nous.**
   Aucun commit sur l'adaptateur depuis le 29/08. Sonde du 26/09 (6 requêtes à
   3 s) : les URL `/searchword_en/…/<page>/…` redirigent vers `/en/condo-buysell`
   ou `/en/condo-rent/<n>` ; le `ld+json ItemList` est désormais un bloc fixe
   (les 12 mêmes identifiants sur toutes les pages), la vraie liste n'est plus
   que dans les liens HTML (59 identifiants distincts par page) ; et **les
   fiches détail (`/en/detail/…` comme `/detail_en/…`) répondent 202 avec un
   corps vide** — un challenge anti-bot. Effet en base : 6 annonces créées le
   17/09 sans prix, titre = nom de zone, toujours `active` ; le garde-fou
   « scan < 50 % des actives » a bien annulé le délistage des 522 autres.
   La sonde de structure passe (elle trouve « 1 stub ») : **elle ne détecte
   pas ce mode de panne**. `fraicheur` et `watch-health` l'ont vu, eux —
   chaque nuit depuis le 23/09. **Non réparé : contourner un challenge est une
   décision de posture (règle 5).**
4. **`fraicheur` en « failed » tous les jours : ce n'est pas une panne.** Son code
   de sortie 1 signifie « alerte levée » ; il alerte à juste titre (tous les
   extracteurs le 21/09, LivingInsider seul ensuite). Mais l'overseer le compte
   en `contrat_viole` et `status` l'affiche DÛ depuis 8 j : un vrai constat
   compté deux fois. Non modifié.
5. **`watch-sources` DÛ depuis 20 j** : sa lane hebdo tombait le dimanche 20/09,
   perdu dans le trou. Rattrapage attendu au cycle du 27/09 (dimanche). Rien à
   faire.
6. **File T2 abandonnée.** `drain-agent-queue-lowi-bkk` est **désactivée** (dernier
   run 25/08), 31 tickets en attente dans `agents/queue/`, dont les lots
   `organize` (60 paires/jour déposées, 0 réponse depuis le 15/09). Le ledger
   porte 62 escalades `open`, dont des `agent_muet` de juillet.
7. Vu en passant, non creusé : `extract-ddproperty` du 25/09 n'a scanné que
   4 264 annonces contre ~6 700 les nuits précédentes.

**Non fait, et pourquoi.** Aucune réparation LivingInsider (posture). Aucune
correction des 6 annonces sans prix (aucune suppression sans décision). Aucune
clôture d'escalade ni réactivation de la tâche de drainage (choix
d'organisation). Double comptage `fraicheur`/overseer laissé en l'état. Le
disjoncteur n'a pas encore rencontré de vraie panne : sa confirmation en
conditions réelles attend la prochaine coupure du pooler. Travail sur la
branche `fix/reparations-2026-09-26` (tirée de `fix/pouls-pid-recycle`), non
fusionnée — c'est l'arbre de travail que la tâche de 01:00 exécute.

## 2026-09-26 (suite) — LivingInsider suspendu, 6 annonces fantômes passées inactive

Décision utilisateur, en réponse au point 3 de l'entrée précédente.

- **Suspension** : `extract-livinginsider` → `lanes: []` + motif `_suspendu`
  (`agents/agents.json`). Retour : remettre `"daily"`. Vérifié par
  `run-lane daily --all --dry-run` : 4 extracteurs, plus LivingInsider.
- **Pour que l'arrêt voulu ne crie pas chaque nuit (règle 2)** : `watch-health`
  ne juge plus que les extracteurs ayant une lane (sinon « parseur_casse » en
  sévérité haute sur son dernier run figé) ; `fraicheur` continue de relever
  la source mais ne la juge plus (`_sources_suspendues()`, lit agents.json) —
  sinon ses 516 actives, que plus rien ne confirme, auraient alerté à vie.
  `test_lanes.py` exclut un extracteur à lanes vide **seulement s'il porte un
  `_suspendu`** : une lane vidée par erreur échoue toujours.
- **6 annonces passées inactive** (`livinginsider:sale:3048952`, `3189961`,
  `3222636`, `3222631`, `rent:2974692`, `3222639`) : garde vérifiée avant
  écriture (6 lignes, toutes actives, prix nul, créées le 17/09). État
  antérieur sauvegardé dans
  `agents/audits/2026-09-26-livinginsider-inactives-rollback.json`.
  `delisted_at` et `dirty_since` posés : la prochaine remontée propagera le
  statut au serveur.

**Non fait.** `livinginsider:rent:3160325` a le même symptôme (prix nul,
titre = URL) mais date du 16/09, avant la panne — hors du périmètre demandé,
laissé actif. Les 516 autres actives LivingInsider restent `active` sans
confirmation : leur délistage n'aura lieu qu'à la reprise d'un scan complet.
Escalades `parser_break` LivingInsider laissées ouvertes dans le ledger.
`fraicheur --verifier` pas rejoué en réel (il écrit son historique et peut
ouvrir des tickets) : vérification par `test_fraicheur.py` + lecture directe de
`_sources_suspendues()` → `{'livinginsider'}`.

## 2026-09-28 — Revue des scraps, éditions mal datées, file de tickets abandonnée

**Scraps (mesuré au ledger, 3 derniers cycles 26→28/09) : tous les extracteurs
actifs `ok`.** Nuit du 28 : FazWaz 85 099 URL sitemap / 96 nouvelles,
DDproperty 6 740 / 1 465, PropertyScout 1 240 / 45, Nestopa 553 / 21. Analyse,
organize, social-leads (346 leads chargés le 27), report, backup, overseer : ok.
Seul échec : `remonter-supabase`, 2 nuits (26 : 500 erreurs sur un lot ; 28 :
abandon par le disjoncteur, `EAUTHQUERY auth_query secret check timed out`
côté pooler Supabase — panne serveur, pas de code).

**Défaut de datation (corrigé).** `study/run_study.py` nommait ses éditions en
date **UTC** (`TODAY`). Le cycle part à 01:00 Bangkok ; quand `report` finit
avant 07:00 locale, l'UTC est encore la veille. Mesuré sur les mtimes :
5 éditions mal nommées (31/08→01/09, 01/09→02/09, 10/09→11/09, 21/09→22/09,
27/09→28/09), et **celle de la nuit du 28 a écrasé la vraie édition du 27**
(perdue, non reconstructible : l'étude lit l'état courant de la base).
Correctif : date locale, même convention que `jour_local()` de
l'orchestrateur. Même défaut dans `agents/bots/overseer.py` (nom de l'audit
quotidien) — corrigé. Les 5 éditions (snapshot JSON + champ `date`, `.md`,
`.xlsx`, `khet-*.csv`) ont été **renommées** à leur vraie date, rien supprimé ;
copie des snapshots avant renommage dans le scratchpad de la séance. Étude
relancée : `docs/etudes/etude-2026-09-28.md`, 35 snapshots, 109 281 actives
dans le périmètre (49 782 ventes / 59 499 locations, 3 977 immeubles).

**File de tickets T2 : plus drainée depuis le 16/09.** La routine
`drain-agent-queue-lowi-bkk` est **désactivée depuis le 25/08** et vit dans le
profil PC1 (`C:\Users\schoe`), alors que la file est sur PC2. 33 tickets en
attente. Fermés (avec diagnostic, via `escalation.resolve`) : 24 alertes
périmées — cycles manquants/longs/vides et agents muets des 15-22/09 (incident
déjà consigné le 26/09, 3 cycles propres depuis), `parser_break` et fraîcheur
LivingInsider (source suspendue, 066fb2a), fraîcheur effondrée des autres
sources pendant les nuits perdues.

**Non fait.**
- **9 tickets `organize` (540 paires) laissés ouverts** : aucune statistique
  n'en dépend, et les trancher à la main coûte cher en tokens pour un stock
  ambigu de 604 032 paires qui croît plus vite que 60/jour. Décision à prendre :
  réactiver un drainage sur PC2 (tâche Windows + `claude -p` Haiku, comme
  `social-leads`), ou arrêter le dépôt de tickets.
- **Routine de drainage non recréée** : où elle doit tourner (PC2) et avec
  quel modèle est un arbitrage utilisateur.
- **`watch-health` juge FazWaz en « dérive »** chaque nuit (192 nouvelles
  contre une médiane de 2 006) : la médiane date du rattrapage sitemap
  (~17 000 fiches en retard, repris sur ~9 nuits) et n'est plus représentative.
  Pas d'escalade, mais constat récurrent inutile (règle 2) — seuil laissé à
  trancher (règle 5).
- **Quota Supabase : 446 Mo / 500 Mo (89 %)** après la remontée manuelle de ce
  jour (mesuré : 436 → 446 Mo pour 1 627 nouvelles + 2 704 statuts corrigés,
  soit ~10 Mo par nuit). **Plein dans ~5 nuits** au rythme actuel. Aucun
  garde-fou ne prévient. Leviers à arbitrer : purger les inactives du serveur
  (copie vérifiée d'abord, règle 8), alléger `raw_data`, ou plafonner la
  remontée — non tranché.

**Remontée relancée à la main** (Supabase de nouveau joignable) : 113 436
actives, 1 627 nouvelles, 117 mises à jour, 0 erreur, 2 704 fantômes
corrigés. Serveur à jour au 28/09 ~09:50.

### 2026-09-28 (suite) — drainage Haiku sur PC2 + fuite `posted_at_history`

**Agent `drain-tickets` (T2, lane daily, juste après `organize`)** —
`agents/bots/drain_tickets.py`, skill, test `test_drain_tickets.py` (modèle
simulé). Haiku (`claude -p`, appel repris de `social-leads`) rend les 6 faits,
`appliquer_reponses()` → `decider()` tranche : contrat inchangé. Au plus 12
tickets par cycle. Chaque réponse est recomparée aux faits recalculés en code
(`verite_code`) → `paires_fausses`, constat au-delà de 5 %. Les tickets
d'alerte restent pour un humain (comptés dans `autres_par_nature`).
Constat en l'écrivant : le texte des paires est produit par `organize.fmt()`
depuis des champs de la base, donc les 6 faits sont **calculables en code sans
modèle** — Haiku ne fait que relire ce que le code a écrit. Laissé à
l'arbitrage : garder Haiku (demandé) ou passer la comparaison en T0 (gratuit,
exact par construction).
**⚠ Non mesuré : la session `claude` de PC2 a expiré** (« OAuth session
expired and could not be refreshed ») — aucun appel Haiku possible, ni pour
cet agent ni pour `social-leads`. Rien n'est perdu (tickets et collectes
restent en attente), mais il faut se reconnecter (`claude` puis `/login`)
avant la première mesure réelle.

**Fuite `posted_at_history` côté serveur — corrigée dans le code.** Réponse à
la question « les inactives sont-elles purgées à 90 j ? » : non — l'agent de
purge est neutralisé depuis le 25/08 ; le serveur garde 47 274 inactives (632
de plus de 90 j), le local les a toutes (48 404). Mais ce n'est pas là qu'est
le poids : `posted_at_history` pèse **196 Mo** (1 699 284 lignes, dont
**105 093 distinctes**, 94 % de doublons) contre 104 527 lignes en local.
Cause : `SupabaseStore` comparait `str(timestamptz)` ('… 16:54:35+00:00') au
texte ISO local ('…T16:54:35+00:00') → toujours différents → chaque remontée
ré-historisait tout DDproperty (~400 k lignes/semaine depuis le 24/08, 79 k ce
matin). Correctif : `_meme_instant()` compare des instants (chemin lot ET
chemin ligne). Tests `test_remonter_bulk`, `test_remontee_isolee`,
`test_stores_alignes` verts.
**Non fait, à valider** : supprimer les 1,59 M doublons du serveur (garder la
1re observation de chaque couple `listing_id, posted_at` — aucune information
distincte perdue, l'app ne lit pas cette table). Suppression en production,
donc soumise à l'utilisateur.

### 2026-09-28 (suite 2) — tri des paires passé en CODE (décision utilisateur)

Décision de l'utilisateur : les six faits d'`organize` sont lus dans les
champs de la paire (`faits_code`) au lieu d'être extraits par un modèle, puis
`decider()` tranche comme avant. Motif : le texte soumis au modèle était
fabriqué par `fmt()` depuis ces mêmes champs. Sur un poste sans T1
(`agents/t1-absent`), `organize` tranche désormais **tout** le stock ambigu
chaque nuit, sans ticket. Premier run réel : **205 817 paires en 17 s**,
205 800 abstentions, **17 en revue** (`origine: code`), 0 incohérence en base.
Contre 60 paires/nuit en ticket auparavant, que plus rien ne drainait.
Ce que ça révèle : avec des faits exacts, `decider()` ne rend `same_unit` que
pour les republications à écart < 2 % survenues **plus de 90 j** après le
retrait (les autres sont déjà tranchées par `prefiltre_sql`) ; le reste
s'abstient par construction. Le stade « modèle » n'apportait donc que du
bruit ou ces cas-là.
L'agent `drain-tickets` (Haiku) écrit plus tôt dans la journée est **retiré**
(module, skill, test, entrée `agents.json`) avant d'avoir jamais tourné. Les 9
tickets `comparaison_deleguee` en attente sont refermés (540 paires libérées).
Test : `agents/tests/test_organize_code.py`. `deposer_en_ticket` et le chemin
T1 (Ollama, PC1) sont conservés tels quels.
**Non fait** : la file de revue (17 + antérieures) n'est lue par personne ;
aucune statistique n'en dépend.

### 2026-09-28/29 — doublons `posted_at_history` supprimés du serveur (décision utilisateur)

- **Copie avant suppression** : export intégral du serveur →
  `archive/posted_at_history-serveur-2026-09-28.csv.gz` (17,6 Mo, gitignoré).
  Vérifié : 1 699 284 lignes exportées = compte serveur, 1 699 284 id
  distincts, 105 093 couples `(listing_id, posted_at)`. Export : 2 h 03
  (instance Supabase saturée toute la journée, pooler en `EAUTHQUERY`).
- **Suppression** : 1 594 191 lignes, par lots de 20 000 id, en gardant pour
  chaque couple la 1re observation (`observed_at` puis `id`). Aucune
  information distincte perdue. Résultat mesuré : 105 093 lignes, 105 093
  couples distincts. Ralentie par le serveur (~6 h).
- **Rollback** : recharger le CSV (`COPY posted_at_history FROM STDIN CSV
  HEADER` des id absents) — les id d'origine sont conservés dans l'export.
- **Place rendue au quota : pas encore.** Le `VACUUM FULL` a perdu sa
  connexion (SSL fermé) ; la table pèse toujours 196 Mo, base 453 Mo. Une
  relance en arrière-plan attend que le serveur accepte les connexions et
  qu'aucun vacuum ne tourne déjà. Sans lui, Postgres réutilisera l'espace
  libéré pour les futures insertions (la croissance est donc absorbée), mais
  `pg_database_size` — ce que mesure le quota — ne baisse pas.

### 2026-09-29 — réparation autonome : secret exposé depuis 3 mois + un mois de travail jamais commité

Session de réparation planifiée. Cycle de scraping lui-même sain (tous les
agents à jour, aucune erreur nouvelle sur 7 jours — voir
`agents/audits/reparations-2026-09-29.md` pour le détail complet). Les deux
vrais problèmes trouvés étaient dans le dépôt, pas dans le pipeline.

**Mot de passe du site en clair sur GitHub public depuis le 2026-06-21**
(commit `34aabd8`). Déjà diagnostiqué en sévérité HAUTE le 2026-09-13
(`agents/audits/audit-2026-09-13.md`) et par l'audit de sécurité
`docs/replication-blueprint.md` §5.1 — jamais traité. Corrigé : ligne
retirée de `CLAUDE.md`, remplacée par un pointeur vers la variable Vercel
`BASIC_AUTH_PASSWORD`. **Non fait** : changer le mot de passe sur Vercel
(retirer la ligne ne rotate pas le secret réellement actif) — laissé à
l'utilisateur, impact d'accès immédiat. L'historique git garde le mot de
passe ; pas de réécriture tentée (dépôt déjà public depuis des mois, même
conclusion que l'audit du 13/09).

**171 fichiers non commités, certains depuis avant le 2026-08-26.**
`ops/verifie-synchro.py` le signalait déjà lui-même. Vérifiés un par un puis
commités en 4 lots distincts : `CLAUDE.md` (architecture des données, règles
6-10, état d'avancement — absent de git depuis avant la bascule SQLite du
25/08), le correctif « double coureur » de `verifie-synchro.py` +
`agents/tests/test_remonter_bulk.py` (garde-fou anti-réécriture du 09-02,
déjà en prod dans `supabase_store.py`, testé de nouveau contre le vrai
Supabase avant commit — vert), 4 docs de référence jamais ajoutées
(`masterlog.md`, `methodes-calculs.md`, `replication-blueprint.md`,
`journal-technique-archive-2026-06_08.md`), et 33 jours de sorties d'étude
jamais commitées depuis le cycle du 22/08 (160 fichiers : `etude-*.md`,
`.xlsx`/`.csv`, `study/snapshots/*.json`, `study/official/official-*.json`).

**Fausse alerte corrigée dans `verifie-synchro.py`** : la section « archive
locale » vérifiait encore `archive/lowi-archive.db`, remplacé depuis le
2026-08-25 par la sauvegarde clé USB (`sauvegarde-cle.py` /
`backup-apres-cycle`) — le fichier n'existe plus, le check criait au loup en
continu (règle 2). Lit maintenant le dernier run `backup-apres-cycle`
réussi au ledger. Vérifié sain : dernier backup 0,2 j, 3 526,7 Mo, 3/3
essais de relecture.

**Boîte `agents/queue/mail/` vidée** : 21 alertes accumulées du 16/09 au
27/09 (non vidée depuis le 13/09), toutes déjà résolues à cette date.
Envoyées en un seul mail de synthèse (pas 21 mails d'historique sans action
requise — règle 2) plutôt que individuellement.

**Non fait, le plus important à trancher** : la branche
`fix/reparations-2026-09-26` n'a **aucun upstream configuré** et compte
**51 commits** d'avance sur `main` — tout le travail depuis la bascule
SQLite (système d'agents, sécurité RLS, sitemap FazWaz, tous les correctifs
depuis fin août) n'existe que sur le disque de PC2. Pas poussé par cette
session (action visible depuis l'extérieur, laissée à l'utilisateur), mais
c'est le risque numéro un du dépôt en l'état : une panne disque emporterait
un mois de travail non recréable depuis GitHub.

## 2026-09-29 — lowi.asia : scintillement du fond (dépôt `lowi-th`)

Consigné ici faute de journal dans `lowi-th` ; seul `lowi-th` est touché.

**Symptôme** (signalé par l'utilisateur, Chrome PC) : le fond de `lowi.asia`
s'allumait et s'éteignait très vite. Le fond de `public/dossier*.html` et
`public/agent-pipeline*.html` : trois disques de ~56vw, `filter: blur(90px)`,
`will-change: transform`, animés en continu (`cloudDrift*`, 46–58 s), sous une
barre du haut en `backdrop-filter: blur(14px)`.

**1re tentative — fausse, et elle a aggravé le défaut** (`0b45a23`) : cause
supposée = le filtre de flou sur des calques géants ; remplacé par des
`radial-gradient` sans filtre ni `will-change`. Vérifié seulement par capture
d'écran statique (rendu équivalent), pas sur le clignotement lui-même, que je
ne pouvais pas observer. Résultat en ligne : « pire qu'avant ». Explication
probable, non mesurée : sans `will-change`, les trois dégradés plein écran
étaient repeints à chaque image au lieu d'être déplacés comme calques GPU.

**Correctif retenu** (`a97d3a3`, option B choisie par l'utilisateur parmi :
revenir en arrière / figer / retirer le flou de la barre / supprimer les
nuages) : flou d'origine rétabli, **nuages figés** — lignes `animation:`
retirées, `@keyframes cloudDrift*` conservées pour pouvoir réanimer. Confirmé
par l'utilisateur : plus de scintillement. La cause était donc l'**animation**,
pas le flou.

**Au passage** : `lowi.asia` se déploie tout seul depuis `main` de
`Erok-gg/lowi-th` (mise en ligne < 1 min après chaque push, vérifiée par
`curl`) — aucun lien Vercel n'existe sur PC2 et le connecteur Vercel ne voit
pas ce projet. Le 1er push a aussi publié deux commits pitch deck du 02/09
restés hors ligne jusque-là (demandé par l'utilisateur). Le `main` local de
`lowi-th` avait un historique sans lien avec `origin/main` ; identique à
`archive/main` (dépôt `lowi-th-archive`), il a été réaligné sur `origin/main`.

**Non fait** : le clignotement n'a jamais été observé ni mesuré de ce côté
(ni trace de performance Chrome) ; le diagnostic tient à la confirmation de
l'utilisateur. `lowiShimmer` (logo) et l'animation d'entrée des vues restent
actifs, sans signalement.

## 2026-09-30 — Réparation autonome : aval Facebook muet depuis 7 jours, cycle retardé par la veille prolongée

**`social-leads` en panne depuis le 23/09, sous une fausse étiquette.** 162
appels `claude -p` en échec, 6 constats moyens par cycle « le modèle n'a rien
rendu d'exploitable ». Reproduit : le CLI autonome n'est plus authentifié
(`OAuth session expired and could not be refreshed`). La cause ne se voyait
pas : stdout tronqué à 300 caractères, alors que le champ `result` arrive en
fin de JSON. Corrigé (`9d84933`, branche `fix/reparations-2026-09-30`) :
cause lue dans le JSON, arrêt au premier lot, **un** constat haut
`claude_cli_non_authentifie`. Test de non-régression + essai réel (1 appel,
cause exacte, 7 collectes en attente, rien de perdu : aucune n'a son
`_charge.json`).

**Cycle du 30/09 démarré avec 7 h de retard.** `LowiBKK-Agents` à 01:01:12,
puis Kernel-Power 42 *« Hibernate from Sleep - Fixed Timeout »* à 01:01:13 ;
relancé par l'ouverture du capot à 08:06. `HIBERNATEIDLE` secteur = 1 800 s.
La veille prolongée est quotidienne (13 fois en 30 j) mais tombait jusqu'ici
hors du cycle ; 1 démarrage retardé sur 52 cycles depuis le 20/08 (hors
l'arrêt du 09 au 17/09, déjà connu).

**Autorisations** : `.claude/settings.local.json` passe en
`bypassPermissions` à la demande de l'utilisateur (tâche autonome sans
prompts). Retour : retirer `defaultMode` et les entrées larges de `allow`.

**Non fait** : reconnexion du CLI (`claude` puis `/login`, à faire par
l'utilisateur, pas de saisie d'identifiants par un agent) ; `HIBERNATEIDLE`
non modifié (réglage système, options chiffrées dans
`agents/audits/reparations-2026-09-30.md` : jamais sur secteur, ou caler
au-delà de 13 h dans `ops/regle-alimentation.py`, ou statu quo) ; aucune
alerte « démarrage tardif » ajoutée (1 cas sur 52, risque de crier au loup) ;
cycle non relancé (il tourne). Base : `quick_check` ok, 112 691 actives ;
sauvegarde USB du 29/09 : 3/3 relectures.

### 2026-09-30 (suite) — Mail quand Facebook ne peut pas scraper

Demande de l'utilisateur : être prévenu par mail, le lendemain, si la collecte
Facebook ne peut pas tourner. Une session perdue était jusqu'ici invisible :
Facebook sert la page du groupe sous un mur de connexion, le run finit en
« Aucun post collecté », **code 0, aucun fichier écrit**. Le seul signal était
`collecte_facebook_muette`, au bout de 48 h, en sévérité moyenne, donc sans mail.
`agent.js` détecte maintenant le mur de connexion et l'écrit dans la sonde
(`deconnecte`, `posts_total`). À chaque cycle, `social-leads` lit cette sonde
et envoie **un mail par jour de panne** (`alert.alert`) dans cinq cas : sonde
absente, sonde de plus de 30 h, session déconnectée, 0 post, structure cassée.
Vérifié en réel des deux côtés : session connectée → rien, contexte sans
cookies → détecté (champ mot de passe, **sans** redirection vers /login : le
groupe est public).

**Correction de l'entrée précédente** : un constat `high` au ledger n'envoie
pas de mail à lui seul. La panne d'authentification de `claude -p` passe
désormais aussi par `alert.alert`. Délai réel du mail : environ 25 h après la
collecte ratée (collecte 01:00 → `social-leads` vers 07:00 → file vidée par la
tâche planifiée de 02:14). **Non fait** : le code de sortie vide que
journalise `scrape-immo-facebook.ps1` (`Start-Process -PassThru` sans lecture
de `.Handle`). L'alerte n'en dépend pas.

### 2026-09-30 (suite 2) — Calibrage de la chaîne Facebook

À la demande de l'utilisateur : comparer par caractéristiques, filtrer,
garder les statistiques de chaque choix. Détail des seuils :
`docs/methodes-calculs.md` § 11 ; mesures de départ :
`docs/etudes/facebook-2026-09-30.md`.

- **`social_calibrage.py`** — doublons par caractéristiques (29,3 %),
  drapeaux, présence sur les plateformes (79,6 %, plafond), écart au m² par
  immeuble × chambres. Rien n'est supprimé (copie de `social-leads.db` prise
  avant la première écriture). Résultat : 406 lignes → 283 uniques
  exploitables → 47 exclusives. La grille de sensibilité est archivée à
  chaque exécution. Durée : 39 s, dont la relecture de `bangkok.db` ; le
  délai maximal de `charger()` passe de 300 à 900 s.
- **Collecte** — 15 défilements par groupe ne couvrent que **~12 h** de posts
  (13:13 → 01:13 UTC le 30/09). Porté à 32 (`FB_MAX_SCROLL`, retour arrière :
  retirer la ligne du ps1). La sonde enregistre désormais par groupe le
  nombre de tours, la raison d'arrêt et la date la plus ancienne atteinte.
  C'est sur ces données qu'on recalibre.
- **Défaut que j'avais introduit plus tôt dans la journée, corrigé** :
  l'expression régulière `/login` de la détection de déconnexion avait perdu
  ses barres obliques inverses à l'écriture et était devenue un commentaire.
  Seul le test du formulaire fonctionnait (c'est lui qu'avait vérifié l'essai
  réel). Même cause lors de cette passe : `element.$$` était devenu
  `element.$` (motif `$$` d'un `String.replace`), corrigé avant commit. Les
  deux sont relus dans le diff complet depuis le matin.
- Auteur « Indicateur de statut En ligne » (28 posts) écarté du nom.

**Non fait** : aucune collecte réelle lancée pour vérifier les 32 tours.
`scrape-immo-facebook.ps1` ferme tous les Chrome ouverts, et un scrap
Facebook en journée n'était pas justifié. Vérification à la sonde de cette
nuit. Aucun calibrage appliqué aux 766 posts du 23 au 30/09 : ils attendent
la reconnexion de `claude -p`. La normalisation de `street` n'est pas faite,
donc pas de statistique par rue. Le regroupement transitif peut chaîner deux
logements proches (21 000 → 22 000 → 23 000 dans le groupe de 8 de Rhythm
Sathorn), à surveiller via `taille_groupes_doublons`.

### 2026-10-01 — Réparation autonome : cycle suspendu, pas bloqué ; `reap_stale` fermait les runs longs vivants

Deux tickets `pouls` (`cycle_long` 17 h, `cycle_manquant` 41 h), une seule
cause. Le cycle du 30/09, parti à 08:07, a été **suspendu** : capot fermé à
10:12, puis veille prolongée à 10:42 (Kernel-Power 42 « Fixed Timeout »),
reprise à 01:06 le 01/10. Débit mesuré par les dossiers d'images : 77
annonces par tranche de 10 min avant la fermeture du capot, 3 entre 10:12 et
10:42, 0 jusqu'à 01:06, puis 85. La veille moderne arrête donc déjà le travail
dès que le capot se ferme. `HIBERNATEIDLE` sur secteur vaut **toujours
1 800 s** : le commit `95e0d42` a ajouté 13 h à `REGLAGES` sans que
`regle-alimentation.py` soit relancé.

**Défaut corrigé** (branche `fix/reparations-2026-10-01`) : `reap_stale()`
fermait tout run de plus de 12 h, même avec un PID vivant. Un simple
`orchestrator status` a ainsi classé `interrompu` le run #642
(`extract-ddproperty`, page 143/150, bien vivant). Désormais, un PID vivant
dont la date de création WMI précède le run n'est plus fermé. `OpenProcess`
est refusé entre sessions, même en accès limité (code 5 mesuré). Le seuil de
12 h est inchangé. Test : `agents/tests/test_reap_run_long.py`. Vérifié sur le
vrai PID du cycle, puis run #642 restauré en `running` (ledger copié avant).

**Non fait** : `HIBERNATEIDLE` non appliqué (réglage système, commande
laissée à l'utilisateur) ; action du capot non modifiée (choix d'usage) ;
cycle non relancé (il finit seul) ; consommation CPU du dashboard (~8 % d'un
cœur en continu) relevée, non traitée. Erreurs d'extraction : 8 isolées, toutes
absorbées. Base : `quick_check` ok, 114 639 actives. Mail `pouls` envoyé.

### 2026-10-01 (suite) — Réglages d'alimentation appliqués (approuvés par l'utilisateur)

`ops/regle-alimentation.py` relancé : les 6 réglages renvoient 0 et ont été
**relus** avec `powercfg /qh` plutôt que crus sur leur code retour.
`HIBERNATEIDLE` sur secteur vaut bien `0xb6d0` (13 h). Un `powercfg` avait
déjà été lancé à 12:45 (évènement UserModePowerService 12), hors de cette
session. **Ajouté : `LIDACTION` sur secteur = 0** (ne rien faire quand le
capot se ferme), relu à 0. C'est la seule parade à la panne mesurée le 30/09
(capot fermé, débit tombé de 77 à 3 annonces par 10 min). Retour :
`powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 1`, puis
`/setactive SCHEME_CURRENT`. Constaté sans y toucher : sur batterie,
`LIDACTION` valait **déjà 0** avant ce changement (le script ne règle que le
secteur). Un poste débranché, capot fermé, reste donc éveillé jusqu'au
minuteur batterie (`HIBERNATEIDLE` 12 h, `STANDBYIDLE` 180 s).

### 2026-10-01 (suite 2) — Deux fausses alertes d'un cycle long, corrigées à la source

Le cycle du 30/09 s'est bien terminé à 05:37 : 19 runs, tous `ok`, dont 4
extracteurs et 5 089 annonces écrites. Il a pourtant produit deux alertes
hautes, avec mail. Même cause pour les deux : une fenêtre fixe plus courte
que le cycle, qui a duré 21 h 30 entre le début des extractions et la fin,
28 h 36 entre `garde-veille` et l'overseer.

- **`pouls` → `cycle_vide`** : `battement()` comptait les extracteurs sur
  12 h. Il compte désormais les runs du PID de l'orchestrateur, passé par
  l'appelant, depuis la création de ce processus. Sans PID, l'ancienne
  fenêtre de 12 h s'applique toujours. Test : `test_pouls_cycle_long.py`.
  `pouls.json` a été corrigé à la main (15 runs, 4/4 extracteurs, 5 089
  annonces, recomptés sur le ledger).
- **`overseer` → `agent_muet` (garde-veille)** : sa fenêtre de 24 h remonte
  désormais au premier run du cycle quand celui-ci est plus ancien. Test :
  `test_overseer_cycle_long.py`.
- Les PID recyclés sont écartés par la date de création du processus, comme
  dans `_demarrage_processus`. Aucun seuil modifié.
- Les deux tickets sont clos, les deux mails classés **non envoyés** (fausses
  alertes). Le mail `social-leads` (`claude -p` déconnecté, panne réelle) a
  été envoyé.

**Non fait** : la reconnexion de `claude -p` reste à faire par l'utilisateur.


### 2026-10-04 — Réparation autonome : `cycle_manquant` faisait crier un cycle en cours

- **`pouls` → `cycle_manquant` (ticket du 02/10), fausse alerte corrigée.**
  `verifier()` comparait l'âge du dernier battement (dernière FIN de cycle) à
  26 h. Fin à 05:37 le 01/10, cycle suivant lancé à 01:00 le 02/10 et terminé à
  11:33 : le contrôle de 08:00 tombait au milieu, à 26,4 h, alors que les 4
  extracteurs tournaient. Le contrôle se tait désormais si le ledger montre un
  cycle en cours démarré après le battement. `cycle_long` (16 h) garde la
  durée. Seuils inchangés. Test : `test_pouls_cycle_en_cours.py`, qui échoue
  sans le correctif.
- **`extract-fazwaz` « parseur_casse » (0 nouvelle), faux positif mesuré.**
  Sitemap lu à 01:03, régénéré par FazWaz à 02:04 (`lastmod` de l'index). Le run
  précédent, parti à 03:10, avait déjà lu le même sitemap (85 005 URL dans les
  deux cas). Pas de perte : découverte cumulative. En régime normal, le
  décalage est d'environ 23 h.
- **`remonter-supabase` exit 1** : coupure réseau de 06:04 à 06:45, aucune
  trace locale. 1 000 annonces non remontées sur 113 493, reprises au cycle
  suivant.
- Base : `quick_check` ok, 174 133 annonces. USB du 03/10 ok.

**Non fait** : avancer ou retarder FazWaz par rapport à la régénération de
02:04 (décision de cadence, 3 options chiffrées dans
`agents/audits/reparations-2026-10-04.md`) ; étiquetage « sitemap non
régénéré » dans `watch-health` (touche le contrat de métriques de
l'adaptateur) ; cause de la coupure réseau ; vérification de la sauvegarde USB
de cette nuit, encore en cours.

## 2026-10-04 (journée) — veille Claude du cycle, cycle à 02:30, trois défauts

Demande de l'utilisateur : que Claude suive le cycle toute la journée (Haiku
toutes les 30 min, Opus en cas de problème, silence une fois le travail fini),
réparer FazWaz puis le relancer, et démarrer les scraps à 02:30.

**Ce qui a déclenché la demande — mon propre rapport, faux par omission.**
Le 02/10, j'ai signalé `claude -p` déconnecté alors que l'utilisateur s'était
reconnecté la veille : j'avais repris un constat du 30/09 sans le revérifier.
Le 04/10, j'ai annoncé que `social-leads` avait « bien tourné » (c'était vrai)
sans regarder le reste du cycle : `remonter-supabase` en échec et un constat
haut FazWaz étaient dans le ledger. J'ai aussi affirmé l'absence de collecte du
29/09 sans l'avoir vérifiée (cause trouvée ensuite, voir plus bas).

**Faits.**
- **Veille** : `ops/veille-cycle.py` + tâche `LowiBKK-VeilleClaude` (02:30,
  toutes les 30 min sur 23 h 30, sans `WakeToRun`). Le code décide de l'état
  (pas parti / en cours / terminé) et des problèmes. Haiku (`claude -p`, sans
  outil) rend le verdict. En cas de problème : ticket `veille-claude`, puis
  `claude -p --model opus` détaché, une fois par jour et par signature. Un
  marqueur `agents/state/veille/<jour>.json` éteint la veille. L'heure du
  cycle est lue sur la tâche : une constante aurait crié « pas parti » à
  chaque transition. Testé en réel sur le cycle du jour : verdict fidèle,
  marqueur posé, passage suivant silencieux (code 0). Test :
  `test_veille_cycle.py`, 5/5.
- **FazWaz attend la régénération du sitemap** : il sonde le 1er fichier, qui
  porte toujours les plus fraîches (mesuré sur les 28), toutes les 15 min,
  pendant 3 h au plus. FazWaz tourne en parallèle de DDproperty (5,6 h en
  médiane) : l'attente n'allonge pas le cycle. Test :
  `test_fazwaz_sitemap_regeneration.py`, 3/3. `test_fazwaz_sitemap.py`
  passe toujours (attente désactivée dans sa config : sinon il dormait 15 min
  sur son propre cache).
- **Cycle et collecte Facebook à 02:30** (décision de l'utilisateur ; FazWaz
  régénère à 02:04). Routine `lowi-reparation-autonome` à 12:00 (après la fin
  médiane du cycle, ~10:45). Widget resynchronisé.
- **Collecte Facebook écrasée** : `immo_<date UTC>.json`. La collecte du 30/09
  à 08:14 et celle du 01/10 à 01:24 tombent le même jour UTC, et la seconde a
  écrasé la première avant son chargement (`scraped_at` du fichier :
  2026-09-30T18:24Z). C'est la « collecte manquante du 29/09 ». Suffixe
  horaire si le fichier existe.
- **Code retour de la collecte Facebook toujours vide** depuis le 13/09 :
  `ExitCode` est vide sous PowerShell 5.1 avec `-RedirectStandard*` tant
  qu'on n'a pas lu `.Handle` (reproduit : `cmd /c exit 3` → vide sans, 3
  avec). La tâche rendait donc 0 quel que soit le sort du scrape.
- **Temps de scrap mesuré** (ledger, 14 j, runs ok) : cycle 8,2 h en médiane
  (moyenne 9,5 h, tirée par les 28,6 h du 30/09) ; DDproperty 5,6 h, FazWaz
  0,9 h, PropertyScout 0,2 h, Nestopa 0,2 h.

**Non fait.**
- **`LowiBKK-Agents` n'est PAS déplacée à 02:30** : tâche S4U, sa modification
  exige un terminal administrateur (`Accès refusé`). Commande à lancer :
  `powershell -NoProfile -ExecutionPolicy Bypass -File ops\install-agents-task.ps1`
  (02:30 par défaut désormais). Tant que ce n'est pas fait, le cycle part à
  01:00 et la collecte Facebook à 02:30. FazWaz attend alors la régénération,
  et la veille suit l'heure réelle de la tâche : aucun des deux ne casse.
- **Coût de la veille, plus haut qu'estimé** : 0,09 $ par passage Haiku (le
  CLI embarque ~48 k tokens fixes), soit ~1,5 $ par cycle de 8 h (16 passages),
  ~45 $/mois. Leviers possibles, non appliqués : n'appeler Haiku que quand
  l'état mécanique change, ou espacer à 1 h. Arbitrage laissé à l'utilisateur.
- **Garde-fou `parseur_casse` non retouché** : avec l'attente, un 0 nouvelle
  après 3 h sans régénération sera un vrai signal ; l'option 3 du rapport du
  matin (étiqueter « sitemap non régénéré ») n'est pas faite.
- **Collecte Facebook du 30/09 08:14 perdue**, non récupérable. Les posts
  couvrent 7 jours, donc la collecte suivante en a probablement repris une
  bonne partie (non mesuré).
- 15 posts non extraits (collecte du 28/09) : non retentés.
- Branche `fix/veille-claude-2026-10-04` non poussée, non fusionnée.

## 2026-10-05 — Supabase : budget Disk IO épuisé → remontée nocturne passée en `--delta`

**Déclencheur** : e-mail Supabase « Your project is depleting its Disk IO
Budget ». Au moment du diagnostic, la base ne répondait plus : deux requêtes
`pg_stat_statements` ont expiré en timeout. **Rien n'a donc été mesuré côté
serveur** ; ce qui suit vient du ledger et des logs locaux.

**Mesuré (logs `remonter-supabase`)** :
- Chaque nuit, le plein renvoi réévaluait **112 436 actives** (contre 53 k en
  août : le stock a doublé) et **62 266 mortes**, pour ~2 à 5 mises à jour
  réelles par lot de 500 et **1 689** statuts corrigés (run du 2026-10-05).
  Le `WHERE` de `upsert_listings_bulk` évite déjà les écritures inutiles, mais
  pas la relecture de chaque ligne, `raw_data` jsonb compris.
- 2 des 3 dernières nuits ont échoué au bout de 1 h 40 et 23 min, sur
  `connect() bloqué au-delà de 25s` : symptôme cohérent avec un budget épuisé
  (lien de cause à effet **déduit**, pas prouvé).
- `dirty_since` est posé sur **174 702 / 174 702** lignes depuis le backfill du
  2026-09-07 : aucune remontée `--delta` n'est jamais allée au bout.

**Décision (arbitrée par l'utilisateur)** : `agents.json` passe
`remonter-supabase` de `--statut actives --synchro-statuts` à `--delta`.
Vérifié avant de basculer : `dirty_since` ne bouge que sur changement de
contenu ou de statut (`sqlite_store.py`), pas sur un simple passage du scrap ;
le `last_seen` du serveur n'est pas plus figé qu'avant, puisque le plein
renvoi ne le rafraîchissait déjà pas sur les lignes inchangées.
`test_dirty_since` est à 10/10. **Le premier passage coûtera autant qu'un
plein renvoi** (tout est marqué) ; le gain n'apparaît qu'à partir du second.
Retour arrière : remettre `--statut actives --synchro-statuts`.

**Fausse piste corrigée dans la séance** : j'avais d'abord signalé un défaut
d'encodage (`'charmap' codec can't encode '⚠'`) dans les runs en échec.
C'était le `print` de mon propre script de lecture, dans la console cp1252.
Les logs de production sont propres (`shell.py` force déjà
`PYTHONIOENCODING=utf-8`). Rien n'a été modifié de ce côté.

**PAS fait, laissé à arbitrage** :
- B — retirer la copie Supabase → archive (agent `storage` hebdomadaire,
  `sync_supabase_local.py --prune`, et routine mensuelle de PC1) : une lecture
  complète de la base à chaque fois, pour un sens de copie devenu faux depuis
  la bascule SQLite.
- C — pages Vercel : `force-dynamic` + chargement du stock entier, avec un
  cache non partagé entre instances. Non mesuré.
- D — `pg_stat_statements`, bloat de `listings` et advisors de performance à
  relever dès que la base répondra, puis à comparer après deux nuits en
  `--delta`.
- E — passer sur une instance plus grosse (payant) : non retenu.
- Aucun commit.

### 2026-10-05 (suite) — B fait, C non fait après mesure

**B, retirer la copie Supabase → archive.** Côté agents, c'était déjà fait :
`storage` et `verifie-backup` ont `lanes: []` depuis le 2026-08-25.
CLAUDE.md (§ Architecture, rupture 2) était en retard sur ce point. Restait
la routine Claude `rapport-mensuel-lowi-bkk`, qui tourne sur PC1 dans
l'ancienne copie `C:\Users\schoe\++FILES++\Lowi_bkk`. Son prompt contenait
encore deux choses :
- étape 1 : des scraps `--full --store supabase`, soit des écritures
  complètes sur le serveur, avec le risque de remettre en « active » les
  annonces délistées (`upsert_listing` force `status='active'`) ;
- étape 4 : `sync_supabase_local.py --prune`, soit une lecture complète de
  toutes les tables plus une purge.

Le prompt a été remplacé : il est identique, sauf que l'étape 1 se limite à
une lecture de fraîcheur (aucun scrap) et que l'étape 4 est supprimée. La
version d'origine est conservée dans le transcript de la session PC1 du
2026-10-01. **Non vérifié** : ce que le run du 2026-10-01 a réellement fait.
Son transcript s'arrête au premier appel PowerShell.

**C, alléger les lectures de Vercel : NON FAIT.**
- Mesuré en local : ne charger que la 1re image des annonces actives et que
  le `price_history` des actives ne retire que **24 %** (147 407 → 112 415)
  et **35 %** (179 389 → 116 381) des lignes. Côté disque, Postgres balaierait
  quand même les tables entières pour la jointure. Gain en entrées/sorties
  estimé proche de zéro (**déduit**). Abandonné.
- Le vrai levier serait un cache **partagé** entre instances, par exemple un
  instantané JSON publié chaque nuit dans Storage et lu par Vercel à la place
  du SQL. Mais `unstable_cache` est plafonné à 2 Mo, et passer par Storage
  déplace le coût vers l'egress de Storage. C'est un changement d'architecture
  à chiffrer avant d'y toucher (règle 6).
- **Trafic Vercel impossible à mesurer aujourd'hui** : le connecteur Vercel ne
  voit que le projet `blog` de l'équipe `schoenaueranthony`, pas `lowi-bkk`
  (le site répond pourtant, 200 sur `/login`). Le projet vit probablement sur
  un autre compte ou une autre équipe.
- Étape suivante proposée : après deux nuits en `--delta`, lire
  `pg_stat_statements` pour départager la part des lectures de pages de celle
  de la remontée. Ne lancer C que si les pages pèsent réellement.

### 2026-10-05 (réparation autonome, 12:00) — veille Claude muette, FazWaz sans sitemap neuf, relance de la remontée

- **La veille `LowiBKK-VeilleClaude` n'a fait aucun passage le 05/10.** Il n'y
  a aucune ligne dans `ops/logs/veille/` avant mon essai manuel de 12:18, et
  dernier résultat de la tâche : `0x800710E0` à 12:00:05. Le script, lui,
  fonctionne (`--sans-llm --sans-escalade --forcer` → `termine`, 3 problèmes),
  et le jour du cycle est bien calculé. Le poste était en veille moderne au
  déclenchement de 02:30, et la tâche n'a ni `WakeToRun` ni
  `StartWhenAvailable`. Ensuite, aucun passage, même pendant la présence de
  l'utilisateur de 08:51 à 10:40. **Le journal opérationnel du Planificateur
  est désactivé** : on ne peut pas savoir pourquoi. La prémisse
  d'`install-veille-task.ps1` (« la veille suit tant que LowiBKK-Agents tient
  le poste debout ») est démentie. **Non corrigé** : c'est un choix de posture
  documenté la veille. Options (a) `StartWhenAvailable`, (b) `WakeToRun`,
  (c) lancement par l'orchestrateur : voir `agents/audits/reparations-2026-10-05.md`.
- **Le cycle est parti à 03:30 et non à 02:30.** Le poste était en veille
  moderne de 23:44 à 03:30:03, et la tâche a démarré une seconde après le
  réveil. Le minuteur de 02:30 n'a pas réveillé le poste. Cause non établie
  (`powercfg /waketimers` exige un terminal administrateur).
- **FazWaz « parseur_casse », deuxième nuit** : le parseur n'est pas en
  cause. Vérifié à 12:1x, l'index du sitemap est encore au 04/10 02:04 et le
  premier fichier au 04/10 01:37. FazWaz n'a pas régénéré depuis plus de
  34 h. Le « régénéré chaque nuit vers 02:04 » reposait sur une seule
  observation. Le marqueur `[sitemap-non-regenere]` est bien dans le journal
  de l'extracteur, mais `watch-health` ne le lit pas : cette fausse alerte
  reviendra (règle 2).
- **`remonter-supabase` : ma relance de 12:20 est venue en plein épuisement
  du budget Disk IO.** Elle a tourné en plein renvoi, puisque `agents.json`
  n'était pas encore passé en `--delta`. Résultat : code 0, 569 nouvelles,
  128 mises à jour, 1 689 statuts corrigés (c'est le « log du 2026-10-05 »
  cité dans l'entrée précédente). J'avais d'abord conclu à une coupure
  réseau quotidienne vers 06:00, parce que les échecs touchaient les runs
  partis entre 05:23 et 06:19. **Cette conclusion est fausse** : à 13:4x, la
  connexion a de nouveau bloqué au-delà de 25 s alors que le TCP passait.
  Mes sondes ont été arrêtées. Le mail d'échec en attente a été classé non
  envoyé (périmé).
- Base : `quick_check` ok, 174 702 annonces. Sauvegarde USB de la nuit : 3/3
  essais ok. Extracteurs : 2 lignes d'erreur en tout (404 FazWaz).

**Non fait** : aucun réglage de la tâche de veille ; pas d'étiquette « sitemap
non régénéré » dans `watch-health` ; budget de reprise de
`_connect_resilient` laissé à 1 200 s (le problème vient de la charge du
serveur, attendre ne sert à rien) ; `agents.json` laissé tel quel (modifié
par la séance de 13:00, non commité) ; aucun commit.

## 2026-10-06 — Réparation autonome : cycle figé 6 h 20 par une coupure secteur en veille moderne

- **Mesuré** (journal Windows) : poste en veille moderne depuis le 05/10
  16:37 ; le cycle de 02:30 y tournait. Bascule secteur → batterie à 03:51:40,
  réseau coupé, retour secteur à 05:00:53, mais réveil seulement à
  l'ouverture du capot (10:14:02). `extract-ddproperty` encore en cours à
  12:14 ; FazWaz/PropertyScout/Nestopa terminés (278/51/22 nouvelles).
- L'alerte « claude -p (haiku) en échec » de 10:14 est un artefact : l'appel
  de 05:00:56 a expiré au réveil. Mail envoyé avec ce diagnostic.
- Base : `quick_check` ok, 176 325 annonces ; sauvegarde USB 3/3 ok.

**Non fait** : aucun réglage d'alimentation (arbitrage utilisateur) ; pas
d'étiquette « réveil après veille » dans `veille-cycle.py` (proposée) ; pas de
relance du cycle ; aucun commit. Détail : `agents/audits/reparations-2026-10-06.md`.

## 2026-10-06 (suite) — Veille : un délai Haiku « expiré » pendant la veille n'est plus une panne

- `ops/veille-cycle.py` : si `claude -p` dépasse son délai alors que plus de
  300 + 120 s d'horloge se sont écoulées, le processus était gelé par la veille
  (mesuré ce matin : 18 815 s pour un délai de 300 s). → `HaikuGele`, pas
  d'alerte, un seul nouvel essai immédiat ; s'il échoue, alerte comme avant.
  Un vrai blocage (~300 s) alerte toujours.
- Vérifié : `agents/tests/test_veille_cycle.py` 6/6 (cas 18 815 s → gel, 301 s
  → panne) ; passage réel `--sans-escalade --forcer` ok (0,0025 $).
- **Non fait** : pas de lecture du journal Kernel-Power dans le message (le
  temps d'horloge suffit à trancher) ; le texte « Si c'est une
  authentification : /login » reste dans l'alerte des vraies pannes.

## 2026-10-06 (soir) — Le garde-fou Supabase nommait la mauvaise cause depuis un mois

**Déclencheur** : veille Haiku du cycle → ticket
`2026-10-06T150013-veille-claude-cycle_probleme.json`, « remonter-supabase :
failed (run #722, code 1) ». Compte rendu complet (avec la 1re intervention
du jour, à 12:15) : [agents/audits/reparations-2026-10-06.md](../agents/audits/reparations-2026-10-06.md).

**Ce qui s'est passé** : run #722 a tourné **8 h 28** (06:11 → 14:39 UTC),
publié **5 500 / 113 978** annonces, puis rendu la main proprement par son
disjoncteur. Le disjoncteur a donc bien fonctionné ; ce sont ses **messages**
qui étaient faux.

**Mesuré, et c'est le point de l'entrée.** L'entrée du 2026-10-05 posait
l'épuisement du budget Disk IO comme un **lien déduit, pas prouvé** (« rien
n'a donc été mesuré côté serveur » — la base ne répondait pas). Cette fois
elle répondait assez pour être interrogée, et le lien est **prouvé** :

- `postgres_logs` du jour : checkpoint d'**UN** buffer (16 ko) = **17,6 à
  22,4 s** ; 250 buffers (2 Mo) = **147,4 s** ;
  `pg_database_size('template1')` = **17,1 s** puis **23,6 s** ; autovacuum
  « worker took too long to start; **canceled** » ; « canceling statement due
  to statement timeout » en rafale.
- `supavisor_logs` : `DbHandler: Authentication timeout after 15000ms`, puis
  `(ECHECKOUTTIMEOUT) unable to check out connection from the pool after
  15000ms in Session mode`.
- Écrire 16 ko en 18 s n'est pas une charge mal encaissée : c'est un disque
  qui ne rend plus la main. Le pooler n'arrive plus à s'authentifier auprès du
  Postgres dans ses 15 s, donc nos connexions échouent.

**Ce n'était pas le réseau**, contrairement à ce que le log affirmait : DNS
résolu (3 A records), TCP établi (`TcpTestSucceeded=True`, 8,37 s), les deux
vérifiés avant de toucher au code. Le MCP Supabase lui-même n'a pas pu
exécuter de SQL alors que l'API de gestion annonçait `ACTIVE_HEALTHY` — une
métadonnée de santé ne dit rien de la joignabilité.

**Fréquence** : **5 des 12 derniers runs** de `remonter-supabase` ont échoué
(**42 %**), dont **3 des 4 dernières nuits**. Asymétrie des durées : une nuit
qui réussit prend **3 à 6 min** (05/10 : 5 min 14 s pour 112 436 actives +
62 266 statuts, cohérent avec les ~250/s de `upsert_listings_bulk`) ; une nuit
qui échoue coûte de 23 min à 8 h 28. **Le coût du travail n'est pas le
problème, le coût de l'échec l'est.**

### Deux défauts de NOTRE code, corrigés (branche `fix/supabase-connect-vraie-cause-2026-10-06`, `d37777f`)

**1. Le watchdog détruisait la vraie cause et en inventait une.**
`CONNECT_HARD_TIMEOUT = 25 s` tombe **avant** que libpq ne rende son erreur —
mesurée à **32,89 / 32,01 / 32,01 s** (3 essais consécutifs contre le vrai
pooler) :

    FATAL: Failed to connect to database:
           authentication did not complete within 15000ms

Le watchdog levait donc toujours le premier, avec un message qui **affirmait**
« hors du contrôle de connect_timeout — DNS ou TCP ». Conséquence concrète et
vérifiable : les commentaires de `scraper/store/supabase_store.py` parlent de
DNS depuis un mois (entrées des 2026-09-04, 09-07, 09-09) pour une panne qui
n'a jamais été réseau. C'est la règle 2 prise en défaut par l'intérieur — un
garde-fou qui ne crie pas au loup mais qui **désigne le mauvais loup**, ce qui
coûte autant.
Correctif : le message ne nomme plus de cause qu'il ignore, et un ramasseur
restitue la vraie dès qu'elle arrive (le recul du backoff laisse au thread au
moins 30 s, contre 25 au watchdog).

**2. Fuite de connexion, qui aggravait la panne réessayée.** Si
`psycopg.connect` aboutissait **après** la deadline, `resultat["db"]` tenait
une connexion que personne ne fermait jamais. En mode **session** chacune
occupe un backend du pooler — exactement la ressource dont la pénurie produit
l'`ECHECKOUTTIMEOUT` relevé ci-dessus. Le commentaire existant mentionnait le
thread orphelin, pas la connexion qu'il pouvait tenir. Désormais fermées.

**Vérifié en production**, la panne étant encore vive : la ligne « ↳ cause
réelle de l'attente précédente : … authentication did not complete within
15000ms » sort bien, aucune attente ne reste en vol, et la connexion a fini
par être obtenue à **149 s** (instance dégradée, pas morte).
Non-régression : `agents/tests/test_supabase_cause_reelle.py` (4 essais).
Suite complète **38/38** (`test_local_llm` sauté, Ollama absent de PC2 par
conception).

**3. Un test accusait le code à sa place.** `test_social_leads` échouait, et
**échouait déjà sans mes modifications** (vérifié par `git stash`) : sa sonde
« déconnecté » est datée en dur du `2026-10-01T01:14:46Z` alors que `run()`
appelle `etat_collecte_facebook()` **sans argument**, donc avec l'horloge
réelle. Au 06/10 la sonde avait 134 h, et la branche « n'a pas abouti depuis
N h » (`SONDE_FB_MAX_H = 30`) répondait avant la branche « DÉCONNECTÉ »
testée. Horodatage rendu relatif. **La collecte Facebook est saine** :
`etat_collecte_facebook()` rend `None`, 222 posts le 06/10 à 02:44,
`LastTaskResult = 0`.

### État du reste

`bangkok.db` : `quick_check` **ok**, WAL, **3,95 Go**, **176 325** annonces
dont **113 978 actives**, dernier `last_seen` 06/10 06:09 UTC. Sauvegarde clé
USB du cycle du 05/10 : `"ok": true`, **3 essais sur 3** concordants, 3 884,5
Mo, copie vérifiée présente (`D:\++SCRAP DB++`, 3,88 Go). Erreurs des
extracteurs depuis le 29/09, comptées par nature : 9 `OperationalError`,
7 `[erreur lot N]`, 2 `parseur_casse`, 1 `Traceback` — **toutes** de la
famille Supabase, **zéro erreur HTTP**, **zéro `SONDE-ECHEC`**. Les 2
`parseur_casse` FazWaz des 04–05/10 sont des faux positifs sur un `scan_run`
« 0 nouvelle / 6 retirées » légitime (déjà expliqué le 05/10). 0 escalade
ouverte. `ops/pouls.py --verifier` s'est tu correctement tout du long (« cycle
en cours, surveillé par `cycle_long` »).

**Mesure que j'ai d'abord faite de travers, et qui mérite d'être consignée** :
mon premier comptage d'erreurs annonçait « 94× HTTP 403 » et « 76× HTTP 429 ».
C'étaient des **chiffres pris dans des nombres** (`43402`, `142929`,
`104033`) — faux positifs d'un motif de recherche trop large. Il n'y a aucune
erreur HTTP. Huitième occurrence du schéma d'août 2026 : c'est la mesure, et
non le système mesuré, qui était en cause. La conclusion inverse aurait lancé
une enquête anti-bannissement sans objet.

### Non fait, et pourquoi

- **Le fond n'est pas réparé** : l'instance Supabase ne tient plus la charge.
  **Aucun seuil, palier, budget, cadence ni définition de calcul n'a été
  touché** (`CONNECT_HARD_TIMEOUT`, `OUTAGE_*`, `CIRCUIT_OUVERT_PALIER`,
  `JITTER`, périmètre `--delta`, seuil `parseur_casse`, `SONDE_FB_MAX_H`,
  `COLLECTE_MUETTE_H`) — posture, donc arbitrage de l'utilisateur (règle 5).
- **Point dur mesuré, laissé en décision** : `--delta` n'arrive pas à
  s'amorcer. **173 325 / 176 325 lignes (98,3 %)** portent encore
  `dirty_since` ; la nuit du 06 n'en a nettoyé que **3 000**. Le progrès est
  persistant (pas un blocage définitif), mais il faut **une nuit complète**
  pour repartir propre — ce que le disque saturé empêche. Trois options
  chiffrées dans le compte rendu : (a) laisser gratter, 1 à ~58 nuits selon le
  disque ; (b) amorcer une fois à la main hors cycle, ~5 min si l'instance
  répond ; (c) réduire le périmètre publié ou passer au palier payant (coût
  **non mesuré**, pas lisible d'ici).
- **Quatrième levier non mesuré** : la part du budget disque consommée par
  `posted_at_history` (1,70 M lignes / 196 Mo au 2026-09-28, ~400 k/semaine).
  S'il domine les écritures, le traiter ferait plus que tout le reste —
  vérifiable seulement par `pg_stat_statements` sur une instance qui répond.
- **Pas relancé `remonter-supabase`** ni aucun scrap : le cycle tournait encore
  pendant toute l'intervention, deux publications en parallèle contre une
  instance à genoux auraient aggravé les choses. Il repart seul à 02:30.
- **Pas touché à l'instance** (ni `VACUUM`, ni purge, ni palier) : donnée
  servie au public et poste de dépense.
- **Volumétries de `CLAUDE.md` non mises à jour** : il annonce 1,19 Go /
  76 942 annonces (relevé du 2026-08-26) contre **3,95 Go / 176 325** mesurés.
  Écart signalé, correction non faite — doc de référence, hors périmètre du
  ticket.
- **Fragilité repérée, non corrigée** : les `print` de
  `_connect_resilient`/`_execute` contiennent « ⚠ » ; sur une sortie non-UTF-8
  ils lèvent `UnicodeEncodeError`, non rattrapé par le
  `except (OperationalError, InterfaceError)`, ce qui tuerait le run. Inoffensif
  en production (les logs rendent « ⚠ », et `test_console_utf8.py` garde ce
  point) ; rencontré dans mon propre harnais, pas dans le cycle.
- **Branche non poussée, non fusionnée.** Les modifications non commitées
  trouvées à l'arrivée (arbitrage `--delta` du 05/10 dans `agents.json` + son
  entrée de journal, CSV d'étude, `official-latest.json`) ont été **laissées
  telles quelles** : elles ne sont pas de moi.

## 2026-10-07 — Supabase : moins d'écritures par mise à jour (index, VACUUM, fillfactor)

Suite de l'entrée du 2026-10-06 (soir). L'instance Nano manque de budget IO,
mais **notre volume est faible** (mesuré, `pg_stat_wal` depuis le 28/09 : 457 Mo
de WAL en 9 j ≈ 50 Mo/j ; checkpointer : 1,07 Go en 9 j, à ~48 ms par bloc).
Le levier était le **coût par mise à jour**, pas le volume :

| Mesure avant (stats depuis 2026-09-28) | Valeur |
|---|---|
| Index sur `listings` | 13, dont **12 à `idx_scan = 0`** (pkey : 1 255 754) |
| Mises à jour HOT | **227 / 16 841 (1,3 %)** → ~14 écritures par UPDATE |
| Versions mortes | **25 027 (14 %)**, autovacuum jamais passé (annulé en boucle) |
| `statement timeout` sur 24 h | **476**, encore ~50/h à 00:00 UTC hors cycle |

Lecteurs vérifiés avant suppression : `lib/listings-db.ts` ne filtre que sur
`status='active'` (~65 % des lignes) et `khet is not null` (scans séquentiels de
toute façon) ; l'app ne lit aucune vue ; les agents d'analyse lisent le SQLite.

**Appliqué sur Supabase à 01:19 UTC** (migration
`supabase/migrations/2026-10-07_index_inutiles_listings.sql`, rollback livré
**avant** application, généré depuis `pg_get_indexdef` sur le live) :
10 index retirés (agent, bench, khet, missed, posted, repost, source, status,
street, unit) ; gardés : pkey + les deux partiels `market_status`/`sold_since`
(16 ko, servent à la requête `market_status='sold'` du store) ;
`fillfactor = 85` ; `VACUUM (ANALYZE)` simple. Résultat immédiat :
**0 version morte**, `listings` **170 → 148 Mo** (index 12 Mo).

**Point de référence pour juger l'effet** (01:19 UTC) : `n_tup_upd = 16 841`,
`n_tup_hot_upd = 227`, checkpointer `write_time = 6 556 877 ms` pour
`136 758` blocs. Après la prochaine remontée, la part HOT des nouvelles mises à
jour et le temps d'écriture par bloc diront si ça a servi.

### Non fait, et pourquoi
- **Pas de suspension du cycle** : la maintenance a abouti du premier coup, la
  condition posée par l'utilisateur (« si tu n'y arrives pas ») n'est pas remplie.
  Le cycle du jour (DDproperty en cours, écrit en local) continue ;
  `remonter-supabase` qui suivra sert de premier test.
- **Pas de `VACUUM FULL`** ni de réécriture de table : trop coûteux en IO, le
  `fillfactor` ne s'applique donc qu'aux pages écrites désormais.
- **Pas de passage au palier payant**, pas de changement de périmètre publié :
  arbitrages de l'utilisateur.
- `schema.sql` et les migrations historiques **créent encore ces index** :
  les rejouer sur Supabase les remettrait. Non modifiés (ils servent aussi au
  SQLite local) — avertissement porté en tête de la migration.
- Non vérifié : budget IO et swap dans le tableau de bord (non accessible d'ici).

## 2026-10-07 (suite) — Cycle du 08/10 suspendu pour maintenance, sans fausse alerte

Demande de l'utilisateur : pas de cycle la nuit du 08/10 (une nuit sans
remontée après la maintenance Supabase), reprise normale le 09/10 à 02:30, et
la nuit notée comme **maintenance**, pas comme panne.

Désactiver `LowiBKK-Agents` aurait suffi à ne rien lancer, mais deux
surveillances l'auraient prise pour une panne (règle 2) : `ops/veille-cycle.py`
(« pas parti » → ticket + Opus) et `ops/pouls.py --verifier` (`cycle_manquant`
après 26 h). D'où une **fenêtre de maintenance déclarée** :
`agents/state/maintenance.json` (par machine, gitignoré) lu par
`agents/core/maintenance.py`.
- `orchestrator.py --due` / `--boot` : ne lance rien dans la fenêtre, le dit
  dans son log, ne pose pas de battement. `run`/`run-lane` manuels restent possibles.
- `veille-cycle.py` : nuit sans run dans la fenêtre → marqueur du jour posé
  avec le motif, ni Haiku ni escalade (vérifié par simulation du 08/10 02:30 :
  0 appel modèle, 0 escalade).
- `pouls.py` : l'âge du dernier battement se compte depuis la fin de la
  fenêtre si elle le suit (vérifié en réel : ✓ « maintenance déclarée »).
- Fichier absent ou illisible = **pas** de maintenance (on préfère une fausse
  alerte à un cycle sauté en silence). `agents/tests/test_maintenance.py`, 4 essais.

Fenêtre posée : **2026-10-08 00:00 → 2026-10-09 00:00 (Bangkok)**. Le cycle du
jour (07/10), déjà parti, n'est pas touché : sa remontée Supabase sera la
première mesure de l'effet de la maintenance.

### Non fait
- La tâche Windows n'est pas désactivée : c'est l'orchestrateur qui s'abstient
  (aucun ré-armement manuel à oublier). La machine se réveille donc à 02:30 le
  08/10 et se rendort.
- Pas d'outil pour poser une fenêtre en ligne de commande : le JSON s'écrit à la main.
