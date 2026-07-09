"""fetch_official.py — Récupère les données officielles récurrentes (cf. official/sources.md).

v1 : population DOPA par khet (mensuelle) + indice BOT (manuel via bot-manual.json,
automatique si BOT_API_KEY présent un jour). Écrit study/official/official-latest.json
(+ copie datée) consommé par run_study.py.

Lancement seul :  scraper/.venv/Scripts/python.exe study/fetch_official.py
Sinon appelé automatiquement par run_study.py (best effort — l'étude tourne sans).
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ODIR = os.path.join(ROOT, "study", "official")

sys.path.insert(0, os.path.join(ROOT, "scraper"))
import requests  # noqa: E402

FWD = "https://stat.bora.dopa.go.th/stat/statnew/connectSAPI/stat_forward.php?API="
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://stat.bora.dopa.go.th/stat/statnew/statMONTH/statmonth/",
}

def buddhist_yymm(d: date) -> str:
    """Mois précédent en année bouddhiste 2 chiffres + mois (ex. 2026-07 → '6906')."""
    y, m = d.year, d.month - 1
    if m == 0:
        y, m = y - 1, 12
    return f"{(y + 543) % 100:02d}{m:02d}"

def prev_yymm(yymm: str) -> str:
    yy, mm = int(yymm[:2]), int(yymm[2:])
    mm -= 1
    if mm == 0:
        yy, mm = yy - 1, 12
    return f"{yy:02d}{mm:02d}"

def fetch_dopa_pop() -> dict | None:
    """Population par khet (essaie le mois dernier, recule jusqu'à 3 mois si vide)."""
    codes = json.load(open(os.path.join(ODIR, "khet-codes.json"), encoding="utf-8"))
    codes = {k: v for k, v in codes.items() if not k.startswith("_")}
    yymm = buddhist_yymm(date.today())
    for _ in range(3):
        # sonde sur un district avant de lancer les 50
        probe = requests.get(
            FWD + f"/api/statpophouse/v1/statpop/list?action=24&yymm={yymm}&nat=999&popst=99&cc=10&rcode=1004",
            headers=HEADERS, timeout=40)
        ok = False
        try:
            rows = probe.json()
            ok = bool(rows) and any(r.get("lsSumTotTot") for r in rows)
        except Exception:
            ok = False
        if ok:
            break
        yymm = prev_yymm(yymm)
    else:
        print("  DOPA : aucun mois disponible (WAF ? format ?) — skip")
        return None

    print(f"  DOPA : mois {yymm} (bouddhiste)")
    pops = {}
    for rcode, khet in codes.items():
        url = FWD + (f"/api/statpophouse/v1/statpop/list?action=24&yymm={yymm}"
                     f"&nat=999&popst=99&cc=10&rcode={rcode}")
        try:
            rows = requests.get(url, headers=HEADERS, timeout=40).json()
            total = sum(int(r.get("lsSumTotTot") or 0) for r in rows)
            if total > 0:
                pops[khet] = total
        except Exception as e:
            print(f"    {khet}: erreur ({str(e)[:60]})")
        time.sleep(0.4)  # politesse
    print(f"  DOPA : {len(pops)}/50 khets")
    return {"yymm_buddhist": yymm, "population_by_khet": pops} if pops else None

def load_bot_manual() -> dict | None:
    """Indice BOT saisi à la main (en attendant une clé API). Format libre documenté."""
    path = os.path.join(ODIR, "bot-manual.json")
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    return None

def main() -> dict | None:
    print("▶ fetch_official")
    out = {"fetched": date.today().isoformat()}
    dopa = fetch_dopa_pop()
    if dopa:
        out["dopa"] = dopa
    bot = load_bot_manual()
    if bot:
        out["bot"] = bot
    if len(out) == 1:
        print("  rien de récupéré")
        return None
    latest = os.path.join(ODIR, "official-latest.json")
    dated = os.path.join(ODIR, f"official-{date.today().isoformat()}.json")
    for p in (latest, dated):
        json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✓ {latest}")
    return out

if __name__ == "__main__":
    main()
