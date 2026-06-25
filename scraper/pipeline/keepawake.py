"""keepawake.py — Empêche la mise en veille SYSTÈME (Windows) pendant une tâche
longue (scrap, backfill), tout en laissant l'écran s'éteindre. Valable quel que
soit le mode de lancement. Libéré automatiquement à la sortie du process.
"""
from __future__ import annotations

import atexit
import ctypes
import sys

_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001


def prevent_sleep() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(
            ctypes.c_uint(_ES_CONTINUOUS | _ES_SYSTEM_REQUIRED)
        )
        atexit.register(allow_sleep)
        print("→ anti-veille actif (système maintenu éveillé, écran libre)")
    except Exception:
        pass


def allow_sleep() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(ctypes.c_uint(_ES_CONTINUOUS))
    except Exception:
        pass
