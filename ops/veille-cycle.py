"""veille-cycle.py — Claude suit le cycle de nuit jusqu'à ce qu'il soit fini.

POURQUOI CE MODULE EXISTE (2026-10-04, demande de l'utilisateur)
Jusqu'ici, Claude ne regardait le cycle qu'une fois par jour, à ~02:15
(`lowi-reparation-autonome`), alors que le cycle démarrait à 01:00 et finit
entre 05:30 et 21:30. Le 04/10, `remonter-supabase` était en échec depuis
07:44 et personne ne l'a vu de la journée. L'utilisateur veut que Claude
reste « éveillé » tant que le cycle tourne : un passage toutes les 30 min à
partir de l'heure du cycle (02:30), puis plus rien une fois le travail fini et vérifié.

QUI FAIT QUOI
  - CE SCRIPT (déterministe) rassemble les preuves et décide de l'état du
    cycle : pas parti / en cours / terminé. Le code décide, comme partout
    ailleurs dans agents/ (règle du mode extraction, journal du 2026-07-31).
  - HAIKU lit les preuves et rend un verdict court (`claude -p`, sans outil,
    contexte minimal). C'est la vérification demandée ; elle coûte quelques
    centimes par passage.
  - OPUS n'est appelé qu'en cas de problème : ticket dans agents/queue/ puis
    `claude -p --model opus` détaché, avec la procédure de
    `lowi-reparation-autonome`. Une seule escalade par jour et par signature
    de problème. Sans cette limite, un même échec relancerait Opus toutes
    les 30 min.

S'ÉTEINDRE
Une fois le cycle du jour terminé et vérifié, le marqueur
agents/state/veille/<jour>.json est posé. Les passages suivants de la journée
sortent à la première ligne, sans appeler aucun modèle.

Usage :
  scraper\\.venv\\Scripts\\python.exe ops\\veille-cycle.py              (tâche LowiBKK-VeilleClaude)
  ... --sans-llm --sans-escalade --forcer    (essai : n'appelle personne, ignore le marqueur)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
import sqlite3
import hashlib

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agents.core import alert, escalation          # noqa: E402
from agents.core.ledger import Ledger               # noqa: E402

LEDGER = ROOT / "agents" / "ledger.db"
POULS = ROOT / "agents" / "state" / "pouls.json"
ETAT = ROOT / "agents" / "state" / "veille"
LOGS = ROOT / "agents" / "logs"
JOURNAL = ROOT / "ops" / "logs" / "veille"
PY = ROOT / "scraper" / ".venv" / "Scripts" / "python.exe"
SKILL_OPUS = Path.home() / ".claude" / "scheduled-tasks" / "lowi-reparation-autonome" / "SKILL.md"

HAIKU = "claude-haiku-4-5-20251001"
OPUS = "opus"
# L'heure du cycle est LUE sur la tâche LowiBKK-Agents à chaque passage, et
# non supposée : elle est passée de 01:00 à 02:30 le 2026-10-04 (FazWaz
# régénère son sitemap vers 02:00). Une constante figée aurait crié « pas
# parti » à chaque nuit de transition (règle 2). Repli si la tâche est
# illisible : 02:30.
HEURE_PAR_DEFAUT = (2, 30)
# Le cycle compte à partir de 30 min avant son heure, parce qu'un réveil RTC
# peut le lancer quelques secondes avant l'heure annoncée.
MARGE_AVANT_MIN = 30
# Le cycle n'a pas démarré 90 min après son heure → problème. Le 30/09, il est
# parti à 08:07 (veille prolongée) et rien ne l'a signalé avant 02:15 le
# lendemain.
PAS_PARTI_APRES_H = 2.0       # compté depuis le début de fenêtre (heure − 30 min)
MOTIFS_ERREUR = re.compile(r"\[erreur|Traceback|SONDE-ECHEC")
#: La veille ne se surveille pas elle-même. `escalader()` écrit le compte rendu
#: d'Opus dans ce MÊME dossier (`veille-opus-<ts>.log`), et un compte rendu
#: honnête de panne cite forcément les motifs ci-dessus. Mesuré le 2026-10-06 :
#: le rapport de 22:00 contenait « zero `SONDE-ECHEC` » — une phrase qui dit que
#: tout va bien — et la veille de 23:00 l'a compté comme « 1 ligne d'erreur »,
#: changeant la signature du problème, donc contournant la déduplication, donc
#: rappelant un second Opus pour une panne déjà réparée 22 min plus tôt. Le
#: garde-fou criait au loup à sa propre voix (règle 2). Ces journaux sont de la
#: prose de Claude, pas des traces d'agent : ils ne sont pas une preuve sur le
#: cycle. La panne de fond, elle, reste détectée par son propre run `failed`.
PREFIXE_JOURNAL_VEILLE = "veille-opus-"


def _ecrire(msg: str) -> None:
    JOURNAL.mkdir(parents=True, exist_ok=True)
    ligne = f"{datetime.now().strftime('%H:%M:%S')} {msg}"
    print(ligne, flush=True)
    with open(JOURNAL / f"veille-{datetime.now():%Y-%m-%d}.log", "a", encoding="utf-8") as f:
        f.write(ligne + "\n")


# ─── Preuves (lecture seule) ────────────────────────────────────────────────

def debut_cycle(maintenant: datetime, heure: tuple[int, int] = HEURE_PAR_DEFAUT) -> datetime:
    """Début de la fenêtre du cycle du jour, en heure LOCALE du poste (Bangkok)."""
    d = (maintenant.replace(hour=heure[0], minute=heure[1], second=0, microsecond=0)
         - timedelta(minutes=MARGE_AVANT_MIN))
    return d if maintenant >= d else d - timedelta(days=1)


def runs_du_cycle(debut_utc: str) -> list[dict]:
    cx = sqlite3.connect(f"file:{LEDGER}?mode=ro", uri=True, timeout=30)
    cx.row_factory = sqlite3.Row
    rows = [dict(r) for r in cx.execute(
        "select id, agent, lane, started_at, ended_at, status, exit_code, pid, metrics "
        "from agent_runs where started_at >= ? order by id", (debut_utc,))]
    cx.close()
    for r in rows:
        # Les métriques d'un extracteur pèsent des kilo-octets ; Haiku n'a
        # besoin que des compteurs de tête.
        try:
            m = json.loads(r.pop("metrics") or "{}")
        except json.JSONDecodeError:
            m = {}
        r["metrics"] = {k: v for k, v in m.items() if not isinstance(v, (list, dict))}
        if r["status"] == "running":
            r["pid_vivant"] = Ledger._processus_vivant(r["pid"])
    return rows


def constats_hauts(debut_utc: str) -> list[dict]:
    cx = sqlite3.connect(f"file:{LEDGER}?mode=ro", uri=True, timeout=30)
    rows = [{"agent": a, "kind": k, "subject": s, "created_at": c} for a, k, s, c in cx.execute(
        "select agent, kind, subject, created_at from findings "
        "where severity='high' and created_at >= ? order by id", (debut_utc,))]
    cx.close()
    return rows


def erreurs_journaux(debut_local: datetime) -> dict[str, int]:
    seuil = debut_local.timestamp()
    out = {}
    for p in LOGS.glob("*.log*"):
        if p.name.startswith(PREFIXE_JOURNAL_VEILLE):
            continue                 # cf. PREFIXE_JOURNAL_VEILLE : pas sa propre voix
        if p.stat().st_mtime < seuil:
            continue
        with open(p, encoding="utf-8", errors="replace") as f:
            n = sum(1 for ligne in f if MOTIFS_ERREUR.search(ligne))
        if n:
            out[p.name] = n
    return out


def pouls_verifier() -> dict:
    r = subprocess.run([str(PY), str(ROOT / "ops" / "pouls.py"), "--verifier"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=ROOT, timeout=120)
    return {"code": r.returncode, "sortie": (r.stdout + r.stderr).strip()[-800:]}


def tache_agents() -> dict:
    ps = ("$i = Get-ScheduledTaskInfo -TaskName 'LowiBKK-Agents'; "
          "$t = Get-ScheduledTask -TaskName 'LowiBKK-Agents'; "
          "\"$($t.State)|$($i.LastRunTime.ToString('s'))|$($i.LastTaskResult)|$($t.Triggers[0].StartBoundary)\"")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True,
                           text=True, timeout=60)
        etat, dernier, code, depart = r.stdout.strip().split("|")
        h = datetime.fromisoformat(depart)
        return {"etat": etat, "dernier_lancement": dernier, "code": int(code),
                "heure": f"{h:%H:%M}"}
    except Exception as e:                               # noqa: BLE001
        return {"erreur": str(e)[:200]}


def heure_cycle(tache: dict) -> tuple[int, int]:
    try:
        h, m = tache["heure"].split(":")
        return int(h), int(m)
    except (KeyError, ValueError, AttributeError):
        return HEURE_PAR_DEFAUT


def rassembler(maintenant: datetime) -> dict:
    tache = tache_agents()
    debut = debut_cycle(maintenant, heure_cycle(tache))
    debut_utc = debut.astimezone(timezone.utc).isoformat(timespec="seconds")
    runs = runs_du_cycle(debut_utc)
    try:
        pouls = json.loads(POULS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pouls = None
    return {
        "maintenant_local": maintenant.isoformat(timespec="seconds"),
        "debut_cycle_local": debut.isoformat(timespec="seconds"),
        "runs": runs,
        "constats_hauts": constats_hauts(debut_utc),
        "erreurs_journaux": erreurs_journaux(debut),
        "pouls": pouls,
        "pouls_verifier": pouls_verifier(),
        "tache_agents": tache,
        "tickets_en_attente": len(list((ROOT / "agents" / "queue").glob("*.json"))),
    }


# ─── Décision (déterministe) ────────────────────────────────────────────────

def etat_mecanique(p: dict, maintenant: datetime) -> tuple[str, list[str]]:
    """(état, problèmes). État ∈ pas_parti | en_cours | termine."""
    debut = datetime.fromisoformat(p["debut_cycle_local"])
    runs = p["runs"]
    vivants = [r for r in runs if r["status"] == "running" and r.get("pid_vivant")]
    morts = [r for r in runs if r["status"] == "running" and not r.get("pid_vivant")]
    problemes = []
    for r in runs:
        if r["status"] in ("failed", "interrompu"):
            problemes.append(f"{r['agent']} : {r['status']} (run #{r['id']}, code {r['exit_code']})")
    for r in morts:
        problemes.append(f"{r['agent']} : marqué running mais processus {r['pid']} absent (run #{r['id']})")
    for c in p["constats_hauts"]:
        problemes.append(f"constat haut {c['agent']}/{c['kind']} : {c['subject'][:160]}")
    for f, n in p["erreurs_journaux"].items():
        problemes.append(f"{n} ligne(s) d'erreur dans {f}")
    if p["pouls_verifier"]["code"] != 0:
        problemes.append(f"pouls --verifier : {p['pouls_verifier']['sortie'][-300:]}")

    if not runs:
        if (maintenant - debut).total_seconds() / 3600 > PAS_PARTI_APRES_H:
            problemes.insert(0, f"aucun run depuis {debut:%H:%M} : le cycle n'est pas parti "
                                f"(tâche : {p['tache_agents']})")
            return "pas_parti", problemes
        return "en_cours", problemes      # trop tôt pour conclure
    if vivants:
        return "en_cours", problemes
    termine_a = (p["pouls"] or {}).get("termine_a")
    if termine_a and datetime.fromisoformat(termine_a) >= debut.astimezone(timezone.utc):
        return "termine", problemes
    # Plus aucun run vivant, mais pas de battement : soit l'orchestrateur est
    # entre deux agents (quelques secondes), soit il est mort. On ne tranche
    # qu'au passage suivant (30 min plus tard).
    if p["tache_agents"].get("etat") == "Running":
        return "en_cours", problemes
    problemes.insert(0, "plus aucun agent actif, tâche arrêtée, et pas de battement de fin de cycle")
    return "termine", problemes


# ─── Haiku ──────────────────────────────────────────────────────────────────

SYSTEME_HAIKU = (
    "Tu surveilles le cycle de nuit d'un système de scraping immobilier. "
    "Tu réponds UNIQUEMENT par un objet JSON valide, sans commentaire.")

CONSIGNE_HAIKU = """Voici l'état mesuré du cycle du jour (preuves brutes) et l'état décidé par le code.

Rends un objet JSON :
{"verdict": "en_cours" | "termine_ok" | "probleme",
 "resume": "<2 phrases en français : où en est le cycle, avec les chiffres des preuves>",
 "problemes": ["<un problème par entrée, avec sa preuve>"]}

Règles :
- "en_cours" si l'état du code est en_cours et qu'aucun problème n'est visible.
- "termine_ok" seulement si l'état du code est termine ET qu'aucun problème n'est visible.
- "probleme" dès qu'une preuve montre un échec : run failed/interrompu, constat haut,
  lignes d'erreur, pouls --verifier en échec, extracteurs_ok < extracteurs_lances,
  annonces_ecrites à 0, cycle pas parti, erreurs dans les métriques d'un run.
- Ne cite que ce qui figure dans les preuves. N'invente aucun chiffre.

État décidé par le code : {etat}
Problèmes relevés par le code : {problemes}

Preuves :
{preuves}
"""


def _claude_bin() -> str:
    return (shutil.which("claude") or shutil.which("claude.exe")
            or str(Path.home() / ".local" / "bin" / "claude.exe"))


DELAI_HAIKU_S = 300
#: Un délai réellement dépassé se constate ~300 s après le départ. Le
#: 2026-10-06, l'appel parti à 05:00:56 a « expiré » à 10:14:31 : 18 815 s
#: d'horloge, le poste en veille moderne de 05:00 à l'ouverture du capot
#: (Kernel-Power 507 à 10:14:02). L'alerte qui a suivi suggérait un /login
#: inutile. Au-delà de cette marge, le processus était gelé, pas en panne.
MARGE_GEL_S = 120
_horloge = time.time          # remplaçable par le test


class HaikuGele(RuntimeError):
    """Délai expiré parce que le poste dormait pendant l'appel."""


def demander_haiku(preuves: dict, etat: str, problemes: list[str]) -> dict:
    prompt = (CONSIGNE_HAIKU.replace("{etat}", etat)
              .replace("{problemes}", json.dumps(problemes, ensure_ascii=False))
              .replace("{preuves}", json.dumps(preuves, ensure_ascii=False, indent=1)))
    # --strict-mcp-config + config MCP vide : sans eux, le CLI embarque la
    # définition des outils des connecteurs du compte (Gmail, Supabase,
    # Vercel, Drive…) même avec --tools "". Mesuré le 2026-10-04 sur un appel
    # trivial : 36 331 tokens de contexte (0,008 $ en lecture de cache, 0,07 $
    # quand le cache s'écrit) contre 236 tokens (0,0007 $) sans eux. Le
    # premier passage de la veille avait coûté 0,09 $, les suivants 0,02-0,03 $.
    # cwd temporaire : sinon le CLI charge CLAUDE.md.
    with tempfile.TemporaryDirectory() as tmp:
        vide = Path(tmp) / "mcp-vide.json"
        vide.write_text('{"mcpServers": {}}', encoding="utf-8")
        cmd = [_claude_bin(), "-p", "--model", HAIKU, "--output-format", "json",
               "--tools", "", "--setting-sources", "", "--strict-mcp-config",
               "--mcp-config", str(vide), "--system-prompt", SYSTEME_HAIKU]
        # Réflexion coupée et cache désactivé. Mesuré le 2026-10-04 sur les
        # mêmes preuves : 3 618 tokens de réflexion (0,018 $) et 4 454 tokens
        # ÉCRITS en cache à tarif double (0,009 $), un cache jamais relu
        # puisque les preuves changent à chaque passage. Total 0,028 $. Sans
        # les deux : 0,0055 $, même verdict sur deux essais.
        env = {**os.environ, "MAX_THINKING_TOKENS": "0", "DISABLE_PROMPT_CACHING": "1"}
        t0 = _horloge()
        try:
            r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, env=env,
                               encoding="utf-8", errors="replace", timeout=DELAI_HAIKU_S, cwd=tmp)
        except subprocess.TimeoutExpired:
            ecoule = _horloge() - t0
            if ecoule > DELAI_HAIKU_S + MARGE_GEL_S:
                raise HaikuGele(f"délai de {DELAI_HAIKU_S} s constaté après {ecoule / 60:.0f} min "
                                "d'horloge — poste en veille pendant l'appel") from None
            raise
    try:
        d = json.loads(r.stdout)
    except (json.JSONDecodeError, TypeError):
        d = None
    if r.returncode != 0 or not isinstance(d, dict) or d.get("is_error"):
        cause = str(d.get("result"))[:300] if isinstance(d, dict) else (r.stderr or r.stdout)[:300]
        raise RuntimeError(f"claude -p (haiku) code {r.returncode} : {cause}")
    m = re.search(r"\{.*\}", d.get("result") or "", re.S)
    v = json.loads(m.group(0)) if m else {}
    v["cout_usd"] = round(float(d.get("total_cost_usd") or 0), 4)
    return v


# ─── Opus ───────────────────────────────────────────────────────────────────

def _signature(problemes: list[str]) -> str:
    # Les chiffres changent d'un passage à l'autre (« 3 lignes » puis « 5 »)
    # pour un même problème : on les retire avant de hacher.
    norm = sorted({re.sub(r"\d+", "#", p) for p in problemes})
    return hashlib.sha1("\n".join(norm).encode()).hexdigest()[:10]


def escalader(jour: str, preuves: dict, problemes: list[str], verdict: dict, lancer: bool) -> str | None:
    sig = _signature(problemes)
    marque = ETAT / f"{jour}.escalade-{sig}.json"
    if marque.exists():
        _ecrire(f"escalade {sig} déjà faite aujourd'hui — pas de nouvel appel à Opus")
        return None
    # Pas deux Opus en parallèle : ils travailleraient sur la même branche.
    for m in ETAT.glob(f"{jour}.escalade-*.json"):
        try:
            pid = json.loads(m.read_text(encoding="utf-8")).get("pid")
        except (OSError, json.JSONDecodeError):
            pid = None
        if pid and Ledger._processus_vivant(pid):
            _ecrire(f"Opus (pid {pid}) travaille déjà — escalade {sig} reportée au passage suivant")
            return None

    ticket = escalation.create(
        "veille-claude", "cycle_probleme", "high",
        f"veille du cycle : {len(problemes)} problème(s) — {problemes[0][:120]}",
        {"problemes": problemes, "verdict_haiku": verdict,
         "runs": [{k: r[k] for k in ("id", "agent", "status", "exit_code", "started_at", "ended_at")}
                  for r in preuves["runs"]]},
        "Reproduire, diagnostiquer, corriger sur une branche si c'est un défaut de code ; "
        "consigner si c'est un incident passager. Ne rien changer aux règles de méthode.")
    _ecrire(f"ticket {ticket}")
    pid = None
    if lancer:
        try:
            consigne = SKILL_OPUS.read_text(encoding="utf-8").split("---", 2)[-1]
        except OSError:
            consigne = "Applique la procédure de réparation décrite dans C:\\Lowi_bkk\\CLAUDE.md."
        prompt = (consigne + "\n\n## Pourquoi tu es appelé maintenant\n\n"
                  "La veille Haiku du cycle (ops/veille-cycle.py) a relevé ces problèmes ; le ticket "
                  f"`agents/queue/{ticket}` les porte. Commence par lui.\n\n"
                  + "\n".join(f"- {p}" for p in problemes))
        LOGS.mkdir(exist_ok=True)
        sortie = open(LOGS / f"veille-opus-{datetime.now():%Y-%m-%dT%H%M%S}.log", "w", encoding="utf-8")
        # Détaché et hors du job de la tâche planifiée : sinon la limite
        # d'exécution de LowiBKK-VeilleClaude (20 min) tuerait Opus en pleine
        # réparation.
        flags = 0x00000008 | 0x00000200 | 0x01000000   # DETACHED | NEW_GROUP | BREAKAWAY_FROM_JOB
        cmd = [_claude_bin(), "-p", "--model", OPUS, "--permission-mode", "bypassPermissions"]
        try:
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=sortie, stderr=subprocess.STDOUT,
                                 cwd=ROOT, creationflags=flags, text=True, encoding="utf-8")
        except OSError:
            # Le job de la tâche peut interdire la sortie (BREAKAWAY refusé).
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=sortie, stderr=subprocess.STDOUT,
                                 cwd=ROOT, creationflags=flags & ~0x01000000, text=True, encoding="utf-8")
        p.stdin.write(prompt)
        p.stdin.close()
        pid = p.pid
        _ecrire(f"Opus lancé (pid {pid})")
    ETAT.mkdir(parents=True, exist_ok=True)
    marque.write_text(json.dumps({"ticket": ticket, "pid": pid, "problemes": problemes,
                                  "le": datetime.now().isoformat(timespec="seconds")},
                                 ensure_ascii=False, indent=1), encoding="utf-8")
    alert.log("veille-claude", "high", f"escalade Opus {sig} : {problemes[0][:200]}")
    return ticket


# ─── Passage ────────────────────────────────────────────────────────────────

ECHECS_CONSOMMES = (": failed", ": interrompu", "processus", "constat haut", "pas parti")


def doit_escalader(etat: str, problemes: list[str]) -> bool:
    """Cycle fini ou pas parti : tout problème remonte. Cycle EN COURS : seuls
    les échecs déjà consommés (run terminé en échec, processus disparu,
    constat haut). Les lignes d'erreur d'un extracteur qui tourne encore sont
    souvent des reprises réseau (« délai curl dépassé… repris », 3 fois le
    30/09, toutes rattrapées) : on attend la fin du cycle pour en juger."""
    if not problemes:
        return False
    if etat != "en_cours":
        return True
    return any(m in p for p in problemes for m in ECHECS_CONSOMMES)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sans-llm", action="store_true", help="n'appelle pas Haiku")
    ap.add_argument("--sans-escalade", action="store_true", help="ni ticket ni Opus")
    ap.add_argument("--forcer", action="store_true", help="ignore le marqueur de fin et n'en pose pas")
    a = ap.parse_args()

    maintenant = datetime.now().astimezone()
    preuves = rassembler(maintenant)
    jour = preuves["debut_cycle_local"][:10]
    fin = ETAT / f"{jour}.json"
    if fin.exists() and not a.forcer:
        return 0                      # cycle du jour déjà vérifié : on dort

    # Nuit de maintenance déclarée (agents/core/maintenance.py) : « pas parti »
    # est l'effet voulu, pas une panne. On le consigne et on dort jusqu'au
    # prochain cycle — ni Haiku, ni ticket, ni Opus.
    from agents.core import maintenance
    m = maintenance.active(maintenant)
    if m and not preuves["runs"]:
        ETAT.mkdir(parents=True, exist_ok=True)
        fin.write_text(json.dumps({"verifie_le": maintenant.isoformat(timespec="seconds"),
                                   "maintenance": m["motif"],
                                   "jusqu_au": m["fin"].isoformat()},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
        _ecrire(f"cycle du {jour} non lancé : maintenance ({m['motif']}) — veille éteinte")
        return 0

    etat, problemes = etat_mecanique(preuves, maintenant)
    _ecrire(f"état {etat} — {len(preuves['runs'])} runs, {len(problemes)} problème(s)")

    verdict = {}
    if not a.sans_llm:
        try:
            try:
                verdict = demander_haiku(preuves, etat, problemes)
            except HaikuGele as e:
                # Gel par la veille : ni panne ni authentification. Pas
                # d'alerte ; un seul nouvel essai, maintenant que le poste est
                # réveillé. S'il échoue aussi, c'est une vraie panne → alerte.
                _ecrire(f"haiku gelé par la veille ({e}) — nouvel essai")
                verdict = demander_haiku(preuves, etat, problemes)
            _ecrire(f"haiku : {verdict.get('verdict')} — {verdict.get('resume', '')} "
                    f"({verdict.get('cout_usd')} $)")
        except Exception as e:                           # noqa: BLE001
            # Haiku muet ne doit pas rendre la veille muette : le verdict
            # mécanique suffit pour décider, et la panne elle-même est signalée
            # (une fois par jour). C'est le défaut du 23-29/09 (OAuth expiré,
            # 7 jours sans signal) qu'on ne veut pas reproduire ici.
            _ecrire(f"haiku indisponible : {e}")
            marque = ETAT / f"{jour}.haiku-ko"
            if not marque.exists() and not a.sans_escalade:
                ETAT.mkdir(parents=True, exist_ok=True)
                marque.write_text(str(e)[:500], encoding="utf-8")
                alert.alert("veille-claude", "veille du cycle : claude -p (haiku) en échec",
                            f"{e}\n\nLa veille continue sur le seul verdict du code. "
                            "Si c'est une authentification : lancer `claude` puis /login sur PC2.")

    # Haiku peut relever un problème que le code n'a pas codé (ex. « 1000
    # erreur(s) » dans les métriques d'un run ok). On l'ajoute, marqué comme tel,
    # pour pouvoir mesurer plus tard combien de ces ajouts étaient fondés.
    if verdict.get("verdict") == "probleme" and not problemes:
        problemes = [f"(haiku) {x}" for x in verdict.get("problemes") or ["sans détail"]]

    if doit_escalader(etat, problemes):
        if not a.sans_escalade:
            escalader(jour, preuves, problemes, verdict, lancer=True)
        else:
            _ecrire("escalade désactivée (--sans-escalade) : " + " | ".join(problemes))

    if etat == "termine" and not a.forcer:
        ETAT.mkdir(parents=True, exist_ok=True)
        fin.write_text(json.dumps({"verifie_le": maintenant.isoformat(timespec="seconds"),
                                   "problemes": problemes, "verdict_haiku": verdict},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
        _ecrire(f"cycle du {jour} terminé et vérifié — veille éteinte jusqu'au prochain cycle")
    return 0


if __name__ == "__main__":
    sys.exit(main())
