"""test_supabase_cause_reelle.py — ne pas détruire la vraie cause, ne pas fuir de connexion.

POURQUOI CE TEST EXISTE
Cycle du 2026-10-06 : `remonter-supabase` a tourné 8 h 28 (06:11 → 14:39 UTC),
traité 5 500 des 113 978 annonces, puis abandonné. Ses ~60 lignes de log
annonçaient toutes la même chose :

    ⚠ connexion Postgres perdue (coupure ?) — nouvel essai dans 34s
    [erreur lot 0-500] OperationalError connect() bloqué au-delà de 25s
    (hors du contrôle de connect_timeout — DNS ou TCP) — abandon

Les deux causes nommées étaient FAUSSES, et vérifiables en trois minutes :
le DNS résolvait (3 A records), le TCP passait (`TcpTestSucceeded=True` en
8,4 s). En rejouant `psycopg.connect` à la main, la vraie erreur est arrivée
en 32,0 / 32,1 / 32,9 s — soit APRÈS le watchdog de 25 s, qui la détruisait :

    FATAL: Failed to connect to database:
           authentication did not complete within 15000ms

C'est le pooler qui n'arrive pas à s'authentifier auprès du Postgres, lui-même
saturé en I/O (`postgres_logs` du jour : checkpoint d'UN buffer = 17 à 22 s,
250 buffers = 147 s, `pg_database_size('template1')` = 23 s). Rien à voir avec
le réseau — et c'est bien pour cela que les commentaires de `supabase_store.py`
parlent de DNS depuis un mois : le garde-fou mentait, l'enquête suivait.

Second défaut trouvé en lisant ce chemin : le thread orphelin pouvait tenir une
connexion ouverte que personne ne fermait (`resultat["db"]` atterri après la
deadline). En mode SESSION chacune occupe un backend du pooler, et
`supavisor_logs` montrait justement « (ECHECKOUTTIMEOUT) unable to check out
connection from the pool after 15000ms in Session mode ». On aggravait la panne
qu'on réessayait.

CE QUE CE TEST VERROUILLE — et ce qu'il ne verrouille PAS
Il vérifie le DIAGNOSTIC et la FUITE, pas les seuils. Aucun délai, palier ou
budget n'est testé ici : ce sont des réglages de posture qui appartiennent à
l'utilisateur (règle 5). `test_supabase_backoff.py` couvre déjà la reprise.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_supabase_cause_reelle.py
"""
import os
import sys

for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "scraper"))

import threading                                           # noqa: E402
import time                                                # noqa: E402

import psycopg                                             # noqa: E402
from store import supabase_store as ss                     # noqa: E402

# Le watchdog doit tomber AVANT que le faux connect ne réponde : c'est tout le
# défaut mesuré (25 s de watchdog contre 32 s de réponse réelle), transposé en
# millisecondes pour que le test reste instantané.
ss.CONNECT_HARD_TIMEOUT = 0.05
_REPONSE_TARDIVE = 0.30

VRAIE_ERREUR = ("connection failed: FATAL:  Failed to connect to database: "
                "authentication did not complete within 15000ms\n"
                "Multiple connection attempts failed. All failures were:\n"
                "- host: 'aws-1-ap-southeast-1.pooler.supabase.com'")


def _vide_le_ramasseur():
    ss._attentes_orphelines.clear()


# ───────── 1. le message du watchdog ne NOMME plus de cause qu'il ignore
_vide_le_ramasseur()
_vrai_connect = psycopg.connect
psycopg.connect = lambda *a, **k: time.sleep(_REPONSE_TARDIVE)
try:
    ss._connect_borne("postgresql://test/fake")
    raise AssertionError("un connect qui dépasse le watchdog doit lever")
except psycopg.OperationalError as exc:
    message = str(exc)
finally:
    psycopg.connect = _vrai_connect

assert "DNS" not in message and "TCP" not in message, (
    "le watchdog ne doit PLUS affirmer « DNS ou TCP » : à 25 s il ne sait pas "
    f"encore pourquoi l'appel n'a pas répondu. Message obtenu : {message!r}")
assert "pas encore connue" in message, (
    f"le message doit dire que la cause est inconnue à ce stade : {message!r}")
print("1. watchdog : ne nomme plus une cause qu'il ignore : OK")


# ───────── 2. la vraie cause, arrivée en retard, est bien restituée
_vide_le_ramasseur()


def _connect_lent_qui_echoue(*a, **k):
    time.sleep(_REPONSE_TARDIVE)
    raise psycopg.OperationalError(VRAIE_ERREUR)


psycopg.connect = _connect_lent_qui_echoue
try:
    try:
        ss._connect_borne("postgresql://test/fake")
    except psycopg.OperationalError:
        pass
    assert len(ss._attentes_orphelines) == 1, (
        "l'attente abandonnée doit être confiée au ramasseur, sinon la vraie "
        "cause est définitivement perdue")
    # Avant que le thread n'ait fini : rien à dire, et l'attente reste en vol.
    assert ss._ramasse_orphelines() is None, (
        "ne rien inventer tant que l'appel n'a pas répondu")
    assert len(ss._attentes_orphelines) == 1, (
        "une attente encore en vol ne doit pas être jetée — on la reverra")
    time.sleep(_REPONSE_TARDIVE * 2)
    cause = ss._ramasse_orphelines()
finally:
    psycopg.connect = _vrai_connect

assert cause is not None and "authentication did not complete" in cause, (
    "la cause réelle arrivée après le watchdog doit être restituée, c'est tout "
    f"l'objet du correctif. Obtenu : {cause!r}")
assert "Multiple connection attempts failed" not in cause, (
    "une seule ligne : psycopg empile un bloc par IP, qui noierait le log")
assert not ss._attentes_orphelines, "l'attente ramassée doit être retirée"
print("2. cause réelle tardive : restituée en une ligne : OK")


# ───────── 3. une connexion atterrie en retard est FERMÉE, pas fuitée
#     En mode session chaque connexion orpheline occupe un backend du pooler :
#     la fuite nourrissait l'ECHECKOUTTIMEOUT qu'on réessayait.
_vide_le_ramasseur()
ferme = threading.Event()


class _ConnexionTardive:
    def close(self):
        ferme.set()


def _connect_lent_qui_reussit(*a, **k):
    time.sleep(_REPONSE_TARDIVE)
    return _ConnexionTardive()


psycopg.connect = _connect_lent_qui_reussit
try:
    try:
        ss._connect_borne("postgresql://test/fake")
    except psycopg.OperationalError:
        pass
    time.sleep(_REPONSE_TARDIVE * 2)
    ss._ramasse_orphelines()
finally:
    psycopg.connect = _vrai_connect

assert ferme.is_set(), (
    "une connexion qui atterrit après le watchdog doit être FERMÉE : en mode "
    "session elle occupe un backend du pooler, celui-là même dont la pénurie "
    "provoque l'ECHECKOUTTIMEOUT qu'on est en train de réessayer")
assert not ss._attentes_orphelines, "l'attente ramassée doit être retirée"
print("3. connexion tardive : fermée, pas fuitée : OK")


# ───────── 4. une fermeture qui échoue ne doit pas tuer la remontée
#     Le ramassage est du soin, pas du travail utile : il ne peut pas être une
#     nouvelle cause de panne.
_vide_le_ramasseur()


class _ConnexionRecalcitrante:
    def close(self):
        raise RuntimeError("socket déjà morte")


def _connect_lent_recalcitrant(*a, **k):
    time.sleep(_REPONSE_TARDIVE)
    return _ConnexionRecalcitrante()


psycopg.connect = _connect_lent_recalcitrant
try:
    try:
        ss._connect_borne("postgresql://test/fake")
    except psycopg.OperationalError:
        pass
    time.sleep(_REPONSE_TARDIVE * 2)
    ss._ramasse_orphelines()          # ne doit pas lever
finally:
    psycopg.connect = _vrai_connect

assert not ss._attentes_orphelines, (
    "une fermeture en échec doit tout de même retirer l'attente, sinon le "
    "ramasseur la rejoue à chaque tour")
print("4. fermeture en échec : absorbée, attente retirée : OK")

print("\nTOUT OK — la vraie cause survit au watchdog, "
      "et plus aucune connexion n'est fuitée.")
