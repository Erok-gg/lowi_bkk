"""scores-tension — calcul MENSUEL des scores de tension et de liquidité par immeuble.

Décision de l'utilisateur (2026-10-17) : le travail par cohorte se fait une fois
par mois, faute de puissance de calcul pour le refaire à chaque demande ; le
résultat est écrit dans un fichier, SANS remontée Supabase pour l'instant.

Mesuré le même jour : ~2 min 15 de coût fixe puis ~0,7 s par immeuble, soit de
l'ordre de 50 min pour ~4 000 immeubles. C'est pourquoi l'agent est mensuel et
non quotidien.

Ce que l'agent signale, et pourquoi si peu (règle 2 : un garde-fou qui crie au
loup apprend à être ignoré) :
  · une grande source écartée par le filtre de santé → constat BAS, informatif :
    c'est le filtre qui fait son travail, pas une panne de l'agent ;
  · les deux grandes sources écartées → MOYEN : le score ne repose plus que sur
    les petites sources et ne doit pas être servi tel quel ;
  · des immeubles en erreur → MOYEN, avec le compte.
"""
from __future__ import annotations

from datetime import date

GRANDES_SOURCES = ("ddproperty", "fazwaz")


def run(led, run_id: int, lane: str, spec: dict) -> dict:
    # import tardif : ne charger le moteur (et la base) que si l'agent tourne
    from study.tension import lot
    from study.tension.__main__ import _fin_par_defaut
    from study.tension.donnees import DB, config

    t1 = _fin_par_defaut(DB)
    # `limite` (facultatif dans la spec) sert aux essais : jamais posé en production
    res = lot.calculer(t1, config(), DB, spec.get("limite"),
                       journal=lambda m: print(f"    {m}", flush=True))
    fichier = lot.ecrire(res)
    st = res["_stats"]
    gardees = sorted(s for s, v in res["sources"].items() if v["gardee"])
    ecartees = {s: v["raisons"] for s, v in res["sources"].items() if not v["gardee"]}

    for s in GRANDES_SOURCES:
        if s in ecartees:
            led.finding("scores-tension", "low", "source_ecartee",
                        f"{s} écartée de la fenêtre au {t1} : {'; '.join(ecartees[s])}",
                        {"source": s, "raisons": ecartees[s]}, run_id)
    if all(s in ecartees for s in GRANDES_SOURCES):
        led.finding("scores-tension", "medium", "score_sans_grande_source",
                    f"fenêtre au {t1} : DDproperty ET FazWaz écartées — scores à ne pas servir",
                    {"gardees": gardees}, run_id)
    if st["erreurs"]:
        led.finding("scores-tension", "medium", "immeubles_en_erreur",
                    f"{st['erreurs']} immeuble(s) en erreur sur {st['immeubles'] + st['erreurs']}",
                    {"erreurs": st["erreurs"]}, run_id)

    rayon = sum(1 for r in res["immeubles"] for b in r["par_chambres"].values()
                for k, v in b["tension"].items() if k.startswith("within") and v["score"] is not None)
    return {"fichier": fichier, "fin_fenetre": t1.isoformat(), "immeubles": st["immeubles"],
            "erreurs": st["erreurs"], "sources_gardees": gardees,
            "lignes_notees_rayon": rayon, "duree_s": st["duree_s"],
            "calcule_le": date.today().isoformat()}
