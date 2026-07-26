"""load_social_leads.py — charge les annonces réseaux sociaux dans social_leads.

Lit le JSON produit par agent2_scraper (collecte Facebook → extraction par le
modèle local → rapprochement avec les condos Lowi) et l'insère dans la table
`social_leads`, VOLONTAIREMENT SÉPARÉE de `listings` : ces données sont
déclaratives et non vérifiées, elles ne doivent pas contaminer les statistiques
de marché.

Usage :
  python load_social_leads.py <fichier_resolu.json> [--sqlite]
    --sqlite : charge dans archive/lowi-archive.db au lieu de Supabase
               (utile pour tester sans toucher au serveur)
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
MIGRATION = BASE / "supabase" / "migrations" / "social_leads.sql"

# Le JSON vient du pipeline français ; la table suit les conventions anglaises
# de Lowi (deal_type sale/rent…). Traduction explicite plutôt qu'implicite.
DEAL = {"vente": "sale", "location": "rent", "vente_et_location": "sale_and_rent",
        "recherche": "wanted", "autre": "other"}
PROP = {"condo": "condo", "maison": "house", "townhouse": "townhouse",
        "terrain": "land", "commerce": "commercial", "inconnu": "unknown"}
SELLER = {"proprietaire": "owner", "agent": "agent", "inconnu": "unknown"}
QUOTA = {"etranger": "foreigner", "thai": "thai", "inconnu": "unknown"}


def lead_id(f: dict) -> str:
    """Identifiant stable : même annonce republiée = même id (déduplication).

    On hache le contenu normalisé plutôt que l'URL : sur Facebook la même
    annonce repostée reçoit une URL différente, mais son texte ne bouge pas.
    """
    cle = f"{f.get('nom_immeuble','')}|{f.get('prix_vente_thb',0)}|{f.get('loyer_mensuel_thb',0)}|{(f.get('texte') or '')[:200]}"
    h = hashlib.sha1(cle.encode("utf-8")).hexdigest()[:16]
    return f"facebook:{f.get('groupe','?')}:{h}"


def to_row(f: dict) -> dict | None:
    if not f.get("est_une_annonce"):
        return None
    num = lambda v: v if isinstance(v, (int, float)) and v > 0 else None
    return {
        "id": lead_id(f),
        "source": "facebook",
        "source_group": str(f.get("groupe") or ""),
        "source_url": f.get("lien"),
        "posted_at": f.get("date"),
        "author": (f.get("auteur") or "")[:120],
        "deal_type": DEAL.get(f.get("type_transaction"), "other"),
        "property_type": PROP.get(f.get("type_bien"), "unknown"),
        "price": num(f.get("prix_vente_thb")),
        "rent_monthly": num(f.get("loyer_mensuel_thb")),
        "area_sqm": num(f.get("surface_sqm")),
        "bedrooms": num(f.get("chambres")),
        "bathrooms": num(f.get("salles_de_bain")),
        "condo_name_raw": f.get("nom_immeuble") or None,
        "station": f.get("station_proche") or None,
        "district_raw": f.get("quartier") or None,
        "furnished": f.get("meuble"),
        "seller_type": SELLER.get(f.get("vendeur"), "unknown"),
        "quota": QUOTA.get(f.get("quota"), "unknown"),
        "condo_name": f.get("condo_lowi"),
        "match_score": f.get("condo_score"),
        "khet": f.get("condo_khet"),
        "lat": f.get("condo_lat"),
        "lng": f.get("condo_lng"),
        "median_rent_condo": f.get("condo_med_loyer"),
        "median_sale_condo": f.get("condo_med_vente"),
        "deviation_pct": f.get("ecart_loyer_pct") if f.get("ecart_loyer_pct") is not None else f.get("ecart_vente_pct"),
        "confidence": f.get("confiance"),
        "raw_text": (f.get("texte") or "")[:4000],
    }


COLS = list(to_row({"est_une_annonce": True}).keys())


def charger_sqlite(rows: list[dict]) -> None:
    db = BASE / "archive" / "lowi-archive.db"
    con = sqlite3.connect(db)
    # Le SQL Postgres n'est pas exécutable tel quel en SQLite : on crée une
    # table équivalente simplifiée (mêmes colonnes, sans les contraintes).
    con.execute(
        "create table if not exists social_leads ("
        + ", ".join(f"{c} text" for c in COLS)
        + ", status text default 'new', first_seen text, last_seen text, primary key(id))"
    )
    ph = ",".join("?" * len(COLS))
    con.executemany(
        f"insert or replace into social_leads ({','.join(COLS)}) values ({ph})",
        [tuple(str(r[c]) if r[c] is not None else None for c in COLS) for r in rows],
    )
    con.commit()
    print(f"{len(rows)} pistes → {db}")


def charger_supabase(rows: list[dict]) -> None:
    import psycopg  # dans le venv du scraper

    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        env = BASE / "scraper" / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.startswith("SUPABASE_DB_URL="):
                    url = line.split("=", 1)[1].strip().strip('"')
    if not url:
        sys.exit("SUPABASE_DB_URL introuvable (scraper/.env)")

    with psycopg.connect(url) as con, con.cursor() as cur:
        cur.execute(MIGRATION.read_text(encoding="utf-8"))  # idempotent
        maj = ", ".join(f"{c}=excluded.{c}" for c in COLS if c != "id")
        cur.executemany(
            f"insert into social_leads ({','.join(COLS)}) values ({','.join('%(' + c + ')s' for c in COLS)})"
            f" on conflict (id) do update set {maj}, last_seen=now()",
            rows,
        )
        con.commit()
    print(f"{len(rows)} pistes → Supabase social_leads")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    fiches = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    rows = [r for r in (to_row(f) for f in fiches) if r]
    # Déduplication sur l'id (même annonce republiée)
    uniq = {r["id"]: r for r in rows}
    print(f"{len(fiches)} fiches → {len(rows)} annonces → {len(uniq)} uniques "
          f"({len(rows) - len(uniq)} doublons écartés)")
    prop = sum(1 for r in uniq.values() if r["seller_type"] == "owner")
    quo = sum(1 for r in uniq.values() if r["quota"] == "foreigner")
    print(f"  dont propriétaire direct : {prop} | quota étranger explicite : {quo}")
    (charger_sqlite if "--sqlite" in sys.argv else charger_supabase)(list(uniq.values()))
