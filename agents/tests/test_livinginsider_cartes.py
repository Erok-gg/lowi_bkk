"""test_livinginsider_cartes.py — lecture des cartes de liste LivingInsider.

POURQUOI CE TEST EXISTE (2026-10-20)
1. La source a tourné « ok » à 0 annonce du 25/09 au 20/10 : le challenge AWS
   WAF (202, ~2 Ko) arrivait à l'adaptateur comme une page normale et sortait
   par le même chemin qu'une annonce hors Bangkok. `est_challenge` doit le
   reconnaître, et une liste bloquée doit être déclarée, pas tue.
2. Le nom d'immeuble lu par position dans le texte valait « Condo » (étiquette
   de catégorie) sur 1 carte sur 6, dès que le titre affiché différait de son
   attribut (emoji, double espace). On le lit dans le DOM.
3. Une carte « boostée » se répète de page en page : une seule occurrence.
4. Un type d'annonce bloqué (location) ne doit pas être délisté par --full.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_livinginsider_cartes.py
"""
import os
import sqlite3
import sys
import tempfile

for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "scraper"))

from adapters.livinginsider import LivinginsiderAdapter, est_challenge  # noqa: E402

BASE = "https://www.livinginsider.com"


def carte(id_, titre_attr, titre_txt, immeuble, beds="1", prix="฿ 4,500,000", kind="Sell"):
    """Gabarit d'une carte réelle (relevée le 2026-10-20), classes retirées."""
    return f"""
<div><div><a href="/en/detail/condo-for-sale-x-{id_}"></a>
<img alt="x" src="https://image.livinginsider.com/upload/topic3337/{id_}.jpeg">
<button aria-label="view-profile"><img src="https://image.livinginsider.com/upload/mod_member/a.png"></button></div>
<a href="/en/detail/condo-for-sale-x-{id_}"><div><div><span>Condo</span><span>{kind}</span></div>
<p title="{titre_attr}">{titre_txt}</p><div><div><span>{immeuble} </span></div>
<div><div><span><span aria-hidden="true"></span>{beds}</span><span><span aria-hidden="true"></span>1</span>
<span><span aria-hidden="true"></span>Fl. 11-20</span><span><span aria-hidden="true"></span>35.5 Sq.m.</span></div></div></div></div>
<div><p>{prix}</p><span>(126,760 baht/sq.m.)</span></div><div><span>Boosted 2 hours ago</span><span>1</span></div></a></div>
"""


CHALLENGE = ('<!DOCTYPE html><html><head><title></title><script type="text/javascript">'
             'window.awsWafCookieDomainList = [];</script></head><body></body></html>')

P1 = "<html><body>" + carte(101, "Life Ladprao 🔥", "Life Ladprao  🔥", "Life Ladprao") \
     + carte(102, "Studio deal", "Studio deal", "The Room Phayathai", beds="Studio", prix="฿ 2,850,000") \
     + carte(103, "Pattaya", "Pattaya", "Copacabana Beach Jomtien") + "x" * 30_000 + "</body></html>"
P2 = "<html><body>" + carte(101, "Life Ladprao 🔥", "Life Ladprao  🔥", "Life Ladprao") \
     + carte(104, "Ari", "Ari", "Via ARI", beds="2", prix="฿ 19,900,000")      + carte(105, "2BR | ฿39.9M", "2BR | ฿39.9M", "Life Ladprao", kind="Sell&amp;Rent",
             prix="฿ 5.6M</p><span>Sell (98,992 baht/sq.m.)</span><p>฿ 22K /mo") + "x" * 30_000 + "</body></html>"
PAGES = {BASE + "/en/condo-buysell": P1, BASE + "/en/condo-buysell/2": P2,
         BASE + "/en/condo-buysell/3": P2,        # page identique → fin de pagination
         BASE + "/en/condo-rent": CHALLENGE}


class FauxFetcher:
    def __init__(self):
        self.urls = []

    def get_text(self, url, referer=None):
        self.urls.append(url)
        return PAGES.get(url, "")


def referentiel(chemin):
    db = sqlite3.connect(chemin)
    db.execute("create table listings (source, condo_name, khet, lat, lng, id, status, deal_type)")
    db.executemany("insert into listings values (?,?,?,?,?,?,?,?)", [
        ("ddproperty", "Life Ladprao", "Chatuchak District", 13.81, 100.56, "d1", "active", "sale"),
        ("fazwaz", "The Room Phayathai", "Ratchathewi District", 13.75, 100.53, "f1", "active", "sale"),
        ("fazwaz", "Via ARI, Bangkok", "Phaya Thai District", 13.78, 100.54, "f2", "active", "sale"),
    ])
    db.commit()
    db.close()


def config(ref_db):
    return {"source": "livinginsider", "base_url": BASE, "max_pages": 5, "mode": "liste",
            "referentiel_db": ref_db,
            "searches": [
                {"path_first": "/en/condo-buysell", "path": "/en/condo-buysell/{page}", "deal_type": "sale"},
                {"path_first": "/en/condo-rent", "path": "/en/condo-rent/{page}", "deal_type": "rent"}]}


# ---- 1. challenge reconnu, vraie page non
assert est_challenge(CHALLENGE)
assert not est_challenge(P1), "une vraie page (> 20 Ko) ne doit pas passer pour un challenge"
assert not est_challenge("")
print("est_challenge : OK")

with tempfile.TemporaryDirectory() as tmp:
    ref_db = os.path.join(tmp, "ref.db")
    referentiel(ref_db)
    ad = LivinginsiderAdapter(config(ref_db))
    f = FauxFetcher()

    # ---- 2. sonde : cartes lisibles sur la vente
    ok, diag = ad.sonder(f)
    assert ok, diag
    print(f"sonde : {diag}")

    stubs = list(ad.list_urls(f))
    par_id = {s["source_id"]: s for s in stubs if s["deal_type"] == "sale"}

    # ---- 3. dédup des boostées + filtre référentiel
    assert sorted(par_id) == ["LV101", "LV102", "LV104", "LV105"], sorted(par_id)
    assert len(stubs) == 5, f"attendu 5 (dont LV105 vente + location), obtenu {len(stubs)}"
    print("dédup boostées + filtre Bangkok (Pattaya écartée) : OK")

    # ---- 3b. carte Sell&Rent : deux annonces, prix en M/K, titre « ฿39.9M » ignoré
    sr = {s["deal_type"]: s for s in stubs if s["source_id"] == "LV105"}
    assert sr["sale"]["price"] == 5_600_000, sr["sale"]["price"]
    assert sr["rent"]["price"] == 22_000, sr["rent"]["price"]
    assert sr["sale"]["_prix_arrondi"] and not par_id["LV101"]["_prix_arrondi"]
    print("Sell&Rent : vente 5,6 M + loyer 22 K, OK")

    # ---- 4. lecture des champs ; nom d'immeuble malgré le titre divergent
    s = par_id["LV101"]
    assert s["condo_name"] == "Life Ladprao", s["condo_name"]
    assert (s["price"], s["area_sqm"], s["bedrooms"], s["bathrooms"]) == (4_500_000, 35.5, 1, 1), s
    assert s["district"] == "Chatuchak District" and s["lat"] == 13.81
    assert s["image_urls"] == [f"{BASE.replace('www', 'image')}/upload/topic3337/101.jpeg"], s["image_urls"]
    assert par_id["LV102"]["bedrooms"] == 0, "Studio = 0 chambre"
    assert par_id["LV104"]["district"] == "Phaya Thai District", "suffixe ', Bangkok' non normalisé"
    rec = ad.parse_listing(f, s)
    assert rec["raw_data"]["coords"] == "referentiel_immeuble"
    assert not any(k.startswith("_") for k in rec), "champ interne fuité dans l'enregistrement"
    print("lecture des cartes : OK")

    # ---- 5. location bloquée : déclarée, et protégée du délistage
    assert ad._etat()["bloques"] == {"rent"}
    assert not any(u.startswith(BASE + "/en/condo-rent/") for u in f.urls), \
        "on a insisté après un challenge"

    class FauxStore:
        def __init__(self):
            self.db = sqlite3.connect(":memory:")
            self.db.execute("create table listings (id, source, status, deal_type, condo_name)")
            self.db.executemany("insert into listings values (?,?,?,?,?)", [
                ("livinginsider:rent:LV9", "livinginsider", "active", "rent", "Life Ladprao"),
                ("livinginsider:sale:LV8", "livinginsider", "active", "sale", "Hors Ref Tower"),
                ("livinginsider:sale:LV7", "livinginsider", "active", "sale", "Life Ladprao"),
            ])

        def ids_actifs(self, source, deal_type=None):
            q = "select id from listings where source=? and status='active'"
            p = [source]
            if deal_type:
                q += " and deal_type=?"
                p.append(deal_type)
            return {r[0] for r in self.db.execute(q, p)}

    prot = ad.ids_hors_couverture(FauxStore(), None)
    assert prot == {"livinginsider:rent:LV9", "livinginsider:sale:LV8"}, prot
    print("couverture : location bloquée + immeuble hors référentiel protégés, OK")

print("test_livinginsider_cartes : OK")
