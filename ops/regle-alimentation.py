"""regle-alimentation.py — ajuste le plan d'alimentation actif pour un cycle
de scrap long, sans dépendre des privilèges administrateur.

Trois réglages, tous vérifiés `powercfg /setacvalueindex` (fonctionne SANS
élévation depuis Windows 8, contrairement à `powercfg /requests` qui, lui,
l'exige — vérifié le 2026-08-16) :

1. Écran éteint après 5 min (`SUB_VIDEO/VIDEOIDLE`) — déjà la valeur du plan
   « Silent » actif sur ce poste, reposé ici pour que le script reste correct
   si le plan change.
2. Mise en veille après 5 h (`SUB_SLEEP/STANDBYIDLE`) — un FILET DE SÉCURITÉ,
   PAS la protection principale : garde-veille (agents/bots/garde_veille.py)
   tient un verrou système (`SetThreadExecutionState`) pendant tout cycle
   actif, qui empêche la veille idle QUELLE QUE SOIT cette valeur. Les 5 h ne
   jouent que si ce verrou échoue, ou en dehors d'un cycle d'agents.
3. Processeur plafonné (`SUB_PROCESSOR/PROCTHROTTLEMAX` à 60 %, MIN à 5 %) —
   pour limiter bruit/chaleur du ventilateur pendant un scrap, qui est
   I/O-bound et n'a pas besoin de la fréquence max. MESURÉ le 2026-08-16 :
   ce matériel n'expose PAS le réglage standard de politique de
   refroidissement (`SYSCOOLPOL`, GUID 94D3A615-A899-4AC5-AE2B-E4D8F634367F)
   — `powercfg /query` le renvoie vide même après un `/setacvalueindex`
   "réussi" (code retour 0 mais rien à lire derrière). Le plafond de
   fréquence est le seul levier vérifié qui influence réellement bruit et
   chaleur sur CE poste ; ne pas supposer que SYSCOOLPOL fonctionne ailleurs
   sans le revérifier.

Ne tourne PAS automatiquement dans une lane (`agents.json` : `lanes: []`) —
change une préférence utilisateur persistante (jusqu'au prochain changement
manuel ou prochain appel de ce script), pas une correction de bug détectée en
cycle. Invocation :
    scraper/.venv/Scripts/python.exe agents/orchestrator.py run regle-alimentation
"""
from __future__ import annotations

import json
import subprocess
import sys

# (sous-groupe, réglage, valeur AC, unité, pourquoi)
REGLAGES = [
    ("SUB_VIDEO", "VIDEOIDLE", 300, "s",
     "écran éteint après 5 min"),
    # REPOUSSÉ de 5 h à 13 h le 2026-08-26, en conséquence de l'ajout de
    # `remonter-supabase` à la lane daily. Mesures : un cycle complet dure
    # 7 h 15 (ledger, cycle du 2026-08-22, 25 agents), la remontée ajoute
    # ~3 h 40 d'upserts (débit mesuré 4,1 annonces/s sur 53 258) plus ~40 min de
    # recopie de statuts, soit ~11 h 35 au total. Un filet à 5 h coupait donc
    # désormais le cycle en son milieu au lieu de le rattraper après coup —
    # exactement la panne qui a tué extract-ddproperty deux cycles d'affilée le
    # 2026-08-16. 13 h laisse ~1 h 25 de marge.
    # CONTREPARTIE ASSUMÉE : si le verrou d'éveil de garde-veille échoue, la
    # machine reste allumée 13 h au lieu de 5. C'est le prix d'un filet qui ne
    # coupe pas ce qu'il est censé protéger.
    ("SUB_SLEEP", "STANDBYIDLE", 46800, "s",
     "veille après 13 h — filet de sécurité calé sur un cycle de ~11 h 35"),
    # AJOUTÉ le 2026-09-30. Le plan « ASUS Recommended » avait
    # HIBERNATEIDLE = 1 800 s sur secteur : 30 min après toute entrée en
    # veille, bascule en veille prolongée, d'où le réveil RTC de 01:00 ne
    # ressort pas. Mesuré cette nuit-là : Kernel-Power 42 « Hibernate from
    # Sleep - Fixed Timeout » à 01:01:13, une seconde après le déclenchement
    # de LowiBKK-Agents ; cycle bloqué jusqu'à l'ouverture du capot à 08:06
    # (7 h perdues). Veille prolongée quotidienne sur 30 j (13 fois).
    # Calée sur le même filet de 13 h que STANDBYIDLE, à la demande de
    # l'utilisateur (« l'alimentation doit tenir toute la nuit »).
    ("SUB_SLEEP", "HIBERNATEIDLE", 46800, "s",
     "veille prolongée après 13 h — ne plus couper le réveil de 01:00"),
    ("SUB_PROCESSOR", "PROCTHROTTLEMIN", 5, "%",
     "processeur au repos entre requêtes réseau"),
    ("SUB_PROCESSOR", "PROCTHROTTLEMAX", 60, "%",
     "plafond pour limiter bruit/chaleur — SYSCOOLPOL absent sur ce matériel, mesuré"),
]


def _set(sous_groupe: str, reglage: str, valeur: int) -> int:
    r = subprocess.run(
        ["powercfg", "/setacvalueindex", "SCHEME_CURRENT", sous_groupe, reglage, str(valeur)],
        capture_output=True, text=True)
    return r.returncode


def appliquer() -> dict:
    resultats = []
    for sous_groupe, reglage, valeur, unite, pourquoi in REGLAGES:
        code = _set(sous_groupe, reglage, valeur)
        resultats.append({"reglage": reglage, "valeur": f"{valeur}{unite}",
                          "exit": code, "pourquoi": pourquoi})

    activation = subprocess.run(["powercfg", "/setactive", "SCHEME_CURRENT"],
                                capture_output=True, text=True)

    return {"reglages": resultats,
            "tous_ok": all(r["exit"] == 0 for r in resultats),
            "activation_exit": activation.returncode}


if __name__ == "__main__":
    r = appliquer()
    print(json.dumps(r, ensure_ascii=False, indent=2))
    sys.exit(0 if r["tous_ok"] else 1)
