"""test_fraicheur.py — le garde-fou de fraîcheur doit se taire ET savoir parler.

POURQUOI CE TEST EXISTE
`ops/fraicheur.py` est né le 2026-09-09 d'une panne restée MUETTE des semaines :
`recense.py` sautait le rafraîchissement de `last_seen` dès que le parcours avait
un trou — il en a un à chaque run — et ddproperty se retrouvait avec 9,6 % de ses
69 149 actives confirmées depuis moins de 48 h, la plus ancienne remontant au
23/07. Rien ne le signalait : le recensement rend `code 0`, son abstention se lit
dans un champ que personne ne regardait.

Un garde-fou qui remplace ce silence ne vaut que s'il tient les DEUX bouts
(règle 2) :
  · il se TAIT quand tout va bien, et quand il n'a pas de quoi juger ;
  · il PARLE quand le mécanisme est mort ou que la fraîcheur s'effondre.

Les quatre cas ci-dessous couvrent les deux bouts. Le cas 1 est le plus
important : c'est celui qui a manqué pendant des semaines.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_fraicheur.py
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

import ops.fraicheur as fr                               # noqa: E402

# On isole tout état sur disque : ce test n'écrit ni dans le vrai historique,
# ni dans le journal d'alertes, ni dans agents/queue/.
tmp = Path(tempfile.mkdtemp())
fr.HISTORIQUE = tmp / "fraicheur.jsonl"
fr.DEJA_CRIE = tmp / "alertes.json"

cris: list[tuple[str, str]] = []
fr._crier = lambda motif, sujet, corps, preuves: cris.append((motif, sujet))


def _releve(pct_dd: float) -> dict:
    return {"mesure_a": "2026-09-09T00:00:00+00:00", "fenetre_h": 48,
            "sources": {"ddproperty": {"actives": 69149,
                                       "frais": int(69149 * pct_dd / 100),
                                       "pct": pct_dd}}}


def _rejouer(pct_courant, historique_pcts, muets=()):
    cris.clear()
    fr.HISTORIQUE.write_text(
        "".join(__import__("json").dumps(_releve(p)) + "\n" for p in historique_pcts),
        encoding="utf-8")
    fr.DEJA_CRIE.unlink(missing_ok=True)
    fr.mesurer = lambda: _releve(pct_courant)
    fr._recensements_muets = lambda: list(muets)
    return fr.verifier()


# ───────────────────── 1. le mécanisme est mort : DOIT parler
# Le défaut du 2026-09-09, mot pour mot : des pages lues, zéro rafraîchie.
code = _rejouer(80.0, [80.0, 82.0, 79.0, 81.0],
                muets=[{"agent": "extract-ddproperty",
                        "pages_lues": 5256, "rafraichies": 0}])
assert code == 1 and any(m == "rafraichissement_mort" for m, _ in cris), (
    f"un recensement qui lit 5 256 pages et ne rafraichit RIEN doit alerter, "
    f"meme si la fraicheur du jour est encore bonne — c'est le defaut d'origine. "
    f"Cris : {cris}")
print("1. recensement qui lit des pages et ne rafraichit rien -> alerte : OK")

# ───────────────────── 2. la fraîcheur s'effondre : DOIT parler
# 9,6 % contre une médiane de ~80 % : c'est la mesure réelle du 2026-09-09.
code = _rejouer(9.6, [80.0, 82.0, 79.0, 81.0])
assert code == 1 and any(m.startswith("fraicheur_effondree") for m, _ in cris), (
    f"9,6 % contre une mediane de 80 % doit alerter. Cris : {cris}")
assert "9.6" in cris[0][1] and "80" in cris[0][1], (
    f"l'alerte doit porter les DEUX chiffres, le releve et la mediane : {cris[0][1]}")
print("2. fraicheur a 9,6 % pour une mediane de 80 % -> alerte : OK")

# ───────────────────── 3. tout va bien : DOIT se taire
code = _rejouer(78.0, [80.0, 82.0, 79.0, 81.0])
assert code == 0 and not cris, (
    f"78 % pour une mediane de 80 % est une fluctuation normale, pas une panne — "
    f"le garde-fou doit se TAIRE. Cris : {cris}")
print("3. fluctuation normale (78 % vs 80 %) -> silence : OK")

# ───────────────────── 4. pas assez d'historique : DOIT se taire
# Juger une tendance sur deux points, c'est crier au loup. Vaut aussi pour une
# source structurellement basse (nestopa est gelee a une page par conception) :
# tant qu'on n'a pas SA mediane, on ne la juge pas.
code = _rejouer(9.6, [80.0, 82.0])
assert code == 0 and not cris, (
    f"avec 2 releves sur {fr.MIN_HISTORIQUE} requis, aucune derive ne doit etre "
    f"jugee — meme un effondrement apparent. Cris : {cris}")
print(f"4. {fr.MIN_HISTORIQUE - 2} releves manquants -> silence : OK")

# ───────────────────── 5. une alerte par motif et par jour
# On teste la primitive d'anti-doublon elle-meme : `_crier` est mocke plus haut,
# donc le dedoublonnage ne passerait pas par lui.
fr.DEJA_CRIE.unlink(missing_ok=True)
assert fr._deja_crie_aujourdhui("motif_x") is False, \
    "le premier cri de la journee doit passer"
assert fr._deja_crie_aujourdhui("motif_x") is True, \
    "le deuxieme cri du MEME motif le meme jour doit etre etouffe (regle 2)"
assert fr._deja_crie_aujourdhui("motif_y") is False, \
    "un motif DIFFERENT doit toujours pouvoir crier le meme jour"
print("5. un cri par motif et par jour, motifs independants : OK")

print("\nTOUS LES ESSAIS PASSENT")
