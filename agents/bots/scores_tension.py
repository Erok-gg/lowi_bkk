"""scores-tension — calcul QUOTIDIEN des scores de tension et de liquidité par
immeuble, et surveillance de ce qui les nourrit.

Historique de la cadence : mensuelle le 2026-10-17 (décision utilisateur, faute
de puissance de calcul) ; QUOTIDIENNE depuis le 2026-10-20, en fin de cycle
(décision utilisateur : « tous les jours à la fin des cycles de scrap et
agents »). Coût mesuré le 2026-10-17 : ~2 min 15 fixes + ~0,7 s par immeuble,
soit ~50 min ajoutées au cycle. Un fichier par jour (~6 Mo) : ~2,2 Go par an.

SURVEILLANCE (2026-10-20, même demande : « un défaut appelle la réparation »)
Tout défaut ci-dessous est un constat de sévérité HAUTE : la veille
(ops/veille-cycle.py) le lit et appelle Opus avec la procédure de réparation.
Jusqu'ici une grande source écartée n'était qu'un constat BAS (« le filtre fait
son travail ») ; or la mesure du 2026-10-20 a montré que l'écart venait d'une
panne de NOTRE côté (recensement DDproperty arrêté au plafond de pages, donc
aucun délistage) : c'est à réparer, pas à constater.

  1. delistage_a_l_arret   grande source, >= 200 actives, >= 3 jours sans retrait
                           en fin de fenêtre. Le filtre l'écarte à 5 : l'alerte
                           à 3 laisse 2 jours pour réparer avant de perdre la
                           fenêtre (et la continuité de la série).
  2. source_ecartee        grande source écartée par le filtre de santé.
  3. immeubles_en_erreur   au moins un immeuble en erreur.
  4. fenetre_perimee       le dernier retrait connu date de plus de 2 jours :
                           tout le délistage est à l'arrêt, pas une source.
  5. regression_publication part des lignes notées à une maille fine (district
                           ou plus près) en baisse de plus de 15 points, ou
                           scores de revente publiés divisés par deux, face au
                           run précédent. Se tait au premier run (pas de
                           référence) : règle 2.
"""
from __future__ import annotations

import json
from datetime import date

GRANDES_SOURCES = ("ddproperty", "fazwaz")
ALERTE_SANS_RETRAIT_J = 3
FENETRE_PERIMEE_J = 2
REGRESSION_POINTS = 15
REGRESSION_LIQUIDITE = 0.5


def _publies(res: dict, zones: set[str]) -> dict:
    """Mêmes règles que bilan_RE/tension/rapport._niveau_retenu : la maille la
    plus fine qui a un score affirmable."""
    n = fines = liq = 0
    for im in res["immeubles"]:
        for b in im["par_chambres"].values():
            n += 1
            for mod in ("tension", "liquidite"):
                chaine = b.get(mod) or {}
                niv = next((k for k in reversed(list(chaine))
                            if chaine[k]["score"] is not None
                            and chaine[k]["libelle"] != "not enough data"), None)
                if niv is None:
                    continue
                if mod == "liquidite":
                    liq += 1
                elif niv != "Bangkok" and niv not in zones:
                    fines += 1
    return {"lignes": n, "part_tension_fine": round(100 * fines / n, 1) if n else 0.0,
            "liquidite_publiees": liq}


def _precedent(led, nom: str) -> dict | None:
    row = led.last_run(nom, only_ok=True)
    try:
        return json.loads(row["metrics"] or "{}") if row else None
    except (json.JSONDecodeError, TypeError):
        return None


def run(led, run_id: int, lane: str, spec: dict) -> dict:
    # import tardif : ne charger le moteur (et la base) que si l'agent tourne
    from bilan_RE.tension import lot
    from bilan_RE.tension.__main__ import _fin_par_defaut
    from bilan_RE.tension.donnees import DB, config

    cfg = config()
    t1 = _fin_par_defaut(DB)
    # `limite` (facultatif dans la spec) sert aux essais : jamais posé en production
    res = lot.calculer(t1, cfg, DB, spec.get("limite"),
                       journal=lambda m: print(f"    {m}", flush=True))
    fichier = lot.ecrire(res)
    st = res["_stats"]
    gardees = sorted(s for s, v in res["sources"].items() if v["gardee"])
    pub = _publies(res, set(cfg["zones"]))
    prec = _precedent(led, "scores-tension")

    def haut(kind: str, sujet: str, details: dict) -> None:
        led.finding("scores-tension", "high", kind, sujet, details, run_id)

    for s in GRANDES_SOURCES:
        v = res["sources"].get(s)
        if not v:
            continue
        if not v["gardee"]:
            haut("source_ecartee", f"{s} écartée de la fenêtre au {t1} : {'; '.join(v['raisons'])}",
                 {"source": s, **v})
        elif (v["actives_debut"] >= cfg["sante_sources"]["stock_min"]
              and v["jours_sans_retrait_fin"] >= ALERTE_SANS_RETRAIT_J):
            haut("delistage_a_l_arret",
                 f"{s} : {v['jours_sans_retrait_fin']} jours sans retrait au {t1} "
                 f"(écartée à {cfg['sante_sources']['jours_sans_retrait_max']}) — "
                 "vérifier que le scan lit le site entier", {"source": s, **v})
    if st["erreurs"]:
        haut("immeubles_en_erreur",
             f"{st['erreurs']} immeuble(s) en erreur sur {st['immeubles'] + st['erreurs']}",
             {"erreurs": st["erreurs"]})
    retard = (date.today() - t1).days
    if retard > FENETRE_PERIMEE_J:
        haut("fenetre_perimee", f"dernier retrait connu le {t1}, il y a {retard} jours",
             {"fin_fenetre": t1.isoformat()})
    if prec and "part_tension_fine" in prec:
        if prec["part_tension_fine"] - pub["part_tension_fine"] > REGRESSION_POINTS:
            haut("regression_publication",
                 f"tension à maille fine : {prec['part_tension_fine']} % → "
                 f"{pub['part_tension_fine']} % des lignes", {"avant": prec, "apres": pub})
        if prec.get("liquidite_publiees", 0) and \
                pub["liquidite_publiees"] < REGRESSION_LIQUIDITE * prec["liquidite_publiees"]:
            haut("regression_publication",
                 f"scores de revente publiés : {prec['liquidite_publiees']} → "
                 f"{pub['liquidite_publiees']}", {"avant": prec, "apres": pub})

    rayon = sum(1 for r in res["immeubles"] for b in r["par_chambres"].values()
                for k, v in b["tension"].items() if k.startswith("within") and v["score"] is not None)
    return {"fichier": fichier, "fin_fenetre": t1.isoformat(), "immeubles": st["immeubles"],
            "erreurs": st["erreurs"], "sources_gardees": gardees,
            "lignes_notees_rayon": rayon, "duree_s": st["duree_s"],
            "calcule_le": date.today().isoformat(), **pub}
