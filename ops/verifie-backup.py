"""verifie-backup.py — vérifie l'INTÉGRITÉ du backup local avant de lancer un
cycle de scrap, et rattrape si besoin. Ne resynchronise PAS à l'aveugle à
chaque cycle (c'est ce que faisait l'ancien backup-avant-cycle,
inconditionnel) : on lit ce qui existe déjà, on ne relance
ops/sync_supabase_local.py QUE si quelque chose ne va pas.

CE QU'ON VÉRIFIE (voir agents/skills correspondant pour le contrat de sortie) :
  1. Le fichier archive/lowi-archive.db existe et s'ouvre sans corruption
     (PRAGMA integrity_check — pas juste "le fichier existe").
  2. Les tables attendues sont présentes et 'listings' n'est pas vide.
  3. Le volume archivé n'est pas très en retard sur le volume réel côté
     Supabase (ratio < 90 % = signal qu'une sync précédente s'est mal passée
     ou n'est jamais allée au bout).
  4. Le DERNIER run de backup-apres-cycle dans le ledger s'est bien terminé
     'ok', et pas trop vieux (plus de every_days+1 jours = un cycle a été
     manqué sans qu'on rattrape).

À DÉFAUT (n'importe lequel des points ci-dessus en échec) : on relance
ops/sync_supabase_local.py tout de suite, avant que l'extraction ne démarre —
un backup fait pendant CE cycle plutôt que d'attendre le suivant. On journalise
la raison du rattrapage (sévérité medium/high) : un rattrapage n'est jamais
silencieux, c'est un signal que le cycle précédent a eu un problème.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE = os.path.join(ROOT, "archive", "lowi-archive.db")
SYNC_SCRIPT = os.path.join(ROOT, "ops", "sync_supabase_local.py")
PY = os.path.join(ROOT, "scraper", ".venv", "Scripts", "python.exe")

# Liste de SECOURS uniquement : si Supabase est injoignable on retombe dessus.
# En marche normale les tables attendues sont celles que le SERVEUR expose —
# une liste figée ici avait le défaut qu'elle prétendait corriger : elle a
# déclaré « aucune table manquante » pendant des semaines alors que condos,
# cohort_snapshots et posted_at_history n'étaient pas archivées du tout
# (mesuré le 2026-08-20, même angle mort que SYNC_TABLES).
TABLES_SECOURS = ["listings", "listing_images", "listing_amenities",
                  "price_history", "scan_runs", "khet_snapshots", "pois"]
RATIO_MIN = 0.90        # archive.listings / supabase.listings en dessous -> rattrapage
CADENCE_JOURS = 4        # doit rester aligné sur backup-apres-cycle.every_days (agents.json)
MARGE_JOURS = 1          # tolérance avant de considérer un cycle manqué


def _sqlite_ok(tables_attendues: list[str]) -> tuple[bool, dict]:
    """Intégrité + comptes locaux. Ne lève jamais : une exception EST un
    échec d'intégrité, pas un bug à remonter."""
    import sqlite3
    detail: dict = {"fichier_existe": os.path.exists(ARCHIVE)}
    if not detail["fichier_existe"]:
        return False, detail
    try:
        conn = sqlite3.connect(f"file:{ARCHIVE.replace(chr(92), '/')}?mode=ro",
                               uri=True, timeout=5)
        detail["integrity_check"] = conn.execute("PRAGMA integrity_check").fetchone()[0]
        tables_presentes = {r[0] for r in conn.execute(
            "select name from sqlite_master where type='table'")}
        detail["tables_manquantes"] = [t for t in tables_attendues
                                       if t not in tables_presentes]
        detail["n_listings"] = (conn.execute("select count(*) from listings").fetchone()[0]
                                if "listings" in tables_presentes else 0)
        detail["mtime"] = os.path.getmtime(ARCHIVE)
        conn.close()
    except Exception as e:                                    # noqa: BLE001
        detail["exception"] = f"{type(e).__name__}: {e}"
        return False, detail
    ok = (detail.get("integrity_check") == "ok"
         and not detail["tables_manquantes"]
         and detail["n_listings"] > 0)
    return ok, detail


def _tables_supabase() -> list[str] | None:
    """Tables réellement exposées par le serveur. None si injoignable."""
    try:
        _charger_env()
        import psycopg
        dsn = os.environ.get("SUPABASE_DB_URL")
        if not dsn:
            return None
        with psycopg.connect(dsn, connect_timeout=10, autocommit=True) as c:
            return [r[0] for r in c.execute(
                "select table_name from information_schema.tables "
                "where table_schema='public' and table_type='BASE TABLE'")]
    except Exception:                                          # noqa: BLE001
        return None


def _charger_env() -> None:
    for line in open(os.path.join(ROOT, "scraper", ".env"), encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
    sys.path.insert(0, os.path.join(ROOT, "scraper"))


def _n_listings_supabase() -> int | None:
    try:
        for line in open(os.path.join(ROOT, "scraper", ".env"), encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
        sys.path.insert(0, os.path.join(ROOT, "scraper"))
        import psycopg
        dsn = os.environ.get("SUPABASE_DB_URL")
        if not dsn:
            return None
        with psycopg.connect(dsn, connect_timeout=10, autocommit=True) as c:
            return c.execute("select count(*) from listings").fetchone()[0]
    except Exception:                                          # noqa: BLE001
        return None


def _dernier_backup_apres_cycle() -> dict:
    """Lit le ledger directement (pas d'import circulaire avec orchestrator.py :
    ce script tourne aussi en dehors de l'orchestrateur, cf. __main__)."""
    import sqlite3
    p = os.path.join(ROOT, "agents", "ledger.db")
    if not os.path.exists(p):
        return {"trouve": False}
    try:
        conn = sqlite3.connect(f"file:{p.replace(chr(92), '/')}?mode=ro", uri=True, timeout=5)
        row = conn.execute(
            "select status, started_at, ended_at from agent_runs "
            "where agent='backup-apres-cycle' and status='ok' "
            "order by started_at desc limit 1").fetchone()
        conn.close()
    except Exception:                                          # noqa: BLE001
        return {"trouve": False}
    if not row:
        return {"trouve": False}
    started = datetime.fromisoformat(row[1])
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    age_jours = (datetime.now(timezone.utc) - started).total_seconds() / 86400
    return {"trouve": True, "started_at": row[1], "age_jours": age_jours}


def verifier() -> dict:
    tables_serveur = _tables_supabase()
    sqlite_ok, detail_sqlite = _sqlite_ok(tables_serveur or TABLES_SECOURS)
    detail_sqlite["tables_attendues_source"] = "serveur" if tables_serveur else "secours"
    n_live = _n_listings_supabase()
    n_archive = detail_sqlite.get("n_listings", 0)
    ratio = (n_archive / n_live) if (n_live and n_live > 0) else None
    volume_ok = ratio is None or ratio >= RATIO_MIN   # None (Supabase injoignable) -> on ne bloque pas dessus

    dernier = _dernier_backup_apres_cycle()
    cadence_ok = dernier.get("trouve") and dernier["age_jours"] <= (CADENCE_JOURS + MARGE_JOURS)

    rattrapage = not (sqlite_ok and volume_ok and cadence_ok)

    raisons = []
    if not detail_sqlite.get("fichier_existe"):
        raisons.append("archive introuvable")
    elif not sqlite_ok:
        raisons.append(f"integrite douteuse ({detail_sqlite})")
    if ratio is not None and not volume_ok:
        raisons.append(f"volume archive {n_archive} / live {n_live} = {ratio:.0%} < {RATIO_MIN:.0%}")
    if not cadence_ok:
        if not dernier.get("trouve"):
            raisons.append("aucun backup-apres-cycle 'ok' trouve dans le ledger")
        else:
            raisons.append(f"dernier backup-apres-cycle vieux de {dernier['age_jours']:.1f} j "
                          f"(> {CADENCE_JOURS + MARGE_JOURS} j)")

    resultat = {
        "sqlite_ok": sqlite_ok, "n_archive": n_archive, "n_live": n_live,
        "ratio": ratio, "cadence_ok": cadence_ok,
        "dernier_backup_apres_cycle": dernier,
        "rattrapage_necessaire": rattrapage, "raisons": raisons,
    }

    if rattrapage:
        code = subprocess.run([PY, SYNC_SCRIPT], cwd=ROOT).returncode
        resultat["rattrapage_execute"] = True
        resultat["rattrapage_code_retour"] = code
    else:
        resultat["rattrapage_execute"] = False

    return resultat


if __name__ == "__main__":
    r = verifier()
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
    # code retour non-zero si un rattrapage a ete necessaire ET a echoue --
    # sinon 0 (verification propre, ou rattrapage reussi).
    sys.exit(1 if (r["rattrapage_necessaire"] and r.get("rattrapage_code_retour", 1) != 0) else 0)
