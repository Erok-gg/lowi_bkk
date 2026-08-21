"""wake_lock.py — empêche Windows d'entrer en Veille moderne (S0 idle) pendant
un cycle d'agents.

Mesuré le 2026-08-16 : extract-ddproperty tué deux cycles d'affilée par
Kernel-Power (motif « Idle Timeout », journal Système), `powercfg /requests`
vide au moment du constat — aucun processus ne tenait de demande d'éveil.
Cause directe, pas un bug du scraper : ce portable ne supporte QUE l'état S0
(pas de S1/S2/S3, `powercfg /a`), et Windows y suspend le réseau des process
d'arrière-plan dès l'inactivité clavier/souris, scrap ou pas.

SetThreadExecutionState est une demande SYSTÈME : peu importe quel process la
tient, tant qu'UN thread la maintient le système ne part pas en veille idle.
Le process orchestrator.py vit du premier au dernier agent de la lane — poser
le flag une fois au début (agent garde-veille, en Prelude) suffit pour tout
le cycle. Pas de release explicite en usage normal : Windows relâche la
demande de lui-même à la sortie du process (comportement documenté de l'API).
"""
from __future__ import annotations

import ctypes

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def acquire() -> bool:
    """Pose la demande d'éveil pour le reste de la vie de CE process."""
    try:
        res = ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        return res != 0
    except (OSError, AttributeError):
        return False


def release() -> bool:
    """Repasse en ES_CONTINUOUS seul, c'est-à-dire plus aucune demande active.
    Sert aux tests, pour ne pas garder un process de test éveillé."""
    try:
        res = ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        return res != 0
    except (OSError, AttributeError):
        return False
