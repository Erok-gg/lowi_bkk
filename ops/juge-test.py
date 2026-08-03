"""juge-test.py — évalue un scrap de test isolé, avec des critères explicites.

Le verdict n'est pas une impression : chaque contrôle a un seuil écrit d'avance,
et le script sort en code 1 si un contrôle BLOQUANT échoue.

Usage : scraper/.venv/Scripts/python.exe ops/juge-test.py <dossier-de-test>
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys

# ── seuils, fixés AVANT de voir les résultats ────────────────────────────
SEUILS = {
    # (libellé, clé, minimum en %, bloquant ?)
    "prix":            ("price is not null and price > 0",           99, True),
    "surface":         ("area_sqm is not null and area_sqm > 0",     90, True),
    "chambres":        ("bedrooms is not null",                      90, True),
    "quartier":        ("khet is not null",                          95, True),
    "coordonnées":     ("lat is not null and lng is not null",       80, True),
    "immeuble":        ("condo_name is not null",                    90, True),
    "descriptif":      ("description is not null",                   70, True),
    "provenance":      ("agent_id is not null",                      70, False),
    "date de mise en ligne": ("posted_at is not null",               70, False),
    "clé de cohorte":  ("unit_key is not null",                      90, False),
}
VOLUME_MIN_PCT = 80       # % du volume demandé
PLAUSIBLE_MIN_PCT = 90    # % dans les bornes de marché
ERREURS_MAX = 10          # lignes [erreur] tolérées dans le log


def pct(n: int, total: int) -> float:
    return 100.0 * n / total if total else 0.0


def main() -> int:
    if len(sys.argv) < 2:
        print("usage : juge-test.py <dossier-de-test>")
        return 2
    dossier = sys.argv[1]
    db_path = os.path.join(dossier, "bangkok.db")
    if not os.path.exists(db_path):
        print(f"✗ base introuvable : {db_path}")
        return 2

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    total = db.execute("select count(*) c from listings").fetchone()["c"]
    if total == 0:
        print("✗ BLOQUANT — aucune annonce collectée.")
        return 1

    # volume demandé, lu depuis le nom du dossier
    m = re.search(r"-(\d+)$", os.path.basename(dossier.rstrip("\\/")))
    demande = int(m.group(1)) if m else total

    print(f"╔═ RÉSULTAT DU TEST ═══════════════════════════════════════")
    print(f"║ dossier : {os.path.basename(dossier)}")
    print(f"║ collecté : {total} annonces (demandé {demande})")
    print(f"╚══════════════════════════════════════════════════════════\n")

    echecs, avertissements = [], []

    # ── 1. volume ────────────────────────────────────────────────────────
    p = pct(total, demande)
    ok = p >= VOLUME_MIN_PCT
    print(f"{'✓' if ok else '✗'} volume            {total}/{demande} = {p:.0f}% "
          f"(seuil {VOLUME_MIN_PCT}%)")
    if not ok:
        echecs.append(f"volume à {p:.0f}%")

    # ── 2. complétude des champs ─────────────────────────────────────────
    print("\n  Complétude des champs")
    for libelle, (cond, seuil, bloquant) in SEUILS.items():
        try:
            n = db.execute(f"select count(*) c from listings where {cond}").fetchone()["c"]
        except sqlite3.OperationalError as e:
            print(f"  ? {libelle:24s} colonne absente ({e})")
            (echecs if bloquant else avertissements).append(f"{libelle} : colonne absente")
            continue
        p = pct(n, total)
        ok = p >= seuil
        marque = "✓" if ok else ("✗" if bloquant else "!")
        print(f"  {marque} {libelle:24s} {n:5d}/{total} = {p:5.1f}%  (seuil {seuil}%)")
        if not ok:
            (echecs if bloquant else avertissements).append(
                f"{libelle} à {p:.1f}% (seuil {seuil}%)")

    # ── 3. plausibilité marché ───────────────────────────────────────────
    # CHAQUE deal_type contre SES bornes. Le juge prenait auparavant le type le
    # plus fréquent et confrontait TOUT le lot à ces bornes-là : sur un scrap
    # mixte il annonçait 50,5 % d'invraisemblance, ce qui n'était que la part de
    # l'autre type. Il avait été écrit pour un dossier de test mono-type.
    # Un garde-fou qui crie au loup est pire que pas de garde-fou.
    BORNES = {"rent": "price >= 3000 and price <= 500000",
              "sale": "price >= 800000 and price <= 100000000"}
    AIRE = "(area_sqm is null or (area_sqm >= 15 and area_sqm <= 500))"
    n_ok = n_tot = 0
    detail = []
    for dt, borne in BORNES.items():
        t = db.execute("select count(*) c from listings where deal_type=?",
                       (dt,)).fetchone()["c"]
        if not t:
            continue
        k = db.execute(f"select count(*) c from listings where deal_type=? "
                       f"and {borne} and {AIRE}", (dt,)).fetchone()["c"]
        n_ok += k
        n_tot += t
        detail.append(f"{dt} {pct(k, t):.1f}%")
    p = pct(n_ok, n_tot)
    ok = p >= PLAUSIBLE_MIN_PCT
    print(f"\n{'✓' if ok else '✗'} plausibilité      {n_ok}/{n_tot} = {p:.1f}% dans les bornes "
          f"({', '.join(detail)} — seuil {PLAUSIBLE_MIN_PCT}%)")
    if not ok:
        echecs.append(f"plausibilité à {p:.1f}%")

    # ── 4. qualité du descriptif (la nouveauté à valider) ────────────────
    row = db.execute("select count(*) n, avg(length(description)) moy, "
                     "min(length(description)) mn, max(length(description)) mx "
                     "from listings where description is not null").fetchone()
    if row["n"]:
        print(f"\n  Descriptifs : {row['n']} capturés — longueur "
              f"min {row['mn']} / moy {row['moy']:.0f} / max {row['mx']} car.")
        # un descriptif qui ressemble à du code ou à du texte de marque = défaut
        suspects = db.execute(
            "select count(*) c from listings where description is not null and ("
            "description like '%{%:%;%' or description like '%function(%' "
            "or lower(description) like '%most popular property website%')"
        ).fetchone()["c"]
        if suspects:
            print(f"  ✗ {suspects} descriptif(s) contiennent du code ou du texte de marque")
            echecs.append(f"{suspects} descriptifs pollués")
        else:
            print("  ✓ aucun descriptif pollué (code / texte de marque)")
        ech = db.execute("select description from listings where description is not null "
                         "order by random() limit 1").fetchone()
        if ech:
            print(f"  échantillon : « {ech['description'][:180]}… »")

    # ── 5. doublons internes ─────────────────────────────────────────────
    dbl = db.execute("select count(*) c from (select id from listings "
                     "group by id having count(*) > 1)").fetchone()["c"]
    print(f"\n{'✓' if dbl == 0 else '✗'} identifiants uniques  {dbl} collision(s)")
    if dbl:
        echecs.append(f"{dbl} identifiants en collision")

    # ── 6. images ────────────────────────────────────────────────────────
    try:
        imgs = db.execute("select count(*) c from listing_images").fetchone()["c"]
        avec = db.execute("select count(distinct listing_id) c from listing_images").fetchone()["c"]
        print(f"  images            {imgs} fichiers pour {avec}/{total} annonces "
              f"({pct(avec, total):.0f}%)")
    except sqlite3.OperationalError:
        print("  images            table absente")

    # ── 7. erreurs dans le log ───────────────────────────────────────────
    log = os.path.join(dossier, "scrap.log")
    if os.path.exists(log):
        txt = open(log, encoding="utf-8", errors="replace").read()
        err = txt.count("[erreur]")
        tb = txt.lower().count("traceback")
        ok = err <= ERREURS_MAX and tb == 0
        print(f"\n{'✓' if ok else '✗'} log               {err} erreur(s) d'annonce, "
              f"{tb} traceback(s)  (seuils {ERREURS_MAX} / 0)")
        if not ok:
            echecs.append(f"{err} erreurs, {tb} tracebacks")

    # ── verdict ──────────────────────────────────────────────────────────
    print("\n" + "═" * 62)
    if avertissements:
        print("AVERTISSEMENTS (non bloquants) :")
        for a in avertissements:
            print(f"  ! {a}")
    if echecs:
        print("\n✗ NON CONCLUANT — corriger avant le lancement complet :")
        for e in echecs:
            print(f"  · {e}")
        return 1
    print("\n✓ CONCLUANT — le scrap est prêt pour un lancement complet.")
    if avertissements:
        print("  (les avertissements ci-dessus ne bloquent pas, mais sont à connaître)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
