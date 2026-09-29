"""mesure-cadence.py — ce que la cadence quotidienne change vraiment.

POURQUOI CE SCRIPT EXISTE
L'extraction est passée de 4 jours à 1 jour le 2026-08-23. Trois promesses ont
été faites en la décidant, et aucune n'est vraie tant qu'elle n'est pas mesurée
(règle 1) :

  1. **ça coûte moins cher** — à cadence resserrée, presque tout ce que le scan
     voit devrait déjà être en base au même prix, donc évité par la dédup
     incrémentale (prix inchangé dans la liste → fiche non re-visitée) ;
  2. **la donnée est plus fraîche** — un stock revu chaque jour au lieu de tous
     les quatre ;
  3. **les calculs y gagnent** — plus de points de prix observés, des cohortes
     échantillonnées plus finement.

Et un risque, à surveiller autant que les gains : le délai de grâce du
délistage vaut 2 scans CONSÉCUTIFS. Il représentait 8 jours d'absence, il en
représente 2. Une annonce simplement sortie de la fenêtre de 150 pages pendant
deux nuits sera délistée. Si ce chiffre s'envole sans que le marché bouge, la
tension et le churn mesurent la cadence de scan, pas le marché.

CE SCRIPT NE CONCLUT RIEN : il pose les chiffres côte à côte, avant et après la
bascule. Lancé n'importe quand, il lit le ledger des agents et la base locale.

Usage :
    scraper/.venv/Scripts/python.exe ops/mesure-cadence.py [--jours 14]
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agents.core.metrics import aplatir  # noqa: E402

#: Jour de la bascule 4 j → 1 j. Sépare l'avant de l'après dans tous les tableaux.
BASCULE = "2026-08-24"

LEDGER = ROOT / "agents" / "ledger.db"
BASE = Path(os.environ.get("LOWI_DB") or (
    Path(os.environ.get("LOWI_OUTPUT_DIR") or (ROOT / "scraper" / "output")) / "bangkok.db"))


def _lignes(cx, sql, params=()):
    cx.row_factory = sqlite3.Row
    return cx.execute(sql, params).fetchall()


def vitesse_et_dedup(depuis: str) -> None:
    """Durée et composition de chaque run d'extraction, dédup comprise."""
    print("\n── 1. COÛT D'UN CYCLE ET PART DE DÉDUP " + "─" * 40)
    print(f"{'jour':11} {'source':22} {'durée':>8} {'scannées':>9} {'neuves':>7} "
          f"{'chang.':>7} {'retirées':>9} {'dédup':>7} {'part':>6}")
    cx = sqlite3.connect(f"file:{LEDGER}?mode=ro", uri=True)
    par_jour: dict[str, list] = defaultdict(list)
    for r in _lignes(cx, "select agent, started_at, ended_at, metrics from agent_runs "
                         "where agent like 'extract-%' and status='ok' and started_at >= ? "
                         "order by started_at", (depuis,)):
        m = aplatir(json.loads(r["metrics"] or "{}"))
        duree = ""
        if r["ended_at"]:
            d = (datetime.fromisoformat(r["ended_at"])
                 - datetime.fromisoformat(r["started_at"])).total_seconds()
            duree = f"{int(d // 3600)}h{int(d % 3600 // 60):02d}"
        vus = m.get("scannees") or 0
        dedup = m.get("dedup")
        part = f"{100 * dedup / vus:.0f} %" if dedup is not None and vus else "—"
        jour = r["started_at"][:10]
        par_jour[jour].append(m)
        print(f"{jour:11} {r['agent']:22} {duree:>8} {vus:>9} "
              f"{str(m.get('nouvelles', '—')):>7} {str(m.get('changees', '—')):>7} "
              f"{str(m.get('retirees', '—')):>9} {str(dedup if dedup is not None else '—'):>7} "
              f"{part:>6}")
    cx.close()
    print("\n  `dédup` = annonces revues dont le prix n'avait pas bougé dans la liste,")
    print("  donc dont la page détail n'a pas été rouverte. C'est l'économie réelle.")
    print("  Vide sur les runs d'avant le 2026-08-23 : la métrique n'était pas capturée.")


def fraicheur() -> None:
    """Quelle part du stock actif a été revue récemment, par source."""
    print("\n── 2. FRAÎCHEUR DU STOCK ACTIF " + "─" * 47)
    cx = sqlite3.connect(f"file:{BASE}?mode=ro", uri=True)
    maintenant = datetime.now(timezone.utc)
    seuils = [("24 h", 1), ("48 h", 2), ("4 j", 4), ("8 j", 8)]
    print(f"{'source':16} {'actives':>8} " + " ".join(f"{lib:>8}" for lib, _ in seuils))
    for r in _lignes(cx, "select source, count(*) n from listings "
                         "where status='active' group by source order by n desc"):
        parts = []
        for _, j in seuils:
            limite = (maintenant - timedelta(days=j)).isoformat()
            n = cx.execute("select count(*) from listings where status='active' "
                           "and source=? and last_seen >= ?", (r["source"], limite)).fetchone()[0]
            parts.append(f"{100 * n / r['n']:.0f} %")
        print(f"{r['source']:16} {r['n']:>8} " + " ".join(f"{p:>8}" for p in parts))
    cx.close()
    print("\n  Une source dont la colonne 24 h reste basse n'est pas rafraîchie par la")
    print("  cadence : son catalogue déborde la fenêtre de scan (cf. le recensement).")


def churn(jours: int) -> None:
    """Entrées et sorties du stock, jour par jour. Le risque de la cadence."""
    print("\n── 3. ENTRÉES ET SORTIES PAR JOUR " + "─" * 44)
    cx = sqlite3.connect(f"file:{BASE}?mode=ro", uri=True)
    depuis = (datetime.now(timezone.utc) - timedelta(days=jours)).isoformat()
    entrees = {r["j"]: r["n"] for r in _lignes(
        cx, "select substr(first_seen,1,10) j, count(*) n from listings "
            "where first_seen >= ? group by j", (depuis,))}
    sorties = {r["j"]: r["n"] for r in _lignes(
        cx, "select substr(delisted_at,1,10) j, count(*) n from listings "
            "where delisted_at >= ? group by j", (depuis,))}
    prix = {r["j"]: r["n"] for r in _lignes(
        cx, "select substr(observed_at,1,10) j, count(*) n from price_history "
            "where observed_at >= ? group by j", (depuis,))}
    cx.close()
    print(f"{'jour':12} {'nouvelles':>10} {'délistées':>10} {'prix observés':>14}   cadence")
    for j in sorted(set(entrees) | set(sorties) | set(prix)):
        regime = "1 j" if j >= BASCULE else "4 j"
        print(f"{j:12} {entrees.get(j, 0):>10} {sorties.get(j, 0):>10} "
              f"{prix.get(j, 0):>14}   {regime}")
    print("\n  `délistées` est le chiffre à surveiller : le délai de grâce vaut 2 scans,")
    print("  soit 2 jours désormais contre 8 avant. Une hausse sans hausse des")
    print("  nouvelles signalerait un délistage par manque de couverture, pas par")
    print("  départ réel du marché — c'est ce qui contaminerait la tension.")


def cohortes(jours: int) -> None:
    """Ce qui alimente la tension : un instantané de stock par scan."""
    print("\n── 4. ÉCHANTILLONNAGE DES COHORTES (entrée de la tension) " + "─" * 20)
    cx = sqlite3.connect(f"file:{BASE}?mode=ro", uri=True)
    depuis = (datetime.now(timezone.utc) - timedelta(days=jours)).isoformat()
    print(f"{'jour':12} {'instantanés':>12} {'cohortes':>10}")
    for r in _lignes(cx, "select substr(taken_at,1,10) j, count(*) n, "
                         "count(distinct unit_key) u from cohort_snapshots "
                         "where taken_at >= ? group by j order by j", (depuis,)):
        print(f"{r['j']:12} {r['n']:>12} {r['u']:>10}")
    cx.close()
    print("\n  Un point par jour au lieu d'un tous les quatre : l'écoulement se mesure")
    print("  sur des pas plus fins, mais toute série qui enjambe le 2026-08-24 change")
    print("  de pas au milieu. À traiter comme une rupture, pas comme une évolution.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Effet mesuré de la cadence quotidienne.")
    ap.add_argument("--jours", type=int, default=14)
    args = ap.parse_args()
    depuis = (datetime.now(timezone.utc) - timedelta(days=args.jours)).isoformat()

    if not BASE.exists():
        sys.exit(f"base locale introuvable : {BASE}")
    print(f"Mesure sur {args.jours} jours — bascule 4 j → 1 j le {BASCULE}")
    print(f"base : {BASE}")
    vitesse_et_dedup(depuis)
    fraicheur()
    churn(args.jours)
    cohortes(args.jours)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
