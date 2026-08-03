"""Réétiquette pairs.json avec la MÊME précédence que la production.

Défaut trouvé par test_local_llm.py le 2026-07-31 : le jeu d'étiquettes avait été
construit en testant « republication séquentielle » AVANT « les deux actives ».
La production fait l'inverse, et elle a raison — une annonce peut porter une
`delisted_at` passée tout en étant ACTIVE aujourd'hui (c'est ce que produisent les
passes de restauration couloirs). Quand les deux sont actives simultanément, ce
sont deux lots distincts : constat du 2026-07-28, « 1 399 doublons » qui étaient
des lots consécutifs d'une même agence.

10 paires sur 120 étaient donc mal étiquetées. Ce script les corrige en appelant
`prefiltre_sql` — la fonction de production — comme unique arbitre.

Usage : scraper/.venv/Scripts/python.exe agents/tests/relabel.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agents.bots.organize import prefiltre_sql  # noqa: E402

ICI = os.path.dirname(os.path.abspath(__file__))
CHEMIN = os.path.join(ICI, "pairs.json")

data = json.load(open(CHEMIN, encoding="utf-8"))
avant = Counter(p["label"] for p in data["labelled"])

corrigees, etiquetees, ambigues = 0, [], list(data["ambiguous"])
for p in data["labelled"]:
    verdict = prefiltre_sql(p)
    if verdict is None:
        # La règle de production ne tranche pas → la paire rejoint les ambiguës,
        # elle n'a rien à faire dans un jeu étiqueté.
        ambigues.append(p)
        corrigees += 1
        continue
    if verdict != p["label"]:
        corrigees += 1
    etiquetees.append({**p, "label": verdict})

apres = Counter(p["label"] for p in etiquetees)
print(f"étiquettes corrigées : {corrigees}")
print(f"  avant : {dict(avant)}")
print(f"  après : {dict(apres)}  ({len(etiquetees)} paires)")
print(f"  ambiguës : {len(data['ambiguous'])} → {len(ambigues)}")

json.dump({"labelled": etiquetees, "ambiguous": ambigues},
          open(CHEMIN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"écrit : {CHEMIN}")
