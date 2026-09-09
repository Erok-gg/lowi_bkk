"""test_supabase_reconnect.py — verrouiller la resilience de SupabaseStore a
une coupure reseau qui dure plus longtemps qu'UN essai de reconnexion.

POURQUOI CE TEST EXISTE
`SupabaseStore._execute()` reconnectait UNE fois sur `OperationalError`/
`InterfaceError` puis abandonnait. Mesure le 2026-09-03/04 : la nuit d'une
vraie coupure reseau, `remonter-local.py --synchro-statuts` a plante sur
`synchroniser_statuts` avec "failed to resolve host ... getaddrinfo failed"
— le seul essai de reconnexion est tombe pile pendant que le reseau etait
encore coupe, alors que le reste du run avait deja absorbe plusieurs
coupures identiques lot par lot (chaque lot a son propre try/except dans
`ops/remonter-local.py`, mais PAS cette derniere etape). Meme remede que
`scraper/pipeline/fetch.py` (voir test_fetch_outage.py) : sonder la
reconnexion elle-meme, a intervalle, avant d'abandonner pour de bon.

Cas 4 (2026-09-07) : `connect_timeout` de libpq ne borne PAS la resolution
DNS. Mesure en conditions reelles : `remonter-supabase` restee bloquee >4h
dans un SEUL appel `_reconnect()` sans qu'aucune ligne de log (attendue
toutes les 30s) ne sorte — le decompte de `_execute()` ne peut avancer que
si l'appel bloquant lui-meme est borne de l'exterieur. `_connect_borne()`
(watchdog thread, pas signal.alarm — indisponible sur Windows) fait ce
travail ; le cas 4 verifie qu'un `connect()` qui ne revient jamais est
neanmoins abandonne au bout de `CONNECT_HARD_TIMEOUT`.

Ce test ne touche a AUCUN reseau ni base reelle — `psycopg.connect` est
remplace par un faux objet controle par le test.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_supabase_reconnect.py
"""
import os
import sys

# CE TEST NE POUVAIT PAS PASSER, et personne ne le savait (constaté le
# 2026-09-09, vérifié en le rejouant sur la version d'avant les correctifs du
# jour) : `supabase_store._execute()` journalise ses reprises avec « ⚠ », le
# test le déclenche exprès, et la console de ce poste est en cp1252 — il
# mourait donc en UnicodeEncodeError AVANT d'atteindre la moindre assertion.
# Un test qui plante toujours n'est pas un test, c'est une alerte qu'on apprend
# à ignorer (règle 2).
# La PRODUCTION, elle, n'est pas concernée : les agents sont lancés en
# sous-processus par agents/core/shell.py, qui force l'UTF-8 — les « ⚠ » sont
# bien présents dans agents/logs/remonter-supabase-*.log. C'est le lancement
# DIRECT qui manquait de ce réglage, exactement comme ops/pouls.py et
# ops/fraicheur.py le font pour eux-mêmes.
for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "scraper"))

import psycopg                                            # noqa: E402
from store import supabase_store as ss                    # noqa: E402

# Plafond tres bas pour que le test reste rapide (le code de prod utilise 20 min).
ss.OUTAGE_POLL_SECONDS = 0.05
ss.OUTAGE_MAX_WAIT_SECONDS = 0.3


class _FauxCurseur:
    def fetchone(self):
        return None


class _FausseConnexion:
    """`compte["echecs_restants"]` execute() qui levent OperationalError avant
    de reussir — simule le reseau qui revient apres N tentatives."""
    def __init__(self, compte):
        self._compte = compte

    def execute(self, sql, params=()):
        if self._compte["echecs_restants"] > 0:
            self._compte["echecs_restants"] -= 1
            raise psycopg.OperationalError("simulated: connection is closed")
        return _FauxCurseur()

    def close(self):
        pass


def _store_sans_vraie_connexion(compte) -> ss.SupabaseStore:
    """Construit un SupabaseStore sans passer par __init__ (qui ouvrirait une
    vraie connexion) : on pose directement `.db`/`.dsn`."""
    store = object.__new__(ss.SupabaseStore)
    store.dsn = "postgresql://test/fake"
    store.db = _FausseConnexion(compte)
    return store


# --------------------------------- 1. coupure resolue AVANT le plafond -> succes, pas d'exception
# La 1ere execute() echoue (connexion cassee), le reconnect POSE une nouvelle
# _FausseConnexion... mais _reconnect() appelle psycopg.connect (vrai module) —
# on le monkeypatch pour qu'il rende une connexion qui reussit desormais.
compte = {"echecs_restants": 1}
store = _store_sans_vraie_connexion(compte)


def _connect_qui_reussit(dsn, **kw):
    return _FausseConnexion({"echecs_restants": 0})


psycopg.connect = _connect_qui_reussit
r = store._execute("select 1")
assert r.fetchone() is None, "attendu un curseur exploitable apres reconnexion"
print("coupure resolue au 1er reconnect : succes, OK")

# --------------------------------- 2. coupure qui dure plusieurs sondes puis se resout -> succes
appels = {"n": 0}


def _connect_qui_echoue_puis_reussit(dsn, **kw):
    appels["n"] += 1
    if appels["n"] < 3:
        raise psycopg.OperationalError("simulated: failed to resolve host")
    return _FausseConnexion({"echecs_restants": 0})


compte2 = {"echecs_restants": 1}
store2 = _store_sans_vraie_connexion(compte2)
psycopg.connect = _connect_qui_echoue_puis_reussit
r2 = store2._execute("select 1")
assert r2.fetchone() is None
assert appels["n"] == 3, f"attendu 3 tentatives de reconnexion avant succes, recu {appels['n']}"
print(f"coupure qui dure {appels['n']} sondes puis se resout : succes, OK "
      f"(reproduit le cas reel du 2026-09-03/04 — 1 seul essai aurait echoue)")

# --------------------------------- 3. coupure persistante au-dela du plafond -> leve, pas de boucle infinie
def _connect_qui_echoue_toujours(dsn, **kw):
    raise psycopg.OperationalError("simulated: getaddrinfo failed")


compte3 = {"echecs_restants": 1}
store3 = _store_sans_vraie_connexion(compte3)
psycopg.connect = _connect_qui_echoue_toujours
try:
    store3._execute("select 1")
    raise SystemExit("attendu une exception apres le plafond d'attente, rien n'a ete leve")
except psycopg.OperationalError:
    print("coupure persistante au-dela du plafond : exception propagee (pas de boucle infinie), OK")

# --------------------------------- 4. connect() qui ne revient JAMAIS -> abandonne au hard-timeout, pas un hang
import time as _time                                       # noqa: E402

ss.CONNECT_HARD_TIMEOUT = 0.2  # plafond tres bas, le code de prod utilise 25s


def _connect_qui_bloque_indefiniment(dsn, **kw):
    _time.sleep(30)  # bien plus long que le hard-timeout : ne doit JAMAIS etre attendu
    return _FausseConnexion({"echecs_restants": 0})


psycopg.connect = _connect_qui_bloque_indefiniment
_debut = _time.monotonic()
try:
    ss._connect_borne("postgresql://test/fake")
    raise SystemExit("attendu OperationalError sur connect() qui ne revient jamais")
except psycopg.OperationalError:
    _duree = _time.monotonic() - _debut
    assert _duree < 5.0, (
        f"_connect_borne a attendu {_duree:.1f}s — le hard-timeout ({ss.CONNECT_HARD_TIMEOUT}s) "
        "n'a pas borne l'appel bloquant, exactement le defaut du 2026-09-07"
    )
    print(f"connect() bloque indefiniment : abandonne en {_duree:.2f}s "
          f"(hard-timeout {ss.CONNECT_HARD_TIMEOUT}s), pas de hang, OK")

print("test_supabase_reconnect : OK")
