# CLAUDE.md — Bangkok Real Estate Map

> Doc de référence du projet. À lire avant toute modif. Tient l'état d'avancement à jour.
>
> **Flow complet du système (scrap → parsing → stockage → heuristiques → calculs) : [docs/pipeline.md](docs/pipeline.md)**
>
> **Système d'agents (12 bots orchestrés, étages T0/T1/T2) : [agents/README.md](agents/README.md)**
>
> **Présentation non technique — flux, méthode, valeur, limites : [docs/dossier-investisseur/](docs/dossier-investisseur/README.md)**
>
> **Décisions, méthodes et défauts corrigés : voir [docs/journal-technique.md](docs/journal-technique.md)**
> (registre append-only — le *pourquoi* des choix, ce qui a été mesuré, ce qui
> restait faux au moment de la décision, et la traçabilité de provenance).
> Toute décision structurante ou tout défaut découvert s'y consigne, daté.

## Règles de travail sur ce dépôt — à appliquer sans qu'on le redemande

**1. Mesurer avant d'affirmer, et distinguer les deux dans ce qu'on écrit.**
Ce qui est mesuré se marque comme tel ; ce qui est déduit ou supposé aussi. La
distinction a coûté cher : sept fois en août 2026, c'est la mesure — et non le
système mesuré — qui était en cause. Un « facteur 14 » qui valait 22 %, un
doublon de processus qui n'existait pas, une optimisation entière bâtie sur
l'idée qu'on rouvrait 2 900 fiches alors qu'on n'en ouvrait que les nouvelles.

**2. Un garde-fou qui crie au loup est pire que pas de garde-fou.** Il apprend à
ignorer les alertes. Avant de livrer une surveillance, vérifier qu'elle se tait
quand tout va bien ET qu'elle parle quand ça ne va pas. Trois s'étaient révélés
inertes le même jour (overseer, watch-health, robots.txt) et un criait au loup
(le juge de plausibilité).

**3. Consigner au journal EN FIN DE SÉANCE, sans qu'on le demande.**
`docs/journal-technique.md`, entrée datée, en ajout seul. On n'y réécrit jamais
le passé : une décision qui s'est révélée fausse y reste, suivie de l'entrée qui
la corrige. **Y faire figurer explicitement ce qui n'a PAS été fait** et
pourquoi — abandonné après mesure, laissé à l'arbitrage, ou non vérifié. C'est
cette section qui évite de refaire trois fois la même enquête.

**4. Le code porte le pourquoi, pas le quoi.** Un commentaire dit quel défaut
mesuré a imposé cette ligne, avec le chiffre. `# ~78 % de gain` vaut mieux que
`# compresse le texte`. Un cinquième du code est du commentaire, délibérément.

**5. Ne pas trancher à la place de l'utilisateur** sur la posture (cadence de
scrap, jitter, contournement d'un blocage, seuils d'un garde-fou) ni sur la
méthode statistique. Proposer, chiffrer, laisser décider.

**6. Rien n'entre en production sans mesure préalable**, et une migration
s'applique avec sa contrepartie côté code (`_COLS`, stores, types) — les deux
vont ensemble, sinon le scrap suivant échoue sur une colonne inconnue.

## Objectif
Outil **perso, non public** : carte interactive de Bangkok découpée par quartiers, cliquable (zoom au clic), thème dark violet/anthracite, alimentée par des annonces immobilières scrapées (condos **vente + location**, **foreigner & thai quota**), avec fiches biens et statistiques agrégées (ville / quartier / rue).

## Stack & choix architecturaux (verrouillés)
| Domaine | Choix | Raison |
|---|---|---|
| Moteur carte | **MapLibre GL JS** (vectoriel WebGL) | Thème dark 100% custom, glow jaune sur bordures, couches POI selon zoom, zoom fluide animé |
| Frontend | **Next.js (App Router) + TypeScript + Tailwind** | SSR/routes API, theming par tokens |
| Données géo | **OSM Overpass** → GeoJSON commité dans `/data` | Fiable, gratuit, pas d'appel runtime |
| Backend/stockage | **Supabase (Postgres + Storage)** | DB relationnelle + stockage images webp |
| Scraping | **Python**, pattern adaptateurs | Modulaire ; ajouter un site = un module |
| Images | **webp 1024×768** optimisées (Pillow) | Efficacité / poids |
| Accès privé | **Mot de passe partagé** (page `/login` + cookie, runtime Node — `lib/auth.ts`) | Le middleware Edge plante sur Vercel (`__dirname` injecté par leur runtime, bundle pourtant propre) → gate en Node |
| Posture scraping | Perso non-commercial, ~hebdo, robots.txt respecté | Risque ToS accepté, documenté |

## Principe directeur : TOUT modulaire / interchangeable
On doit pouvoir changer **variables de scraping** et **présentation des données** sans toucher au cœur.

- **Config-driven** : sélecteurs / pagination / rate-limit de chaque site = fichiers dans `config/scrapers/`, jamais en dur dans le code.
- **Schéma de listing normalisé unique** (`lib/types.ts`) = source de vérité (aligné sur la DB).
- **Fiche bien data-driven** (`config/property-card.config.ts`) : sections/champs réordonnables sans modifier les composants.
- **Tokens de thème centralisés** (`config/theme.ts`) : le look se change d'un seul endroit.
- **Pipeline scraping découplé** : `fetch → parse(adapter) → normalize → images → dedupe → upsert → diff → stats`, chaque étape = module indépendant.
- **Resolver de proximité générique** (`lib/proximity.ts`) : catégories POI (école/métro/bus/CBD) interchangeables.

## Structure
```
/app            Next.js App Router (+ /api/listings, /api/khet-stats, /api/pois, middleware.ts)
/components     MapView.tsx, map/* (couches+interactions), PropertyCard.tsx, KhetPanel.tsx
/config         theme.ts, property-card.config.ts, map-style.json, scrapers/<site>.ts
/lib            types.ts (schéma normalisé), supabase.ts, geo.ts, proximity.ts, stats.ts
/data           bangkok-khet.geojson, poi-seed.json
/scraper        Python : adapters/, pipeline/, run.py, requirements.txt
/supabase       schema.sql, migrations/
```

## Où changer quoi (conventions)
- **Variable de scraping d'un site** → `config/scrapers/<site>.ts` (selectors, URLs, pagination, rate-limit). Pas de code touché.
- **Ajouter un site** → nouvel adaptateur `scraper/adapters/<site>.py` (implémente `base.py`) + sa config.
- **Présentation d'une fiche bien** → `config/property-card.config.ts` (ordre/visibilité/label des champs des 3 sections).
- **Couleurs / thème** → `config/theme.ts` (+ `map-style.json` pour la carte).
- **Style carte (eau, rues, métro, labels)** → `config/map-style.json`.

## Modèle de données (Supabase)
- **listings** : `id, source, source_url, title, deal_type(sale|rent), quota(foreigner|thai), price, currency, area_sqm, price_per_sqm, bedrooms, bathrooms, condo_name, address_raw, khet, khwaeng, street, lat, lng, status(active|inactive|sold), first_seen, last_seen, raw_data jsonb`
- **listing_images** : `id, listing_id, storage_path, width, height, order`
- **listing_amenities** : `id, listing_id, name`
- **price_history** : `id, listing_id, price, observed_at`
- **scan_runs** : `id, started_at, source, new_count, removed_count, changed_count`
- **pois** : `id, category, name_en, name_th, lat, lng, khet`
- **condos** : référentiel des IMMEUBLES (`name` PK, `khet`, `lat/lng`, `year_built`, agrégats). L'année de livraison est une propriété du bâtiment, pas de l'annonce.
- **cohort_snapshots** : stock actif par COHORTE (`unit_key` = immeuble × chambres × tranche 5 m² × type) à chaque scan. C'est cette série qui mesure l'écoulement sans être trompée par les republications.
- **social_leads** : annonces réseaux sociaux, **table séparée à dessein** (déclaratif non vérifié → ne doit pas contaminer les stats de marché).
- **Vues** : `khet_stats`, `street_stats`, `listings_sane` (périmètre assaini), `listing_benchmarks` + `opportunites` (cascade de comparaison), `cohort_tension`, `condos_age`.

### Volumétrie (relevée le 2026-07-31 — elle pilote les décisions)
| | |
|---|---|
| Annonces totales | 35 779 |
| **Actives** | **18 843** — fazwaz 9 847 / ddproperty 6 671 / propertyscout 1 520 / nestopa 805 |
| Immeubles connus / avec annonce active | 4 514 / 2 897 |
| `year_built` renseigné | **0** |
| Quota étranger renseigné | 197 (1,2 %) |
| `agent_id` / `posted_at` renseignés | **1 294** — DDproperty **uniquement** |
| `is_auto_repost` | 675 vrais / 619 faux — **vérité terrain fournie par la source** |
| `description` | **0** — colonne créée le 31/07, capture branchée, **non rétroactive** |
| Paires candidates de doublons | 38 355, dont **16 244 tranchées par SQL seul** (42 %) |

> ⚠ Le projet est passé de ~1 000 à 16 000 actives. Les choix « on charge tout »
> (pages en `force-dynamic` sans cache, tableaux sans virtualisation) datent de
> l'ordre de grandeur précédent — voir le journal technique du 2026-07-28 (soir).

### Bornes de plausibilité — source unique
`lib/market-bounds.ts` (TS) et la vue `listings_sane` (SQL) : vente 800 k–100 M,
loyer 3 k–500 k, surface 15–500 m². **Les deux doivent rester alignés.** Toute
statistique (médiane, décote, rendement, tension) se calcule sur ce périmètre —
ne pas refiltrer à la main ailleurs.

## Comportement carte (cahier des charges)
- **Dézoomé** : tout BKK, quartiers + métro (lignes), eau, rues, monuments, stations métro, hôpitaux, écoles, aéroports, train.
- **Mouseover quartier** : bordures luisent en **jaune** (glow).
- **Clic quartier** : zoom animé plein cadre ; apparaissent en plus **commerces** + **arrêts de bus**. Bouton retour.
- **Pinpoints biens** (survol) → fiche 3 sections **data-driven** :
  1. image + nom + prix + m² + chambres + SDB
  2. amenities du condominium
  3. école 1re/2e + proche, métro 1er/2e, bus le + proche, distance CBD
- **Palette** : anthracite (fond) + violet fluo (accents) + violet sombre (surfaces) + touches de bleu ; jaune réservé au glow de survol.

## Interface & navigation
- **Langue : ANGLAIS uniquement.** Pas de sélecteur de langue, pas de menu hamburger (retirés).
- **Direction visuelle : TOUT SOMBRE.** Header Lowi **re-teinté en sombre** (logo « lowi », accent or `#C9A84C`). Carte et tableaux en thème dark violet/anthracite.
- **Header** (`components/LowiHeader.tsx`, police MCTen, sans auth Supabase) : nav **inline** toujours visible — `The map` (`/`) · `For sale` (`/for-sale`) · `To rent` (`/to-rent`) · `Yields` (`/rendements`).
- **Vue par défaut = Carte plein écran** (`/`). Fiche bien (tooltip) au **survol d'un pin** → coin **haut-gauche** de l'écran.
- **Pages vente/location SÉPARÉES** (`components/ListingsTable.tsx`, prop `deal`) :
  - `/for-sale` : ventes uniquement, **exclut < 800 000 et > 100 000 000 THB**. Colonnes : Listing name · District · Price · Price per sqm · Beds · Baths · Area · **Monthly rent** · **Annual yield** (les 2 dernières = unité location recoupée, sinon —).
  - `/to-rent` : locations uniquement. Réglettes/colonnes **Rent (monthly)** / **Rent per sqm** (au lieu de Price/Price per sqm) ; 2 dernières colonnes : **Sale price** · **Annual yield** (unité vente recoupée).
- **Recoupement même-unité** (`lib/cross-match.ts`) : même condo normalisé + khet + chambres + surface ±7 % → on associe vente↔location (pas de fusion) et on calcule le **rendement annuel réel** = loyer×12/prix.
- **Page Yields** (`/rendements`, `components/YieldsTable.tsx` + `lib/yields.ts`) : rendement brut par quartier (médianes), **clic sur un quartier → rendement par rue répertoriée** (`computeYieldsByStreet`). Les rues proviennent du géocodage (cf. pipeline).
- **Filtres (colonne gauche, réglettes activables par case à cocher)** : prix/loyer, surface, prix/m² ou loyer/m², chambres, SDB, **quota** (page vente), **source**, **quartier** (multi). Filtre `type` retiré (la page fixe déjà le deal_type). Combinables, reflétés sur la carte via l'URL (`lib/filters.ts`).

## Pipeline scraping
1. `run.py` lit les sites actifs depuis `config/scrapers/`.
2. Adaptateur : `list_urls` → `parse_listing` (dicts bruts).
3. `normalize.py` → schéma normalisé (quota inclus).
4. `images.py` → download, resize webp 1024×768, optim, upload Storage.
5. Matching quartier : lat/lng → point-in-polygon ; sinon matching texte.
6. `diff.py` : actif/inactif/vendu, changements de prix → `price_history` + alerte ; fiche HTML par annonce.
7. `stats.py` : agrège `scan_runs` + rapport hebdo (nouveaux / retirés / changés).
- Bien disparu → retiré de la carte, conservé en DB (inactive/sold).

### Règles de filtrage à la source (IMPORTANT)
- **Freehold uniquement** : on **ne scrape PAS le leasehold**. L'adaptateur détecte la tenure (mention "leasehold" / "freehold" sur la fiche ou champ dédié) et **écarte les leasehold**. Stocker `tenure='freehold'`.
- **Quota** : extraire `quota` ∈ {`foreigner`, `thai`} depuis la fiche (mots-clés "Foreign quota" / "Thai quota" / "foreign freehold"). Sert de paramètre/filtre dans l'UI.

## Posture scraping (à respecter)
Usage perso non-commercial. Fréquence ~hebdo (pas de boucle serrée). Respect robots.txt autant que possible. Pas de redistribution, pas d'accès public.

## État d'avancement
- [x] **Phase 1** — Scaffold Next.js + MapLibre + thème dark ✓, GeoJSON 50 Khet via Overpass ✓ (`npm run geo:khet`), hover glow jaune + click-zoom plein cadre ✓, basic auth ✓.
- [x] **Phase 5** — POI custom via Overpass ✓ (`npm run geo:pois`) : lignes métro/BTS (**couleurs officielles** via relations de route OSM, tag `colour` porté par feature), stations, gares, aéroports, hôpitaux, **écoles internationales** (filtrées sur nom EN "International" / TH "นานาชาติ"), monuments (overview) + malls & arrêts de bus (zoom quartier). Couches zoom-gatées + légende activable, le tout piloté par `config/poi-config.ts`. Popups au survol. Données : `public/data/pois.geojson` + `pois-local.geojson`.
  - Note : les lignes utilisent `["coalesce", ["get","color"], <fallback>]` dans `components/map/pois.ts`. Le script requête des **relations** `route=*` avec `out body geom` (les members ne sont PAS inclus avec `out tags geom`).
  - **Écoles internationales** : filtre par nom EN "International" / TH "นานาชาติ" + liste blanche de marques (`INTL_SCHOOL_KEYWORDS` dans `scripts/fetch-pois.ts`). Exhaustivité garantie par un **seed manuel** `data/intl-schools-seed.json` (Patana, Denla, KIS — absents/mal tagués dans OSM), fusionné avec dédup nom+proximité. Pour ajouter une école manquante : éditer ce JSON. ~67 écoles.
- [~] **Phase 2** — **Partie locale FAITE** (FazWaz **+ DDproperty**) : `supabase/schema.sql` écrit (à appliquer demain). Pipeline `scraper/` : adaptateurs FazWaz (JSON-LD liste) et DDproperty (`__NEXT_DATA__` Next.js), **fiche complète par bien + galerie webp 1024×768** (détail visité pour tous les biens, `fetch_detail` activé), normalisation, **matching khet point-in-polygon** (`pipeline/geo_match.py`), fiches HTML, **store SQLite** (`output/bangkok.db`) reflétant le schéma, **diff** (new/changed/unchanged) + `price_history` + alertes, **dédup incrémentale** (prix inchangé lu dans la liste → `[skip-dedup]`, fiche non re-visitée → raccourcit les scraps futurs), `--full` → inactif des disparues, scan_runs + stats khet.
  - **Géoloc** : lat/lng **10/10** sur les tests (FazWaz natif dans le JSON-LD liste ; DDproperty dans le `__NEXT_DATA__` de la fiche) → **pinpoint précis sans géocodage ni Chrome**.
  - **DDproperty / Cloudflare** : pages détail derrière un challenge CF. Contourné **sans Chrome** par une **session `requests` réchauffée** (parcourir la liste d'abord → cookie `__cf_bm`) + en-têtes navigateur, **sans brotli** (requests ne le décode pas). `pipeline/fetch.py` récupère robots.txt via la session ; si illisible (challenge) → accès autorisé par défaut (RFC).
  - [x] **Online Supabase FAIT** : projet **Lowi_bkk** (`qbyxxbtzxxzuofiptnxe`, région ap-southeast-1), schéma appliqué + **RLS activé**. `store/supabase_store.py` (psycopg, **connexion Postgres directe via pooler session** `aws-1-ap-southeast-1.pooler.supabase.com:5432`, bypass RLS) ; `run.py --store supabase`. Peuplé (~20 biens, images, price_history, scan_runs ; dédup OK online). App Next lit Supabase via `lib/listings-db.ts` quand `SUPABASE_DB_URL` est défini (`pg`, sinon fallback SQLite). Connexions/clés dans `.env.local` + `scraper/.env` (gitignorés).
  - [x] **Images → Supabase Storage** : bucket public `listings`, upload via clé secret (en-tête `apikey`) — `scraper/pipeline/storage.py`, backfill `scraper/upload_images.py`, sync auto au scrape (`run.py --store supabase`). App résout l'URL via `lib/image-url.ts` (Storage si `NEXT_PUBLIC_SUPABASE_URL`, sinon `/api/img` local).
  - [x] **GitHub** : repo isolé (`git init` dans Lowi_bkk, le parent était le home), poussé sur `Erok-gg/lowi_bkk` (public ; site protégé par basic-auth). Secrets hors repo (`.env.local`, `scraper/.env` gitignorés).
  - [x] **Déploiement Vercel FAIT** : **https://lowi-bkk.vercel.app** (projet `lowi-bkk`, team schoenaueranthony). Build Next 15.4.11, env (`SUPABASE_DB_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `BASIC_AUTH_PASSWORD`). Accès : page `/login`, mot de passe **anthoicare** (cookie `lowi_auth`). Données Supabase + images Storage.
    - **Pièges rencontrés** : (1) `framework: None` sur le projet → 404 partout → corrigé en `nextjs` ; (2) middleware Edge → `__dirname is not defined` (runtime Vercel) même en no-op → remplacé par gate cookie en Node ; (3) Next **downgradé 15.5.19 → 15.4.11** ; (4) protection SSO Vercel désactivée (on utilise notre mot de passe).
- [x] **Phase UI** — Infrastructure d'interface :
  - [x] Header **Lowi re-teinté sombre** (`components/LowiHeader.tsx`, logo MCTen, accent or), sans auth Supabase ✓
  - [x] **Carte plein écran** en vue par défaut (`/`), header au-dessus, layout flex ✓
  - [x] **Réglettes double-curseur activables** + multi-toggles (quota, source, quartier) ✓
  - [x] **Données** : `lib/listings-db.ts` (Supabase si `SUPABASE_DB_URL`, sinon SQLite local) ✓
  - [x] **Filtres ↔ carte** : `lib/filters.ts` (logique unique), tableau écrit l'URL (`history.replaceState`), carte relit (`applyUrlFilters`) ✓
  - Note dev : `reactStrictMode:false` (le double-mount dev annulait le chargement du style MapLibre). `window.__map` exposé pour debug.
- [x] **Phase UI v2 (2026-06-23)** — **Anglais only** (sélecteur de langue + hamburger retirés) ; nav `The map / For sale / To rent / Yields`. **Pages vente/location séparées** (`/for-sale` exclut <800k & >100M ; `/to-rent` relabel Rent/Rent per sqm). Colonne+filtre **Type retirés**. **Recoupement même-unité** `lib/cross-match.ts` → colonnes Monthly rent/Sale price + **Annual yield** réel. **Yields par rue** (clic quartier, `computeYieldsByStreet`). Tooltip carte → **haut-gauche**. PropertyCard/property-card.config en anglais.
- [x] **Règles scraping freehold/quota** — **DDproperty** : `tenureCode='F'` → freehold gardé, leasehold écarté ; quota non exposé (None). **FazWaz** : freehold par défaut + quota best-effort via code `ownership` de l'unité (snapshot Livewire inconstant → souvent None). `tenure` ajouté au schéma (SQLite + `supabase/schema.sql`).
- [x] **Phase 4** — Pinpoints biens sur carte (or Lowi + anneau blanc, `components/MapView.tsx`) ✓ ; **PropertyCard data-driven** (`components/PropertyCard.tsx` piloté par `config/property-card.config.ts`, photo via `/api/img`) au survol ✓ ; **proximité** client-side (`lib/proximity.ts` : école 1re/2e, métro 1er/2e, bus le + proche, distance CBD, via les POI de `/public`) ✓. Reste : amenities FazWaz enrichies, géoloc DDproperty (déjà précise via fiche).
- [x] **Sources locatif + 2 nouveaux sites (2026-06-23)** : adaptateurs **PropertyScout** (`adapters/propertyscout.py`, Next.js `__NEXT_DATA__`, pagination `/page-N/`) et **Nestopa** (`adapters/nestopa.py`, ld+json `Product` du flux `/th-en/for-sale|for-rent`, filtre Bangkok par l'URL, champs depuis le slug/nom ; **pas de coords serveur** → khet par slug, coords via géocodage). **FazWaz rent réparé** (URL `/property-rent/`, id inclut le deal_type). **Utiliser `.venv/Scripts/python.exe`** (psycopg).
- [x] **Géocodage condos Nominatim (2026-06-23)** : `scraper/pipeline/geocode.py` (1 req/s, cache `output/geocode-cache.json`, échecs cachés) ; flag `run.py --geocode` (complète street/coords manquants au scrape) ; backfill `scraper/backfill_geocode.py` (ne remplit que le manquant, ne crase pas les coords précises, redéduit le khet sur nouvelles coords). Taux de hit Nominatim ~35-40 % sur noms de condos thaï.
- [x] **Stats v2 — double médiane par condo (2026-07-04)** : `lib/yields.ts` réécrit. Prix/m² = médiane des annonces PAR CONDO puis médiane des condos (1 immeuble = 1 voix ; neutralise vétusté/vue/étage sans date de construction). Rendement = médiane des rendements **within-condo** (loyer et prix du MÊME immeuble, ≥5 condos appariés, sinon repli ratio marqué †). Winsorisation p5-p95 par groupe (n≥20), badge `lowSample` (<20 condos d'un côté). **Strate 0–1BR par défaut** (panier constant) — toggle Studio–1BR / 2BR / 3BR+ / All sur `/rendements` (calcul client, `YieldsTable`) et `/yields-map`. Méthode expliquée dans l'UI ("How is this computed?" + légende carte). `YListing` porte désormais `id`+`condoName`. Constat data (2026-07-04) : 1 154 condos ont vente ET location actives = 81 % du stock actif → base du within-condo.
- [x] **Scrap ciblé par district (2026-07-04)** : flag `run.py --config <json>` (config alternative, mêmes clés). Configs `scraper/config/targets/fazwaz-corridors.json` (rent 13 districts + sale 7, URLs `/condo-for-rent/thailand/bangkok/<slug>`) et `ddproperty-corridors.json` (rent, `freetext=<district>`). Cible : rive ouest (Bangkok Noi/Yai, Thon Buri, Phasi Charoen, Bang Phlat, Taling Chan, Chom Thong, Rat Burana) + couloir Orange Est (Bang Kapi, Bueng Kum, Saphan Sung, Wang Thonglang, Min Buri). ⚠ jamais `--full` avec une config ciblée (scan partiel → délistage interdit).
- [x] **Calques couloirs de développement (2026-07-04)** : `npm run geo:corridors` (`scripts/fetch-corridors.ts`) → `public/data/corridors.geojson`. Lignes en construction via Overpass `railway=construction` (Orange E/O, Purple Sud, HSR 3 aéroports + segments génériques gris) + zones de développement seed manuel `data/dev-zones-seed.json` (Bang Sue/KTA acté, Makkasan pending, Khlong Toei port pending, Rama IV livré — polygones approximatifs, statut→couleur). Catégories `future_line` (pointillés, label le long de la ligne) et `dev_zone` (fill + contour pointillé + popup note) dans `poi-config.ts` (groupe `corridors`) ; `pois.ts` gère désormais `geometry:"polygon"` et `dash`. **+ Masques contexte (2026-07-04)** : `expat_zone` (8 hubs expat, seed manuel `data/expat-zones-seed.json` — Sukhumvit core, Silom/Sathon, Riverside, Ari, On Nut, Rama 9, Nichada Thani, Bang Na-Trat) et `industrial_zone` (OSM `landuse=industrial` ≥ 0,25 km², ~60 zones). Décochés par défaut dans la légende.
- [x] **Framework d'étude de marché récurrente (2026-07-06)** : `study/` — `config.json` (TOUS les paramètres figés, versionnés par `config_version` ; en changer un = incrémenter la version, ça trace les ruptures de série), `context.md` (narratif manuel : historique 10 ans + perspectives, à éditer à la main quand le contexte change), `run_study.py` (orchestrateur). **Rituel : après chaque cycle hebdo de scraps `--full`, lancer `scraper/.venv/Scripts/python.exe study/run_study.py`** → snapshot daté `study/snapshots/YYYY-MM-DD.json` (committé) + étude datée `docs/etudes/etude-YYYY-MM-DD.md`. Les tables d'évolution (prix/m², rendement WC, churn par khet, Δ vs édition précédente) se construisent automatiquement dès 2 snapshots. Sections : état marché 0-1BR, évolution, contexte manuel, 10 opportunités/quartier expat (fiches+liens, flags ⚠ si décote >40 % ou renta >9,5 %), école ≤5 km + métro ≤500 m (existant ou futur), tension délistées (churn normalisé par le stock actif). 1re édition manuelle : `docs/etude-marche-2026-07.md` ; 1re édition framework : `docs/etudes/etude-2026-07-06.md`.
- [x] **Archivage local + purge serveur (2026-07-09)** : `ops/sync_supabase_local.py` — réplique toutes les tables Supabase dans `archive/lowi-archive.db` (SQLite, gitignoré), puis `--prune` supprime du serveur les annonces inactives délistées >90 j **uniquement si leur copie est vérifiée id par id dans l'archive** (garde-fous : une table archivée en retard sur le serveur → purge interdite ; candidates absentes → annulée). ⚠ **L'introspection n'a longtemps porté que sur les COLONNES** : `SYNC_TABLES` était une liste figée de 7 noms, si bien que `condos`, `cohort_snapshots` et `posted_at_history` (~607 k lignes) n'ont jamais été archivées jusqu'au 2026-08-20. Depuis, tables, colonnes **et clés primaires** sont lues au catalogue à chaque run (`condos` a pour PK `name`, pas `id`). Le local = référence historique complète ; le serveur = fenêtre chaude. **Tâche Windows `LowiBKK-ArchiveSync`** (hebdo, dim. 21:00, wrapper `ops/sync-archive.ps1`, logs `ops/logs/`) — suppression : `schtasks /Delete /TN "LowiBKK-ArchiveSync" /F`. Le local = référence historique complète ; le serveur = fenêtre chaude. **Tâche Windows `LowiBKK-ArchiveSync`** (hebdo, dim. 21:00, wrapper `ops/sync-archive.ps1`, logs `ops/logs/`) — suppression : `schtasks /Delete /TN "LowiBKK-ArchiveSync" /F`.
- [x] **Scraps planifiés (2026-07-09)** : tâches Windows tous les 4 jours à 08:00, en alternance décalée de 2 j — **`LowiBKK-ScrapVente`** (dès 11/07 : fazwaz sale --full → passe ciblée couloirs en RESTAURATION → ddproperty sale --full --geocode) et **`LowiBKK-ScrapLocation`** (dès 13/07 : fazwaz rent --full → couloirs → ddproperty rent --full --geocode → couloirs DD → propertyscout --full → nestopa --full --geocode → **run_study.py**). Wrappers `ops/scrap-vente.ps1` / `ops/scrap-location.ps1`, logs `ops/logs/`, rattrapage si PC éteint (StartWhenAvailable), limite 10 h. Principe anti-conflit : le scan global --full peut délister à tort les annonces des districts ciblés hors fenêtre 150 pages → la passe ciblée qui SUIT les réactive (touch/upsert remettent status=active + images re-traitées). L'étude tourne en fin de journée location (les 2 deal_types frais ≤4 j).
- [x] **Rapport mensuel planifié (2026-07-09)** : tâche Claude `rapport-mensuel-lowi-bkk` (1er du mois 09:00, sidebar "Scheduled") — scraps full si données >5 j, `study/run_study.py`, note de conjoncture `docs/etudes/mensuel-YYYY-MM.md` (mouvements vs snapshots + veille web REIC/BOT/transit), `ops/sync --prune`, commit+push. Prompt autonome prévu pour tourner sur Opus.
- [ ] **Phase 3** — Vues stats affinées (déjà : diff/price_history/stats khet en local) + street_stats
- [ ] **Phase 6** — Autres adaptateurs (Hipflat…), cron hebdo, alertes email, stats affinées
- [x] **Revue de code + assainissement (2026-07-28 soir)** — sept écarts entre descriptif et code, corrigés (détail et mesures : journal technique).
  - **Bornes de plausibilité** unifiées : `lib/market-bounds.ts` + vue `listings_sane` ; `opportunites` reconstruite dessus (elle affichait en tête des locations mal classées en vente à −100 %). Appliquées à `/for-sale`, `/to-rent`, `/rendements`, `/yields-map`, `lib/deals.ts`. **Pas** appliquées à la carte : un pin reste de la donnée brute, une médiane non.
  - **Tension** : pression vendeuse sur périmètre ACTIF (le dénominateur incluait les délistées → tension gonflée dans les quartiers à fort churn, −33 % à Vadhana) ; `reliableDelistingSince` = `DELISTING_FIX_DATE` **par défaut** ; momentum prix sur la **médiane** (la moyenne court 16 % au-dessus) ; colonne « Sellers/bldg » affichée ; descriptifs des 2 vues corrigés.
  - **`lib/condo-name.ts`** : normalisation du nom d'immeuble, exemplaire unique (était en double dans `yields.ts`/`cross-match.ts`, absente de `tension.ts`). ⚠ diverge encore de `_norm_condo` (Python) — ne pas comparer un regroupement TS à un `unit_key`.
  - **Médiane vs moyenne** : `median_price` contenait une moyenne en SQLite et une médiane en Postgres ; aligné. `median_price_per_sqm` désormais renseigné en local.
  - **Arrondi de tranche** : Python (arrondi bancaire) divergeait de SQL (half-up) → cohortes scindées. Convention SQL adoptée.
  - **`npm test`** (node:test + tsx) et `npm run typecheck` : le test précédent ne pouvait pas s'exécuter et ne sortait jamais en erreur.
- [x] **Provenance des annonces + allègement des pages (2026-07-28 nuit)**
  - **Les « 1 399 doublons » n'en étaient pas.** Inspection : identifiants d'unité FazWaz *consécutifs* (u6548791…u6548800) = lots distincts versés en lot par une agence. Une dédup aurait effacé de l'offre réelle. Ces annonces sont de plus *simultanément* actives — rien à voir avec la republication séquentielle que traitent les cohortes.
  - **Ce qui rend la question décidable** : `agent_id`/`agency_id`, déjà présents dans le `__NEXT_DATA__` DDproperty et jusqu'ici ignorés (remplis 22/22 à la sonde). Vue `doublons_agent` fournie mais **non branchée** sur les stats : vide tant que le champ n'est pas collecté.
  - **`posted_at`** (`postedOn.unix`) et **`is_auto_repost`** capturés. ⚠ **Ce n'est PAS une date de mise en ligne, et la substitution à `first_seen` annoncée ici est ANNULÉE** — mesure du 2026-08-02, détail dans [posted_at_history.sql](supabase/migrations/posted_at_history.sql) : écart médian `first_seen − posted_at` = **−16 j**, soit l'annonce vue seize jours *avant* sa publication déclarée. Le champ se comporte comme une date de **remontée en tête de liste** ; le substituer *raccourcirait* le time-on-market et mesurerait l'assiduité des agents à rafraîchir. S'ajoute que le champ n'existe que sur DDproperty, dont la part du stock actif va de **3 % à 89 % selon le quartier** : une métrique mixte varierait avec la composition des sources, pas avec le marché. **`first_seen` reste la base unique** (biais uniforme sur les 4 sources, donc comparable) ; le correctif de l'absorption reste les cohortes `unit_key`. Table `posted_at_history` branchée sur les 2 stores pour prouver ou démentir le mécanisme au prochain scrap.
  - **Poids des pages −80 %** : `/for-sale` 19,6 → **3,9 Mo** (3,7 s → **0,51 s** en cache), `/to-rent` 19,7 → 4,0 Mo, `/rendements` 13,4 → 3,2 Mo. Quatre causes : requêtes rejouées (mémoïsation `lib/cache.ts` — **pas `unstable_cache`**, plafonné à 2 Mo/entrée sur Vercel), appariement vente↔location déporté côté serveur, projections `ListingRow`/`YieldInput` au lieu de `Listing` complets, et rendu du tableau par tranches de 200.
- [x] **Système d'agents — 12 bots orchestrés (2026-07-31)** — `agents/`, doc complète : [agents/README.md](agents/README.md).
  - **Les 3 tâches Windows n'avaient JAMAIS tourné** depuis leur création (11/07) : guillemets échappés littéraux dans le XML (`-File \"C:\...\"`), insérés par le parsing de la chaîne `schtasks`. Preuve : `ops/logs/` n'existait pas. D'où aussi `docs/etudes/` figé au 09/07 sur des données du 29/07. Remplacées par **une seule** tâche `LowiBKK-Agents` (quotidienne 08:00 → `orchestrator.py --due`), enregistrée par `ops/install-agents-task.ps1` **qui relit le XML et refuse tout `\"`**. Vérifiée en exécution (`0x00041301`).
  - **12 agents** alignés sur le deck : 4 extraction · 2 surveillance · 2 analyse · 1 organisation · 1 reporting · 1 stockage · 1 supervision. Chacun a son `agents/skills/<agent>/SKILL.md` (mission, procédure, **contrat de sortie** vérifié par l'overseer, bandes, escalade, modes de panne).
  - **Trois étages** : **T0 déterministe** (8 agents — il leur manquait l'orchestration, pas l'intelligence) · **T1 local `qwen3:8b` en MODE EXTRACTION uniquement** · **T2 Claude** par file de tickets `agents/queue/` (pas de CLI ni de clé API sur la machine).
  - **Ledger SQLite** (`agents/ledger.db`) : chaque run, chaque constat, chaque escalade. C'est lui qui rend l'overseer possible et qui calcule ce qui est dû (le rattrapage vient de la base, pas de `StartWhenAvailable`).
  - **Ce que la mesure a imposé** (650+ appels sur paires réelles, détail au journal) : `/no_think` est **silencieusement ignoré** → sorties vides → **panne muette** (0/10) ; le paramètre natif `think` corrige (8/10). Raisonnement inutile ici (9/10 à 22 s contre 9/10 à 3,6 s). Prompt bref **92 %** vs procédure verbeuse **69 %**. Abstention forcée par prompt → **12/100**. **Mode extraction** (le modèle constate, le code décide) → **99 % et 77 % d'abstention** contre **0 %** d'abstention pour le verdict direct. Auto-cohérence sans effet. `confidence` auto-déclarée inutilisable comme seuil.
  - **Garde-fou permanent** : `agents/tests/test_local_llm.py` — seuils **≥ 90/100** et **≥ 70 % d'abstention**, à ne pas relâcher pour faire passer le test.
  - **Aucune fusion ni suppression d'annonce** : findings seulement. Les verdicts sur paires ambiguës vont en file de revue (`agents/state/organize/revue.jsonl`) et n'influencent aucune statistique.
  - **Alertes** : `agents/audits/CHANGELOG.md` exhaustif + e-mail Gmail sur sévérité haute seulement. Claude écrit sur **branche**, jamais `main`.
- [x] **Descriptifs capturés (2026-07-31)** — colonne `description` + `scraper/pipeline/description.py`, branchée sur les 4 adaptateurs. Aucun texte libre n'était stocké jusque-là (`raw_data ? 'description'` = 0 partout) : le « motif du vendeur » des case studies venait de l'audit humain, pas de la donnée. Deux pièges corrigés en testant sur de vraies pages : le `ld+json` FazWaz décrit **l'organisation** et non le bien ; le contenu des blocs `<style>` survivait au détaguage et arrivait en CSS. **Nestopa n'a rien d'exploitable** (champ absent ou redite des specs, pages détail en 403) — 0 % y est attendu. **Non rétroactif.**
- [x] **Cinquième source : LivingInsider (2026-08-05)** — `scraper/adapters/livinginsider.py` + config, agent `extract-livinginsider` (T0, lane rent). Vérifié indépendant de nos 4 sources (images sur son propre domaine, pas de CDN partagé). Deux limites structurelles : **aucune dédup incrémentale possible** (liste sans prix → chaque scan revisite tout, `max_pages` posé bas à 25 en attendant une mesure réelle), et **filtre Bangkok imparfait** sur un flux national à adresses mal formatées (repli sur code postal, 18/20 retenues sur l'échantillon testé contre 1/20 avec la regex stricte seule — voir journal technique). **DotProperty écarté après enquête** : 90/90 annonces échantillonnées chargent leurs photos depuis `cdn.fazwaz.com`/`img.fazwaz.com` — semble syndiquer FazWaz, déjà scrapé ; adaptateur non écrit, décision finale laissée à trancher. **propertynetwork.asia clarifié** : pas un agrégateur, un outil de partage client posé sur PropertyScout (confirmé par l'agent source + vérifié empiriquement) — exclu, aucune donnée unique. **Le mécanisme T2 n'existait pas** : `agents/README.md` promettait une tâche planifiée drainant `agents/queue/`, aucune ne le faisait (`queue/done/` vide depuis le 31/07) — tâche locale `drain-agent-queue-lowi-bkk` créée (quotidienne). Détail complet : [journal technique du 2026-08-05](docs/journal-technique.md). Travail sur branche `agents/new-sources-livinginsider-dotproperty`, pas encore mergée — aucun run de production, bandes provisoires.
- [x] **Widget de bureau (2026-08-10)** — `ops/widget/` ([README](ops/widget/README.md)) : panneau posé sur le bureau, prochaines échéances des tâches Windows + routines Claude + cycle d'agents. Rafraîchi à l'ouverture de session, à la sortie de veille/déverrouillage (`SystemEvents`, drapeau relevé par la minuterie — pas de rappel inter-thread) et toutes les 10 min. Trois sources, trois natures : tâches Windows lues en direct ; agents calculés depuis `agents.json` + `ledger.db` en lecture seule, **rendus au prochain créneau réel de `LowiBKK-Agents`** et non à leur date d'échéance (avec la lane `weekly` calculée sur l'ordinal **UTC** — à 01:00 Bangkok on est encore la veille en UTC) ; **routines Claude recalculées depuis un cron recopié à la main** dans `config.json`, faute d'API locale (elles vivent côté serveur Claude ; vérifié : le calcul retombe à la seconde sur les `nextRunAt` annoncés). ⚠ **toute création/modification d'une routine Claude doit être reportée dans `config.json`**, rien ne signale la désynchronisation. Sobriété demandée et appliquée : ni WinForms ni System.Drawing, collecte dans un processus court séparé, interface reconstruite seulement si `etat.json` a bougé, `EmptyWorkingSet` après chaque rendu (~50-60 Mo). Installé par raccourci Démarrage (`installe.ps1`), relancé par `garde.vbs`.
- [x] **Faille RLS fermée + archive complétée (2026-08-20)** — Les 15 vues de `public` étaient **SECURITY DEFINER** (`reloptions = NULL`) et appartiennent à `postgres`, dont `rolbypassrls = true` : `anon` contournait donc intégralement le RLS deny-all des tables en passant par une vue, et pouvait **écrire** sur `listings`/`condos`/`social_leads` via les 3 vues auto-updatables. Prouvé avant correctif (en transaction annulée, écriture no-op : 1 ligne atteinte via `listings_sane`, 0 via `listings`), re-testé après (`42501 permission denied`). Correctif : `security_invoker = true` sur les 15 vues, `revoke all` pour `anon`/`authenticated` sur `public`, **et** `alter default privileges ... revoke all` (sans quoi `pg_default_acl` reposait les grants sur chaque nouvelle table). Les 14 `create or replace view` du dépôt portent désormais `with (security_invoker = true)` — **`CREATE OR REPLACE VIEW` remet `reloptions` à zéro**, rejouer un fichier rouvrait la faille en silence. Rollback généré depuis l'état live : `supabase/migrations/2026-08-20_rollback_rls_hardening.sql`. ⚠ Les 11 alertes `rls_enabled_no_policy` (INFO) **restent et doivent rester** : c'est le deny-all voulu, y ajouter une policy rouvrirait l'accès. Détail, dérive fichiers↔serveur (4 vues sans migration) et ce qui n'a pas été fait : [journal technique du 2026-08-20](docs/journal-technique.md).
- [ ] **Suites identifiées (mesurées, non traitées)** : `/tension-table` pèse encore 8,6 Mo (sérialise les 34 275 annonces) ; dédup même-agent applicable au prochain scrape ; sonder PropertyScout pour l'agent ; empreinte photo inerte (0 ligne, `est_doublon` sans appelant) ; `year_built` à backfiller **côté serveur** ; quota étranger par immeuble ; logique métier dupliquée `study/run_study.py` ↔ `lib/yields.ts` ; décision à prendre sur le ticket DotProperty (creuser une fraction non-FazWaz, ou clore) ; premier run de production `livinginsider` à lancer puis bandes `agents.json` à recalibrer.
- [ ] **Idées plus tard** : jitter/mouvements aléatoires anti-ban ; heatmaps loyers & prix sur la carte (couche MapLibre pondérée).
