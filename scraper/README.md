# Scraper (partie locale)

Pipeline modulaire qui scrape des annonces, les normalise, traite les images en
webp 1024×768, génère des fiches HTML et stocke le tout dans un **SQLite local**
(`output/bangkok.db`) reflétant le schéma Supabase. Aucune connexion online requise.

## Installation
```bash
cd scraper
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# (macOS/Linux : source .venv/bin/activate && pip install -r requirements.txt)
```

## Utilisation
```bash
python run.py --source fazwaz --limit 5       # test : 5 annonces
python run.py --source ddproperty --limit 5   # idem pour DDproperty
python run.py --source fazwaz                 # selon max_pages de la config
python run.py --source fazwaz --full          # marque les disparues inactives (scan complet)
python run.py --source fazwaz --no-images     # saute les images
```

`fetch_detail` est activé par défaut (config) : chaque bien a sa **fiche
complète + galerie webp**. La **dédup incrémentale** saute la fiche d'une annonce
déjà connue dont le prix (lu dans la liste) n'a pas bougé (`[skip-dedup]`) →
les scraps suivants sont bien plus courts. `--fetch-detail` force l'enrichissement
si désactivé en config.

### Sources
- **FazWaz** : lat/lng + champs dans le JSON-LD des pages de liste ; fiche pour
  galerie + amenities. HTTP simple.
- **DDproperty** : app Next.js, données dans `__NEXT_DATA__`. lat/lng **précis**
  dans la fiche. Pages détail derrière Cloudflare → accédées via la **session
  réchauffée** (liste d'abord = cookie `__cf_bm`) + en-têtes navigateur. **Pas de Chrome.**

Sorties dans `output/` (git-ignoré) :
- `bangkok.db` — base SQLite (listings, images, price_history, scan_runs…)
- `images/<id>/0.webp` — images optimisées
- `fiches/<id>.html` — fiche par annonce

## Modularité — où changer quoi
- **Variables de scraping** (URLs, pagination, débit, taille image, fetch_detail) :
  `config/<source>.json`. Aucun code à toucher.
- **Ajouter un site** : créer `adapters/<site>.py` (sous-classe `BaseAdapter`,
  implémente `list_urls` + `parse_listing`) + `config/<site>.json` + l'enregistrer
  dans `ADAPTERS` de `run.py`.
- **Présentation de la fiche** : `pipeline/fiche.py`.

## Architecture
```
adapters/      base.py (interface) + fazwaz.py
pipeline/      fetch (HTTP+robots+débit), normalize, geo_match (khet PIP),
               images (webp), fiche (HTML)
store/         base.py (interface) + sqlite_store.py  ← demain : supabase_store.py
run.py         orchestrateur
config/        variables par site (JSON)
```

## Posture
Usage perso, non-commercial. Débit limité (`rate_limit_seconds`), robots.txt
respecté (FazWaz n'interdit que `/api/` et `/graphql`). FazWaz est scrapé via le
**JSON-LD des pages de liste** (1 requête = N annonces) — poli et robuste.

## Demain — partie online
- Appliquer `../supabase/schema.sql` sur Supabase.
- Ajouter `store/supabase_store.py` (même interface `BaseStore`) + upload des
  images vers Supabase Storage.
- Brancher `run.py --store supabase`.
```
