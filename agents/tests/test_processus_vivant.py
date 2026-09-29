"""test_processus_vivant.py — un accès refusé n'est pas un processus mort.

POURQUOI CE TEST EXISTE
Mesuré le 2026-09-08, en plein cycle nocturne : `OpenProcess(SYNCHRONIZE, ...)`
échoue avec `ERROR_ACCESS_DENIED` (code 5, pas un handle nul « processus
absent ») quand l'appelant est dans une session Windows différente de celle du
processus visé — une session Claude Code interactive qui interroge le ledger
(`orchestrator status`, ou juste `Ledger()`) pendant qu'une tâche planifiée
tourne dans la session « Services ». Reproduit en direct sur le PID bien vivant
de l'orchestrateur du cycle du jour : handle nul, `GetLastError()==5`.
`reap_stale()` a alors classé `remonter-supabase` `interrompu` alors qu'il
tournait encore (connexion Postgres ESTABLISHED confirmée par `netstat`,
4 heures dans une synchronisation légitime) — un simple contrôle de routine
depuis une autre session suffit à corrompre le ledger d'un run en cours.

Ce que ce test verrouille, dans l'ordre :
  1. le propre PID du test (même session) est vivant → True ;
  2. un PID de processus réellement terminé → False ;
  3. `OpenProcess` refusé avec `ERROR_ACCESS_DENIED` (autre session/utilisateur,
     processus vivant mais inaccessible) → True, PAS False ;
  4. `OpenProcess` refusé pour une autre raison (ex. PID invalide,
     `ERROR_INVALID_PARAMETER`) → False, le cas qu'on veut continuer à fermer.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_processus_vivant.py

Windows uniquement (comme le code testé) — n'utilise ni ledger.db ni queue/.
"""
import ctypes
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from agents.core.ledger import Ledger                    # noqa: E402

# ------------------------------------------------------- 1. soi-même, vivant
assert Ledger._processus_vivant(os.getpid()) is True, \
    "le propre PID du test, meme session, doit etre vu comme vivant"
print("1. propre PID (meme session) -> vivant : OK")

# ------------------------------------------------------- 2. processus terminé
p = subprocess.Popen([sys.executable, "-c", "pass"])
p.wait()
assert Ledger._processus_vivant(p.pid) is False, \
    "un processus dont on a attendu la fin (wait()) doit etre vu comme mort"
print("2. processus reellement termine -> mort : OK")


# --------------------------------------------- 3+4. simulation OpenProcess
class _KernelFactice:
    """Simule kernel32 : handle nul + code d'erreur choisi par le test."""

    def __init__(self, code_erreur):
        self.code_erreur = code_erreur

    def OpenProcess(self, *_a):
        return 0

    def WaitForSingleObject(self, *_a):
        raise AssertionError("ne doit pas etre appele si le handle est nul")

    def CloseHandle(self, *_a):
        raise AssertionError("ne doit pas etre appele si le handle est nul")


def _avec_kernel_factice(code_erreur, appel):
    vrai_windll = ctypes.WinDLL
    vrai_get_last_error = ctypes.get_last_error
    ctypes.WinDLL = lambda *a, **k: _KernelFactice(code_erreur)          # noqa: E731
    ctypes.get_last_error = lambda: code_erreur                          # noqa: E731
    try:
        return appel()
    finally:
        ctypes.WinDLL = vrai_windll
        ctypes.get_last_error = vrai_get_last_error


ERROR_ACCESS_DENIED = 5
ERROR_INVALID_PARAMETER = 87

vivant = _avec_kernel_factice(
    ERROR_ACCESS_DENIED, lambda: Ledger._processus_vivant(4242))
assert vivant is True, (
    "ERROR_ACCESS_DENIED (session/utilisateur different) doit etre traite "
    "comme 'vivant, juste inaccessible' — c'est exactement le defaut mesure "
    "le 2026-09-08"
)
print("3. OpenProcess refuse (ERROR_ACCESS_DENIED) -> vivant : OK")

mort = _avec_kernel_factice(
    ERROR_INVALID_PARAMETER, lambda: Ledger._processus_vivant(4242))
assert mort is False, (
    "un refus pour une autre raison que l'acces (ex. PID invalide) doit "
    "toujours etre traite comme 'processus absent'"
)
print("4. OpenProcess refuse (autre code) -> mort : OK")

print("\nTOUS LES ESSAIS PASSENT")
