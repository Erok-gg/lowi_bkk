# CLAUDE.md — Bangkok Real Estate Map

> Doc de référence du projet. À lire avant toute modif. Tient l'état d'avancement à jour.

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
| Accès privé | **Basic auth** (middleware Next.js, mot de passe en env) | Simple, compatible voyage |
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
- **Vues** : `khet_stats`, `street_stats` (nb annonces, prix moyen/médian/m², distribution par type, évolution).

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
- **Direction visuelle : TOUT SOMBRE.** Header Lowi **re-teinté en sombre** (on garde logo « lowi », structure, l'accent or `#C9A84C` comme touche premium sur anthracite). La carte et le tableau restent dans le thème dark violet/anthracite.
- **Vue par défaut = Carte plein écran** (grand format, zoomable), affichée en premier.
- **Header Lowi** (porté depuis `++FILES++/Github/lowi`) : `LowiNav.tsx` (logo, liens, **menu hamburger + drawer**, sélecteur de langue FR/EN/TH) ; styles `dashboard/app/(public)/public.css` ; tokens `lowi-tokens.css` ; police `mc-ten-lowercase-alt.ttf`. **Adapté** : on retire l'auth Supabase du header (l'app est privée, basic-auth) ; liens = **Carte** / **Biens (tableau)**.
- **Menu hamburger** → bascule Carte ↔ **Vue Tableau des biens**.
- **Vue Tableau** : toutes les annonces, colonnes **Nom de l'annonce · Quartier · Prix · Chambres · SDB · Surface**. **Toutes triables** (asc/desc).
- **Filtres (colonne de gauche, réglettes/sliders)** : fourchette de **prix**, fourchette de **surface (m²)**, **chambres** (min/max), **SDB** (min/max), **quota** (foreigner / thai), **type** (vente / location), fourchette **prix/m²**, **quartier** (multi-sélection), **source** (FazWaz / DDproperty). Filtres et tri combinables, reflétés aussi sur les pinpoints de la carte.

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
  - **Reste online** : déploiement **Vercel** (connecter le repo + variables d'env + basic-auth).
- [~] **Phase UI** — *(AVANT l'online, décision user)* Infrastructure d'interface :
  - [x] Header **Lowi re-teinté sombre** (`components/LowiHeader.tsx`, logo « lowi » police MCTen `public/fonts/mcten.ttf`, accent or), **hamburger + drawer**, langues FR/EN/TH, sans auth Supabase ✓
  - [x] **Carte plein écran** en vue par défaut (`/`), header au-dessus, layout flex ✓
  - [x] **Vue Tableau** (`/biens`) : colonnes Nom · Quartier · Prix · Chambres · SDB · Surface, **toutes triables** (`components/ListingsTable.tsx`) ✓
  - [x] **Filtres latéraux (réglettes double-curseur)** : prix, surface, prix/m², chambres, SDB + multi-toggles quota (foreigner/thai), type (vente/location), source, quartier — combinables ✓
  - [x] **Données** : lecture SQLite local via `node:sqlite` (`lib/listings-db.ts`, `/api/listings`, page `/biens`) — bascule Supabase à l'online sans changer l'UI ✓
  - [x] **Filtres ↔ carte** : `lib/filters.ts` (logique unique), le tableau écrit les filtres dans l'URL (`history.replaceState`), la carte relit ces params pour ses pinpoints (`applyUrlFilters`) ✓
  - Note dev : `reactStrictMode:false` (le double-mount dev annulait le chargement du style MapLibre). `window.__map` exposé pour debug.
- [x] **Règles scraping freehold/quota** — **DDproperty** : `tenureCode='F'` → freehold gardé, leasehold écarté ; quota non exposé (None). **FazWaz** : freehold par défaut + quota best-effort via code `ownership` de l'unité (snapshot Livewire inconstant → souvent None). `tenure` ajouté au schéma (SQLite + `supabase/schema.sql`).
- [x] **Phase 4** — Pinpoints biens sur carte (or Lowi + anneau blanc, `components/MapView.tsx`) ✓ ; **PropertyCard data-driven** (`components/PropertyCard.tsx` piloté par `config/property-card.config.ts`, photo via `/api/img`) au survol ✓ ; **proximité** client-side (`lib/proximity.ts` : école 1re/2e, métro 1er/2e, bus le + proche, distance CBD, via les POI de `/public`) ✓. Reste : amenities FazWaz enrichies, géoloc DDproperty (déjà précise via fiche).
- [ ] **Phase 3** — Vues stats affinées (déjà : diff/price_history/stats khet en local) + street_stats
- [ ] **Phase 6** — Autres adaptateurs (Hipflat…), cron hebdo, alertes email, stats affinées
