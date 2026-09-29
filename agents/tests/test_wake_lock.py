"""test_wake_lock.py — le verrou d'éveil pose bien DEUX mécanismes, pas un seul.

POURQUOI CE TEST EXISTE
Le 2026-08-28, `verrou_veille_pose=true` était enregistré au ledger (l'appel à
SetThreadExecutionState avait bien réussi) et le système est quand même entré
en Veille moderne pendant 12 h 44 (journal Système, Kernel-Power 506→507),
tuant le process orchestrateur en plein cycle. SetThreadExecutionState seul ne
suffit pas à bloquer la Veille moderne sur ce matériel — l'API recommandée par
Microsoft pour ça est PowerCreateRequest/PowerSetRequest, visible dans
`powercfg /requests` contrairement à l'ancien flag. `wake_lock.py` pose
désormais les deux. Ce test verrouille que :

  1. `acquire_detail()` tente RÉELLEMENT les deux mécanismes (pas seulement le
     legacy) et rend un handle Win32 valide pour le power request ;
  2. `release()` referme proprement le handle (CloseHandle) et le remet à None
     — un handle qui fuit d'un run à l'autre serait un défaut discret ;
  3. `acquire()` (l'API historique, encore utilisée par garde_veille.py comme
     valeur de retour agrégée) reste compatible : True si le legacy a réussi,
     indépendamment du power request.

Ce test appelle les VRAIES fonctions Win32 (pas de mock) : il ne peut donc
tourner que sous Windows, comme le reste du dépôt. Il ne peut PAS vérifier que
Windows respecte réellement la demande sur la durée (ça se mesure sur un cycle
complet, pas en quelques secondes) — seulement que l'appel réussit et que la
ressource est bien libérée.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_wake_lock.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from agents.core import wake_lock                       # noqa: E402

# ------------------------------------------------------- 1. acquire_detail()
ok_legacy, ok_power_request = wake_lock.acquire_detail()
print(f"acquire_detail() -> legacy={ok_legacy} power_request={ok_power_request}")
assert ok_legacy, "SetThreadExecutionState devrait reussir sur une session normale"
assert ok_power_request, ("PowerCreateRequest/PowerSetRequest devrait reussir sur "
                           "une session normale (pas de privilege admin requis)")
assert wake_lock._handle is not None, "le handle du power request devrait etre garde"
assert wake_lock._handle not in (0, -1), f"handle invalide : {wake_lock._handle}"
print("handle Win32 valide :", wake_lock._handle)

# ---------------------------------------------------------- 2. release() nettoie
wake_lock.release()
assert wake_lock._handle is None, "release() doit remettre le handle a None"
print("release() : handle referme et remis a None — OK")

# ------------------------------------------ 3. acquire() reste retro-compatible
ok = wake_lock.acquire()
assert ok is True, "acquire() doit toujours rendre le succes du legacy"
assert wake_lock._handle is not None, "acquire() doit AUSSI poser le power request"
wake_lock.release()
print("acquire() retro-compatible (bool) tout en posant les deux mecanismes — OK")

print("\nTOUS LES ESSAIS PASSENT")
