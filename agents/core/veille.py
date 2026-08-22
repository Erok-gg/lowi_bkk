"""veille.py — remet la machine en veille à la fin d'un cycle déclenché par la
tâche planifiée.

POURQUOI CE MODULE EXISTE
Le cycle part à 01:00 et réveille la machine (`WakeToRun` sur la tâche +
minuteurs RTC autorisés au niveau du plan). Sans contrepartie, la machine
restait éveillée jusqu'au matin : `garde-veille` pose un verrou
`SetThreadExecutionState` (agents/core/wake_lock.py) qui tient tout le cycle,
et la veille par inactivité du plan est à 5 h (ops/regle-alimentation.py).
Réveiller sans rendormir, c'est laisser un portable allumé toute la nuit pour
un cycle qui dure ~5 h.

CE QU'IL NE FAUT SURTOUT PAS FAIRE : endormir inconditionnellement. Le même
orchestrateur tourne en `--boot` (rattrapage au logon) et à la main. Endormir
la machine sous les doigts de l'utilisateur serait pire que le défaut qu'on
corrige. D'où DEUX verrous :

  1. l'appelant doit le demander explicitement (`--veille-a-la-fin`, posé par
     la seule tâche planifiée `LowiBKK-Agents`, jamais par `--boot`) ;
  2. ce module refuse si quelqu'un a touché clavier ou souris récemment
     (`GetLastInputInfo`, seuil ci-dessous). C'est la garantie qui ne dépend
     pas de la bonne foi de l'appelant.

MESURÉ SUR CE POSTE (REMIZDABOSS, 2026-08-22, `powercfg /a`)
Seul l'état **S0 (veille moderne, « Connecté au réseau »)** existe : ni S1, ni
S2, ni S3. La veille prolongée, elle, est disponible — ce qui compte, parce que
`SetSuspendState(bHibernate=FALSE, …)` est documenté comme pouvant **mettre en
veille prolongée quand même** si l'hibernation est active sur la machine. Sur
un système S0 le comportement n'a PAS été vérifié ici (on ne teste pas une mise
en veille depuis une session de travail). Si la machine hiberne au lieu de
dormir, ce n'est pas une panne du cycle : le réveil RTC fonctionne aussi depuis
l'hibernation, le retour est simplement plus lent.

`powercfg /query SCHEME_CURRENT SUB_SLEEP RTCWAKE` le 2026-08-22 :
**secteur = 0x1 (autorisé), batterie = 0x0 (interdit)**. Sur batterie, la
machine endormie ici ne se réveillera donc pas à 01:00 — elle repartira au
prochain logon par `LowiBKK-RattrapageBoot`.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

from . import wake_lock

# Quelqu'un a touché clavier/souris depuis moins de ça → on ne dort pas.
# 15 min : plus long qu'une pause café devant l'écran, plus court que le délai
# d'extinction d'écran du plan (5 min) multiplié par une marge raisonnable.
INACTIVITE_MINIMALE_S = 900


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def secondes_depuis_interaction() -> float | None:
    """Temps écoulé depuis la dernière frappe/mouvement de souris, ou None si
    l'API n'est pas interrogeable (autre OS, appel refusé)."""
    try:
        info = _LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        # GetTickCount64 : GetTickCount déborde à 49,7 jours d'uptime.
        return (ctypes.windll.kernel32.GetTickCount64() - info.dwTime) / 1000.0
    except (OSError, AttributeError):
        return None


def endort(dry_run: bool = False) -> tuple[bool, str]:
    """Rendort la machine. Rend (a_dormi, raison) — la raison est journalisée
    dans les deux cas, parce qu'un « je n'ai pas dormi » silencieux serait
    indiscernable d'un module qui ne tourne pas."""
    inactif = secondes_depuis_interaction()
    if inactif is None:
        return False, "veille sautée : impossible de lire l'inactivité clavier/souris"
    if inactif < INACTIVITE_MINIMALE_S:
        return False, (f"veille sautée : quelqu'un utilise la machine "
                       f"(dernière interaction il y a {inactif / 60:.0f} min, "
                       f"seuil {INACTIVITE_MINIMALE_S // 60} min)")
    if dry_run:
        return False, (f"veille SIMULÉE (--dry-run) : aurait dormi, "
                       f"inactif depuis {inactif / 60:.0f} min")

    # Relâcher d'abord le verrou d'éveil posé par garde-veille : SetSuspendState
    # est une demande explicite qui passe outre, mais laisser une demande
    # système active pendant qu'on demande la veille est incohérent — et si le
    # process survivait à l'appel, il rempêcherait la veille par inactivité.
    wake_lock.release()
    try:
        # (bHibernate=0, bForce=1, bWakeupEventsDisabled=0)
        # Le 3e paramètre DOIT rester 0 : à 1, les événements de réveil sont
        # désarmés et le minuteur RTC de 01:00 ne redéclencherait plus rien.
        ok = ctypes.windll.powrprof.SetSuspendState(0, 1, 0)
    except (OSError, AttributeError) as e:
        return False, f"veille impossible : {e}"
    if not ok:
        return False, "veille refusée par le système (SetSuspendState a rendu 0)"
    # Au réveil, l'exécution reprend ici — d'où le passé dans le message.
    return True, "machine endormie en fin de cycle"
