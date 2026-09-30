"""social_calibrage.py — dédoublonnage par caractéristiques, filtres de
qualité et comparaison aux plateformes pour les annonces Facebook
(`social-leads.db`). Chaque exécution conserve ses statistiques pour affiner
les seuils plus tard.

Demandé le 2026-09-30 (« compare par caractéristique, applique les filtres
qui te semblent les plus cohérents, garde toutes les statistiques de tes
choix »). Point de départ mesuré ce jour-là sur 406 fiches chargées
(docs/etudes/facebook-2026-09-30.md) :
  - 23,6 % de doublons exacts, 29,3 % à ±2 m² / ±5 % : la déduplication par
    hachage de texte ET de groupe (`lead_id`) laissait passer le même bien
    posté dans plusieurs groupes (63 groupes de doublons sur 76) ou par
    plusieurs agents (31 sur 76) ;
  - 80 % des locations comparables (179 / 225) sont le même logement que sur
    une plateforme — seules les exclusives apportent une information neuve.

RIEN N'EST SUPPRIMÉ. Les lignes sont MARQUÉES (`dedup_of`, `quality_flags`,
`on_platforms`), et deux vues donnent le périmètre utile :
  social_leads_uniques     un bien = une ligne, hors drapeaux d'exclusion
  social_leads_exclusives  uniques absents des plateformes
Retour arrière : les colonnes ajoutées sont ignorées par le chargeur
(`load_social_leads.COLS` ne les contient pas) ; `drop view` des deux vues
et ne plus appeler `calibrer()` rend l'état d'avant.

Usage : python scraper/social_calibrage.py        (toute la table)
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import statistics as st
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SOCIAL_DB = Path(os.environ.get("LOWI_SOCIAL_DB") or BASE / "scraper" / "output" / "social-leads.db")
REF_DB = BASE / "scraper" / "output" / "bangkok.db"
CALIB_DIR = BASE / "scraper" / "output" / "social" / "calibrage"

# ─── Seuils retenus (tous rejoués dans la grille de sensibilité) ────────────
# Doublon « même bien » : même immeuble × type × chambres, surface ±2 m²,
# prix ±5 %. Mesuré le 2026-09-30 : l'exact (surface arrondie, prix égal)
# trouve 96 lignes en trop, cette tolérance 119. Les 23 d'écart sont des
# reformulations du même bien (« 35 m² » / « 35.5 sqm », « 25k » / « 24,900 »).
DUP_SURFACE_M2 = 2.0
DUP_PRIX_PCT = 5.0
# Même logement sur une plateforme : surface ±7 % (tolérance de
# lib/cross-match.ts, déjà utilisée pour apparier vente ↔ location) et prix
# ±5 %. Deux unités identiques du même immeuble au même prix se confondent :
# le taux obtenu est un PLAFOND.
PLAT_SURFACE_PCT = 7.0
PLAT_PRIX_PCT = 5.0
# Référence de prix : annonces ACTIVES du même immeuble × chambres, dans les
# bornes de plausibilité, et au moins 3 pour qu'une médiane ait un sens.
REF_MIN_N = 3
# Bornes de plausibilité — alignées sur lib/market-bounds.ts et la vue
# listings_sane (CLAUDE.md : « les deux doivent rester alignés », ici aussi).
BORNES = {"sale": (800_000, 100_000_000), "rent": (3_000, 500_000)}
SURFACE = (15, 500)
# Loyer au m² aberrant : mesuré le 2026-09-30, médiane 657 THB, p10–p90
# 392–1 029 ; 4 fiches sur 393 hors 150–2 000 (loyer lu comme prix de vente,
# surface en pieds carrés…). Exclu des statistiques, pas supprimé.
LOYER_M2 = (150, 2_000)
# Écart relatif au marché de l'immeuble au-delà duquel on ne croit plus au
# chiffre sans relecture : drapeau d'alerte, NON exclusif (une vraie affaire
# à −40 % existe ; c'est justement ce qu'on cherche dans les exclusives).
ECART_SUSPECT_PCT = 40.0

EXCLUANTS = ("hors_bornes", "loyer_m2_aberrant")

COLONNES = {
    "dedup_of": "text", "on_platforms": "integer", "platform_ids": "text",
    "ref_n": "integer", "ref_median_psqm": "real", "deviation_psqm_pct": "real",
    "quality_flags": "text", "calibrated_at": "text",
}


def _norm(s) -> str:
    return re.sub(r"[^a-z0-9ก-๙]", "", str(s or "").lower())


def _num(v):
    try:
        x = float(v)
        return x if x > 0 else None
    except (TypeError, ValueError):
        return None


def _prix_ref(r) -> float | None:
    """Le montant qui identifie le bien : loyer pour une location (y compris
    vente+location, 386+6 fiches sur 406), prix pour une vente."""
    return r["rent_monthly"] if r["deal_type"] != "sale" else r["price"]


def _proches(a, b, surf, pct) -> bool:
    pa, pb = _prix_ref(a), _prix_ref(b)
    return bool(a["area_sqm"] and b["area_sqm"] and pa and pb
                and abs(a["area_sqm"] - b["area_sqm"]) <= surf
                and abs(pa - pb) / max(pa, pb) * 100 <= pct)


def grouper(leads: list[dict], surf=DUP_SURFACE_M2, pct=DUP_PRIX_PCT) -> dict[str, str]:
    """id → id canonique du bien. Canonique = première vue (first_seen),
    puis confiance la plus haute : on garde l'annonce d'origine, pas la
    republication."""
    seaux = defaultdict(list)
    for r in leads:
        seaux[(_norm(r["condo_name"] or r["condo_name_raw"]), r["deal_type"], r["bedrooms"])].append(r)
    parent = {r["id"]: r["id"] for r in leads}

    def racine(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for v in seaux.values():
        for i in range(len(v)):
            for j in range(i + 1, len(v)):
                if _proches(v[i], v[j], surf, pct):
                    parent[racine(v[i]["id"])] = racine(v[j]["id"])
    groupes = defaultdict(list)
    for r in leads:
        groupes[racine(r["id"])].append(r)
    canon = {}
    for membres in groupes.values():
        tete = min(membres, key=lambda r: (r["first_seen"] or "", -(r["confidence"] or 0), r["id"]))
        for r in membres:
            canon[r["id"]] = tete["id"]
    return canon


def _charger_leads(con) -> list[dict]:
    con.row_factory = sqlite3.Row
    out = []
    for row in con.execute("select * from social_leads"):
        r = dict(row)
        for k in ("price", "rent_monthly", "area_sqm", "bedrooms", "confidence"):
            r[k] = _num(r[k])
        r["condo_name"] = None if r["condo_name"] in (None, "None", "") else r["condo_name"]
        out.append(r)
    return out


def _referentiel(condos: set[str]) -> dict[str, list[tuple]]:
    """Annonces des plateformes pour les seuls immeubles rapprochés — lecture
    seule de bangkok.db, sans verrou sur le scrap en cours."""
    ref = defaultdict(list)
    if not condos or not REF_DB.exists():
        return ref
    c = sqlite3.connect(f"file:{REF_DB.as_posix()}?mode=ro", uri=True)
    lst = sorted(condos)
    for i in range(0, len(lst), 500):
        lot = lst[i:i + 500]
        for row in c.execute(
                "select condo_name, deal_type, status, price, area_sqm, bedrooms, khet, id, source "
                f"from listings where condo_name in ({','.join('?' * len(lot))})", lot):
            ref[row[0]].append(row)
    c.close()
    return ref


def _dans_bornes(deal, prix, surface) -> bool:
    lo, hi = BORNES[deal]
    return bool(prix and surface and lo <= prix <= hi and SURFACE[0] <= surface <= SURFACE[1])


def _comparer(r, ref, surf_pct=PLAT_SURFACE_PCT, prix_pct=PLAT_PRIX_PCT) -> dict:
    """Présence sur les plateformes + écart au m² au marché de l'immeuble."""
    res = {"on_platforms": None, "platform_ids": [], "ref_n": 0,
           "ref_median_psqm": None, "deviation_psqm_pct": None}
    if not r["condo_name"] or not r["area_sqm"]:
        return res
    lignes = ref.get(r["condo_name"], [])
    res["on_platforms"] = 0
    for deal, val in (("rent", r["rent_monthly"]), ("sale", r["price"])):
        if not val:
            continue
        for x in lignes:
            if (x[1] == deal and x[5] == r["bedrooms"] and x[4] and x[3]
                    and abs(x[4] - r["area_sqm"]) / r["area_sqm"] * 100 <= surf_pct
                    and abs(x[3] - val) / val * 100 <= prix_pct):
                res["on_platforms"] = 1
                if len(res["platform_ids"]) < 5:
                    res["platform_ids"].append(x[7])
    deal = "sale" if r["deal_type"] == "sale" else "rent"
    val = _prix_ref(r)
    base = [x[3] / x[4] for x in lignes if x[1] == deal and x[2] == "active"
            and x[5] == r["bedrooms"] and _dans_bornes(deal, x[3], x[4])]
    res["ref_n"] = len(base)
    if val and len(base) >= REF_MIN_N:
        med = st.median(base)
        res["ref_median_psqm"] = round(med, 1)
        res["deviation_psqm_pct"] = round(100 * ((val / r["area_sqm"]) / med - 1), 1)
    return res


def _drapeaux(r, comp) -> list[str]:
    f = []
    deal = "sale" if r["deal_type"] == "sale" else "rent"
    val = _prix_ref(r)
    if not _dans_bornes(deal, val, r["area_sqm"]):
        f.append("hors_bornes")
    if deal == "rent" and val and r["area_sqm"] and not (LOYER_M2[0] <= val / r["area_sqm"] <= LOYER_M2[1]):
        f.append("loyer_m2_aberrant")
    if comp["deviation_psqm_pct"] is not None and abs(comp["deviation_psqm_pct"]) > ECART_SUSPECT_PCT:
        f.append("ecart_suspect")
    if not r["condo_name"]:
        f.append("immeuble_non_rapproche")
    elif comp["ref_n"] < REF_MIN_N:
        f.append("reference_insuffisante")
    return f


def _q(v, q):
    v = sorted(v)
    return round(v[min(len(v) - 1, int(q * len(v)))], 1) if v else None


def _resume(ecarts: list[float]) -> dict:
    if not ecarts:
        return {"n": 0}
    return {"n": len(ecarts), "mediane": round(st.median(ecarts), 1), "p25": _q(ecarts, .25),
            "p75": _q(ecarts, .75), "sous_10": sum(e < -10 for e in ecarts),
            "dans_10": sum(-10 <= e <= 10 for e in ecarts), "sur_10": sum(e > 10 for e in ecarts)}


def _migrer(con) -> None:
    exist = {row[1] for row in con.execute("pragma table_info(social_leads)")}
    for col, typ in COLONNES.items():
        if col not in exist:
            con.execute(f"alter table social_leads add column {col} {typ}")
    excl = " and ".join(f"coalesce(quality_flags,'') not like '%{f}%'" for f in EXCLUANTS)
    con.execute("drop view if exists social_leads_uniques")
    con.execute(f"create view social_leads_uniques as select * from social_leads "
                f"where dedup_of is null and {excl}")
    con.execute("drop view if exists social_leads_exclusives")
    con.execute("create view social_leads_exclusives as select * from social_leads_uniques "
                "where on_platforms = 0")
    con.execute("create table if not exists calibration_runs (run_at text primary key, "
                "params text, stats text)")


def calibrer(db: Path | None = None, entonnoir: dict | None = None, ecrire=True) -> dict:
    """Recalcule doublons, drapeaux et comparaison sur TOUTE la table (406
    lignes le 2026-09-30 : < 2 s), puis archive les statistiques."""
    con = sqlite3.connect(db or SOCIAL_DB)
    _migrer(con)
    leads = _charger_leads(con)
    ref = _referentiel({r["condo_name"] for r in leads if r["condo_name"]})
    canon = grouper(leads)
    maintenant = datetime.now(timezone.utc).isoformat(timespec="seconds")
    comps, flags = {}, {}
    for r in leads:
        comps[r["id"]] = _comparer(r, ref)
        flags[r["id"]] = _drapeaux(r, comps[r["id"]])
    if ecrire:
        con.executemany(
            "update social_leads set dedup_of=?, on_platforms=?, platform_ids=?, ref_n=?, "
            "ref_median_psqm=?, deviation_psqm_pct=?, quality_flags=?, calibrated_at=? where id=?",
            [(None if canon[r["id"]] == r["id"] else canon[r["id"]], comps[r["id"]]["on_platforms"],
              json.dumps(comps[r["id"]]["platform_ids"]) if comps[r["id"]]["platform_ids"] else None,
              comps[r["id"]]["ref_n"], comps[r["id"]]["ref_median_psqm"], comps[r["id"]]["deviation_psqm_pct"],
              ",".join(flags[r["id"]]) or None, maintenant, r["id"]) for r in leads])
        con.commit()

    uniques = [r for r in leads if canon[r["id"]] == r["id"]
               and not any(f in flags[r["id"]] for f in EXCLUANTS)]
    stats = statistiques(leads, canon, comps, flags, uniques, ref)
    if entonnoir:
        stats["entonnoir_dernier_chargement"] = entonnoir
    params = {k: v for k, v in globals().items() if k.isupper() and isinstance(v, (int, float, tuple, dict))}
    if ecrire:
        con.execute("insert or replace into calibration_runs values (?,?,?)",
                    (maintenant, json.dumps(params, ensure_ascii=False), json.dumps(stats, ensure_ascii=False)))
        con.commit()
        dossier = Path(os.environ.get("LOWI_CALIB_DIR") or CALIB_DIR)
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / f"calibrage-{maintenant[:10]}.json").write_text(
            json.dumps({"run_at": maintenant, "params": params, "stats": stats}, ensure_ascii=False, indent=1),
            encoding="utf-8")
    con.close()
    return stats


def statistiques(leads, canon, comps, flags, uniques, ref) -> dict:
    n = len(leads)
    en_trop = sum(1 for r in leads if canon[r["id"]] != r["id"])
    tailles = Counter(Counter(canon.values()).values())
    groupes = defaultdict(list)
    for r in leads:
        groupes[canon[r["id"]]].append(r)
    multi = [g for g in groupes.values() if len(g) > 1]
    compar = [r for r in uniques if comps[r["id"]]["on_platforms"] is not None]
    ecarts = [comps[r["id"]]["deviation_psqm_pct"] for r in uniques
              if comps[r["id"]]["deviation_psqm_pct"] is not None and r["deal_type"] != "sale"]
    excl = [r for r in compar if comps[r["id"]]["on_platforms"] == 0]

    def par(cle):
        g = defaultdict(list)
        for r in uniques:
            e = comps[r["id"]]["deviation_psqm_pct"]
            if e is not None and r["deal_type"] != "sale":
                g[cle(r) or "(inconnu)"].append(e)
        return {k: _resume(v) for k, v in sorted(g.items(), key=lambda kv: -len(kv[1])) if len(v) >= 3}

    khet_de = {}
    for nom, lignes in ref.items():
        k = Counter(x[6] for x in lignes if x[6]).most_common(1)
        khet_de[nom] = k[0][0] if k else None

    # Grille de sensibilité : ce que chaque seuil changerait, pour recalibrer
    # sans refaire l'enquête.
    grille_dup = {f"surface±{s}_prix±{p}%": sum(1 for r in leads if grouper(leads, s, p)[r["id"]] != r["id"])
                  for s in (0, 1, 2, 3, 5) for p in (0, 2, 5, 10)}
    grille_plat = {}
    for s in (3, 5, 7, 10):
        for p in (2, 5, 10):
            v = [_comparer(r, ref, s, p)["on_platforms"] for r in uniques if r["condo_name"] and r["area_sqm"]]
            grille_plat[f"surface±{s}%_prix±{p}%"] = f"{sum(v)}/{len(v)}"

    return {
        "lignes": n,
        "biens_distincts": len(groupes),
        "doublons_lignes_en_trop": en_trop,
        "taux_doublons_pct": round(100 * en_trop / n, 1) if n else None,
        "taille_groupes_doublons": dict(sorted(tailles.items())),
        "doublons_multi_groupes_fb": sum(1 for g in multi if len({r["source_group"] for r in g}) > 1),
        "doublons_multi_auteurs": sum(1 for g in multi if len({r["author"] for r in g}) > 1),
        "drapeaux": dict(Counter(f for v in flags.values() for f in v)),
        "uniques_hors_exclusion": len(uniques),
        "comparables": len(compar),
        "sur_plateformes": sum(1 for r in compar if comps[r["id"]]["on_platforms"] == 1),
        "taux_sur_plateformes_pct": round(100 * (len(compar) - len(excl)) / len(compar), 1) if compar else None,
        "exclusives": len(excl),
        "ecart_loyer_m2_tous": _resume(ecarts),
        "ecart_loyer_m2_exclusives": _resume([comps[r["id"]]["deviation_psqm_pct"] for r in excl
                                              if comps[r["id"]]["deviation_psqm_pct"] is not None
                                              and r["deal_type"] != "sale"]),
        "ecart_par_vendeur": par(lambda r: r["seller_type"]),
        "ecart_par_khet": par(lambda r: khet_de.get(r["condo_name"]) or r["khet"]),
        "ecart_par_immeuble": par(lambda r: r["condo_name"]),
        "sensibilite_doublons_lignes_en_trop": grille_dup,
        "sensibilite_sur_plateformes": grille_plat,
    }


if __name__ == "__main__":
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    s = calibrer()
    print(json.dumps({k: v for k, v in s.items() if not k.startswith(("sensibilite", "ecart_par_immeuble"))},
                     ensure_ascii=False, indent=1))
