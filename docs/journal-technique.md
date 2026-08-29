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
