"""test_metrics.py — verrouiller la lecture des métriques d'un run.

POURQUOI CE TEST EXISTE
Du 2026-08-06 (chaînage `then`) au 2026-08-23, les deux surveillances lisaient
`nouvelles` à la racine alors que les extracteurs l'écrivaient sous `etapes`.
Mesuré sur le ledger : 24 runs d'extraction avec `nouvelles = None`, donc
verdict `metriques_absentes` (medium, muet) au lieu de `parseur_casse` (high,
escalade + mail). Nestopa ramenait 0 annonce depuis le 2026-08-17 et rien n'a
parlé. Aucun test ne reliait la FORME écrite à la forme LUE : c'est ce trou-là
que ce fichier ferme.

Ce qu'il verrouille, dans l'ordre :
  1. un dict déjà plat (agents T1) traverse `aplatir` inchangé ;
  2. les compteurs des étapes chaînées s'additionnent, `exit` et `then_exit`
     restent distincts, et la trace par étape survit ;
  3. un champ numérique NON déclaré sommable n'est jamais additionné ;
  4. sur la forme réelle du 2026-08-22, le classement rend `parseur_casse` —
     le seul verdict qui escalade ;
  5. le bilan JSON terminal d'un script alimente les métriques (contrat de
     `verifie-backup`), et un JSON imprimé au fil de l'eau ne le fait pas ;
  6. une purge sans candidate rend `lignes_purgees = 0`, pas un champ absent.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_metrics.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from agents.core.metrics import aplatir                 # noqa: E402
from agents.core.shell import metrics_from_output       # noqa: E402
from agents.bots.watch_health import _classer           # noqa: E402

# --------------------------------- 1. dict plat : identité
plat = {"khets_analyses": 43, "mouvements": 0}
assert aplatir(plat) == plat, "un dict sans etapes doit traverser inchange"
assert aplatir({}) == {}
print("dict plat : OK")

# --------------------------------- 2. étapes chaînées : somme + codes séparés
#: Forme RÉELLE du run extract-fazwaz du 2026-08-22 (ledger, run 3 étapes).
fazwaz = {"etapes": [
    {"etape": "principal", "exit": 0, "scannees": 4497, "nouvelles": 100,
     "changees": 31, "retirees": 366, "traces_erreur": 0},
    {"etape": "then_0", "exit": 0, "scannees": 4496, "nouvelles": 325,
     "changees": 24, "retirees": 969, "traces_erreur": 0},
    {"etape": "then_1", "exit": 3, "scannees": 2126, "nouvelles": 0,
     "changees": 1, "retirees": 0, "traces_erreur": 0},
]}
m = aplatir(fazwaz)
assert m["nouvelles"] == 425, m["nouvelles"]
assert m["retirees"] == 1335, m["retirees"]
assert m["scannees"] == 11119, m["scannees"]
assert m["exit"] == 0, "exit doit rester celui de l'etape principale"
assert m["then_exit"] == 3, "un then en echec ne doit pas se cacher derriere un principal a 0"
assert len(m["etapes"]) == 3, "la trace par etape doit survivre a l'agregation"
print("etapes chainees : OK  (nouvelles=425, retirees=1335, then_exit=3)")

# --------------------------------- 3. pas de somme sauvage
ratios = {"etapes": [
    {"etape": "principal", "exit": 0, "ratio": 0.9, "nouvelles": 2},
    {"etape": "then_0", "exit": 0, "ratio": 0.5, "nouvelles": 3},
]}
r = aplatir(ratios)
assert r["nouvelles"] == 5
assert r["ratio"] == 0.5, "un ratio ne s'additionne pas — derniere valeur attendue"
print("champ non sommable : OK  (ratio=0.5, pas 1.4)")

# --------------------------------- 4. le verdict qui escalade
nestopa = {"etapes": [{"etape": "principal", "exit": 0, "scannees": 0,
                       "nouvelles": 0, "changees": 0, "retirees": 0,
                       "traces_erreur": 0, "erreurs_http": 0}]}
n = aplatir(nestopa)
assert n["nouvelles"] == 0, "une etape unique doit remonter telle quelle"
verdict, severite = _classer(n["nouvelles"], n["traces_erreur"], 45.5, None, 0)
assert (verdict, severite) == ("parseur_casse", "high"), (verdict, severite)
# Le régression-test qui compte vraiment : la forme imbriquée NON aplatie
# rendait `metriques_absentes`, c'est-à-dire le silence.
muet, _ = _classer(nestopa.get("nouvelles"), 0, 45.5, None, 0)
assert muet == "metriques_absentes", "temoin : c'est bien la forme lue qui decidait"
print("verdict : OK  (aplati -> parseur_casse/high ; brut -> metriques_absentes)")

# --------------------------------- 5. bilan JSON terminal
sortie = (
    "[10:14:24] verification du backup\n"
    '  {"annonce": "au fil de l eau"}\n'
    "  archive: 11 tables\n"
    '{"sqlite_ok": true, "n_archive": 65283, "n_live": 65283, "ratio": 1.0,\n'
    ' "cadence_ok": true, "rattrapage_necessaire": false, "raisons": [],\n'
    ' "rattrapage_execute": false, "rattrapage_code_retour": null}\n')
b = metrics_from_output(sortie)
for champ in ("sqlite_ok", "n_archive", "n_live", "ratio", "cadence_ok",
              "raisons", "rattrapage_necessaire", "rattrapage_execute",
              "rattrapage_code_retour"):
    assert champ in b, f"{champ} manquant — contrat verifie-backup non honore"
assert "annonce" not in b, "un JSON imprime au fil de l eau n'est pas un bilan de run"
assert metrics_from_output("aucun json ici\n") .get("sqlite_ok") is None
print("bilan JSON : OK  (9 champs de contrat, le JSON au fil de l eau ignore)")

# --------------------------------- 6. purge sans candidate
p = metrics_from_output("  candidates à la purge (inactives >90 j) : 0\n")
assert p["lignes_purgees"] == 0, "0 candidate doit rendre 0, pas un champ absent"
print("purge a vide : OK")

print("\nTOUS LES ESSAIS PASSENT")
