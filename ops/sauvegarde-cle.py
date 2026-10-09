"""sauvegarde-cle.py — la base de référence, copiée sur clé USB et PROUVÉE.

POURQUOI CE MODULE EXISTE
Depuis le 2026-08-23 la base de référence est locale (SQLite sur PC2). Une base
de référence sans copie hors machine n'est pas sauvegardée : un disque qui lâche
emporte tout. Décision du 2026-08-25 : **une seule base sur le PC, une copie sur
clé USB**.

CE QUI DISTINGUE CE SCRIPT D'UN `copy`
Une sauvegarde jamais relue est une sauvegarde supposée. Ici la copie est
**vérifiée par trois ouvertures réelles et indépendantes** avant que quoi que ce
soit d'ancien ne soit détruit :

  1. intégrité SQLite (`pragma quick_check`) ;
  2. comptage des annonces, comparé à la source ;
  3. requête métier — actives par source — comparée à la source.

Trois essais, trois processus de connexion distincts : une base corrompue passe
rarement les trois. **La génération précédente n'est supprimée qu'après ces
trois succès** ; en cas d'échec, on garde les deux et on crie.

LA CLÉ N'EST PAS DÉSIGNÉE PAR SA LETTRE. Elle est reconnue au dossier repère
`++SCRAP DB++` posé à sa racine : brancher la clé sur un autre port, ou sur
l'autre poste, ne casse rien. Aucune lettre de lecteur en dur, nulle part.

⚠ FAT32 : plafonné à 4 Go par fichier. Sur un volume FAT32 (ou de format
illisible), le script refuse la copie au-delà de 3,9 Go plutôt que de produire
un fichier tronqué. Le plafond est levé sur NTFS / exFAT / ReFS (format lu au
volume à chaque run). La base pesait 3,80 Go le 2026-10-09, +~70 Mo par cycle.

Usage :
    scraper/.venv/Scripts/python.exe ops/sauvegarde-cle.py
    scraper/.venv/Scripts/python.exe ops/sauvegarde-cle.py --essais 3 --garder 1
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import string
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Dossier repère à la racine de la clé. C'est LUI qui désigne la cible, pas une
#: lettre de lecteur : les lettres changent d'un port à l'autre et d'un poste à
#: l'autre, un dossier non.
REPERE = "++SCRAP DB++"

SOURCE = Path(os.environ.get("LOWI_DB") or (
    Path(os.environ.get("LOWI_OUTPUT_DIR") or (ROOT / "scraper" / "output")) / "bangkok.db"))

#: Plafond FAT32, moins une marge. Au-delà, la copie serait tronquée en silence.
PLAFOND_FAT32 = 3.9 * 1024 ** 3

#: Systèmes de fichiers SANS plafond de 4 Go par fichier. Le plafond n'est levé
#: que pour eux ; tout le reste — FAT32, FAT, ou un format illisible — le garde.
#: 2026-10-09 : le contrôle s'appliquait quel que soit le format de la clé, si
#: bien que la reformater en exFAT ou NTFS (le remède qu'il recommandait
#: lui-même) n'aurait rien changé — refus à 3,9 Go quand même, la base pesant
#: 3,80 Go et grossissant de ~70 Mo par cycle.
SANS_PLAFOND = frozenset({"NTFS", "EXFAT", "REFS"})


def systeme_fichiers(dossier: Path) -> str | None:
    """Format du volume qui porte `dossier` (« FAT32 », « exFAT », « NTFS »…).

    None si illisible : l'appelant garde alors le plafond (prudence par défaut)."""
    if os.name != "nt":
        return None
    import ctypes
    racine = str(Path(dossier).resolve().anchor)
    nom = ctypes.create_unicode_buffer(64)
    ok = ctypes.windll.kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(racine), None, 0, None, None, None, nom, len(nom))
    return nom.value if ok and nom.value else None


def plafond(dossier: Path) -> float | None:
    """Taille maximale d'une copie sur ce volume (None = pas de plafond)."""
    fs = systeme_fichiers(dossier)
    return None if fs and fs.upper() in SANS_PLAFOND else PLAFOND_FAT32


def trouver_cle() -> Path | None:
    """Le premier volume portant le dossier repère. Aucune lettre en dur."""
    for lettre in string.ascii_uppercase:
        cible = Path(f"{lettre}:/") / REPERE
        try:
            if cible.is_dir():
                return cible
        except OSError:
            continue
    return None


def _essai(chemin: Path, attendu_lignes: int, attendu_actives: dict) -> tuple[bool, str]:
    """Une vérification complète, connexion neuve à chaque fois."""
    cx = sqlite3.connect(f"file:{chemin}?mode=ro", uri=True)
    try:
        integrite = cx.execute("pragma quick_check").fetchone()[0]
        if integrite != "ok":
            return False, f"intégrité : {integrite}"
        lignes = cx.execute("select count(*) from listings").fetchone()[0]
        if lignes != attendu_lignes:
            return False, f"{lignes} annonces au lieu de {attendu_lignes}"
        actives = dict(cx.execute(
            "select source, count(*) from listings where status='active' group by source"))
        if actives != attendu_actives:
            return False, f"actives par source divergentes : {actives}"
        return True, f"{lignes} annonces, {sum(actives.values())} actives"
    except sqlite3.Error as e:
        return False, f"{type(e).__name__}: {e}"
    finally:
        cx.close()


def sauvegarder(essais: int, garder: int) -> dict:
    bilan: dict = {"source": str(SOURCE), "repere": REPERE}

    if not SOURCE.exists():
        return {**bilan, "ok": False, "raison": f"base de référence introuvable : {SOURCE}"}
    dossier = trouver_cle()
    if dossier is None:
        return {**bilan, "ok": False,
                "raison": f"aucun volume ne porte le dossier « {REPERE} » — clé absente ?"}
    bilan["destination"] = str(dossier)

    taille = SOURCE.stat().st_size
    bilan["systeme_fichiers"] = systeme_fichiers(dossier)
    maxi = plafond(dossier)
    if maxi is not None and taille > maxi:
        return {**bilan, "ok": False,
                "raison": f"base de {taille / 1024**3:.2f} Go : au-delà du plafond FAT32 "
                          f"de 4 Go (volume : {bilan['systeme_fichiers'] or 'format illisible'}). "
                          f"Reformater la clé en NTFS ou exFAT."}

    libre = os.statvfs(dossier).f_bavail * os.statvfs(dossier).f_frsize \
        if hasattr(os, "statvfs") else __import__("shutil").disk_usage(dossier).free
    if libre < taille * 2:
        return {**bilan, "ok": False,
                "raison": f"place insuffisante : {libre / 1024**3:.1f} Go libres, il en "
                          f"faut {taille * 2 / 1024**3:.1f} (copie + génération précédente)"}

    # Référence attendue, lue AVANT la copie.
    cx = sqlite3.connect(f"file:{SOURCE}?mode=ro", uri=True)
    attendu_lignes = cx.execute("select count(*) from listings").fetchone()[0]
    attendu_actives = dict(cx.execute(
        "select source, count(*) from listings where status='active' group by source"))
    cx.close()

    horodatage = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M")
    cible = dossier / f"bangkok-{horodatage}.db"
    t0 = time.perf_counter()
    src = sqlite3.connect(f"file:{SOURCE}?mode=ro", uri=True)
    dst = sqlite3.connect(cible)
    try:
        # API `backup` et non copie de fichier : la base est en WAL depuis le
        # 2026-08-25, une copie brute perdrait les transactions non fusionnées.
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    bilan.update({"copie": str(cible), "mo": round(cible.stat().st_size / 1e6, 1),
                  "secondes_copie": round(time.perf_counter() - t0, 1)})

    # ── LES TROIS ESSAIS ────────────────────────────────────────────────────
    resultats = []
    for n in range(1, essais + 1):
        ok, detail = _essai(cible, attendu_lignes, attendu_actives)
        resultats.append({"essai": n, "ok": ok, "detail": detail})
        print(f"  essai {n}/{essais} : {'OK' if ok else 'ÉCHEC'} — {detail}")
        if not ok:
            break
    bilan["essais"] = resultats
    bilan["ok"] = all(r["ok"] for r in resultats) and len(resultats) == essais

    if not bilan["ok"]:
        # RIEN n'est supprimé : on préfère deux copies douteuses à zéro copie.
        bilan["rotation"] = "annulée — la nouvelle copie n'a pas passé les essais"
        return bilan

    # ── ROTATION, seulement maintenant ──────────────────────────────────────
    anciennes = sorted((p for p in dossier.glob("bangkok-*.db") if p != cible),
                       key=lambda p: p.stat().st_mtime, reverse=True)
    supprimees = []
    for vieille in anciennes[max(0, garder - 1):]:
        try:
            vieille.unlink()
            supprimees.append(vieille.name)
            # Les fichiers annexes du mode WAL (-shm, -wal) survivaient à la
            # rotation — constaté le 2026-08-25, deux orphelins laissés sur la
            # clé. Inoffensifs mais trompeurs : un -wal traînant à côté d'une
            # base absente donne l'impression d'une copie en cours.
            for annexe in (vieille.with_name(vieille.name + "-shm"),
                           vieille.with_name(vieille.name + "-wal")):
                if annexe.exists():
                    annexe.unlink()
                    supprimees.append(annexe.name)
        except OSError as e:
            supprimees.append(f"{vieille.name} (échec: {e})")
    bilan["generations_conservees"] = garder
    bilan["supprimees"] = supprimees
    return bilan


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--essais", type=int, default=3,
                    help="nombre de vérifications avant rotation (défaut 3)")
    ap.add_argument("--garder", type=int, default=1,
                    help="générations conservées sur la clé, la nouvelle comprise")
    args = ap.parse_args()
    bilan = sauvegarder(args.essais, args.garder)
    print(json.dumps(bilan, ensure_ascii=False, indent=1))
    return 0 if bilan.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
