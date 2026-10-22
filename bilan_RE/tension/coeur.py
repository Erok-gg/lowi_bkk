"""coeur.py — score de tension acheteur/vendeur, calcul PUR (aucune base, aucun réseau).

POURQUOI CE DÉCOUPAGE. Le score doit tenir sans IA et sans relecture humaine :
tout ce qui décide d'un chiffre vit ici, en fonctions pures, testables sur des
données synthétiques (bilan_RE/tests/test_tension_score.py). Le chargement depuis
SQLite et le filtre de santé des sources sont dans donnees.py.

LE CHEMIN D'UN CHIFFRE
  annonces ─► cohortes (unit_key) ─► faits par cohorte sur la fenêtre
          ─► 6 signaux bruts ─► retour vers la moyenne (parent)
          ─► z robuste face à la référence ─► 100·Φ(z) ─► moyenne pondérée
          ─► bootstrap sur les cohortes ─► médiane, p10–p90, libellé

POURQUOI LA COHORTE ET PAS L'ANNONCE. Mesuré le 2026-10-17 : 72 % des retraits
DDproperty sont des republications (la même unité réapparaît sous un autre
identifiant). Une cohorte vidée puis repeuplée ne « sort » pas : la republication
devient invisible par construction, sans heuristique de rapprochement.

POURQUOI UN z SUR UNE RÉFÉRENCE ET PAS UN RANG ENTRE DISTRICTS. Un rang est à
somme nulle : il y a toujours un tiers de districts « acheteurs », même si tout
Bangkok se retourne, et son évolution dans le temps ne veut rien dire. Le z sur
une distribution de référence laisse tout Bangkok monter ou baisser ensemble.
"""
from __future__ import annotations

import bisect
import math
import random
import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable

# Sens de chaque signal : +1 = une valeur haute favorise le VENDEUR.
SENS = {
    "ecoulement": +1,   # part des cohortes qui sortent par mois : ça part vite
    "duree": -1,        # âge médian de sortie (Kaplan-Meier) : long = acheteur
    "offre": +1,        # −ln(stock t / stock t−90) : l'offre fond = vendeur
    "baisses": -1,      # part des cohortes avec une baisse de prix sur 30 j
    "momentum": +1,     # évolution du prix/m² à panier constant
    "vendeurs": -1,     # cohortes actives par immeuble : concurrence directe
}
# « prix » = moyenne de baisses et momentum : deux mesures d'un même comportement
# vendeur, qui ne doivent pas peser double.
FAMILLE = {"ecoulement": "ecoulement", "duree": "duree", "offre": "offre",
           "baisses": "prix", "momentum": "prix", "vendeurs": "vendeurs"}


# ─────────────────────────────── données ──────────────────────────────────────
@dataclass
class Annonce:
    id: str
    source: str
    unit_key: str
    condo: str
    khet: str
    chambres: int | None
    surface: float | None
    lat: float | None
    lng: float | None
    debut: date
    fin: date | None                      # date de retrait, None = encore en ligne
    prix: list[tuple[date, float]] = field(default_factory=list)   # observations datées
    annee: int | None = None              # livraison de l'IMMEUBLE (pas de l'annonce)
    charges: float | None = None          # charges de copropriété THB/m²/mois, si connues
    # Date de CRÉATION estimée par l'identifiant séquentiel de la source
    # (donnees.naissances) ; None = inconnue, on retombe sur `debut` (première
    # vue). Pourquoi : `debut` date notre DÉCOUVERTE, pas la mise en ligne. Mesuré
    # le 2026-10-21 (vente, fenêtre au 18/10) : le stock DDproperty passe de
    # 3 996 à 40 562 entre t−90 j et t1, presque tout du rattrapage de couverture.
    cree: date | None = None
    # Premier jour où NOUS suivions cette source : avant, l'absence d'une
    # annonce ne dit rien (PropertyHub et Hipflat, ajoutées le 2026-10-20).
    suivi_depuis: date | None = None

    @property
    def naissance(self) -> date:
        return min(self.cree, self.debut) if self.cree else self.debut

    def active(self, t: date) -> bool:
        return self.debut <= t and (self.fin is None or self.fin > t)

    def existait(self, t: date) -> bool:
        """En ligne à t, qu'on l'ait déjà vue ou non : sert au stock passé,
        pas au risque de sortie (une sortie n'est observable qu'après la vue)."""
        return self.naissance <= t and (self.fin is None or self.fin > t)

    def suivie(self, t: date) -> bool:
        return self.suivi_depuis is None or self.suivi_depuis <= t

    def prix_a(self, t: date) -> float | None:
        """Dernier prix observé à la date t (ou avant)."""
        avant = [p for d, p in self.prix if d <= t]
        return avant[-1] if avant else None


@dataclass
class Cohorte:
    cle: str
    annonces: list[Annonce]

    def __post_init__(self):
        a = self.annonces
        self.condo = a[0].condo
        self.khet = statistics.mode([x.khet for x in a])
        self.chambres = a[0].chambres
        s = [x.surface for x in a if x.surface]
        self.surface = statistics.median(s) if s else None
        la = [x.lat for x in a if x.lat is not None]
        ln = [x.lng for x in a if x.lng is not None]
        self.lat = statistics.median(la) if la else None
        self.lng = statistics.median(ln) if ln else None
        self.debut = min(x.debut for x in a)
        self.naissance = min(x.naissance for x in a)
        an = [x.annee for x in a if x.annee]
        self.annee = statistics.mode(an) if an else None

    def active(self, t: date) -> bool:
        return any(x.active(t) for x in self.annonces)

    def date_sortie(self, t0: date, t1: date, grace: int) -> date | None:
        """Date où la cohorte s'est VIDÉE dans ]t0, t1], sinon None.

        Active à t0, plus active à t1, et personne ne la repeuple dans les
        `grace` jours qui suivent t1 : sinon c'était une republication."""
        if not self.active(t0) or self.active(t1):
            return None
        if any(t1 < x.debut <= t1 + timedelta(days=grace) for x in self.annonces):
            return None
        fins = [x.fin for x in self.annonces if x.fin is not None and x.fin <= t1]
        return max(fins) if fins else None

    def prix_m2(self, t: date) -> float | None:
        v = [p / x.surface for x in self.annonces
             if x.active(t) and x.surface and (p := x.prix_a(t))]
        return statistics.median(v) if v else None

    def a_baisse(self, t_debut: date, t1: date) -> bool:
        """Une annonce de la cohorte a-t-elle baissé son prix dans ]t_debut, t1] ?"""
        for x in self.annonces:
            obs = [(d, p) for d, p in x.prix if d <= t1]
            for (d0, p0), (d1, p1) in zip(obs, obs[1:]):
                if d1 > t_debut and p1 < p0:
                    return True
        return False


def cohortes(annonces: list[Annonce]) -> list[Cohorte]:
    groupes: dict[str, list[Annonce]] = {}
    for a in annonces:
        groupes.setdefault(a.unit_key, []).append(a)
    return [Cohorte(k, v) for k, v in groupes.items()]


# ─────────────────────────── faits par cohorte ────────────────────────────────
@dataclass
class Faits:
    """Ce qu'une cohorte apporte aux signaux sur UNE fenêtre. Calculé une fois :
    le bootstrap ne fait plus ensuite que ré-agréger ces faits (sinon 200 tirages
    × recherche de prix = minutes au lieu de secondes)."""
    condo: str
    a_risque: bool          # active au début de fenêtre
    sortie: bool
    entree: float           # âge (j) à l'entrée sous observation — troncature à gauche
    age_fin: float          # âge à la sortie ou à la censure
    active_fin: bool
    active_recul: bool      # existait à t1 − recul_offre (périmètre de l'offre)
    baisse: bool
    ratio_prix: float | None    # ln(prix/m² t1 / prix/m² t1−recul), panier constant
    prix_m2: float | None = None   # au dernier jour vu dans la fenêtre (sortie ou t1)
    age_immeuble: int | None = None
    chambres: int | None = None
    offre_fin: bool | None = None  # active à t1, périmètre de l'offre (None = active_fin)


def faits(c: Cohorte, t1: date, cfg: dict) -> Faits | None:
    t0 = t1 - timedelta(days=cfg["fenetre_jours"])
    vue = c.active(t0) or any(a.debut <= t1 and (a.fin is None or a.fin > t0)
                              for a in c.annonces)
    if not vue:
        return None
    ds = c.date_sortie(t0, t1, cfg["grace_repost_jours"])
    # Âges comptés depuis la NAISSANCE ; l'entrée sous observation est la
    # première vue (ou t0) : troncature à gauche exacte pour une annonce
    # découverte tard. Sans `cree`, naissance = debut et rien ne change.
    entree = max(0, (max(t0, c.debut) - c.naissance).days)
    fin = ds if ds else t1
    t_off = t1 - timedelta(days=cfg["recul_offre_jours"])
    # Offre : même périmètre aux deux dates — seules les sources déjà suivies à
    # t_off, et le stock passé compte les annonces qui EXISTAIENT alors.
    off_fin = any(x.active(t1) and x.suivie(t_off) for x in c.annonces)
    off_recul = any(x.existait(t_off) and x.suivie(t_off) for x in c.annonces)
    t_px = t1 - timedelta(days=cfg["recul_prix_jours"])
    p1, p0 = c.prix_m2(t1), c.prix_m2(t_px)
    return Faits(
        condo=c.condo, a_risque=c.active(t0), sortie=ds is not None,
        entree=float(entree), age_fin=float(max((fin - c.naissance).days, entree)),
        active_fin=c.active(t1), active_recul=off_recul, offre_fin=off_fin,
        baisse=c.active(t1) and c.a_baisse(t1 - timedelta(days=cfg["fenetre_baisses_jours"]), t1),
        ratio_prix=math.log(p1 / p0) if p1 and p0 else None,
        prix_m2=c.prix_m2(ds - timedelta(days=1)) if ds else p1,
        age_immeuble=(t1.year - c.annee) if c.annee else None,
        chambres=c.chambres,
    )


# ─────────────────────────────── signaux ──────────────────────────────────────
def kaplan_meier(spells: list[tuple[float, float, bool]]) -> list[tuple[float, float, int]]:
    """Courbe de survie [(âge, S(âge), à risque)] aux âges de sortie observés,
    avec troncature à gauche. Même logique que la médiane ci-dessous."""
    entrees = sorted(e for e, _, _ in spells)
    fins = sorted(f for _, f, _ in spells)
    morts: dict[float, int] = {}
    for _, f, ev in spells:
        if ev:
            morts[f] = morts.get(f, 0) + 1
    s, out = 1.0, []
    for t in sorted(morts):
        risque = bisect.bisect_left(entrees, t) - bisect.bisect_left(fins, t)
        if risque > 0:
            s *= 1 - morts[t] / risque
        out.append((t, s, risque))
    return out


def survie_a(courbe: list[tuple[float, float, int]], age: float, risque_min: int = 10) -> float | None:
    """S(âge) lue sur la courbe ; None si moins de `risque_min` cohortes étaient
    encore observées à cet âge (la queue d'une courbe KM est du bruit)."""
    s = 1.0
    for t, st, r in courbe:
        if t > age:
            break
        if r < risque_min:
            return None
        s = st
    return s


def kaplan_meier_mediane(spells: list[tuple[float, float, bool]]) -> float | None:
    """Âge médian de sortie, avec troncature à gauche (entrée retardée).

    `spells` = (âge d'entrée, âge de fin, sortie observée ?). Une cohorte encore
    en vente est CENSURÉE : elle compte dans le risque jusqu'à sa fin, jamais
    comme sortie. Calculer la médiane sur les seules sorties la raccourcirait
    par construction — c'est l'erreur que ce calcul évite.
    Renvoie None si la survie ne descend jamais sous 0,5."""
    # Au temps t, une cohorte est à risque si elle est entrée avant t et n'est
    # pas encore finie : e < t ≤ f. Compté par bisection sur les bornes triées
    # (O(n log n)) : la boucle naïve coûtait des minutes sur Bangkok × 200 tirages.
    entrees = sorted(e for e, _, _ in spells)
    fins = sorted(f for _, f, _ in spells)
    morts: dict[float, int] = {}
    for _, f, ev in spells:
        if ev:
            morts[f] = morts.get(f, 0) + 1
    s = 1.0
    for t in sorted(morts):
        risque = bisect.bisect_left(entrees, t) - bisect.bisect_left(fins, t)
        if risque > 0:
            s *= 1 - morts[t] / risque
        if s <= 0.5:
            return t
    return None


def signaux(fs: list[Faits], cfg: dict) -> dict:
    """Six signaux bruts + effectifs. Un signal sans assez de matière vaut None."""
    risque = [f for f in fs if f.a_risque]
    n, sorties = len(risque), sum(f.sortie for f in risque)
    out = {"n": n, "sorties": sorties}
    out["ecoulement"] = sorties / n * 30 / cfg["fenetre_jours"] if n else None
    out["duree"] = kaplan_meier_mediane([(f.entree, f.age_fin, f.sortie) for f in fs])
    fin = sum(f.active_fin if f.offre_fin is None else f.offre_fin for f in fs)
    recul = sum(f.active_recul for f in fs)
    out["offre"] = -math.log(fin / recul) if fin and recul else None
    actives = [f for f in fs if f.active_fin]
    out["baisses"] = sum(f.baisse for f in actives) / len(actives) if actives else None
    r = [f.ratio_prix for f in fs if f.ratio_prix is not None]
    out["momentum"] = statistics.median(r) if len(r) >= 5 else None
    immeubles: dict[str, int] = {}
    for f in actives:
        immeubles[f.condo] = immeubles.get(f.condo, 0) + 1
    out["vendeurs"] = statistics.mean(immeubles.values()) if immeubles else None
    return out


# ───────────────────── retour vers la moyenne, normalisation ──────────────────
def retour_moyenne(brut: dict, parent: dict | None, k: float, sens: dict = SENS) -> dict:
    """ŝ = (n·s + k·parent)/(n + k). Sans parent, ou sans valeur chez le parent,
    la valeur propre est gardée. Sans valeur propre, on hérite du parent : une
    maille vide ne doit pas faire disparaître un signal que le district connaît."""
    if parent is None:
        return dict(brut)
    n = brut["n"]
    out = dict(brut)
    for s in sens:
        v, p = brut.get(s), parent.get(s)
        if v is None:
            out[s] = p
        elif p is not None:
            out[s] = (n * v + k * p) / (n + k)
    return out


def reference(valeurs_par_signal: dict[str, list[float]]) -> dict[str, tuple[float, float]]:
    """(médiane, échelle robuste) par signal. Échelle = 1,4826·MAD, repli sur
    l'écart interquartile, sinon None (aucune dispersion : le signal ne départage
    rien et vaudra 50)."""
    ref = {}
    for s, v in valeurs_par_signal.items():
        v = [x for x in v if x is not None]
        if len(v) < 5:
            continue
        med = statistics.median(v)
        mad = statistics.median([abs(x - med) for x in v]) * 1.4826
        if mad == 0:
            q = statistics.quantiles(v, n=4)
            mad = (q[2] - q[0]) / 1.349
        ref[s] = (med, mad if mad > 0 else None)
    return ref


def phi(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def note(valeur: float, ref: tuple[float, float | None], sens: int, borne: float) -> float:
    med, ech = ref
    if ech is None:
        return 50.0
    z = max(-borne, min(borne, sens * (valeur - med) / ech))
    return 100 * phi(z)


@dataclass(frozen=True)
class Modele:
    """Un indicateur = des signaux orientés, groupés en familles pondérées. La
    tension et la liquidité partagent toute la mécanique (référence, retour vers
    la moyenne, bootstrap, libellés) : seule cette fiche les distingue."""
    nom: str
    sens: dict
    famille: dict
    poids: Callable[[dict], dict]
    signaux: Callable[[list, dict], dict]
    etiquettes: tuple[str, str, str]      # bas, milieu, haut
    penche: tuple[str, str]               # intervalle chevauchant : bas, haut


def score(sig: dict, ref: dict, cfg: dict, modele: "Modele | None" = None) -> tuple[float | None, dict]:
    """Moyenne pondérée des notes disponibles ; les poids des signaux absents sont
    redistribués (documenté dans le détail renvoyé, jamais silencieux)."""
    m = modele or TENSION
    notes = {s: note(sig[s], ref[s], m.sens[s], cfg["z_borne"])
             for s in m.sens if sig.get(s) is not None and s in ref}
    fam: dict[str, list[float]] = {}
    for s, v in notes.items():
        fam.setdefault(m.famille[s], []).append(v)
    fam = {f: statistics.mean(v) for f, v in fam.items()}
    poids = {f: w for f, w in m.poids(cfg).items() if not f.startswith("_") and f in fam}
    tot = sum(poids.values())
    if not tot:
        return None, {"notes": notes, "familles": fam, "poids": {}}
    sc = sum(fam[f] * w for f, w in poids.items()) / tot
    return sc, {"notes": notes, "familles": fam, "poids": {f: w / tot for f, w in poids.items()}}


# ─────────────────────────── bootstrap et libellé ─────────────────────────────
def bootstrap(fs: list[Faits], parent: dict | None, ref: dict, cfg: dict,
              modele: "Modele | None" = None) -> list[float]:
    """Rééchantillonne les COHORTES (pas les annonces), graine fixe : deux
    exécutions sur les mêmes données donnent le même intervalle."""
    m = modele or TENSION
    rng = random.Random(cfg["bootstrap"]["graine"])
    out = []
    for _ in range(cfg["bootstrap"]["tirages"]):
        tirage = [fs[rng.randrange(len(fs))] for _ in fs]
        sig = retour_moyenne(m.signaux(tirage, cfg), parent, cfg["retour_moyenne_k"], m.sens)
        s, _ = score(sig, ref, cfg, m)
        if s is not None:
            out.append(s)
    return out


def quantile(v: list[float], p: float) -> float:
    v = sorted(v)
    k = (len(v) - 1) * p
    i = int(k)
    return v[i] + (v[min(i + 1, len(v) - 1)] - v[i]) * (k - i)


def libelle(p10: float, p50: float, p90: float, cfg: dict, modele: "Modele | None" = None) -> str:
    m = modele or TENSION
    a, v = cfg["seuils_libelle"]["acheteur"], cfg["seuils_libelle"]["vendeur"]
    if p90 - p10 > cfg["intervalle_max_points"]:
        return "not enough data"
    bas, mil, haut = m.etiquettes
    def bande(x):
        return bas if x < a else haut if x > v else mil
    b = bande(p50)
    if bande(p10) == bande(p90):
        return b
    # L'intervalle chevauche un seuil : on penche, on n'affirme pas. Une médiane
    # au milieu dont l'intervalle déborde reste au milieu : c'est le libellé qui
    # promet le moins.
    return {bas: m.penche[0], haut: m.penche[1]}.get(b, b)


def evaluer(fs: list[Faits], parent: dict | None, ref: dict, cfg: dict,
            modele: "Modele | None" = None, minimum: dict | None = None) -> dict:
    """Le résultat complet d'une maille : ce que le bilan affiche, effectifs compris.

    `minimum` = {"cohortes", "sorties"} propre au NIVEAU (config v4, 2026-10-22) ;
    absent, c'est le minimum global de la config."""
    m = modele or TENSION
    brut = m.signaux(fs, cfg)
    sig = retour_moyenne(brut, parent, cfg["retour_moyenne_k"], m.sens)
    res = {"n_cohortes": brut["n"], "n_sorties": brut["sorties"], "brut": brut, "signaux": sig}
    mini = minimum or cfg["minimum"]
    if brut["n"] < mini["cohortes"] or brut["sorties"] < mini["sorties"]:
        res.update(score=None, libelle="not enough data", p10=None, p90=None, detail=None)
        return res
    sc, detail = score(sig, ref, cfg, m)
    tirages = bootstrap(fs, parent, ref, cfg, m) if sc is not None else []
    if not tirages:
        # Pas de référence exploitable (moins de 5 districts publiables) : se
        # situer face à rien n'a pas de sens, on ne note pas.
        res.update(score=None, libelle="no reference yet", p10=None, p90=None, detail=detail)
        return res
    p10, p50, p90 = (quantile(tirages, q) for q in (0.1, 0.5, 0.9))
    res.update(score=round(p50), point=sc, p10=round(p10), p90=round(p90),
               libelle=libelle(p10, p50, p90, cfg, m), detail=detail)
    return res


TENSION = Modele("tension", SENS, FAMILLE, lambda cfg: cfg["poids"], signaux,
                 ("buyer's market", "balanced", "seller's market"),
                 ("leaning buyer's", "leaning seller's"))


# ─────────────────────────────── mailles ──────────────────────────────────────
def distance_km(a_lat, a_lng, b_lat, b_lng) -> float:
    r = 6371.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lng - a_lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def filtre(cs: list[Cohorte], ou: tuple, chambres: int | None = None,
           surface: tuple[float, float] | None = None) -> list[Cohorte]:
    """ou ∈ ('tout',) | ('zone', [khets]) | ('khet', k) | ('rayon', lat, lng, km)
    | ('immeuble', condo). surface = (m² visés, tolérance relative, ex. 0,15)."""
    def garde(c: Cohorte) -> bool:
        if chambres is not None and c.chambres != chambres:
            return False
        if surface is not None:
            cible, tol = surface
            if c.surface is None or abs(c.surface - cible) > tol * cible:
                return False
        t = ou[0]
        if t == "tout":
            return True
        if t == "zone":
            return c.khet in ou[1]
        if t == "khet":
            return c.khet == ou[1]
        if t == "immeuble":
            return c.condo == ou[1]
        if t == "rayon":
            return c.lat is not None and distance_km(ou[1], ou[2], c.lat, c.lng) <= ou[3]
        raise ValueError(t)
    return [c for c in cs if garde(c)]
