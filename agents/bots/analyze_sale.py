"""analyze-sale — suivre le côté vente entre deux études.

Tout se calcule sur `listings_sane` : le périmètre assaini est la source unique
de vérité. Ne jamais refiltrer à la main — un filtre local diverge fatalement
des bornes centrales (lib/market-bounds.ts).
"""
from __future__ import annotations

import glob
import json
import os

from agents.core import db, escalation

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOTS = os.path.join(os.path.dirname(ROOT), "study", "snapshots")

# Double médiane par condo : 1 immeuble = 1 voix. Neutralise vétusté, vue, étage.
SQL = """
with par_condo as (
  select khet, condo_name,
         percentile_cont(0.5) within group (order by price_per_sqm) as ppsqm
  from listings_sane
  where deal_type = 'sale' and status = 'active'
    and price_per_sqm is not null and condo_name is not null
    and khet is not null
  group by khet, condo_name
)
select khet,
       count(*) as n_condos,
       percentile_cont(0.5) within group (order by ppsqm) as median_ppsqm
from par_condo
group by khet
having count(*) >= 5
order by median_ppsqm desc
"""


def dernier_snapshot() -> dict | None:
    fichiers = sorted(glob.glob(os.path.join(SNAPSHOTS, "*.json")))
    if not fichiers:
        return None
    try:
        return json.load(open(fichiers[-1], encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _reference(snap: dict | None) -> dict[str, float]:
    """Extrait {khet: prix/m²} du snapshot, quelle que soit sa forme exacte."""
    if not snap:
        return {}
    for cle in ("khet_stats", "D01", "khets"):
        bloc = snap.get(cle)
        if isinstance(bloc, dict):
            out = {}
            for khet, v in bloc.items():
                if isinstance(v, dict):
                    p = v.get("median_ppsqm") or v.get("sale_ppsqm") or v.get("ppsqm")
                    if isinstance(p, (int, float)):
                        out[khet] = float(p)
            if out:
                return out
    return {}


def run(led, run_id: int, lane: str, spec: dict) -> dict:
    lignes = db.query(SQL)
    ref = _reference(dernier_snapshot())

    detail, mouvements = [], 0
    for r in lignes:
        khet = r["khet"]
        actuel = float(r["median_ppsqm"] or 0)
        avant = ref.get(khet)
        delta = ((actuel - avant) / avant * 100) if avant else None
        detail.append({"khet": khet, "median_ppsqm": round(actuel),
                       "n_condos": r["n_condos"],
                       "delta_pct": round(delta, 1) if delta is not None else None})
        if delta is not None and abs(delta) > 5:
            mouvements += 1
            sev = "medium" if abs(delta) > 15 else "low"
            led.finding("analyze-sale", sev, "mouvement_prix",
                        f"{khet} : prix/m² vente {delta:+.1f} % vs snapshot précédent",
                        {"khet": khet, "avant": avant, "apres": actuel,
                         "n_condos": r["n_condos"]}, run_id)
            if abs(delta) > 15:
                escalation.create(
                    agent="analyze-sale", kind="mouvement_anormal", severity="medium",
                    subject=f"{khet} : {delta:+.1f} % sur le prix/m² vente",
                    evidence={"khet": khet, "avant": avant, "apres": actuel,
                              "n_condos": r["n_condos"]},
                    asked_of_claude="Déterminer s'il s'agit du marché ou d'un effet de "
                                    "composition (lot d'annonces neuves, changement de mix). "
                                    "Un mouvement de plus de 15 % en 4 jours est presque "
                                    "toujours un artefact.",
                    ledger=led)

    # Décotes signalées par la vue existante (déjà bâtie sur le périmètre assaini)
    try:
        decotes = db.scalar(
            "select count(*) from opportunites where decote_pct > 40") or 0
    except Exception:  # noqa: BLE001 — la vue peut évoluer
        decotes = 0

    return {"khets_analyses": len(lignes), "mouvements": mouvements,
            "decotes_signalees": int(decotes), "detail": detail[:20]}
