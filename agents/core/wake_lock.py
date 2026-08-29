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

DEUXIÈME MÉCANISME AJOUTÉ LE 2026-08-29 — SetThreadExecutionState NE SUFFIT PAS.
Cycle du 2026-08-28 : `verrou_veille_pose=true` enregistré au ledger (l'appel a
bien réussi), et pourtant le journal Système montre le système ENTRER en veille
moderne à 18:45:32 UTC et ne PAS en ressortir avant 07:29:46 (12 h 44, réveil par
mouvement de souris) — `extract-ddproperty` a fini son travail (log complet
jusqu'aux stats finales) mais le PROCESS PARENT (orchestrateur, PID 21304) était
mort à la reprise, jamais de `led.end_run()`. SetThreadExecutionState est une
API historique (pré-Windows 8) : documentée par Microsoft comme non fiable pour
bloquer la Veille moderne (S0 Low Power Idle) sur du matériel qui ne supporte
QUE cet état — exactement ce poste (`powercfg /a`, 2026-08-16). Le remplacement
recommandé est l'API Power Request (`PowerCreateRequest`/`PowerSetRequest`),
que `powercfg /requests` sait lister nommément — contrairement à l'ancien flag,
invisible dans cette commande, ce qui explique pourquoi le diagnostic du
2026-08-16 la voyait « vide » alors que le processus croyait tenir un verrou.
Les deux mécanismes sont posés en même temps (l'un n'annule pas l'autre) :
défense en profondeur, coût nul, aucune garantie que celui-ci suffise non plus
tant qu'un cycle complet n'a pas tourné dessus sans coupure."""
from __future__ import annotations

import ctypes
from ctypes import wintypes

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001

POWER_REQUEST_CONTEXT_VERSION = 0
POWER_REQUEST_CONTEXT_SIMPLE_STRING = 0x00000001
PowerRequestSystemRequired = 0


class _REASON_UNION(ctypes.Union):
    _fields_ = [("SimpleReasonString", wintypes.LPWSTR)]


class _REASON_CONTEXT(ctypes.Structure):
    _fields_ = [("Version", wintypes.ULONG),
                ("Flags", wintypes.DWORD),
                ("Reason", _REASON_UNION)]


# Handle du power request en cours, None si non posé (ou si l'OS ne l'expose
# pas — Wine, machine virtuelle sans les DLL attendues, etc.).
_handle: int | None = None


def _power_request_acquire() -> bool:
    """Déclare une demande PowerRequestSystemRequired, visible dans
    `powercfg /requests` — voir le second mécanisme documenté ci-dessus."""
    global _handle
    try:
        ctx = _REASON_CONTEXT(
            Version=POWER_REQUEST_CONTEXT_VERSION,
            Flags=POWER_REQUEST_CONTEXT_SIMPLE_STRING,
            Reason=_REASON_UNION(SimpleReasonString="Lowi BKK — cycle d'agents en cours"))
        h = ctypes.windll.kernel32.PowerCreateRequest(ctypes.byref(ctx))
        if not h or h == -1:                      # NULL ou INVALID_HANDLE_VALUE
            return False
        if not ctypes.windll.kernel32.PowerSetRequest(h, PowerRequestSystemRequired):
            ctypes.windll.kernel32.CloseHandle(h)
            return False
        _handle = h
        return True
    except (OSError, AttributeError, TypeError):
        return False


def _power_request_release() -> None:
    global _handle
    if _handle is None:
        return
    try:
        ctypes.windll.kernel32.PowerClearRequest(_handle, PowerRequestSystemRequired)
        ctypes.windll.kernel32.CloseHandle(_handle)
    except (OSError, AttributeError):
        pass
    _handle = None


def acquire() -> bool:
    """Pose la demande d'éveil pour le reste de la vie de CE process, par les
    DEUX mécanismes. Rend True si AU MOINS le legacy a réussi (comportement
    historique inchangé) — `acquire_detail()` donne le détail des deux."""
    ok_legacy, _ = acquire_detail()
    return ok_legacy


def acquire_detail() -> tuple[bool, bool]:
    """(succès SetThreadExecutionState, succès PowerRequest) — séparés pour que
    garde-veille puisse consigner lequel des deux a réellement tenu."""
    try:
        res = ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        ok_legacy = res != 0
    except (OSError, AttributeError):
        ok_legacy = False
    ok_power_request = _power_request_acquire()
    return ok_legacy, ok_power_request


def release() -> bool:
    """Repasse en ES_CONTINUOUS seul et efface le power request s'il était posé.
    Sert aux tests, pour ne pas garder un process de test éveillé."""
    _power_request_release()
    try:
        res = ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        return res != 0
    except (OSError, AttributeError):
        return False
