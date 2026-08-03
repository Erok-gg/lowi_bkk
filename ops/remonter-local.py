"""remonter-local.py — pousse un scrap LOCAL validé vers Supabase.

Raison d'être : un cycle complet dure 6 à 10 heures. Le refaire en ligne après
validation gaspillerait ce temps et solliciterait les sources une seconde fois
sans raison. Ce script transfère ce qui a déjà été collecté.

Il réutilise `SupabaseStore.upsert_listing` — le MÊME chemin d'écriture que le
scraper. Rien de spécifique n'est réinventé : l'historique de prix, les images et
les amenities suivent la même logique qu'un scrap en ligne.

CE QU'IL NE FAIT PAS, volontairement :
  - aucun délistage. Un transfert n'est pas un scan : il ne peut pas conclure
    qu'une annonce absente a disparu du marché.
  - aucune suppression, aucun écrasement de champ par une valeur vide.

Usage :
    python ops/remonter-local.py <dossier-de-test> --dry-run   # compte, n'écrit rien
    python ops/remonter-local.py <dossier-de-test>             # écrit
    python ops/remonter-local.py <dossier> --avec-images       # + upload Storage
"""
from __future__ import annotations

import argparse
import json
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


def charger(db_path: str) -> list[dict]:
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    lignes = [dict(r) for r in db.execute("select * from listings")]
    for l in lignes:
        # raw_data est stocké en TEXT côté SQLite, en jsonb côté Postgres
        if isinstance(l.get("raw_data"), str):
            try:
                l["raw_data"] = json.loads(l["raw_data"])
            except json.JSONDecodeError:
                l["raw_data"] = {}
        # is_auto_repost : integer côté SQLite, boolean côté Postgres
        if l.get("is_auto_repost") is not None:
            l["is_auto_repost"] = bool(l["is_auto_repost"])
        # photo_sizes : TEXT JSON côté SQLite, ARRAY côté Postgres
        if isinstance(l.get("photo_sizes"), str):
            try:
                l["photo_sizes"] = json.loads(l["photo_sizes"])
            except json.JSONDecodeError:
                l["photo_sizes"] = None
        l["amenities"] = []
        l["image_urls"] = []
    return lignes


def images_de(db_path: str) -> dict[str, list[dict]]:
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    out: dict[str, list[dict]] = {}
    try:
        for r in db.execute("select * from listing_images order by listing_id, \"order\""):
            out.setdefault(r["listing_id"], []).append(dict(r))
    except sqlite3.OperationalError:
        pass
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dossier")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--avec-images", action="store_true",
                    help="upload aussi les fichiers vers Supabase Storage")
    a = ap.parse_args()

    db_path = os.path.join(a.dossier, "bangkok.db")
    if not os.path.exists(db_path):
        print(f"✗ base introuvable : {db_path}")
        return 2

    lignes = charger(db_path)
    imgs = images_de(db_path)
    par_source: dict[str, int] = {}
    for l in lignes:
        par_source[l["source"]] = par_source.get(l["source"], 0) + 1

    print(f"Source  : {db_path}")
    print(f"À remonter : {len(lignes)} annonces — " +
          ", ".join(f"{s} {n}" for s, n in sorted(par_source.items())))
    print(f"Images     : {sum(len(v) for v in imgs.values())} pour {len(imgs)} annonces")

    if a.dry_run:
        print("\n[dry-run] rien n'a été écrit.")
        print("Retirer --dry-run pour transférer vers Supabase.")
        return 0

    dsn = os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        print("✗ SUPABASE_DB_URL manquant (scraper/.env)")
        return 2

    from store.supabase_store import SupabaseStore
    store = SupabaseStore(dsn)

    storage = None
    if a.avec_images:
        try:
            from pipeline import storage as storage_mod
            storage = storage_mod.SupabaseStorage.from_env()
            print(f"Storage    : bucket '{storage.bucket}'")
        except Exception as e:  # noqa: BLE001
            print(f"! upload Storage indisponible ({e}) — métadonnées seulement")

    # VERROU D'INSTANCE UNIQUE. Le 2026-08-03, deux exemplaires de ce script ont
    # tourné en concurrence sur la MÊME base : le premier n'avait pas été arrêté
    # avant le lancement du second, après correction d'un conflit de type. Sans
    # dommage durable — les deux écrivaient par upsert — mais 16 990 écritures
    # perdues et une charge inutile sur Supabase. Rien ne l'empêchait.
    sys.path.insert(0, ROOT)
    from agents.core.gpu import Verrou

    # Pris pour toute la durée du processus. Pas de `with` : le verrou est posé
    # par le SYSTÈME sur un descripteur ouvert, donc il se relâche tout seul à la
    # mort du processus — plantage compris. C'est exactement ce qu'on veut ici.
    Verrou("remonter-local").__enter__()

    nouvelles = maj = erreurs = 0
    for i, l in enumerate(lignes, 1):
        try:
            existant = store.get_listing(l["id"])
            store.upsert_listing(l, imgs.get(l["id"]))
            if existant:
                maj += 1
            else:
                nouvelles += 1
            if storage:
                for im in imgs.get(l["id"], []):
                    chemin = os.path.join(a.dossier, im["storage_path"])
                    if os.path.exists(chemin):
                        storage.upload(chemin, im["storage_path"])
        except Exception as e:  # noqa: BLE001
            erreurs += 1
            if erreurs <= 5:
                print(f"  [erreur] {l['id']} : {type(e).__name__} {e}")
        if i % 500 == 0:
            print(f"  … {i}/{len(lignes)} ({nouvelles} nouvelles, {maj} mises à jour)")

    print(f"\n✓ Terminé — {nouvelles} nouvelles, {maj} mises à jour, {erreurs} erreur(s)")
    print("  Aucun délistage effectué : un transfert n'est pas un scan.")
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
