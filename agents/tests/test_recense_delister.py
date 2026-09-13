"""test_recense_delister.py — verrouiller le délistage par le recensement.

POURQUOI CE TEST EXISTE
Mesuré le 2026-09-13 : run.py --full ne retirait RIEN sur DDproperty
(`retirees: 0` sur 12/12 runs — le scan couvre 16 % des actives, le garde-fou
des 50 % annule le délistage chaque nuit), 12 700 actives non revues depuis 3
à 60 jours, base locale 1,19 → 2,56 Go et Supabase 139 → 336 Mo en 18 jours.
Le recensement voit le catalogue entier : c'est le seul scan où « absente »
veut dire quelque chose. Trois choses à verrouiller :
  1. les abstentions (page terminale non atteinte, trous > 1 %, moins de 50 %
     des actives revues) n'écrivent RIEN ;
  2. quand on délist, c'est via mark_missing_inactive avec la grâce de 3
     nuits, avec `vus` comme ensemble des présentes ;
  3. le flag est opt-in : sans --delister, le chemin n'est pas appelé.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_recense_delister.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "scraper"))

import recense                                           # noqa: E402


class StoreFactice:
    def __init__(self, actives):
        self.actives = set(actives)
        self.appels = []

    def mark_missing_inactive(self, source, seen_ids, deal_type=None, grace=2):
        self.appels.append((source, set(seen_ids), deal_type, grace))
        return sorted(self.actives - set(seen_ids))


ACTIVES = {f"dd:sale:{i}" for i in range(100)}
VUS = {f"dd:sale:{i}" for i in range(90)} | {"dd:sale:900"}   # 10 absentes, 1 inconnue

# 1. abstentions : rien n'est écrit
s = StoreFactice(ACTIVES)
r = recense._delister(s, "dd", "sale", VUS, ACTIVES, trous=0, derniere=2600, fin_atteinte=False)
assert r["delistees"] == 0 and "terminale" in r["delistage"] and not s.appels
r = recense._delister(s, "dd", "sale", VUS, ACTIVES, trous=30, derniere=2600, fin_atteinte=True)
assert r["delistees"] == 0 and "trouées" in r["delistage"] and not s.appels
r = recense._delister(s, "dd", "sale", set(list(VUS)[:40]), ACTIVES, trous=0, derniere=2600, fin_atteinte=True)
assert r["delistees"] == 0 and "revues" in r["delistage"] and not s.appels
print("1. trois abstentions, zéro écriture : OK")

# 2. parcours complet à 5 trous sur 2 600 (0,2 %, le cas réel) : on délist via la grâce
r = recense._delister(s, "dd", "sale", VUS, ACTIVES, trous=5, derniere=2600, fin_atteinte=True)
assert r["delistees"] == 10 and r["absentes_cette_nuit"] == 10, r
assert s.appels == [("dd", VUS, "sale", recense.DELIST_GRACE)], s.appels
assert recense.DELIST_GRACE >= 3, "la grâce absorbe les trous : ne pas descendre sous 3"
print("2. délistage par mark_missing_inactive, grâce 3, deal_type scopé : OK")

# 3. opt-in : le chemin n'existe que sous `if args.delister`
src = open(os.path.join(os.path.dirname(recense.__file__), "recense.py"), encoding="utf-8").read()
assert "if args.delister:" in src and src.index("_rafraichir(store") < src.index("_delister(store")
assert "delete_images" not in src, "le recensement ne supprime pas de photos (règle 8)"
print("3. opt-in, après le rafraîchissement, aucune suppression : OK")
print("TOUS LES ESSAIS PASSENT")
