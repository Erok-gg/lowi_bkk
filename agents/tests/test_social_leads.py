"""test_social_leads.py — verrouiller l'aval automatique de la collecte Facebook.

POURQUOI CE TEST EXISTE
Le 2026-09-13, l'audit a trouvé que rien ne lisait les collectes Facebook :
la « routine Claude/Haiku » annoncée le 12/09 n'existait pas. L'agent
`social-leads` remplace immo-extract.mjs (Ollama, absent de PC2) par des
appels `claude -p` en lots. Trois choses à verrouiller sans appeler le modèle :
  1. le parsing tolérant de la réponse (fences, index manquants, objet cassé)
     — un lot mal formé compte des échecs, ne fait pas tomber l'agent ;
  2. les décisions du CODE sur `vendeur` et `quota` (port des regex de
     immo-extract.mjs : le modèle inventait un propriétaire par défaut) ;
  3. le découpage en lots et le format de sortie, identique à immo-extract
     (immo-resolve et load_social_leads ne doivent voir aucune différence).

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_social_leads.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.bots import social_leads as sl                # noqa: E402

# 1. parsing tolérant
rep = '```json\n[{"index": 2, "est_une_annonce": true}, {"index": 1, "est_une_annonce": false}, "poubelle"]\n```'
objs = sl.parser_reponse(rep, 3)
assert objs[0] == {"index": 1, "est_une_annonce": False} and objs[1]["index"] == 2 and objs[2] is None
assert sl.parser_reponse("pas de json", 2) == [None, None]
assert sl.parser_reponse('[{"a":1}, {"b":2}]', 2)[1] == {"b": 2}, "sans index : position"
print("1. parsing tolérant (fences, index, objet cassé) : OK")

# 2. décisions du code
post_agence = {"author": "Bangkok Prime Property", "content": "Noble Ploenchit 1BR 45 sqm 35,000/mo"}
post_proprio = {"author": "Somchai K", "content": "เจ้าของขายเอง Rhythm Asoke 2 โควตาต่างชาติ 4.2 ล้าน"}
post_neutre = {"author": "Ann", "content": "Life Asoke 1 bed 30 sqm 15,000"}
assert sl.deduire_vendeur(post_agence, "proprietaire") == "agent"
assert sl.deduire_vendeur(post_proprio, "agent") == "proprietaire"
assert sl.deduire_vendeur(post_neutre, "proprietaire") == "inconnu", "le modèle seul ne fait pas un propriétaire"
assert sl.deduire_vendeur(post_neutre, "agent") == "agent"
assert sl.deduire_quota(post_proprio) == "etranger" and sl.deduire_quota(post_neutre) == "inconnu"
assert sl.deduire_quota({"author": "", "content": "thai quota only"}) == "thai"
print("2. vendeur/quota tranchés par le code : OK")

# 3. lots + format de sortie
posts = [{"author": f"A{i}", "content": f"Condo {i} 1BR 30 sqm 15,000", "link": f"l{i}", "group": "g", "date": None}
         for i in range(sl.LOT + 3)]
appels = []

def faux_appel(prompt):
    n = prompt.count("### Annonce ")
    appels.append(n)
    objs = [{"index": i, "est_une_annonce": True, "type_transaction": "location", "type_bien": "condo",
             "prix_vente_thb": 0, "loyer_mensuel_thb": "15,000", "surface_sqm": 30.0, "chambres": 1,
             "salles_de_bain": 1, "nom_immeuble": f"Condo {i}", "station_proche": "", "quartier": "",
             "meuble": True, "vendeur": "proprietaire", "quota": "etranger", "confiance": 9}
            for i in range(1, n + 1)]
    objs.pop()                       # le dernier objet manque → 1 échec par lot
    import json
    return json.dumps(objs), 0.01

fiches, echecs, cout = sl.extraire(posts, appel=faux_appel, journal=lambda m: None)
assert appels == [sl.LOT, 3], appels
assert echecs == 2 and len(fiches) == len(posts) - 2 and abs(cout - 0.02) < 1e-9
f = fiches[0]
assert f["loyer_mensuel_thb"] == 15000 and f["surface_sqm"] == 30 and f["confiance"] == 5
assert f["vendeur"] == "inconnu" and f["quota"] == "inconnu", "modèle ignoré : pas de marqueur dans le texte"
assert set(sl.CHAMPS) <= set(f) and {"auteur", "date", "lien", "groupe", "texte"} <= set(f)
assert f["texte"] == posts[0]["content"] and f["lien"] == "l0"
print("3. lots de 15, échec par objet manquant, format immo-extract : OK")

# 4. l'état c'est le disque : seul le marqueur _charge.json (écrit APRÈS le
#    chargement) vaut "traité" — un _extrait_resolu.json produit à la main ne suffit pas
import tempfile, pathlib
with tempfile.TemporaryDirectory() as tmp:
    d = pathlib.Path(tmp)
    (d / "immo_2026-09-12.json").write_text("{}")
    (d / "immo_2026-09-12_extrait.json").write_text("[]")
    (d / "immo_2026-09-12_extrait_resolu.json").write_text("[]")
    (d / "immo_2026-09-12_charge.json").write_text("{}")
    (d / "immo_2026-09-13.json").write_text("{}")
    (d / "immo_2026-09-13_extrait.json").write_text("[]")
    (d / "immo_2026-09-13_extrait_resolu.json").write_text("[]")
    orig, sl.OUT = sl.OUT, d
    try:
        assert [p.name for p in sl.a_traiter()] == ["immo_2026-09-13.json"]
    finally:
        sl.OUT = orig
print("4. sélection des collectes à traiter par le disque : OK")
print("TOUS LES ESSAIS PASSENT")
