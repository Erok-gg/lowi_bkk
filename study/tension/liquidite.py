"""liquidite.py — « pourrai-je revendre ce bien facilement, et dans X ans ? »

DIFFÉRENCE AVEC LA TENSION. La tension dit qui a la main AUJOURD'HUI (acheteur ou
vendeur). La liquidité dit avec quelle facilité un bien de ce type se REVEND, au
prix du marché, et comment cette facilité évolue quand l'immeuble vieillit.

POSTULAT (décision de l'utilisateur, 2026-10-17) : on revend à la valeur de
marché. On ne mesure donc la vitesse que sur les cohortes affichées près de la
médiane de leur immeuble (±10 %) : une annonce surévaluée reste en ligne
longtemps à cause de son prix, pas du marché, et fausserait la mesure.

TROIS SIGNAUX, notés sur 100 comme la tension (50 = district typique)
  vitesse     âge médian de sortie (Kaplan-Meier, censure comprise)   court = liquide
  vente90     probabilité de partir dans les 90 jours = 1 − S(90)       haut = liquide
  profondeur  ln(1 + sorties par mois) : un marché où il se passe       haut = liquide
              quelque chose se revend mieux qu'un marché à trois ventes

L'ÂGE DE L'IMMEUBLE. La vitesse est remesurée par tranche d'âge sur tout Bangkok
(mêmes chambres) : c'est la courbe qui dit, d'après NOS données, si un immeuble
de 20 ans se revend plus lentement qu'un de 5 ans. La projection à +5 / +10 ans
applique à la vitesse actuelle le rapport entre la tranche d'âge future et la
tranche actuelle. Aucun coefficient « travaux » n'est inventé : les jalons de
gros entretien sont dans la config, VIDES tant que personne ne les a sourcés.
"""
from __future__ import annotations

import math
import statistics

from . import coeur

SENS = {"vitesse": -1, "vente90": +1, "profondeur": +1}
FAMILLE = {s: s for s in SENS}


def au_prix_du_marche(fs: list[coeur.Faits], tol: float, min_pairs: int = 3) -> list[coeur.Faits]:
    """Garde les cohortes affichées à ±tol du prix/m² de leurs PAIRS.

    Pairs = même immeuble ET même nombre de chambres (au moins `min_pairs`
    cohortes avec prix), sinon mêmes chambres dans la maille, sinon la maille.
    Comparer à tout l'immeuble mélangeait studios et 3 chambres : un petit lot
    est toujours plus cher au m², et le filtre écartait des lots normaux
    (défaut trouvé par le test « surévaluées », 2026-10-17)."""
    avec = [f for f in fs if f.prix_m2]
    if not avec:
        return []
    groupes: dict[tuple, list[float]] = {}
    for f in avec:
        groupes.setdefault((f.condo, f.chambres), []).append(f.prix_m2)
        groupes.setdefault((None, f.chambres), []).append(f.prix_m2)
    # Une médiane par GROUPE, calculée une fois : la version précédente la
    # recalculait pour chaque cohorte (~9 000² opérations sur Bangkok, × 200
    # tirages × 20 mailles) — le bilan d'une annonce dépassait 15 min.
    med = {k: statistics.median(v) for k, v in groupes.items() if len(v) >= min_pairs}
    med_maille = statistics.median(f.prix_m2 for f in avec)
    out = []
    for f in avec:
        ref = med.get((f.condo, f.chambres)) or med.get((None, f.chambres)) or med_maille
        if abs(f.prix_m2 / ref - 1) <= tol:
            out.append(f)
    return out


def signaux(fs: list[coeur.Faits], cfg: dict) -> dict:
    L = cfg["liquidite"]
    mk = au_prix_du_marche(fs, L["tolerance_prix"])
    risque = [f for f in mk if f.a_risque]
    n, sorties = len(risque), sum(f.sortie for f in risque)
    spells = [(f.entree, f.age_fin, f.sortie) for f in mk]
    courbe = coeur.kaplan_meier(spells)
    s90 = coeur.survie_a(courbe, 90)
    return {"n": n, "sorties": sorties,
            "vitesse": coeur.kaplan_meier_mediane(spells),
            "vente90": (1 - s90) if s90 is not None else None,
            "profondeur": math.log1p(sorties * 30 / cfg["fenetre_jours"]) if n else None}


LIQUIDITE = coeur.Modele("liquidite", SENS, FAMILLE, lambda cfg: cfg["liquidite"]["poids"], signaux,
                         ("hard to resell", "average", "easy to resell"),
                         ("leaning hard", "leaning easy"))


def tranche(age: int | None, bornes: list[int]) -> str | None:
    if age is None or age < 0:
        return None
    for lo, hi in zip(bornes, bornes[1:]):
        if lo <= age < hi:
            return f"{lo}-{hi}"
    return f"{bornes[-1]}+"


def courbe_age(fs: list[coeur.Faits], cfg: dict) -> dict[str, dict]:
    """Vitesse et probabilité à 90 j par tranche d'âge d'immeuble, avec effectifs.
    Une tranche sous le minimum de cohortes n'a pas de valeur (None)."""
    L = cfg["liquidite"]
    groupes: dict[str, list[coeur.Faits]] = {}
    for f in fs:
        t = tranche(f.age_immeuble, L["tranches_age"])
        if t:
            groupes.setdefault(t, []).append(f)
    out = {}
    for t, g in groupes.items():
        sig = signaux(g, cfg)
        ok = sig["n"] >= cfg["minimum"]["cohortes"] and sig["sorties"] >= cfg["minimum"]["sorties"]
        out[t] = {"n": sig["n"], "sorties": sig["sorties"],
                  "vitesse": sig["vitesse"] if ok else None,
                  "vente90": sig["vente90"] if ok else None}
    return out


def projeter(sig: dict, age: int | None, courbe: dict, ref: dict, cfg: dict) -> list[dict]:
    """Score de liquidité recalculé à +H ans, en appliquant à la vitesse et à la
    probabilité à 90 j le rapport « tranche d'âge future / tranche actuelle ».
    Sans âge connu, ou si l'une des deux tranches manque de données : pas de
    projection, et on le dit."""
    L = cfg["liquidite"]
    out = []
    now = courbe.get(tranche(age, L["tranches_age"]) or "", {})
    for h in L["horizons_ans"]:
        fut_t = tranche(age + h, L["tranches_age"]) if age is not None else None
        fut = courbe.get(fut_t or "", {})
        r = {"horizon_ans": h, "age_futur": (age + h) if age is not None else None,
             "tranche": fut_t, "jalons": [j for j in L["jalons_travaux"]
                                         if age is not None and age < j["age"] <= age + h]}
        if not (now.get("vitesse") and fut.get("vitesse") and sig.get("vitesse")):
            r.update(score=None, raison="âge inconnu ou tranche d'âge sans assez de données")
            out.append(r)
            continue
        proj = dict(sig)
        proj["vitesse"] = sig["vitesse"] * fut["vitesse"] / now["vitesse"]
        if sig.get("vente90") and now.get("vente90") and fut.get("vente90"):
            proj["vente90"] = min(1.0, sig["vente90"] * fut["vente90"] / now["vente90"])
        sc, _ = coeur.score(proj, ref, cfg, LIQUIDITE)
        r.update(score=round(sc) if sc is not None else None,
                 rapport_vitesse=fut["vitesse"] / now["vitesse"])
        out.append(r)
    return out
