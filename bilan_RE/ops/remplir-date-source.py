"""remplir-date-source.py — remplit `listed_at_source` des annonces PropertyScout
déjà en base, depuis le texte de fiche conservé (`page_text`, « Date Listed »).

    python bilan_RE/ops/remplir-date-source.py            # à blanc : compte, n'écrit rien
    python bilan_RE/ops/remplir-date-source.py --appliquer

Pas de réseau. Ne touche QUE les lignes où la colonne est vide ; rejouable.
Les scraps à venir la renseignent eux-mêmes (adaptateur propertyscout) — mais la
dédup incrémentale ne rouvre pas une fiche dont le prix n'a pas bougé, d'où ce
rattrapage. Rollback : bilan_RE/migrations/2026-10-22_date_source_rollback.sql.
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import zlib
from datetime import date, datetime

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(RACINE, "scraper", "output", "bangkok.db")
MOTIF = re.compile(r"Date Listed\W+([A-Z][a-z]+ \d{1,2}, \d{4})")


def lire(texte: bytes | str | None) -> str | None:
    if texte is None:
        return None
    if isinstance(texte, bytes):
        try:
            texte = zlib.decompress(texte).decode("utf-8", "ignore")
        except zlib.error:
            texte = texte.decode("utf-8", "ignore")
    m = MOTIF.search(texte)
    if not m:
        return None
    try:
        d = datetime.strptime(m.group(1), "%B %d, %Y").date()
    except ValueError:
        return None
    return d.isoformat() if d <= date.today() else None   # une date future est une erreur


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--appliquer", action="store_true")
    ap.add_argument("--db", default=DB)
    a = ap.parse_args()
    c = sqlite3.connect(a.db, timeout=60)
    if "listed_at_source" not in {r[1] for r in c.execute("pragma table_info(listings)")}:
        raise SystemExit("colonne absente : appliquer d'abord bilan_RE/migrations/2026-10-22_date_source.sql")
    lignes = c.execute("select id, page_text from listings where source='propertyscout' "
                       "and listed_at_source is null and page_text is not null").fetchall()
    trouves = [(lire(t), i) for i, t in lignes]
    ok = [(d, i) for d, i in trouves if d]
    print(f"candidates {len(lignes)} · date lue {len(ok)} · illisibles {len(lignes) - len(ok)}")
    if a.appliquer:
        for k in range(0, len(ok), 500):
            with c:
                c.executemany("update listings set listed_at_source=? where id=?", ok[k:k + 500])
        print("écrit.")
    else:
        print("à blanc : rien écrit (--appliquer pour écrire).")


if __name__ == "__main__":
    main()
