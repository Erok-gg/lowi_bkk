"""comparer-local-prod.py — confronte un scrap LOCAL isolé à la production Supabase.

But : répondre à « ce nouveau balayage voit-il la même chose que l'ancien ? »
avant de décider d'écraser quoi que ce soit en ligne.

Trois familles d'écarts, qui n'ont pas la même signification :

  COUVERTURE   Ce que le local voit et pas la prod = annonces neuves (attendu si
               le tri par fraîcheur fonctionne). L'inverse = ce que la fenêtre de
               150 pages ne ramène plus — c'est là qu'un délistage se déciderait,
               et c'est pour ça qu'on regarde AVANT d'écrire.

  ENRICHISSEMENT  Champs remplis d'un côté et vides de l'autre. C'est ici qu'on
               mesure le gain réel du nouveau code (descriptifs, provenance).

  DIVERGENCE   Annonces présentes des deux côtés mais dont un champ diffère.
               Un prix qui change est normal ; une surface qui change ne l'est pas.

Usage : python ops/comparer-local-prod.py <dossier-local> [--csv]
"""
from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agents.core import db as agentsdb  # noqa: E402

CHAMPS_STABLES = ("area_sqm", "bedrooms", "condo_name", "khet", "deal_type")
CHAMPS_ENRICHIS = ("description", "agent_id", "posted_at", "lat", "year_built")


def pct(n, t):
    return f"{100.0 * n / t:5.1f}%" if t else "  n/a"


def charger_local(dossier: str) -> dict[str, dict]:
    chemin = os.path.join(dossier, "bangkok.db")
    if not os.path.exists(chemin):
        sys.exit(f"✗ base locale introuvable : {chemin}")
    c = sqlite3.connect(chemin)
    c.row_factory = sqlite3.Row
    return {r["id"]: dict(r) for r in c.execute("select * from listings")}


def charger_prod() -> dict[str, dict]:
    lignes = agentsdb.query(
        "select id, source, deal_type, status, price, area_sqm, bedrooms, "
        "condo_name, khet, lat, description, agent_id, posted_at, year_built "
        "from listings")
    return {r["id"]: r for r in lignes}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dossier")
    ap.add_argument("--csv", action="store_true", help="écrit le détail en CSV")
    a = ap.parse_args()

    loc = charger_local(a.dossier)
    prod = charger_prod()
    prod_actives = {k: v for k, v in prod.items() if v["status"] == "active"}

    ids_loc, ids_pa = set(loc), set(prod_actives)
    communs = ids_loc & ids_pa
    neuves = ids_loc - set(prod)          # inconnues même en historique
    revues = (ids_loc & set(prod)) - ids_pa  # connues mais inactives en prod
    absentes = ids_pa - ids_loc           # actives en prod, hors fenêtre locale

    print("╔═ COMPARAISON LOCAL ↔ PRODUCTION ══════════════════════════")
    print(f"║ local : {len(loc):6d} annonces   ({os.path.basename(a.dossier)})")
    print(f"║ prod  : {len(prod):6d} dont {len(prod_actives)} actives")
    print("╚═══════════════════════════════════════════════════════════\n")

    print("① COUVERTURE")
    print(f"  vues des deux côtés          {len(communs):6d}")
    print(f"  NEUVES (inconnues en prod)   {len(neuves):6d}  ← apport du balayage")
    print(f"  réapparues (inactives→vues)  {len(revues):6d}")
    print(f"  actives en prod, non revues  {len(absentes):6d}  ← candidates au délistage")
    if absentes:
        par_src: dict[str, int] = {}
        for i in absentes:
            s = prod_actives[i]["source"]
            par_src[s] = par_src.get(s, 0) + 1
        print("     par source :", ", ".join(f"{s} {n}" for s, n in sorted(par_src.items())))
        print("     ⚠ un fort taux sur UNE source signale une fenêtre trop courte")
        print("       ou un parseur cassé, PAS un marché qui se vide.")

    print("\n② ENRICHISSEMENT (sur les annonces vues des deux côtés)")
    print(f"  {'champ':14s} {'local':>8s} {'prod':>8s}   gagné")
    for ch in CHAMPS_ENRICHIS:
        nl = sum(1 for i in communs if loc[i].get(ch) not in (None, ""))
        np_ = sum(1 for i in communs if prod[i].get(ch) not in (None, ""))
        gain = sum(1 for i in communs
                   if loc[i].get(ch) not in (None, "") and prod[i].get(ch) in (None, ""))
        print(f"  {ch:14s} {pct(nl, len(communs))} {pct(np_, len(communs))}   +{gain}")

    print("\n③ DIVERGENCES sur champs qui NE devraient pas bouger")
    divergences = []
    for i in communs:
        for ch in CHAMPS_STABLES:
            vl, vp = loc[i].get(ch), prod[i].get(ch)
            if vl is None or vp is None:
                continue
            if ch == "area_sqm":
                if abs(float(vl) - float(vp)) > 0.5:
                    divergences.append((i, ch, vp, vl))
            elif str(vl).strip() != str(vp).strip():
                divergences.append((i, ch, vp, vl))
    par_champ: dict[str, int] = {}
    for _, ch, _, _ in divergences:
        par_champ[ch] = par_champ.get(ch, 0) + 1
    if par_champ:
        for ch, n in sorted(par_champ.items(), key=lambda x: -x[1]):
            print(f"  {ch:14s} {n:5d} écart(s)  {pct(n, len(communs))}")
        print("  exemples :")
        for i, ch, vp, vl in divergences[:5]:
            print(f"    {i[:38]:38s} {ch}: prod={str(vp)[:22]!r} → local={str(vl)[:22]!r}")
    else:
        print("  aucune — les champs stables concordent")

    # prix : un écart est NORMAL, on le mesure sans le compter comme défaut
    ecarts_prix = [(i, float(prod[i]["price"]), float(loc[i]["price"]))
                   for i in communs
                   if prod[i].get("price") and loc[i].get("price")
                   and abs(float(prod[i]["price"]) - float(loc[i]["price"])) > 1]
    print(f"\n④ MOUVEMENTS DE PRIX (normaux)  {len(ecarts_prix)} sur {len(communs)}")
    if ecarts_prix:
        baisses = sum(1 for _, p, l in ecarts_prix if l < p)
        print(f"  {baisses} baisse(s), {len(ecarts_prix) - baisses} hausse(s)")

    if a.csv:
        dst = os.path.join(a.dossier, "comparaison.csv")
        with open(dst, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["categorie", "id", "champ", "prod", "local"])
            for i in sorted(neuves):
                w.writerow(["neuve", i, "", "", loc[i].get("condo_name")])
            for i in sorted(absentes):
                w.writerow(["non_revue", i, "", prod_actives[i].get("condo_name"), ""])
            for i, ch, vp, vl in divergences:
                w.writerow(["divergence", i, ch, vp, vl])
        print(f"\n  détail écrit : {dst}")

    print("\n" + "═" * 60)
    print("Lecture : des NEUVES nombreuses et peu de divergences = balayage sain.")
    print("Des non-revues massives sur une seule source = à investiguer AVANT")
    print("toute remontée, car c'est ce qui déclencherait un délistage en ligne.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
