"""test_watch_health_sitemap.py — un sitemap FazWaz figé n'est pas un parseur cassé.

POURQUOI CE TEST EXISTE
2026-10-08 : 3 constats `parseur_casse` (high, le seul verdict qui escalade et
envoie un mail) en 5 nuits sur extract-fazwaz — runs 686, 702, 733. Les trois
fois : sonde de structure OK, 0 erreur, sitemap non régénéré par le site ; 702
et 733 portent `[sitemap-non-regenere]` dans leur journal (686 précède
l'attente de régénération, posée le 04/10). La nuit
suivante a chaque fois repris 130 à 278 nouvelles. Signalé deux fois au journal
(05/10, 07/10) sans être corrigé : la fausse alerte revenait (règle 2).

Ce que ce test vérifie :
  1. `_classer` : 0 nouvelle + sitemap figé → `sitemap_non_regenere`/medium ;
     0 nouvelle sans marqueur → toujours `parseur_casse`/high (le vrai garde-fou
     n'est pas affaibli) ;
  2. `_sitemap_fige` lit le marqueur, et se tait sur un journal absent ;
  3. rejeu sur les VRAIS journaux de production quand ils sont présents
     (PC2) : les 3 runs à tort reconnus, les 2 runs sains voisins non.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_watch_health_sitemap.py
"""
import os
import sys
import tempfile

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RACINE)

from agents.bots import watch_health as wh                    # noqa: E402


def test_classer():
    assert wh._classer(0, 0, 226.0, None, sitemap_fige=True) == ("sitemap_non_regenere", "medium")
    assert wh._classer(0, 0, 226.0, None, sitemap_fige=False) == ("parseur_casse", "high")
    assert wh._classer(0, 0, 226.0, None) == ("parseur_casse", "high")
    # des erreurs l'emportent : un sitemap figé n'excuse pas une panne réseau
    assert wh._classer(0, 3, 226.0, None, sitemap_fige=True) == ("panne_reseau", "high")
    # des nouvelles malgré le marqueur : classement normal
    assert wh._classer(200, 0, 226.0, None, sitemap_fige=True) == ("ok", "low")


def test_sitemap_fige():
    with tempfile.TemporaryDirectory() as tmp:
        oui = os.path.join(tmp, "a.log")
        non = os.path.join(tmp, "b.log")
        with open(oui, "w", encoding="utf-8") as f:
            f.write("  [sitemap-non-regenere] plus frais lastmod toujours 2026-10-06 — scan\n")
        with open(non, "w", encoding="utf-8") as f:
            f.write("  sitemap régénéré après 30 min d'attente\n")
        assert wh._sitemap_fige(oui)
        assert not wh._sitemap_fige(non)
        assert not wh._sitemap_fige(os.path.join(tmp, "absent.log"))
        assert not wh._sitemap_fige(None)


def test_rejeu_production():
    logs = os.path.join(RACINE, "agents", "logs")
    # Run 686 (03/10) est antérieur à l'attente de régénération (04/10) : pas de
    # marqueur, donc hors de portée de ce correctif — c'est lui qui l'a motivée.
    faux = ["extract-fazwaz-2026-10-04T203010.log",    # run 702
            "extract-fazwaz-2026-10-06T201930.log"]    # run 733
    sains = ["extract-fazwaz-2026-10-04T031652.log",   # run 700, 130 nouvelles
             "extract-fazwaz-2026-10-05T193005.log"]   # run 718, 278 nouvelles
    if not all(os.path.exists(os.path.join(logs, n)) for n in faux + sains):
        print("  (journaux de production absents sur ce poste — rejeu sauté)")
        return
    for n in faux:
        assert wh._sitemap_fige(os.path.join(logs, n)), n
    for n in sains:
        assert not wh._sitemap_fige(os.path.join(logs, n)), n


if __name__ == "__main__":
    test_classer()
    test_sitemap_fige()
    test_rejeu_production()
    print("OK — test_watch_health_sitemap : 3/3")
