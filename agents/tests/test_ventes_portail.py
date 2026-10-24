"""Ventes conclues d'un portail : source FAIBLE, tenue à l'écart des annonces.

    scraper/.venv/Scripts/python.exe agents/tests/test_ventes_portail.py

Vérifie ce qui doit rester vrai (décision du 2026-10-22) :
  1. le parseur lit les ventes ET la synthèse écrite par le portail ;
  2. un format cassé ne lève jamais (le scrap ne doit pas échouer pour ça) ;
  3. l'écriture est rejouable (relire la page ne crée rien) ;
  4. chaque ligne est étiquetée 'faible' et `listings` n'est pas touchée ;
  5. le bilan ne donne une médiane qu'à partir de MIN_VENTES_MEDIANE ventes, et
     toujours avec l'étiquette « Weak source ».
Base temporaire : jamais celle de production.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RACINE), str(RACINE / "scraper")]

from pipeline.ventes_portail import lire_fazwaz          # noqa: E402
from store.sqlite_store import SqliteStore               # noqa: E402
from bilan_RE.tension import rapport                     # noqa: E402

echecs: list[str] = []


def verif(nom: str, ok: bool, detail: str = "") -> None:
    print(("  ok   " if ok else "  ECHEC ") + nom + (f" - {detail}" if detail else ""))
    if not ok:
        echecs.append(nom)


def page(n: int) -> str:
    units = [{"unit_id": i, "sold_date": f"2025-{1 + i % 9:02d}-10", "sold_price": f"{5000000 + 100000 * i}.0",
              "unit_area": "37.0", "floor_number": 20 + i, "bedrooms": 1, "furniture_option": 1,
              "property_ownership_title": "Foreign Quota" if i % 2 else "Thai Quota"} for i in range(n)]
    bloc = [{"saleType": "forsale", "units": units,
             "description": "We have data on the last 29 sales transactions that have taken place in X. The overall "
                            "price per sqm of these sales was ฿159,000, and they were listed for an average of "
                            "715 days before being sold. The actual sales prices were 7% below the initial listing prices."}]
    return ("<div><previous-sales v-if=\"isLoadedSection('previous-sales')\" :data='" + json.dumps(bloc)
            + "' :active-tab-index=\"0\"></previous-sales></div>")


print("Parseur")
v, r = lire_fazwaz(page(6))
verif("6 ventes lues", len(v) == 6, str(len(v)))
verif("synthèse du portail lue", r == {"n": 29.0, "price_per_sqm": 159000.0, "jours_avant_vente": 715.0,
                                       "decote_pct": 7.0}, str(r))
verif("quota lu", {x["quota"] for x in v} == {"thai", "foreigner"})
verif("page sans composant -> vide", lire_fazwaz("<html></html>") == ([], {}))
verif("JSON cassé -> vide, sans lever", lire_fazwaz("<previous-sales :data='[oops' :x") == ([], {}))

print("Store")
tmp = Path(tempfile.mkdtemp())
st = SqliteStore(tmp / "t.db")
st.db.execute("insert into listings (id, source, source_url, deal_type, status, first_seen, last_seen)"
              " values ('a','fazwaz','u','sale','active','2026-10-01','2026-10-01')")
avant = st.db.execute("select count(*) from listings").fetchone()[0]
proj = [{"cle": "k/immeuble-x", "url": "https://x", "condo_name": "Immeuble X", "ventes": v, "resume": r}]
verif("1re écriture : 6 nouvelles", st.enregistrer_ventes_portail("fazwaz", proj) == (6, 6))
verif("2e écriture rejouable : 0 nouvelle", st.enregistrer_ventes_portail("fazwaz", proj) == (0, 6))
verif("toutes étiquetées 'faible'", st.db.execute(
    "select count(*) from ventes_portail where fiabilite != 'faible'").fetchone()[0] == 0)
verif("`listings` intacte", st.db.execute("select count(*) from listings").fetchone()[0] == avant)
st.db.commit()
st.db.close()

print("Bilan")
c = sqlite3.connect(tmp / "t.db")
ann = {"cle": "immeuble x", "surface": 37.0, "chambres": 1, "prix_m2": 140000.0}
b = rapport._ventes_portail(c, ann, date(2026, 10, 22))
verif("bloc présent et étiqueté", bool(b) and b["fiabilite"] == "low" and b["etiquette"] == "Weak source")
verif("6 comparables < seuil 7 ? pas de médiane" if rapport.MIN_VENTES_MEDIANE > 6 else
      "6 comparables >= seuil : médiane", (b["mediane_m2"] is None) == (6 < rapport.MIN_VENTES_MEDIANE),
      f"n={b['n_comparables']} médiane={b['mediane_m2']}")
ann4 = {**ann, "cle": "inconnu"}
verif("immeuble sans vente -> pas de bloc", rapport._ventes_portail(c, ann4, date(2026, 10, 22)) is None)
st2 = SqliteStore(tmp / "t.db")
p2 = [{"cle": "k/y", "url": "https://y", "condo_name": "Immeuble Y", "ventes": lire_fazwaz(page(3))[0], "resume": {}}]
st2.enregistrer_ventes_portail("fazwaz", p2)
b2 = rapport._ventes_portail(sqlite3.connect(tmp / "t.db"), {**ann, "cle": "immeuble y"}, date(2026, 10, 22))
verif("3 ventes < 5 -> aucune médiane, ventes listées", b2["mediane_m2"] is None and len(b2["ventes"]) == 3)
b3 = rapport._ventes_portail(sqlite3.connect(tmp / "t.db"), {**ann, "cle": "immeuble x", "prix_m2": 150000.0},
                             date(2026, 10, 22))
verif("médiane présente quand n >= seuil", (b3["n_comparables"] >= rapport.MIN_VENTES_MEDIANE)
      == (b3["mediane_m2"] is not None))

print()
if echecs:
    print(f"{len(echecs)} ECHEC(S) : " + ", ".join(echecs))
    sys.exit(1)
print("Tous les controles executes sont passes.")
