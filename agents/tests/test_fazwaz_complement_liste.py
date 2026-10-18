"""test_fazwaz_complement_liste.py — le filet « pages de liste » quand le sitemap est figé.

POURQUOI : sitemap-listings.xml n'a pas été republié du 2026-10-14 au moins
jusqu'au 2026-10-18 (0 nouvelle FazWaz par nuit). `_complement_liste` parcourt
les pages de liste (sans order_by, interdit) et n'émet que ce que le sitemap
ne porte pas. Verrouille : (1) déjà-dans-le-sitemap non ré-émis, (2) filtre
Bangkok/condo, (3) arrêt à la 1re page vide (le site plafonne à 25 pages),
(4) désactivé si `list_complement_max_pages` = 0, (5) pas de complément sous --limit.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_fazwaz_complement_liste.py
"""
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RACINE, "scraper"))

from adapters.fazwaz import FazwazAdapter                     # noqa: E402

CFG = json.load(open(os.path.join(RACINE, "scraper", "config", "fazwaz.json"), encoding="utf-8"))
U = "https://www.fazwaz.com/property-rent/{}-bedroom-condo-for-rent-at-x-in-bang-na-bangkok-u{}"


class FauxFetcher:
    def __init__(self, pages):
        self.pages, self.appels = pages, []

    def get_text(self, url, referer=None):
        self.appels.append(url)
        return self.pages.get(url)


class AdapteurTest(FazwazAdapter):
    def _parse_list_page(self, html):                  # le HTML de test EST la liste d'URL
        return [{"source_url": u, "source_id": u.rsplit("-u", 1)[1], "deal_type": "rent"}
                for u in html.split()]


def adapt(pages_max):
    cfg = dict(CFG, list_complement_max_pages=pages_max,
               searches=[{"path": "/condo-for-rent/thailand/bangkok", "deal_type": "rent"}])
    return AdapteurTest(cfg)


def test_n_emet_que_labsent_du_sitemap():
    base = "https://www.fazwaz.com/condo-for-rent/thailand/bangkok"
    connu, neuf = U.format(1, 100), U.format(2, 200)
    hors = "https://www.fazwaz.com/property-rent/2-bedroom-condo-for-rent-at-x-in-phuket-u300"
    f = FauxFetcher({base: f"{connu} {neuf} {hors}", base + "?page=2": f"{neuf}"})
    sortie = list(adapt(25)._complement_liste(f, {connu}))
    assert [s["source_url"] for s in sortie] == [neuf], sortie     # connu, doublon, hors Bangkok écartés
    assert f.appels[-1].endswith("?page=3"), f.appels             # s'arrête à la 1re page vide


def test_desactive_a_zero():
    f = FauxFetcher({})
    assert list(adapt(0)._complement_liste(f, set())) == [] and f.appels == []


def test_limit_pas_de_complement():
    base = "https://www.fazwaz.com/condo-for-rent/thailand/bangkok"
    a = adapt(25)
    a._stub_sitemap = lambda e: None
    a._entrees_sitemap = lambda f: []
    f = FauxFetcher({base: U.format(2, 200)})
    assert list(a._list_urls_sitemap(f, limit=5)) == [] and f.appels == []


if __name__ == "__main__":
    test_n_emet_que_labsent_du_sitemap()
    test_desactive_a_zero()
    test_limit_pas_de_complement()
    print("3/3 ok")
