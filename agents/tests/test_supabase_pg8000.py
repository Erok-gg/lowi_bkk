"""test_supabase_pg8000.py — le chemin d'écriture vers Supabase ne dépend plus d'une DLL.

POURQUOI CE TEST EXISTE
Nuit du 2026-10-09 : `remonter-supabase` (#752) meurt en 9 s sur
« no pq wrapper available ». Smart App Control a bloqué la libpq de
`psycopg_binary` (CodeIntegrity 3077 à l'instant du run, 5 processus neufs sur
5). Le jugement porte sur la RÉPUTATION du fichier et peut basculer sans
préavis (l'import repassait le même jour à 13 h). Le site public a pris
2 jours de retard (3 428 actives absentes). Correctif choisi par l'utilisateur :
pilote Python pur `pg8000`, sans DLL native.

Ce que ce test vérifie :
  1. `store.supabase_store` s'importe et ouvre sa connexion avec `psycopg`
     rendu INTROUVABLE (même simulation que test_study_sans_psycopg.py :
     le test dit la même chose quel que soit l'état de Smart App Control) ;
  2. le tri coupure / erreur déterministe reproduit celui de psycopg
     (`OperationalError` → on rejoue ; syntaxe, contrainte, limite → on lève
     tout de suite, rejouer 20 min ne changerait rien) ;
  3. `_execute` ne rejoue PAS une erreur déterministe, et rejoue un
     `statement timeout` (57014, rangé par psycopg dans OperationalError) ;
  4. le DSN est bien décodé (mot de passe encodé en URL, base, port, SSL).

  5. (réseau, si LOWI_TEST_RESEAU=1) connexion réelle au pooler, psycopg
     bloqué, et lecture du compte d'actives — sans écrire.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_supabase_pg8000.py
"""
import importlib
import os
import sys

for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RACINE, "scraper"))

from pg8000.exceptions import DatabaseError, InterfaceError   # noqa: E402


class _BloquePsycopg:
    """Rend `import psycopg` impossible, quoi qu'il y ait sur la machine."""

    def find_spec(self, nom, chemin=None, cible=None):
        if nom == "psycopg" or nom.startswith("psycopg"):
            raise ImportError("simulé : no pq wrapper available (Smart App Control)")
        return None


for nom in [k for k in sys.modules if k.startswith("psycopg") or k == "store.supabase_store"]:
    del sys.modules[nom]
sys.meta_path.insert(0, _BloquePsycopg())
try:
    import psycopg  # noqa: F401
    raise SystemExit("le blocage simulé n'est pas effectif (psycopg importable)")
except ImportError:
    pass

# ───────── 1. le store s'importe sans psycopg
ss = importlib.import_module("store.supabase_store")
assert "psycopg" not in sys.modules, "supabase_store ne doit plus importer psycopg"
print("1. supabase_store s'importe avec psycopg introuvable : OK")


def err(code):
    return DatabaseError({"S": "ERROR", "C": code, "M": f"simulé {code}"})


# ───────── 2. tri coupure / erreur déterministe
for exc in (InterfaceError("network error"), OSError("WinError 10054"),
            err("08006"), err("57014"), err("57P01"), err("53300")):
    assert ss._est_coupure(exc), f"doit être traité comme une coupure : {exc!r}"
for exc in (err("42601"), err("23505"), err("54000"), err("22012"),
            ValueError("bug de code")):
    assert not ss._est_coupure(exc), f"ne doit PAS être rejoué : {exc!r}"
print("2. tri coupure / erreur déterministe : OK")

# ───────── 3. _execute : déterministe levée tout de suite, timeout rejoué
ss.OUTAGE_POLL_SECONDS = 0.01
ss.OUTAGE_POLL_MAX = 0.02
ss.OUTAGE_MAX_WAIT_SECONDS = 0.2
ouvertures = {"n": 0}


class _Curseur:
    def fetchone(self):
        return [1]


class _Faux:
    def __init__(self, erreurs):
        self.erreurs = list(erreurs)

    def execute(self, sql, params=()):
        if self.erreurs:
            raise self.erreurs.pop(0)
        return _Curseur()

    def close(self):
        pass


def _ouvre(dsn):
    ouvertures["n"] += 1
    return _Faux([])


ss._ouvre = _ouvre
store = object.__new__(ss.SupabaseStore)
store.dsn = "postgresql://u:p@h/db"

store.db = _Faux([err("42601")])
try:
    store._execute("selec 1")
    raise SystemExit("une erreur de syntaxe doit lever")
except DatabaseError:
    pass
assert ouvertures["n"] == 0, "une erreur déterministe ne doit déclencher AUCUNE reconnexion"

store.db = _Faux([err("57014")])
assert store._execute("select 1").fetchone() == [1]
assert ouvertures["n"] == 1, "un statement timeout doit être rejoué après reconnexion"
print("3. _execute : syntaxe levée sans reconnexion, timeout rejoué : OK")

# ───────── 4. DSN
p = ss._parametres("postgresql://postgres.abc:p%40ss%2Fw@pooler.example:6543/postgres")
assert (p["user"], p["password"], p["host"], p["port"], p["database"]) == \
    ("postgres.abc", "p@ss/w", "pooler.example", 6543, "postgres"), p
assert ss._parametres("postgresql://u:p@h/x")["port"] == 5432
import ssl                                                    # noqa: E402
assert p["ssl_context"].verify_mode == ssl.CERT_NONE and not p["ssl_context"].check_hostname
assert p["timeout"] == ss.SOCKET_TIMEOUT
print("4. DSN décodé (mot de passe encodé, port, SSL comme libpq « prefer ») : OK")

# ───────── 5. réseau réel, en lecture seule
if os.environ.get("LOWI_TEST_RESEAU") == "1":
    importlib.reload(ss)                       # vrai pilote, vrais délais
    dsn = None
    for ligne in open(os.path.join(RACINE, "scraper", ".env"), encoding="utf-8"):
        if ligne.startswith("SUPABASE_DB_URL="):
            dsn = ligne.split("=", 1)[1].strip().strip('"')
    vrai = object.__new__(ss.SupabaseStore)
    vrai.dsn, vrai.db = dsn, ss._connect_resilient(dsn)
    actives = vrai._execute("select count(*) from listings where status='active'").fetchone()[0]
    vrai.close()
    assert actives > 0
    assert "psycopg" not in sys.modules
    print(f"5. pooler réel, psycopg bloqué : connexion et lecture OK ({actives} actives)")
else:
    print("5. (réseau sauté — LOWI_TEST_RESEAU=1 pour l'exécuter)")

print("\nOK — test_supabase_pg8000")
