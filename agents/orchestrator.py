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
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone

# Lancé à la main dans une console cp1252 (ACP par défaut sur ce poste), les
# caractères ✓/✗ de cmd_status/run_lane plantent en UnicodeEncodeError.
# Connu depuis le 2026-08-22 (journal technique) pour tout script lancé hors
# sous-processus — shell.py force déjà l'UTF-8 pour les ENFANTS, rien ne le
# faisait pour ce process-ci quand on l'appelle directement.
for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(ROOT)
sys.path.insert(0, PROJECT)

from agents.core import alert, escalation, shell           # noqa: E402
from agents.core.metrics import aplatir                    # noqa: E402
from agents.core.ledger import Ledger                     # noqa: E402


class Tee:
    """Duplique l'écriture vers un fichier ET la console d'origine.

    Sous la tâche planifiée, sys.stdout n'a pas de console attachée : ses
    écritures partent dans le vide (même défaut que shell.py documentait déjà
    côté sous-processus avant le correctif du 2026-08-22, jamais posé côté
    process orchestrateur lui-même). Constaté le 2026-09-12 : extract-
    livinginsider absent d'un cycle sans aucune trace du print()/exception qui
    l'aurait expliqué — la piste s'arrêtait net, root-cause non mesurable.
    Ce tee écrit TOUJOURS dans le fichier ; la console d'origine reste en
    best-effort (une écriture cassée dessus ne doit jamais faire planter le
    cycle réel)."""

    def __init__(self, original, fichier):
        self._original = original
        self._fichier = fichier

    def write(self, s: str) -> int:
        try:
            self._original.write(s)
        except Exception:                                   # noqa: BLE001
            pass
        return self._fichier.write(s)

    def flush(self) -> None:
        try:
            self._original.flush()
        except Exception:                                   # noqa: BLE001
            pass
        self._fichier.flush()

#: Marqueur émis par scraper/run.py quand la sonde de structure (page 1)
#: échoue AVANT le scan complet — voir scraper/adapters/base.py:sonder().
#: Repris ici pour escalader tout de suite, sans attendre watch-health (qui
#: reste à sa place normale, en fin de cycle, et n'escalade qu'après 2 runs
#: consécutifs à zéro — jusqu'à 8 j de scans pour rien sinon).
SONDE_ECHEC_RE = re.compile(r"^\[SONDE-ECHEC\] (\S+) : (.+)$", re.M)

#: Marqueur émis par scraper/pipeline/fetch.py + scraper/run.py quand une
#: coupure réseau a duré plus longtemps que l'attente inline (20 min, voir
#: Fetcher._attend_coupure) : le scan s'est arrêté au milieu, pas délisté
#: (garde-fou dans run.py), mais forcément incomplet. Contrairement à
#: SONDE_ECHEC_RE (qui bloque avant même de commencer), ceci arrive APRÈS un
#: scan partiellement fait — le run reste "ok" (le script n'a pas planté),
#: mais is_due() ne doit pas le compter comme la réussite du jour, sinon la
#: source attend sa cadence normale (demain) au lieu d'être reprise au
#: prochain déclenchement de l'orchestrateur (nuit suivante ou
#: LowiBKK-RattrapageBoot au prochain logon).
COUPURE_RESEAU_RE = re.compile(r"^\[COUPURE-RESEAU\] (\S+) : (.+)$", re.M)

#: Signature d'une panne RÉSEAU dans la sortie d'un scan. Sert à ne pas
#: confondre « le site a changé » et « on n'a pas pu joindre le site » —
#: distinction que la sonde elle-même ne peut pas faire (elle ne voit qu'une
#: page vide), mais que la trace de l'exception, elle, porte noir sur blanc.
RESEAU_RE = re.compile(
    r"NameResolutionError|getaddrinfo failed|Max retries exceeded|"
    r"ConnectionError|Connection refused|Temporary failure in name resolution",
    re.I)

#: Agents longs qu'un second cycle ne doit pas relancer par-dessus, SANS être
#: de la famille Extraction. Ajouté le 2026-08-26 avec `remonter-supabase` :
#: la remontée dure ~4 h 20 (débit mesuré 4,1 annonces/s sur 53 258), ce qui
#: allonge le cycle de 7 h 15 à ~11 h 35 et le fait déborder sur la journée.
#: `LowiBKK-RattrapageBoot` part au logon : sans cette liste, un logon à 09:00
#: tombait dans la fenêtre de remontée, ne voyait aucun extracteur en vol, et
#: relançait une lane par-dessus. Le verrou d'instance de `remonter-local.py`
#: aurait protégé la DONNÉE (il lève une RuntimeError, il ne bloque pas), mais
#: au prix d'un agent en échec dans le ledger — soit une alerte pour un
#: fonctionnement normal, exactement ce que la règle 2 interdit.
LONGS_A_NE_PAS_COUPER = {"remonter-supabase"}

REGISTRY = json.load(open(os.path.join(ROOT, "agents.json"), encoding="utf-8"))
AGENTS = {a["name"]: a for a in REGISTRY["agents"]}


# ───────────────────────── cadence ─────────────────────────
def jour_local(iso: str) -> date:
    """Date LOCALE d'un horodatage du ledger (stocké en UTC).

    Le fuseau du poste est le fuseau de référence de la cadence : le cycle part
    à 01:00 à Bangkok, soit 18:00 la VEILLE en UTC. Compter en UTC décalerait le
    calendrier d'un jour — même piège que `current_lane()` et le widget."""
    t = datetime.fromisoformat(iso)
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone().date()


def days_since_ok(led: Ledger, name: str) -> float | None:
    """Heures écoulées depuis le dernier succès, en jours décimaux. Sert au
    DIAGNOSTIC affiché, plus à la décision — cf. is_due()."""
    row = led.last_run(name, only_ok=True)
    if not row:
        return None
    then = datetime.fromisoformat(row["started_at"])
    return (datetime.now(timezone.utc) - then).total_seconds() / 86400


def is_due(led: Ledger, spec: dict) -> tuple[bool, str]:
    """Cadence en JOURS CALENDAIRES LOCAUX, pas en heures écoulées.

    Corrigé le 2026-08-25. `every_days: 1` veut dire « tous les jours, au
    créneau de 01:00 » ; la comparaison en heures écoulées en faisait « au moins
    24 h après le DÉPART du dernier succès ». Dès qu'un cycle glissait dans la
    journée — rattrapage au logon, coupure réseau, lancement à la main — le
    01:00 suivant tombait sous les 24 h et TOUT était sauté : une nuit sur deux
    perdue, sans qu'aucune alerte ne se déclenche (le cycle se terminait
    « normalement », simplement vide).

    Mesuré ce jour-là : cycle parti à 08:24 faute de réveil, extracteurs à
    10:00 ; à 01:00 la nuit suivante il ne s'était écoulé que 0,6 j et les 12
    agents de la lane se déclaraient « à jour ». Aucun scrap.

    En jours calendaires, un succès daté d'HIER rend l'agent dû AUJOURD'HUI
    quelle que soit l'heure — ce qui est la définition de « tous les jours ».
    Le pendant de ce choix est le garde-fou `scrap_en_cours()` : c'est lui, et
    non la cadence, qui empêche de repartir sur un scrap encore en vol."""
    row = led.last_run(spec["name"], only_ok=True)
    if row is None:
        return True, "jamais exécuté"
    every = spec.get("every_days", 1)
    ecart = (datetime.now().date() - jour_local(row["started_at"])).days
    h = (days_since_ok(led, spec["name"]) or 0) * 24
    if ecart >= every:
        return True, (f"dernier succès il y a {ecart} j calendaire(s) "
                      f"(cadence {every} j — {h:.0f} h)")
    # Le dernier run "ok" est peut-être un scan coupé en vol par une coupure
    # réseau (COUPURE_RESEAU_RE, cf. plus haut) : le script n'a pas planté
    # (status='ok'), mais il n'a pas vu tout ce qu'un cycle normal aurait vu.
    # Sans ce contrôle, la source attendrait sa cadence normale (demain) au
    # lieu d'être reprise au prochain déclenchement — exactement le manque
    # relevé le 2026-09-04 : ops/superviseur.py (2026-08-01) le faisait par
    # sondage externe toutes les 30 min, capacité perdue au passage au
    # système d'agents (2026-07-31) et jamais remplacée jusqu'ici.
    try:
        if json.loads(row["metrics"] or "{}").get("coupure_reseau"):
            return True, "dernier succès coupé par une coupure réseau — reprise immédiate"
    except (json.JSONDecodeError, TypeError):
        pass
    return False, f"à jour ({ecart} j / {every} j — dernier succès il y a {h:.0f} h)"


def scrap_en_cours(led: Ledger) -> str | None:
    """Un scrap tourne-t-il DÉJÀ ? Rend sa description, ou None.

    C'est la contrepartie de la cadence en jours calendaires (cf. is_due) :
    « tous les jours à 01:00 » ne doit jamais vouloir dire « quitte à couper
    celui d'hier ». Un extracteur tué en vol est pire qu'un cycle manqué — la
    passe `--full` en cours n'a vu qu'une partie du site, et ce qu'elle n'a pas
    revu, le diff le compte comme délisté. On perdrait des annonces vivantes.

    Deux sondes, par ordre de fiabilité :

    1. LE LEDGER — un run de famille Extraction resté `running` dont le PID vit
       encore. Couvre le cas qui compte : le cycle précédent n'a pas fini. Les
       runs orphelins (process tué) sont déjà refermés en `interrompu` par le
       nettoyage d'ouverture du ledger, donc ne font pas de faux positif.
    2. LES LIGNES DE COMMANDE du poste — un `scraper/run.py` ou
       `scraper/recense.py` lancé à la main, que le ledger ne connaît pas.
       Coûte ~1 s, une fois par cycle. **En cas d'échec de la sonde on laisse
       passer, en le disant** : bloquer un cycle entier sur un hoquet de
       PowerShell serait un garde-fou pire que le défaut (règle 2)."""
    moi = os.getpid()
    for r in led.conn.execute(
            "select agent, started_at, pid from agent_runs where status='running'"):
        spec = AGENTS.get(r["agent"], {})
        if spec.get("famille") != "Extraction" and r["agent"] not in LONGS_A_NE_PAS_COUPER:
            continue
        if r["pid"] and int(r["pid"]) != moi and led._processus_vivant(r["pid"]):
            return (f"{r['agent']} tourne encore (démarré {r['started_at']}, "
                    f"PID {r['pid']}) — ledger")

    try:
        import subprocess
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
             "ForEach-Object { \"$($_.ProcessId)|$($_.CommandLine)\" }"],
            capture_output=True, text=True, timeout=25).stdout
    except Exception as e:                                  # noqa: BLE001
        print(f"  ⚠ sonde « scrap manuel » indisponible ({type(e).__name__}) — "
              f"on ne bloque pas le cycle sur ça")
        return None

    for ligne in out.splitlines():
        pid, _, cmd = ligne.partition("|")
        bas = cmd.replace("\\", "/").lower()
        if not pid.strip().isdigit() or int(pid) == moi:
            continue
        if ("scraper/run.py" in bas or "scraper/recense.py" in bas
                or "ops/remonter-local.py" in bas):
            return f"scrap lancé hors cycle : PID {pid.strip()} — {cmd.strip()[:110]}"
    return None


def ouvre_dashboard(led: Ledger) -> None:
    """Affiche `ops/dashboard.py` pour toute la durée du scrap.

    Demandé le 2026-08-25 : « tant que le scrap n'est pas terminé, je veux que
    le dashboard soit affiché ». La fenêtre n'est PAS refermée à la fin — le
    dashboard bascule alors de lui-même sur le résultat du cycle, qui est
    justement ce qu'on vient lire le matin.

    Ne fait rien si une fenêtre est déjà ouverte (témoin `agents/state/
    dashboard.pid`, posé par le dashboard, relu ici) : sans ça, un cycle par
    nuit finirait par empiler autant de fenêtres que de nuits. Le témoin d'un
    dashboard fermé de force (session tuée) reste sur le disque : on vérifie
    donc que le PID VIT, on ne se fie pas à la seule présence du fichier."""
    temoin = os.path.join(PROJECT, "agents", "state", "dashboard.pid")
    try:
        if os.path.exists(temoin):
            pid = int(open(temoin, encoding="utf-8").read().strip() or 0)
            if pid and led._processus_vivant(pid):
                print(f"  ▤ dashboard déjà ouvert (PID {pid})")
                return
    except (OSError, ValueError):
        pass

    pyw = os.path.join(PROJECT, "scraper", ".venv", "Scripts", "pythonw.exe")
    script = os.path.join(PROJECT, "ops", "dashboard.py")
    if not (os.path.exists(pyw) and os.path.exists(script)):
        print("  ⚠ dashboard introuvable — le cycle continue sans")
        return
    try:
        import subprocess
        # DETACHED_PROCESS : le dashboard doit SURVIVRE à l'orchestrateur, sinon
        # il disparaîtrait juste au moment où il affiche le résultat du cycle.
        subprocess.Popen([pyw, script], cwd=PROJECT,
                         creationflags=0x00000008 | 0x00000200)
        print("  ▤ dashboard ouvert (suivi du scrap)")
    except Exception as e:                                  # noqa: BLE001
        print(f"  ⚠ dashboard non lancé ({type(e).__name__}: {e}) — sans effet sur le cycle")


def current_lane() -> str:
    """Vente ET location le même jour (2026-08-06 : l'ancienne alternance vente/
    location sur des jours différents retardait chaque catégorie de 4 jours
    supplémentaires pour rien — chaque source enchaîne maintenant sale PUIS
    rent elle-même, cf. agents.json 'then'). "weekly" reste une cadence à part
    (archivage + purge + sondage de nouvelles sources).

    ⚠ JOUR LOCAL, PAS UTC. Corrigé le 2026-08-25 : le cycle part à 01:00 à
    Bangkok, soit 18:00 la VEILLE en UTC. Le calendrier hebdomadaire était donc
    décalé d'un jour, et le cycle du 2026-08-24 — le premier de la cadence
    quotidienne — a été classé « weekly » et n'a lancé AUCUN extracteur. Même
    piège que celui déjà documenté pour le widget de bureau."""
    day = datetime.now().toordinal()
    return "weekly" if day % 7 == 0 else "daily"


def lanes_actives(lane: str) -> set[str]:
    """Agents concernés par la lane du jour.

    LE JOUR HEBDOMADAIRE S'AJOUTE AU QUOTIDIEN, il ne le remplace pas. Corrigé
    le 2026-08-25 : `weekly` ne sélectionnait que les agents portant ce mot,
    donc ni extraction ni analyse ni sauvegarde un jour sur sept. Invisible tant
    que l'extraction tournait tous les 4 jours (elle repartait la nuit
    suivante) ; avec la cadence quotidienne du 2026-08-23, c'est une journée de
    marché perdue chaque semaine."""
    return {"daily", "weekly"} if lane == "weekly" else {lane}


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

                sonde = SONDE_ECHEC_RE.search(out)
                if sonde and RESEAU_RE.search(out):
                    # PANNE RÉSEAU, PAS STRUCTURE CHANGÉE. Le 2026-08-25, une
                    # coupure DNS de quelques minutes a fait échouer la sonde de
                    # DEUX sources : quatre escalades de sévérité HAUTE ont été
                    # ouvertes vers Claude pour « parseur cassé » alors que les
                    # sites n'avaient pas bougé d'un octet — le résolveur ne
                    # répondait plus. Envoyer quelqu'un chercher un bug de
                    # parsing quand le réseau est coupé, c'est exactement le
                    # garde-fou qui crie au loup (règle 2).
                    # Une coupure réseau se reprend seule au cycle suivant : on
                    # le CONSIGNE, on n'escalade pas.
                    source, diag = sonde.group(1), sonde.group(2)
                    metrics["etapes"][-1]["sonde_reseau"] = diag
                    led.finding(name, "low", "panne_reseau",
                                f"{name} ({label}) : site injoignable — "
                                f"résolution DNS ou connexion refusée, structure "
                                f"non mise en cause", {"diagnostic": diag,
                                                       "etape": label, "log": lg}, run_id)
                    print(f"  ⚠ {name} ({label}) : panne réseau, pas de ticket "
                          f"(reprise au prochain cycle)")
                elif sonde:
                    source, diag = sonde.group(1), sonde.group(2)
                    metrics["etapes"][-1]["sonde_echec"] = diag
                    ticket = escalation.create(
                        agent=name, kind="parser_break", severity="high",
                        subject=f"{name} ({label}) : sonde de structure en échec avant scan — {diag}",
                        evidence={"source": source, "diagnostic": diag, "etape": label, "log": lg},
                        asked_of_claude=(
                            f"Le marqueur de structure attendu sur la page de liste de {source} "
                            f"a changé ou disparu : « {diag} ». Inspecter une page de liste réelle, "
                            f"identifier le changement, corriger scraper/adapters/{source}.py "
                            f"SUR UNE BRANCHE."),
                        ledger=led)
                    led.finding(name, "high", "sonde_echec",
                               f"{name} ({label}) : {diag}", {"ticket": ticket}, run_id)
                    alert.alert(name, f"{name} : sonde de structure en échec ({source})",
                               f"{diag}\nTicket : {ticket}\nLog : {lg}")
                    print(f"  ⚠ sonde de structure en échec — ticket {ticket} déposé "
                         f"(pas d'attente des 2 runs de watch-health)")

                coupure = COUPURE_RESEAU_RE.search(out)
                if coupure:
                    # Pas d'escalade (règle 2 — une coupure se résout seule),
                    # mais PAS non plus une réussite ordinaire pour la cadence :
                    # voir is_due() plus bas, qui relit ce flag depuis le ledger.
                    source, diag = coupure.group(1), coupure.group(2)
                    metrics["etapes"][-1]["coupure_reseau"] = diag
                    metrics["coupure_reseau"] = True
                    led.finding(name, "low", "coupure_reseau",
                                f"{name} ({label}) : scan coupé par une coupure réseau — "
                                f"{diag}", {"diagnostic": diag, "etape": label, "log": lg}, run_id)
                    print(f"  ⚠ {name} ({label}) : coupure réseau en cours de scan, pas de "
                          f"ticket (reprise dès le prochain déclenchement de l'orchestrateur)")
    except Exception as e:                                   # noqa: BLE001
        led.end_run(run_id, "failed", 1, {"exception": f"{type(e).__name__}: {e}"})
        led.finding(name, "high", "exception", f"{name} a levé {type(e).__name__}",
                    {"message": str(e)[:500]}, run_id)
        alert.alert(name, f"{name} a échoué ({type(e).__name__})", str(e)[:1500])
        print(f"  ✗ {name} — {type(e).__name__}: {e}")
        return False

    status = "ok" if code == 0 else "failed"
    # Les compteurs des etapes chainees remontent AUSSI a la racine (l'agregat
    # s'ajoute a la trace, il ne la remplace pas). Sans ca, tout lecteur des
    # metriques doit connaitre la forme imbriquee : les deux surveillances ne la
    # connaissaient pas et sont restees inertes du 2026-08-06 au 2026-08-23,
    # 24 runs d'extraction (voir agents/core/metrics.py).
    metrics = aplatir(metrics)
    led.end_run(run_id, status, code, metrics)
    alert.log(name, "info" if status == "ok" else "high",
              f"{status} — {json.dumps(metrics, ensure_ascii=False)[:200]}")
    if status == "failed":
        alert.alert(name, f"{name} a échoué (code {code})",
                    f"Log : {log}\nMétriques : {json.dumps(metrics, ensure_ascii=False)}")
    print(f"  {'✓' if status == 'ok' else '✗'} {name} — code={code} {metrics}")
    return status == "ok"


def run_lane(led: Ledger, lane: str, dry: bool = False, only_due: bool = True,
             local: str | None = None, parallele: bool = True,
             skip_extraction: bool = False) -> None:
    """`skip_extraction` (2026-08-17) : rejoue la séquence normale — analyse,
    organisation, rapport, backup, overseer — SANS retoucher aux extracteurs.

    Sert à deux cas où re-scraper serait du temps perdu ou pire : (1) un
    rattrapage manuel après une extraction déjà faite hors du `--due` normal
    (ex. relancée à la main suite à une coupure) ; (2) le rattrapage au boot
    (voir `--boot`) — si la machine était éteinte au moment du cycle de nuit,
    on veut que analyse/rapport/backup partent au réveil SANS déclencher un
    scrap complet à une heure imprévisible. `is_due()` continue de filtrer
    normalement : si rien n'est dû, ce mode ne fait rien (pas de forçage)."""
    mode = f" — LOCAL → {local}" if local else ""
    if skip_extraction:
        mode += " — SANS EXTRACTION"
    print(f"\n═══ Lane « {lane} » — {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC{mode} ═══")
    actives = lanes_actives(lane)
    ordered = [a for a in REGISTRY["agents"] if actives & set(a.get("lanes", []))]
    # l'overseer relit le cycle : toujours en dernier
    ordered.sort(key=lambda a: a["name"] == "overseer")

    a_lancer = []
    for spec in ordered:
        due, why = is_due(led, spec)
        if spec.get("always_run") and not due:
            why = f"{why} — lancé quand même (always_run : {spec['name']} agit sur CE process, pas sur l'état laissé par le précédent)"
            due = True
        if only_due and not due:
            print(f"  · {spec['name']} — {why}")
            continue
        a_lancer.append(spec)

    # SUPERVISION (garde-veille) : avant même le Prelude. Pose le verrou
    # d'éveil sur le process AVANT que quoi que ce soit de long ne démarre —
    # un Prelude qui prend du temps (rattrapage backup) est tout aussi exposé
    # à une mise en veille que les extracteurs.
    supervision = [s for s in a_lancer if s.get("famille") == "Supervision"]
    for spec in supervision:
        run_agent(led, spec["name"], lane, dry, local)

    # NE JAMAIS COUPER UN SCRAP EN VOL. Depuis le passage de la cadence en jours
    # calendaires (is_due, 2026-08-25), le créneau de 01:00 rend TOUT dû dès que
    # le dernier succès date de la veille — y compris quand le cycle d'hier
    # tourne encore, parce qu'il est parti en retard ou qu'une source a traîné
    # (mesuré le 2026-08-25 : ddproperty seul, 10:00 → 15:56).
    # On reporte alors le cycle ENTIER, pas seulement l'extraction : `report` et
    # surtout `backup-apres-cycle` (copie de 1 Go du SQLite) liraient une base
    # en cours d'écriture. La garde `MultipleInstances=IgnoreNew` de la tâche
    # Windows ne couvre que la tâche elle-même, pas un scrap lancé à la main.
    if not dry:
        occupe = scrap_en_cours(led)
        if occupe:
            print(f"  ⏸ CYCLE REPORTÉ — {occupe}")
            print("     (rien n'est lancé : le prochain créneau reprendra ce qui est dû)")
            led.finding("orchestrator", "medium", "cycle_reporte",
                        "cycle sauté : un scrap était encore en cours",
                        {"raison": occupe, "lane": lane})
            return

    # PRELUDE : avant toute extraction, séquentiel. Sert au backup local
    # (ops/sync_supabase_local.py, agent backup-avant-cycle) — un point de
    # retour en arrière pris juste avant que le cycle ne touche la base.
    # Ne DOIT PAS tourner en parallèle des extracteurs ni entre agents Prelude
    # eux-mêmes : c'est un point de repère, pas un travail concurrent.
    # verifie-backup n'a de sens que juste AVANT une extraction (c'est tout
    # son rôle) — inutile en skip_extraction, et pas anodin (peut déclencher
    # un rattrapage ops/sync_supabase_local.py pour rien).
    prelude = [] if skip_extraction else [s for s in a_lancer if s.get("famille") == "Prelude"]
    for spec in prelude:
        run_agent(led, spec["name"], lane, dry, local)

    # Les EXTRACTEURS visent quatre DOMAINES DIFFÉRENTS : les lancer ensemble ne
    # change rien à la cadence vue par chaque site — le rate-limit est par
    # Fetcher, donc par source. Le temps de cycle tombe à celui de la source la
    # plus lourde au lieu de la somme (mesuré : 31 h → ~16 h).
    # Tout le reste (analyse, organisation, audit) reste séquentiel : ces agents
    # lisent l'état laissé par les extracteurs.
    extracteurs = [] if skip_extraction else [s for s in a_lancer if s.get("famille") == "Extraction"]
    suite = [s for s in a_lancer if s.get("famille") not in ("Extraction", "Prelude", "Supervision")]

    if skip_extraction:
        sautes = [s["name"] for s in a_lancer if s.get("famille") in ("Extraction", "Prelude")]
        if sautes:
            print(f"  ⏭ sautés (skip_extraction) : {', '.join(sautes)}")

    if extracteurs and not dry:
        ouvre_dashboard(led)

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
    fermees = escalation.reconcile(led)
    if fermees:
        print(f"  ({fermees} escalade(s) réconciliée(s) avec queue/done/ — "
              f"déjà résolues, le ledger n'était pas à jour)")
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
    ap.add_argument("--skip-extraction", action="store_true",
                    help="run-lane : rejoue analyse/organisation/rapport/backup/overseer "
                         "SANS toucher aux extracteurs ni à verifie-backup")
    ap.add_argument("--boot", action="store_true",
                    help="mode rattrapage au démarrage/logon : comme --due, mais SANS "
                         "extraction (voir --skip-extraction) — rattrape la suite du cycle "
                         "si la machine était éteinte au moment du cycle de nuit, sans "
                         "déclencher un scrap complet à une heure imprévisible")
    # Contrepartie du réveil de 01:00 : sans elle, la machine réveillée pour un
    # cycle de ~5 h reste allumée jusqu'au matin (garde-veille tient un verrou
    # d'éveil tout du long, et la veille par inactivité du plan est à 5 h).
    # Réservé à la tâche planifiée : jamais posé par --boot, qui part au logon,
    # utilisateur présent. agents/core/veille.py refuse de toute façon si
    # clavier ou souris ont bougé récemment — deux verrous, pas un.
    ap.add_argument("--veille-a-la-fin", action="store_true",
                    help="rendort la machine quand la lane est finie (tâche "
                         "planifiée uniquement ; sauté si quelqu'un utilise le poste)")
    a = ap.parse_args()

    if a.local:
        a.local = os.path.abspath(a.local)
        os.makedirs(a.local, exist_ok=True)

    # Capture des prints DE L'ORCHESTRATEUR LUI-MÊME (pas des sous-processus,
    # déjà journalisés par shell.py) — seulement pour les modes que la tâche
    # planifiée utilise réellement. Un `status`/`due` interactif garde sa
    # console normale sans fichier superflu.
    log_orchestrateur = None
    stdout_origine, stderr_origine = sys.stdout, sys.stderr
    if a.due or a.boot or a.command == "run-lane":
        os.makedirs(shell.LOG_DIR, exist_ok=True)
        chemin_log = os.path.join(
            shell.LOG_DIR,
            f"orchestrator-{datetime.now(timezone.utc):%Y-%m-%dT%H%M%S}.log")
        log_orchestrateur = open(chemin_log, "w", encoding="utf-8", errors="replace")
        sys.stdout = Tee(stdout_origine, log_orchestrateur)
        sys.stderr = Tee(stderr_origine, log_orchestrateur)

    led = Ledger()
    # Seuls les modes qui EXÉCUTENT une lane déposent le témoin de vie. Une
    # consultation (`status`, `due`) ne doit surtout pas faire croire qu'un
    # cycle est passé — le témoin sert justement à distinguer les deux.
    a_tourne = False
    try:
        if a.boot:
            run_lane(led, current_lane(), a.dry_run, only_due=True, local=a.local,
                     skip_extraction=True)
            a_tourne = True
        elif a.due:
            run_lane(led, current_lane(), a.dry_run, only_due=True, local=a.local)
            a_tourne = True
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
            a_tourne = True
        elif a.command == "run-lane":
            if not a.target:
                ap.error("run-lane demande sale|rent|weekly")
            run_lane(led, a.target, a.dry_run, only_due=not a.all, local=a.local,
                     skip_extraction=a.skip_extraction)
            a_tourne = True
    finally:
        led.close()

    # APRÈS led.close() : la base doit être fermée proprement avant que le
    # système se suspende. En veille moderne (S0) le process survit, mais un
    # SQLite laissé ouvert au moment d'une coupure d'alimentation ne survivrait
    # pas — et le ledger est la seule mémoire de ce qui est dû.
    # TÉMOIN DE VIE — déposé à la fin de TOUT passage de l'orchestrateur, quel
    # que soit le mode et même si rien n'était dû. C'est ce témoin qu'une tâche
    # Windows séparée relit plusieurs fois par jour (ops/pouls.py --verifier) :
    # les 24 et 25 août 2026, deux nuits sans scrap n'ont produit AUCUN signal,
    # parce que les surveillances existantes sont des agents — elles tournent
    # DANS le cycle et ne peuvent pas constater son absence.
    try:
        if a_tourne and not a.dry_run:
            from ops.pouls import battement
            # `--boot` et `--skip-extraction` sautent délibérément
            # l'extraction ; un `run <agent>` isolé ne l'attaque que si
            # l'agent visé EST un extracteur. Dans tous les autres cas,
            # cette invocation ne peut rien dire sur l'extraction — voir
            # ops/pouls.battement() pour l'incident du 2026-09-09 que ça
            # corrige (cycle_vide crié à tort par un rattrapage isolé).
            extraction_tentee = not (a.boot or a.skip_extraction)
            if a.command == "run" and a.target:
                cible = next((s for s in REGISTRY["agents"]
                              if s["name"] == a.target), None)
                extraction_tentee = bool(
                    cible and cible.get("famille") == "Extraction")
            battement(current_lane(), extraction_tentee=extraction_tentee)
    except Exception as e:                                   # noqa: BLE001
        # Un témoin qui plante ne doit jamais faire échouer un cycle réussi.
        print(f"[pouls] témoin non déposé : {type(e).__name__}: {e}")

    if log_orchestrateur:
        # Restaurer AVANT de fermer : sinon sys.stdout reste un Tee pointant
        # sur un fichier fermé, et le nettoyage de l'interpréteur à la sortie
        # tente de le reflusher — "Exception ignored while flushing sys.stdout"
        # (mesuré en testant ce correctif, 2026-09-12).
        sys.stdout, sys.stderr = stdout_origine, stderr_origine
        log_orchestrateur.close()

    if a.veille_a_la_fin:
        from agents.core import veille
        dormi, raison = veille.endort(dry_run=a.dry_run)
        print(f"[veille] {raison}")


if __name__ == "__main__":
    main()
