"""referentiel-condos.py — construit un référentiel d'IMMEUBLES, en ISOLATION.

POURQUOI. `condos.year_built` est à **0** côté serveur depuis le début : c'était
le chantier n°1 du projet. Or l'information existe déjà — `d_annee_construction`
est extrait du descriptif sur 79 % des annonces depuis le 2026-08-02. Il ne
manquait que de la remonter au niveau de l'IMMEUBLE, qui est sa vraie maille :
une année de livraison est une propriété du bâtiment, pas de l'annonce.

CE QUI EST ÉCRIT, ET OÙ. Rien n'est écrit dans `listings`, ni en local ni en
ligne. La sortie est un fichier SQLite AUTONOME (`condos-candidat.db`) plus un
rapport lisible. C'est un candidat à relire, pas une mise à jour.

LES DEUX SOURCES, ET LEUR ORDRE.
  1. `d_annee_construction`, agrégé par immeuble — 2 310 immeubles sur 3 551.
  2. La prose DDproperty pour les étages, les lots et le promoteur. Elle décrit
     le PROJET et non le lot, ce qui la rend inutile pour une annonce mais
     pertinente ici. Mesurée sans erreur sur 100 fiches étiquetées à la main
     (cf. agents/tests/test_prose_ddproperty.py) — et c'est la RÈGLE qui est
     retenue, pas le modèle local : là où elle se tait, il invente dans 76 à
     94 % des cas.

ARBITRAGE — ON COMPTE LES TÉMOINS, PAS LES ANNONCES.

C'est la correction du 2026-08-03, et elle vient d'une mesure : au sein d'UNE
MÊME source, les annonces d'un immeuble s'accordent sur l'année dans **99 à
100 %** des cas (FazWaz 908/909). Autrement dit chaque portail lit une FICHE
PROJET unique, et ses N annonces ne sont pas N confirmations — c'est **une seule
voix répétée**. Compter les annonces gonflait donc la confiance d'un facteur
égal au nombre d'annonces.

Entre sources différentes, en revanche, l'accord tombe à **57 %**. C'est là que
l'information se trouve : FazWaz donne 2018 pour Ashton Silom, PropertyScout
2016.

Le témoin est donc LA SOURCE. Échelle de confiance :

    valide         >= 3 sources concordantes
    corrobore         2 sources concordantes
    source_unique     1 seule source — invérifiable, pas faux pour autant
    conflit           sources divergentes sans majorite de 3 -> ABSTENTION

REGROUPEMENT PAR NOM NORMALISÉ, et ce n'est pas un détail : sur le nom brut,
« Modiz Vault Kaset Sripatum », « Modiz Vault Kaset-Sripatum, Bangkok » et la
variante à espace initial comptaient pour TROIS immeubles. Normaliser fait passer
les immeubles vus par >= 3 sources de **47 à 457** — le faible recoupement était
un artefact de rapprochement, pas une réalité.

⚠ On utilise `normalize._norm_condo` (Python), celui qui produit déjà les
`unit_key`. Il DIVERGE de `lib/condo-name.ts` (TS) — ne pas comparer un
regroupement de ce fichier à un regroupement calculé côté application.

Usage :
    python ops/referentiel-condos.py                 # base de test la + récente
    python ops/referentiel-condos.py --db <chemin>
"""
from __future__ import annotations

import argparse
import collections
import glob
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agents.tests.test_prose_ddproperty import AMBIGU, regex_extrait  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "scraper"))
from pipeline.normalize import _norm_condo  # noqa: E402

#: Nombre de sources INDÉPENDANTES concordantes pour qu'une valeur soit validée.
SOURCES_POUR_VALIDER = 3


def _arbitrer(par_valeur: dict):
    """(valeur retenue, niveau de confiance) à partir de {valeur: {sources}}.

    Le second membre part dans `condos.year_source` : il dit COMMENT la valeur a
    été obtenue, ce qui permet de rejuger un immeuble sans tout recalculer — et
    de ne jamais présenter une voix unique comme une certitude.
    """
    if not par_valeur:
        return None, None
    toutes = set().union(*par_valeur.values())
    tete, srcs = max(par_valeur.items(), key=lambda x: len(x[1]))

    if len(par_valeur) == 1:                       # aucune divergence
        n = len(toutes)
        if n >= SOURCES_POUR_VALIDER:
            return tete, f"valide {n} sources"
        if n == 2:
            return tete, "corrobore 2 sources"
        return tete, "source_unique"

    # divergence : seule une majorité d'au moins 3 sources tranche
    if len(srcs) >= SOURCES_POUR_VALIDER:
        return tete, f"valide {len(srcs)}/{len(toutes)} sources"
    return None, f"conflit {len(par_valeur)} valeurs / {len(toutes)} sources"


def construire(db_path: str) -> tuple[dict, dict]:
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    # ── 1. année de livraison : {immeuble: {année: {sources}}} ─────────────────
    votes = collections.defaultdict(lambda: collections.defaultdict(set))
    for r in db.execute("""select condo_name c, source s, d_annee_construction a
                           from listings
                           where condo_name is not null and d_annee_construction is not null
                           group by 1, 2, 3"""):
        votes[_norm_condo(r["c"])][r["a"]].add(r["s"])

    # ── 2. l'immeuble est-il livré ? même arbitrage ────────────────────────────
    votes_livre = collections.defaultdict(lambda: collections.defaultdict(set))
    for r in db.execute("""select condo_name c, source s, d_livre v from listings
                           where condo_name is not null and d_livre is not null
                           group by 1, 2, 3"""):
        votes_livre[_norm_condo(r["c"])][r["v"]].add(r["s"])

    # ── 3. étages / lots / promoteur, depuis la prose DDproperty ───────────────
    # Un texte de projet est répété à l'identique sur toutes les annonces de
    # l'immeuble (37 annonces de Belle Grand Rama 9 partagent UN texte) : on
    # déduplique avant d'extraire, sinon on paie 4,3 fois le même travail.
    textes = collections.defaultdict(set)
    for r in db.execute("""select condo_name c, description d from listings
                           where source='ddproperty' and description is not null
                             and condo_name is not null"""):
        textes[_norm_condo(r["c"])].add(r["d"])

    prose = {}
    for cn, ts in textes.items():
        acc = collections.defaultdict(set)
        for t in ts:
            for k, v in regex_extrait(re.sub(r"\s+", " ", t)).items():
                if v not in (None, AMBIGU):
                    acc[k].add(v)
        # deux textes du même immeuble qui se contredisent : on n'ose rien
        prose[cn] = {k: next(iter(v)) for k, v in acc.items() if len(v) == 1}

    # ── 4. contexte, agrégé sur le nom NORMALISÉ lui aussi ─────────────────────
    # `libelle` garde l'orthographe la plus fréquente : le nom normalisé est une
    # clé de rapprochement, pas quelque chose qu'on montre à un humain.
    meta = collections.defaultdict(lambda: {"n_annonces": 0, "n_actives": 0,
                                            "khet": None, "lat": [], "lng": [],
                                            "libelles": collections.Counter(),
                                            "sources": set()})
    for r in db.execute("""select condo_name c, source s, status st, khet, lat, lng
                           from listings where condo_name is not null"""):
        m = meta[_norm_condo(r["c"])]
        m["n_annonces"] += 1
        m["n_actives"] += r["st"] == "active"
        m["khet"] = m["khet"] or r["khet"]
        m["libelles"][r["c"].strip()] += 1
        m["sources"].add(r["s"])
        if r["lat"]:
            m["lat"].append(r["lat"])
            m["lng"].append(r["lng"])

    moy = lambda v: sum(v) / len(v) if v else None
    out = {}
    for cn in sorted(meta):
        m = meta[cn]
        an, conf = _arbitrer(votes.get(cn, {}))
        liv, conf_liv = _arbitrer(votes_livre.get(cn, {}))
        p = prose.get(cn, {})
        out[cn] = {
            "name": m["libelles"].most_common(1)[0][0], "name_normalized": cn,
            "khet": m["khet"], "lat": moy(m["lat"]), "lng": moy(m["lng"]),
            "n_annonces": m["n_annonces"], "n_actives": m["n_actives"],
            "n_sources": len(m["sources"]),
            "year_built": an, "year_source": conf,
            "livre": liv, "livre_source": conf_liv,
            "nb_etages": p.get("nb_etages"), "nb_lots": p.get("nb_lots"),
            "promoteur": p.get("promoteur"),
        }
    db.close()
    return out, {"votes": votes, "prose": prose}


CHAMPS = ("name", "name_normalized", "khet", "lat", "lng",
          "n_annonces", "n_actives", "n_sources",
          "year_built", "year_source", "livre", "livre_source",
          "nb_etages", "nb_lots", "promoteur")


def ecrire(out: dict, chemin: str) -> None:
    """Fichier SQLite AUTONOME. On ne touche à aucune base existante."""
    if os.path.exists(chemin):
        os.remove(chemin)
    db = sqlite3.connect(chemin)
    db.execute("""create table condos_candidat (
        name text, name_normalized text primary key, khet text, lat real, lng real,
        n_annonces integer, n_actives integer, n_sources integer,
        year_built integer, year_source text,
        livre integer, livre_source text,
        nb_etages integer, nb_lots integer, promoteur text,
        calcule_le text)""")
    now = datetime.now(timezone.utc).isoformat()
    db.executemany(
        f"insert into condos_candidat ({','.join(CHAMPS)},calcule_le) "
        f"values ({','.join('?' * len(CHAMPS))},?)",
        [tuple(v[c] for c in CHAMPS) + (now,) for v in out.values()])
    db.commit()
    db.close()


def rapport(out: dict) -> str:
    n = len(out)
    def part(f):
        k = sum(1 for v in out.values() if v[f] is not None)
        return k, 100 * k / max(1, n)

    L = [f"{n} immeubles\n", f"  {'champ':14s}{'rempli':>9s}{'couverture':>13s}", "  " + "-" * 36]
    for f, lib in (("year_built", "annee"), ("livre", "livre"),
                   ("nb_etages", "etages"), ("nb_lots", "lots"), ("promoteur", "promoteur")):
        k, p = part(f)
        L.append(f"  {lib:14s}{k:>9d}{p:>12.0f} %")

    # INDICATEUR DE CONFIANCE — la valeur et sa solidité se lisent séparément.
    # Une année vue par une seule source n'est pas fausse ; elle est
    # INVÉRIFIABLE, et le référentiel doit le dire plutôt que le taire.
    niv = collections.Counter(
        (v["year_source"] or "").split()[0] for v in out.values() if v["year_source"])
    LIB = {"valide": "validé — 3 sources ou +",
           "corrobore": "corroboré — 2 sources",
           "source_unique": "source unique — invérifiable",
           "conflit": "en conflit — ABSTENTION"}
    L.append("\n  Indicateur de confiance sur l'annee :")
    for k in ("valide", "corrobore", "source_unique", "conflit"):
        if niv.get(k):
            L.append(f"    {LIB[k]:32s} {niv[k]:>5d}")

    # Ce que ça change vraiment : la couverture sur le stock ACTIF, pondérée.
    act = sum(v["n_actives"] or 0 for v in out.values())
    couv = sum(v["n_actives"] or 0 for v in out.values() if v["year_built"])
    L.append(f"\n  Annonces ACTIVES dont l'immeuble a desormais une annee : "
             f"{couv}/{act} ({100*couv/max(1,act):.0f} %)")

    dec = collections.Counter()
    for v in out.values():
        if v["year_built"]:
            dec[min(2030, max(1980, v["year_built"])) // 5 * 5] += 1
    L.append("\n  Repartition par periode de livraison :")
    for d in sorted(dec):
        L.append(f"    {d}-{d+4}  {dec[d]:>4d}  {'#' * (dec[d] // 15)}")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    a = ap.parse_args()

    chemin = a.db or (sorted(glob.glob(os.path.join(ROOT, "tests-scrap", "*", "bangkok.db")),
                             key=os.path.getmtime, reverse=True) or [None])[0]
    if not chemin or not os.path.exists(chemin):
        print("Base introuvable — passer --db")
        return 2
    print(f"source  : {chemin}")

    out, _ = construire(chemin)
    sortie = os.path.join(os.path.dirname(chemin), "condos-candidat.db")
    ecrire(out, sortie)
    print(f"sortie  : {sortie}   (fichier AUTONOME — aucune base existante modifiee)\n")
    print(rapport(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
