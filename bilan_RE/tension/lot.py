"""lot.py — calcul MENSUEL des scores pour tous les immeubles à annonce active.

    scraper/.venv/Scripts/python.exe -m bilan_RE.tension.lot [--fin AAAA-MM-JJ] [--limite N]

POURQUOI UN LOT ET PAS N BILANS. Le bilan d'une annonce prend 1 min 30 (mesuré le
2026-10-17), presque tout dans les niveaux larges (Bangkok, zone, district), qui
sont LES MÊMES pour tous les immeubles d'un district. Ici ils sont calculés une
fois et partagés ; seuls le rayon de 1 km et l'immeuble sont propres à chacun.
Le rayon passe par un index en grille (~1,1 km) au lieu de mesurer la distance
aux 11 000 cohortes pour chaque immeuble.

CE QUI EST ÉCRIT. `scraper/output/scores-tension/scores-AAAA-MM.json` (+ une
copie `scores-latest.json`) : par immeuble × chambres (et « toutes chambres »),
tension et liquidité à chaque niveau, avec effectifs et fourchettes, prix/m²
médian actif, année, charges. Le dossier est hors dépôt (scraper/output/ est
gitignoré). Rien n'est écrit dans la base, rien n'est remonté sur Supabase
(décision de l'utilisateur : pas de remontée pour l'instant).

Combinaisons « même surface » non calculées ici : elles dépendent de la surface
du lot visé, connue seulement au moment d'un bilan d'annonce (`--annonce`).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time
from collections import defaultdict
from datetime import date

from . import coeur, liquidite
from .donnees import DB, SORTIES, Calcul, config

SORTIE = os.path.join(SORTIES, "scores-tension")
MODELES = (("tension", coeur.TENSION), ("liquidite", liquidite.LIQUIDITE))
CHAMPS = ("score", "p10", "p90", "libelle", "n_cohortes", "n_sorties")


def _resume(r: dict) -> dict:
    return {k: r.get(k) for k in CHAMPS}


class Grille:
    """Index spatial : cellules de PAS degrés ; un rayon de 1 km ne regarde que
    les 9 cellules voisines."""
    PAS = 0.01   # ~1,1 km en latitude à Bangkok

    def __init__(self, cohortes):
        self.cases = defaultdict(list)
        for c in cohortes:
            if c.lat is not None and c.lng is not None:
                self.cases[(int(c.lat / self.PAS), int(c.lng / self.PAS))].append(c)

    def autour(self, lat, lng, km):
        i, j = int(lat / self.PAS), int(lng / self.PAS)
        r = max(1, math.ceil(km / 1.1))
        for di in range(-r, r + 1):
            for dj in range(-r, r + 1):
                for c in self.cases.get((i + di, j + dj), ()):
                    if coeur.distance_km(lat, lng, c.lat, c.lng) <= km:
                        yield c


def calculer(t1: date, cfg: dict, db: str = DB, limite: int | None = None, journal=print) -> dict:
    debut = time.time()
    calc = Calcul(t1, cfg, db)
    gardees = [s for s, v in calc.sante.items() if v["gardee"]]
    journal(f"fenêtre au {t1} · sources gardées : {', '.join(gardees)} · {len(calc.cohortes)} cohortes")

    # Regroupement par nom NORMALISÉ (même règle que unit_key) : FazWaz écrit
    # « Noble Ploenchit », DDproperty « Noble Ploenchit, Bangkok ». Par nom brut,
    # un même immeuble se scindait en plusieurs entrées (trouvé en démo, 2026-10-17).
    import sys as _sys
    _sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "scraper"))
    from pipeline.normalize import _norm_condo
    par_immeuble = defaultdict(list)
    libelles = defaultdict(lambda: defaultdict(int))
    for c in calc.cohortes:
        k = _norm_condo(c.condo)
        par_immeuble[k].append(c)
        libelles[k][c.condo] += 1
    grille = Grille(calc.cohortes)
    fx = calc.faits(t1)
    fs_de = lambda cs: [fx[c.cle] for c in cs if c.cle in fx]

    # immeubles visés : au moins une cohorte de vente active à la fin de fenêtre
    cibles = sorted(k for k, cs in par_immeuble.items()
                    if k and any(fx.get(c.cle) and fx[c.cle].active_fin for c in cs))
    if limite:
        cibles = cibles[:limite]

    cache = {}   # (modèle, niveau, chambres) → résultat : partagé par tous les immeubles

    def niveau_large(nom_m, m, cle, cs, chambres, parent, ref):
        k = (nom_m, cle, chambres)
        if k not in cache:
            cache[k] = coeur.evaluer(fs_de([c for c in cs if chambres is None or c.chambres == chambres]),
                                     parent, ref, cfg, m)
        return cache[k]

    tout = calc.cohortes
    zones = cfg["zones"]
    resultats, erreurs = [], 0
    for n, condo in enumerate(cibles, 1):
        cs_imm = par_immeuble[condo]
        try:
            khet = statistics.mode(c.khet for c in cs_imm)
            la = [c.lat for c in cs_imm if c.lat is not None]
            ln = [c.lng for c in cs_imm if c.lng is not None]
            lat, lng = (statistics.median(la), statistics.median(ln)) if la else (None, None)
            actifs = [c for c in cs_imm if fx.get(c.cle) and fx[c.cle].active_fin]
            chambres_presentes = sorted({c.chambres for c in actifs if c.chambres is not None})
            voisins = list(grille.autour(lat, lng, cfg["rayon_km"])) if lat is not None else []
            annee = next((c.annee for c in cs_imm if c.annee), None)
            charges = next((a.charges for c in cs_imm for a in c.annonces if a.charges), None)
            ligne = {"immeuble": max(libelles[condo], key=libelles[condo].get), "cle": condo, "khet": khet, "lat": lat, "lng": lng, "annee": annee,
                     "charges_thb_m2": charges, "par_chambres": {}}
            for ch in [None] + chambres_presentes:
                cle_ch = "all" if ch is None else str(ch)
                bloc = {}
                filt = lambda cs: [c for c in cs if ch is None or c.chambres == ch]
                for nom_m, m in MODELES:
                    ref = calc.reference(ch, None, m)
                    parent, chaine = None, {}
                    niveaux = [("Bangkok", ("tout",), tout)]
                    niveaux += [(z, ("zone", z), [c for c in tout if c.khet in ks])
                                for z, ks in zones.items() if khet in ks]
                    niveaux += [(khet, ("khet", khet), None)]
                    for nom_niv, cle, cs in niveaux:
                        if cs is None:   # district : filtré à la volée puis mis en cache
                            cs = [c for c in tout if c.khet == khet]
                        r = niveau_large(nom_m, m, cle, cs, ch, parent, ref)
                        chaine[nom_niv] = _resume(r)
                        if r["n_cohortes"]:
                            parent = r["signaux"]
                    for nom_niv, cs in ((f"within {cfg['rayon_km']:g} km", voisins), ("building", cs_imm)):
                        r = coeur.evaluer(fs_de(filt(cs)), parent, ref, cfg, m)
                        chaine[nom_niv] = _resume(r)
                        if r["n_cohortes"]:
                            parent = r["signaux"]
                    bloc[nom_m] = chaine
                prix = [fx[c.cle].prix_m2 for c in filt(actifs) if fx[c.cle].prix_m2]
                bloc["prix_m2_median_actif"] = statistics.median(prix) if prix else None
                bloc["n_cohortes_actives"] = len(filt(actifs))
                ligne["par_chambres"][cle_ch] = bloc
            resultats.append(ligne)
        except Exception as e:   # un immeuble au nom ou aux données atypiques ne doit pas tuer le lot
            erreurs += 1
            journal(f"  ! {condo[:40]} : {type(e).__name__} {e}")
        if n % 250 == 0:
            journal(f"  {n}/{len(cibles)} immeubles · {time.time() - debut:.0f} s")

    notes = sum(1 for r in resultats for b in r["par_chambres"].values()
                if b["tension"]["building"]["score"] is not None)
    return {"fin_fenetre": t1.isoformat(), "calcule_le": date.today().isoformat(),
            "frequence_calcul": cfg.get("frequence_calcul"), "config_version": cfg["config_version"],
            "sources": calc.sante, "immeubles": resultats,
            "_stats": {"immeubles": len(resultats), "erreurs": erreurs,
                       "cohortes": len(calc.cohortes), "lignes_notees_immeuble": notes,
                       "duree_s": round(time.time() - debut)}}


def ecrire(res: dict, dossier: str | None = None) -> str:
    dossier = dossier or SORTIE      # lu à l'appel : remplaçable dans les essais
    os.makedirs(dossier, exist_ok=True)
    nom = os.path.join(dossier, f"scores-{res['fin_fenetre'][:7]}.json")
    for chemin in (nom, os.path.join(dossier, "scores-latest.json")):
        tmp = chemin + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False)
        os.replace(tmp, chemin)    # jamais de fichier à moitié écrit
    return nom


def main() -> None:
    from .__main__ import _fin_par_defaut
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB)
    ap.add_argument("--fin")
    ap.add_argument("--limite", type=int)
    ap.add_argument("--sortie", default=SORTIE)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    t1 = date.fromisoformat(a.fin) if a.fin else _fin_par_defaut(a.db)
    res = calculer(t1, config(), a.db, a.limite)
    print(json.dumps(res["_stats"], ensure_ascii=False))
    print(f"-> {ecrire(res, a.sortie)}")


if __name__ == "__main__":
    main()
