"""test_scores_tension_surveillance.py — scores-tension se tait quand tout va
bien, et appelle la réparation (constat HAUT) sur chaque défaut (2026-10-20).

Moteur simulé : le vrai calcul prend ~50 min. Rejeu :
  scraper/.venv/Scripts/python.exe agents/tests/test_scores_tension_surveillance.py
"""
import json
import os
import sys
from datetime import date, timedelta

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RACINE)
from agents.bots import scores_tension as st  # noqa: E402
from bilan_RE.tension import lot, __main__ as tmain  # noqa: E402


class FauxLedger:
    def __init__(self, precedent=None):
        self.constats, self.prec = [], precedent

    def finding(self, agent, sev, kind, sujet, details, run_id):
        self.constats.append((sev, kind))

    def last_run(self, nom, only_ok=False):
        return {"metrics": json.dumps(self.prec)} if self.prec else None


def source(gardee=True, sec=0, actives=5000):
    return {"gardee": gardee, "raisons": [] if gardee else ["x"], "actives_debut": actives,
            "actives_fin": actives, "retraits": 100, "jours_sans_retrait_fin": sec}


def resultat(dd=None, fz=None, erreurs=0, niveau="Vadhana District", liq=True):
    ch = {"tension": {"Bangkok": {"score": 50, "libelle": "balanced"},
                      niveau: {"score": 60, "libelle": "balanced"}},
          "liquidite": {"Bangkok": {"score": 55 if liq else None,
                                    "libelle": "balanced" if liq else "no reference yet"}}}
    return {"sources": {"ddproperty": dd or source(), "fazwaz": fz or source()},
            "immeubles": [{"par_chambres": {"1": ch}}] * 10,
            "_stats": {"immeubles": 10, "erreurs": erreurs, "duree_s": 1}}


def lancer(res, t1=None, prec=None):
    t1 = t1 or date.today()
    lot.calculer = lambda *a, **k: res
    lot.ecrire = lambda r: "faux.json"
    tmain._fin_par_defaut = lambda db: t1
    led = FauxLedger(prec)
    m = st.run(led, 1, "daily", {})
    return led.constats, m


def test_silence_si_tout_va_bien():
    c, m = lancer(resultat())
    assert c == [], c
    assert m["part_tension_fine"] == 100.0 and m["liquidite_publiees"] == 10
    # premier run sans métriques de référence : pas de régression inventée
    assert lancer(resultat(), prec={"immeubles": 10})[0] == []


def test_chaque_defaut_appelle_la_reparation():
    cas = {
        "delistage_a_l_arret": resultat(dd=source(sec=3)),
        "source_ecartee": resultat(fz=source(gardee=False)),
        "immeubles_en_erreur": resultat(erreurs=2),
    }
    for kind, res in cas.items():
        c, _ = lancer(res)
        assert c == [("high", kind)], (kind, c)
    c, _ = lancer(resultat(), t1=date.today() - timedelta(days=3))
    assert c == [("high", "fenetre_perimee")], c
    # 2 jours sans retrait : sous le seuil d'alerte
    assert lancer(resultat(dd=source(sec=2)))[0] == []
    # petite source figée : pas une grande source, pas d'alerte
    assert lancer(resultat(dd=source(sec=4, actives=100)))[0] == []


def test_regression_publication():
    prec = {"part_tension_fine": 100.0, "liquidite_publiees": 10}
    c, _ = lancer(resultat(niveau="CBD"), prec=prec)          # tout retombe à la zone
    assert ("high", "regression_publication") in c, c
    c, _ = lancer(resultat(liq=False), prec=prec)
    assert c == [("high", "regression_publication")], c
    assert lancer(resultat(), prec=prec)[0] == []


if __name__ == "__main__":
    test_silence_si_tout_va_bien()
    test_chaque_defaut_appelle_la_reparation()
    test_regression_publication()
    print("OK — test_scores_tension_surveillance : 3/3")
