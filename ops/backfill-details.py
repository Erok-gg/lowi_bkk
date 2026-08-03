"""backfill-details.py — remplit les 12 colonnes de details sur une base EXISTANTE.

Les descriptifs sont deja collectes ; l'extraction ne demande aucun reseau et
tourne en quelques secondes sur 15 000 annonces. Ce script evite donc de
re-scraper pour beneficier des nouvelles colonnes.

Par defaut il vise la base de TEST la plus recente — la production n'est jamais
touchee sans --db explicite.

Usage :
    python ops/backfill-details.py                    # base de test la + recente
    python ops/backfill-details.py --db <chemin>      # base precise
    python ops/backfill-details.py --dry-run          # compte, n'ecrit rien
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sqlite3
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scraper"))

from pipeline import details  # noqa: E402

COLONNES = details.COLONNES   # types declares une seule fois, dans details.py


def assurer_colonnes(db: sqlite3.Connection) -> None:
    existantes = {r[1] for r in db.execute("pragma table_info(listings)")}
    for nom, typ in COLONNES:
        if nom not in existantes:
            db.execute(f"alter table listings add column {nom} {typ}")
    db.commit()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    chemin = a.db
    if not chemin:
        cands = sorted(glob.glob(os.path.join(ROOT, "tests-scrap", "*", "bangkok.db")),
                       key=os.path.getmtime, reverse=True)
        if not cands:
            print("Aucune base de test trouvee — passer --db")
            return 2
        chemin = cands[0]
    if not os.path.exists(chemin):
        print(f"Base introuvable : {chemin}")
        return 2
    print(f"base : {chemin}\n")

    db = sqlite3.connect(chemin)
    db.row_factory = sqlite3.Row
    if not a.dry_run:
        assurer_colonnes(db)

    lignes = db.execute("select id, source, area_sqm, description from listings "
                        "where description is not null").fetchall()
    print(f"{len(lignes)} annonces avec descriptif")

    remplis = Counter()
    par_source = {}
    maj = 0
    for r in lignes:
        e = details.extraire(r["description"], r["area_sqm"])
        vals = []
        for c in details.CHAMPS:
            v = e[c]
            if isinstance(v, list):
                v = json.dumps(v, ensure_ascii=False)
            elif isinstance(v, bool):
                v = int(v)
            vals.append(v)
            if e[c] is not None:
                remplis[c] += 1
                par_source.setdefault(r["source"], Counter())[c] += 1
        if not a.dry_run:
            sql = ("update listings set "
                   + ",".join(f"d_{c}=?" for c in details.CHAMPS) + " where id=?")
            db.execute(sql, (*vals, r["id"]))
            maj += 1
    if not a.dry_run:
        db.commit()

    n = len(lignes)
    print(f"\n{'champ':22s}{'rempli':>8s}{'couverture':>12s}")
    print("-" * 42)
    for c in details.CHAMPS:
        print(f"d_{c:20s}{remplis[c]:>8d}{100 * remplis[c] / max(1, n):>11.0f}%")

    print(f"\n{'source':16s}" + "".join(f"{c[:9]:>10s}" for c in
                                        ("etage", "annee_con", "meuble", "quota", "cam_fee")))
    src_tot = Counter(r["source"] for r in lignes)
    for src, cnt in par_source.items():
        t = src_tot[src]
        print(f"{src:16s}" + "".join(
            f"{100 * cnt[c] / max(1, t):>9.0f}%" for c in
            ("etage", "annee_construction", "meuble", "quota", "cam_fee_thb")))

    print(f"\n{'[dry-run] rien ecrit' if a.dry_run else f'{maj} annonces mises a jour'}")
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
