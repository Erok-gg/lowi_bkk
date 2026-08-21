#!/usr/bin/env python
"""État des agents Lowi BKK, en JSON, pour le widget de bureau.

Lecture SEULE, en mode `ro` : le widget ne doit jamais verrouiller la base
pendant qu'un cycle écrit dedans. Aucune dépendance hors stdlib.

Reproduit exactement la cadence d'orchestrator.py :
  · `days_since_ok` = maintenant − dernier run de statut 'ok' (started_at, UTC)
  · `is_due`        = ce délai ≥ `every_days` de agents.json
Le widget se contente d'AFFICHER ce que l'orchestrateur déciderait ; il ne
recalcule pas de règle de son côté (une divergence donnerait un widget qui
ment). Le choix du prochain créneau réel appartient à collecte.ps1, qui seul
connaît l'heure de déclenchement de la tâche Windows.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEDGER = os.path.join(ROOT, "agents", "ledger.db")
REGISTRE = os.path.join(ROOT, "agents", "agents.json")


def connecte() -> sqlite3.Connection:
    """Ouverture read-only par URI : pas de création de fichier fantôme si la
    base manque, pas de verrou pris sur une base en cours d'écriture."""
    uri = "file:" + LEDGER.replace("\\", "/").replace("?", "%3f").replace("#", "%23")
    conn = sqlite3.connect(uri + "?mode=ro", uri=True, timeout=2.0)
    conn.row_factory = sqlite3.Row
    return conn


def iso_utc(txt: str | None) -> datetime | None:
    if not txt:
        return None
    try:
        d = datetime.fromisoformat(txt)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def main() -> None:
    sortie: dict = {"agents": [], "escalades": 0, "problemes": 0,
                    "problemes_detail": [], "constats_hauts": 0, "erreurs": []}

    try:
        registre = json.load(open(REGISTRE, encoding="utf-8"))
    except OSError as e:
        sortie["erreurs"].append(f"agents.json illisible : {e}")
        print(json.dumps(sortie, ensure_ascii=False))
        return

    try:
        conn = connecte()
    except sqlite3.Error as e:
        # Base absente ou corrompue : on rend quand même le registre, sans
        # dates. Un widget qui affiche « jamais vu » est plus utile qu'un vide.
        sortie["erreurs"].append(f"ledger.db : {e}")
        conn = None

    maintenant = datetime.now(timezone.utc)

    for spec in registre.get("agents", []):
        nom = spec["name"]
        every = spec.get("every_days", 1)
        dernier_ok = dernier_tout = statut = None

        if conn is not None:
            try:
                r = conn.execute(
                    "select started_at from agent_runs where agent=? and status='ok'"
                    " order by started_at desc limit 1", (nom,)).fetchone()
                dernier_ok = iso_utc(r["started_at"]) if r else None
                r = conn.execute(
                    "select started_at, status from agent_runs where agent=?"
                    " order by started_at desc limit 1", (nom,)).fetchone()
                if r:
                    dernier_tout, statut = iso_utc(r["started_at"]), r["status"]
            except sqlite3.Error as e:
                sortie["erreurs"].append(f"{nom} : {e}")

        jours = None if dernier_ok is None else (maintenant - dernier_ok).total_seconds() / 86400
        du = jours is None or jours >= every
        # Instant à partir duquel l'agent redevient dû. Sert à collecte.ps1 pour
        # choisir le premier déclenchement de la tâche Windows qui suivra.
        du_a_partir_de = maintenant if dernier_ok is None else dernier_ok + timedelta(days=every)

        sortie["agents"].append({
            "nom": nom,
            "tier": spec.get("tier", ""),
            "famille": spec.get("famille", ""),
            "lanes": spec.get("lanes", []),
            "every_days": every,
            "dernier_ok_utc": dernier_ok.isoformat() if dernier_ok else None,
            "dernier_run_utc": dernier_tout.isoformat() if dernier_tout else None,
            "dernier_statut": statut,
            "jours_depuis_ok": None if jours is None else round(jours, 2),
            "du": du,
            "du_a_partir_de_utc": du_a_partir_de.isoformat(),
        })

    if conn is not None:
        try:
            sortie["escalades"] = conn.execute(
                "select count(*) c from escalations where status='open'").fetchone()["c"]

            # PROBLÈMES DISTINCTS, pas occurrences. Mesuré le 2026-08-13 : 29
            # constats de sévérité haute sur 7 jours ne recouvrent que 4 vrais
            # sujets — `agent_muet` de l'overseer s'était répété 22 fois, une
            # par cycle. Afficher 29 ferait crier au loup (règle 2 du CLAUDE.md)
            # et le compteur cesserait d'être lu. On regroupe donc par
            # (agent, nature).
            # Le registre borne la requête : le ledger garde des traces
            # d'agents de test (_test_multi_then) qui ne sont plus au registre
            # et ne sont donc plus des problèmes à régler.
            noms = [a["nom"] for a in sortie["agents"]]
            depuis = (maintenant - timedelta(days=7)).isoformat()
            trous = ",".join("?" * len(noms)) or "''"
            sortie["problemes"] = conn.execute(
                "select count(*) c from (select distinct agent, kind from findings"
                f" where created_at >= ? and severity='high' and agent in ({trous}))",
                (depuis, *noms)).fetchone()["c"]
            sortie["problemes_detail"] = [
                f"{r['agent']} — {r['kind']} (x{r['n']})"
                for r in conn.execute(
                    "select agent, kind, count(*) n from findings"
                    f" where created_at >= ? and severity='high' and agent in ({trous})"
                    " group by agent, kind order by n desc", (depuis, *noms))]
            sortie["constats_hauts"] = conn.execute(
                "select count(*) c from findings where created_at >= ? and severity='high'",
                (depuis,)).fetchone()["c"]
        except sqlite3.Error as e:
            sortie["erreurs"].append(f"compteurs : {e}")
        conn.close()

    print(json.dumps(sortie, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:                                  # noqa: BLE001
        print(json.dumps({"agents": [], "escalades": 0, "problemes": 0,
                          "problemes_detail": [], "constats_hauts": 0,
                          "erreurs": [f"{type(e).__name__}: {e}"]}, ensure_ascii=False))
        sys.exit(0)
