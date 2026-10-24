"""test_veille_cadence_changee.py — changer la cadence d'un agent ne doit pas
le déclarer mort dans la seconde.

POURQUOI CE TEST EXISTE (2026-10-23)
Mesuré ce jour-là. La cadence de `extract-propertyhub` et `extract-hipflat` est
passée de 3 jours à 1 jour à 09:05, sur décision de l'utilisateur. À 09:30, la
veille a mesuré « aucun démarrage depuis 55,0 h (seuil 24 h) » sur les deux et
a tout déclenché : 2 constats de sévérité haute, une relance du cycle, un Opus
réveillé. Or les deux agents étaient parfaitement à l'heure : leur dernier
passage datait du 21/10 à 02:30 et, sous la cadence de 3 jours en vigueur à ce
moment-là, le suivant n'était dû que le 24/10.

Le défaut n'est PAS le seuil de 24 h — il reste inchangé, c'est une règle de
méthode qui appartient à l'utilisateur. Le défaut est le point de départ du
décompte : on comparait au seuil d'aujourd'hui un temps écoulé sous la cadence
d'hier. Contrefactuel vérifié sur la vraie configuration : avec `every_days: 3`
les deux agents ne figurent même pas dans la liste surveillée.

Ce que ce test vérifie :
  1. REPRO — cadence passée à 1 j, dernier départ il y a 55 h : sans plancher,
     l'agent est déclaré inactif (le défaut mesuré) ;
  2. CORRECTIF — avec le plancher posé au changement de cadence, il se tait ;
  3. le garde-fou n'est pas devenu sourd : 24 h après le changement, sans
     nouveau départ, il parle de nouveau ;
  4. AMORÇAGE — un fichier d'état absent ne pose AUCUN plancher ; sinon la
     première installation aveuglerait les 20 agents quotidiens pendant 24 h
     (un garde-fou muet vaut celui qui crie, règle 2) ;
  5. une cadence inchangée d'un passage à l'autre ne remet jamais le compteur
     à zéro — sans quoi il suffirait de réécrire la configuration pour taire
     l'alerte indéfiniment ;
  6. le plancher ne masque pas un agent réellement en panne : s'il a démarré
     APRÈS le changement de cadence, c'est son départ qui compte.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_veille_cadence_changee.py
"""
import importlib.util
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location(
    "veille_cycle", os.path.join(RACINE, "ops", "veille-cycle.py"))
vc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vc)

BKK = timezone(timedelta(hours=7))
#: L'instant du constat réel : 2026-10-23 09:30, 55 h après le dernier passage.
MAINTENANT = datetime(2026, 10, 23, 9, 30, tzinfo=BKK)
DERNIER_DEPART = MAINTENANT - timedelta(hours=55)
#: La cadence a été relevée à 09:05, soit 25 min avant le constat.
CHANGEMENT = datetime(2026, 10, 23, 9, 5, tzinfo=BKK)

essais = 0


def verifie(nom, condition, detail=""):
    global essais
    essais += 1
    if not condition:
        raise AssertionError(f"{nom} : {detail}")


class Bac:
    """Ledger + agents.json + état des cadences, tous jetables."""

    def __init__(self, cadences, derniers_departs):
        self.tmp = tempfile.mkdtemp()
        db = os.path.join(self.tmp, "ledger.db")
        cx = sqlite3.connect(db)
        cx.execute("create table agent_runs (agent text, started_at text)")
        cx.executemany("insert into agent_runs values (?, ?)",
                       [(n, d.isoformat()) for n, d in derniers_departs.items()])
        cx.commit()
        cx.close()
        cfg = {"agents": [{"name": n, "lanes": ["daily"], "every_days": j}
                          for n, j in cadences.items()]}
        aj = os.path.join(self.tmp, "agents.json")
        Path(aj).write_text(json.dumps(cfg), encoding="utf-8")
        self.vrais = (vc.LEDGER, vc.AGENTS_JSON, vc.CADENCES_VUES, vc.ETAT, vc._ecrire)
        vc.LEDGER = Path(db)
        vc.AGENTS_JSON = Path(aj)
        vc.ETAT = Path(self.tmp)
        vc.CADENCES_VUES = Path(os.path.join(self.tmp, "cadences.json"))
        vc._ecrire = lambda _m: None          # pas de journal pendant un test

    def etat_cadences(self, contenu):
        vc.CADENCES_VUES.write_text(json.dumps(contenu), encoding="utf-8")

    def lu(self):
        return json.loads(vc.CADENCES_VUES.read_text(encoding="utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        vc.LEDGER, vc.AGENTS_JSON, vc.CADENCES_VUES, vc.ETAT, vc._ecrire = self.vrais


def test_1_repro_sans_plancher_lagent_est_declare_mort():
    """Le défaut tel que mesuré le 2026-10-23 à 09:30."""
    with Bac({"extract-propertyhub": 1}, {"extract-propertyhub": DERNIER_DEPART}):
        sans = vc.inactifs(MAINTENANT, vc.agents_quotidiens())
        verifie("repro", sans == [("extract-propertyhub", 55.0)],
                f"attendu 55,0 h sans plancher, obtenu {sans}")


def test_2_correctif_le_changement_de_cadence_remet_le_compteur_a_zero():
    with Bac({"extract-propertyhub": 1}, {"extract-propertyhub": DERNIER_DEPART}) as b:
        b.etat_cadences({"extract-propertyhub": {"every_days": 3, "depuis": None}})
        planchers = vc.planchers_cadence(CHANGEMENT)
        verifie("plancher posé", planchers.get("extract-propertyhub") == CHANGEMENT,
                f"obtenu {planchers}")
        avec = vc.inactifs(MAINTENANT, vc.agents_quotidiens(), planchers)
        verifie("se tait", avec == [], f"devait se taire, obtenu {avec}")
        verifie("état écrit", b.lu()["extract-propertyhub"]["every_days"] == 1)


def test_3_le_gardefou_reparle_24h_apres_le_changement():
    """Le délai est un report, pas une amnistie."""
    with Bac({"extract-propertyhub": 1}, {"extract-propertyhub": DERNIER_DEPART}) as b:
        b.etat_cadences({"extract-propertyhub": {"every_days": 3, "depuis": None}})
        planchers = vc.planchers_cadence(CHANGEMENT)
        plus_tard = CHANGEMENT + timedelta(hours=25)
        tardif = vc.inactifs(plus_tard, vc.agents_quotidiens(), planchers)
        verifie("reparle", [n for n, _ in tardif] == ["extract-propertyhub"],
                f"devait reparler 25 h après le changement, obtenu {tardif}")


def test_4_amorcage_sans_fichier_detat_ne_pose_aucun_plancher():
    """Première installation : la surveillance ne doit pas s'éteindre 24 h."""
    with Bac({"a": 1, "b": 1}, {"a": DERNIER_DEPART, "b": DERNIER_DEPART}) as b:
        planchers = vc.planchers_cadence(CHANGEMENT)
        verifie("aucun plancher à l'amorçage", planchers == {}, f"obtenu {planchers}")
        verifie("parle quand même", len(vc.inactifs(MAINTENANT, ["a", "b"], planchers)) == 2)
        verifie("mais mémorise", set(b.lu()) == {"a", "b"})


def test_5_cadence_inchangee_ne_remet_jamais_le_compteur_a_zero():
    """Sinon réécrire la configuration suffirait à taire l'alerte sans fin."""
    with Bac({"a": 1}, {"a": DERNIER_DEPART}) as b:
        b.etat_cadences({"a": {"every_days": 1, "depuis": None}})
        for pas in range(3):                      # trois passages de veille
            planchers = vc.planchers_cadence(CHANGEMENT + timedelta(minutes=30 * pas))
            verifie(f"passage {pas} muet", planchers == {}, f"obtenu {planchers}")
        verifie("toujours signalé", vc.inactifs(MAINTENANT, ["a"], planchers) != [])


def test_6_un_depart_posterieur_au_changement_prime_sur_le_plancher():
    """Le plancher recule le départ, il ne l'efface pas : un agent qui a tourné
    APRÈS le changement et s'est tu depuis doit être signalé normalement."""
    with Bac({"a": 1}, {"a": CHANGEMENT + timedelta(hours=1)}) as b:
        b.etat_cadences({"a": {"every_days": 3, "depuis": None}})
        planchers = vc.planchers_cadence(CHANGEMENT)
        tard = CHANGEMENT + timedelta(hours=30)   # 29 h après son vrai départ
        res = vc.inactifs(tard, ["a"], planchers)
        verifie("signalé sur son vrai départ", res == [("a", 29.0)], f"obtenu {res}")


if __name__ == "__main__":
    # Liste DÉDUITE, pas recopiée (cf. test_veille_cycle.py) : une liste écrite
    # à la main laisse dormir les tests ajoutés après coup.
    cas = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    for nom, fn in cas:
        fn()
    print(f"OK — test_veille_cadence_changee : {len(cas)}/{len(cas)} cas, {essais} verifications")
