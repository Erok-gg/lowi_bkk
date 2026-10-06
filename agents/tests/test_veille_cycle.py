"""test_veille_cycle.py — la veille de Claude décide juste, et se tait quand tout va bien.

POURQUOI CE TEST EXISTE (2026-10-04)
ops/veille-cycle.py passe toutes les 30 min tant que le cycle tourne et appelle
Opus en cas de problème. Deux façons de rater, toutes deux déjà vues ici :
  - crier au loup (règle 2) : une heure de cycle figée aurait déclaré « pas
    parti » toutes les nuits de la transition 01:00 → 02:30 ; des lignes
    d'erreur d'un extracteur EN COURS (reprises réseau, 3 le 30/09, toutes
    rattrapées) auraient appelé Opus pour rien ;
  - se taire : un run `failed` en plein cycle (remonter-supabase, 04/10, vu
    par personne de la journée) doit remonter sans attendre la fin.

Ce que ce test vérifie :
  1. la fenêtre du cycle suit l'heure de la tâche (01:00 comme 02:30) ;
  2. en cours + run failed → escalade ; en cours + lignes d'erreur seules → non ;
  3. terminé sans problème → pas d'escalade ; terminé avec erreurs → escalade ;
  4. pas parti 2 h après le début de fenêtre → problème ; 1 h après → on attend ;
  5. la signature d'un problème ne dépend pas de ses chiffres (une seule
     escalade par jour pour « 3 lignes » puis « 5 lignes ») ;
  6. un délai Haiku « expiré » parce que le poste dormait (2026-10-06, 5 h 13
     d'horloge pour un délai de 300 s) n'est pas confondu avec une panne.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_veille_cycle.py
"""
import importlib.util
import os
from datetime import datetime, timedelta, timezone

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location("veille_cycle", os.path.join(RACINE, "ops", "veille-cycle.py"))
vc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vc)

BKK = timezone(timedelta(hours=7))


def preuves(maintenant, runs=(), pouls_fini=None, erreurs=None, tache="Ready", heure=(2, 30)):
    debut = vc.debut_cycle(maintenant, heure)
    return {"debut_cycle_local": debut.isoformat(), "runs": list(runs), "constats_hauts": [],
            "erreurs_journaux": erreurs or {}, "pouls_verifier": {"code": 0, "sortie": ""},
            "pouls": {"termine_a": pouls_fini.astimezone(timezone.utc).isoformat()} if pouls_fini else None,
            "tache_agents": {"etat": tache}}


def run(agent, status, vivant=None):
    r = {"id": 1, "agent": agent, "status": status, "exit_code": 0 if status == "ok" else 1, "pid": 42}
    if status == "running":
        r["pid_vivant"] = vivant
    return r


def test_fenetre_suit_la_tache():
    m = datetime(2026, 10, 5, 3, 0, tzinfo=BKK)
    assert vc.debut_cycle(m, (2, 30)) == datetime(2026, 10, 5, 2, 0, tzinfo=BKK)
    assert vc.debut_cycle(m, (1, 0)) == datetime(2026, 10, 5, 0, 30, tzinfo=BKK)
    # 01:45 avec un cycle à 02:30 : on est encore dans la fenêtre de la VEILLE
    assert vc.debut_cycle(datetime(2026, 10, 5, 1, 45, tzinfo=BKK), (2, 30)).day == 4
    assert vc.heure_cycle({"heure": "02:30"}) == (2, 30)
    assert vc.heure_cycle({"erreur": "x"}) == vc.HEURE_PAR_DEFAUT


def test_en_cours():
    m = datetime(2026, 10, 5, 6, 0, tzinfo=BKK)
    p = preuves(m, [run("extract-ddproperty", "running", True), run("remonter-supabase", "failed")])
    etat, pb = vc.etat_mecanique(p, m)
    assert etat == "en_cours" and vc.doit_escalader(etat, pb), pb
    p = preuves(m, [run("extract-ddproperty", "running", True)], erreurs={"extract-ddproperty.log": 3})
    etat, pb = vc.etat_mecanique(p, m)
    assert etat == "en_cours" and pb and not vc.doit_escalader(etat, pb), pb
    # processus disparu sous un run « running » → escalade
    p = preuves(m, [run("extract-ddproperty", "running", False)], tache="Running")
    etat, pb = vc.etat_mecanique(p, m)
    assert vc.doit_escalader(etat, pb), (etat, pb)


def test_termine():
    m = datetime(2026, 10, 5, 11, 0, tzinfo=BKK)
    fini = datetime(2026, 10, 5, 10, 30, tzinfo=BKK)
    p = preuves(m, [run("extract-fazwaz", "ok"), run("report", "ok")], pouls_fini=fini)
    etat, pb = vc.etat_mecanique(p, m)
    assert etat == "termine" and pb == [] and not vc.doit_escalader(etat, pb)
    p = preuves(m, [run("extract-fazwaz", "ok")], pouls_fini=fini, erreurs={"x.log": 2})
    etat, pb = vc.etat_mecanique(p, m)
    assert etat == "termine" and vc.doit_escalader(etat, pb)
    # battement d'HIER : pas terminé tant que la tâche tourne
    hier = fini - timedelta(days=1)
    p = preuves(m, [run("extract-fazwaz", "ok")], pouls_fini=hier, tache="Running")
    assert vc.etat_mecanique(p, m)[0] == "en_cours"


def test_pas_parti():
    tot = datetime(2026, 10, 5, 3, 0, tzinfo=BKK)      # 1 h après le début de fenêtre (02:00)
    etat, pb = vc.etat_mecanique(preuves(tot), tot)
    assert etat == "en_cours" and pb == []
    tard = datetime(2026, 10, 5, 4, 30, tzinfo=BKK)
    etat, pb = vc.etat_mecanique(preuves(tard), tard)
    assert etat == "pas_parti" and vc.doit_escalader(etat, pb)


def test_signature_sans_chiffres():
    a = vc._signature(["3 ligne(s) d'erreur dans extract-x-2026-10-05T193000.log"])
    b = vc._signature(["5 ligne(s) d'erreur dans extract-x-2026-10-05T193000.log"])
    c = vc._signature(["remonter-supabase : failed (run #690, code 1)"])
    assert a == b != c


def test_delai_gele_par_la_veille():
    """2026-10-06 : appel parti à 05:00:56, « expiré » à 10:14:31 (poste en
    veille) → HaikuGele, pas d'alerte « /login ». Un vrai blocage de ~300 s
    reste un TimeoutExpired ordinaire, qui alerte."""
    import subprocess
    vrai_run, vraie_horloge = vc.subprocess.run, vc._horloge

    def bloque(*a, **k):
        raise subprocess.TimeoutExpired(a[0], vc.DELAI_HAIKU_S)

    try:
        vc.subprocess.run = bloque
        for ecoule, attendu in ((18_815, vc.HaikuGele), (301, subprocess.TimeoutExpired)):
            t = iter((1000.0, 1000.0 + ecoule))
            vc._horloge = lambda: next(t)
            try:
                vc.demander_haiku({}, "en_cours", [])
            except Exception as e:                      # noqa: BLE001
                assert type(e) is attendu, (ecoule, type(e))
            else:
                raise AssertionError("aucune exception")
    finally:
        vc.subprocess.run, vc._horloge = vrai_run, vraie_horloge


if __name__ == "__main__":
    test_fenetre_suit_la_tache()
    test_en_cours()
    test_termine()
    test_pas_parti()
    test_signature_sans_chiffres()
    test_delai_gele_par_la_veille()
    print("OK — test_veille_cycle : 6/6")
