"""test_social_calibrage.py — verrouiller le calibrage des annonces Facebook.

POURQUOI CE TEST EXISTE
Le 2026-09-30, 29 % des lignes de social_leads étaient des doublons du même
bien (posté dans plusieurs groupes ou par plusieurs agents) : la clé
`lead_id` hachait le texte ET le groupe. `social_calibrage.py` marque les
doublons par caractéristiques, les fiches implausibles et la présence sur
les plateformes. À verrouiller :
  1. deux annonces du même bien (groupes/auteurs différents, ±2 m², ±5 %)
     fusionnent ; un autre étage de prix ou une autre chambre, non ;
  2. la tête de groupe est la PREMIÈRE vue ;
  3. rien n'est supprimé : les lignes restent, les vues filtrent ;
  4. les drapeaux d'exclusion (bornes, loyer/m² aberrant) sortent la ligne
     de la vue des uniques, pas de la table ;
  5. le chargeur complet (load_social_leads --sqlite) déclenche le calibrage
     et archive l'entonnoir ;
  6. COLS du chargeur n'a pas bougé (la voie Supabase ne connaît pas les
     nouvelles colonnes).

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_social_calibrage.py
"""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scraper"))
import social_calibrage as sc                                   # noqa: E402
import load_social_leads as lsl                                  # noqa: E402

COLS_AVANT = ["id", "source", "source_group", "source_url", "posted_at", "author", "deal_type",
              "property_type", "price", "rent_monthly", "area_sqm", "bedrooms", "bathrooms",
              "condo_name_raw", "station", "district_raw", "furnished", "seller_type", "quota",
              "condo_name", "match_score", "khet", "lat", "lng", "median_rent_condo",
              "median_sale_condo", "deviation_pct", "confidence", "raw_text"]
assert lsl.COLS == COLS_AVANT, "COLS a changé : la voie Supabase casserait"
print("6. colonnes du chargeur inchangées : OK")


def lead(i, **kw):
    r = {"id": f"facebook:g:{i}", "source_group": "g1", "author": "A", "deal_type": "rent",
         "condo_name": "Test Tower", "condo_name_raw": "Test Tower", "bedrooms": 1.0,
         "area_sqm": 35.0, "rent_monthly": 20000.0, "price": None, "confidence": 4.0,
         "first_seen": f"2026-09-{10 + i:02d} 00:00:00"}
    r.update(kw)
    return r


# 1-2. regroupement
L = [lead(1), lead(2, source_group="g2", author="B", area_sqm=36.5, rent_monthly=20900),
     lead(3, rent_monthly=26000), lead(4, bedrooms=2.0), lead(5, condo_name=None, condo_name_raw="Autre")]
canon = sc.grouper(L)
assert canon["facebook:g:2"] == "facebook:g:1", "même bien, autre groupe/auteur : fusion"
assert canon["facebook:g:3"] == "facebook:g:3", "loyer +30 % : autre bien"
assert canon["facebook:g:4"] == "facebook:g:4", "autre nombre de chambres : autre bien"
assert canon["facebook:g:5"] == "facebook:g:5"
assert sc.grouper(list(reversed(L)))["facebook:g:2"] == "facebook:g:1", "tête = première vue"
print("1-2. doublons par caractéristiques, tête = première vue : OK")

# 4. drapeaux
vide = {"on_platforms": None, "platform_ids": [], "ref_n": 0, "ref_median_psqm": None, "deviation_psqm_pct": None}
assert "hors_bornes" in sc._drapeaux(lead(9, rent_monthly=2000), vide)
assert "loyer_m2_aberrant" in sc._drapeaux(lead(9, rent_monthly=90000, area_sqm=30), vide)
assert "ecart_suspect" in sc._drapeaux(lead(9), dict(vide, ref_n=5, deviation_psqm_pct=-55.0))
assert sc._drapeaux(lead(9), dict(vide, ref_n=5, deviation_psqm_pct=-5.0)) == []
print("4. drapeaux de qualité : OK")

# 3 + 5. bout en bout sur une base temporaire, via le vrai chargeur
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    fiche = {"est_une_annonce": True, "type_transaction": "location", "type_bien": "condo",
             "prix_vente_thb": 0, "loyer_mensuel_thb": 20000, "surface_sqm": 35, "chambres": 1,
             "salles_de_bain": 1, "nom_immeuble": "Test Tower", "station_proche": "", "quartier": "",
             "meuble": True, "confiance": 4, "vendeur": "agent", "quota": "inconnu",
             "auteur": "A", "date": None, "lien": "l1", "groupe": "g1", "texte": "Test Tower 1BR 35 sqm 20,000"}
    fiches = [fiche,
              dict(fiche, groupe="g2", auteur="B", lien="l2", texte="Test Tower 1 bed 35.5 sqm 20,500/month"),
              dict(fiche, loyer_mensuel_thb=1500, lien="l3", texte="Test Tower 1500"),     # hors bornes
              dict(fiche, type_bien="maison", lien="l4", texte="House"),                  # rejet entonnoir
              dict(fiche, surface_sqm=0, lien="l5", texte="Test Tower sans surface")]     # rejet entonnoir
    src = tmp / "immo_test_extrait_resolu.json"
    src.write_text(json.dumps(fiches, ensure_ascii=False), encoding="utf-8")
    env = dict(os.environ, LOWI_SOCIAL_DB=str(tmp / "s.db"), LOWI_CALIB_DIR=str(tmp / "calib"),
               PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "scraper" / "load_social_leads.py"), str(src), "--sqlite"],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=ROOT)
    assert r.returncode == 0, r.stderr[-800:]
    assert "→ 3 uniques" in r.stdout, r.stdout      # lu par agents/bots/social_leads.charger()
    con = sqlite3.connect(tmp / "s.db")
    assert con.execute("select count(*) from social_leads").fetchone()[0] == 3, "rien n'est supprimé"
    assert con.execute("select count(*) from social_leads_uniques").fetchone()[0] == 1, \
        "doublon marqué + hors bornes exclu de la vue"
    assert con.execute("select count(*) from social_leads where dedup_of is not null").fetchone()[0] == 1
    run = json.loads(con.execute("select stats from calibration_runs").fetchone()[0])
    ent = run["entonnoir_dernier_chargement"]
    assert ent["retenue"] == 3 and ent["pas_un_condo"] == 1 and ent["sans_surface"] == 1, ent
    assert "sensibilite_doublons_lignes_en_trop" in run
    assert list((tmp / "calib").glob("calibrage-*.json")), "statistiques archivées en JSON"
    con.close()
print("3-5. chargeur → calibrage → vues + entonnoir archivé, aucune ligne supprimée : OK")
print("TOUS LES ESSAIS PASSENT")
