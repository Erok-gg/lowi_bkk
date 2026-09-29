"""test_orchestrator_tee.py — le Tee de orchestrator.py ne doit jamais faire
planter le cycle réel, même quand la console d'origine est cassée.

POURQUOI CE TEST EXISTE
Constaté le 2026-09-12 : extract-livinginsider absent d'un cycle daily
(4/5 extracteurs lancés, aucune ligne au ledger pour le 5e) sans qu'aucune
trace n'explique pourquoi — la tâche planifiée n'a pas de console, et les
print()/exceptions de l'orchestrateur LUI-MÊME (pas des sous-processus, déjà
journalisés par shell.py) partaient dans le vide. Root-cause de CET incident
resté non mesurable pour cette raison précise. Le correctif (agents/
orchestrator.py:Tee, branché dans main() pour --due/--boot/run-lane) ferme ce
trou pour la prochaine occurrence — il ne prétend pas expliquer celle-ci.

Ce que ce test vérifie :
  1. Tee écrit bien dans le fichier ;
  2. une console d'origine dont .write()/.flush() lève une exception ne fait
     PAS planter Tee (sinon le correctif introduirait la panne qu'il corrige).

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_orchestrator_tee.py
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from agents.orchestrator import Tee                       # noqa: E402


class _ConsoleCassee:
    """Simule sys.stdout sans console attachée (tâche planifiée Windows)."""

    def write(self, s):
        raise OSError("console non disponible")

    def flush(self):
        raise OSError("console non disponible")


fichier = io.StringIO()
tee = Tee(_ConsoleCassee(), fichier)

# 1. l'écriture arrive bien dans le fichier malgré la console cassée
tee.write("ligne de test\n")
tee.flush()
assert fichier.getvalue() == "ligne de test\n", (
    f"le fichier doit recevoir la ligne : {fichier.getvalue()!r}")
print("1. Tee écrit dans le fichier malgré une console cassée : OK")

# 2. plusieurs écritures ne font pas planter (pas d'exception propagée)
for i in range(3):
    tee.write(f"ligne {i}\n")
assert "ligne 2\n" in fichier.getvalue()
print("2. écritures répétées sur console cassée -> aucune exception : OK")

print("\nTOUS LES ESSAIS PASSENT")
