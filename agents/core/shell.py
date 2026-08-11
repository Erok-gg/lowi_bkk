"""shell.py — exécution d'un sous-processus avec capture, pour les agents T0.

Les 6 agents déterministes (les 4 extracteurs, `report`, `storage`) n'ont pas de
module Python : leur commande est déclarée dans agents.json. Ce module est ce qui
les exécute, capture leur sortie dans agents/logs/, et en tire des métriques.
"""
from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.dirname(ROOT)
LOG_DIR = os.path.join(ROOT, "logs")
VENV_PY = os.path.join(PROJECT, "scraper", ".venv", "Scripts", "python.exe")


def log_path(agent: str) -> str:
    os.makedirs(LOG_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
    return os.path.join(LOG_DIR, f"{agent}-{stamp}.log")


def run(cmd: list[str], cwd: str | None = None, log: str | None = None,
        timeout: int = 6 * 3600, env_extra: dict | None = None) -> tuple[int, str]:
    """Exécute, écrit le log au fil de l'eau, rend (code_retour, texte).

    `env_extra` sert au mode local : LOWI_OUTPUT_DIR redirige base, images et
    fiches vers un dossier de test sans toucher à la production."""
    cmd = [VENV_PY if part == "@py" else part for part in cmd]
    env = None
    if env_extra:
        env = os.environ.copy()
        env.update(env_extra)
    buf: list[str] = []
    fh = open(log, "w", encoding="utf-8", errors="replace") if log else None
    try:
        proc = subprocess.Popen(
            cmd, cwd=cwd or PROJECT, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace", bufsize=1, env=env,
            # Pas de console par sous-processus : la sortie est deja capturee
            # et journalisée dans agents/logs/.
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        assert proc.stdout is not None
        for line in proc.stdout:
            buf.append(line)
            if fh:
                fh.write(line)
                fh.flush()
        code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        buf.append(f"\n[shell] TIMEOUT après {timeout}s — processus tué\n")
        code = 124
    finally:
        if fh:
            fh.close()
    return code, "".join(buf)


# ── métriques tirées de la sortie des scripts ────────────────────────────
# Les motifs collent aux lignes RÉELLEMENT imprimées :
#   scraper/run.py       → "  scannées : N | nouvelles : N | changées : N | … | retirées : N …"
#   study/run_study.py   → "  snapshot : <chemin>"  puis  "✓ rapport : <chemin>"
#   ops/sync_…           → "  <table>: N lignes serveur → M en archive"
#                          "✓ N annonces purgées du serveur"
_RESUME = re.compile(
    r"scannées\s*:\s*(\d+).*?nouvelles\s*:\s*(\d+).*?changées\s*:\s*(\d+)"
    r".*?retirées\s*:\s*(\d+)", re.S)
_SNAPSHOT = re.compile(r"snapshot\s*:\s*(\S+)")
_RAPPORT = re.compile(r"rapport\s*:\s*(\S+)")
_ARCHIVE = re.compile(r":\s*(\d+)\s+lignes serveur\s*→\s*(\d+)\s+en archive")
_PURGE = re.compile(r"(\d+)\s+annonces purgées")
_HTTP_ERR = re.compile(r"HTTP\s*(?:error\s*)?(4\d\d|5\d\d)", re.I)

# ÉCHECS SUR LES IMAGES — comptés à part du scraping.
#
# Relevé le 2026-08-11 : les métriques annonçaient `traces_erreur: 0` et
# `erreurs_http: 0` pendant que les journaux contenaient des
# « upload erreur ... RemoteDisconnected » vers le stockage et des 502/503 du
# CDN de PropertyScout. `watch-health` déclarait donc la source SAINE alors que
# des photos se perdaient.
#
# Le défaut n'était pas le comptage mais le PÉRIMÈTRE : on ne mesurait que la
# collecte des annonces, jamais ce qu'on en faisait ensuite. « Source saine »
# voulait dire « le scraping va bien », et personne ne le savait.
_IMG_ERR = re.compile(
    r"upload erreur|échec GET \(bytes\)|echec GET \(bytes\)|erreur image", re.I)


def metrics_from_output(text: str) -> dict:
    """Métriques structurées. Elles alimentent les bandes de `watch-health` et
    sont vérifiées par l'overseer contre le contrat de sortie du SKILL.md."""
    m: dict = {}

    if (r := _RESUME.search(text)):
        m["scannees"] = int(r.group(1))
        m["nouvelles"] = int(r.group(2))
        m["changees"] = int(r.group(3))
        m["retirees"] = int(r.group(4))

    if (r := _SNAPSHOT.search(text)):
        m["snapshot"] = r.group(1)
    if (r := _RAPPORT.search(text)):
        m["rapport"] = r.group(1)

    paires = _ARCHIVE.findall(text)
    if paires:
        m["tables_repliquees"] = len(paires)
        m["lignes_archivees"] = sum(int(b) for _, b in paires)
    if (r := _PURGE.search(text)):
        m["lignes_purgees"] = int(r.group(1))
    elif "purge ANNULÉE" in text or "purge interdite" in text:
        m["lignes_purgees"] = 0
        m["purge_refusee"] = True

    m["erreurs_http"] = len(_HTTP_ERR.findall(text))
    m["erreurs_images"] = len(_IMG_ERR.findall(text))
    m["lignes_log"] = text.count("\n")
    low = text.lower()
    m["traces_erreur"] = low.count("traceback") + low.count("[erreur]")
    return m
