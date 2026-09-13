"""test_fazwaz_sitemap.py — verrouiller le mode de découverte par sitemap de FazWaz.

POURQUOI CE TEST EXISTE
Le 2026-09-12, robots.txt de fazwaz.com a interdit `order_by=` : le tri par
fraîcheur qui faisait tenir le catalogue dans 150 pages est devenu illégal,
et FazWaz (vente + location + couloirs) est tombé en bloc. Le remplacement
lit `sitemap-listings.xml` (déclaré par ce même robots.txt) et prend prix,
surface, SDB et coordonnées sur la FICHE au lieu de la page de liste. Trois
choses à verrouiller, chacune mesurée sur le site réel le 2026-09-13 :
  1. le parsing du sitemap (filtre Bangkok/condo, deal_type, id, lastmod,
     tri fraîcheur d'abord) ;
  2. la lecture de la fiche (meta title/description, :lat/:lng) — sans
     elle on écrirait des annonces sans prix ;
  3. la règle de tri `trier()` : présente = vivante, lastmod > last_seen =
     à rouvrir, fenêtre seulement pour ce qu'on ne suit pas encore.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_fazwaz_sitemap.py
"""
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "scraper"))

from adapters.fazwaz import FazwazAdapter, TITLE_RE          # noqa: E402
from pipeline import sitemap                                  # noqa: E402

INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://www.fazwaz.com/sitemaps-listings/www.fazwaz.com-0.xml</loc>
    <lastmod>2026-09-13T02:03:53+07:00</lastmod></sitemap>
</sitemapindex>"""

SHARD = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
<url><loc>https://www.fazwaz.com/property-sales/2-bedroom-condo-for-sale-at-aspire-sathorn-taksin-priva-in-bang-kho-bangkok-u6741301</loc>
<lastmod>2026-09-10T09:10:52+07:00</lastmod>
<image:image><image:loc>https://cdn.fazwaz.com/x/263x170/unit/6741301/1.jpg</image:loc></image:image></url>
<url><loc>https://www.fazwaz.com/property-rent/studio-condo-for-rent-at-the-link-sukhumvit-50-in-phra-khanong-bangkok-u6440858</loc>
<lastmod>2026-09-13T01:31:38+07:00</lastmod></url>
<url><loc>https://www.fazwaz.com/property-sales/4-bedroom-villa-for-sale-in-maret-surat-thani-u6676374</loc>
<lastmod>2026-09-13T01:31:38+07:00</lastmod></url>
<url><loc>https://www.fazwaz.com/property-sales/1-bedroom-condo-for-sale-at-x-in-mahasawat-nonthaburi-u1</loc>
<lastmod>2026-09-13T01:31:38+07:00</lastmod></url>
</urlset>"""

FICHE = """<html><head>
<meta name="title" content="2 Bedroom Condo for Sale at Aspire Sathorn-Taksin Priva for &#3647;4,045,300 | U6741301" />
<meta name="description" content="This property is a 45 SqM condo with 2 bedrooms and 1 bathroom that is available for sale." />
</head><body><location-matrix :lat="13.7128744" :lng="100.4635746" type="unit"></location-matrix>
<img src="https://cdn.fazwaz.com/wbr/abc/1024x768/gallery/1/photo.jpg"></body></html>"""


class FauxFetcher:
    def __init__(self, pages):
        self.pages, self.vues = pages, []

    def get_text(self, url, referer=None):
        self.vues.append(url)
        return self.pages.get(url)

    def allowed(self, url):
        return True


def _adapter(tmp, deal_types=("sale", "rent")):
    cfg = {"base_url": "https://www.fazwaz.com", "discovery": "sitemap",
           "sitemap_index": "https://www.fazwaz.com/sitemap-listings.xml",
           "sitemap_cache_minutes": 0,
           "sitemap_cache": os.path.join(tmp, "sitemap.json"),   # jamais le cache réel
           "searches": [{"path": "/x", "deal_type": d} for d in deal_types],
           "image": {"max_per_listing": 1}}
    a = FazwazAdapter(cfg)
    assert a.config["fetch_detail"] is True, "le mode sitemap doit forcer fetch_detail"
    return a


def test_parsing_et_tri():
    assert sitemap.parse_index(INDEX) == [
        "https://www.fazwaz.com/sitemaps-listings/www.fazwaz.com-0.xml"]
    entrees = sitemap.parse_shard(SHARD)
    assert len(entrees) == 4 and entrees[0]["image"].endswith("1.jpg") and entrees[1]["image"] is None

    with tempfile.TemporaryDirectory() as tmp:
        a = _adapter(tmp)
        f = FauxFetcher({a.config["sitemap_index"]: INDEX,
                         "https://www.fazwaz.com/sitemaps-listings/www.fazwaz.com-0.xml": SHARD})
        stubs = list(a.list_urls(f))
        # villa + Nonthaburi écartées, condos Bangkok gardés, plus frais d'abord
        assert [s["source_id"] for s in stubs] == ["6440858", "6741301"], stubs
        assert stubs[0]["deal_type"] == "rent" and stubs[0]["bedrooms"] == 0
        assert stubs[1]["deal_type"] == "sale" and stubs[1]["bedrooms"] == 2
        assert stubs[1]["condo_name"] == "Aspire Sathorn Taksin Priva"   # provisoire, aplati
        assert stubs[1]["lastmod"] == "2026-09-10T09:10:52+07:00" and stubs[1]["price"] is None
        # deal_type filtré par les `searches` (run.py --deal-type)
        a2 = _adapter(tmp, deal_types=("sale",))
        assert [s["source_id"] for s in a2.list_urls(f)] == ["6741301"]
        # --limit respecté
        assert len(list(a.list_urls(f, limit=1))) == 1


def test_fiche_complete_le_stub():
    with tempfile.TemporaryDirectory() as tmp:
        a = _adapter(tmp)
    url = "https://www.fazwaz.com/property-sales/2-bedroom-condo-for-sale-at-aspire-sathorn-taksin-priva-in-bang-kho-bangkok-u6741301"
    stub = a._stub_sitemap({"url": url, "lastmod": "2026-09-10T09:10:52+07:00", "image": None})
    rec = a.parse_listing(FauxFetcher({url: FICHE}), stub)
    assert rec["price"] == 4045300 and rec["area_sqm"] == 45.0 and rec["bathrooms"] == 1
    assert rec["bedrooms"] == 2 and rec["condo_name"] == "Aspire Sathorn-Taksin Priva"  # nom EXACT
    assert (rec["lat"], rec["lng"]) == (13.7128744, 100.4635746)
    assert rec["image_urls"] == ["https://cdn.fazwaz.com/wbr/abc/1024x768/gallery/1/photo.jpg"]
    assert rec["title"] == "2BR condo — Aspire Sathorn-Taksin Priva"
    assert rec["raw_data"]["lastmod"] == "2026-09-10T09:10:52+07:00"
    # description rédigée par l'agent (sans SqM) → repli sur le bloc d'infos
    fiche2 = FICHE.replace("This property is a 45 SqM condo with 2 bedrooms and 1 bathroom that is available for sale.",
                           "River view corner unit on 26th floor.") + \
        '<div>118 SqM <small>Size</small></div><div>2 <small> Bathrooms </small></div>'
    rec2 = a.parse_listing(FauxFetcher({url: fiche2}), a._stub_sitemap({"url": url, "lastmod": None, "image": None}))
    assert rec2["area_sqm"] == 118.0 and rec2["bathrooms"] == 2, (rec2["area_sqm"], rec2["bathrooms"])
    # loyer « ฿28,000/mo » et fiche sans prix
    t = TITLE_RE.match("Studio Condo for Rent at Plum Condo Sukhumvit 97.1 for ฿10,000/mo | U5647513")
    assert t and t.group(1) == "Studio" and t.group("price") == "10,000"
    t = TITLE_RE.match("1 Bedroom Condo for Sale at Noble Refine | U1398028")
    assert t and t.group("price") is None and t.group("name") == "Noble Refine"
    # fiche injoignable, aucun prix connu → None + marqueur pour run.py
    stub2 = a._stub_sitemap({"url": url, "lastmod": None, "image": None})
    assert a.parse_listing(FauxFetcher({}), stub2) is None and stub2["_indisponible"] is True


def test_trier():
    now = datetime(2026, 9, 13, tzinfo=timezone.utc)
    frais, vieux = "2026-09-12T10:00:00+07:00", "2026-05-01T10:00:00+07:00"
    vu_avant = {"status": "active", "last_seen": "2026-09-11T18:00:00+00:00"}   # < frais
    vu_apres = {"status": "active", "last_seen": "2026-09-12T18:00:00+00:00"}   # > frais
    T = lambda ex, lm, budget=True, img=True: sitemap.trier(ex, lm, 60, budget, img, now)  # noqa: E731
    # inconnue : fenêtre puis budget
    assert T(None, frais) == "visiter" and T(None, frais, budget=False) == "reporter"
    assert T(None, vieux) == "ignorer"
    # active, rien de neuf → confirmée quel que soit l'âge (présente = vivante)
    assert T(vu_apres, frais) == "confirmer" and T(vu_apres, vieux) == "confirmer"
    # active mise à jour depuis notre passage → à rouvrir ; sans budget on NE touche PAS
    assert T(vu_avant, frais) == "visiter" and T(vu_avant, frais, budget=False) == "reporter"
    # active sans photos : on rouvre si on peut, sinon on confirme quand même
    assert T(vu_apres, frais, img=False) == "visiter"
    assert T(vu_apres, frais, budget=False, img=False) == "confirmer"
    # délistée chez nous : fenêtre, puis budget, puis confirmation si rien de neuf
    inact = {"status": "inactive", "last_seen": "2026-09-12T18:00:00+00:00"}
    assert T(inact, vieux) == "ignorer" and T(inact, frais) == "visiter"
    assert T(inact, frais, budget=False) == "confirmer"
    assert T({"status": "inactive", "last_seen": "2026-09-01T00:00:00+00:00"}, frais, budget=False) == "reporter"
    # sans lastmod on ne sait rien → visite
    assert T(vu_apres, None) == "visiter"
    assert sitemap.deja_vu_depuis(None, frais) is False


if __name__ == "__main__":
    test_parsing_et_tri()
    test_fiche_complete_le_stub()
    test_trier()
    print("OK — test_fazwaz_sitemap : 3/3")
