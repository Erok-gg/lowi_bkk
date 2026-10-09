"""rapatrie-textes.py — ramene en local le texte que SEUL le serveur detient.

POURQUOI CE SCRIPT EXISTE
Constate le 2026-08-25 en preparant le degraissage de Supabase : quelques
annonces portent `page_text` / `description` sur le serveur et rien en local.
Cause mesuree, pas supposee : la DEDUP INCREMENTALE. Prix inchange dans la page
de liste -> la fiche detail n'est pas revisitee -> le texte n'est jamais capture
cote local, alors que le serveur l'avait capture avant la bascule en
`--store sqlite`. Ces annonces sont bien presentes en local (0 absente) ; c'est
leur TEXTE qui manque.

Retirer les colonnes du serveur sans ce rapatriement detruirait ce texte.

Deux details qui comptent :
  - `page_text` est stocke COMPRESSE (zlib) cote SQLite et en clair cote
    Postgres. On recompresse a l'ecriture, sinon la colonne devient illisible
    pour `SqliteStore.decompresser()`.
  - on n'ecrase JAMAIS une valeur locale non vide : le local fait reference.

Usage :
    python ops/rapatrie-textes.py --dry-run   # compte, n'ecrit rien
    python ops/rapatrie-textes.py             # ecrit
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scraper"))

for _l in open(os.path.join(ROOT, "scraper", ".env"), encoding="utf-8"):
    _l = _l.strip()
    if _l and not _l.startswith("#") and "=" in _l:
        _k, _v = _l.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip())

from store.pg import connecter  # pg8000 (Python pur) et non psycopg depuis le 2026-10-09 — voir store/pg.py

LOCAL = os.path.join(ROOT, "scraper", "output", "bangkok.db")
LOT = 20000


def a_rapatrier(cx, loc, col: str) -> list[str]:
    """Ids dont le serveur a le texte et le local ne l'a pas."""
    manquants: list[str] = []
    with cx.cursor(name=f"cur_{col}") as cur:
        cur.itersize = LOT
        cur.execute(f"select id from listings where {col} is not null and {col} <> ''")
        while True:
            lot = cur.fetchmany(LOT)
            if not lot:
                break
            ids = [r[0] for r in lot]
            marques = ",".join("?" * len(ids))
            local = {
                r[0]: r[1] for r in loc.execute(
                    f"select id, length(coalesce({col},'')) from listings "
                    f"where id in ({marques})", ids)
            }
            # absente du local = probleme d'un autre ordre, signale mais pas traite ici
            manquants += [i for i in ids if local.get(i, 0) == 0 and i in local]
    return manquants


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ecriture = sqlite3.connect(LOCAL, timeout=60)
    ecriture.execute("pragma busy_timeout=60000")
    loc = ecriture  # meme connexion : lecture et ecriture

    total = 0
    with connecter(os.environ["SUPABASE_DB_URL"]) as cx:
        for col in ("page_text", "description"):
            ids = a_rapatrier(cx, loc, col)
            print(f"{col} : {len(ids)} annonce(s) a rapatrier")
            if not ids or args.dry_run:
                continue
            with cx.cursor() as cur:
                cur.execute(
                    f"select id, {col} from listings where id = any(%s)", (ids,))
                for lid, texte in cur.fetchall():
                    if not texte:
                        continue
                    # `page_text` est un bytea cote Postgres : psycopg rend des
                    # bytes. Mesure du 2026-08-25 : le contenu y est du TEXTE
                    # CLAIR (rien ne l'a jamais compresse sur le chemin
                    # Supabase - cf. journal du 2026-08-20). On ramene donc a
                    # une chaine avant de recompresser pour SQLite.
                    if isinstance(texte, (bytes, bytearray, memoryview)):
                        brut = bytes(texte)
                        try:
                            texte = zlib.decompress(brut).decode("utf-8")
                        except zlib.error:
                            texte = brut.decode("utf-8", "replace")
                    valeur = (zlib.compress(texte.encode("utf-8"), 6)
                              if col == "page_text" else texte)
                    # `is null or = ''` : garde-fou, on n'ecrase pas du contenu
                    ecriture.execute(
                        f"update listings set {col}=? "
                        f"where id=? and ({col} is null or {col}='')",
                        (valeur, lid))
                    total += 1
                    print(f"   <- {lid}  ({len(texte)} caracteres)")
            ecriture.commit()

    print(f"\n{total} valeur(s) rapatriee(s)" if not args.dry_run
          else "\n[dry-run] rien ecrit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
