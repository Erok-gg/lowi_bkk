"""test_social_leads_mcp_isole.py — l'extraction ne doit pas charger les connecteurs du compte.

POURQUOI CE TEST EXISTE
Nuit du 2026-10-09, cycle réel : `social-leads` a perdu le **lot 9** (15 posts
sur 150) sur l'erreur

    Prompt is too long · the request is ~217620 tokens (limit 200000)
    but this conversation is only ~4215 tokens — the rest is system prompt,
    tool definitions, and attachment content.

Le message dit l'essentiel : le prompt ne pesait que **4 215 tokens**. Les
~213 k restants étaient des **définitions d'outils** — celles des connecteurs
MCP du COMPTE claude.ai (Vercel en déclare ~250 à lui seul, plus Gmail, Drive,
Supabase, Agenda, IBKR…), injectées dans chaque appel `claude -p`.

Le piège : `--tools ""` était déjà passé, et ne suffit pas. Il ne coupe que les
outils INTÉGRÉS ; les connecteurs viennent du compte, pas des réglages du
dépôt, donc ni `--tools ""` ni `--setting-sources ""` ne les écartent. Seul
`--strict-mcp-config` le fait.

MESURE (2026-10-09, prompt vide, même modèle) :
    sans --strict-mcp-config : 36 907 tokens d'entrée
    avec --strict-mcp-config :      242 tokens d'entrée   → -99,3 %

Et ce surcoût **n'est pas borné** : il croît avec les connecteurs que le compte
gagne, sans que le dépôt change d'une ligne. C'est ce qui rend la panne
intermittente — 8 lots sur 10 ont passé cette nuit-là, le 9e a dépassé la
limite. Un cycle peut donc perdre des posts des mois après la dernière
modification du code.

Vérifié en production le 2026-10-09 : le lot 9 exact qui avait échoué
ré-extrait **15/15** avec le drapeau.

Ce test ne fait AUCUN appel réseau : il intercepte `subprocess.run` et
inspecte la ligne de commande construite.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_social_leads_mcp_isole.py
"""
import json
import os
import pathlib
import sys

for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from agents.bots import social_leads as sl                 # noqa: E402

_ECHECS: list[str] = []


def verifie(condition: bool, libelle: str) -> None:
    print(("  ✓ " if condition else "  ✗ ") + libelle)
    if not condition:
        _ECHECS.append(libelle)


def _capture_cmd() -> list[str]:
    """Appelle `appeler_claude` en interceptant subprocess.run ; rend la cmd."""
    vu: dict = {}

    class _Fausse:
        returncode = 0
        stdout = json.dumps({"result": "[]", "total_cost_usd": 0.0,
                             "is_error": False})
        stderr = ""

    vrai = sl.subprocess.run

    def _faux(cmd, **kw):
        vu["cmd"] = cmd
        return _Fausse()

    sl.subprocess.run = _faux
    try:
        sl.appeler_claude("peu importe")
    finally:
        sl.subprocess.run = vrai
    return vu["cmd"]


def main() -> int:
    print(__doc__.strip().splitlines()[0])
    cmd = _capture_cmd()
    print(f"  commande : {' '.join(repr(c) if ' ' in c or not c else c for c in cmd[:9])} …")

    # Le cœur du test : sans ce drapeau, un cycle peut reperdre des posts
    # dès que le compte gagne un connecteur, sans modification du dépôt.
    verifie("--strict-mcp-config" in cmd,
            "--strict-mcp-config présent (isole des connecteurs MCP du compte)")

    # Les deux drapeaux déjà là : ils ne suffisent pas, mais les retirer
    # rechargerait CLAUDE.md et les outils intégrés (64 k tokens mesurés).
    verifie("--tools" in cmd and cmd[cmd.index("--tools") + 1] == "",
            '--tools "" conservé (coupe les outils intégrés)')
    verifie("--setting-sources" in cmd and cmd[cmd.index("--setting-sources") + 1] == "",
            '--setting-sources "" conservé (ne charge pas CLAUDE.md)')

    # On ne teste PAS l'absence de --mcp-config : `ops/veille-cycle.py` en
    # passe un qui déclare `{"mcpServers": {}}`, et c'est inoffensif (mesuré
    # équivalent : 236 tokens là-bas, 242 ici sans le fichier). Interdire la
    # variante ferait crier le garde-fou pour rien. Ce qu'il faut interdire,
    # c'est un --mcp-config qui DÉCLARE des serveurs : ça rouvrirait la porte.
    if "--mcp-config" in cmd:
        chemin = cmd[cmd.index("--mcp-config") + 1]
        try:
            serveurs = json.loads(pathlib.Path(chemin).read_text(
                encoding="utf-8")).get("mcpServers") or {}
        except (OSError, ValueError):
            serveurs = {"illisible": True}
        verifie(not serveurs,
                f"--mcp-config ne déclare aucun serveur (vu : {list(serveurs)})")
    else:
        verifie(True, "aucun --mcp-config (strict seul = zéro serveur MCP)")

    print()
    if _ECHECS:
        print(f"ÉCHEC — {len(_ECHECS)} vérification(s) : " + " | ".join(_ECHECS))
        return 1
    print("OK — l'extraction reste isolée des connecteurs du compte.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
