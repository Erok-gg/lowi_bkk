"""orchestrator.py — POINT D'ENTRÉE UNIQUE du système d'agents.

Remplace les trois tâches Windows (LowiBKK-ScrapVente / ScrapLocation /
ArchiveSync) qui n'ont jamais tourné : leur XML contenait des guillemets
échappés littéraux, PowerShell recevait un chemin introuvable et sortait avant
la première ligne. Preuve : ops/logs/ n'a jamais existé.

La leçon retenue ici : une seule tâche, et le rattrapage se calcule depuis le
LEDGER (« quand cet agent a-t-il réussi pour la dernière fois ? ») plutôt que de
dépendre de StartWhenAvailable — qui ne rattrape rien quand c'est la tâche
elle-même qui est cassée.

Usage :
    python agents/orchestrator.py status
    python agents/orchestrator.py due
    python agents/orchestrator.py run <agent> [--dry-run] [--lane sale]
    python agents/orchestrator.py run-lane <sale|rent|weekly> [--dry-run]
    python agents/orchestrator.py --due            # ce que la tâche planifiée appelle
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(ROOT)
sys.path.insert(0, PROJECT)

from agents.core import alert, shell                      # noqa: E402
from agents.core.ledger import Ledger                     # noqa: E402

REGISTRY = json.load(open(os.path.join(ROOT, "agents.json"), encoding="utf-8"))
AGENTS = {a["name"]: a for a in REGISTRY["agents"]}


# ───────────────────────── cadence ─────────────────────────
def days_since_ok(led: Ledger, name: str) -> float | None:
    row = led.last_run(name, only_ok=True)
    if not row:
        return None
    then = datetime.fromisoformat(row["started_at"])
    return (datetime.now(timezone.utc) - then).total_seconds() / 86400


def is_due(led: Ledger, spec: dict) -> tuple[bool, str]:
    d = days_since_ok(led, spec["name"])
    if d is None:
        return True, "jamais exécuté"
    every = spec.get("every_days", 1)
    if d >= every:
        return True, f"{d:.1f} j depuis le dernier succès (cadence {every} j)"
    return False, f"à jour ({d:.1f} j / {every} j)"


def current_lane() -> str:
    """Vente ET location le même jour (2026-08-06 : l'ancienne alternance vente/
    location sur des jours différents retardait chaque catégorie de 4 jours
    supplémentaires pour rien — chaque source enchaîne maintenant sale PUIS
    rent elle-même, cf. agents.json 'then'). "weekly" reste une cadence à part
    (archivage + purge + sondage de nouvelles sources)."""
    day = datetime.now(timezone.utc).toordinal()
    return "weekly" if day % 7 == 0 else "daily"


# ───────────────────────── exécution ─────────────────────────
def localiser(cmd: list[str]) -> list[str]:
    """Bascule une commande vers le store LOCAL. Utilisé par le mode --local :
    on valide un cycle complet sans écrire une ligne dans Supabase."""
    out, i = [], 0
    while i < len(cmd):
        if cmd[i] == "--store" and i + 1 < len(cmd):
            out += ["--store", "sqlite"]
            i += 2
            continue
        out.append(cmd[i])
        i += 1
    return out


def run_agent(led: Ledger, name: str, lane: str | None = None,
              dry: bool = False, local: str | None = None) -> bool:
    spec = AGENTS.get(name)
    if spec is None:
        print(f"  ! agent inconnu : {name}")
        return False

    # Mode local : les agents qui LISENT Supabase analyseraient la production
    # et non le scrap de test. Les sauter est la seule lecture honnête.
    if local and spec.get("needs_supabase"):
        print(f"  ⏭ {name} sauté — lit Supabase, hors périmètre d'un test local")
        return True

    lane = lane or current_lane()

    # garde-fou : un agent déjà en cours ne se relance pas. Les runs zombies
    # (processus tué) sont refermés par Ledger.reap_stale() au démarrage, donc un
    # 'running' encore présent ici est bien une exécution vivante.
    encours = led.last_run(name)
    if encours is not None and encours["status"] == "running":
        print(f"  ⏸ {name} déjà en cours depuis {encours['started_at'][11:19]} — non relancé")
        return False

    # garde-fou : ne jamais purger derrière un cycle douteux
    for dep in spec.get("requires_healthy", []):
        row = led.last_run(dep)
        if row is None or row["status"] != "ok":
            msg = f"{name} sauté — {dep} n'a pas de dernier run 'ok'"
            print(f"  ⏸ {msg}")
            led.finding(name, "medium", "garde_fou", msg)
            alert.log(name, "medium", msg)
            return False

    if dry:
        if "module" in spec:
            what = spec["module"]
        else:
            base = localiser(spec["cmd"]) if local else spec["cmd"]
            what = " ".join(base)
            for extra in spec.get("then", []):
                e = localiser(extra) if local else extra
                what += "\n         puis → " + " ".join(e)
        print(f"  [dry] {name} ({spec['tier']}) → {what}")
        return True

    log = shell.log_path(name)
    run_id = led.start_run(name, spec["tier"], lane, log)
    # LOWI_OUTPUT_DIR redirige base SQLite, images et fiches vers le dossier de test.
    env_local = {"LOWI_OUTPUT_DIR": local} if local else None
    print(f"  ▶ {name} ({spec['tier']}, lane={lane}{', LOCAL' if local else ''})")

    try:
        if "module" in spec:
            mod = importlib.import_module(spec["module"])
            metrics = mod.run(led=led, run_id=run_id, lane=lane, spec=spec) or {}
            code = 0
        else:
            # Chaque étape (cmd principal + tous les 'then') s'exécute même si
            # une précédente a échoué : un échec sur la passe vente ne doit pas
            # empêcher la passe location d'être tentée, ce sont deux catégories
            # indépendantes sur le même site. Le statut global agrège TOUTES
            # les étapes — avant ce correctif (2026-08-06), seul le code retour
            # du cmd principal comptait et un 'then' raté passait pour 'ok'.
            etapes = [("principal", spec["cmd"])] + \
                     [(f"then_{i}", e) for i, e in enumerate(spec.get("then", []))]
            metrics = {"etapes": []}
            code = 0
            for label, brute in etapes:
                c = localiser(brute) if local else brute
                lg = log if label == "principal" else f"{log}.{label}"
                c_code, out = shell.run(c, log=lg, env_extra=env_local)
                m = shell.metrics_from_output(out)
                metrics["etapes"].append({"etape": label, "exit": c_code, **m})
                if c_code != 0:
                    code = c_code   # code final = dernier echec rencontre
    except Exception as e:                                   # noqa: BLE001
        led.end_run(run_id, "failed", 1, {"exception": f"{type(e).__name__}: {e}"})
        led.finding(name, "high", "exception", f"{name} a levé {type(e).__name__}",
                    {"message": str(e)[:500]}, run_id)
        alert.alert(name, f"{name} a échoué ({type(e).__name__})", str(e)[:1500])
        print(f"  ✗ {name} — {type(e).__name__}: {e}")
        return False

    status = "ok" if code == 0 else "failed"
    led.end_run(run_id, status, code, metrics)
    alert.log(name, "info" if status == "ok" else "high",
              f"{status} — {json.dumps(metrics, ensure_ascii=False)[:200]}")
    if status == "failed":
        alert.alert(name, f"{name} a échoué (code {code})",
                    f"Log : {log}\nMétriques : {json.dumps(metrics, ensure_ascii=False)}")
    print(f"  {'✓' if status == 'ok' else '✗'} {name} — code={code} {metrics}")
    return status == "ok"


def run_lane(led: Ledger, lane: str, dry: bool = False, only_due: bool = True,
             local: str | None = None, parallele: bool = True) -> None:
    mode = f" — LOCAL → {local}" if local else ""
    print(f"\n═══ Lane « {lane} » — {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC{mode} ═══")
    ordered = [a for a in REGISTRY["agents"] if lane in a.get("lanes", [])]
    # l'overseer relit le cycle : toujours en dernier
    ordered.sort(key=lambda a: a["name"] == "overseer")

    a_lancer = []
    for spec in ordered:
        due, why = is_due(led, spec)
        if only_due and not due:
            print(f"  · {spec['name']} — {why}")
            continue
        a_lancer.append(spec)

    # PRELUDE : avant toute extraction, séquentiel. Sert au backup local
    # (ops/sync_supabase_local.py, agent backup-avant-cycle) — un point de
    # retour en arrière pris juste avant que le cycle ne touche la base.
    # Ne DOIT PAS tourner en parallèle des extracteurs ni entre agents Prelude
    # eux-mêmes : c'est un point de repère, pas un travail concurrent.
    prelude = [s for s in a_lancer if s.get("famille") == "Prelude"]
    for spec in prelude:
        run_agent(led, spec["name"], lane, dry, local)

    # Les EXTRACTEURS visent quatre DOMAINES DIFFÉRENTS : les lancer ensemble ne
    # change rien à la cadence vue par chaque site — le rate-limit est par
    # Fetcher, donc par source. Le temps de cycle tombe à celui de la source la
    # plus lourde au lieu de la somme (mesuré : 31 h → ~16 h).
    # Tout le reste (analyse, organisation, audit) reste séquentiel : ces agents
    # lisent l'état laissé par les extracteurs.
    extracteurs = [s for s in a_lancer if s.get("famille") == "Extraction"]
    suite = [s for s in a_lancer if s.get("famille") not in ("Extraction", "Prelude")]

    if extracteurs and not dry and parallele and len(extracteurs) > 1:
        print(f"  ⇉ {len(extracteurs)} extracteurs en parallèle "
              f"({', '.join(s['name'] for s in extracteurs)})")
        with ThreadPoolExecutor(max_workers=len(extracteurs)) as ex:
            futurs = {ex.submit(run_agent, led, s["name"], lane, False, local): s
                      for s in extracteurs}
            for f in as_completed(futurs):
                nom = futurs[f]["name"]
                try:
                    f.result()
                except Exception as e:                      # noqa: BLE001
                    print(f"  ✗ {nom} — {type(e).__name__}: {e}")
    else:
        for spec in extracteurs:
            run_agent(led, spec["name"], lane, dry, local)

    for spec in suite:
        run_agent(led, spec["name"], lane, dry, local)


# ───────────────────────── commandes ─────────────────────────
def cmd_status(led: Ledger) -> None:
    print(f"Lane du jour : {current_lane()}")
    from agents.core import local_llm
    ok, msg = local_llm.health()
    print(f"Modèle local : {'✓' if ok else '✗'} {msg}")
    opened = led.open_escalations()
    print(f"Escalades ouvertes : {len(opened)}")
    for e in opened[:5]:
        print(f"   · [{e['severity']}] {e['agent']} — {e['kind']} ({e['created_at']})")

    print(f"\n{'agent':24s} {'tier':5s} {'cadence':8s} {'dernier succès':22s} statut")
    print("─" * 88)
    for spec in REGISTRY["agents"]:
        d = days_since_ok(led, spec["name"])
        last = "jamais" if d is None else f"il y a {d:.1f} j"
        due, why = is_due(led, spec)
        print(f"{spec['name']:24s} {spec['tier']:5s} "
              f"{str(spec.get('every_days', 1)) + ' j':8s} {last:22s} "
              f"{'DÛ' if due else 'à jour'}")

    hi = led.findings_since(
        (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(), "high")
    if hi:
        print(f"\n⚠ {len(hi)} constat(s) de sévérité haute sur 7 jours :")
        for f in hi[:8]:
            print(f"   · {f['created_at'][:16]} {f['agent']}: {f['subject']}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Orchestrateur des agents Lowi BKK")
    ap.add_argument("command", nargs="?", default="status",
                    choices=["status", "due", "run", "run-lane"])
    ap.add_argument("target", nargs="?", help="nom d'agent, ou lane")
    ap.add_argument("--lane", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--due", action="store_true",
                    help="mode tâche planifiée : lance la lane du jour, agents dus seulement")
    ap.add_argument("--all", action="store_true", help="ignore la cadence")
    ap.add_argument("--local", metavar="DOSSIER", default=None,
                    help="scrap vers un store SQLite isolé (aucune écriture Supabase) ; "
                         "les agents qui lisent Supabase sont sautés")
    a = ap.parse_args()

    if a.local:
        a.local = os.path.abspath(a.local)
        os.makedirs(a.local, exist_ok=True)

    led = Ledger()
    try:
        if a.due:
            run_lane(led, current_lane(), a.dry_run, only_due=True, local=a.local)
        elif a.command == "status":
            cmd_status(led)
        elif a.command == "due":
            for spec in REGISTRY["agents"]:
                due, why = is_due(led, spec)
                if due:
                    print(f"{spec['name']:24s} {why}")
        elif a.command == "run":
            if not a.target:
                ap.error("run demande un nom d'agent")
            run_agent(led, a.target, a.lane, a.dry_run, a.local)
        elif a.command == "run-lane":
            if not a.target:
                ap.error("run-lane demande sale|rent|weekly")
            run_lane(led, a.target, a.dry_run, only_due=not a.all, local=a.local)
    finally:
        led.close()


if __name__ == "__main__":
    main()
