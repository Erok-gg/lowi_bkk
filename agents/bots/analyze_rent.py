"""analyze-rent — côté location, puis recoupement vente↔location par immeuble.

Le rendement se calcule WITHIN-CONDO : loyer et prix du MÊME immeuble. Un ratio
de deux médianes indépendantes mesure autre chose — et se fait piéger par la
composition du parc.

Le recoupement n'est PAS une fusion : on associe, on ne confond pas.
"""
from __future__ import annotations

import os

from agents.core import db, escalation

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SQL_LOYERS = """
with par_condo as (
  select khet, condo_name,
         percentile_cont(0.5) within group (order by price / nullif(area_sqm,0))
           as loyer_sqm
  from listings_sane
  where deal_type = 'rent' and status = 'active' and area_sqm > 0
    and condo_name is not null and khet is not null
  group by khet, condo_name
)
select khet, count(*) as n_condos,
       percentile_cont(0.5) within group (order by loyer_sqm) as median_rent_sqm
from par_condo group by khet having count(*) >= 5
"""

# Rendement within-condo : le même immeuble doit avoir vente ET location actives.
SQL_RENDEMENT = """
with v as (
  select khet, condo_name,
         percentile_cont(0.5) within group (order by price) as prix
  from listings_sane
  where deal_type='sale' and status='active' and condo_name is not null
    and khet is not null
  group by khet, condo_name
),
l as (
  select khet, condo_name,
         percentile_cont(0.5) within group (order by price) as loyer
  from listings_sane
  where deal_type='rent' and status='active' and condo_name is not null
    and khet is not null
  group by khet, condo_name
),
apparies as (
  select v.khet, v.condo_name, l.loyer * 12 / nullif(v.prix,0) * 100 as rdt
  from v join l on v.khet=l.khet and v.condo_name=l.condo_name
  where v.prix > 0 and l.loyer > 0
)
select khet, count(*) as n_condos,
       percentile_cont(0.5) within group (order by rdt) as yield_pct
from apparies group by khet having count(*) >= 5
"""


def run(led, run_id: int, lane: str, spec: dict) -> dict:
    loyers = {r["khet"]: r for r in db.query(SQL_LOYERS)}
    rdts = {r["khet"]: r for r in db.query(SQL_RENDEMENT)}

    detail, suspects = [], 0
    total_condos = 0
    for khet, r in rdts.items():
        y = float(r["yield_pct"] or 0)
        n = int(r["n_condos"])
        total_condos += n
        lo = loyers.get(khet)
        detail.append({
            "khet": khet, "yield_pct": round(y, 2), "n_condos": n,
            "median_rent_sqm": round(float(lo["median_rent_sqm"]), 1) if lo else None,
            "low_sample": n < 20,
        })
        if y > 10:
            suspects += 1
            led.finding("analyze-rent", "medium", "rendement_suspect",
                        f"{khet} : rendement médian {y:.1f} % — au-delà du plausible",
                        {"khet": khet, "yield_pct": y, "n_condos": n}, run_id)
            escalation.create(
                agent="analyze-rent", kind="rendement_suspect", severity="medium",
                subject=f"{khet} : rendement médian à {y:.1f} %",
                evidence={"khet": khet, "yield_pct": y, "n_condos": n},
                asked_of_claude="Un rendement de quartier au-delà de 10 % signale presque "
                                "toujours un défaut de donnée (prix mal classé, surface "
                                "aberrante) plutôt qu'une affaire. Vérifier les annonces "
                                "sous-jacentes avant toute conclusion.",
                ledger=led)

    return {"khets_analyses": len(rdts), "condos_apparies": total_condos,
            "mouvements": suspects, "detail": sorted(
                detail, key=lambda d: -d["yield_pct"])[:20]}
