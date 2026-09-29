"""test_dirty_since.py — la file d'attente locale du delta Supabase
(`dirty_since`) doit se poser et s'effacer exactement quand il faut, ni plus
ni moins.

POURQUOI CE TEST EXISTE
Mesuré en direct le 2026-09-07 : `remonter-supabase` réévaluait chaque jour
TOUTE la fenêtre active (81 889 annonces, 33 lots) pour laisser Postgres
décider ce qui avait changé — 33 fenêtres d'exposition à une coupure réseau
par jour, cause plausible du blocage `ECIRCUITBREAKER` (« too many
authentication failures ») qui a immobilisé le process ce soir-là.
L'utilisateur, en observant l'incident, a demandé : "only update what's new
and remove what's not updated anymore [...] there is a cycle for that". Le
calcul du delta est déplacé côté local (`SqliteStore.upsert_listing`,
`mark_missing_inactive`, `appliquer_ventes`, `touch_listing`) — gratuit, déjà
fait à l'écriture — au lieu d'un aller-retour réseau par lot pour le
redécouvrir chaque jour.

CE QUI EST VÉRIFIÉ, sans AUCUN réseau (SQLite local en fichier temporaire) :
  1. une annonce NOUVELLE est marquée `dirty_since` (à remonter) ;
  2. revue SANS AUCUN changement (prix, statut, tout identique) : `dirty_since`
     N'EST PAS modifié — ni remis à zéro s'il était déjà à `null` (déjà
     synchronisée), ni rafraîchi à `now()` s'il datait d'avant ;
  3. un changement de PRIX marque `dirty_since` même si la ligne était déjà
     synchronisée (`dirty_since` effacé au préalable, comme après un
     `remonter-local.py --delta` réussi) ;
  4. le délistage par délai de grâce (`mark_missing_inactive`) marque
     `dirty_since` — c'est un changement de statut à propager, pas seulement
     de contenu ;
  5. une résurrection (`touch_listing` sur une ligne inactive) marque
     `dirty_since` ; le même appel sur une ligne DÉJÀ active ne le touche pas ;
  6. `ops/remonter-local.py::charger(..., delta=True)` et `statuts_morts(...,
     delta=True)` ne renvoient QUE les lignes marquées — vérifié en
     n'important que ces deux fonctions (aucune dépendance Supabase) ;
  7. `marquer_synchronise()` efface bien `dirty_since` pour les ids donnés,
     et seulement ceux-là.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_dirty_since.py
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scraper"))
sys.path.insert(0, os.path.join(ROOT, "ops"))

from store.sqlite_store import SqliteStore  # noqa: E402

tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
tmp.close()
db_path = Path(tmp.name)

try:
    store = SqliteStore(db_path)

    def _norm(id_, price, **extra):
        n = {"id": id_, "source": "test", "source_url": "https://test/x",
             "deal_type": "sale", "price": price}
        n.update(extra)
        return n

    def _dirty(listing_id: str):
        row = store.db.execute(
            "select dirty_since from listings where id=?", (listing_id,)
        ).fetchone()
        return row["dirty_since"]

    # --------------------------------- 1. nouvelle annonce -> dirty_since pose
    statut, _ = store.upsert_listing(_norm("t1", 1_000_000), None)
    assert statut == "new"
    d1 = _dirty("t1")
    assert d1 is not None, "une annonce neuve doit etre marquee a remonter"
    print("1. nouvelle annonce : dirty_since pose, OK")

    # --------------------------------- 2. revue sans changement -> dirty_since INTACT
    statut, _ = store.upsert_listing(_norm("t1", 1_000_000), None)
    assert statut == "unchanged"
    assert _dirty("t1") == d1, "rien n'a change : dirty_since ne doit pas bouger"
    print("2. revue identique : dirty_since inchange, OK")

    # Simule une remontee reussie (ce que fait marquer_synchronise() cote ops/)
    store.db.execute("update listings set dirty_since=null where id='t1'")
    store.db.commit()
    assert _dirty("t1") is None

    # --------------------------------- 2bis. revue identique APRES synchro -> reste a null
    statut, _ = store.upsert_listing(_norm("t1", 1_000_000), None)
    assert statut == "unchanged"
    assert _dirty("t1") is None, (
        "une ligne deja synchronisee et revue SANS changement ne doit pas "
        "redevenir 'a remonter' — sinon --delta ne converge jamais"
    )
    print("2bis. revue identique apres synchro : reste synchronisee, OK")

    # --------------------------------- 3. changement de prix -> dirty_since repose
    statut, _ = store.upsert_listing(_norm("t1", 1_200_000), None)
    assert statut == "changed"
    assert _dirty("t1") is not None, "un changement de prix doit re-marquer la ligne"
    print("3. changement de prix : dirty_since repose, OK")

    store.db.execute("update listings set dirty_since=null where id='t1'")
    store.db.commit()

    # --------------------------------- 4. delistage par delai de grace -> dirty_since pose
    store.mark_missing_inactive("test", seen_ids=set(), grace=0)
    row = store.db.execute("select status, dirty_since from listings where id='t1'").fetchone()
    assert row["status"] == "inactive"
    assert row["dirty_since"] is not None, "un delistage doit etre propage (dirty_since)"
    print("4. delistage (delai de grace = 0) : dirty_since pose, OK")

    store.db.execute("update listings set dirty_since=null where id='t1'")
    store.db.commit()

    # --------------------------------- 5. resurrection -> dirty_since pose ; touch sur active -> intact
    store.touch_listing("t1")
    row = store.db.execute("select status, dirty_since from listings where id='t1'").fetchone()
    assert row["status"] == "active"
    assert row["dirty_since"] is not None, "une resurrection doit etre propagee"
    print("5a. resurrection (touch sur ligne inactive) : dirty_since pose, OK")

    store.db.execute("update listings set dirty_since=null where id='t1'")
    store.db.commit()
    store.touch_listing("t1")  # deja active : simple "revu"
    assert _dirty("t1") is None, "toucher une ligne DEJA active ne doit rien re-marquer"
    print("5b. touch sur ligne deja active : dirty_since intact, OK")

    # --------------------------------- 6. charger()/statuts_morts() en mode --delta
    from importlib import import_module
    remonter = import_module("remonter-local".replace("-", "_")) if False else None
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "remonter_local", os.path.join(ROOT, "ops", "remonter-local.py"))
    remonter_local = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(remonter_local)

    # t2 : nouvelle annonce active, jamais synchronisee -> doit apparaitre en delta
    store.upsert_listing(_norm("t2", 500_000), None)
    # t1 est active mais dirty_since=null (synchronisee au 5b) -> absente du delta
    lignes = remonter_local.charger(str(db_path), statut="actives", delta=True)
    ids = {l["id"] for l in lignes}
    assert "t2" in ids and "t1" not in ids, (
        f"delta attendu = {{'t2'}} uniquement, recu {ids}"
    )
    print("6a. charger(delta=True) : ne renvoie que les lignes non synchronisees, OK")

    # t3 : delistee et jamais propagee -> doit apparaitre dans statuts_morts(delta=True)
    store.upsert_listing(_norm("t3", 700_000), None)
    store.mark_missing_inactive("test", seen_ids={"t2"}, grace=0)  # delaisse t1(deja inactive)+t3
    morts = remonter_local.statuts_morts(str(db_path), delta=True)
    morts_ids = {m[0] for m in morts}
    assert "t3" in morts_ids, f"t3 vient d'etre delistee et jamais propagee, attendue dans {morts_ids}"
    print("6b. statuts_morts(delta=True) : renvoie les delistages non propages, OK")

    # --------------------------------- 7. marquer_synchronise() efface UNIQUEMENT les ids donnes
    remonter_local.marquer_synchronise(str(db_path), ["t2"])
    store2 = SqliteStore(db_path)  # reouvre pour lire l'ecriture faite par une AUTRE connexion
    assert store2.db.execute(
        "select dirty_since from listings where id='t2'"
    ).fetchone()["dirty_since"] is None, "t2 aurait du etre marquee synchronisee"
    assert store2.db.execute(
        "select dirty_since from listings where id='t3'"
    ).fetchone()["dirty_since"] is not None, "t3 ne devait PAS etre touchee"
    print("7. marquer_synchronise() : efface exactement les ids demandes, OK")

    print("\ntest_dirty_since : OK")
finally:
    try:
        os.unlink(db_path)
        for ext in ("-wal", "-shm"):
            p = str(db_path) + ext
            if os.path.exists(p):
                os.unlink(p)
    except OSError:
        pass
