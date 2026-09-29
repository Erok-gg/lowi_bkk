"""test_console_utf8.py -- ops/pouls.py et agents/orchestrator.py ne doivent
plus planter en UnicodeEncodeError quand la console n'est pas en UTF-8.

POURQUOI CE TEST EXISTE
Connu depuis le 2026-08-22 (journal technique) : tout script lance a la main
sur ce poste heritait de l'ACP (cp1252), pas de l'UTF-8 -- agents/core/shell.py
forcait deja l'encodage pour les SOUS-PROCESSUS, mais rien ne le faisait pour
un lancement direct. Reproduit le 2026-08-27 : `ops/pouls.py --verifier` et
`python -m agents.orchestrator status`, lances a la main sans PYTHONUTF8,
plantaient tous deux des le premier caractere hors-ASCII (⚠, ✓, ✗) imprime,
AVANT meme d'afficher le contenu utile (l'alerte etait deja ecrite en base,
seul l'affichage mourait -- mais le code de sortie non nul masquait ca dans
les journaux Windows).

Correctif : `sys.stdout/stderr.reconfigure(encoding="utf-8")` en tete de
chaque module, avant tout print. Ce test simule l'environnement qui
declenchait le defaut (PYTHONIOENCODING=cp1252) sans toucher aux fichiers
d'etat reels (pas d'appel a --battement/--verifier, seulement l'import + un
print du caractere qui plantait).

Rejeu : scraper/.venv/Scripts/python.exe agents/tests/test_console_utf8.py
"""
import os
import subprocess
import sys
from pathlib import Path

# Ce test imprime lui-même les caractères qui plantaient (⚠, ✓, ✗) dans ses
# messages de résultat -- sans ce garde, le lancer à la main ici reproduirait
# le défaut qu'il vérifie, dans le PROCESS DU TEST cette fois.
for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

RACINE = Path(__file__).resolve().parents[2]
VENV_PY = RACINE / "scraper" / ".venv" / "Scripts" / "python.exe"

echecs: list[str] = []


def verifie(nom: str, condition: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if condition else 'ECHEC'} {nom}{(' - ' + detail) if detail else ''}")
    if not condition:
        echecs.append(nom)


def importe_sous_cp1252(module: str, caractere: str) -> subprocess.CompletedProcess:
    """Importe `module` puis imprime `caractere` dans un process enfant dont
    l'encodage de sortie est forcé en cp1252 -- la condition exacte qui
    plantait avant le correctif (aucun code de pouls.py/orchestrator.py
    n'est exécuté au-delà de l'import, donc aucun état réel n'est modifié)."""
    code = f"import {module}\nprint({caractere!r})\n"
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "cp1252"
    env["PYTHONUTF8"] = "0"
    return subprocess.run(
        [str(VENV_PY), "-c", code], cwd=str(RACINE),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=30)


for module, caractere in [("ops.pouls", "⚠"), ("agents.orchestrator", "✓ ✗")]:
    r = importe_sous_cp1252(module, caractere)
    sortie = r.stdout + r.stderr
    verifie(f"{module} n'a pas planté sur {caractere!r} en console cp1252",
            "UnicodeEncodeError" not in sortie and r.returncode == 0,
            detail=sortie[-300:] if r.returncode != 0 else "")

if echecs:
    print(f"\n{len(echecs)} ECHEC(S) : {echecs}")
    raise SystemExit(1)
print("\nTOUS LES ESSAIS PASSENT")
