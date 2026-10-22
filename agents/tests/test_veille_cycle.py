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
     d'horloge pour un délai de 300 s) n'est pas confondu avec une panne ;
  7. la veille ne compte pas SON PROPRE compte rendu d'Opus comme une erreur du
     cycle (2026-10-06 : « zero SONDE-ECHEC » lu comme 1 ligne d'erreur, donc
     un second Opus appelé pour une panne déjà réparée) ;
  8. un agent quotidien sans démarrage depuis plus de 24 h est signalé, même
     après la fin du cycle (2026-10-20, demande utilisateur).

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


def test_prose_de_haiku_ne_reveille_pas_opus():
    """2026-10-23 : un Opus réveillé à 04:30 pour rien.

    Haiku avait écrit « processus vivant mais pas de métriques collectées —
    extraction suspendue » sur extract-ddproperty à 2 h de course. Deux
    défauts cumulés :
      - la porte d'escalade cherchait le mot « processus » dans de la prose
        libre, donc « processus VIVANT » passait par le motif prévu pour
        « processus ABSENT » ;
      - les preuves ne portaient aucun repère de durée, alors que la médiane
        mesurée de cet agent est de 327 min (de 166 à 1 201 sur 30 runs) et
        qu'il n'écrit ses métriques qu'à la fin.
    Ce test fige le premier point ; le second est une consigne + un repère
    ajoutés aux preuves (duree_habituelle / tourne_depuis_min)."""
    m = datetime(2026, 10, 5, 6, 0, tzinfo=BKK)
    p = preuves(m, [run("extract-ddproperty", "running", True)])
    etat, pb = vc.etat_mecanique(p, m)
    assert etat == "en_cours" and pb == []

    # La phrase exacte du 2026-10-23, et deux tournures anodines : aucune ne
    # doit réveiller Opus pendant que le cycle tourne.
    for prose in ("Run 989 (extract-ddproperty) : état 'running' depuis "
                  "2026-10-22T19:30:04+00:00 sans ended_at, processus vivant mais pas "
                  "de métriques collectées — extraction suspendue",
                  "le processus tourne normalement",
                  "aucun constat haut, mais le cycle paraît lent"):
        assert not vc.doit_escalader("en_cours", [vc.PREFIXE_HAIKU + prose]), prose

    # Ce qui doit TOUJOURS passer : les phrases que le code fabrique lui-même.
    assert vc.doit_escalader("en_cours", ["remonter-supabase : failed (run #1, code 1)"])
    assert vc.doit_escalader(
        "en_cours", ["extract-x : marqué running mais processus 42 absent (run #1)"])
    assert vc.doit_escalader("en_cours", ["constat haut extract-x/sonde_echec : blob changé"])
    # Cycle FINI : la prose de Haiku remonte comme avant (rien n'est perdu).
    assert vc.doit_escalader("termine", [vc.PREFIXE_HAIKU + "extraction suspendue"])


def test_repere_de_duree_dans_les_preuves():
    """Un run en cours doit arriver à Haiku avec de quoi juger : depuis combien
    de temps il tourne, et combien de temps cet agent met d'habitude."""
    d = vc.duree_habituelle("extract-ddproperty")
    assert d is None or ({"runs_mesures", "mediane_min", "plus_court_min",
                          "plus_long_min"} <= set(d)), d
    assert vc.duree_habituelle("agent-qui-n-a-jamais-tourne-xyz") is None
    assert "duree_habituelle" in vc.CONSIGNE_HAIKU and "tourne_depuis_min" in vc.CONSIGNE_HAIKU


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


def test_ne_se_surveille_pas_elle_meme():
    """La veille ne compte pas son propre compte rendu comme une erreur du cycle.

    Defaut mesure le 2026-10-06 : `escalader()` ecrit le rapport d'Opus dans
    agents/logs/veille-opus-<ts>.log, le MEME dossier que `erreurs_journaux()`
    balaie. Le rapport de 22:00 disait « zero `SONDE-ECHEC` » — donc que tout
    allait bien — et la veille de 23:00 l'a compte comme « 1 ligne d'erreur ».
    Cette ligne en plus changeait la signature du probleme, contournait la
    deduplication par signature, et rappelait un second Opus pour une panne
    deja reparee a 15:38 UTC. Un garde-fou qui crie au loup a sa propre voix
    (regle 2), et qui coute une session Opus entiere par passage.
    """
    import pathlib
    import tempfile
    d = pathlib.Path(tempfile.mkdtemp())
    vrai_logs = vc.LOGS
    try:
        vc.LOGS = d
        # un vrai journal d'agent : doit etre compte
        (d / "extract-ddproperty-2026-10-06T020000.log").write_text(
            "[erreur] delai curl depasse\n", encoding="utf-8")
        # le compte rendu d'Opus : prose de Claude, pas une trace d'agent
        (d / "veille-opus-2026-10-06T220013.log").write_text(
            "Zero HTTP errors, zero `SONDE-ECHEC`, 0 open escalations.\n"
            "Traceback cited in prose only.\n", encoding="utf-8")
        debut = datetime.now().astimezone() - timedelta(hours=2)
        vu = vc.erreurs_journaux(debut)
        assert vu == {"extract-ddproperty-2026-10-06T020000.log": 1}, vu

        # Et la consequence qui a reellement declenche le second Opus : sans
        # l'exclusion, la ligne surnumeraire changeait la signature.
        base = ["remonter-supabase : failed (run #722, code 1)",
                "5 ligne(s) d'erreur dans remonter-supabase-2026-10-06T061147.log"]
        avec_sa_voix = base + ["1 ligne(s) d'erreur dans veille-opus-2026-10-06T220013.log"]
        assert vc._signature(base) != vc._signature(avec_sa_voix)
    finally:
        vc.LOGS = vrai_logs


def test_inactivite_24h():
    """8. (2026-10-20) Un agent quotidien sans démarrage depuis > 24 h est vu,
    même après la fin du cycle ; un agent jamais lancé ou récent ne l'est pas."""
    import sqlite3, tempfile
    vrai = vc.LEDGER
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "ledger.db")
        cx = sqlite3.connect(db)
        cx.execute("create table agent_runs (agent text, started_at text)")
        m = datetime(2026, 10, 20, 14, 0, tzinfo=BKK)
        cx.executemany("insert into agent_runs values (?, ?)", [
            ("recent", (m - timedelta(hours=11)).isoformat()),
            ("vieux", (m - timedelta(hours=30)).isoformat())])
        cx.commit(); cx.close()
        vc.LEDGER = vc.Path(db)
        try:
            assert vc.inactifs(m, ["recent", "vieux", "jamais"]) == [("vieux", 30.0)]
            assert vc.inactifs(m, ["recent"]) == []          # se tait quand tout va bien
        finally:
            vc.LEDGER = vrai


if __name__ == "__main__":
    # Liste DÉDUITE, pas recopiée : la liste écrite à la main avait laissé
    # 2 tests ajoutés le 2026-10-23 hors de l'exécution, en annonçant « 8/8 ».
    # Un test qu'on croit jouer et qui dort est un garde-fou inerte (règle 2).
    cas = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    for nom, fn in cas:
        fn()
    print(f"OK — test_veille_cycle : {len(cas)}/{len(cas)}")
