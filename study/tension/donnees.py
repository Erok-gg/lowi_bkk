"""donnees.py — chargement SQLite (lecture seule), santé des sources, mailles.

Tout ce qui touche à la base ou au calendrier réel est ici ; coeur.py ne voit
que des objets Python. On lit `scraper/output/bangkok.db` (PC2, référence) en
`mode=ro` : ce module n'écrit jamais rien.
"""
from __future__ import annotations

import json
import os
import sqlite3
import statistics
from collections import Counter, defaultdict
from datetime import date, timedelta

from . import coeur, liquidite, prix as prix_mod

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(os.path.dirname(ICI))
DB = os.path.join(RACINE, "scraper", "output", "bangkok.db")


def config(chemin: str | None = None) -> dict:
    with open(chemin or os.path.join(ICI, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def _d(s: str | None) -> date | None:
    return date.fromisoformat(s[:10]) if s else None


def charger(db: str, cfg: dict, t1: date) -> list[coeur.Annonce]:
    """Annonces de VENTE dans les bornes de plausibilité, qui existent à un moment
    entre le plus ancien recul utile et t1 + délai de grâce."""
    b = cfg["bornes"]
    recul = max(cfg["recul_offre_jours"], cfg["recul_prix_jours"]) + cfg["fenetre_jours"]
    t_min = t1 - timedelta(days=recul)
    t_max = t1 + timedelta(days=cfg["grace_repost_jours"])
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = c.execute("""
        select id, source, unit_key, condo_name, khet, bedrooms, area_sqm, lat, lng,
               first_seen, coalesce(delisted_at, case when status <> 'active' then last_seen end),
               price
        from listings
        where deal_type = 'sale' and unit_key is not null and khet is not null and khet <> ''
          and price between ? and ? and area_sqm between ? and ?
          and substr(first_seen, 1, 10) <= ?
          and (delisted_at is null or substr(delisted_at, 1, 10) >= ?)
    """, (b["prix_min"], b["prix_max"], b["surface_min"], b["surface_max"],
          t_max.isoformat(), t_min.isoformat())).fetchall()
    # Année et charges sont des propriétés de l'IMMEUBLE : on les agrège par nom
    # sur toutes les annonces (vente ET location), qui les répètent de fiche en
    # fiche. Année = valeur la plus fréquente ; charges = médiane.
    annees, charges = defaultdict(list), defaultdict(list)
    for nom, an, cam, surf in c.execute(
            "select condo_name, d_annee_construction, d_cam_fee_thb, area_sqm from listings "
            "where condo_name is not null and (d_annee_construction between 1970 and 2035 "
            "or d_cam_fee_thb > 0)"):
        k = (nom or "").strip()
        if an and 1970 <= an <= 2035:
            annees[k].append(int(an))
        # d_cam_fee_thb est un montant mensuel par lot : ramené au m² pour
        # comparer des lots de tailles différentes
        if cam and surf:
            charges[k].append(cam / surf)
    annee = {k: statistics.mode(v) for k, v in annees.items()}
    charge = {k: statistics.median(v) for k, v in charges.items()}
    ids = {r[0] for r in rows}
    prix = defaultdict(list)
    for lid, p, obs in c.execute(
            "select listing_id, price, observed_at from price_history "
            "where substr(observed_at, 1, 10) >= ? order by observed_at", (t_min.isoformat(),)):
        if lid in ids and p:
            prix[lid].append((_d(obs), float(p)))
    out = []
    for (i, src, uk, condo, khet, ch, surf, lat, lng, fs, fin, p) in rows:
        obs = prix.get(i) or []
        # le prix courant vaut observation à la première vue quand l'historique
        # ne remonte pas jusque-là (annonce plus ancienne que la fenêtre de prix)
        if not obs or obs[0][0] > _d(fs):
            obs = [(_d(fs), float(p))] + obs
        out.append(coeur.Annonce(
            id=i, source=src, unit_key=uk, condo=(condo or "").strip(), khet=khet,
            chambres=int(ch) if ch is not None else None, surface=surf,
            lat=lat, lng=lng, debut=_d(fs), fin=_d(fin), prix=obs,
            annee=annee.get((condo or "").strip()), charges=charge.get((condo or "").strip())))
    return out


# ───────────────────────────── santé des sources ──────────────────────────────
def sante(annonces: list[coeur.Annonce], t1: date, cfg: dict) -> dict[str, dict]:
    """Verdict par source pour la fenêtre ]t1 − fenêtre, t1].

    Pourquoi : sans ce filtre, le score bougerait à cause de NOUS. Mesuré :
    DDproperty 0 retrait en août puis 12 982 en septembre (recensement), délistage
    à l'arrêt depuis le 13/10 ; Nestopa 0 retrait pour 2 074 actives. Un garde-fou
    figé sur une liste de sources ne survit pas à la prochaine panne : les règles
    se recalculent à chaque fenêtre."""
    s = cfg["sante_sources"]
    t0 = t1 - timedelta(days=cfg["fenetre_jours"])
    # horizon = dernier jour où UNE source a délisté : au-delà, l'absence de
    # retrait dit seulement que le cycle n'est pas encore passé.
    horizon = max((a.fin for a in annonces if a.fin and a.fin <= t1), default=t1)
    par = defaultdict(list)
    for a in annonces:
        par[a.source].append(a)
    verdicts = {}
    for src, la in par.items():
        v = {"actives_debut": sum(a.active(t0) for a in la),
             "actives_fin": sum(a.active(t1) for a in la)}
        jours = Counter(a.fin for a in la if a.fin and t0 < a.fin <= t1)
        v["retraits"] = sum(jours.values())
        sec, j = 0, min(t1, horizon)
        while j > t0 and not jours.get(j):
            sec += 1
            j -= timedelta(days=1)
        v["jours_sans_retrait_fin"] = sec
        raisons = []
        for m in s["exclusions_manuelles"]:
            if m["source"] == src and _d(m["depuis"]) <= t1:
                raisons.append(f"exclusion manuelle : {m['raison']}")
        if v["actives_debut"] >= s["stock_min"] and v["retraits"] == 0:
            raisons.append("aucun retrait sur la fenêtre")
        elif v["actives_debut"] >= s["stock_min"] and sec >= s["jours_sans_retrait_max"]:
            raisons.append(f"{sec} jours sans retrait en fin de fenêtre")
        if v["actives_debut"] and v["actives_fin"] / v["actives_debut"] - 1 > s["croissance_stock_max"]:
            raisons.append("stock en hausse de plus de "
                           f"{s['croissance_stock_max']:.0%} sur la fenêtre (recensement ?)")
        v["gardee"] = not raisons
        v["raisons"] = raisons
        verdicts[src] = v
    return verdicts


# ─────────────────────────────── calcul complet ──────────────────────────────
def fenetres_reference(t1: date, cfg: dict) -> list[date]:
    """Fins de fenêtre des 12 derniers mois, pas de 28 j, jamais avant
    `fiable_depuis` + une fenêtre. Au 2026-10-17 il n'en existe qu'une : la
    référence s'enrichira d'elle-même avec l'historique."""
    debut = _d(cfg["fiable_depuis"]) + timedelta(days=cfg["fenetre_jours"])
    out, t = [], t1
    while t >= debut and t > t1 - timedelta(days=365):
        out.append(t)
        t -= timedelta(days=cfg["fenetre_jours"])
    return out or [t1]


class Calcul:
    """Charge une fois, puis évalue autant de mailles que voulu pour une date."""

    def __init__(self, t1: date, cfg: dict | None = None, db: str = DB,
                 annonces: list[coeur.Annonce] | None = None):
        self.cfg = cfg or config()
        self.t1 = t1
        self.annonces = annonces if annonces is not None else charger(db, self.cfg, t1)
        self.sante = sante(self.annonces, t1, self.cfg)
        gardees = {s for s, v in self.sante.items() if v["gardee"]}
        self.cohortes = coeur.cohortes([a for a in self.annonces if a.source in gardees])
        self._faits: dict[date, dict[str, coeur.Faits]] = {}
        self._refs: dict = {}

    def faits(self, t: date) -> dict[str, coeur.Faits]:
        if t not in self._faits:
            self._faits[t] = {c.cle: f for c in self.cohortes
                              if (f := coeur.faits(c, t, self.cfg)) is not None}
        return self._faits[t]

    def _fs(self, cs: list[coeur.Cohorte], t: date | None = None) -> list[coeur.Faits]:
        fx = self.faits(t or self.t1)
        return [fx[c.cle] for c in cs if c.cle in fx]

    def _ref_brute(self, chambres, surface, m: coeur.Modele) -> dict:
        cle = (chambres, surface, m.nom)
        if cle not in self._refs:
            khets = {c.khet for c in self.cohortes}
            vals = defaultdict(list)
            for t in fenetres_reference(self.t1, self.cfg):
                for k in khets:
                    fs = self._fs(coeur.filtre(self.cohortes, ("khet", k), chambres, surface), t)
                    sig = m.signaux(fs, self.cfg)
                    if (sig["n"] >= self.cfg["minimum"]["cohortes"]
                            and sig["sorties"] >= self.cfg["minimum"]["sorties"]):
                        for s in m.sens:
                            vals[s].append(sig[s])
            self._refs[cle] = coeur.reference(vals)
        return self._refs[cle]

    def reference(self, chambres, surface, modele: coeur.Modele | None = None) -> dict:
        """Distribution des signaux sur les khets publiables, mêmes filtres de
        chambres et de surface, poolée sur les fenêtres de référence.

        Repli si moins de la moitié des signaux ont une référence (mesuré le
        2026-10-17 : « 2 ch. ± 15 % » ne laisse presque aucun khet au-dessus du
        minimum) : mêmes chambres toutes surfaces, puis tout le stock. Le niveau
        effectivement utilisé est renvoyé sous la clé "_maille"."""
        m = modele or coeur.TENSION
        for ch, sz, nom in ((chambres, surface, "same filters"), (chambres, None, "same beds"),
                            (None, None, "all units")):
            ref = self._ref_brute(ch, sz, m)
            if len(ref) * 2 >= len(m.sens):
                return {**ref, "_maille": nom}
        return {"_maille": "none"}

    def niveaux(self, condo: str, khet: str, lat, lng) -> list[tuple[str, tuple]]:
        """Du plus large au plus fin : chaque niveau est ramené vers le précédent."""
        out = [("Bangkok", ("tout",))]
        for nom, ks in self.cfg["zones"].items():
            if khet in ks:
                out.append((nom, ("zone", ks)))
        out.append((khet, ("khet", khet)))
        if lat is not None and lng is not None:
            out.append((f"within {self.cfg['rayon_km']:g} km", ("rayon", lat, lng, self.cfg["rayon_km"])))
        out.append((condo, ("immeuble", condo)))
        return out

    def evaluer_chaine(self, condo, khet, lat, lng, chambres=None, surface=None,
                       modele: coeur.Modele | None = None) -> list[dict]:
        m = modele or coeur.TENSION
        ref = self.reference(chambres, surface, m)
        parent, out = None, []
        for nom, ou in self.niveaux(condo, khet, lat, lng):
            fs = self._fs(coeur.filtre(self.cohortes, ou, chambres, surface))
            r = coeur.evaluer(fs, parent, ref, self.cfg, m)
            r["niveau"], r["reference"] = nom, ref.get("_maille")
            out.append(r)
            if r["n_cohortes"]:
                parent = r["signaux"]
        return out

    def courbe_age(self, chambres) -> dict:
        fs = self._fs(coeur.filtre(self.cohortes, ("tout",), chambres))
        return liquidite.courbe_age(fs, self.cfg)

    def comparer_prix(self, prix_m2, condo, khet, lat, lng, chambres, surface_m2) -> list[dict]:
        """Immeuble tous lots, immeuble mêmes ch. et surface, puis élargissement."""
        tol = 0.15
        mailles = [("building, all units", ("immeuble", condo), None, None),
                   ("building, same beds & size", ("immeuble", condo), chambres, (surface_m2, tol))]
        if lat is not None:
            mailles.append((f"within {self.cfg['rayon_km']:g} km, same beds & size",
                            ("rayon", lat, lng, self.cfg["rayon_km"]), chambres, (surface_m2, tol)))
        mailles.append((f"{khet}, same beds & size", ("khet", khet), chambres, (surface_m2, tol)))
        out = []
        for nom, ou, ch, sz in mailles:
            r = prix_mod.comparer(prix_m2, self._fs(coeur.filtre(self.cohortes, ou, ch, sz)))
            r["niveau"] = nom
            out.append(r)
        return out

    def bilan(self, condo, khet, lat, lng, chambres, surface_m2, prix_m2=None) -> dict:
        """Tout ce que montre le rapport envoyé : tension et liquidité par niveau
        × (chambres, surface), projection de liquidité, comparaison de prix."""
        tol = 0.15
        combos = {"same beds, same size": (chambres, (surface_m2, tol)),
                  "same beds, any size": (chambres, None),
                  "any beds, same size": (None, (surface_m2, tol)),
                  "any beds, any size": (None, None)}
        tension = {nom: self.evaluer_chaine(condo, khet, lat, lng, ch, sz)
                   for nom, (ch, sz) in combos.items()}
        liq = {nom: self.evaluer_chaine(condo, khet, lat, lng, ch, sz, liquidite.LIQUIDITE)
               for nom, (ch, sz) in combos.items()}
        courbe = self.courbe_age(chambres)
        imm = [c for c in self.cohortes if c.condo == condo]
        annee = next((c.annee for c in imm if c.annee), None)
        age = (self.t1.year - annee) if annee else None
        charges = next((a.charges for c in imm for a in c.annonces if a.charges), None)
        # projection sur la maille la plus fine qui a un score (pas sur une maille vide)
        base = next((r for r in reversed(liq["same beds, any size"]) if r["score"] is not None), None)
        ref_l = self.reference(chambres, None, liquidite.LIQUIDITE)
        return {"fin_fenetre": self.t1.isoformat(),
                "frequence_calcul": self.cfg.get("frequence_calcul"),
                "config_version": self.cfg["config_version"],
                "sources": self.sante,
                "comparaisons": tension,
                "liquidite": {"comparaisons": liq, "age_immeuble": age, "annee": annee,
                              "charges_thb_m2": charges, "courbe_age": courbe,
                              "projection": liquidite.projeter(base["signaux"], age, courbe, ref_l, self.cfg)
                              if base else [],
                              "projection_maille": base["niveau"] if base else None},
                "prix": self.comparer_prix(prix_m2, condo, khet, lat, lng, chambres, surface_m2)
                if prix_m2 else []}
