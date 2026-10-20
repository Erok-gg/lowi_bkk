"""test_ddproperty_blob_elague.py — DDproperty élague `listingsData` : on récupère, et la sonde ne ment plus.

POURQUOI CE TEST EXISTE (2026-10-21)
Dans la nuit du 19 au 20/10, DDproperty a cessé de servir la charge utile des
annonces dans `listingsData` tout en continuant à servir, pour les MÊMES
annonces, les blocs annexes `contactAgentCardData` / `enquiryModalData`,
indexés par identifiant. Mesuré le 2026-10-21 sur 16 pages réelles :
`listingsData` rendait **10/160 annonces en vente (6 %) et 2/160 en location
(1 %)**, `contactAgentCardData` **20/20 sur les 16 pages**. La veille (run 927
du ledger), le recensement voyait encore 18,5 annonces/page.

Deux défauts se sont révélés ce jour-là, et ce test verrouille les deux :

  1. **On perdait 94 à 99 % du catalogue.** `_parse_list` ne lisait que
     `listingsData`. Le complément par les cartes annexes récupère l'identité,
     l'URL, le prix, l'immeuble, les chambres et l'agent ; la surface, les SDB,
     l'adresse, la tenure et `postedOn` viennent de la fiche détail, que
     `fetch_detail` visite déjà et qui, elle, est intacte.

  2. **La sonde a dit OK en perdant 95 % de la page** (règle 2 : un garde-fou
     qui se tait quand ça va mal). La passe couloirs du 2026-10-20 a journalisé
     « sonde structure : OK — 1 stub obtenu » sur une page qui en portait 20,
     puis a scanné tout le catalogue à ce régime sans une alerte. La sonde
     compare désormais ce qu'elle extrait à ce que la page ELLE-MÊME annonce
     porter — une mesure prise sur la page du jour, pas un seuil arbitraire.

Et le garde-fou doit se taire quand tout va bien : une page saine, ou une page
qui annonce légitimement des annonces hors Bangkok (2 sur 200 le 2026-10-21,
des condos de Nakhon Ratchasima), ne doit pas déclencher la sonde.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_ddproperty_blob_elague.py
"""
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RACINE, "scraper"))

from adapters.ddproperty import DdpropertyAdapter             # noqa: E402

CFG = json.load(open(os.path.join(RACINE, "scraper", "config", "ddproperty.json"),
                     encoding="utf-8"))

echecs = []


def verifie(nom, condition, detail=""):
    print(f"  {'OK  ' if condition else 'ECHEC'} {nom}" + (f"  [{detail}]" if detail else ""))
    if not condition:
        echecs.append(nom)


def _url(slug, sid, deal="sale", ville="bangkok"):
    return f"https://www.ddproperty.com/en/property/{slug}-{ville}-for-{deal}-{sid}"


def _entree_listingsdata(sid, nom, deal="sale"):
    """Une annonce telle que `listingsData` la servait avant le 2026-10-20."""
    return {"listingData": {
        "id": sid,
        "url": _url(nom.lower().replace(" ", "-"), sid, deal),
        "fullAddress": f"{nom} Road, Khlong Tan, Vadhana, Bangkok",
        "price": {"value": 5000000, "pretty": "B5,000,000"},
        "bedrooms": 2, "bathrooms": 1, "floorArea": 55,
        "property": {"projectName": nom},
        "additionalData": {"tenure": "F"},
        "agent": {"id": 11, "agencyId": 22, "name": "Agent " + nom},
        "listerType": "agent",
    }}


def _carte_annexe(sid, nom, deal="sale", ville="Bangkok"):
    """La même annonce vue par `contactAgentCardData` (bloc resté complet)."""
    return {
        "localizedTitle": f"{nom}, {ville}",
        "propertyName": nom,
        "price": 5000000,
        "listingType": deal.upper(),
        "bedrooms": 2,
        "listerType": "agent",
        "url": _url(nom.lower().replace(" ", "-"), sid, deal, ville.lower().replace(" ", "-")),
        "agent": {"id": 11, "name": "Agent " + nom},
    }


def blob(listings, cartes):
    """Un `__NEXT_DATA__` de page de liste, réduit à ce que l'adaptateur lit."""
    return {"props": {"pageProps": {"pageData": {
        "resultCount": 50804,
        "data": {
            "listingsData": listings,
            "contactAgentCardData": {str(k): v for k, v in cartes.items()},
            "enquiryModalData": {str(k): {"listing": {"id": k}} for k in cartes},
            "paginationData": {"currentPage": 1, "totalPages": 2541},
        },
    }}}}


class FauxFetcher:
    """Rend toujours la même page de liste, sans réseau."""

    def __init__(self, html):
        self.html = html

    def get_text(self, url, referer=None):
        return self.html


def page_html(donnees):
    return ('<html><body><script id="__NEXT_DATA__" type="application/json">'
            + json.dumps(donnees) + "</script></body></html>")


A = DdpropertyAdapter(CFG)
NOMS = [f"Condo {i:02d}" for i in range(20)]
IDS = [500669000 + i for i in range(20)]

# ─────────────────────────────────────────────────────────────────────────
print("\n1. Page élaguée : listingsData vide, 20 cartes annexes")
# C'est exactement l'état mesuré le 2026-10-21 sur les pages 1 à 4 en vente.
elaguee = blob([], {sid: _carte_annexe(sid, nom) for sid, nom in zip(IDS, NOMS)})
stubs = A._parse_list(elaguee, "sale")
verifie("les 20 annonces sont récupérées malgré listingsData vide",
        len(stubs) == 20, detail=f"{len(stubs)} stubs")
verifie("chaque stub porte un identifiant et une URL",
        all(s.get("source_id") and s.get("source_url") for s in stubs))
verifie("les identifiants sont ceux de la page",
        {s["source_id"] for s in stubs} == {str(i) for i in IDS})
verifie("le prix est récupéré (il sert à la dédup incrémentale)",
        all(s.get("price") == 5000000 for s in stubs))
verifie("l'immeuble et les chambres sont récupérés",
        all(s.get("condo_name") and s.get("bedrooms") == 2 for s in stubs))
verifie("l'agent est récupéré (il tranche les doublons même-agent)",
        all(s.get("agent_id") == "11" for s in stubs))
# Ce que ce chemin NE porte PAS, et qu'il ne faut donc pas croire renseigné :
verifie("surface/SDB/tenure/adresse restent vides — la fiche détail les remplit",
        all(s.get("area_sqm") is None and s.get("bathrooms") is None
            and s.get("tenure") is None and s.get("khet") is None for s in stubs))

# ─────────────────────────────────────────────────────────────────────────
print("\n2. Page saine : listingsData complète, le chemin annexe ne double rien")
saine = blob([_entree_listingsdata(sid, nom) for sid, nom in zip(IDS, NOMS)],
             {sid: _carte_annexe(sid, nom) for sid, nom in zip(IDS, NOMS)})
stubs = A._parse_list(saine, "sale")
verifie("20 stubs, pas 40 — aucune annonce comptée deux fois", len(stubs) == 20,
        detail=f"{len(stubs)} stubs")
verifie("les identifiants restent uniques",
        len({s["source_id"] for s in stubs}) == 20)
verifie("la charge utile riche est conservée quand elle existe",
        all(s.get("area_sqm") == 55.0 and s.get("tenure") == "freehold"
            and s.get("khet") == "Vadhana" for s in stubs))

# ─────────────────────────────────────────────────────────────────────────
print("\n3. Page mixte : 3 annonces riches + 17 élaguées")
# L'état réel des pages 5, 7 et 8 en vente le 2026-10-21.
mixte = blob([_entree_listingsdata(sid, nom) for sid, nom in zip(IDS[:3], NOMS[:3])],
             {sid: _carte_annexe(sid, nom) for sid, nom in zip(IDS, NOMS)})
stubs = A._parse_list(mixte, "sale")
verifie("les 20 annonces sortent, sans doublon", len(stubs) == 20,
        detail=f"{len(stubs)} stubs")
riches = [s for s in stubs if s.get("area_sqm") is not None]
verifie("les 3 riches gardent leur surface (listingsData prime)", len(riches) == 3,
        detail=f"{len(riches)} riches")

# ─────────────────────────────────────────────────────────────────────────
print("\n4. Filtre province : une annonce hors Bangkok reste écartée")
# Mesuré le 2026-10-21 : 198 titres « …, Bangkok » et 2 « …, Nakhon Ratchasima »
# sur 200 cartes ; le slug de l'URL dit la même chose 200/200.
cartes = {sid: _carte_annexe(sid, nom) for sid, nom in zip(IDS[:5], NOMS[:5])}
cartes[IDS[0]] = _carte_annexe(IDS[0], NOMS[0], ville="Nakhon Ratchasima")
stubs = A._parse_list(blob([], cartes), "sale")
verifie("l'annonce de province n'entre pas", len(stubs) == 4, detail=f"{len(stubs)} stubs")
verifie("c'est bien celle de Nakhon Ratchasima qui manque",
        str(IDS[0]) not in {s["source_id"] for s in stubs})

# ─────────────────────────────────────────────────────────────────────────
print("\n5. La sonde se tait quand la page est entièrement extraite")
ok, msg = A.sonder(FauxFetcher(page_html(saine)))
verifie("page saine → sonde OK", ok, detail=msg)
ok, msg = A.sonder(FauxFetcher(page_html(elaguee)))
verifie("page élaguée mais entièrement récupérée → sonde OK", ok, detail=msg)
cartes = {sid: _carte_annexe(sid, nom) for sid, nom in zip(IDS[:5], NOMS[:5])}
cartes[IDS[0]] = _carte_annexe(IDS[0], NOMS[0], ville="Nakhon Ratchasima")
ok, msg = A.sonder(FauxFetcher(page_html(blob([], cartes))))
verifie("une annonce de province ne fait pas crier la sonde", ok, detail=msg)

# ─────────────────────────────────────────────────────────────────────────
print("\n6. La sonde parle quand la page porte plus que ce qu'on sait lire")
# LE DÉFAUT DU 2026-10-20 : « sonde OK — 1 stub obtenu » sur une page de 20.
# On simule l'étage suivant de la dégradation : les cartes annexes sont là
# (la page annonce donc 20 annonces) mais leur URL a disparu à son tour, si
# bien qu'une seule annonce reste lisible.
muettes = {sid: {k: v for k, v in _carte_annexe(sid, nom).items() if k != "url"}
           for sid, nom in zip(IDS, NOMS)}
muettes[IDS[0]] = _carte_annexe(IDS[0], NOMS[0])
ok, msg = A.sonder(FauxFetcher(page_html(blob([], muettes))))
verifie("1 annonce extraite sur 20 annoncées → sonde en ÉCHEC", not ok, detail=msg)
verifie("le diagnostic chiffre la perte", "1/20" in msg and "19" in msg, detail=msg)

# ─────────────────────────────────────────────────────────────────────────
print("\n7. La fiche détail rebouche ce que la carte annexe ne porte pas")
# Sans ce complément, les annonces reprises par les cartes annexes sortaient
# avec khwaeng, street, agency_id, posted_at et is_auto_repost à 0 %, contre
# 94-100 % la veille (4 962 annonces du 19-20/10). Concordance liste↔fiche
# vérifiée le 2026-10-21 sur 6 annonces : posted_at 6/6 à la seconde,
# agency_id 6/6, khwaeng 6/6, is_auto_repost 6/6, street 5/6.
fiche = {"props": {"pageProps": {"pageData": {"data": {
    "propertyOverviewData": {"propertyInfo": {
        "fullAddress": "19 Pridi Banomyong 14 Alley, Phra Kanong Nua, Watthana, Bangkok"}},
    "listingDetail": {"agencyId": 44502, "postedOn": {"unix": 1792527674},
                      "products": {"isAutoRepost": True},
                      "tenureCode": "F"},
    "listingLocationData": {"center": {"lat": 13.72, "lng": 100.58}},
}}}}}
html_fiche = page_html(fiche)
rec = {"source_url": "x", "deal_type": "sale", "khet": "Vadhana District"}
A._enrich_from_detail(html_fiche, rec)
verifie("le khwaeng est repris de la fiche", rec.get("khwaeng") == "Phra Kanong Nua",
        detail=str(rec.get("khwaeng")))
verifie("la rue est reprise de la fiche",
        rec.get("street") == "19 Pridi Banomyong 14 Alley", detail=str(rec.get("street")))
verifie("l'agence est reprise de la fiche", rec.get("agency_id") == "44502",
        detail=str(rec.get("agency_id")))
verifie("la date de publication est reprise de la fiche",
        (rec.get("posted_at") or "").startswith("2026-10-20T20:21:14"), detail=str(rec.get("posted_at")))
verifie("la republication automatique est reprise de la fiche",
        rec.get("is_auto_repost") is True, detail=str(rec.get("is_auto_repost")))
# LE PIÈGE : la fiche écrit « Watthana », le point-in-polygon écrit « Vadhana
# District ». Mélanger les deux orthographes scinderait les stats par quartier.
verifie("le khet N'EST PAS écrasé par l'orthographe de la fiche",
        rec.get("khet") == "Vadhana District", detail=str(rec.get("khet")))
rec2 = {"source_url": "x", "deal_type": "sale",
        "khwaeng": "Deja La", "street": "Deja Rue", "agency_id": "999",
        "posted_at": "2026-01-01T00:00:00+00:00", "is_auto_repost": False,
        "full_address": "deja renseigne"}
A._enrich_from_detail(html_fiche, rec2)
verifie("quand la liste a répondu, elle fait foi — rien n'est écrasé",
        (rec2["khwaeng"], rec2["street"], rec2["agency_id"], rec2["is_auto_repost"])
        == ("Deja La", "Deja Rue", "999", False))

print("\n8. Page vraiment vide de tout marqueur → échec, comme avant")
ok, msg = A.sonder(FauxFetcher(page_html(blob([], {}))))
verifie("ni listingsData ni cartes annexes → sonde en ÉCHEC", not ok, detail=msg)
ok, msg = A.sonder(FauxFetcher("<html><body>rien</body></html>"))
verifie("pas de __NEXT_DATA__ du tout → sonde en ÉCHEC", not ok, detail=msg)

if echecs:
    print(f"\n{len(echecs)} ECHEC(S) : {echecs}")
    raise SystemExit(1)
print("\nTOUS LES ESSAIS PASSENT")
