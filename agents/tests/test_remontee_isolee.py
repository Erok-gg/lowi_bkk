"""test_remontee_isolee.py — une remontée Supabase bloquée ne doit plus
faire sauter les extracteurs.

POURQUOI CE TEST EXISTE
Mesuré le 2026-09-16 : la nuit du 15→16, `remonter-local.py` est resté
bloqué ~14h par une panne EXTERNE du pooler Supabase (confirmée par mesure
directe — connexion directe, TCP brut, et même le MCP Supabase lui-même,
tous en échec sur ce projet au même moment). L'ancien `scrap_en_cours()`
unique traitait un `remonter-supabase`/`ops/remonter-local.py` encore actif
exactement comme une extraction en cours, et reportait le cycle ENTIER :
0 extracteur lancé, 0 annonce écrite cette nuit-là — alors que les 5
extracteurs ne dépendent ni de Supabase ni de `remonter-local.py` (qui LIT
bangkok.db, mais n'y écrit jamais).

Décision de l'utilisateur le jour même : Supabase ne doit bloquer QUE la
remontée. `scrap_en_cours()` est désormais scindée en `extraction_en_cours()`
(garde le cycle entier, comme avant, pour une VRAIE collision d'extraction)
et `remontee_en_cours()` (saute uniquement `remonter-supabase`).

Ce que ce test vérifie, sur un ledger temporaire :
  1. `remonter-supabase` seul « running » -> `extraction_en_cours()` ne le
     voit PAS (ce n'est pas une extraction) ;
  2. ... mais `remontee_en_cours()` le voit ;
  3. un extracteur (`extract-fazwaz`) « running » -> `extraction_en_cours()`
     le voit (comportement inchangé, c'est la vraie collision à protéger).

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_remontee_isolee.py
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import agents.orchestrator as orch                          # noqa: E402
from agents.core.ledger import Ledger                        # noqa: E402

essais = 0


def verifie(nom: str, condition: bool, detail: str = "") -> None:
    global essais
    essais += 1
    if not condition:
        raise SystemExit(f"ECHEC — {nom} {detail}")
    print(f"{nom} : OK  {detail}")


def _insere_running(led: Ledger, agent: str) -> None:
    # PID du PARENT (ce process Python lui-même, distinct et vivant pendant
    # tout le test) : scrap_en_cours()/extraction_en_cours()/remontee_en_cours()
    # s'excluent eux-mêmes par leur PROPRE PID (os.getpid()) pour ne jamais se
    # bloquer eux-mêmes -- l'insérer ici produirait un faux négatif silencieux
    # (vu une fois sur test_cadence.py, qui ne le détecte pas non plus).
    led.conn.execute(
        "insert into agent_runs(agent,tier,lane,started_at,status,pid)"
        " values(?, 'T0', 'daily', ?, 'running', ?)",
        (agent, datetime.now(timezone.utc).isoformat(), os.getppid()))
    led.conn.commit()


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        led = Ledger(os.path.join(tmp, "ledger.db"))

        # 1 + 2. remonter-supabase seul en cours
        _insere_running(led, "remonter-supabase")
        verifie("remonter-supabase seul -> extraction_en_cours() ne voit rien",
                orch.extraction_en_cours(led) is None)
        occupe = orch.remontee_en_cours(led)
        verifie("remonter-supabase seul -> remontee_en_cours() le detecte",
                occupe is not None, f"→ {occupe}")

        led.close()

    with tempfile.TemporaryDirectory() as tmp:
        led = Ledger(os.path.join(tmp, "ledger.db"))

        # 3. un extracteur en cours -> toujours vu comme une vraie collision
        _insere_running(led, "extract-fazwaz")
        occupe = orch.extraction_en_cours(led)
        verifie("extract-fazwaz en cours -> extraction_en_cours() le detecte",
                occupe is not None, f"→ {occupe}")

        led.close()

    print(f"\nTOUS LES ESSAIS PASSENT ({essais})")
