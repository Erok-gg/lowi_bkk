---
name: lowi-couche-donnees
description: Ordre de construction et vérifications pour tout changement de la couche données Lowi BKK — schéma, migration SQL, stores SQLite/Supabase, types TS, lecture app. À utiliser dès qu'on ajoute ou modifie une colonne, une vue, un store, un chemin de lecture de la base, ou qu'on bascule la source de données (online ↔ locale). Triggers — 'ajoute une colonne', 'migration', 'schema.sql', 'nouvelle vue', 'store', 'SUPABASE_DB_URL', 'base offline', 'archive locale', 'listings-db'.
---

# lowi-couche-donnees

Ce qui a déjà cassé ici est écrit dans [docs/journal-technique.md](../../../docs/journal-technique.md).
Ce skill est l'ordre dans lequel on procède pour ne pas le refaire.

## 1. Avant de toucher : nommer, puis mesurer

`$env:COMPUTERNAME` — `BB-12` = PC1 (sauvegarde), `REMIZDABOSS` = PC2 (coureur).

Puis **relever l'état de départ, chiffré, et l'écrire** : nombre de lignes, de
colonnes, poids. Sept fois en août 2026 c'est la mesure — et non le système
mesuré — qui était en cause. Un « avant » non relevé rend l'« après » illisible.

## 2. L'ordre canonique

Sauter une case fait mourir le scrap suivant sur une colonne inconnue.

> **Un RETRAIT s'applique dans l'ordre INVERSE.** Pour ajouter : schéma →
> migration → code. Pour retirer une colonne ou une table : **le code cesse
> d'écrire d'abord**, la suppression vient ensuite — sinon le scrap en cours meurt
> sur `column ... does not exist`. Et avant tout retrait, prouver que la donnée
> survit ailleurs : `ops/verifie-avant-degraissage.py` (2026-08-25, il a refusé
> deux fois à raison). Le `drop column` ne rend l'espace qu'après
> `vacuum full` — verrou exclusif, donc jamais pendant un scrap.

1. **`supabase/schema.sql`** — la référence.
2. **`supabase/migrations/<sujet>.sql`** — appliquée en ligne. Une vue se réécrit
   **avec `with (security_invoker = true)`** : `create or replace view` remet
   `reloptions` à zéro, rejouer un fichier sans cette clause rouvre la faille RLS
   fermée le 2026-08-20.
3. **`scraper/store/base.py` → `COLONNES_LISTING`** — exemplaire unique. Les deux
   stores l'importent ; ne jamais recopier la liste dans l'un d'eux.
   Les colonnes de détail dérivent de `details.COLONNES`, jamais recopiées non plus.
4. **`sqlite_store._migrate()`** — le `alter table` qui rattrape les bases
   existantes. SQLite se répare tout seul ; **Postgres non**.
5. **`lib/types.ts` + `lib/listings-db.ts`** — les deux branches de lecture
   (`SUPABASE_DB_URL`, et le repli SQLite piloté par `LOWI_SQLITE_DB`).
6. **Le test** — sans quoi rien n'applique les points 3 et 4 :

```bash
scraper/.venv/Scripts/python.exe agents/tests/test_stores_alignes.py
```

Il confronte `COLONNES_LISTING` aux colonnes **réelles** des deux bases. Le volet
Postgres exige `SUPABASE_DB_URL` ; sans lui il se déclare **NON VERIFIÉ à voix
haute**, et c'est pourtant le seul qui prouve qu'une migration a été appliquée.

## 3. Vérifier le garde-fou, pas seulement le code

Un garde-fou qui crie au loup est pire que pas de garde-fou. Avant de livrer :
**le faire échouer exprès** (casser la donnée qu'il surveille) et vérifier qu'il
parle ; puis le rejouer sur l'état sain et vérifier qu'il se tait. Trois s'étaient
révélés inertes le même jour, un criait au loup.

## 4. Les pièges déjà payés sur cette pile

- **`lowi-archive.db` n'est pas une base applicative** : miroir d'introspection
  (tables, colonnes et PK lues au catalogue). Ne pas supposer qu'il répond aux
  requêtes de l'app.
- **`scraper/output/` est vide sur PC2** alors que `listings-db.ts` y pointe par
  défaut : le repli SQLite est mort par défaut ici. Vérifier avant de s'y fier.
- **WAL** : `ledger.db` et les bases SQLite se copient par l'API `backup` de
  sqlite, jamais par `cp` — sinon transactions perdues.
- **Booléens** : SQLite range 0/1, Postgres exige `boolean`
  (`_BOOLEENNES` dans `supabase_store.py`).
- **Arrondi** : Python arrondit à la banquière, SQL en half-up. Convention SQL
  adoptée — un écart scinde les cohortes.
- **Médiane ≠ moyenne** : `median_price` a contenu l'une en SQLite et l'autre en
  Postgres.
- **Bornes de plausibilité** : `lib/market-bounds.ts` **et** la vue
  `listings_sane` — les deux doivent rester alignées, ne pas refiltrer ailleurs.
- **Tâches Windows** : réinstallées par `ops/install-*.ps1`, jamais par réimport
  du XML (chemins figés). `[int]` **arrondit** en PowerShell, utiliser `[Math]::Floor`.

## 5. Ce qui reste à l'arbitrage de l'utilisateur

Ne pas trancher seul : cadence de scrap, seuils d'un garde-fou, méthode
statistique, et **le partage online/local** (ce que Supabase garde vs ce que la
base locale porte). Proposer, chiffrer, laisser décider.

## 6. Fin de séance

`docs/journal-technique.md`, entrée datée, en ajout seul, **avec la section « ce
qui n'a PAS été fait »** — abandonné après mesure, laissé à l'arbitrage, ou non
vérifié.
