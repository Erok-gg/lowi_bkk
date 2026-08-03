"""corriger-khet.py — ramène les quartiers aux 50 noms du découpage officiel.

LE DÉFAUT. Quand le rattachement par point-dans-polygone échouait, le libellé
brut de la source passait TEL QUEL en base. Les sources écrivent « Bang Na », le
découpage dit « Bang Na District » : deux valeurs pour un même quartier.

Constaté le 2026-08-03 sur une capture du tableau des rendements — « Bang Na »
y figurait DEUX FOIS, à 6,1 % sur 3 immeubles et à 5,6 % sur 45. L'affichage
retire le suffixe, donc les deux lignes sont identiques à l'œil. Un quartier
fantôme dans le palmarès, qu'un lecteur ne peut pas interpréter.

Variantes relevées : sept par le suffixe (Khlong Toei, Pathum Wan, Huai Khwang,
Sathon, Bang Rak, Chatuchak, Bang Na), plus « Watthana » pour Vadhana et
« Bearing » — qui est un nom de station de métro, pas un quartier.

CE QUI TRANCHE : LES COORDONNÉES, PAS LE TEXTE.
On ne devine aucune graphie. Pour chaque annonce au quartier non canonique, on
RECALCULE le point-dans-polygone. Le renommage n'a lieu que si le point tombe
effectivement dans un quartier. C'est une preuve ; une correspondance de chaînes
n'en est pas une, et c'est elle qui a créé le problème.

Trois issues, et chacune est dite :
  · corrigé    — le point désigne un quartier, on le prend
  · hors BKK   — le point ne tombe dans aucun des 50 (Bang Phli, Pak Kret… sont
                 en province) : on ne touche à rien, ce n'est pas une erreur
  · à décider  — aucune coordonnée exploitable : on n'invente pas, on signale

Le correctif d'écriture est ailleurs (`KhetMatcher.canoniser`, appelé par
`run.py`) : sans lui le défaut se reproduirait au prochain scrap. Celui-ci ne
traite que l'existant.

Usage :
    python ops/corriger-khet.py --dry-run     # montre, n'écrit rien
    python ops/corriger-khet.py               # applique
"""
from __future__ import annotations

import argparse
import collections
import os
import pathlib
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scraper"))

from pipeline.geo_match import KhetMatcher  # noqa: E402


def charger_env() -> None:
    for f in ("scraper/.env", ".env.local"):
        p = pathlib.Path(ROOT) / f
        if p.exists():
            for l in p.read_text(encoding="utf-8").splitlines():
                m = re.match(r'\s*([A-Z_]+)\s*=\s*"?([^"\n]+)"?\s*$', l)
                if m:
                    os.environ.setdefault(m.group(1), m.group(2))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    charger_env()
    import psycopg

    m = KhetMatcher()
    canoniques = {n for n, _ in m.khets}
    print(f"{len(canoniques)} quartiers de référence\n")

    with psycopg.connect(os.environ["SUPABASE_DB_URL"], connect_timeout=30) as cx:
        lignes = cx.execute(
            "select id, khet, lat, lng from listings "
            "where khet is not null and khet <> all(%s)",
            (list(canoniques),)).fetchall()
        print(f"{len(lignes)} annonces au quartier non canonique\n")

        corrections, hors, indecis = [], collections.Counter(), collections.Counter()
        for lid, khet, lat, lng in lignes:
            trouve = m.match(float(lat) if lat is not None else None,
                             float(lng) if lng is not None else None)
            if trouve:
                corrections.append((lid, khet, trouve))
            elif lat is not None and lng is not None:
                hors[khet] += 1
            else:
                indecis[khet] += 1

        par_paire = collections.Counter((av, ap) for _, av, ap in corrections)
        print("── CORRIGÉ (le point désigne un quartier) ──")
        for (av, ap), n in par_paire.most_common():
            print(f"   {n:>4d}  {av!r} → {ap!r}")
        print(f"   total : {len(corrections)}")

        if hors:
            print("\n── HORS BANGKOK (aucun des 50 polygones — normal) ──")
            for k, n in hors.most_common():
                print(f"   {n:>4d}  {k}")
        if indecis:
            print("\n── À DÉCIDER (pas de coordonnées — rien n'est touché) ──")
            for k, n in indecis.most_common():
                print(f"   {n:>4d}  {k}")

        if a.dry_run:
            print("\n[dry-run] rien n'a été écrit.")
            return 0
        for lid, _, ap in corrections:
            cx.execute("update listings set khet=%s where id=%s", (ap, lid))
        cx.commit()
        print(f"\n{len(corrections)} annonces mises à jour.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
