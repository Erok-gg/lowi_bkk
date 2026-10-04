"""test_fazwaz_sitemap_regeneration.py — ne pas relire le sitemap de la veille.

POURQUOI CE TEST EXISTE
Mesuré le 2026-10-04 : le run FazWaz du 04/10 est parti à 01:01, avant que le
site régénère ses sitemaps (vers 02:00). Il a relu le sitemap déjà traité par
le run du 03/10, parti tard à 03:10 : le plus frais lastmod était le 03/10 à
01:31 des deux côtés. Résultat : 1 fiche ouverte et 0 nouvelle par deal_type,
contre 99 à 315 les nuits précédentes, et un faux constat `parseur_casse`.

Ce que ce test vérifie :
  1. `regenere_depuis` : identique → non ; plus récent → oui ; pas de run
     précédent → oui (on ne peut pas savoir, on ne bloque pas) ;
  2. l'adaptateur ATTEND tant que le 1er fichier n'a rien de plus frais, puis
     scanne dès qu'il change ;
  3. au plafond d'attente, il scanne quand même (et le dit) au lieu de bloquer
     le cycle.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_fazwaz_sitemap_regeneration.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "scraper"))

import adapters.fazwaz as fz                                  # noqa: E402
from adapters.fazwaz import FazwazAdapter                     # noqa: E402
from pipeline import sitemap                                  # noqa: E402

URL = "https://www.fazwaz.com/property-rent/1-bedroom-condo-for-rent-at-x-in-min-buri-bangkok-u{}"


def shard(*lastmods):
    corps = "".join(f"<url><loc>{URL.format(i)}</loc><lastmod>{lm}</lastmod></url>"
                    for i, lm in enumerate(lastmods))
    return f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{corps}</urlset>'


HIER = "2026-10-03T01:31:19+07:00"        # valeur réelle du 04/10
AUJ = "2026-10-04T01:52:00+07:00"


def test_regenere_depuis():
    prec = [{"url": "a", "lastmod": HIER}, {"url": "b", "lastmod": "2026-09-28T18:20:38+07:00"}]
    assert not sitemap.regenere_depuis(prec, sitemap.parse_shard(shard(HIER)))
    assert sitemap.regenere_depuis(prec, sitemap.parse_shard(shard(HIER, AUJ)))
    assert sitemap.regenere_depuis(None, sitemap.parse_shard(shard(HIER)))
    # même instant écrit dans un autre fuseau : pas une régénération
    assert not sitemap.regenere_depuis(prec, [{"url": "a", "lastmod": "2026-10-02T18:31:19+00:00"}])


class FauxFetcher:
    def __init__(self, reponses):
        self.reponses = list(reponses)
        self.appels = 0

    def get_text(self, url, **_):
        self.appels += 1
        return self.reponses.pop(0) if len(self.reponses) > 1 else self.reponses[0]


def _adapter(tmp, plafond):
    cfg = {"base_url": "https://www.fazwaz.com", "discovery": "sitemap",
           "sitemap_index": "https://www.fazwaz.com/sitemap-listings.xml",
           "sitemap_cache": os.path.join(tmp, "sitemap.json"),
           "sitemap_attente_pas_minutes": 15, "sitemap_attente_max_minutes": plafond,
           "searches": [{"path": "/x", "deal_type": "rent"}], "image": {"max_per_listing": 1}}
    a = FazwazAdapter(cfg)
    sitemap.ecrire_cache(__import__("pathlib").Path(cfg["sitemap_cache"]),
                         [{"url": URL.format(0), "lastmod": HIER, "image": None}])
    return a, __import__("pathlib").Path(cfg["sitemap_cache"])


def test_attend_puis_scanne():
    dodos = []
    fz.time.sleep, vrai = (lambda s: dodos.append(s)), fz.time.sleep
    try:
        with tempfile.TemporaryDirectory() as tmp:
            a, cache = _adapter(tmp, plafond=180)
            f = FauxFetcher([shard(HIER), shard(HIER), shard(HIER, AUJ)])
            a._attendre_regeneration(f, cache, ["s1"])
            assert f.appels == 3 and dodos == [900, 900], (f.appels, dodos)
    finally:
        fz.time.sleep = vrai


def test_plafond_ne_bloque_pas():
    dodos = []
    fz.time.sleep, vrai = (lambda s: dodos.append(s)), fz.time.sleep
    try:
        with tempfile.TemporaryDirectory() as tmp:
            # plafond 0 : aucune attente possible → un seul essai, puis on scanne
            a, cache = _adapter(tmp, plafond=0)
            f = FauxFetcher([shard(HIER)])
            a._attendre_regeneration(f, cache, ["s1"])
            assert f.appels == 1 and dodos == []
    finally:
        fz.time.sleep = vrai


if __name__ == "__main__":
    test_regenere_depuis()
    test_attend_puis_scanne()
    test_plafond_ne_bloque_pas()
    print("OK — test_fazwaz_sitemap_regeneration : 3/3")
