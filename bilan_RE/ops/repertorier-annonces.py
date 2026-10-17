"""repertorier-annonces.py — à lancer APRÈS chaque scrap : tient `condo_norm` à jour.

    scraper/.venv/Scripts/python.exe bilan_RE/ops/repertorier-annonces.py [--db <base>] [--tout]

POURQUOI. Le bilan retrouve un immeuble sur tous les portails par son nom
normalisé (FazWaz « Noble Ploenchit », DDproperty « Noble Ploenchit, Bangkok »),
et l'interroge par l'index `idx_listings_condo_norm`. Or les extracteurs ne
remplissent pas cette colonne : ils nomment leurs colonnes à l'écriture et ne la
connaissent pas (choix délibéré : pas de changement des stores, pas de
désalignement avec Supabase, qui n'en a pas besoin). Ce script la remplit.

CE QU'IL FAIT
  1. Si la colonne ou les index manquent (base restaurée d'une sauvegarde, autre
     poste) : applique bilan_RE/migrations/2026-10-17_index_bilan.sql puis _2.sql,
     additifs, et le dit. Les rollbacks sont dans le même dossier.
  2. Recalcule `condo_norm` pour les annonces jamais répertoriées (NULL) et pour
     celles vues depuis le dernier passage (un nom peut avoir changé au scrap).
     `--tout` recalcule toute la table (premier passage, ou changement de la
     règle de normalisation).
  3. Imprime une ligne JSON de métriques (contrat de l'agent `repertorier-annonces`).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RACINE, "scraper"))
from pipeline.normalize import _norm_condo  # noqa: E402

SORTIES = os.environ.get("LOWI_OUTPUT_DIR") or os.path.join(RACINE, "scraper", "output")
DB = os.path.join(SORTIES, "bangkok.db")
MIGRATIONS = os.path.join(RACINE, "bilan_RE", "migrations")
MIGRATION = os.path.join(MIGRATIONS, "2026-10-17_index_bilan.sql")
MIGRATION_2 = os.path.join(MIGRATIONS, "2026-10-17_index_bilan_2.sql")
INDEX = {"idx_listings_condo_norm", "idx_listings_vente_khet", "idx_listings_last_seen"}
INDEX_2 = {"idx_listings_vente_lat", "idx_price_history_listing"}
LOT = 5000   # mises à jour par transaction : la base reste lisible pendant le passage


def migrer_si_besoin(c: sqlite3.Connection) -> bool:
    cols = {r[1] for r in c.execute("pragma table_info(listings)")}
    idx = {r[0] for r in c.execute("select name from sqlite_master where type='index'")}
    fait = False
    if not INDEX_2 <= idx:     # second lot : index seuls, idempotent
        c.executescript(open(MIGRATION_2, encoding="utf-8").read())
        fait = True
    if "condo_norm" in cols and INDEX <= idx:
        return fait
    sql = open(MIGRATION, encoding="utf-8").read()
    if "condo_norm" in cols:   # colonne déjà là, seuls des index manquent
        sql = "\n".join(l for l in sql.splitlines() if not l.strip().upper().startswith("ALTER TABLE"))
    c.executescript(sql)
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB)
    ap.add_argument("--tout", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    t0 = time.perf_counter()
    c = sqlite3.connect(a.db, timeout=60)
    migree = migrer_si_besoin(c)
    etat = os.path.join(os.path.dirname(os.path.abspath(a.db)), "repertorier-annonces.etat")
    depuis = None if a.tout or migree or not os.path.exists(etat) else open(etat).read().strip()
    debut_passage = c.execute("select max(last_seen) from listings").fetchone()[0]

    if depuis:
        rows = c.execute("select id, condo_name, condo_norm from listings "
                         "where condo_norm is null or last_seen >= ?", (depuis,)).fetchall()
    else:
        rows = c.execute("select id, condo_name, condo_norm from listings").fetchall()
    # Un nom qui se normalise en vide (« Bangkok Condo ») reçoit "" et non NULL :
    # NULL veut dire « pas encore répertorié », et le contrôle de fin compterait
    # sinon 10 fausses anomalies chaque nuit (mesuré au premier passage).
    maj = [(n, i) for i, nom, ancien in rows
           if (n := (_norm_condo(nom) if nom is not None else None)) != ancien]
    for k in range(0, len(maj), LOT):
        c.executemany("update listings set condo_norm = ? where id = ?", maj[k:k + LOT])
        c.commit()
    restantes = c.execute("select count(*) from listings where condo_norm is null "
                          "and condo_name is not null and trim(condo_name) <> ''").fetchone()[0]
    c.close()
    if debut_passage:
        with open(etat, "w") as f:
            f.write(debut_passage)
    print(json.dumps({"lignes_examinees": len(rows), "lignes_mises_a_jour": len(maj),
                      "lignes_nulles_restantes": restantes, "migration_appliquee": migree,
                      "passage": "complet" if not depuis else f"depuis {depuis[:19]}",
                      "duree_s": round(time.perf_counter() - t0, 1)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
