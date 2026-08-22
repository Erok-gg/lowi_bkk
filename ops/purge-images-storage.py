"""purge-images-storage.py — vider Supabase Storage des images, SANS perdre la
possibilité de les remettre.

POURQUOI CE SCRIPT EXISTE
Mesuré le 2026-08-22 : le bucket `listings` pesait **1 610 Mo pour 39 785
fichiers**, soit ~157 % du quota free tier (1 Go), alors que les *métadonnées*
de ces mêmes images ne pèsent que 11 Mo en base. Le poids n'était pas là où on
le cherchait — et purger les images des annonces retirées n'aurait rendu que
2,3 Mo (58 fichiers), la quasi-totalité étant sur des annonces ACTIVES.

CE QUI EST CONSERVÉ, DÉLIBÉRÉMENT
  · la table `listing_images` et ses lignes — donc le lien annonce ↔ image ;
  · le pipeline (`scraper/pipeline/images.py`, `storage.py`) intact ;
  · les fichiers LOCAUX de `scraper/output/images/`.
Remettre les images en ligne = `python scraper/upload_images.py`, qui parcourt
le disque local et re-téléverse. Rien à reconstruire.

LE GARDE-FOU, repris de `sync_supabase_local.py --prune`
On ne supprime du serveur QUE les objets dont la copie locale est vérifiée
fichier par fichier. Un objet sans copie locale est LAISSÉ EN PLACE et signalé :
le supprimer serait une perte sèche, pas une libération d'espace.

Lancement :
    scraper\\.venv\\Scripts\\python.exe ops/purge-images-storage.py            (à blanc)
    ... --confirmer            supprime réellement
    ... --sans-copie-locale    supprime AUSSI ce qui n'a pas de copie locale
                               (perte définitive — à n'utiliser qu'en connaissance)
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL = os.path.join(ROOT, "scraper", "output")

for _l in open(os.path.join(ROOT, "scraper", ".env"), encoding="utf-8"):
    _l = _l.strip()
    if _l and not _l.startswith("#") and "=" in _l:
        _k, _v = _l.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip())
sys.path.insert(0, os.path.join(ROOT, "scraper"))
import psycopg                                    # noqa: E402
from pipeline.storage import SupabaseStorage      # noqa: E402

LOT = 400          # taille de lot pour l'API Storage (body JSON {"prefixes": [...]})


def main() -> int:
    ap = argparse.ArgumentParser(description="Purge des images de Supabase Storage")
    ap.add_argument("--confirmer", action="store_true",
                    help="supprime réellement (sans ce drapeau : simulation)")
    ap.add_argument("--sans-copie-locale", action="store_true",
                    help="supprime aussi les objets sans copie locale (PERTE DÉFINITIVE)")
    a = ap.parse_args()

    storage = SupabaseStorage.from_env()
    if not storage:
        return print("SUPABASE_URL / SUPABASE_SERVICE_KEY manquants dans scraper/.env") or 1

    # Inventaire côté serveur, lu au catalogue Storage plutôt qu'à l'API de
    # listing : l'API pagine par 100 et demanderait 400 requêtes.
    with psycopg.connect(os.environ["SUPABASE_DB_URL"], connect_timeout=60) as pg:
        c = pg.cursor()
        c.execute("select name, (metadata->>'size')::bigint from storage.objects "
                  "where bucket_id = %s order by name", (storage.bucket,))
        objets = c.fetchall()

    if not objets:
        print(f"Bucket '{storage.bucket}' déjà vide.")
        return 0

    total_o = sum(t or 0 for _, t in objets)
    print(f"Bucket '{storage.bucket}' : {len(objets)} objets, {total_o / 1048576:.0f} Mo")

    avec, sans, poids_avec, poids_sans = [], [], 0, 0
    for nom, taille in objets:
        # storage_path == chemin relatif sous scraper/output/ (images/<id>/N.webp)
        if os.path.exists(os.path.join(LOCAL, nom.replace("/", os.sep))):
            avec.append(nom)
            poids_avec += taille or 0
        else:
            sans.append(nom)
            poids_sans += taille or 0

    print(f"  copie locale vérifiée : {len(avec)} objets, {poids_avec / 1048576:.0f} Mo")
    print(f"  SANS copie locale     : {len(sans)} objets, {poids_sans / 1048576:.0f} Mo")

    cibles = avec + (sans if a.sans_copie_locale else [])
    if sans and not a.sans_copie_locale:
        print("\n  Les objets sans copie locale sont LAISSÉS EN PLACE : les supprimer")
        print("  serait une perte sèche. `--sans-copie-locale` pour passer outre.")

    poids = poids_avec + (poids_sans if a.sans_copie_locale else 0)
    restant = total_o - poids
    print(f"\nÀ supprimer : {len(cibles)} objets, {poids / 1048576:.0f} Mo")
    print(f"Resterait   : {len(objets) - len(cibles)} objets, {restant / 1048576:.0f} Mo "
          f"(quota free tier : 1024 Mo)")

    if not a.confirmer:
        print("\nSIMULATION — rien n'a été supprimé. Ajouter --confirmer pour agir.")
        return 0
    if not cibles:
        print("\nRien à supprimer.")
        return 0

    print()
    faits = 0
    for i in range(0, len(cibles), LOT):
        lot = cibles[i:i + LOT]
        faits += storage.delete_many(lot)
        print(f"  {faits}/{len(cibles)} supprimés", flush=True)

    with psycopg.connect(os.environ["SUPABASE_DB_URL"], connect_timeout=60) as pg:
        c = pg.cursor()
        c.execute("select count(*), coalesce(sum((metadata->>'size')::bigint), 0) "
                  "from storage.objects where bucket_id = %s", (storage.bucket,))
        n, o = c.fetchone()
    print(f"\nAprès purge : {n} objets, {o / 1048576:.0f} Mo dans '{storage.bucket}'")
    print("Les lignes de `listing_images` sont CONSERVÉES : remettre les images en")
    print("ligne = scraper\\.venv\\Scripts\\python.exe scraper/upload_images.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
