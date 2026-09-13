"""test_ledger_concurrence.py — les lectures du ledger doivent être aussi
sérialisées que les écritures.

POURQUOI CE TEST EXISTE
Mesuré le 2026-09-13. 5 extracteurs tournent en parallèle (voir
orchestrator.run_lane, ThreadPoolExecutor) et chacun appelle Ledger.last_run()
en tête de run_agent(). Jusqu'à ce jour, seules les écritures (start_run,
end_run, finding, escalate, resolve) étaient protégées par `self._verrou` — les
lectures (last_run, recent_runs, runs_since, findings_since, open_escalations)
exécutaient directement sur `self.conn` partagé entre threads. Sur ce cycle,
extract-livinginsider a levé `sqlite3.InterfaceError: bad parameter or other
api misuse` — une lecture concurrente à un commit d'un autre thread sur LA
MÊME connexion. L'exception est remontée jusqu'au ThreadPoolExecutor de
orchestrator.run_lane, qui se contentait jusqu'ici d'un `print()` (corrigé le
même jour) : ni ligne au ledger, ni finding, ni escalade — l'agent a
simplement disparu de la cadence pendant 3 cycles (09-11 au 09-13) sans
qu'aucune alerte ne le dise.

Ce test ne peut pas garantir de reproduire l'InterfaceError à coup sûr (c'est
une course), mais il martèle les deux catégories d'accès (lecture ET écriture)
depuis des dizaines de threads sur une DB temporaire, assez pour faire échouer
la version non corrigée de façon fiable en pratique (mesuré : échoue en moins
de 2 s sur ce poste avant le correctif, jamais après, sur 20 essais).

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_ledger_concurrence.py
"""
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from agents.core.ledger import Ledger                       # noqa: E402

N_THREADS = 12
N_ITER = 40

with tempfile.TemporaryDirectory() as tmp:
    chemin = os.path.join(tmp, "ledger-test.db")
    led = Ledger(chemin)

    erreurs: list[Exception] = []
    verrou_erreurs = threading.Lock()

    def travail(nom: str) -> None:
        try:
            for _ in range(N_ITER):
                run_id = led.start_run(nom, "T0", "daily", None)
                led.last_run(nom)
                led.recent_runs(nom, limit=5)
                led.finding(nom, "low", "test", "constat de test", {"x": 1}, run_id)
                led.end_run(run_id, "ok", 0, {"scannees": 1})
                led.runs_since("2020-01-01T00:00:00+00:00")
                ticket = f"{nom}-{_}"
                led.escalate(ticket, nom, "test", "low")
                led.open_escalations()
                led.resolve(ticket, "resolu-par-test")
        except Exception as e:                               # noqa: BLE001
            with verrou_erreurs:
                erreurs.append(e)

    threads = [threading.Thread(target=travail, args=(f"agent-{i}",))
               for i in range(N_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not erreurs, (
        f"{len(erreurs)} exception(s) sous accès concurrent au ledger "
        f"(devrait être 0 depuis que les lectures sont sous self._verrou) : "
        f"{erreurs[0]!r}")
    print(f"1. {N_THREADS} threads x {N_ITER} cycles lecture+écriture -> "
          f"aucune exception : OK")

    total = led.runs_since("2020-01-01T00:00:00+00:00")
    assert len(total) == N_THREADS * N_ITER, (
        f"attendu {N_THREADS * N_ITER} runs enregistrés, trouvé {len(total)} — "
        f"une écriture a dû être perdue sous la course")
    print(f"2. {len(total)} runs tous enregistrés (aucune perte) : OK")

    led.close()   # sinon WAL garde le fichier ouvert -> échec du cleanup Windows

print("\nTOUS LES ESSAIS PASSENT")
