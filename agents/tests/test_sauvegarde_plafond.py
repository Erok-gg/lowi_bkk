"""test_sauvegarde_plafond.py — le plafond de 4 Go suit le format RÉEL de la clé.

POURQUOI CE TEST EXISTE
2026-10-09 : `ops/sauvegarde-cle.py` refusait toute copie au-delà de 3,9 Go
quel que soit le système de fichiers. Reformater la clé en NTFS ou exFAT — le
remède qu'il recommandait lui-même — n'aurait rien changé : la base pesait
3,80 Go (+~70 Mo par cycle), la sauvegarde aurait échoué quand même 1 à
2 nuits plus tard.

Ce que ce test vérifie :
  1. FAT32 et format illisible → plafond gardé (on ne lève jamais un garde-fou
     de troncature silencieuse sur une supposition) ;
  2. NTFS / exFAT / ReFS (casse indifférente) → pas de plafond ;
  3. `systeme_fichiers` lit le vrai format d'un volume réel (C: en NTFS ici).

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_sauvegarde_plafond.py
"""
import importlib.util
import os
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("sauvegarde_cle", RACINE / "ops" / "sauvegarde-cle.py")
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)

vrai = sc.systeme_fichiers
for fs, attendu in (("FAT32", sc.PLAFOND_FAT32), ("FAT", sc.PLAFOND_FAT32), (None, sc.PLAFOND_FAT32),
                    ("NTFS", None), ("exFAT", None), ("ReFS", None)):
    sc.systeme_fichiers = lambda d, fs=fs: fs
    assert sc.plafond(Path("X:/")) == attendu, (fs, sc.plafond(Path("X:/")))
sc.systeme_fichiers = vrai
print("1-2. plafond gardé sur FAT32/illisible, levé sur NTFS/exFAT/ReFS : OK")

if os.name == "nt":
    fs_c = sc.systeme_fichiers(Path(os.environ.get("SystemDrive", "C:") + "\\"))
    assert fs_c, "le format du disque système doit être lisible"
    print(f"3. format réel du disque système : {fs_c} : OK")
print("\nOK — test_sauvegarde_plafond")
