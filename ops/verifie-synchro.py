"""verifie-synchro.py — les trois endroits disent-ils la même chose ?

POURQUOI CE SCRIPT EXISTE
Depuis le passage à deux postes (2026-08-21), l'état du projet vit à trois
endroits qui ne se synchronisent PAS entre eux, et c'est voulu :

    Supabase        les données. Vérité unique, lue par les deux PC.
    le COUREUR      ledger, state/, queue/, archive/. UN SEUL poste le détient.
    git             le code et les sorties (études, journal, audits).

Rien ne relie ces trois-là automatiquement. La question « tout est-il synchro ? »
n'a donc pas de réponse évidente, et trois pannes silencieuses sont possibles :
le cycle n'a pas tourné, il a tourné sans rien écrire en ligne, ou LES DEUX
machines ont scrapé en parallèle.

CE QU'IL VÉRIFIE, et pourquoi chacun compte
  1. Le cycle a tourné      — sinon rien d'autre n'a de sens.
  2. Supabase a reçu        — un cycle « ok » qui n'écrit rien est le pire cas :
                              vert au ledger, muet en base.
  3. Aucun double coureur   — croisement scan_runs × ledger local. Une écriture
                              en base sans run local correspondant vient d'une
                              AUTRE machine. C'est LE risque de la période de
                              bascule : deux PC qui scrapent les 5 mêmes sources.
  4. L'archive suit         — elle est la seule copie de ce que le serveur purge.
  5. git est poussé         — les sorties du coureur ne sont visibles de l'autre
                              poste que par GitHub. Un commit oublié = un PC qui
                              lit des études périmées sans le savoir.

LECTURE SEULE. N'écrit nulle part, ne répare rien.

Lancement :
    scraper\\.venv\\Scripts\\python.exe ops/verifie-synchro.py
    ... --jours 7      fenêtre d'examen (défaut : 5)
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "agents", "ledger.db")
ARCHIVE = os.path.join(ROOT, "archive", "lowi-archive.db")
QUEUE = os.path.join(ROOT, "agents", "queue")
SOURCES = ["fazwaz", "ddproperty", "propertyscout", "nestopa", "livinginsider"]

for _l in open(os.path.join(ROOT, "scraper", ".env"), encoding="utf-8"):
    _l = _l.strip()
    if _l and not _l.startswith("#") and "=" in _l:
        _k, _v = _l.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip())
sys.path.insert(0, os.path.join(ROOT, "scraper"))
import psycopg  # noqa: E402

OK, ALERTE, INFO = "  [ok] ", "  [!!] ", "  [--] "
anomalies: list[str] = []


def souci(msg: str) -> None:
    anomalies.append(msg)
    print(ALERTE + msg)


def titre(t: str) -> None:
    print(f"\n{t}\n" + "─" * 78)


def _dt(s):
    """Les timestamps du ledger sont des chaînes ISO en UTC."""
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Verification de synchro serveur / coureur / git")
    ap.add_argument("--jours", type=int, default=5)
    a = ap.parse_args()
    depuis = datetime.now(timezone.utc) - timedelta(days=a.jours)

    print(f"Fenêtre : {a.jours} derniers jours — depuis {depuis:%Y-%m-%d %H:%M} UTC")
    print(f"Poste   : {os.environ.get('COMPUTERNAME', '?')}")

    # ───────────────────────────── 1. le cycle a-t-il tourné ?
    titre("1. Cycle local (ledger)")
    if not os.path.exists(LEDGER):
        souci("ledger.db absent — ce poste n'est pas le coureur, ou l'import a échoué")
        runs = []
    else:
        led = sqlite3.connect(LEDGER)
        runs = led.execute(
            "select agent, started_at, ended_at, status from agent_runs "
            "where started_at >= ? order by started_at", (depuis.isoformat(),)).fetchall()
        print(f"{INFO}{len(runs)} run(s) sur la fenêtre")
        if not runs:
            souci("aucun run — la tâche LowiBKK-Agents ne s'est pas déclenchée")
        derniers = {}
        for ag, st, en, stt in runs:
            derniers[ag] = (st, stt)
        for ag, (st, stt) in sorted(derniers.items()):
            marque = OK if stt == "ok" else ALERTE
            print(f"{marque}{ag:24s} {str(st)[:16]}  {stt}")
            if stt not in ("ok",):
                anomalies.append(f"{ag} : dernier run en '{stt}'")

        hauts = led.execute(
            "select agent, subject, count(*) from findings "
            "where created_at >= ? and severity='high' group by agent, subject "
            "order by count(*) desc limit 5", (depuis.isoformat(),)).fetchall()
        if hauts:
            print(f"\n{INFO}constats de sévérité haute (sujets distincts) :")
            for ag, subj, n in hauts:
                print(f"       {n:3d}x  {ag} — {str(subj)[:60]}")

    # ───────────────────────────── 2. Supabase a-t-il reçu ?
    titre("2. Serveur Supabase")
    scans = []
    try:
        with psycopg.connect(os.environ["SUPABASE_DB_URL"], connect_timeout=30) as pg:
            c = pg.cursor()
            c.execute("select source, started_at, finished_at, scanned_count, new_count, "
                      "removed_count, changed_count from scan_runs where started_at >= %s "
                      "order by started_at", (depuis,))
            scans = c.fetchall()

            c.execute("select source, count(*), max(last_seen) from listings "
                      "where status='active' group by source order by count(*) desc")
            actives = c.fetchall()

        if not scans:
            print(f"{INFO}aucun scan_run sur la fenêtre "
                  f"(normal si aucun scrap n'était dû — cadence 4 jours)")
        else:
            par_source = {}
            for s in scans:
                par_source.setdefault(s[0], []).append(s)
            for src in sorted(par_source):
                lignes = par_source[src]
                tot = sum((x[4] or 0) for x in lignes)
                print(f"{OK}{src:16s} {len(lignes)} passe(s), "
                      f"{tot} nouvelle(s), dernière {lignes[-1][1]:%Y-%m-%d %H:%M}")

        print()
        total = sum(n for _, n, _ in actives)
        print(f"{INFO}{total} annonces actives en base :")
        maintenant = datetime.now(timezone.utc)
        for src, n, vu in actives:
            age = (maintenant - vu).days if vu else 999
            # Une source qui n'a pas été revue depuis > 2 cadences (8 j) est soit
            # cassée, soit plus scrapée. Le stock reste "actif" en base et
            # continue de peser sur les médianes : c'est une panne silencieuse.
            marque = OK if age <= 8 else ALERTE
            print(f"{marque}{src:16s} {n:6d} actives, vue il y a {age} j")
            if age > 8:
                anomalies.append(f"{src} : plus revue depuis {age} jours")
    except Exception as e:                                          # noqa: BLE001
        souci(f"Supabase injoignable : {type(e).__name__}: {e}")

    # ───────────────────────────── 3. deux coureurs ?
    titre("3. Double coureur (croisement scan_runs x ledger)")
    if not runs:
        print(f"{INFO}pas de ledger local exploitable — croisement impossible")
    elif not scans:
        print(f"{INFO}aucune écriture en base sur la fenêtre — rien à croiser")
    else:
        # Chaque scan_run doit tomber DANS la fenêtre d'un run d'extracteur local.
        # Sinon, quelqu'un d'autre a écrit : l'ancien poste, ou un lancement manuel.
        fenetres = []
        for ag, st, en, stt in runs:
            if not ag.startswith("extract-"):
                continue
            d, f = _dt(st), _dt(en) or datetime.now(timezone.utc)
            if d:
                fenetres.append((ag.replace("extract-", ""), d, f))
        orphelines = []
        for src, st, *_ in scans:
            couvert = any(s == src and d <= st <= f + timedelta(minutes=10)
                          for s, d, f in fenetres)
            if not couvert:
                orphelines.append((src, st))
        if orphelines:
            souci(f"{len(orphelines)} écriture(s) en base SANS run local correspondant")
            print("       Une autre machine écrit dans la même base, ou un lancement")
            print("       manuel a eu lieu. Vérifier que les tâches LowiBKK-* de")
            print("       l'ancien poste sont bien désactivées.")
            for src, st in orphelines[:8]:
                print(f"       {src:16s} {st:%Y-%m-%d %H:%M} UTC")
        else:
            print(f"{OK}toutes les écritures en base viennent de ce poste "
                  f"({len(scans)} passe(s) rapprochée(s) de {len(fenetres)} run(s))")

    # ───────────────────────────── 4. archive
    titre("4. Archive locale")
    if not os.path.exists(ARCHIVE):
        souci("archive/lowi-archive.db absente — elle est la seule copie de ce que "
              "le serveur purge au bout de 90 jours")
    else:
        mo = os.path.getsize(ARCHIVE) / 1048576
        try:
            ar = sqlite3.connect(f"file:{ARCHIVE}?mode=ro", uri=True)
            integre = ar.execute("pragma quick_check").fetchone()[0]
            n_arch = ar.execute("select count(*) from listings").fetchone()[0]
            ar.close()
            print(f"{OK if integre == 'ok' else ALERTE}intégrité : {integre} — "
                  f"{mo:.0f} Mo, {n_arch} annonces")
            if integre != "ok":
                anomalies.append("archive corrompue")
        except Exception as e:                                      # noqa: BLE001
            souci(f"archive illisible : {type(e).__name__}: {e}")

    # ───────────────────────────── 5. git
    titre("5. Dépôt git")

    def git(*args):
        return subprocess.run(["git", "-C", ROOT, *args], capture_output=True,
                              text=True, encoding="utf-8", errors="replace").stdout.strip()

    branche = git("branch", "--show-current")
    sale = git("status", "--short")
    print(f"{INFO}branche : {branche or '(détachée)'}")
    if sale:
        n = len(sale.splitlines())
        souci(f"{n} fichier(s) non commité(s) — les sorties du cycle ne sont pas "
              f"visibles de l'autre poste tant qu'elles ne sont pas poussées")
        for l in sale.splitlines()[:8]:
            print(f"       {l}")
    else:
        print(f"{OK}arbre propre")

    git("fetch", "origin", "--quiet")
    ecart = git("rev-list", "--left-right", "--count", f"origin/{branche}...HEAD")
    if ecart and "\t" in ecart:
        derriere, devant = ecart.split("\t")
        if int(devant):
            souci(f"{devant} commit(s) non poussé(s)")
        if int(derriere):
            print(f"{INFO}{derriere} commit(s) à récupérer (git pull)")
        if not int(devant) and not int(derriere):
            print(f"{OK}aligné sur origin/{branche}")

    # ───────────────────────────── file de tickets
    if os.path.isdir(QUEUE):
        tickets = [f for f in os.listdir(QUEUE) if f.endswith(".json")]
        comp = [t for t in tickets if "comparaison_deleguee" in t]
        print(f"\n{INFO}file de tickets : {len(tickets)} en attente"
              + (f", dont {len(comp)} de comparaison déléguée" if comp else ""))

    # ───────────────────────────── verdict
    titre("VERDICT")
    if anomalies:
        print(f"  {len(anomalies)} point(s) à regarder :")
        for x in anomalies:
            print(f"   · {x}")
        return 1
    print("  Les trois endroits concordent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
