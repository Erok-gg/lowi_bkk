"""test_courtiers.py — noms des agents immobiliers (table `courtiers`) et vue
`courtiers_stats`.

POURQUOI CE TEST EXISTE
Demande du 2026-10-17 : nommer les agents et tenir des statistiques sur eux.
Sonde du jour sur UNE page DDproperty de 20 annonces : un même `agent_id`
s'affiche sous plusieurs noms (« Hometoday789 » / son nom thaï ; « NR AGENT » /
« NR agent »), avec une URL de profil dont le slug suit le nom. La première
version écrasait le nom à chaque passage : 4 réécritures sur 20 annonces au
2e passage, au lieu de 0 — et `noter_courtier` est appelé pour CHAQUE annonce de
CHAQUE page de scan.

CE QUI EST VÉRIFIÉ, sans réseau (SQLite en fichier temporaire) :
  1. le premier nom reste `nom`, les suivants vont dans `alias` (sans casse) ;
  2. un 2e passage identique n'écrit RIEN (total_changes inchangé) ;
  3. l'URL de profil reste la première vue ;
  4. réouvrir la base ne réécrit pas le schéma (schema_version stable) — sinon
     chaque lancement d'agent ferait redémarrer une copie par l'API `backup` ;
  5. la vue compte annonces / actives / délistées / ventes et donne les
     secteurs dominants, y compris pour un agent jamais nommé ;
  6. une donnée inattendue ne lève pas d'exception (l'annonce serait sautée).

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_courtiers.py
"""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scraper"))

from store.sqlite_store import SqliteStore  # noqa: E402

tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
tmp.close()
db_path = Path(tmp.name)
echecs = []


def verifie(cond, libelle):
    print(("  ok   " if cond else "  ECHEC ") + libelle)
    if not cond:
        echecs.append(libelle)


try:
    store = SqliteStore(db_path)
    db = store.db

    def stub(nom, url):
        return {"agent_id": "A1", "agent_name": nom, "agency_id": "G1",
                "agency_name": "Agence 1", "lister_type": "agent",
                "agent_profile_url": url}

    store.noter_courtier("ddproperty", stub("Hometoday789", "/en/agent/hometoday789-A1"))
    store.noter_courtier("ddproperty", stub("ดลภัทร", "/en/agent/ดลภัทร-A1"))
    store.noter_courtier("ddproperty", stub("HOMETODAY789", "/en/agent/hometoday789-A1"))
    r = db.execute("select * from courtiers where agent_id='A1'").fetchone()
    verifie(r["nom"] == "Hometoday789" and r["alias"] == "ดลภัทร",
            f"1er nom conservé, alias accumulé sans casse ({r['nom']!r} / {r['alias']!r})")
    verifie(r["profil_url"] == "/en/agent/hometoday789-A1", "URL de profil = la première vue")

    avant = db.total_changes
    for n, u in (("Hometoday789", "/en/agent/hometoday789-A1"), ("ดลภัทร", "/en/agent/ดลภัทร-A1")):
        store.noter_courtier("ddproperty", stub(n, u))
    verifie(db.total_changes == avant, "2e passage identique : aucune écriture")

    store.noter_courtier("ddproperty", {"agent_id": "A1", "agent_name": 123})
    verifie(True, "donnée inattendue absorbée sans exception")

    # annonces : A1 nommé (2 actives vente Vadhana, 1 délistée), A2 jamais nommé
    for i, (aid, st, deal, khet, uk) in enumerate([
            ("A1", "active", "sale", "Vadhana", "u1"), ("A1", "active", "sale", "Vadhana", "u1"),
            ("A1", "inactive", "sale", "Khlong Toei", "u2"), ("A2", "active", "rent", "Bang Na", "u3")]):
        db.execute("insert into listings (id, source, source_url, deal_type, status, khet,"
                   " unit_key, agent_id, first_seen, last_seen) values (?,?,?,?,?,?,?,?,?,?)",
                   (f"L{i}", "ddproperty", "u", deal, st, khet, uk, aid, "2026-10-01", "2026-10-17"))
    db.commit()
    v = {r["agent_id"]: r for r in db.execute("select * from courtiers_stats")}
    a1, a2 = v.get("A1"), v.get("A2")
    verifie(a1 is not None and (a1["annonces"], a1["biens"], a1["actives"], a1["delistees"],
                                a1["ventes_actives"]) == (3, 2, 2, 1, 2),
            "A1 : 3 annonces, 2 biens, 2 actives, 1 délistée, 2 ventes actives")
    verifie(a1 is not None and a1["secteurs_probables"] == "Vadhana (67 %), Khlong Toei (33 %)",
            f"A1 : secteurs dominants ({a1['secteurs_probables'] if a1 else None!r})")
    verifie(a2 is not None and a2["nom"] is None and a2["locations_actives"] == 1,
            "A2 jamais nommé : compté quand même")

    store.close()
    v1 = sqlite3.connect(db_path).execute("pragma schema_version").fetchone()[0]
    SqliteStore(db_path).close()
    v2 = sqlite3.connect(db_path).execute("pragma schema_version").fetchone()[0]
    verifie(v1 == v2, f"réouverture sans réécriture de schéma ({v1} -> {v2})")
finally:
    try:
        db_path.unlink()
    except OSError:
        pass

print("\nTous les contrôles sont passés." if not echecs else f"\n{len(echecs)} ÉCHEC(S).")
sys.exit(1 if echecs else 0)
