"""load_social_leads.py — charge les annonces réseaux sociaux dans social_leads.

Lit le JSON produit par scraper/social (collecte Facebook, rapatriée de
C:\agentic\agents\agent2_scraper le 2026-09-13 → extraction par une
routine Claude planifiée, modèle Haiku — pas d'Ollama, PC1 n'est pas engagé
dans ce pipeline, décision du 2026-09-12 → rapprochement avec les condos Lowi)
et l'insère dans la table
`social_leads`, VOLONTAIREMENT SÉPARÉE de `listings` : ces données sont
déclaratives et non vérifiées, elles ne doivent pas contaminer les statistiques
de marché.

Usage :
  python load_social_leads.py <fichier_resolu.json> [--sqlite]
    --sqlite : charge dans scraper/output/social-leads.db — base DÉDIÉE, séparée
               de bangkok.db (2026-09-12, décision explicite : les leads FB
               s'analysent à part, une réconciliation avec la référence reste
               un geste manuel futur, pas un flux automatique). C'est le mode
               par défaut voulu pour social_leads : pas de page publique
               dessus, donc pas de raison de payer du quota Supabase non plus
               (règle 9). Supabase reste disponible si une revue web est un
               jour voulue.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

# Appelé par l'agent social-leads avec stdout en tube : Python retombe alors sur
# cp1252 et le premier « → » plantait en UnicodeEncodeError. Mesuré : 10
# collectes (13→22/09) rejetées chaque nuit du 21 au 26/09, 0 fiche chargée.
for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

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


# Villes thaïlandaises fréquentes hors Bangkok, citées de temps en temps dans
# ces groupes (annonce d'un membre ailleurs, discussion) — rejet explicite
# plutôt qu'une absence de filtre qui laisserait tout passer par défaut.
AUTRE_VILLE = re.compile(
    r"\b(pattaya|phuket|chiang\s*mai|chiang\s*rai|hua\s*hin|koh\s*samui|koh\s*phangan|"
    r"เชียงใหม่|เชียงราย|ภูเก็ต|พัทยา|หัวหิน|สมุย)\b", re.I,
)


def collecte_solide(f: dict) -> bool:
    """2026-09-12, demande explicite : ne collecter que du condo à Bangkok,
    et seulement si assez de champs sont renseignés pour être comparable au
    marché des plateformes (adresse/condo, surface, prix OU loyer, chambres).
    Vérifié AVANT tout le reste — un condo sans ces 4 signaux n'est pas une
    fiche exploitable, juste du bruit qui gonflerait social_leads pour rien.
    """
    if f.get("type_bien") != "condo":
        return False
    texte = f"{f.get('quartier','')} {f.get('texte','')}"
    if AUTRE_VILLE.search(texte):
        return False
    a_adresse = bool((f.get("nom_immeuble") or "").strip())
    a_surface = isinstance(f.get("surface_sqm"), (int, float)) and f.get("surface_sqm", 0) > 0
    a_prix = (isinstance(f.get("prix_vente_thb"), (int, float)) and f.get("prix_vente_thb", 0) > 0) or \
             (isinstance(f.get("loyer_mensuel_thb"), (int, float)) and f.get("loyer_mensuel_thb", 0) > 0)
    a_chambres = isinstance(f.get("chambres"), (int, float)) and f.get("chambres", 0) > 0
    return a_adresse and a_surface and a_prix and a_chambres


def _row(f: dict) -> dict:
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


def motif_rejet(f: dict) -> str | None:
    """Pourquoi une fiche n'entre pas (None = elle entre). Même décision que
    collecte_solide(), détaillée champ par champ pour l'entonnoir de
    calibrage (social_calibrage.py) — demandé le 2026-09-30 : garder la
    statistique de chaque filtre pour pouvoir les affiner."""
    if not f.get("est_une_annonce"):
        return "pas_une_annonce"
    if f.get("type_bien") != "condo":
        return "pas_un_condo"
    if AUTRE_VILLE.search(f"{f.get('quartier','')} {f.get('texte','')}"):
        return "hors_bangkok"
    num = lambda k: isinstance(f.get(k), (int, float)) and f.get(k, 0) > 0
    if not (f.get("nom_immeuble") or "").strip():
        return "sans_immeuble"
    if not num("surface_sqm"):
        return "sans_surface"
    if not (num("prix_vente_thb") or num("loyer_mensuel_thb")):
        return "sans_prix"
    if not num("chambres"):
        return "sans_chambres"
    return None


def to_row(f: dict) -> dict | None:
    if not f.get("est_une_annonce"):
        return None
    if not collecte_solide(f):
        return None
    return _row(f)


COLS = list(_row({}).keys())


def charger_sqlite(rows: list[dict]) -> None:
    # LOWI_SOCIAL_DB : base de test (agents/tests/test_social_calibrage.py).
    db = Path(os.environ.get("LOWI_SOCIAL_DB") or BASE / "scraper" / "output" / "social-leads.db")
    con = sqlite3.connect(db)
    # Le SQL Postgres n'est pas exécutable tel quel en SQLite : on crée une
    # table équivalente simplifiée (mêmes colonnes, sans les contraintes).
    con.execute(
        "create table if not exists social_leads ("
        + ", ".join(f"{c} text" for c in COLS)
        + ", status text not null default 'new',"
        + " first_seen text not null default (datetime('now')),"
        + " last_seen text not null default (datetime('now')),"
        + " primary key(id))"
    )
    ph = ",".join("?" * len(COLS))
    # upsert : first_seen n'est JAMAIS réécrit (c'est la date de première
    # collecte, la donnée d'historique qu'on veut préserver) ; seul last_seen
    # avance à chaque republication vue — c'est ce qui rendra mesurable la
    # fraîcheur des annonces Facebook une fois plusieurs jours accumulés.
    maj = ", ".join(f"{c}=excluded.{c}" for c in COLS if c != "id")
    con.executemany(
        f"insert into social_leads ({','.join(COLS)}) values ({ph}) "
        f"on conflict(id) do update set {maj}, last_seen=datetime('now')",
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
    if "--sqlite" in sys.argv:
        # Dédoublonnage par caractéristiques + comparaison aux plateformes sur
        # toute la table, statistiques archivées (scraper/social_calibrage.py).
        from collections import Counter
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import social_calibrage
        motifs = Counter(motif_rejet(f) or "retenue" for f in fiches)
        s = social_calibrage.calibrer(entonnoir={"fichier": Path(args[0]).name, "fiches": len(fiches),
                                                 **dict(motifs)})
        print(f"calibrage : {s['biens_distincts']} biens distincts sur {s['lignes']} lignes "
              f"({s['taux_doublons_pct']} % de doublons), {s['exclusives']} exclusives")
