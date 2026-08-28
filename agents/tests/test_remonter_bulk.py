"""test_remonter_bulk.py — l'upsert par lots doit produire le MÊME état que
l'upsert ligne à ligne qu'il remplace.

POURQUOI CE TEST EXISTE
`ops/remonter-local.py` transférait vers Supabase à 4,1 annonces/s (2
allers-retours Bangkok↔Singapour par annonce, réseau-bound) — mesuré le
2026-08-26. Conséquence directe : ~4h20 pour 53 258 actives, ce qui a fait
dépasser `ExecutionTimeLimit` de la tâche planifiée 3 nuits de suite
(2026-08-26 à 28, voir agents/audits/reparations-2026-08-2{7,8}.md).
`SupabaseStore.upsert_listings_bulk` remplace la boucle par un upsert par lot
(1 SELECT + 1 INSERT ON CONFLICT pour `batch_size` annonces). Un bug de
sémantique y serait invisible au run — Postgres n'objecte pas si `first_seen`
se met à jour à tort, ou si `price_history` double-compte — jusqu'à ce que les
stats d'ancienneté ou de tension du site public soient silencieusement fausses.

CE QUI EST VÉRIFIÉ, comparé explicitement au comportement de la méthode
ligne à ligne qu'il remplace (`upsert_listing`, toujours utilisée par le
scraper en ligne) :
  1. une annonce absente du serveur est INSÉRÉE (xmax=0 côté SQL) ;
  2. une annonce déjà présente est MISE À JOUR SANS toucher `first_seen` —
     exactement ce que fait la branche UPDATE de `upsert_listing` (son SET
     n'inclut pas non plus `first_seen`) ;
  3. un changement de prix ajoute une ligne à `price_history` ; un prix
     inchangé n'en ajoute aucune ;
  4. les identifiants ne se mélangent pas entre eux (chaque ligne reçoit ses
     propres valeurs, pas celles du lot).

Écrit contre le VRAI Supabase (même approche que test_stores_alignes.py — pas
de base de test séparée sur ce projet perso). Données synthétiques, préfixe
`test:bulk:` improbable en collision avec un identifiant réel (`<source>:
<deal_type>:<id-site>`, aucune source ne s'appelle "test"). Nettoyage en
`finally`, avant ET après, pour qu'un test interrompu ne laisse rien traîner.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_remonter_bulk.py
         (exige SUPABASE_DB_URL ; sans lui, NON VERIFIE — règle 2, il ne se
          tait pas)
"""
import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "scraper"))

echecs: list[str] = []


def verifie(nom: str, condition: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if condition else 'ECHEC'} {nom}{(' - ' + detail) if detail else ''}")
    if not condition:
        echecs.append(nom)


def _dsn() -> str | None:
    dsn = os.environ.get("SUPABASE_DB_URL")
    if dsn:
        return dsn
    env = RACINE / "scraper" / ".env"
    if env.exists():
        for ligne in env.read_text(encoding="utf-8").splitlines():
            if ligne.startswith("SUPABASE_DB_URL="):
                return ligne.split("=", 1)[1].strip().strip('"').strip("'")
    return None


PREFIXE = "test:bulk:"
IDS = [f"{PREFIXE}{i}" for i in range(1, 4)]


def _ligne(i: int, prix: float) -> dict:
    from store.base import COLONNES_LISTING
    l = {c: None for c in COLONNES_LISTING}
    l.update({
        "id": IDS[i], "source": "test", "source_url": "https://example.invalid",
        "title": f"Annonce de test {i}", "deal_type": "sale", "price": prix,
        "currency": "THB", "area_sqm": 50.0, "khet": "Test",
        "raw_data": {"test": True},
    })
    return l


def _nettoyer(store) -> None:
    store._execute("delete from price_history where listing_id = any(%s)", (IDS,))
    store._execute("delete from posted_at_history where listing_id = any(%s)", (IDS,))
    store._execute("delete from listing_images where listing_id = any(%s)", (IDS,))
    store._execute("delete from listings where id = any(%s)", (IDS,))


dsn = _dsn()
if not dsn:
    print("NON VERIFIE — SUPABASE_DB_URL absent (ni environnement, ni scraper/.env).")
    sys.exit(0)

from store.supabase_store import SupabaseStore  # noqa: E402

store = SupabaseStore(dsn)
try:
    _nettoyer(store)  # au cas où un run precedent aurait ete interrompu

    # --- 1. Insertion d'annonces neuves --------------------------------------
    print("Insertion (3 annonces neuves)")
    r1 = store.upsert_listings_bulk([_ligne(0, 1_000_000), _ligne(1, 2_000_000), _ligne(2, 3_000_000)])
    verifie("3 nouvelles, 0 mise a jour", r1["nouvelles"] == 3 and r1["maj"] == 0, str(r1))

    lignes = {r[0]: r for r in store._execute(
        "select id, price, first_seen, last_seen from listings where id = any(%s)", (IDS,)
    ).fetchall()}
    verifie("les 3 lignes existent", len(lignes) == 3)
    verifie("chaque ligne a SON prix (pas de melange dans le lot)",
            all(float(lignes[IDS[i]][1]) == p for i, p in enumerate([1_000_000, 2_000_000, 3_000_000])))
    verifie("first_seen == last_seen a l'insertion",
            all(lignes[i][2] == lignes[i][3] for i in IDS))

    premiers_first_seen = {i: lignes[i][2] for i in IDS}

    nb_prix = store._execute(
        "select count(*) from price_history where listing_id = any(%s)", (IDS,)
    ).fetchone()[0]
    verifie("3 lignes price_history a l'insertion (1 par annonce)", nb_prix == 3, f"{nb_prix} lignes")

    # --- 2. Mise a jour : 1 prix change, 2 inchanges -------------------------
    print("\nMise a jour (1 prix change sur 3)")
    r2 = store.upsert_listings_bulk([_ligne(0, 1_500_000), _ligne(1, 2_000_000), _ligne(2, 3_000_000)])
    verifie("0 nouvelle, 3 mises a jour, 1 changee",
            r2["nouvelles"] == 0 and r2["maj"] == 3 and r2["changees"] == 1, str(r2))

    lignes2 = {r[0]: r for r in store._execute(
        "select id, price, first_seen, last_seen from listings where id = any(%s)", (IDS,)
    ).fetchall()}
    verifie("le prix change est bien en base", float(lignes2[IDS[0]][1]) == 1_500_000)
    verifie("first_seen INCHANGE apres mise a jour (meme invariant que upsert_listing)",
            all(lignes2[i][2] == premiers_first_seen[i] for i in IDS),
            "upsert_listings_bulk ne doit JAMAIS toucher first_seen d'une ligne existante")
    verifie("last_seen avance", all(lignes2[i][3] >= premiers_first_seen[i] for i in IDS))

    nb_prix2 = store._execute(
        "select count(*) from price_history where listing_id = any(%s)", (IDS,)
    ).fetchone()[0]
    verifie("4 lignes price_history apres 1 changement (3 initiales + 1 nouvelle)",
            nb_prix2 == 4, f"{nb_prix2} lignes")

finally:
    _nettoyer(store)
    store.close()

print()
if echecs:
    print(f"ECHEC : {len(echecs)} controle(s) - {', '.join(echecs)}")
    sys.exit(1)
print("Tous les controles executes sont passes.")
