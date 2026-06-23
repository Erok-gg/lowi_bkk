"""backfill_nestopa_names.py — Renomme les condos Nestopa à partir du titre.

Nestopa ne fournit pas de nom de projet propre (fiches détail bloquées par
Cloudflare). Le titre le contient pourtant ("... at Belgravia", "3 Bed/3 Bath
Fynn Sukhumvit 31"). On nettoie ce titre (clean_condo_name) puis on **snap** au
dictionnaire des condos connus des autres sources quand un nom connu y figure.
Ensuite, relancer `backfill_geocode.py` pour localiser les noms améliorés.

Usage : .venv/Scripts/python.exe backfill_nestopa_names.py [--dry]
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from adapters.nestopa import clean_condo_name  # noqa: E402

ROOT = Path(__file__).resolve().parent


def load_env() -> None:
    env = ROOT / ".env"
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", s.lower())).strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="n'écrit rien, affiche seulement")
    args = ap.parse_args()

    load_env()
    db = psycopg.connect(os.environ["SUPABASE_DB_URL"], connect_timeout=20, autocommit=True)

    # dictionnaire de condos propres (autres sources)
    known = db.execute(
        "select distinct split_part(condo_name,',',1) from listings "
        "where source<>'nestopa' and condo_name is not null"
    ).fetchall()
    known_norm = {_norm(k[0]): k[0].strip() for k in known if k[0] and len(k[0].strip()) >= 4}

    def snap(cand: str) -> str:
        """Snap UNIQUEMENT si un nom de condo connu complet (≥6 car.) est
        contenu dans le candidat (mot entier) → évite area→condo (Asoke→Asoke Tower)."""
        nc = _norm(cand)
        best = None
        for kn, orig in known_norm.items():
            if len(kn) >= 6 and re.search(rf"\b{re.escape(kn)}\b", nc):
                if best is None or len(kn) > len(_norm(best)):
                    best = orig
        return best or cand

    # on dérive depuis `title` (conserve l'original ; condo_name a pu être réécrit)
    rows = db.execute(
        "select id, title, condo_name from listings where source='nestopa' and title is not null"
    ).fetchall()

    n_renamed = n_snap = 0
    for lid, title, cur in rows:
        cleaned = clean_condo_name(title)
        if not cleaned:
            continue
        final = snap(cleaned)
        if _norm(final) != _norm(cur) and final != cleaned:
            n_snap += 1
        if final != cur:
            n_renamed += 1
            if not args.dry:
                # nouveau nom + on réinitialise street pour re-géocoder proprement
                db.execute(
                    "update listings set condo_name=%s, street=null where id=%s", (final, lid)
                )

    print(f"{len(rows)} Nestopa | renommés {n_renamed} | snappés condo connu {n_snap}"
          + (" (DRY)" if args.dry else ""))


if __name__ == "__main__":
    main()
