"""test_remonter_disjoncteur.py — une panne Supabase longue doit rendre la main.

POURQUOI CE TEST EXISTE
Le 2026-09-19, `ops/remonter-local.py` a tourné **69 h** : chacun des 204 lots
a épuisé son propre budget d'attente réseau (1 200 s) contre un pooler Supabase
en panne, 51 500 erreurs au total. Le process orchestrateur est resté pris, et
la tâche planifiée (`MultipleInstances=IgnoreNew`) a refusé les cycles des 19,
20 et 21/09 : trois nuits sans aucun extracteur. Le correctif du 2026-09-16
(`remontee_en_cours()`) ne couvrait que le cas d'une remontée dans un AUTRE
process ; ici elle bloquait le cycle depuis l'intérieur.

CE QUI EST VÉRIFIÉ, sans réseau (store factice) :
  1. `--max-lots-en-echec` lots d'affilée en échec → abandon, code 1 ;
  2. les lots suivants ne sont PAS tentés ;
  3. ni recopie des statuts ni `scan_run` après abandon (un scan_run ferait
     croire à verifie-synchro.py que le serveur a été rafraîchi) ;
  4. un échec isolé suivi d'un succès remet le compteur à zéro (une coupure
     brève, cas du 18/09, ne doit rien déclencher).

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_remonter_disjoncteur.py
"""
import importlib.util
import sys
import types
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
echecs: list[str] = []


def verifie(nom: str, condition: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if condition else 'ECHEC'} {nom}{(' - ' + detail) if detail else ''}")
    if not condition:
        echecs.append(nom)


class StoreFactice:
    def __init__(self, motif):
        # motif : liste de booléens, True = le lot réussit ; au-delà, échec
        self.motif = list(motif)
        self.tentes = 0
        self.scan_runs = 0

    def upsert_listings_bulk(self, lot, imgs, batch_size):
        ok = self.motif[self.tentes] if self.tentes < len(self.motif) else False
        self.tentes += 1
        if not ok:
            raise OSError("pooler Supabase injoignable (simulé)")
        return {"nouvelles": len(lot), "maj": 0, "changees": 0}

    def record_scan_run(self, *a, **k):
        self.scan_runs += 1


def lancer(motif, n_lots=10, seuil=3):
    spec = importlib.util.spec_from_file_location(
        "remonter_local_test", RACINE / "ops" / "remonter-local.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    store = StoreFactice(motif)
    statuts = {"appels": 0}
    mod.charger = lambda *a, **k: [{"id": f"t:{i}", "source": "test"} for i in range(n_lots)]
    mod.statuts_morts = lambda *a, **k: [("x", "inactive", None)]
    mod.images_de = lambda *a, **k: {}
    mod.marquer_synchronise = lambda *a, **k: None

    def _statuts(*a, **k):
        statuts["appels"] += 1
        return 0
    mod.synchroniser_statuts = _statuts
    mod.os.path.exists = lambda p: True

    faux_store = types.ModuleType("store.supabase_store")
    faux_store.SupabaseStore = lambda dsn: store
    faux_gpu = types.ModuleType("agents.core.gpu")
    faux_gpu.Verrou = lambda nom: types.SimpleNamespace(__enter__=lambda: None)
    anciens = {k: sys.modules.get(k) for k in ("store.supabase_store", "agents.core.gpu")}
    sys.modules["store.supabase_store"] = faux_store
    sys.modules["agents.core.gpu"] = faux_gpu
    mod.os.environ["SUPABASE_DB_URL"] = "postgresql://factice"
    argv = sys.argv
    sys.argv = ["remonter-local.py", "dossier", "--statut", "actives",
                "--synchro-statuts", "--lot", "1", "--max-lots-en-echec", str(seuil)]
    try:
        code = mod.main()
    finally:
        sys.argv = argv
        for k, v in anciens.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return code, store, statuts["appels"]


print("1. panne continue dès le premier lot")
code, store, appels = lancer([], n_lots=10, seuil=3)
verifie("code de sortie 1", code == 1, f"code={code}")
verifie("3 lots tentés, pas 10", store.tentes == 3, f"tentés={store.tentes}")
verifie("pas de recopie des statuts", appels == 0, f"appels={appels}")
verifie("pas de scan_run", store.scan_runs == 0, f"scan_runs={store.scan_runs}")

print("2. échecs isolés entrecoupés de succès")
code, store, appels = lancer([True, False, False, True, False, True] + [True] * 4,
                             n_lots=10, seuil=3)
verifie("les 10 lots tentés", store.tentes == 10, f"tentés={store.tentes}")
verifie("statuts recopiés", appels == 1, f"appels={appels}")
verifie("scan_run écrit", store.scan_runs == 1)
verifie("code 1 (il y a eu des erreurs)", code == 1, f"code={code}")

print("3. tout passe")
code, store, appels = lancer([True] * 10, n_lots=10, seuil=3)
verifie("code 0", code == 0, f"code={code}")

if echecs:
    print(f"\nECHEC — {len(echecs)} vérification(s) : {', '.join(echecs)}")
    sys.exit(1)
print("\nOK — le disjoncteur rend la main sur panne longue, et se tait sur panne brève")
