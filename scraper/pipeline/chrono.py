"""chrono.py — où passe le temps d'un scrap.

POURQUOI. Le cycle du 2026-08-11 : DDproperty a pris **6,2 h** sur les 6 h 16 du
cycle complet. En reconstituant le coût à partir du code, on n'en explique que
~3 h 30 — 2 h de requêtes de pages (150 listes + 1 488 fiches à 4,5 s), ~10 min
d'empreintes photo, ~1 h 15 d'images. **Deux heures et demie restent
inexpliquées.**

Et surtout : j'ai construit une proposition d'optimisation entière sur une
supposition — « on rouvre 2 900 fiches » — alors que l'adaptateur n'en ouvre que
les nouvelles, ce que la dédup fait correctement depuis longtemps. Le gain
annoncé (« 1 h au lieu de 6 ») était nul.

D'où ce module : **on mesure d'abord, on optimise ensuite.** Sans ça on répare
ce qui n'est pas cassé, et le vrai poste continue de coûter.

CE QU'IL FAIT. Un accumulateur de durées par poste, remis à zéro à chaque run.
Le coût de la mesure est un `time.perf_counter()` par appel : négligeable devant
des requêtes de plusieurs secondes.

CE QU'IL NE FAIT PAS. Il ne change AUCUN comportement — ni cadence, ni ordre, ni
géocodage. C'est un thermomètre, pas un traitement.

    from pipeline import chrono
    with chrono.mesure("fiches"):
        html = fetcher.get_text(url)
    ...
    print(chrono.rapport())
    metriques.update(chrono.resume())
"""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager

_verrou = threading.Lock()
_total: dict[str, float] = {}
_appels: dict[str, int] = {}
_depart = time.perf_counter()


def remettre_a_zero() -> None:
    global _depart
    with _verrou:
        _total.clear()
        _appels.clear()
        _depart = time.perf_counter()


@contextmanager
def mesure(poste: str):
    """Compte le temps passé dans `poste`. Réentrant sans risque : chaque appel
    ajoute sa propre durée, les imbrications se cumulent — donc ne PAS imbriquer
    deux postes qu'on veut comparer, sinon on compte deux fois."""
    t0 = time.perf_counter()
    try:
        yield
    finally:
        d = time.perf_counter() - t0
        with _verrou:
            _total[poste] = _total.get(poste, 0.0) + d
            _appels[poste] = _appels.get(poste, 0) + 1


def resume() -> dict:
    """Durées en secondes, arrondies — destiné aux métriques du ledger."""
    with _verrou:
        ecoule = time.perf_counter() - _depart
        out = {f"t_{k}": round(v, 1) for k, v in _total.items()}
        out.update({f"n_{k}": n for k, n in _appels.items()})
        out["t_total_run"] = round(ecoule, 1)
        # Ce qui n'est dans AUCUN poste. C'est la colonne qui compte : le
        # 2026-08-11, 2 h 30 sur 6,2 h ne se rattachaient à rien de connu.
        out["t_non_mesure"] = round(max(0.0, ecoule - sum(_total.values())), 1)
        return out


def rapport() -> str:
    with _verrou:
        ecoule = max(1e-9, time.perf_counter() - _depart)
        lignes = ["", "  ── où est passé le temps ──",
                  f"  {'poste':22s}{'durée':>10s}{'part':>8s}{'appels':>9s}{'moyen':>9s}"]
        for k, v in sorted(_total.items(), key=lambda x: -x[1]):
            n = _appels.get(k, 0)
            lignes.append(f"  {k:22s}{v/60:>8.1f} m{100*v/ecoule:>7.0f} %"
                          f"{n:>9d}{v/max(1, n):>8.2f}s")
        reste = max(0.0, ecoule - sum(_total.values()))
        lignes.append(f"  {'NON MESURÉ':22s}{reste/60:>8.1f} m{100*reste/ecoule:>7.0f} %")
        lignes.append(f"  {'total':22s}{ecoule/60:>8.1f} m")
        return "\n".join(lignes)
