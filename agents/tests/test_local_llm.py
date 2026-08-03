"""Test de non-régression du client local durci.

C'EST LE GARDE-FOU CENTRAL DU SYSTÈME. Il ne teste pas « le modèle est-il
intelligent », il teste « le dispositif est-il encore capable de détecter qu'il
ne sait pas ». Deux seuils, tirés d'une campagne de mesure sur 650+ appels
(2026-07-31, cf. docs/journal-technique.md) :

    justesse   ≥ 90/100 sur les paires étiquetées   (mesuré : 91)
    abstention ≥ 70 %   sur les 30 paires ambiguës  (mesuré : 77 %)

Le second seuil est le vrai. Une justesse élevée sans abstention signifie que le
modèle rend un verdict sur des cas indécidables — soit 28 000 fausses certitudes
d'apparence propre. C'est précisément la panne que le mode extraction corrige.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_local_llm.py
"""
from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agents.bots.organize import SCHEMA, SYSTEM, decider, fmt, prefiltre_sql  # noqa: E402
from agents.core import local_llm                                            # noqa: E402

SEUIL_JUSTESSE = 90       # sur 100
SEUIL_ABSTENTION = 0.70   # sur les ambiguës

DATA = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "pairs.json"), encoding="utf-8"))


def juger(paire: dict) -> tuple[str | None, str | None]:
    """Rend (verdict, erreur). Mode extraction : le modèle constate, le code décide."""
    try:
        faits = local_llm.ask(SYSTEM, fmt(paire), SCHEMA, num_predict=300)
    except local_llm.LLMError as e:
        return None, e.kind
    return decider(faits), None


def main() -> int:
    ok, echecs = True, []

    # ── 0. le client répond-il ? ────────────────────────────────────────
    sain, msg = local_llm.health()
    print(f"Modèle local : {'✓' if sain else '✗'} {msg}")
    if not sain:
        print("\n✗ ÉCHEC — le modèle local est injoignable.")
        return 1

    # ── 1. le pré-filtre SQL doit rester exact ──────────────────────────
    # S'il dérive, le modèle se met à voir des paires qu'il n'a pas à voir.
    etiquetees = DATA["labelled"]
    desaccords = [p for p in etiquetees
                  if (v := prefiltre_sql(p)) is not None and v != p["label"]]
    print(f"Pré-filtre SQL : {len(etiquetees) - len(desaccords)}/{len(etiquetees)} "
          f"conformes à l'étiquette")
    if desaccords:
        ok = False
        echecs.append(f"le pré-filtre SQL contredit {len(desaccords)} étiquette(s)")

    # ── 2. justesse sur les paires étiquetées ───────────────────────────
    jeu = etiquetees[10:110]
    t0, justes, pannes = time.time(), 0, 0
    for i, p in enumerate(jeu, 1):
        verdict, err = juger(p)
        if err:
            pannes += 1
        elif verdict == p["label"]:
            justes += 1
        if i % 25 == 0:
            print(f"  … {i}/{len(jeu)} ({justes} justes, {pannes} pannes)")
    dt = time.time() - t0
    print(f"Justesse : {justes}/{len(jeu)} — pannes client : {pannes} "
          f"— {dt / len(jeu):.1f} s/paire")
    if justes < SEUIL_JUSTESSE:
        ok = False
        echecs.append(f"justesse {justes}/100 < seuil {SEUIL_JUSTESSE}")
    if pannes:
        ok = False
        echecs.append(f"{pannes} panne(s) client — sortie vide ou schéma invalide")

    # ── 3. ABSTENTION sur les ambiguës — le seuil qui compte ────────────
    amb = DATA["ambiguous"]
    abst = 0
    for p in amb:
        verdict, err = juger(p)
        if err is None and verdict == "insufficient":
            abst += 1
    taux = abst / len(amb) if amb else 0.0
    print(f"Abstention : {abst}/{len(amb)} = {taux:.0%}")
    if taux < SEUIL_ABSTENTION:
        ok = False
        echecs.append(f"abstention {taux:.0%} < seuil {SEUIL_ABSTENTION:.0%} — "
                      f"le modèle invente des certitudes sur des cas indécidables")

    print()
    if ok:
        print("✓ Non-régression OK — le dispositif sait encore dire qu'il ne sait pas.")
        return 0
    print("✗ ÉCHEC :")
    for e in echecs:
        print(f"   · {e}")
    print("\nNE PAS relâcher les seuils pour faire passer le test : ils viennent "
          "d'une mesure, pas d'une intuition. Vérifier d'abord le client "
          "(paramètre `think` natif, détection de sortie vide) puis le prompt.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
