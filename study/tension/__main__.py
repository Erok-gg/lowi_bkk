"""Ligne de commande du score de tension. Lecture seule.

    scraper/.venv/Scripts/python.exe -m study.tension --khets
    scraper/.venv/Scripts/python.exe -m study.tension --annonce <id> [--json sortie.json]
    options : --fin AAAA-MM-JJ (fin de fenêtre, défaut : dernier jour de retrait connu)
              --db <chemin>     (défaut : scraper/output/bangkok.db)
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date

from . import coeur
from .donnees import DB, Calcul, config


def _fin_par_defaut(db: str) -> date:
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    m = c.execute("select max(substr(delisted_at,1,10)) from listings "
                  "where deal_type='sale'").fetchone()[0]
    return date.fromisoformat(m) if m else date.today()


def _ligne(r: dict) -> str:
    sc = "  —" if r["score"] is None else f"{r['score']:3d}"
    iv = "" if r["score"] is None else f" [{r['p10']}–{r['p90']}]"
    return f"{r['niveau'][:28]:28} {sc}{iv:10} {r['libelle']:17} n={r['n_cohortes']:5} sorties={r['n_sorties']}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB)
    ap.add_argument("--fin")
    ap.add_argument("--annonce")
    ap.add_argument("--khets", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    t1 = date.fromisoformat(a.fin) if a.fin else _fin_par_defaut(a.db)
    calc = Calcul(t1, config(), a.db)
    print(f"Fenêtre se terminant le {t1} · config v{calc.cfg['config_version']} · "
          f"{len(calc.cohortes)} cohortes retenues")
    for s, v in sorted(calc.sante.items()):
        etat = "gardée " if v["gardee"] else "ÉCARTÉE"
        print(f"  {s:14} {etat} actives {v['actives_debut']:6} → {v['actives_fin']:6} "
              f"retraits {v['retraits']:6}  {'; '.join(v['raisons'])}")
    sortie = {}

    if a.khets:
        ref = calc.reference(None, None)
        tout = coeur.evaluer(calc._fs(calc.cohortes), None, ref, calc.cfg)
        tout["niveau"] = "Bangkok"
        print("\n" + _ligne(tout))
        lignes = []
        for k in sorted({c.khet for c in calc.cohortes}):
            fs = calc._fs(coeur.filtre(calc.cohortes, ("khet", k)))
            r = coeur.evaluer(fs, tout["signaux"], ref, calc.cfg)
            r["niveau"] = k
            lignes.append(r)
        for r in sorted(lignes, key=lambda r: (r["score"] is None, r["score"] or 0)):
            print(_ligne(r))
        sortie["khets"] = {r["niveau"]: {k: r[k] for k in ("score", "p10", "p90", "libelle",
                                                            "n_cohortes", "n_sorties")}
                           for r in lignes}

    if a.annonce:
        c = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
        row = c.execute("select condo_name, khet, lat, lng, bedrooms, area_sqm, price from listings "
                        "where id = ?", (a.annonce,)).fetchone()
        if not row:
            sys.exit(f"annonce inconnue : {a.annonce}")
        condo, khet, lat, lng, ch, surf, px = row
        # coordonnées de l'immeuble (médiane de ses cohortes) plutôt que celles
        # de l'annonce : le rayon se centre sur le bâtiment
        cs = [x for x in calc.cohortes if x.condo == (condo or "").strip()]
        if cs and cs[0].lat is not None:
            lat, lng = cs[0].lat, cs[0].lng
        b = calc.bilan((condo or "").strip(), khet, lat, lng,
                       int(ch) if ch is not None else None, surf,
                       px / surf if px and surf else None)
        print(f"\n{condo} · {khet} · {ch} ch. · {surf} m² · {px:,.0f} THB")
        print("\nTENSION")
        for nom, chaine in b["comparaisons"].items():
            print(f"  {nom}  (référence : {chaine[0]['reference']})")
            for r in chaine:
                print("   " + _ligne(r))
        L = b["liquidite"]
        print(f"\nLIQUIDITÉ  · immeuble livré en {L['annee'] or '?'} (âge {L['age_immeuble'] or '?'})"
              f" · charges {L['charges_thb_m2'] and round(L['charges_thb_m2'])} THB/m²/mois")
        for nom, chaine in L["comparaisons"].items():
            print(f"  {nom}  (référence : {chaine[0]['reference']})")
            for r in chaine:
                print("   " + _ligne(r))
        print("  Courbe d'âge (Bangkok, mêmes chambres) :")
        for tr, v in sorted(L["courbe_age"].items(), key=lambda kv: int(kv[0].split("-")[0].rstrip("+"))):
            vit = f"{v['vitesse']:.0f} j" if v["vitesse"] else "—"
            p90 = f"{v['vente90']:.0%}" if v["vente90"] is not None else "—"
            print(f"    {tr:6} ans  vitesse médiane {vit:7} vente < 90 j {p90:5}  n={v['n']} sorties={v['sorties']}")
        print(f"  Projection (maille : {L['projection_maille']}) :")
        for pr in L["projection"]:
            print(f"    +{pr['horizon_ans']} ans (âge {pr['age_futur']}) : score {pr.get('score')}"
                  f" {pr.get('raison', '')} jalons={len(pr['jalons'])}")
        print("\nPRIX/M²")
        for r in b["prix"]:
            if r["n"] >= 5:
                print(f"  {r['niveau'][:42]:42} médiane {r['mediane']:,.0f}  écart {r['ecart']:+.0%}"
                      f"  plus cher que {r['rang_pct']}%  n={r['n']}  {r['verdict']}")
            else:
                print(f"  {r['niveau'][:42]:42} n={r['n']}  {r['verdict']}")
        sortie["bilan"] = b

    if a.json:
        def propre(o):
            if isinstance(o, dict):
                return {k: propre(v) for k, v in o.items() if k not in ("brut", "points")}
            if isinstance(o, list):
                return [propre(x) for x in o]
            return round(o, 4) if isinstance(o, float) else o
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(propre(sortie), f, ensure_ascii=False, indent=1)
        print(f"\n-> {a.json}")


if __name__ == "__main__":
    main()
