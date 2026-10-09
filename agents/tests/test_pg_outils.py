"""test_pg_outils.py — les outils manuels Supabase ne dépendent plus d'une DLL.

POURQUOI CE TEST EXISTE
Le 2026-10-09, Smart App Control a bloqué la libpq de `psycopg_binary`. Le
chemin d'écriture est passé à pg8000 le matin (test_supabase_pg8000.py) ; les
outils manuels l'ont suivi l'après-midi, via `scraper/store/pg.py` :
`ops/verifie-synchro.py`, `ops/sync_supabase_local.py`, `agents/core/db.py`
(LOWI_STORE=supabase). Parité mesurée contre psycopg sur le vrai serveur
(journal technique du jour).

Ce que ce test vérifie, sans réseau :
  1. les trois outils ne citent plus psycopg dans leur code (hors commentaires),
     et `agents.core.db` s'importe avec psycopg rendu INTROUVABLE ;
  2. le curseur rend des TUPLES (pg8000 rend des listes, non hachables) ;
  3. `%%` est traité comme psycopg quand `params` vaut `()` ;
  4. `with connecter(...)` valide si tout va bien, annule sinon, ferme toujours.
  5. (réseau, si LOWI_TEST_RESEAU=1) `db.query` contre le vrai serveur, psycopg
     bloqué.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_pg_outils.py
"""
import os
import sys

for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, "scraper"))


class _BloquePsycopg:
    def find_spec(self, nom, chemin=None, cible=None):
        if nom == "psycopg" or nom.startswith("psycopg"):
            raise ImportError("simulé : no pq wrapper available (Smart App Control)")
        return None


for nom in [k for k in sys.modules if k.startswith("psycopg")]:
    del sys.modules[nom]
sys.meta_path.insert(0, _BloquePsycopg())

# ───────── 1. plus de psycopg dans les outils
for rel in ("ops/verifie-synchro.py", "ops/sync_supabase_local.py", "agents/core/db.py"):
    code = open(os.path.join(RACINE, rel), encoding="utf-8").read().splitlines()
    actifs = [l for l in code if "psycopg" in l and not l.lstrip().startswith("#")]
    assert not actifs, f"{rel} cite encore psycopg : {actifs}"
from store import pg                                          # noqa: E402
from agents.core import db                                    # noqa: E402
assert "psycopg" not in sys.modules
print("1. outils sans psycopg, store.pg et agents.core.db importables sans lui : OK")


class _CurseurBrut:
    def __init__(self):
        self.vu = None
        self.description = (("a", 25, None, None, None, None, None),)
        self.rowcount = 2

    def execute(self, sql, params=()):
        self.vu = (sql, params)

    def fetchone(self):
        return [1, "x"]

    def fetchall(self):
        return [[1, "x"], [2, "y"]]

    def fetchmany(self, n=None):
        return [[3, "z"]]

    def __iter__(self):
        return iter([[4, "w"]])

    def close(self):
        pass


class _ConnexionBrute:
    def __init__(self):
        self.autocommit = None
        self.journal = []
        self.dernier = None

    def cursor(self):
        self.dernier = _CurseurBrut()
        return self.dernier

    def commit(self):
        self.journal.append("commit")

    def rollback(self):
        self.journal.append("rollback")

    def close(self):
        self.journal.append("close")


# ───────── 2. tuples
cx = pg.Connexion(_ConnexionBrute())
cur = cx.execute("select 1", ())
assert cur.fetchone() == (1, "x")
assert cur.fetchall() == [(1, "x"), (2, "y")]
assert cur.fetchmany(5000) == [(3, "z")]
assert list(cur) == [(4, "w")]
assert {r for r in cur.fetchall()}, "une ligne doit pouvoir servir de clé de set"
assert cur.description[0][0] == "a" and cur.rowcount == 2
print("2. curseur : tuples, description, rowcount : OK")

# ───────── 3. %% comme psycopg
cx.execute("select 'a%%'", ())
assert cx.brute.dernier.vu == ("select 'a%'", ()), cx.brute.dernier.vu
cx.execute("select 'a%%'")                      # params=None : rien n'est interprété
assert cx.brute.dernier.vu == ("select 'a%%'", ())
cx.execute("select %s, 'a%%'", (1,))           # avec paramètres : pg8000 s'en charge
assert cx.brute.dernier.vu == ("select %s, 'a%%'", (1,))
print("3. substitution de % alignée sur psycopg : OK")

# ───────── 4. with = commit / rollback / close
brute = _ConnexionBrute()
with pg.Connexion(brute):
    pass
assert brute.journal == ["commit", "close"], brute.journal
brute = _ConnexionBrute()
try:
    with pg.Connexion(brute):
        raise RuntimeError("échec dans le bloc")
except RuntimeError:
    pass
assert brute.journal == ["rollback", "close"], brute.journal
brute = _ConnexionBrute()
with pg.Connexion(brute, autocommit=True):
    pass
assert brute.journal == ["close"] and brute.autocommit is True
print("4. with : commit si succès, rollback si erreur, fermeture toujours : OK")

# ───────── 5. réseau réel
if os.environ.get("LOWI_TEST_RESEAU") == "1":
    os.environ["LOWI_STORE"] = "supabase"
    n = db.scalar("select count(*) from listings where status=%s", ("active",))
    lignes = db.query("select source, count(*) as n from listings where status='active' "
                      "group by source order by n desc")
    assert n > 0 and lignes and "psycopg" not in sys.modules
    print(f"5. db.query/scalar sur le vrai serveur, psycopg bloqué : {n} actives, "
          f"{len(lignes)} sources : OK")
else:
    print("5. (réseau sauté — LOWI_TEST_RESEAU=1 pour l'exécuter)")

print("\nOK — test_pg_outils")
