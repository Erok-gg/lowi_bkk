"""test_recense_rafraichit.py — un parcours troué doit quand même rafraîchir.

POURQUOI CE TEST EXISTE
Mesuré le 2026-09-09, en répondant à « la base est-elle à jour ? ». Elle ne
l'était pas, et le recensement — qui existe précisément pour ça — n'y était pour
rien depuis des semaines.

`_confronter()` faisait DEUX choses : rafraîchir le `last_seen` des annonces vues
au catalogue, et rendre le verdict « absente du catalogue ». Elle n'était
appelée qu'après une série de `continue` qui l'écartaient dès le moindre trou
dans le parcours. Or chaque recensement DDproperty manque 1 à 6 pages sur
~2 600 (0,04 à 0,23 %) : la fonction était donc écartée à TOUS les runs.

Ce que ça coûtait, mesuré :
  · **5,9 %** des 69 149 actives DDproperty avaient un `last_seen` du dernier
    cycle ; le plus ancien remontait au **23/07** ;
  · **8,9 %** des 85 327 actives n'avaient pas été confirmées depuis 30 j ;
  · `missed_count` ne dépassait jamais 1 — le délai de grâce ne tournait pas.

Et rien ne le signalait : `recense.py` rend **code 0** même quand il s'abstient
(à raison — cf. son commentaire de fin), et l'abstention se lit dans
`flux_non_conclusifs`, que personne ne regardait. Panne parfaitement muette.

LES DEUX SENS, tous deux vérifiés ici — c'est le fond du correctif :
  1. un trou n'empêche PAS de rafraîchir ce qu'on a vu (voir une annonce prouve
     qu'elle est vivante) ;
  2. un trou empêche TOUJOURS de conclure sur ce qu'on n'a pas vu — les
     compteurs `absentes_du_catalogue` / `inconnues_de_la_base` doivent rester
     absents (défaut du 2026-08-25 : 12 348 annonces déclarées absentes à tort).

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_recense_rafraichit.py
"""
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RACINE, "scraper"))

import recense                                           # noqa: E402


class StoreFactice:
    """Ne retient que ce qu'on lui demande de toucher."""

    def __init__(self, actives):
        self.actives = set(actives)
        self.touchees = set()

    def ids_actifs(self, source, deal):
        return set(self.actives)

    def toucher_lot(self, ids, quand):
        self.touchees |= set(ids)
        return len(ids)


# Trois annonces actives en base ; le catalogue n'en montre que deux
# (la troisième vit derrière une page trouée — on n'en sait donc RIEN).
ACTIVES = {"dd:sale:1", "dd:sale:2", "dd:sale:3"}
VUS = {"dd:sale:1", "dd:sale:2", "dd:sale:9"}   # :9 est inconnue de la base

# ─────────────────────────── 1. le rafraîchissement ne dépend pas des trous
store = StoreFactice(ACTIVES)
r = recense._rafraichir(store, VUS, store.ids_actifs("dd", "sale"))

assert store.touchees == {"dd:sale:1", "dd:sale:2"}, (
    f"seules les actives CONFIRMEES au catalogue doivent etre touchees, "
    f"pas {store.touchees}")
assert r["rafraichies"] == 2, r
assert r["confirmees"] == 2 and r["actives_en_base"] == 3, r
assert "absentes_du_catalogue" not in r, (
    "_rafraichir ne doit PAS rendre de verdict de comparaison — c'est "
    "precisement la separation qui corrige le defaut")
print("1. _rafraichir touche les 2 confirmees, sans verdict : OK")

# ─────────────────────────── 2. le verdict, lui, reste separe
c = recense._comparer(VUS, ACTIVES)
assert c == {"absentes_du_catalogue": 1, "inconnues_de_la_base": 1}, c
assert "rafraichies" not in c, "_comparer ne doit rien ecrire"
print("2. _comparer rend le verdict, sans ecrire : OK")

# ─────────────────────────── 3. une annonce jamais vue n'est jamais touchee
assert "dd:sale:3" not in store.touchees, (
    "une active absente du catalogue ne doit PAS voir son last_seen rafraichi : "
    "ce serait la maintenir vivante artificiellement, exactement l'inverse du but")
print("3. l'active non vue n'est pas touchee : OK")

# ─────────────────────────── 4. catalogue vide -> aucune ecriture
vide = StoreFactice(ACTIVES)
r = recense._rafraichir(vide, set(), vide.ids_actifs("dd", "sale"))
assert vide.touchees == set() and r["rafraichies"] == 0, r
print("4. catalogue vide -> aucune ecriture : OK")

# ─────────────────────────── 5. l'ordre dans le fichier : rafraîchir AVANT
#     les abstentions. Sans ça, les `continue` du parcours troué sautent le
#     rafraîchissement — c'est le défaut lui-même, il doit rester impossible.
src = open(os.path.join(RACINE, "scraper", "recense.py"), encoding="utf-8").read()
i_raf = src.index("ligne.update(_rafraichir(")
i_trous = src.index("if trous > 0:")
i_cmp = src.index("ligne.update(_comparer(")
assert i_raf < i_trous, (
    "_rafraichir doit etre appele AVANT le branchement `if trous > 0` qui fait "
    "`continue` — sinon un parcours troue ne rafraichit rien, le defaut d'origine")
assert i_cmp > i_trous, (
    "_comparer doit rester APRES les abstentions : le verdict n'a de sens que "
    "sur un parcours complet")
print("5. rafraichissement avant les abstentions, verdict apres : OK")

print("\nTOUS LES ESSAIS PASSENT")
