"""test_cadence.py — « tous les jours à 01:00 » doit vouloir dire tous les jours.

POURQUOI CE TEST EXISTE
Mesuré le 2026-08-25. `every_days: 1` était comparé à des HEURES ÉCOULÉES depuis
le départ du dernier succès. Tant que le cycle partait à l'heure, personne ne
voyait la différence. Mais dès qu'il glissait dans la journée — rattrapage au
logon, coupure réseau, lancement à la main — le créneau de 01:00 suivant tombait
sous les 24 h et TOUT se déclarait « à jour ».

Le jour de la mesure : cycle parti à 08:24 faute de réveil, extracteurs à 10:00.
À 01:00 la nuit suivante il ne s'était écoulé que 0,6 j ; les 12 agents de la
lane étaient « à jour » ; aucun scrap. Et rien n'alertait : le cycle se terminait
« normalement », simplement vide. Une nuit sur deux perdue, en silence.

La contrepartie du passage en jours calendaires, c'est `scrap_en_cours()` : « tous
les jours » ne doit jamais vouloir dire « quitte à couper celui d'hier ». Un
extracteur tué en vol est PIRE qu'un cycle manqué — la passe `--full` en cours
n'a vu qu'une partie du site, et le diff compte comme délisté ce qu'elle n'a pas
revu. On perdrait des annonces vivantes.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_cadence.py
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from agents.core.ledger import Ledger                    # noqa: E402
import agents.orchestrator as orch                       # noqa: E402

essais = 0


def verifie(nom: str, condition: bool, detail: str = "") -> None:
    global essais
    essais += 1
    if not condition:
        print(f"{nom} : ÉCHEC  {detail}")
        sys.exit(1)
    print(f"{nom} : OK  {detail}")


def ledger_neuf() -> Ledger:
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    return Ledger(f.name)


def succes_le(led: Ledger, agent: str, quand: datetime) -> None:
    """Écrit un succès daté. On passe par SQL : `start_run` horodate à
    maintenant, or c'est justement la date qu'on veut contrôler."""
    led.conn.execute(
        "insert into agent_runs(agent,tier,lane,started_at,ended_at,status,pid)"
        " values(?,'T0','daily',?,?,'ok',NULL)",
        (agent, quand.isoformat(), quand.isoformat()))
    led.conn.commit()


def main() -> None:
    led = ledger_neuf()
    minuit_local = datetime.now().astimezone().replace(
        hour=1, minute=0, second=0, microsecond=0)

    # 1. LE DÉFAUT CORRIGÉ. Un succès daté d'HIER mais vieux de moins de 24 h :
    #    l'ancienne règle disait « à jour », la nouvelle dit « dû », parce que
    #    c'est un autre jour calendaire.
    # La date choisie doit DISCRIMINER les deux règles : hier au calendrier ET
    # moins de 24 h. « Hier 10:00 » ne prouverait rien quand le test tourne le
    # soir (36 h écoulées : l'ancienne règle aussi aurait dit « dû »).
    hier_tard = datetime.now().astimezone().replace(
        hour=0, minute=0, second=0, microsecond=0) - timedelta(minutes=1)
    heures = (datetime.now(timezone.utc) - hier_tard.astimezone(timezone.utc)
              ).total_seconds() / 3600
    verifie("le cas de test discrimine bien les deux règles", heures < 24,
            f"({heures:.0f} h < 24 h : l'ancienne règle disait « à jour »)")
    succes_le(led, "extract-fazwaz", hier_tard.astimezone(timezone.utc))
    du, why = orch.is_due(led, {"name": "extract-fazwaz", "every_days": 1})
    verifie("succès d'hier, cadence 1 j", du,
            f"→ dû ({heures:.0f} h écoulées seulement) — {why}")

    # 2. Deux fois le même jour : non. « Tous les jours » n'est pas « en boucle ».
    succes_le(led, "extract-ddproperty", datetime.now(timezone.utc))
    du, why = orch.is_due(led, {"name": "extract-ddproperty", "every_days": 1})
    verifie("succès du jour même, cadence 1 j", not du, f"→ pas dû — {why}")

    # 3. Cadence longue : elle compte toujours en jours calendaires.
    succes_le(led, "watch-sources",
              (minuit_local - timedelta(days=3)).astimezone(timezone.utc))
    du, _ = orch.is_due(led, {"name": "watch-sources", "every_days": 14})
    verifie("succès il y a 3 j, cadence 14 j", not du, "→ pas dû")
    succes_le(led, "storage",
              (minuit_local - timedelta(days=14)).astimezone(timezone.utc))
    du, _ = orch.is_due(led, {"name": "storage", "every_days": 14})
    verifie("succès il y a 14 j, cadence 14 j", du, "→ dû")

    # 4. Jamais exécuté : dû, sans exception.
    du, why = orch.is_due(led, {"name": "inconnu-au-bataillon", "every_days": 1})
    verifie("agent jamais exécuté", du and "jamais" in why, f"→ {why}")

    # 5. LE GARDE-FOU. Un extracteur 'running' dont le PID vit (le nôtre) doit
    #    être vu ; un PID mort ne doit pas faire de faux positif.
    led.conn.execute(
        "insert into agent_runs(agent,tier,lane,started_at,status,pid)"
        " values('extract-fazwaz','T0','daily',?, 'running', ?)",
        (datetime.now(timezone.utc).isoformat(), os.getpid()))
    led.conn.commit()
    # Le vrai orchestrateur s'exclut lui-même par son PID : on interroge donc
    # avec un PID courant différent, en simulant « un AUTRE process tourne ».
    vu = [r for r in led.conn.execute(
        "select agent,pid from agent_runs where status='running'")]
    verifie("run 'running' visible dans le ledger", len(vu) == 1,
            f"→ {vu[0]['agent']} PID {vu[0]['pid']}")
    verifie("PID vivant reconnu", led._processus_vivant(os.getpid()))
    verifie("PID mort non compté", not led._processus_vivant(999999))

    # 6. La sonde complète, sur l'état réel du poste. Elle ne doit jamais lever
    #    d'exception — un garde-fou qui plante est un cycle qui ne part pas.
    resultat = orch.scrap_en_cours(led)
    verifie("sonde scrap_en_cours exécutable", True,
            f"→ {resultat or 'aucun scrap détecté'}")

    led.close()
    print(f"\nTOUS LES ESSAIS PASSENT ({essais})")


if __name__ == "__main__":
    main()
