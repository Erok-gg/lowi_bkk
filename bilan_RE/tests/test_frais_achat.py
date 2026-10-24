"""test_frais_achat.py — le bloc « Buying costs » du bilan (2026-10-22).

Vérifie que le total « payé par l'acheteur » ne compte QUE les postes certains
(moitié du droit de mutation), jamais les postes négociés, conditionnels
(prêt, neuf, étranger) ou optionnels — sinon le total gonfle d'une taxe que
l'usage met à la charge du vendeur.

Rejeu :  scraper/.venv/Scripts/python.exe bilan_RE/tests/test_frais_achat.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from bilan_RE.tension.donnees import config          # noqa: E402
from bilan_RE.tension.rapport import _frais_achat    # noqa: E402

cfg = config()
f = _frais_achat({"prix": 5_000_000}, cfg)
assert f["total_acheteur"] == 50_000, f["total_acheteur"]          # 1 % : moitié du 2 %
assert abs(f["total_acheteur_pct"] - 0.01) < 1e-9
taxe = next(l for l in f["lignes"] if l["poste"].startswith("Specific business tax"))
assert taxe["payeur"] == "seller" and taxe["montant"] == 165_000      # 3,3 %, à titre d'information
assert any(l["etrangers_seulement"] for l in f["lignes"]), "ligne FET absente"
assert _frais_achat({"prix": None}, cfg) is None
print("frais d'achat : OK")
print("TOUS LES ESSAIS PASSENT")
