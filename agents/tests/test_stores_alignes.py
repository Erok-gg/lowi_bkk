"""test_stores_alignes.py — une colonne ajoutee d'un seul cote doit rougir ici.

POURQUOI CE TEST EXISTE
La regle 6 du CLAUDE.md dit qu'« une migration s'applique avec sa contrepartie
cote code (_COLS, stores, types) — les deux vont ensemble, sinon le scrap suivant
echoue sur une colonne inconnue ». C'etait une PHRASE : aucun controle ne
l'appliquait. Deux listes de colonnes vivaient a la main en parallele (`_COLS`
dans supabase_store.py, un tuple local dans sqlite_store.upsert_listing).

Mesure du 2026-08-25, AVANT de toucher quoi que ce soit : les deux listes etaient
identiques, 49 colonnes de part et d'autre. Aucune derive en cours — la fusion en
un exemplaire unique (`store.base.COLONNES_LISTING`) est donc un no-op
semantique, et ce test ne corrige pas un bug : il empeche celui de demain.

CE QU'IL VERIFIE, ET POURQUOI PAS AUTRE CHOSE
Comparer les deux tuples Python entre eux ne prouve plus rien depuis la fusion
(ils sont le meme objet). Le defaut qui coute vraiment, c'est la colonne presente
dans le CODE et absente de la BASE : le scrap part, tourne, et meurt a l'ecriture
sur « column ... does not exist » — cote online seulement, la ou `_migrate()`
rattrape silencieusement le cote SQLite. Le test confronte donc la liste aux
colonnes REELLES des deux bases.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_stores_alignes.py
         (le volet Postgres exige SUPABASE_DB_URL ; sans lui il se declare
          NON VERIFIE a voix haute, il ne se tait pas — regle 2)
"""
import os
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "scraper"))

from store.base import COLONNES_LISTING, COLONNES_LOCALES   # noqa: E402
from store.sqlite_store import SqliteStore       # noqa: E402

echecs: list[str] = []


def verifie(nom: str, condition: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if condition else 'ECHEC'} {nom}{(' - ' + detail) if detail else ''}")
    if not condition:
        echecs.append(nom)


print(f"\nCOLONNES_LISTING : {len(COLONNES_LISTING)} colonnes\n")

# --- 1. Exemplaire unique -----------------------------------------------------
# Un futur « je remets vite fait la liste ici » redonnerait deux exemplaires sans
# rien casser tout de suite. C'est exactement comme ca que la derive commence.
print("Exemplaire unique")
from store import sqlite_store                   # noqa: E402
verifie("sqlite_store utilise COLONNES_LISTING",
        sqlite_store.COLONNES_LISTING is COLONNES_LISTING)
try:
    from store.supabase_store import _COLS
    verifie("supabase_store._COLS est COLONNES_LISTING", _COLS is COLONNES_LISTING)
except ImportError as e:                          # pg8000 absent
    print(f"  NON VERIFIE supabase_store — import impossible ({e})")
    echecs.append("supabase_store non importable")

verifie("aucun doublon dans la liste",
        len(COLONNES_LISTING) == len(set(COLONNES_LISTING)))

# --- 2. La base SQLite porte-t-elle ces colonnes ? ----------------------------
# Base NEUVE : c'est le schema + _migrate() qu'on teste, pas une base de travail
# qui aurait ete rattrapee a la main.
print("\nSQLite (base neuve : schema + _migrate)")
with tempfile.TemporaryDirectory() as d:
    st = SqliteStore(Path(d) / "test.db")
    reelles = {r["name"] for r in st.db.execute("pragma table_info(listings)")}
    st.close() if hasattr(st, "close") else None
attendues_sqlite = COLONNES_LISTING + COLONNES_LOCALES
manquantes = [c for c in attendues_sqlite if c not in reelles]
verifie("socle + colonnes locales existent dans listings",
        not manquantes, f"manquantes : {manquantes}" if manquantes else f"{len(reelles)} colonnes en base")

# --- 3. Et la base Postgres ? -------------------------------------------------
# Le cote qui casse pour de vrai : SQLite se rattrape tout seul par `_migrate()`,
# Postgres non — il faut y avoir applique la migration.
print("\nPostgres (Supabase)")
dsn = os.environ.get("SUPABASE_DB_URL")
if not dsn:
    env = RACINE / "scraper" / ".env"
    if env.exists():
        for ligne in env.read_text(encoding="utf-8").splitlines():
            if ligne.startswith("SUPABASE_DB_URL="):
                dsn = ligne.split("=", 1)[1].strip().strip('"').strip("'")
                break
if not dsn:
    print("  NON VERIFIE — SUPABASE_DB_URL absent (ni environnement, ni scraper/.env).")
    print("  Ce volet est le SEUL qui prouve qu'une migration a ete appliquee en ligne.")
else:
    try:
        from store.pg import connecter  # pg8000 (Python pur) et non psycopg depuis le 2026-10-09 — voir store/pg.py
        with connecter(dsn) as cx, cx.cursor() as cur:
            cur.execute("select column_name from information_schema.columns "
                        "where table_schema='public' and table_name='listings'")
            reelles_pg = {r[0] for r in cur.fetchall()}
            cur.execute("select table_name from information_schema.tables "
                        "where table_schema='public' and table_name in "
                        "('cohort_snapshots','listing_amenities')")
            tables_de_trop = [r[0] for r in cur.fetchall()]
        manquantes_pg = [c for c in COLONNES_LISTING if c not in reelles_pg]
        verifie("le socle commun existe dans public.listings",
                not manquantes_pg,
                f"manquantes : {manquantes_pg}" if manquantes_pg
                else f"{len(reelles_pg)} colonnes en base")
        # L'ABSENCE est un resultat, pas un oubli : elle prouve que la migration
        # du 2026-08-25 a bien ete appliquee en ligne. Si ces colonnes
        # reapparaissent, c'est qu'un `create table` ou un rollback les a
        # remises et que le serveur regonfle sans qu'on l'ait decide.
        restantes = [c for c in COLONNES_LOCALES if c in reelles_pg]
        verifie("les colonnes locales sont ABSENTES du serveur",
                not restantes,
                f"encore presentes : {restantes}" if restantes else "page_text et description bien retires")
        verifie("les tables locales seules sont ABSENTES du serveur",
                not tables_de_trop,
                f"encore presentes : {tables_de_trop}" if tables_de_trop
                else "cohort_snapshots et listing_amenities bien retirees")
    except Exception as e:
        print(f"  NON VERIFIE — connexion impossible ({type(e).__name__}: {e})")

print()
if echecs:
    print(f"ECHEC : {len(echecs)} controle(s) - {', '.join(echecs)}")
    sys.exit(1)
print("Tous les controles executes sont passes.")
