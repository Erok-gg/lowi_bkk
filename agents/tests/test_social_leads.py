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

# 5. panne d'authentification du CLI (2026-09-23 → 09-29 : 162 appels en
#    échec, cause tronquée, 6 constats « le modèle n'a rien rendu » par cycle)
import json as _json, subprocess as _sp, types
sortie_reelle = _json.dumps({"is_error": True, "total_cost_usd": 0, "usage": {"x": "y" * 400},
                             "result": "Failed to authenticate: OAuth session expired and could not be refreshed"})
orig_run = sl.subprocess.run
sl.subprocess.run = lambda *a, **k: types.SimpleNamespace(returncode=1, stdout=sortie_reelle, stderr="")
try:
    try:
        sl.appeler_claude("x")
        raise AssertionError("aurait dû lever")
    except sl.AuthClaudeExpiree as e:
        assert "OAuth session expired" in str(e), "la cause doit survivre à la troncature"
    # une autre erreur reste un échec de lot ordinaire, cause lisible
    sl.subprocess.run = lambda *a, **k: types.SimpleNamespace(
        returncode=1, stdout=_json.dumps({"is_error": True, "usage": {"x": "y" * 400}, "result": "Overloaded"}), stderr="")
    try:
        sl.appeler_claude("x")
        raise AssertionError("aurait dû lever")
    except sl.AuthClaudeExpiree:
        raise AssertionError("Overloaded n'est pas une panne d'auth")
    except RuntimeError as e:
        assert "Overloaded" in str(e)
finally:
    sl.subprocess.run = orig_run

nb = []
def appel_auth(prompt):
    nb.append(1)
    raise sl.AuthClaudeExpiree("Failed to authenticate: OAuth session expired")
try:
    sl.extraire(posts, appel=appel_auth, journal=lambda m: None)
    raise AssertionError("aurait dû remonter")
except sl.AuthClaudeExpiree:
    pass
assert len(nb) == 1, f"arrêt au premier lot, pas {len(nb)} appels"

class _Led:
    def __init__(self): self.f = []
    def finding(self, agent, sev, kind, msg, detail=None, run_id=None): self.f.append((sev, kind))
with tempfile.TemporaryDirectory() as tmp:
    d = pathlib.Path(tmp)
    for j in ("23", "24", "25"):
        (d / f"immo_2026-09-{j}.json").write_text(_json.dumps({"posts": posts[:2]}), encoding="utf-8")
    orig_out, orig_tf, orig_alert, orig_etat = sl.OUT, sl.traiter_fichier, sl.alert.alert, sl.etat_collecte_facebook
    mails = []
    sl.alert.alert = lambda agent, sujet, corps, severity="high": mails.append(sujet)
    sl.etat_collecte_facebook = lambda: None
    sl.OUT = d
    sl.traiter_fichier = lambda src, journal=print, appel=None: (_ for _ in ()).throw(
        sl.AuthClaudeExpiree("OAuth session expired"))
    try:
        led = _Led()
        sl.run(led, 0, "test", {})
    finally:
        sl.OUT, sl.traiter_fichier, sl.alert.alert, sl.etat_collecte_facebook = orig_out, orig_tf, orig_alert, orig_etat
    assert led.f == [("high", "claude_cli_non_authentifie")], led.f
    assert len(mails) == 1, f"un mail pour la panne d'auth, pas {len(mails)}"
print("5. panne d'auth : cause conservée, arrêt immédiat, UN constat haut : OK")

# 6. collecte Facebook impossible → UN mail par cycle (demandé le 2026-09-30).
#    La sonde est écrite par facebook/agent.js ; une collecte à 0 post n'écrit
#    aucun immo_*.json, donc seule la sonde voit une session perdue.
from datetime import datetime, timezone, timedelta
maintenant = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
def sonde(**kw):
    base = {"horodatage": "2026-10-01T01:14:46.862Z", "ok": True, "groupes_en_panne": [],
            "groupes": [{"group": "g1", "containers": 300, "posts": 25}], "deconnecte": False, "posts_total": 25}
    base.update(kw); return base
cas = {
    "normal": (sonde(), None),
    "deconnecte": (sonde(deconnecte=True, posts_total=0,
                         groupes=[{"group": "g1", "containers": 0, "posts": 0, "deconnecte": True}]), "DÉCONNECTÉ"),
    "zero_post": (sonde(posts_total=0, groupes=[{"group": "g1", "containers": 0, "posts": 0}]), "0 post"),
    "ancienne_sonde_sans_champs": ({"horodatage": "2026-10-01T01:14:46Z", "ok": True,
                                    "groupes": [{"group": "g1", "containers": 0, "posts": 0}]}, "0 post"),
    "dom_casse": (sonde(ok=False, groupes_en_panne=["g1"]), "structure"),
    "perimee": (sonde(horodatage="2026-09-29T01:00:00Z"), "n'a pas abouti"),
}
orig_sonde = sl.SONDE_FB
with tempfile.TemporaryDirectory() as tmp:
    sl.SONDE_FB = pathlib.Path(tmp) / "sonde-immo.json"
    try:
        assert "jamais abouti" in sl.etat_collecte_facebook(maintenant), "sonde absente"
        for nom, (contenu, attendu) in cas.items():
            sl.SONDE_FB.write_text(_json.dumps(contenu), encoding="utf-8")
            r = sl.etat_collecte_facebook(maintenant)
            assert (r is None) if attendu is None else (r and attendu in r), (nom, r)
        # bout en bout : run() sur une session perdue → 1 constat haut + 1 mail, aval non bloqué
        sl.SONDE_FB.write_text(_json.dumps(cas["deconnecte"][0]), encoding="utf-8")
        orig_alert, orig_out = sl.alert.alert, sl.OUT
        mails = []
        sl.alert.alert = lambda agent, sujet, corps, severity="high": mails.append((sujet, corps))
        sl.OUT = pathlib.Path(tmp)
        try:
            led = _Led()
            orig_now = sl.datetime
            m = sl.run(led, 0, "test", {})
        finally:
            sl.alert.alert, sl.OUT = orig_alert, orig_out
        assert ("high", "facebook_collecte_ko") in led.f, led.f
        assert len(mails) == 1 and "DÉCONNECTÉ" in mails[0][1], mails
    finally:
        sl.SONDE_FB = orig_sonde
print("6. collecte Facebook impossible (déconnecté, 0 post, DOM, périmée) → 1 mail : OK")
print("TOUS LES ESSAIS PASSENT")
