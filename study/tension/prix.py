"""prix.py — le prix/m² de l'annonce face à l'immeuble, puis aux lots identiques.

Demande de l'utilisateur (2026-10-17) : un visuel prix et une comparaison du
prix/m² d'abord à l'IMMEUBLE, puis à l'immeuble à mêmes chambres et même surface.
Quand l'immeuble n'a pas assez de lots comparables, on élargit (1 km, district)
et on l'écrit : la maille effective fait partie du résultat.

On compare au stock ACTIF à la fin de la fenêtre (prix affichés), pas à des
ventes : on n'en a pas.
"""
from __future__ import annotations

import statistics

from . import coeur

MIN_COMPARABLES = 5   # sous 5 lots, une médiane et un rang ne veulent rien dire


def comparer(prix_m2: float, fs: list[coeur.Faits]) -> dict:
    v = sorted(f.prix_m2 for f in fs if f.active_fin and f.prix_m2)
    out = {"n": len(v)}
    if len(v) < MIN_COMPARABLES:
        out["verdict"] = "not enough comparables"
        return out
    q = statistics.quantiles(v, n=4)
    med = statistics.median(v)
    moins_cher = sum(1 for x in v if x < prix_m2)
    out.update(mediane=med, p25=q[0], p75=q[2], min=v[0], max=v[-1],
               ecart=prix_m2 / med - 1,
               rang_pct=round(100 * moins_cher / len(v)),     # % des comparables moins chers
               verdict=("below most comparables" if prix_m2 < q[0] else
                        "above most comparables" if prix_m2 > q[2] else "in line"),
               points=v)
    return out
