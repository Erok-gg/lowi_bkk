"""test_organize_code.py — le mode « code » d'organize (poste sans T1).

POURQUOI : depuis le 2026-09-28 les six faits sont lus dans les champs de la
paire au lieu d'être extraits par un modèle. Ce test verrouille que :
  1. une republication (> 90 j, écart < 2 %) part en revue `same_unit` ;
  2. une paire indécidable s'abstient ;
  3. un second passage n'ajoute AUCUNE ligne à la file de revue (dédup).

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_organize_code.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
from agents.bots import organize   # noqa: E402

tmp = tempfile.mkdtemp(prefix="lowi-orgcode-")
organize.STATE = tmp
organize.REVUE = os.path.join(tmp, "revue.jsonl")


def paire(i, sta, stb, da, fsb, pa, pb):
    return {"ida": f"a{i}", "idb": f"b{i}", "source": "ddproperty", "condo_name": "X",
            "khet": "K", "sta": sta, "stb": stb, "da": da, "db": None,
            "fsa": "2026-01-01T00:00:00+00:00", "fsb": fsb, "pa": pa, "pb": pb,
            "ecart_prix": abs(pa - pb) / max(pa, pb)}


repub = paire(1, "inactive", "active", "2026-03-01T00:00:00+00:00", "2026-07-01T00:00:00+00:00", 10000, 10050)
floue = paire(2, "inactive", "active", "2026-07-20T00:00:00+00:00", "2026-07-10T00:00:00+00:00", 10000, 13000)

m = organize.trancher_en_code([repub, floue])
assert m["revue_ajoutee"] == 1 and m["abstentions"] == 1, m
m2 = organize.trancher_en_code([repub, floue])
assert m2["revue_ajoutee"] == 0, "doublon dans la file de revue"
assert sum(1 for _ in open(organize.REVUE, encoding="utf-8")) == 1
print("TOUS LES ESSAIS PASSENT")
