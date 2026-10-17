"""mois-de-stock.py — mois de stock (vente) par district, mesure exploratoire du 2026-10-17, lecture seule.

Usage : scraper/.venv/Scripts/python.exe bilan_RE/ops/mois-de-stock.py <sortie.json>
Résultats et limites : bilan_RE/docs/journal-donnees.md (2026-10-17, suite).
"""
import sqlite3, collections, statistics, json, sys
from datetime import datetime, timedelta

DB = r"C:\Lowi_bkk\scraper\output\bangkok.db"
DEB, FIN = "2026-09-14", "2026-10-12"          # FazWaz en sitemap, DDproperty pas encore à l'arrêt
MILIEU = "2026-09-28"
JOURS = 28
SOURCES = ("ddproperty", "fazwaz", "propertyscout")   # délistage crédible sur la fenêtre
MIN_STOCK, MIN_RETRAITS = 30, 10

c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
rows = c.execute(f"""
  select id, source, khet, unit_key, first_seen, delisted_at
  from listings
  where deal_type='sale' and khet is not null and khet<>''
    and price between 800000 and 100000000 and area_sqm between 15 and 500
    and source in {SOURCES}
    and first_seen <= ? and (delisted_at is null or delisted_at >= ?)
""", (FIN, DEB)).fetchall()
print("lignes", len(rows), file=sys.stderr)

d = lambda s: datetime.fromisoformat(s[:19]) if s else None
# reposts : une nouvelle annonce de la même cohorte apparaît -3 j / +21 j autour du retrait
par_cle = collections.defaultdict(list)
for r in rows:
    if r[3]:
        par_cle[r[3]].append((r[0], d(r[4])))

def est_repost(r):
    if not r[3]:
        return False
    t = d(r[5])
    return any(i != r[0] and t - timedelta(days=3) <= fs <= t + timedelta(days=21)
               for i, fs in par_cle[r[3]])

agg = collections.defaultdict(lambda: collections.Counter())
for r in rows:
    src, khet = r[1], r[2]
    fs, dl = r[4], r[5]
    actif_milieu = fs[:10] <= MILIEU and (dl is None or dl[:10] > MILIEU)
    retire = dl is not None and DEB <= dl[:10] <= FIN
    for k in (("tout", khet), (src, khet)):
        if actif_milieu:
            agg[k]["stock"] += 1
        if retire:
            agg[k]["retraits"] += 1
            if not est_repost(r):
                agg[k]["retraits_nets"] += 1

def mos(cnt, cle="retraits"):
    if cnt["stock"] < MIN_STOCK or cnt[cle] < MIN_RETRAITS:
        return None
    return cnt["stock"] / (cnt[cle] * 30 / JOURS)

out = {}
for (src, khet), cnt in agg.items():
    out.setdefault(khet, {})[src] = {"stock": cnt["stock"], "retraits": cnt["retraits"],
                                     "nets": cnt["retraits_nets"],
                                     "mos": mos(cnt), "mos_net": mos(cnt, "retraits_nets")}
json.dump(out, open(sys.argv[1], "w"), indent=1)
