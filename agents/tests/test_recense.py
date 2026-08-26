"""test_recense.py -- le message "parcours troue" ne doit plus planter.

POURQUOI CE TEST EXISTE
Le 2026-08-26, then_2 (recensement) de extract-ddproperty a plante apres 2 724
pages lues sur 3 200 : NameError sur `atteinte`, une variable qui n'a jamais
existe -- le nom local s'appelle `derniere`. Le recensement ne delist ni
n'insere rien (cf. recense.py), donc l'echec n'a corrompu aucune donnee, mais
il a empeche le bilan de sortir et fait echouer le run entier sur la toute
derniere ligne, apres ~3 h de scan reseau.

Isole dans _message_trous() pour etre testable sans reseau -- le code original
etait au milieu de main(), qui fait des appels HTTP reels.

Rejeu : scraper/.venv/Scripts/python.exe agents/tests/test_recense.py
"""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "scraper"))

from recense import _message_trous          # noqa: E402

echecs: list[str] = []


def verifie(nom: str, condition: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if condition else 'ECHEC'} {nom}{(' - ' + detail) if detail else ''}")
    if not condition:
        echecs.append(nom)


# --- Le cas qui plantait en production ----------------------------------
msg = _message_trous(trous=705, derniere=1495)
verifie("pas de NameError sur un vrai appel", isinstance(msg, str))
verifie("le nombre de trous apparait dans le message", "705" in msg,
        detail=msg)
verifie("la derniere page atteinte apparait dans le message", "1495" in msg,
        detail=msg)
verifie("le message ne contient pas le nom de variable fantome",
        "atteinte" not in msg.split(":")[-1] and "{atteinte}" not in msg,
        detail=msg)

# --- Cas limite : zero trou ne devrait jamais atteindre ce message en
# pratique (le code appelant ne l'invoque que si trous > 0), mais la fonction
# elle-meme ne doit pas planter pour autant --------------------------------
msg0 = _message_trous(trous=0, derniere=100)
verifie("trous=0 ne plante pas non plus", "0 pages manquantes sur 100" in msg0,
        detail=msg0)

if echecs:
    print(f"\n{len(echecs)} ECHEC(S) : {echecs}")
    raise SystemExit(1)
print("\nTOUS LES ESSAIS PASSENT")
