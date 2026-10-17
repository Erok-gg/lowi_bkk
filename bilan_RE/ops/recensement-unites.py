"""recensement-unites.py — liste de travail pour recenser le NOMBRE D'UNITÉS par immeuble.

POURQUOI. Le bilan acheteur veut afficher « part des unités de l'immeuble
actuellement en vente » : c'est le signal d'un immeuble que ses propriétaires
quittent. Le numérateur, on l'a (annonces actives). Le dénominateur, non :
`condos.nb_lots` est vide sur les 4 514 lignes (mesuré le 2026-10-17), et la
table `condos` n'est plus rafraîchie depuis le 2026-07-28 — elle ignore donc
une partie des immeubles qui ont aujourd'hui une annonce active.

On repart donc des ANNONCES ACTIVES, pas de `condos`.

CE QUI EST PRÉ-REMPLI. La prose DDproperty décrit le PROJET et donne le
nombre de lots dans 74 % des fiches (mesuré sur 4 035 fiches, cf.
agents/tests/test_prose_ddproperty.py — la regex n'y fait aucune erreur sur 100
fiches étiquetées à la main). C'est une amorce à 1 seule source : elle se
vérifie avant de servir, elle ne se publie pas telle quelle.

CE QUI N'EST JAMAIS ÉCRASÉ. Les colonnes de relevé manuel (`nb_lots_retenu`,
`source_retenue`, `url_preuve`, `date_releve`, `statut`, `note`) sont
relues dans le fichier existant et recopiées à l'identique : relancer le
script ajoute les nouveaux immeubles et met à jour les compteurs, sans perdre
une ligne de recensement déjà faite. Un immeuble qui n'a plus d'annonce active
reste dans le fichier (statut conservé, `n_actives` = 0).

Rien n'est écrit dans la base : lecture seule (`mode=ro`).

Usage :
    scraper/.venv/Scripts/python.exe bilan_RE/ops/recensement-unites.py
    scraper/.venv/Scripts/python.exe bilan_RE/ops/recensement-unites.py --db <chemin> --out <csv>
"""
from __future__ import annotations

import argparse
import collections
import csv
import os
import re
import sqlite3
import statistics
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scraper"))

from agents.tests.test_prose_ddproperty import AMBIGU, regex_extrait  # noqa: E402
from pipeline.normalize import _norm_condo  # noqa: E402

DB = os.path.join(ROOT, "scraper", "output", "bangkok.db")
OUT = os.path.join(ROOT, "bilan_RE", "referentiel", "recensement-unites.csv")

AUTO = ["cle", "nom", "khet", "lat", "lng", "n_actives", "n_vente", "n_location",
        "sources", "url_ddproperty", "url_fazwaz", "url_autre",
        "nb_lots_prose_dd", "nb_etages_prose_dd", "promoteur_prose_dd"]
MANUEL = ["nb_lots_retenu", "source_retenue", "url_preuve", "date_releve",
          "statut", "note"]


def _texte(blob) -> str | None:
    # `description` est en zlib depuis la bascule SQLite (2026-08-25) ; les
    # lignes plus anciennes peuvent être en clair.
    if blob is None or isinstance(blob, str):
        return blob
    try:
        return zlib.decompress(blob).decode("utf-8")
    except (zlib.error, UnicodeDecodeError):
        return None


def collecter(db_path: str) -> dict:
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    imm: dict[str, dict] = collections.defaultdict(lambda: {
        "libelles": collections.Counter(), "khets": collections.Counter(),
        "lat": [], "lng": [], "n_actives": 0, "n_vente": 0, "n_location": 0,
        "sources": set(), "urls": {}})

    for r in db.execute("""select condo_name, khet, lat, lng, deal_type, source, source_url
                           from listings
                           where status = 'active' and condo_name is not null
                             and trim(condo_name) <> ''"""):
        cle = _norm_condo(r["condo_name"])
        if not cle:
            continue
        m = imm[cle]
        m["libelles"][r["condo_name"].strip()] += 1
        if r["khet"]:
            m["khets"][r["khet"]] += 1
        if r["lat"] is not None and r["lng"] is not None:
            m["lat"].append(r["lat"]); m["lng"].append(r["lng"])
        m["n_actives"] += 1
        m["n_vente" if r["deal_type"] == "sale" else "n_location"] += 1
        m["sources"].add(r["source"])
        # une URL par source suffit au relevé : c'est un point d'entrée vers
        # la fiche projet du portail, pas une liste d'annonces.
        m["urls"].setdefault(r["source"], r["source_url"])

    # Prose DDproperty, toutes annonces confondues (actives ou non) : le texte
    # décrit le projet, une annonce délistée le décrit aussi bien. On
    # déduplique les textes avant d'extraire (37 annonces d'un même immeuble
    # partagent souvent UN texte — mesuré sur Belle Grand Rama 9).
    textes = collections.defaultdict(set)
    for r in db.execute("""select condo_name, description from listings
                           where source = 'ddproperty' and description is not null
                             and condo_name is not null"""):
        cle = _norm_condo(r["condo_name"])
        if cle in imm:
            t = _texte(r["description"])
            if t:
                textes[cle].add(re.sub(r"\s+", " ", t))

    for cle, ts in textes.items():
        acc = collections.defaultdict(set)
        for t in ts:
            for k, v in regex_extrait(t).items():
                if v not in (None, AMBIGU):
                    acc[k].add(v)
        # deux textes du même immeuble qui se contredisent → abstention
        for k, v in acc.items():
            imm[cle]["prose_" + k] = next(iter(v)) if len(v) == 1 else "conflit"
    return imm


def lignes(imm: dict) -> dict[str, dict]:
    out = {}
    for cle, m in imm.items():
        urls = m["urls"]
        autre = next((u for s, u in urls.items() if s not in ("ddproperty", "fazwaz")), "")
        out[cle] = {
            "cle": cle,
            "nom": m["libelles"].most_common(1)[0][0],
            "khet": m["khets"].most_common(1)[0][0] if m["khets"] else "",
            "lat": round(statistics.median(m["lat"]), 6) if m["lat"] else "",
            "lng": round(statistics.median(m["lng"]), 6) if m["lng"] else "",
            "n_actives": m["n_actives"], "n_vente": m["n_vente"],
            "n_location": m["n_location"],
            "sources": "|".join(sorted(m["sources"])),
            "url_ddproperty": urls.get("ddproperty", ""),
            "url_fazwaz": urls.get("fazwaz", ""),
            "url_autre": autre or "",
            "nb_lots_prose_dd": m.get("prose_nb_lots", ""),
            "nb_etages_prose_dd": m.get("prose_nb_etages", ""),
            "promoteur_prose_dd": m.get("prose_promoteur", ""),
        }
    return out


def fusionner(neuves: dict, chemin: str) -> list[dict]:
    """Recopie le relevé manuel déjà fait ; ne perd aucune ligne existante."""
    anciennes = {}
    if os.path.exists(chemin):
        with open(chemin, encoding="utf-8-sig", newline="") as f:
            anciennes = {r["cle"]: r for r in csv.DictReader(f)}
    res = []
    for cle in set(neuves) | set(anciennes):
        ligne = dict.fromkeys(AUTO + MANUEL, "")
        if cle in anciennes:
            ligne.update(anciennes[cle])
        if cle in neuves:
            ligne.update(neuves[cle])
        else:
            for k in ("n_actives", "n_vente", "n_location"):
                ligne[k] = 0
        ligne["statut"] = ligne["statut"] or "a_faire"
        res.append(ligne)
    # priorité de recensement : là où un acheteur a le plus de chances de tomber
    res.sort(key=lambda r: (-int(r["n_actives"] or 0), r["cle"]))
    perdues = set(anciennes) - {r["cle"] for r in res}
    assert not perdues, f"lignes de recensement perdues : {sorted(perdues)[:5]}"
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    res = fusionner(lignes(collecter(a.db)), a.out)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    tmp = a.out + ".tmp"
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=AUTO + MANUEL)
        w.writeheader()
        w.writerows(res)
    os.replace(tmp, a.out)   # jamais de fichier à moitié écrit

    actifs = [r for r in res if int(r["n_actives"] or 0) > 0]
    num = lambda r: str(r["nb_lots_prose_dd"]).isdigit()
    cum = sum(int(r["n_actives"]) for r in actifs)
    top = actifs[:500]
    print(f"immeubles dans le fichier       : {len(res)}")
    print(f"  avec annonce active           : {len(actifs)} ({cum} annonces)")
    print(f"  nb_lots amorcé (prose DD)     : {sum(map(num, actifs))}"
          f"  | conflits : {sum(r['nb_lots_prose_dd'] == 'conflit' for r in actifs)}")
    print(f"  top 500 : {sum(int(r['n_actives']) for r in top) / cum:.0%} des annonces actives,"
          f" amorcés {sum(map(num, top))}/500")
    print(f"  déjà relevés à la main        : {sum(bool(r['nb_lots_retenu']) for r in res)}")
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
