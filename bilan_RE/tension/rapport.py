"""rapport.py — le bilan d'UNE annonce, en JSON, pour la page beta et le PDF.

    scraper/.venv/Scripts/python.exe -m bilan_RE.tension.rapport --url <URL d'annonce> [--out dossier]

POURQUOI SÉPARÉ DE `bilan()`. Le bilan complet recalcule tout (1 min 30). Le
calcul par cohorte est désormais MENSUEL (décision de l'utilisateur) : la tension
et la liquidité viennent du fichier `scores-latest.json` produit par l'agent
`scores-tension`. Ne reste à calculer à la demande que ce qui dépend de
l'annonce elle-même — son histoire, son prix face aux comparables, ses
drapeaux — soit quelques requêtes SQL : quelques secondes.

Format de sortie : bilan_RE/docs/regles-construction-ui.md (« Contrat du
rapport JSON »). Lecture seule de la base.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

import sys as _sys

from . import coeur, immeuble
from .donnees import DB, RACINE, SORTIES, config

_sys.path.insert(0, os.path.join(RACINE, "scraper"))
from pipeline.normalize import _norm_condo  # noqa: E402


def _noms(c, condo: str, khet: str) -> list[str]:
    """Toutes les graphies d'un même immeuble dans la base. FazWaz écrit « Noble
    Ploenchit », DDproperty « Noble Ploenchit, Bangkok » : comparer les noms bruts
    perdait l'immeuble d'un portail à l'autre (démo du 2026-10-17). Lu par l'index
    `idx_listings_condo_norm` (18 ms) au lieu d'un parcours de la table (1,5 s).
    La colonne est tenue à jour après chaque scrap par repertorier-annonces.py."""
    cle = _norm_condo(condo)
    try:
        noms = {n for (n,) in c.execute("select distinct trim(condo_name) from listings "
                                        "where condo_norm = ?", (cle,))}
    except sqlite3.OperationalError as e:
        raise SystemExit("colonne condo_norm absente : lancer "
                         "bilan_RE/ops/repertorier-annonces.py sur cette base") from e
    return sorted(noms | {condo})


def _in(noms: list[str]) -> str:
    return "trim(condo_name) in (" + ",".join("?" * len(noms)) + ")"

RAPPORTS = os.path.join(SORTIES, "rapports")
TOL_SURFACE = 0.15
MIN_COMPARABLES = 5
SOURCES_LISIBLES = {"ddproperty": "DDproperty", "fazwaz": "FazWaz / Thaiger", "propertyscout": "PropertyScout",
                    "nestopa": "Nestopa", "livinginsider": "LivingInsider",
                    "propertyhub": "PropertyHub", "hipflat": "Hipflat",
                    "dotproperty": "DotProperty"}

#: Sources dont la date de création déclarée est PLAUSIBLEMENT une vraie date de
#: création et non une remontée en tête de liste. Mesure du 2026-10-22 : chez
#: PropertyScout elle croît strictement avec l'identifiant (10 fiches, 2020 → 2026).
#: DDproperty est EXCLUE (son `posted_at` est une date de remontée, écart médian
#: −16 j avec first_seen) ; FazWaz plausible mais non testé. Ajouter une source =
#: refaire ce test d'abord. Retour arrière : vider ce tuple.
SOURCES_DATE_FIABLE = ("propertyscout",)


def identifiant(url: str) -> str:
    """Identifiant non devinable et stable pour une URL (même URL → même rapport)."""
    return hashlib.sha256(url.strip().encode()).hexdigest()[:16]


def _norm_url(u: str) -> str:
    return u.strip().split("?")[0].split("#")[0].rstrip("/")


def trouver(c: sqlite3.Connection, url: str):
    """L'annonce de VENTE derrière une URL collée : exacte, puis sans paramètres,
    puis par l'identifiant numérique de fin d'URL (les portails changent leur slug)."""
    u = _norm_url(url)
    for q, a in (("source_url = ?", url.strip()), ("source_url = ?", u),
                 ("rtrim(source_url, '/') = ?", u)):
        r = c.execute(f"select id from listings where {q} and deal_type = 'sale' "
                      "order by status = 'active' desc limit 1", (a,)).fetchone()
        if r:
            return r[0]
    m = re.search(r"(\d{5,})/?$", u) or re.search(r"-u?(\d{5,})", u)
    if m:
        r = c.execute("select id from listings where source_url like ? and deal_type = 'sale' "
                      "order by status = 'active' desc limit 1", (f"%{m.group(1)}%",)).fetchone()
        if r:
            return r[0]
    return None


def _meme_lot(a, b) -> bool:
    """Deux annonces décrivent-elles le même lot ? Même étage si les deux le
    donnent, surface à ±1 m², prix à ±5 %. La cohorte seule ne suffit pas :
    mesuré le 2026-10-17, « The Lumpini 24, 2 ch., 55 m² » regroupe 97 annonces
    qui sont des dizaines de lots distincts (la doc de `unit_key` le prévient)."""
    if a["etage"] is not None and b["etage"] is not None and a["etage"] != b["etage"]:
        return False
    if a["surface"] is None or b["surface"] is None or abs(a["surface"] - b["surface"]) > 1:
        return False
    return bool(a["prix"] and b["prix"]) and abs(a["prix"] / b["prix"] - 1) <= 0.05


def _histoire(c, lid: str, uk: str, aujourdhui: date) -> dict:
    """Chaîne de l'annonce : elle-même + ses copies (autres portails, autres
    agents) et ses republications (retrait puis retour à moins de 14 j)."""
    rows = c.execute("""select id, source, first_seen, delisted_at, status, price, area_sqm, d_etage,
                               listed_at_source, source_url
                        from listings where unit_key = ? and deal_type = 'sale'""", (uk,)).fetchall()
    d = lambda s: date.fromisoformat(s[:10]) if s else None
    spans = []
    for i, src, fs, dl, st, p, a, e, ls, lien in rows:
        debut, declare = d(fs), d(ls)
        # Ancienneté = le plus ancien de notre premier passage et de la date de
        # création DÉCLARÉE par le portail — pour les sources dont cette date a
        # passé le test (SOURCES_DATE_FIABLE). `first_seen` retarde de 2 semaines
        # à 3 ans (suivi commencé le 24/06/2026, découverte tardive).
        via_source = bool(src in SOURCES_DATE_FIABLE and declare and declare < debut)
        spans.append({"id": i, "source": src, "debut": declare if via_source else debut,
                      "via_source": via_source, "fin": d(dl) if st != "active" else None,
                      "prix": p, "surface": a, "etage": e,
                      # le lien ne sort que pour une annonce ENCORE active (demande du 2026-10-22)
                      "url": lien if st == "active" else None})
    cible = next(s for s in spans if s["id"] == lid)
    chaine = [cible]
    for s in spans:
        if s is cible or not _meme_lot(cible, s):
            continue
        s_fin = s["fin"] or aujourdhui
        debut = min(x["debut"] for x in chaine)
        fin = max((x["fin"] or aujourdhui) for x in chaine)
        if s["debut"] <= fin + timedelta(days=14) and s_fin >= debut - timedelta(days=14):
            chaine.append(s)
    ids = [s["id"] for s in chaine]
    obs = c.execute(f"select listing_id, price, observed_at from price_history where listing_id in "
                    f"({','.join('?' * len(ids))}) order by observed_at", ids).fetchall()
    evenements = []
    vus = set()
    for s in sorted(chaine, key=lambda s: s["debut"]):
        cle = (s["debut"], s["source"])
        if cle in vus:          # deux agents le même jour sur le même portail : une ligne
            continue
        vus.add(cle)
        evenements.append({"date": s["debut"].isoformat(), "type": "listed",
                           "source": SOURCES_LISIBLES.get(s["source"], s["source"]),
                           "cle": s["source"], "url": s["url"]})
    dernier = {}
    for lid2, p, t in obs:
        if lid2 in dernier and p and dernier[lid2] and p != dernier[lid2]:
            evenements.append({"date": t[:10], "type": "price_cut" if p < dernier[lid2] else "price_rise",
                               "from": dernier[lid2], "to": p,
                               "source": SOURCES_LISIBLES.get(lid2.split(":")[0], lid2),
                               "cle": lid2.split(":")[0], "url": None})
        dernier[lid2] = p
    evenements.sort(key=lambda e: e["date"])
    debut = min(s["debut"] for s in chaine)
    # La date vient-elle du portail plutôt que de notre suivi ? Dit à l'acheteur
    # d'où sort l'ancienneté affichée.
    via = sorted({SOURCES_LISIBLES.get(s["source"], s["source"]) for s in chaine
                  if s["via_source"] and s["debut"] == debut})
    obs_cible = [p for l2, p, _ in obs if l2 == lid and p]
    prix0 = obs_cible[0] if obs_cible else cible["prix"]
    premiers = [p for _, p, _ in obs if p]
    prix_initial = premiers[0] if premiers else prix0
    return {"premier_vu": debut.isoformat(), "jours_en_ligne": (aujourdhui - debut).days,
            "premier_vu_declare_par": via,
            "portails": sorted({SOURCES_LISIBLES.get(s["source"], s["source"]) for s in chaine}),
            "annonces": len(chaine), "prix_initial": prix_initial, "prix_actuel": cible["prix"],
            "variation": (cible["prix"] / prix_initial - 1) if prix_initial and cible["prix"] else None,
            "baisses": sum(1 for e in evenements if e["type"] == "price_cut"),
            "ids": ids, "evenements": evenements}


def _comparables(c, ann: dict, cfg: dict, exclure: set) -> list[dict]:
    """Prix/m² face à l'immeuble, puis mêmes chambres et surface, puis 1 km et
    district. Comparé au niveau de l'ANNONCE (les lots de même type d'un immeuble
    sont dans la même cohorte que l'annonce visée : comparer par cohorte les
    faisait disparaître), mais les copies d'un même lot — mêmes immeuble,
    chambres, surface arrondie, étage et prix — ne comptent qu'une fois."""
    b = cfg["bornes"]
    sel = """select id, condo_name, khet, bedrooms, area_sqm, price, lat, lng, d_etage
             from listings where deal_type='sale' and status='active'
               and price between ? and ? and area_sqm between ? and ? """
    bornes = (b["prix_min"], b["prix_max"], b["surface_min"], b["surface_max"])
    rows = c.execute(sel + "and khet = ?", (*bornes, ann["khet"])).fetchall()
    if ann["lat"] is not None:   # le rayon de 1 km déborde souvent sur le district voisin
        dl = cfg["rayon_km"] / 111.0
        rows += c.execute(sel + "and khet <> ? and lat between ? and ? and lng between ? and ?",
                          (*bornes, ann["khet"], ann["lat"] - dl, ann["lat"] + dl,
                           ann["lng"] - dl, ann["lng"] + dl)).fetchall()
    uniques = {}
    for i, condo, khet, ch, surf, p, la, ln, et in rows:
        if i in exclure:
            continue
        cle = ((condo or "").strip(), ch, round(surf), et, round(p, -4))
        uniques.setdefault(cle, (p / surf, (condo or "").strip(), khet, ch, surf, la, ln))
    coh = list(uniques.values())
    surf, ch = ann["surface"], ann["chambres"]
    noms = set(ann["noms"])
    meme = lambda x: x[3] == ch and abs(x[4] - surf) <= TOL_SURFACE * surf
    proche = lambda x: (ann["lat"] is not None and x[5] is not None
                        and coeur.distance_km(ann["lat"], ann["lng"], x[5], x[6]) <= cfg["rayon_km"])
    mailles = [("building", "The building, all units", lambda x: x[1] in noms),
               ("building_same", "The building, same beds & size", lambda x: x[1] in noms and meme(x)),
               ("radius_same", f"Within {cfg['rayon_km']:g} km, same beds & size", lambda x: proche(x) and meme(x)),
               ("khet_same", f"{ann['khet'].replace(' District', '')}, same beds & size",
                lambda x: x[2] == ann["khet"] and meme(x))]
    out = []
    for cle, nom, f in mailles:
        v = sorted(x[0] for x in coh if f(x))
        # Valeurs aberrantes écartées de l'échantillon (demande du 2026-10-22) :
        # au-delà de 3× ou en deçà de 1/3 de la médiane du niveau. Règle volontairement
        # large — elle ne retire que l'erreur de saisie (un loyer classé en vente, un
        # prix à un zéro de trop), pas l'annonce simplement chère ou bon marché.
        exclus = 0
        if len(v) >= MIN_COMPARABLES:
            m0 = statistics.median(v)
            gardees = [x for x in v if m0 / 3 <= x <= m0 * 3]
            exclus, v = len(v) - len(gardees), gardees
        r = {"cle": cle, "niveau": nom, "n": len(v), "exclus": exclus}
        if len(v) >= MIN_COMPARABLES:
            q = statistics.quantiles(v, n=4)
            med = statistics.median(v)
            r.update(mediane=med, p25=q[0], p75=q[2], min=v[0], max=v[-1],
                     ecart=ann["prix_m2"] / med - 1,
                     rang_pct=round(100 * sum(x < ann["prix_m2"] for x in v) / len(v)),
                     verdict=("below most comparables" if ann["prix_m2"] < q[0] else
                              "above most comparables" if ann["prix_m2"] > q[2] else "in line"),
                     points=[round(x) for x in v])
        else:
            r["verdict"] = "not enough comparables"
        out.append(r)
    return out


def _scores(condo: str, chambres, db: str) -> dict | None:
    # les scores mensuels vivent à côté de la base qu'on lit (même poste, même mois)
    chemin = os.path.join(os.path.dirname(os.path.abspath(db)), "scores-tension", "scores-latest.json")
    if not os.path.exists(chemin):
        return None
    with open(chemin, encoding="utf-8") as f:
        s = json.load(f)
    cle = _norm_condo(condo)
    imm = next((x for x in s["immeubles"] if x.get("cle", _norm_condo(x["immeuble"])) == cle), None)
    entete = {k: s.get(k) for k in ("fin_fenetre", "calcule_le", "frequence_calcul", "config_version")}
    entete["sources_gardees"] = sorted(k for k, v in s["sources"].items() if v["gardee"])
    if not imm:
        return {**entete, "immeuble": None}
    blocs = imm["par_chambres"]
    return {**entete, "immeuble": {k: imm.get(k) for k in ("annee", "charges_thb_m2", "khet")},
            "meme_chambres": blocs.get(str(chambres)), "toutes_chambres": blocs.get("all")}


def _niveau_retenu(chaine: dict | None) -> dict | None:
    """Le niveau le plus FIN qui a un score : c'est celui qui s'affiche en tête."""
    if not chaine:
        return None
    for nom in reversed(list(chaine)):
        # un score dont la fourchette est trop large porte « not enough data » :
        # il ne s'affiche pas en tête (mesuré : liquidité 89, fourchette 10–100)
        if chaine[nom]["score"] is not None and chaine[nom]["libelle"] != "not enough data":
            return {"niveau": nom, **chaine[nom]}
    return None


def _drapeaux(c, ann: dict, comp: list[dict], hist: dict | None = None, chg: dict | None = None,
              lots: tuple[int, int] | None = None) -> list[dict]:
    """Signaux d'alerte que le code SAIT produire, chacun sur une mesure de la base.
    Ils signalent une question à poser, jamais un verdict : `high` = à éclaircir
    avant toute offre. Les seuils sont ceux d'un relevé de bon sens (40 % d'écart,
    180 jours…), non calibrés sur des ventes qu'on ne possède pas."""
    out = []
    add = lambda n, t: out.append({"niveau": n, "texte": t})
    imm = next((x for x in comp if x["cle"] == "building" and x.get("mediane")), None)
    if imm and ann["prix_m2"] < 0.6 * imm["mediane"]:
        add("high", "Price per m² is more than 40% below the building: check for errors, leasehold, or a bait listing.")
    elif imm and ann["prix_m2"] > 1.3 * imm["mediane"]:
        add("medium", "Price per m² is more than 30% above the building's median: ask what justifies the premium "
                      "(floor, view, renovation).")
    if not ann["active"]:
        add("high", "This listing is no longer online: it may have been sold or withdrawn. Check availability.")
    if ann["quota"] == "thai":
        add("high", "Listed under the Thai quota: a foreign buyer cannot hold it freehold in their own name.")
    elif ann["quota"] is None:
        add("medium", "Quota not stated on the listing: ask whether the unit is in the foreign quota.")
    annees = {r[0] for r in c.execute("select distinct d_annee_construction from listings where "
                                      "condo_norm = ? and d_annee_construction between 1970 and 2035",
                                      (ann["cle"],))}
    if len(annees) > 1:
        add("low", f"Sources disagree on the completion year ({', '.join(str(a) for a in sorted(annees))}).")
    if annees and date.today().year - min(annees) >= 30:
        add("medium", f"Building about {date.today().year - min(annees)} years old: ask for the last major works "
                      "and the sinking fund balance.")
    if ann["chambres"] and ann["surface"] / max(ann["chambres"], 1) < 18:
        add("low", "Very small area for the number of bedrooms: check the floor plan.")
    if hist:
        if hist["baisses"] >= 3:
            add("medium", f"{hist['baisses']} price cuts since first seen: the asking price has not found a buyer.")
        if hist["jours_en_ligne"] >= 180:
            add("medium", f"Online for {hist['jours_en_ligne']} days: long for this market, ask why it has not sold.")
        prix = {e["to"] for e in hist["evenements"] if e["type"] != "listed"} | {hist["prix_actuel"]}
        if hist["annonces"] > 1 and len(prix) > 1 and max(prix) / min(prix) > 1.05:
            add("low", "The same unit has been advertised at different prices: confirm which one is current.")
    if lots and lots[1] and lots[0] / lots[1] >= 0.4 and lots[0] >= 5:
        add("low", f"{lots[0]} of the {lots[1]} units we have recorded here are for sale at once: "
                   "the building may be hard to exit, or a developer is still selling.")
    if chg:
        pr, am = chg.get("propre"), chg.get("memes_equipements")
        if pr is None:
            add("low", "Common fee unknown: ask for it, and for the last three years of building accounts.")
        elif am and pr < am["p25"]:
            add("medium", f"Common fee THB {pr:.0f}/m²/month is below buildings with similar amenities "
                          f"(median {am['mediane']:.0f}): maintenance may be underfunded. Ask for the sinking fund.")
        elif am and pr > am["p75"]:
            add("low", f"Common fee THB {pr:.0f}/m²/month is above buildings with similar amenities "
                       f"(median {am['mediane']:.0f}): check what it covers.")
    return out


#: Effectif minimal de ventes comparables pour AFFICHER une médiane. En dessous, le
#: bloc montre les ventes une à une et dit qu'il y en a trop peu : mesuré le
#: 2026-10-22, un immeuble en publie ~2 par an, donc 5 sur 36 mois est déjà rare.
MIN_VENTES_MEDIANE = 5
FENETRE_VENTES_MOIS = 36


def _ventes_portail(c, ann: dict, aujourdhui: date) -> dict | None:
    """Ventes « conclues » déclarées par un portail pour cet immeuble.

    SOURCE FAIBLE, étiquetée comme telle dans la sortie (`fiabilite`) : l'origine
    n'est pas vérifiée (7 ventes sur 53 rapprochées de nos annonces disparues,
    mesure du 2026-10-22), l'échantillon est mince (≈ 2 par an et par immeuble)
    et la table est tenue à l'écart des annonces. Ces chiffres ne sont mêlés à
    AUCUN calcul de marché de ce module ; ils sont montrés à côté. Le portail
    n'est pas nommé (politique `sansSources` du site). Retour arrière : renvoyer
    None ici."""
    try:
        rows = c.execute("select sold_date, sold_price, area_sqm, price_per_sqm, floor, bedrooms, quota "
                         "from ventes_portail where condo_norm = ? and deal_type = 'sale' "
                         "order by sold_date desc", (ann["cle"],)).fetchall()
        resume = c.execute("select n, price_per_sqm, jours_avant_vente, decote_pct, releve_le "
                           "from ventes_portail_projets where condo_norm = ? order by releve_le desc",
                           (ann["cle"],)).fetchone()
    except sqlite3.OperationalError:       # base d'avant la collecte : le bloc n'existe pas
        return None
    if not rows and not resume:
        return None
    depuis = (aujourdhui - timedelta(days=30.44 * FENETRE_VENTES_MOIS)).isoformat()
    surf, ch = ann["surface"], ann["chambres"]
    comparables = [r for r in rows if r[0] >= depuis and r[3] and r[5] == ch and surf
                   and r[2] and abs(r[2] - surf) <= TOL_SURFACE * surf]

    def tranche(f):
        return None if f is None else f"{(f // 10) * 10}-{(f // 10) * 10 + 9}"

    out = {"fiabilite": "low", "etiquette": "Weak source",
           "note": "Sales reported by a listings portal. Origin not verified, small sample, "
                   "kept apart from our own listing data.",
           "n_immeuble": len(rows), "n_comparables": len(comparables),
           "n_24_mois": sum(1 for r in rows if r[0] >= (aujourdhui - timedelta(days=730)).isoformat()),
           "fenetre_mois": FENETRE_VENTES_MOIS, "mediane_m2": None, "ecart": None,
           "ventes": [{"mois": r[0][:7], "surface": r[2], "etage": tranche(r[4]), "prix_m2": r[3]}
                      for r in (comparables or rows)[:6] if r[3]],
           "resume": None}
    if len(comparables) >= MIN_VENTES_MEDIANE:
        med = statistics.median(r[3] for r in comparables)
        out["mediane_m2"] = med
        out["ecart"] = ann["prix_m2"] / med - 1 if ann["prix_m2"] else None
    if resume:
        out["resume"] = {"n": resume[0], "prix_m2": resume[1], "jours_avant_vente": resume[2],
                         "decote_pct": resume[3], "releve_le": resume[4][:10]}
    return out


def construire(url: str, db: str = DB) -> dict:
    cfg = config()
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    lid = trouver(c, url)
    base = {"id": identifiant(url), "url": url.strip(), "genere_le": date.today().isoformat(),
            "demande_le": datetime.now().strftime("%Y-%m-%d %H:%M")}
    if not lid:
        return {**base, "statut": "not_found"}
    r = c.execute("""select id, source, condo_name, khet, bedrooms, bathrooms, area_sqm, price, lat, lng,
                            unit_key, d_quota, d_etage, d_meuble, status, title
                     from listings where id = ?""", (lid,)).fetchone()
    (i, src, condo, khet, ch, sdb, surf, prix, lat, lng, uk, quota, etage, meuble, statut, titre) = r
    ann = {"id": i, "source": SOURCES_LISIBLES.get(src, src), "condo": (condo or "").strip(),
           "khet": khet, "chambres": ch, "sdb": sdb, "surface": surf, "prix": prix,
           "prix_m2": prix / surf if prix and surf else None, "lat": lat, "lng": lng,
           "unit_key": uk, "quota": quota, "etage": etage, "meuble": meuble,
           "active": statut == "active", "titre": titre}
    # coordonnées de l'IMMEUBLE (médiane de ses annonces) : le rayon se centre sur le bâtiment
    ann["noms"] = _noms(c, ann["condo"], khet)
    ann["cle"] = _norm_condo(ann["condo"])
    pts = c.execute("select lat, lng from listings where condo_norm = ? and lat is not null",
                    (ann["cle"],)).fetchall()
    if pts:
        ann["lat"] = statistics.median(p[0] for p in pts)
        ann["lng"] = statistics.median(p[1] for p in pts)
    # max(last_seen) se lit en bout d'index (0,1 ms) ; avec substr() SQLite
    # parcourait toute la colonne (1,6 s, mesuré)
    jour = c.execute("select max(last_seen) from listings").fetchone()[0]
    aujourdhui = date.fromisoformat(jour[:10]) if jour else date.today()
    hist = _histoire(c, i, uk, aujourdhui)
    comp = _comparables(c, ann, cfg, set(hist.pop("ids")))
    sc = _scores(ann["condo"], ch, db)
    # lots distincts en vente (copies multi-portails comptées une fois), pas annonces
    en_vente = len({(r[0], round(r[1] or 0), r[2], round(r[3] or 0, -4)) for r in c.execute(
        # INDEXED BY : sans statistiques (jamais d'ANALYZE sur cette base), SQLite
        # prenait l'index (deal_type, status) et parcourait les ~60 000 ventes
        # actives — 2,7 s mesurées, contre quelques ms par l'immeuble. Pas
        # d'ANALYZE global : il changerait les plans de toutes les requêtes du scraper.
        "select bedrooms, area_sqm, d_etage, price from listings indexed by idx_listings_condo_norm "
        "where condo_norm = ? and deal_type = 'sale' and status = 'active'", (ann["cle"],))})
    imm = (sc or {}).get("immeuble") or {}
    recenses = immeuble.lots_recenses(c, ann["cle"])
    chg = immeuble.charges(c, ann, db)
    tension = liquidite = None
    if sc and sc.get("immeuble"):
        bloc = sc.get("meme_chambres") or sc.get("toutes_chambres") or {}
        tension = {"chaine": bloc.get("tension"), "retenu": _niveau_retenu(bloc.get("tension"))}
        liquidite = {"chaine": bloc.get("liquidite"), "retenu": _niveau_retenu(bloc.get("liquidite"))}
    return {**base, "statut": "ok", "donnees_du": aujourdhui.isoformat(),
            "annonce": {k: v for k, v in ann.items() if k not in ("unit_key", "noms", "cle")},
            "histoire": hist, "prix": comp,
            "ventes_portail": _ventes_portail(c, ann, aujourdhui),
            "immeuble": {"lots_en_vente": en_vente, "lots_recenses": max(recenses, en_vente),
                         "annee": imm.get("annee"), "charges_thb_m2": imm.get("charges_thb_m2"),
                         "adresse": immeuble.adresse(c, ann["cle"], ann["condo"], khet),
                         "charges": chg},
            "sorties_prix": immeuble.sorties_au_meme_prix(c, ann, cfg, aujourdhui),
            "mois_de_stock": immeuble.mois_de_stock_serie(c, ann, cfg, aujourdhui),
            "tension": tension, "liquidite": liquidite,
            "scores_calcul": {k: (sc or {}).get(k) for k in ("fin_fenetre", "calcule_le", "frequence_calcul",
                                                             "config_version", "sources_gardees")},
            "drapeaux": _drapeaux(c, ann, comp, hist, chg, (en_vente, max(recenses, en_vente)))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--db", default=DB)
    ap.add_argument("--out", default=RAPPORTS)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    rep = construire(a.url, a.db)
    os.makedirs(a.out, exist_ok=True)
    chemin = os.path.join(a.out, f"{rep['id']}.json")
    tmp = chemin + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, default=lambda o: None if isinstance(o, float) and math.isnan(o) else o)
    os.replace(tmp, chemin)
    print(json.dumps({"id": rep["id"], "statut": rep["statut"], "fichier": chemin}))


if __name__ == "__main__":
    main()
