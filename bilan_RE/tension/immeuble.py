"""immeuble.py — ce que le bilan dit de l'IMMEUBLE autour d'une annonce.

Adresse, lots recensés, charges comparées (au prix et aux équipements), sorties
d'annonces au même prix. Lecture seule, quelques requêtes SQL.

Ce qui est mesuré et ce qui ne l'est pas (relevé du 2026-10-22, PC2) :
  · charges (`d_cam_fee_thb`) : 1 134 immeubles sur 3 931 (29 %), FazWaz seul. En
    dessous de 10 comparables le graphique n'est pas produit ; il n'est jamais
    complété par une valeur estimée.
  · équipements : 2 693 immeubles actifs sur 3 931 (68 %). Deux d'entre eux —
    « Restaurant » et « Bar » — sont présents sur 99,6 % des annonces FazWaz :
    c'est du gabarit, pas une information. Tout équipement présent dans plus de
    80 % des immeubles est écarté de la comparaison pour la même raison.
  · `condos.nb_lots` : 0 ligne renseignée. « Lots recensés » = lots distincts que
    NOUS avons vus à la vente dans l'immeuble, jamais le nombre de lots réel.
"""
from __future__ import annotations

import json
import os
import statistics
import time
from collections import defaultdict
from datetime import date, timedelta

from . import coeur

#: Regroupe les graphies d'un même équipement (FazWaz et DDproperty écrivent
#: « Gym » / « Fitness », « Lift » / « Elevator »…). Ce qui n'est pas listé garde
#: son nom d'origine, en minuscules.
CANON = {
    "swimming pool": "Swimming pool", "communal pool": "Swimming pool", "pool": "Swimming pool",
    "infinity pool": "Swimming pool", "gym": "Gym", "fitness": "Gym", "fitness center": "Gym",
    "lift": "Lift", "elevator": "Lift", "security": "Security", "24-hour security": "Security",
    "cctv": "Security", "garden": "Garden", "communal garden": "Garden", "sky garden": "Garden",
    "sauna": "Sauna / steam", "steam room": "Sauna / steam", "jacuzzi": "Sauna / steam",
    "library": "Library / co-working", "co-working": "Library / co-working",
    "co-working space": "Library / co-working", "reception": "Reception", "playground": "Playground",
    "clubhouse": "Clubhouse", "shuttle": "Shuttle", "rooftop": "Rooftop", "parking": "Parking",
}
UBIQUITE_MAX = 0.80          # au-delà, l'équipement ne distingue plus rien
JACCARD_MIN = 0.5            # « mêmes équipements, ou proches »
PAIRS_MIN = 10               # sous cet effectif, pas de graphique
TOL_PRIX = 0.15


def _canon(nom: str) -> str | None:
    n = (nom or "").strip().lower()
    if n in ("restaurant", "bar"):          # gabarit FazWaz, 99,6 % des annonces
        return None
    return CANON.get(n, n.title()) if n else None


def adresse(c, cle: str, condo: str, khet: str) -> str:
    """L'adresse la plus complète connue pour l'immeuble : FazWaz ne donne que le
    district (« Watthana »), DDproperty la rue et le quartier. Format d'origine du
    portail, une ligne — pas de code postal, que les sources ne portent pas."""
    r = c.execute("select address_raw from listings indexed by idx_listings_condo_norm "
                  "where condo_norm = ? and address_raw is not null "
                  "order by length(address_raw) desc limit 1", (cle,)).fetchone()
    brut = (r[0] if r else "") or ""
    nom = condo.replace(", Bangkok", "")
    return f"{nom}, {brut}" if brut and nom.lower() not in brut.lower() else (brut or f"{nom}, {khet}")


def lots_recenses(c, cle: str) -> int:
    """Lots distincts vus à la vente dans l'immeuble, tous statuts. Un lot dont le
    prix baisse reste UN lot : la clé ne contient le prix (à 100 k près) que
    lorsque l'étage est inconnu."""
    cles = set()
    for ch, surf, etage, prix in c.execute(
            "select bedrooms, area_sqm, d_etage, price from listings indexed by idx_listings_condo_norm "
            "where condo_norm = ? and deal_type = 'sale'", (cle,)):
        cles.add((ch, round(surf or 0), etage) if etage is not None
                 else (ch, round(surf or 0), None, round(prix or 0, -5)))
    return len(cles)


def _charges_par_immeuble(c) -> dict[str, float]:
    par = defaultdict(list)
    for cle, cam, surf in c.execute("select condo_norm, d_cam_fee_thb, area_sqm from listings "
                                    "where deal_type = 'sale' and d_cam_fee_thb > 0 and area_sqm >= 15"):
        if cle and 5 <= cam / surf <= 300:
            par[cle].append(cam / surf)
    return {k: statistics.median(v) for k, v in par.items()}


def _amenites_par_immeuble(c, db: str) -> dict[str, set[str]]:
    """Équipements par immeuble. 1,5 M de lignes à parcourir : le résultat est mis
    en cache un jour (fichier à côté de la base), sinon chaque bilan paierait
    plusieurs secondes."""
    dossier = os.path.join(os.path.dirname(os.path.abspath(db)), "cache-bilan")
    chemin = os.path.join(dossier, "amenites-immeubles.json")
    if os.path.exists(chemin) and time.time() - os.path.getmtime(chemin) < 86400:
        with open(chemin, encoding="utf-8") as f:
            return {k: set(v) for k, v in json.load(f).items()}
    par = defaultdict(set)
    for cle, nom in c.execute("select l.condo_norm, a.name from listing_amenities a "
                              "join listings l on l.id = a.listing_id "
                              "where l.deal_type = 'sale' and l.condo_norm is not null"):
        n = _canon(nom)
        if n:
            par[cle].add(n)
    freq = defaultdict(int)
    for s in par.values():
        for n in s:
            freq[n] += 1
    ecarte = {n for n, k in freq.items() if k / max(len(par), 1) > UBIQUITE_MAX}
    out = {k: sorted(s - ecarte) for k, s in par.items()}
    os.makedirs(dossier, exist_ok=True)
    with open(chemin + ".tmp", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    os.replace(chemin + ".tmp", chemin)
    return {k: set(v) for k, v in out.items()}


def _bande(v: list[float], propre: float | None) -> dict | None:
    if len(v) < PAIRS_MIN:
        return None
    q = statistics.quantiles(v, n=4)
    return {"n": len(v), "mediane": statistics.median(v), "p25": q[0], "p75": q[2],
            "points": [round(x, 1) for x in sorted(v)], "propre": propre}


def charges(c, ann: dict, db: str) -> dict:
    """Charges de l'immeuble (THB/m²/mois) face à (a) des immeubles au même prix/m²
    à ±15 % et (b) des immeubles aux équipements identiques ou proches."""
    ch = _charges_par_immeuble(c)
    propre = ch.get(ann["cle"])
    prix_imm = defaultdict(list)
    for cle, p in c.execute("select condo_norm, price_per_sqm from listings where deal_type = 'sale' "
                            "and status = 'active' and price_per_sqm > 0"):
        if cle in ch:
            prix_imm[cle].append(p)
    med = {k: statistics.median(v) for k, v in prix_imm.items()}
    ref = ann["prix_m2"]
    meme_prix = [ch[k] for k, m in med.items() if k != ann["cle"] and ref and abs(m / ref - 1) <= TOL_PRIX]
    am = _amenites_par_immeuble(c, db)
    mes = am.get(ann["cle"], set())
    memes_am = []
    if mes:
        memes_am = [ch[k] for k, s in am.items()
                    if k != ann["cle"] and k in ch and s and len(s & mes) / len(s | mes) >= JACCARD_MIN]
    return {"propre": propre, "equipements": sorted(mes),
            "meme_prix": _bande(meme_prix, propre), "memes_equipements": _bande(memes_am, propre),
            "n_immeubles_avec_charges": len(ch)}


def sorties_au_meme_prix(c, ann: dict, cfg: dict, aujourdhui: date, jours: int = 90) -> dict | None:
    """Annonces sorties du marché dans les `jours` derniers jours, à moins d'un
    kilomètre et à ±15 % du prix/m² de celle-ci.

    On ne sait PAS si une sortie est une vente ou un retrait : aucune source ne
    publie la vente (hors les ventes déclarées, traitées à part). Le chiffre se lit
    « parties », pas « vendues ». Les durées partent du premier passage de notre
    robot, donc sous-estiment l'ancienneté réelle."""
    if ann["lat"] is None or not ann["prix_m2"]:
        return None
    b, dl = cfg["bornes"], cfg["rayon_km"] / 111.0
    lo, hi = ann["prix_m2"] * (1 - TOL_PRIX), ann["prix_m2"] * (1 + TOL_PRIX)
    depuis = (aujourdhui - timedelta(days=jours)).isoformat()
    rows = c.execute("select unit_key, first_seen, delisted_at, status, lat, lng from listings "
                     "where deal_type = 'sale' and price_per_sqm between ? and ? "
                     "and price between ? and ? and area_sqm between ? and ? "
                     "and lat between ? and ? and lng between ? and ?",
                     (lo, hi, b["prix_min"], b["prix_max"], b["surface_min"], b["surface_max"],
                      ann["lat"] - dl, ann["lat"] + dl, ann["lng"] - dl, ann["lng"] + dl)).fetchall()
    partis, actifs = {}, set()
    for uk, fs, dl_, st, la, ln in rows:
        if coeur.distance_km(ann["lat"], ann["lng"], la, ln) > cfg["rayon_km"]:
            continue
        if st == "active":
            actifs.add(uk)
        elif dl_ and dl_[:10] >= depuis and fs:
            partis[uk] = (date.fromisoformat(dl_[:10]) - date.fromisoformat(fs[:10])).days
    d = sorted(max(0, x) for x in partis.values())
    return {"jours": jours, "tolerance": TOL_PRIX, "rayon_km": cfg["rayon_km"],
            "n_parties": len(d), "n_actives": len(actifs),
            "mediane_jours": statistics.median(d) if d else None,
            "part_30j": round(sum(x <= 30 for x in d) / len(d), 2) if d else None}


#: Repère OFFICIEL : REIC (Real Estate Information Center, Government Housing Bank),
#: 2e trimestre 2026, publié le 23/09/2026 — absorption de 2,4 % par mois pour les
#: condominiums du Grand Bangkok, soit environ 39 mois pour écouler l'offre. Une
#: seule valeur : aucune série antérieure n'a été retrouvée (vérifié le 2026-10-22,
#: article Nation Thailand). Les autres estimations publiques divergent beaucoup
#: (Knight Frank : 5 à 6 ans, sur un stock d'environ 350 000 logements) : périmètre et
#: définition du stock ne sont pas les mêmes. Aucune donnée CBRE sur ce point n'a été trouvée.
REIC_T2_2026 = {"mois": 39, "absorption_mensuelle": 0.024, "periode": "Q2 2026",
                "perimetre": "Greater Bangkok, condominiums",
                "source": "REIC, publié le 2026-09-23", "url": "https://www.nationthailand.com/business/property/40071360"}
SOURCES_STOCK = ("ddproperty", "fazwaz", "propertyscout")   # délistage crédible (journal-donnees 2026-10-17)
DEBUT_FIABLE = date(2026, 9, 14)


def mois_de_stock_serie(c, ann: dict, cfg: dict, aujourdhui: date, fenetre: int = 28, pas: int = 3) -> dict:
    """Mois de stock = stock actif ÷ (retraits nets par mois), en fenêtres glissantes
    de 28 jours qui se terminent tous les 3 jours, pour Bangkok et pour l'immeuble.

    LIMITES, dites au lecteur : (1) la série ne peut pas remonter avant le
    2026-09-14 (avant, FazWaz sans sitemap et DDproperty sans délistage) : on ne
    dispose donc que de quelques semaines, pas de deux ans ; (2) c'est un stock sur des
    RETRAITS d'annonces, pas sur des ventes notariées ; (3) l'intervalle est un
    intervalle de Poisson à 80 % sur le nombre de retraits : il s'élargit très vite
    pour un seul immeuble (quelques retraits). Un point sous 3 retraits n'est pas
    publié pour l'immeuble."""
    d = lambda s: date.fromisoformat(s[:10]) if s else None
    debut = (aujourdhui - timedelta(days=fenetre + 60)).isoformat()
    b = cfg["bornes"]
    rows = c.execute("select id, condo_norm, unit_key, first_seen, delisted_at from listings "
                     "where deal_type = 'sale' and source in (?,?,?) and price between ? and ? "
                     "and area_sqm between ? and ? and first_seen <= ? "
                     "and (delisted_at is null or delisted_at >= ?)",
                     (*SOURCES_STOCK, b["prix_min"], b["prix_max"], b["surface_min"], b["surface_max"],
                      aujourdhui.isoformat(), debut)).fetchall()
    par_cle = defaultdict(list)
    for i, cn, uk, fs, dl in rows:
        if uk:
            par_cle[uk].append((i, d(fs)))

    def repost(i, uk, t):
        return bool(uk) and any(j != i and t - timedelta(days=3) <= f <= t + timedelta(days=21)
                                for j, f in par_cle[uk])

    items = [(cn, d(fs), d(dl), i, uk) for i, cn, uk, fs, dl in rows]
    points, fin = [], aujourdhui
    while fin - timedelta(days=fenetre) >= DEBUT_FIABLE:
        deb = fin - timedelta(days=fenetre)
        mid = deb + timedelta(days=fenetre // 2)
        glob, loc = [0, 0], [0, 0]
        for cn, fs, dl, i, uk in items:
            actif = fs <= mid and (dl is None or dl > mid)
            retire = dl is not None and deb <= dl <= fin and not repost(i, uk, dl)
            for cible, ok in ((glob, True), (loc, cn == ann["cle"])):
                if ok:
                    cible[0] += actif
                    cible[1] += retire

        def mois(stock, n, minimum):
            if n < minimum or stock == 0:
                return None
            f = lambda k: stock / (max(k, 0.5) * 30 / fenetre)
            return {"mois": round(f(n), 1), "bas": round(f(n + 1.28 * n ** 0.5), 1),
                    "haut": round(f(max(n - 1.28 * n ** 0.5, 0.5)), 1), "retraits": n, "stock": stock}
        points.append({"fin": fin.isoformat(), "bangkok": mois(*glob, 30), "immeuble": mois(*loc, 3)})
        fin -= timedelta(days=pas)
    points.reverse()
    # Un immeuble a trop peu de retraits en 28 jours : on lui donne en plus UNE
    # estimation sur toute la période fiable (depuis le 2026-09-14), tracée comme une
    # ligne et non comme une série.
    jours = (aujourdhui - DEBUT_FIABLE).days
    mid = DEBUT_FIABLE + timedelta(days=jours // 2)
    stock = sum(1 for cn, fs, dl, i, uk in items if cn == ann["cle"] and fs <= mid and (dl is None or dl > mid))
    n = sum(1 for cn, fs, dl, i, uk in items if cn == ann["cle"] and dl is not None
            and DEBUT_FIABLE <= dl <= aujourdhui and not repost(i, uk, dl))
    periode = None
    if n >= 3 and stock:
        f = lambda k: stock / (max(k, 0.5) * 30 / jours)
        periode = {"mois": round(f(n), 1), "bas": round(f(n + 1.28 * n ** 0.5), 1),
                   "haut": round(f(max(n - 1.28 * n ** 0.5, 0.5)), 1), "retraits": n, "stock": stock,
                   "jours": jours}
    return {"fenetre_jours": fenetre, "points": points, "immeuble_periode": periode, "officiel": REIC_T2_2026}
