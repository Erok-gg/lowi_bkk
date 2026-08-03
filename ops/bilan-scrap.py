"""bilan-scrap.py — ce qui a CHANGÉ depuis le dernier état connu.

Compare les statistiques du scrap qui vient de finir aux snapshots antérieurs
(study/snapshots/) et rend, dans le même style terminal que le dashboard :

  · nouvelles opportunités      (décotes apparues, par immeuble)
  · évolution de la tension     (pression vendeuse par quartier)
  · progression des rendements  (par khet, avec courbe par date)

Aucune écriture : c'est une lecture. Lancement :
    scraper\.venv\Scripts\python.exe ops/bilan-scrap.py [<dossier-scrap>] [--md]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sqlite3
import statistics
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPS = os.path.join(ROOT, "study", "snapshots")

# Barres pixel pour les courbes — mêmes blocs que le dashboard
NIVEAUX = "▁▂▃▄▅▆▇█"


def sparkline(valeurs: list[float]) -> str:
    """Courbe compacte : une colonne par date."""
    vs = [v for v in valeurs if v is not None]
    if len(vs) < 2:
        return "·" * len(valeurs)
    lo, hi = min(vs), max(vs)
    if hi - lo < 1e-9:
        return NIVEAUX[3] * len(valeurs)
    out = []
    for v in valeurs:
        if v is None:
            out.append(" ")
        else:
            out.append(NIVEAUX[min(7, int((v - lo) / (hi - lo) * 7.99))])
    return "".join(out)


def fleche(delta: float | None, seuil: float = 1.0) -> str:
    if delta is None:
        return "  ·  "
    if delta > seuil:
        return f" ▲{delta:+.1f}%"
    if delta < -seuil:
        return f" ▼{delta:+.1f}%"
    return f"  ={delta:+.1f}%"


# ───────────────────── stats depuis une base de scrap ─────────────────────
def stats_locales(db_path: str) -> dict:
    """Double médiane par immeuble — un immeuble = une voix (méthode du projet)."""
    uri = "file:" + db_path.replace("\\", "/") + "?mode=ro"
    c = sqlite3.connect(uri, uri=True)
    c.row_factory = sqlite3.Row

    def par_khet(deal: str, borne_min: float, borne_max: float):
        lignes = c.execute(
            "select khet, condo_name, price, area_sqm from listings "
            "where deal_type=? and status='active' and khet is not null "
            "and condo_name is not null and area_sqm>=15 and area_sqm<=500 "
            "and price>=? and price<=?", (deal, borne_min, borne_max)).fetchall()
        par_condo: dict[tuple, list[float]] = {}
        loyers: dict[tuple, list[float]] = {}
        for r in lignes:
            cle = (r["khet"], r["condo_name"])
            par_condo.setdefault(cle, []).append(r["price"] / r["area_sqm"])
            loyers.setdefault(cle, []).append(r["price"])
        med_condo = {k: statistics.median(v) for k, v in par_condo.items()}
        med_prix = {k: statistics.median(v) for k, v in loyers.items()}
        out: dict[str, dict] = {}
        for (khet, condo), v in med_condo.items():
            out.setdefault(khet, {"ppsqm": [], "prix": {}, "n": 0})
            out[khet]["ppsqm"].append(v)
            out[khet]["prix"][condo] = med_prix[(khet, condo)]
            out[khet]["n"] += 1
        return {k: {"ppsqm": statistics.median(v["ppsqm"]), "n": v["n"],
                    "prix": v["prix"]} for k, v in out.items()}

    vente = par_khet("sale", 800_000, 100_000_000)
    loc = par_khet("rent", 3_000, 500_000)

    # rendement WITHIN-CONDO : même immeuble des deux côtés
    rdt: dict[str, float] = {}
    for khet, v in vente.items():
        l = loc.get(khet)
        if not l:
            continue
        paires = [(l["prix"][cn] * 12 / v["prix"][cn]) * 100
                  for cn in v["prix"] if cn in l["prix"] and v["prix"][cn] > 0]
        if len(paires) >= 3:
            rdt[khet] = statistics.median(paires)
    c.close()
    return {"vente": vente, "location": loc, "rendement": rdt}


def charger_snapshots() -> list[tuple[str, dict]]:
    out = []
    for f in sorted(glob.glob(os.path.join(SNAPS, "*.json"))):
        try:
            out.append((os.path.basename(f)[:-5], json.load(open(f, encoding="utf-8"))))
        except (json.JSONDecodeError, OSError):
            continue
    return out


# Structure réelle des snapshots (study/run_study.py) :
#   khet_stats_01   : {khet: {sale_psqm, rent_psqm, yield_wc, paired, …}}
#   tension_by_khet : {khet: {rate, n}}
BLOCS = {"sale_psqm": "khet_stats_01", "rent_psqm": "khet_stats_01",
         "yield_wc": "khet_stats_01", "rate": "tension_by_khet"}


def _lire(snap: dict, khet: str, champ: str) -> float | None:
    bloc = snap.get(BLOCS.get(champ, "khet_stats_01"))
    if not isinstance(bloc, dict):
        return None
    d = bloc.get(khet)
    if isinstance(d, dict) and isinstance(d.get(champ), (int, float)):
        return float(d[champ])
    return None


def serie_khet(snaps, khet: str, champ: str) -> list[float | None]:
    """Valeur d'un khet à travers les snapshots, pour la courbe par date."""
    return [_lire(s, khet, champ) for _, s in snaps]


def ref_snapshot(snaps, champ: str) -> dict[str, float]:
    """Dernier snapshot connu, pour l'écart."""
    if not snaps:
        return {}
    _, s = snaps[-1]
    bloc = s.get(BLOCS.get(champ, "khet_stats_01"))
    if not isinstance(bloc, dict):
        return {}
    return {k: float(v[champ]) for k, v in bloc.items()
            if isinstance(v, dict) and isinstance(v.get(champ), (int, float))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dossier", nargs="?", default=None)
    ap.add_argument("--md", action="store_true", help="écrit aussi un rapport markdown")
    a = ap.parse_args()

    if a.dossier:
        db = os.path.join(a.dossier, "bangkok.db")
    else:
        cands = sorted(glob.glob(os.path.join(ROOT, "tests-scrap", "*", "bangkok.db")),
                       key=os.path.getmtime, reverse=True)
        if not cands:
            print("Aucune base de scrap trouvée.")
            return 2
        db = cands[0]
    if not os.path.exists(db):
        print(f"Base introuvable : {db}")
        return 2

    st = stats_locales(db)
    snaps = charger_snapshots()
    dates = [d for d, _ in snaps]
    L = []

    L.append("")
    L.append("  ██████  ██ ██     ██   ██ ██   ██")
    L.append("  ██   ██ ██ ██     ██   ██ ███ ███   BILAN DE SCRAP")
    L.append("  ██████  ██ ██     ███████ ██ █ ██   ce qui a change")
    L.append("")
    L.append(f"  scrap   : {os.path.basename(os.path.dirname(db))}")
    L.append(f"  compare : {len(snaps)} snapshot(s) — {', '.join(dates) if dates else 'aucun'}")
    L.append("  " + "─" * 118)

    if not snaps:
        L.append("")
        L.append("  ⚠ Aucun snapshot antérieur : rien à comparer.")
        L.append("    Les tables d'évolution se construisent dès la 2e édition de l'étude.")
        L.append("    Lancer : scraper\\.venv\\Scripts\\python.exe study/run_study.py")

    # ── rendements par khet ──
    L.append("")
    L.append("  ▐ RENDEMENT BRUT PAR QUARTIER (within-condo, >=3 immeubles appaires)")
    ref_r = ref_snapshot(snaps, "yield_wc")
    L.append(f"    {'quartier':<24}{'now':>7}{'ref':>8}{'ecart':>8}   courbe par date")
    if st["rendement"]:
        for khet, y in sorted(st["rendement"].items(), key=lambda x: -x[1]):
            r = ref_r.get(khet)
            d = ((y - r) / r * 100) if r else None
            serie = serie_khet(snaps, khet, "yield_wc") + [y]
            nom = khet.replace(" District", "")[:23]
            L.append(f"    {nom:<24}{y:>6.2f}%{(f'{r:.2f}%' if r else '  —'):>8}"
                     f"{fleche(d):>8}   {sparkline(serie)}")
    else:
        L.append("      (pas encore assez d'immeubles avec vente ET location dans ce scrap)")

    # ── prix/m2 vente ──
    L.append("")
    L.append("  ▐ PRIX/M2 VENTE PAR QUARTIER (mediane des medianes d'immeuble)")
    ref_p = ref_snapshot(snaps, "sale_psqm")
    L.append(f"    {'quartier':<24}{'now':>9}{'ref':>10}{'ecart':>8}   courbe par date")
    for khet, v in sorted(st["vente"].items(), key=lambda x: -x[1]["ppsqm"])[:18]:
        r = ref_p.get(khet)
        d = ((v["ppsqm"] - r) / r * 100) if r else None
        serie = serie_khet(snaps, khet, "sale_psqm") + [v["ppsqm"]]
        nom = khet.replace(" District", "")[:23]
        L.append(f"    {nom:<24}{v['ppsqm']:>9,.0f}{(f'{r:,.0f}' if r else '—'):>10}"
                 f"{fleche(d):>8}   {sparkline(serie)}  n={v['n']}")

    # ── opportunites : decote d'un immeuble vs son quartier ──
    L.append("")
    L.append("  ▐ OPPORTUNITES — immeubles sous la mediane de leur quartier")
    L.append(f"    {'quartier':<20}{'immeuble':<34}{'prix/m2':>10}{'khet':>10}{'decote':>9}")
    opp = []
    uri = "file:" + db.replace("\\", "/") + "?mode=ro"
    c = sqlite3.connect(uri, uri=True)
    c.row_factory = sqlite3.Row
    rows = c.execute(
        "select khet, condo_name, count(*) n, "
        "  avg(price/area_sqm) ppsqm from listings "
        "where deal_type='sale' and status='active' and khet is not null "
        "and condo_name is not null and area_sqm between 15 and 500 "
        "and price between 800000 and 100000000 "
        "group by khet, condo_name having count(*) >= 2").fetchall()
    c.close()
    for r in rows:
        base = st["vente"].get(r["khet"], {}).get("ppsqm")
        if not base or not r["ppsqm"]:
            continue
        dec = (r["ppsqm"] - base) / base * 100
        if dec <= -25:
            opp.append((dec, r["khet"], r["condo_name"], r["ppsqm"], base, r["n"]))
    for dec, khet, condo, p, base, n in sorted(opp)[:14]:
        nom = khet.replace(" District", "")[:19]
        L.append(f"    {nom:<20}{condo[:33]:<34}{p:>10,.0f}{base:>10,.0f}"
                 f"{dec:>8.1f}%  n={n}")
    if not opp:
        L.append("      (aucune décote >=25% dans ce périmètre)")
    L.append("")
    L.append("    Rappel : une décote >40% est presque toujours un défaut de donnée,")
    L.append("    pas une affaire. A verifier avant toute conclusion.")

    # ── tension ──
    L.append("")
    L.append("  ▐ TENSION — pression vendeuse (annonces actives par immeuble)")
    L.append(f"    {'quartier':<24}{'annonces':>10}{'immeubles':>11}{'par imm.':>10}")
    tens = []
    for khet, v in st["vente"].items():
        n_ann = sum(1 for _ in v["prix"])
        tens.append((v["n"], khet, n_ann))
    uri = "file:" + db.replace("\\", "/") + "?mode=ro"
    c = sqlite3.connect(uri, uri=True)
    c.row_factory = sqlite3.Row
    t = c.execute(
        "select khet, count(*) ann, count(distinct condo_name) imm from listings "
        "where deal_type='sale' and status='active' and khet is not null "
        "group by khet having count(distinct condo_name) >= 5 "
        "order by 1.0*count(*)/count(distinct condo_name) desc limit 12").fetchall()
    c.close()
    for r in t:
        nom = r["khet"].replace(" District", "")[:23]
        L.append(f"    {nom:<24}{r['ann']:>10}{r['imm']:>11}"
                 f"{r['ann'] / r['imm']:>10.2f}")
    L.append("")
    L.append("    Un ratio eleve = beaucoup d'annonces pour peu d'immeubles :")
    L.append("    soit une mise en marche groupee, soit des republications.")

    L.append("")
    L.append("  " + "─" * 118)
    L.append(f"  genere le {datetime.now():%d/%m/%Y %H:%M}  ·  lecture seule")
    L.append("")

    texte = "\n".join(L)
    print(texte)
    if a.md:
        dst = os.path.join(os.path.dirname(db), "bilan.md")
        open(dst, "w", encoding="utf-8").write("```\n" + texte + "\n```\n")
        print(f"  ecrit : {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
