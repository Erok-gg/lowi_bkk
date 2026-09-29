"""verifie-avant-degraissage.py — le local detient-il TOUT ce qu'on va retirer du serveur ?

POURQUOI CE SCRIPT EXISTE
L'option retenue le 2026-08-25 retire de Supabase ce que l'app ne lit jamais :
les colonnes `page_text` et `description` de `listings`, et les tables
`cohort_snapshots` et `listing_amenities`. Apres quoi PC2 en est le SEUL
detenteur. On ne supprime donc rien avant d'avoir prouve la copie — meme
principe que le garde-fou de purge de ops/sync_supabase_local.py : une table
locale en retard sur le serveur interdit l'operation.

Le bon test n'est pas « meme nombre de lignes » : le local a legitimement PLUS
(il continue de scraper). Le seul test qui compte est :
    aucune ligne du serveur ne manque en local.

Sortie 0 = degraissage autorise. Sortie 1 = INTERDIT, rien ne doit etre supprime.
"""
from __future__ import annotations

import datetime as _dt
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scraper"))

for _l in open(os.path.join(ROOT, "scraper", ".env"), encoding="utf-8"):
    _l = _l.strip()
    if _l and not _l.startswith("#") and "=" in _l:
        _k, _v = _l.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip())

import psycopg  # noqa: E402

LOCAL = os.path.join(ROOT, "scraper", "output", "bangkok.db")
LOT = 20000

echecs: list[str] = []


def _norme(v) -> str:
    """Ecriture canonique d'une cle, pour comparer serveur et local.

    Sans elle, `str(datetime)` cote Postgres rend
    « 2026-07-28 03:58:19.556794+00 » quand SQLite a stocke
    « 2026-07-28T03:58:19.556794+00:00 » : separateur et fuseau different, et
    les 842 738 lignes de cohort_snapshots ressortaient TOUTES comme manquantes
    alors que le local en detient 1 182 220 (mesure du 2026-08-25). C'etait la
    mesure qui etait fausse, pas la base - regle 1 du CLAUDE.md.
    """
    if v is None:
        return ""
    if isinstance(v, _dt.datetime):
        return v.isoformat()
    return str(v)


def verdict(nom: str, ok: bool, detail: str) -> None:
    print(f"  {'ok   ' if ok else 'REFUS'} {nom} - {detail}", flush=True)
    if not ok:
        echecs.append(nom)


def colonne_listings(cur, loc, col: str) -> None:
    """Chaque annonce du serveur portant une valeur doit la porter en local."""
    cur.execute(f"select count(*) from listings where {col} is not null and {col} <> ''")
    n_srv = cur.fetchone()[0]
    cur.execute(f"select id from listings where {col} is not null and {col} <> ''")
    manquantes, vides = 0, 0
    exemples: list[str] = []
    while True:
        lot = cur.fetchmany(LOT)
        if not lot:
            break
        ids = [r[0] for r in lot]
        marques = ",".join("?" * len(ids))
        trouve = {
            r[0]: r[1] for r in loc.execute(
                f"select id, length(coalesce({col},'')) from listings where id in ({marques})", ids)
        }
        for i in ids:
            if i not in trouve:
                manquantes += 1
                if len(exemples) < 3:
                    exemples.append(f"{i} (absente)")
            elif not trouve[i]:
                vides += 1
                if len(exemples) < 3:
                    exemples.append(f"{i} (vide en local)")
    ok = manquantes == 0 and vides == 0
    detail = (f"{n_srv} lignes serveur, toutes retrouvees en local"
              if ok else f"{manquantes} absentes + {vides} vides — ex. {exemples}")
    verdict(f"listings.{col}", ok, detail)


def table_entiere(cx, loc, table: str, cle: list[str]) -> None:
    """Chaque ligne du serveur doit exister en local, sur sa cle.

    Comparaison ENSEMBLISTE et non ligne a ligne : la premiere version
    interrogeait SQLite une fois par ligne serveur et n'a pas fini en 10 minutes
    sur listing_amenities (613 000 lignes). On charge les cles locales une fois
    dans un set, puis on balaye le serveur en flux.
    """
    try:
        n_loc = loc.execute(f"select count(*) from {table}").fetchone()[0]
    except sqlite3.OperationalError as e:
        verdict(table, False, f"table absente en local ({e})")
        return
    locales = {
        tuple(_norme(v) for v in r)
        for r in loc.execute(f"select {','.join(cle)} from {table}")
    }
    n_srv = 0
    manquantes, exemples = 0, []
    with cx.cursor(name=f"cur_{table}") as cur:
        cur.itersize = LOT
        cur.execute(f"select {','.join(cle)} from {table}")
        while True:
            lot = cur.fetchmany(LOT)
            if not lot:
                break
            n_srv += len(lot)
            for ligne in lot:
                k = tuple(_norme(v) for v in ligne)
                if k not in locales:
                    manquantes += 1
                    if len(exemples) < 3:
                        exemples.append(str(ligne))
    ok = manquantes == 0
    verdict(table, ok,
            f"{n_srv} lignes serveur / {n_loc} en local, aucune manquante"
            if ok else f"{manquantes} lignes serveur ABSENTES en local - ex. {exemples}")


def main() -> int:
    if not os.path.exists(LOCAL):
        print(f"base locale introuvable : {LOCAL}")
        return 1
    loc = sqlite3.connect(f"file:{LOCAL}?mode=ro", uri=True)
    print(f"\nlocal   : {LOCAL}")
    print("serveur : Supabase (SUPABASE_DB_URL)\n")
    with psycopg.connect(os.environ["SUPABASE_DB_URL"]) as cx:
        with cx.cursor(name="curseur_verif") as cur:
            colonne_listings(cur, loc, "page_text")
        with cx.cursor(name="curseur_verif2") as cur:
            colonne_listings(cur, loc, "description")
        table_entiere(cx, loc, "listing_amenities", ["listing_id", "name"])
        table_entiere(cx, loc, "cohort_snapshots", ["taken_at", "unit_key"])
    print()
    if echecs:
        print(f"DEGRAISSAGE INTERDIT — {len(echecs)} controle(s) en echec : {', '.join(echecs)}")
        return 1
    print("DEGRAISSAGE AUTORISE — le local detient tout ce qui serait retire du serveur.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
