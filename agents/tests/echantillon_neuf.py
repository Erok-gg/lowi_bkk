"""echantillon_neuf.py — retire un jeu de paires FRAIS depuis la production.

POURQUOI. Le 2026-08-11, `test_local_llm.py` est passé de 91-92/100 (1-3 août) à
87 puis 88, avec l'abstention montée de 77 % à 80 %. Deux exécutions donnent le
même profil, donc ce n'est pas du bruit. Et `git` est formel : `local_llm.py`,
`organize.py` et le jeu de test sont INCHANGÉS.

Il reste deux explications, que seul un échantillon neuf sépare :
  · le MODÈLE se comporte différemment (Ollama, pilote, état machine) ;
  · le JEU du 31 juillet n'est plus représentatif de ce que la production
    soumet aujourd'hui — la base est passée de 35 000 à 52 900 annonces, et
    `organize` n'a rendu que 9 % d'abstention ce matin contre 77 % au banc.

Si le score remonte sur données fraîches, c'est le jeu qui a vieilli. S'il reste
bas, c'est le modèle.

MÊME ARBITRE QUE LA PRODUCTION. Les étiquettes viennent de `prefiltre_sql`, la
fonction qui tranche en production — jamais d'un jugement à la main. C'est la
correction du 2026-07-31 : le jeu initial avait été étiqueté en testant
« republication séquentielle » AVANT « les deux actives », l'inverse de la
production. 10 paires sur 120 étaient fausses, et le score est passé de 91 à 99
une fois corrigé. **Trois fois cette campagne, la référence était l'erreur.**

Usage : scraper/.venv/Scripts/python.exe agents/tests/echantillon_neuf.py
"""
from __future__ import annotations

import json
import os
import random
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scraper"))

from agents.bots.organize import SQL_PAIRES, prefiltre_sql  # noqa: E402

ICI = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join(ICI, "pairs_neuf.json")

#: Mêmes effectifs que le jeu d'origine, pour que les scores soient comparables.
N_TRANCHEES, N_AMBIGUES = 120, 30


def charger_env() -> None:
    import pathlib
    for f in ("scraper/.env", ".env.local"):
        p = pathlib.Path(ROOT) / f
        if p.exists():
            for l in p.read_text(encoding="utf-8").splitlines():
                m = re.match(r'\s*([A-Z_]+)\s*=\s*"?([^"\n]+)"?\s*$', l)
                if m:
                    os.environ.setdefault(m.group(1), m.group(2))


def main() -> int:
    charger_env()
    import psycopg

    with psycopg.connect(os.environ["SUPABASE_DB_URL"], connect_timeout=60) as cx:
        cur = cx.execute(SQL_PAIRES)
        cols = [c.name for c in cur.description]
        paires = [dict(zip(cols, r)) for r in cur.fetchall()]
    print(f"  {len(paires)} paires candidates en base")

    tranchees, ambigues = [], []
    for p in paires:
        v = prefiltre_sql(p)
        (tranchees if v else ambigues).append((p, v))
    print(f"  tranchees par SQL : {len(tranchees)}  |  ambigues : {len(ambigues)}")

    random.seed(2026_08_11)

    def alleger(p: dict) -> dict:
        """On ne garde que ce que le prompt utilise, plus de quoi rejouer."""
        gardees = ("ida", "idb", "condo_name", "khet", "bedrooms", "deal_type",
                   "sa", "sb", "pa", "pb", "sta", "stb", "fsa", "fsb", "da", "db",
                   "aga", "agb", "ecart_prix", "deux_actives",
                   # requis par prefiltre_sql : sans lui le rejeu plante
                   "sequentiel")
        return {k: (str(p[k]) if hasattr(p.get(k), "isoformat") else p.get(k))
                for k in gardees if k in p}

    # Équilibrage : sans lui, `distinct_units` écraserait tout et la justesse
    # mesurerait surtout la capacité à dire « deux actives ».
    par_verdict: dict[str, list] = {}
    for p, v in tranchees:
        par_verdict.setdefault(v, []).append(p)
    for v, lst in par_verdict.items():
        print(f"    {v:16s} {len(lst)}")

    lab = []
    par_classe = max(1, N_TRANCHEES // max(1, len(par_verdict)))
    for v, lst in par_verdict.items():
        for p in random.sample(lst, min(par_classe, len(lst))):
            lab.append({**alleger(p), "label": v})
    random.shuffle(lab)

    amb = [alleger(p) for p, _ in random.sample(ambigues, min(N_AMBIGUES, len(ambigues)))]

    json.dump({"labelled": lab, "ambiguous": amb},
              open(SORTIE, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(f"\n  ecrit : {SORTIE}")
    print(f"  {len(lab)} tranchees, {len(amb)} ambigues")
    return 0


if __name__ == "__main__":
    sys.exit(main())
