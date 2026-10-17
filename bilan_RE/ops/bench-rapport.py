"""bench-rapport.py — combien de temps prend un bilan sur CETTE machine ?

    python bilan_RE/ops/bench-rapport.py --db <chemin>/bangkok.db

Lance les mêmes 10 annonces que la mesure de référence de PC2 (2026-10-17),
d'abord une par une, puis par 3 et par 6 en parallèle, et affiche la machine.
Lecture seule : les rapports vont dans un dossier temporaire, effacé à la fin.

Référence PC2 (i7-10510U, 4 cœurs / 8 threads, 16 Go, SSD NVMe, base 4,6 Go) :
1 rapport ≈ 10,1 s ; 3 en parallèle ≈ 18,5 s ; 6 ≈ 28,1 s. Profil : ~90 % du
temps en lecture de la base (requêtes qui parcourent toute la table), pas en
calcul — un processeur plus rapide aide, un disque et de la RAM aussi, un GPU
non.

Prérequis : la base `bangkok.db` (copiée de PC2) ; `scores-tension/scores-latest.json`
à côté d'elle est facultatif (sans lui, la tension n'est pas lue, le temps
change à peine : 0,5 s mesurées).
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

URLS = [  # tirées au hasard dans les ventes actives le 2026-10-17, figées pour comparer
    "https://www.ddproperty.com/en/property/rhythm-charoenkrung-pavillion-for-sale-500255175",
    "https://www.ddproperty.com/en/property/life-asoke-rama-9-for-sale-500563294",
    "https://www.ddproperty.com/en/property/elio-del-moss-phaholyothin-34-for-sale-11219316",
    "https://www.ddproperty.com/en/property/the-lumpini-24-for-sale-500337518",
    "https://www.fazwaz.com/property-sales/1-bedroom-condo-for-sale-at-noble-ploenchit-in-lumphini-bangkok-u636442",
    "https://www.fazwaz.com/property-sales/3-bedroom-condo-for-sale-at-president-park-sukhumvit-24-in-khlong-tan-bangkok-u5995772",
    "https://www.ddproperty.com/en/property/langsuan-ville-for-sale-500423064",
    "https://www.ddproperty.com/en/property/up-ekamai-for-sale-500450752",
    "https://www.ddproperty.com/en/property/maru-ekkamai-2-for-sale-500397972",
    "https://www.ddproperty.com/en/property/oriental-towers-for-sale-500264732",
]


def machine() -> str:
    cpu = platform.processor()
    if sys.platform == "win32":
        try:
            cpu = subprocess.run(["powershell", "-NoProfile", "-Command",
                                  "(Get-CimInstance Win32_Processor).Name"],
                                 capture_output=True, text=True, timeout=20).stdout.strip() or cpu
        except Exception:
            pass
    return f"{cpu} · {os.cpu_count()} threads · {platform.system()} {platform.release()}"


def un_rapport(url: str, db: str, out: str) -> float:
    t = time.perf_counter()
    r = subprocess.run([sys.executable, "-m", "bilan_RE.tension.rapport", "--url", url, "--db", db, "--out", out],
                       cwd=RACINE, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-800:])
    return time.perf_counter() - t


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    db = os.path.abspath(a.db)
    print(f"Machine : {machine()}")
    print(f"Base    : {db} ({os.path.getsize(db) / 1e9:.1f} Go)\n")
    out = tempfile.mkdtemp(prefix="bench-rapport-")
    try:
        un_rapport(URLS[0], db, out)          # préchauffe : cache disque, imports
        seq = [un_rapport(u, db, out) for u in URLS]
        print(f"1 à la fois  : médiane {sorted(seq)[len(seq) // 2]:.1f} s "
              f"(min {min(seq):.1f}, max {max(seq):.1f})   — PC2 : 10,1 s")
        for n, ref in ((3, 18.5), (6, 28.1)):
            t = time.perf_counter()
            with ThreadPoolExecutor(n) as ex:
                list(ex.map(lambda u: un_rapport(u, db, out), URLS[:n]))
            print(f"{n} en parallèle : tous prêts en {time.perf_counter() - t:.1f} s   — PC2 : {ref} s")
    finally:
        shutil.rmtree(out, ignore_errors=True)


if __name__ == "__main__":
    main()
