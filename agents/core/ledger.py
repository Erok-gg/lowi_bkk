"""ledger.py — la mémoire d'exécution du système d'agents.

C'est ce qui rend l'overseer possible : il ne juge pas au feeling, il relit des
runs horodatés et vérifie qu'ils honorent le contrat de sortie déclaré dans le
SKILL.md de chaque agent. C'est aussi ce qui permet à l'orchestrateur de savoir
ce qui est DÛ sans dépendre de `StartWhenAvailable` (dont on a vu qu'il ne
rattrape rien quand la tâche elle-même est cassée).

Trois tables :
  agent_runs   — un enregistrement par exécution (métriques en JSON)
  findings     — ce qu'un agent a constaté d'anormal
  escalations  — ce qui a été passé à Claude, et ce qu'il en est advenu
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "ledger.db")

SCHEMA = """
create table if not exists agent_runs (
  id          integer primary key autoincrement,
  agent       text not null,
  tier        text not null,              -- T0 | T1 | T2
  lane        text,                       -- sale | rent | weekly | manual
  started_at  text not null,
  ended_at    text,
  status      text not null,              -- running | ok | failed | skipped
  exit_code   integer,
  metrics     text,                       -- JSON
  log_path    text
);
create index if not exists idx_runs_agent on agent_runs(agent, started_at desc);

create table if not exists findings (
  id        integer primary key autoincrement,
  run_id    integer references agent_runs(id),
  agent     text not null,
  severity  text not null,                -- low | medium | high
  kind      text not null,
  subject   text not null,
  detail    text,                         -- JSON
  created_at text not null
);
create index if not exists idx_findings_sev on findings(severity, created_at desc);

create table if not exists escalations (
  id          integer primary key autoincrement,
  ticket      text not null unique,       -- nom du fichier dans queue/
  agent       text not null,
  kind        text not null,
  severity    text not null,
  created_at  text not null,
  status      text not null,              -- open | done | dropped
  resolved_at text,
  resolution  text
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: str | None = None) -> sqlite3.Connection:
    # check_same_thread=False : les extracteurs tournent en parallèle (4 domaines
    # distincts), et chacun journalise son run. Les écritures restent sérialisées
    # par le verrou de la classe Ledger — SQLite n'aime pas les écritures
    # concurrentes, mais les nôtres sont rares et brèves.
    conn = sqlite3.connect(path or DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma journal_mode=WAL")   # lecteurs non bloqués par l'écrivain
    conn.executescript(SCHEMA)
    return conn


class Ledger:
    def __init__(self, path: str | None = None):
        self.conn = connect(path)
        self._verrou = threading.Lock()   # écritures sérialisées (extracteurs parallèles)
        self._migrer_pid()
        self.reap_stale()

    def _migrer_pid(self) -> None:
        """Ajoute `pid` aux runs. Migration douce : la table existe en production.

        Sans le PID, un run reste « en cours » pendant `max_hours` même quand le
        processus est mort depuis longtemps — et l'agent concerné est alors
        SAUTÉ à chaque cycle (orchestrator.run_agent refuse de relancer un agent
        déjà en cours). Constaté le 2026-08-25 : deux extracteurs tués à 09:05
        ont été écartés du cycle de 09:35, sans qu'aucune alerte ne le dise.
        Avec le PID, la question « ce run est-il vivant ? » se mesure au lieu de
        se déduire d'une durée arbitraire."""
        cols = {r[1] for r in self.conn.execute("pragma table_info(agent_runs)")}
        if "pid" not in cols:
            self.conn.execute("alter table agent_runs add column pid integer")
            self.conn.commit()

    @staticmethod
    def _processus_vivant(pid) -> bool:
        """Le processus existe-t-il encore ? Windows : OpenProcess via ctypes.

        Mesuré le 2026-09-08 : `OpenProcess` échoue avec `ERROR_ACCESS_DENIED`
        (code 5) quand l'appelant est dans une session Windows différente de
        celle du processus visé — exactement le cas d'une session Claude Code
        interactive qui interroge le ledger PENDANT qu'un cycle nocturne tourne
        (tâche planifiée, session « Services »). Reproduit en direct : un
        `OpenProcess(SYNCHRONIZE, ...)` sur le PID bien vivant de
        l'orchestrateur a rendu un handle nul avec `GetLastError()==5`, ce qui
        a fait classer `remonter-supabase` (alors 4 h dans une synchronisation
        légitime) comme `interrompu` alors qu'il tournait toujours — un simple
        `python -m agents.orchestrator status` depuis une autre session suffit
        à le déclencher. Un handle nul ne veut donc PAS dire absent : seul
        `ERROR_ACCESS_DENIED` distingue « existe mais inaccessible » de
        « n'existe plus », et le code traitait les deux cas pareil."""
        if not pid:
            return True          # PID inconnu (run d'avant la migration) → on ne tranche pas
        try:
            import ctypes
            ERROR_ACCESS_DENIED = 5
            SYNCHRONIZE = 0x00100000
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            h = kernel32.OpenProcess(SYNCHRONIZE, False, int(pid))
            if not h:
                return ctypes.get_last_error() == ERROR_ACCESS_DENIED
            # 0 = toujours actif ; 0x80 (WAIT_ABANDONED)/0 signalé = terminé
            etat = kernel32.WaitForSingleObject(h, 0)
            kernel32.CloseHandle(h)
            return etat != 0
        except Exception:                                # noqa: BLE001
            return True          # dans le doute, on ne referme pas un run vivant

    def reap_stale(self, max_hours: int = 12) -> int:
        """Referme les runs restés en 'running'.

        Un processus tué (arrêt de tâche, redémarrage, coupure) ne referme jamais
        sa ligne. Sans ce nettoyage, l'agent concerné resterait éternellement
        'en cours' et l'orchestrateur ne le relancerait plus — la panne serait
        silencieuse, exactement le mode de défaillance qu'on cherche à éliminer.

        DEUX CRITÈRES, et le premier est une MESURE (2026-08-25) : un run dont le
        processus n'existe plus est mort, quelle que soit son ancienneté. Le
        délai de 12 h ne reste que comme filet pour les runs sans PID (ceux
        d'avant la migration) et pour un PID recyclé par le système."""
        ferme = 0
        for r in self.conn.execute(
                "select id, pid, started_at from agent_runs where status='running'").fetchall():
            trop_vieux = r["started_at"] < (
                datetime.now(timezone.utc) - timedelta(hours=max_hours)).isoformat()
            if trop_vieux or not self._processus_vivant(r["pid"]):
                self.conn.execute(
                    "update agent_runs set status='interrompu', ended_at=? where id=?",
                    (now(), r["id"]))
                ferme += 1
        if ferme:
            self.conn.commit()
        return ferme

    # ── runs ────────────────────────────────────────────────────────────
    def start_run(self, agent: str, tier: str, lane: str | None = None,
                  log_path: str | None = None) -> int:
        with self._verrou:
            cur = self.conn.execute(
                "insert into agent_runs(agent,tier,lane,started_at,status,log_path,pid)"
                " values(?,?,?,?, 'running', ?, ?)",
                (agent, tier, lane, now(), log_path, os.getpid()))
            self.conn.commit()
        return int(cur.lastrowid)

    def end_run(self, run_id: int, status: str, exit_code: int | None = None,
                metrics: dict | None = None) -> None:
        with self._verrou:
            self.conn.execute(
                "update agent_runs set ended_at=?, status=?, exit_code=?, metrics=? where id=?",
                (now(), status, exit_code, json.dumps(metrics or {}, ensure_ascii=False), run_id))
            self.conn.commit()

    def last_run(self, agent: str, only_ok: bool = False) -> sqlite3.Row | None:
        q = "select * from agent_runs where agent=?"
        if only_ok:
            q += " and status='ok'"
        q += " order by started_at desc limit 1"
        return self.conn.execute(q, (agent,)).fetchone()

    def recent_runs(self, agent: str, limit: int = 20) -> list[sqlite3.Row]:
        return self.conn.execute(
            "select * from agent_runs where agent=? and status='ok'"
            " order by started_at desc limit ?", (agent, limit)).fetchall()

    def runs_since(self, iso: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "select * from agent_runs where started_at >= ? order by started_at",
            (iso,)).fetchall()

    # ── findings ────────────────────────────────────────────────────────
    def finding(self, agent: str, severity: str, kind: str, subject: str,
                detail: dict | None = None, run_id: int | None = None) -> int:
        assert severity in ("low", "medium", "high"), severity
        with self._verrou:
            cur = self.conn.execute(
                "insert into findings(run_id,agent,severity,kind,subject,detail,created_at)"
                " values(?,?,?,?,?,?,?)",
                (run_id, agent, severity, kind, subject,
                 json.dumps(detail or {}, ensure_ascii=False), now()))
            self.conn.commit()
        return int(cur.lastrowid)

    def findings_since(self, iso: str, severity: str | None = None) -> list[sqlite3.Row]:
        q, p = "select * from findings where created_at >= ?", [iso]
        if severity:
            q += " and severity=?"
            p.append(severity)
        return self.conn.execute(q + " order by created_at desc", p).fetchall()

    # ── escalations ─────────────────────────────────────────────────────
    def escalate(self, ticket: str, agent: str, kind: str, severity: str) -> None:
        self.conn.execute(
            "insert or ignore into escalations(ticket,agent,kind,severity,created_at,status)"
            " values(?,?,?,?,?, 'open')", (ticket, agent, kind, severity, now()))
        self.conn.commit()

    def resolve(self, ticket: str, resolution: str, status: str = "done") -> None:
        self.conn.execute(
            "update escalations set status=?, resolved_at=?, resolution=? where ticket=?",
            (status, now(), resolution, ticket))
        self.conn.commit()

    def open_escalations(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "select * from escalations where status='open' order by created_at").fetchall()

    def close(self) -> None:
        self.conn.close()
