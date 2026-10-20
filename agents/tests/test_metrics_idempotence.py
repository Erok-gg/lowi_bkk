# -*- coding: utf-8 -*-
"""test_metrics_idempotence — `aplatir` doit pouvoir s'appliquer DEUX fois.

POURQUOI CE TEST EXISTE (défaut mesuré le 2026-10-16)
`aplatir` est appliquée à l'ÉCRITURE par l'orchestrateur
(`orchestrator.py` : `metrics = aplatir(metrics)` avant `end_run`) PUIS à
chaque LECTURE (`watch_health`, `overseer`, `ops/fraicheur`, `ops/pouls`,
`ops/mesure-cadence`). Ce double passage est délibéré — le docstring du module
l'explique : la médiane des 10 derniers runs doit aussi voir les runs déjà en
base, écrits avant un correctif.

Il n'était pas idempotent. L'agrégat racine servait de point de départ au
cumul, si bien que la somme des étapes s'y ajoutait une seconde fois :
**×2 exactement** dès qu'un agent chaîne plus d'une étape, ×3 au troisième
passage. Rejeu du ledger sur 30 j : 51 runs sur 391 touchés, les deux seuls
agents qui chaînent (extract-fazwaz 26, extract-ddproperty 25), 8 champs
chacun. Conséquences mesurées :
  - `agents/audits/2026-10-15.md` portait les DEUX chiffres pour le même run,
    le récit à 171 622 scannées et son propre tableau à 85 811 ;
  - `pouls.json` du cycle 2026-10-14 annonçait `annonces_ecrites: 3236` pour
    1 650 réelles (+96 %) ;
  - 8 verdicts `volume_anormal` sur 108 runs rejoués étaient faux (bornes de
    `bandes` absolues comparées à un volume doublé).

Ce test ne vérifie pas l'agrégation elle-même (c'est `test_metrics.py`), mais
la seule propriété que le double appel exige : **aplatir(aplatir(m)) ==
aplatir(m)**.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.core.metrics import SOMMABLES, aplatir  # noqa: E402

echecs = []


def verifie(nom: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"{nom} : OK  {detail}")
    else:
        echecs.append(f"{nom} : ÉCHEC  {detail}")
        print(f"{nom} : ÉCHEC  {detail}")


# ── 1. Le cas réel du défaut : agrégat déjà en racine + 2 étapes ──────────────
# Forme exacte de ce que l'orchestrateur stocke pour extract-fazwaz (run 859
# du 2026-10-15 : 34 872 + 50 939 = 85 811 scannées).
fazwaz = {
    "scannees": 85811, "nouvelles": 0, "changees": 0, "retirees": 0,
    "inchangees": 29348, "dedup": 29348,
    "erreurs_http": 0, "erreurs_images": 0, "lignes_log": 129, "traces_erreur": 0,
    "exit": 0, "then_exit": 0,
    "etapes": [
        {"etape": "principal", "exit": 0, "scannees": 34872, "nouvelles": 0,
         "changees": 0, "retirees": 0, "inchangees": 13159, "dedup": 13159,
         "erreurs_http": 0, "erreurs_images": 0, "lignes_log": 83, "traces_erreur": 0},
        {"etape": "then_0", "exit": 0, "scannees": 50939, "nouvelles": 0,
         "changees": 0, "retirees": 0, "inchangees": 16189, "dedup": 16189,
         "erreurs_http": 0, "erreurs_images": 0, "lignes_log": 46, "traces_erreur": 0},
    ],
}
un = aplatir(fazwaz)
deux = aplatir(un)
trois = aplatir(deux)
verifie("agrégat déjà en racine", un["scannees"] == 85811,
        f"(scannees={un['scannees']}, attendu 85811)")
verifie("2e passage identique", deux == un, f"(scannees={deux['scannees']})")
verifie("3e passage identique", trois == un, f"(scannees={trois['scannees']})")

# ── 2. Sans agrégat en racine (1er passage à l'écriture) : la somme est faite ──
sans_racine = {k: v for k, v in fazwaz.items()
               if k in ("etapes",)}
a = aplatir(sans_racine)
verifie("somme faite quand la racine est vide",
        a["scannees"] == 85811 and a["inchangees"] == 29348,
        f"(scannees={a['scannees']}, inchangees={a['inchangees']})")
verifie("somme idempotente", aplatir(a) == a)

# ── 3. Un sommable porté par la SEULE racine n'est pas perdu ──────────────────
# Le correctif ne vide que les champs qu'au moins une étape déclare : sinon un
# total calculé ailleurs et posé en racine disparaîtrait silencieusement.
racine_seule = {
    "lignes_purgees": 42,
    "etapes": [{"etape": "principal", "exit": 0, "scannees": 10},
               {"etape": "then_0", "exit": 0, "scannees": 5}],
}
b = aplatir(racine_seule)
verifie("sommable de la seule racine conservé", b.get("lignes_purgees") == 42,
        f"(lignes_purgees={b.get('lignes_purgees')})")
verifie("sommable des étapes quand même sommé", b.get("scannees") == 15,
        f"(scannees={b.get('scannees')})")
verifie("mélange idempotent", aplatir(b) == b)

# ── 4. Une seule étape : branche `update`, déjà idempotente, ne régresse pas ──
une_etape = {
    "exit": 0, "scannees": 1238, "nouvelles": 36,
    "etapes": [{"etape": "principal", "exit": 0, "scannees": 1238, "nouvelles": 36}],
}
c1 = aplatir(une_etape)
verifie("une étape = identité", c1["scannees"] == 1238 and c1["nouvelles"] == 36,
        f"(scannees={c1['scannees']})")
verifie("une étape idempotente", aplatir(c1) == c1)

# ── 5. `exit` / `then_exit` survivent au double passage ───────────────────────
# Le contrat de sortie des deux extracteurs qui chaînent en dépend : un `then`
# en échec ne doit pas se cacher derrière un `principal` à 0.
casse = {
    "etapes": [{"etape": "principal", "exit": 0, "scannees": 10},
               {"etape": "then_0", "exit": 2, "scannees": 5}],
}
d1 = aplatir(casse)
d2 = aplatir(d1)
verifie("exit / then_exit préservés",
        d1.get("exit") == 0 and d1.get("then_exit") == 2 and d2 == d1,
        f"(exit={d1.get('exit')}, then_exit={d1.get('then_exit')})")

# ── 6. Garde-fou sur le ledger réel, s'il est là ───────────────────────────────
# Le test doit se taire quand le ledger est absent (autre poste, dépôt frais) :
# un essai qui échoue faute de données apprend à ignorer les essais.
LEDGER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ledger.db")
if os.path.exists(LEDGER):
    gonfles, examines = [], 0
    try:
        cx = sqlite3.connect(f"file:{LEDGER}?mode=ro", uri=True)
        cx.row_factory = sqlite3.Row
        for r in cx.execute("select id, agent, metrics from agent_runs "
                            "where metrics is not null order by id desc limit 400"):
            try:
                brut = json.loads(r["metrics"] or "{}")
            except ValueError:
                continue
            if not isinstance(brut.get("etapes"), list) or len(brut["etapes"]) < 2:
                continue
            examines += 1
            plat = aplatir(brut)
            for k in SOMMABLES:
                v = brut.get(k)
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    continue
                if plat.get(k) != v:
                    gonfles.append((r["id"], r["agent"], k, v, plat.get(k)))
        cx.close()
    except sqlite3.Error as e:                              # noqa: BLE001
        print(f"ledger illisible, essai 6 ignoré : {e}")
    else:
        verifie("ledger réel : aucun champ gonflé", not gonfles,
                f"({examines} run(s) multi-étapes examinés"
                + (f", gonflés : {gonfles[:3]}" if gonfles else "") + ")")
else:
    print("pas de ledger local, essai 6 ignoré")

print()
if echecs:
    print("ÉCHECS :")
    for e in echecs:
        print("  -", e)
    sys.exit(1)
print("OK — test_metrics_idempotence : tous les essais passent")
