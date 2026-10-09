"""test_study_sans_psycopg.py — l'étude lit SQLite, elle ne doit pas dépendre de psycopg.

POURQUOI CE TEST EXISTE
Nuit du 2026-10-09, cycle réel : l'agent `report` est mort code 1 en moins
d'une seconde, sur

    File "C:\\Lowi_bkk\\study\\run_study.py", line 36, in <module>
        import psycopg
    ImportError: no pq wrapper available.
    - couldn't import psycopg 'binary' implementation: DLL load failed while
      importing pq: Une stratégie de contrôle d'application a bloqué ce fichier.

Smart App Control (Windows) avait cessé de faire confiance à la DLL `libpq`
de `psycopg_binary` et la bloquait (journal CodeIntegrity, événement 3077).
Mesuré ce jour-là : le blocage est stable, 5 processus neufs sur 5 échouent,
et une copie renommée de la DLL est bloquée aussi — c'est le contenu du
fichier qui est jugé, pas son chemin ni sa signature (29 des 29 DLL natives
du venv sont non signées et fonctionnent).

LE DÉFAUT N'ÉTAIT PAS LA DLL, C'ÉTAIT L'IMPORT.
`study/run_study.py` lit la base **SQLite locale** — c'est la référence depuis
le 2026-08-23, et `store()` rend `"sqlite"` par défaut. `psycopg` n'y servait
qu'à **un seul appel**, dans la branche `LOWI_STORE=supabase`. L'étude est donc
tombée sur une dépendance qu'elle n'utilisait pas. Un blocage qui ne concernait
que la remontée vers le serveur a emporté le rapport avec lui.

Correctif : import repoussé dans la branche qui s'en sert. Vérifié le
2026-10-09 dans la condition de panne réelle (psycopg encore bloqué sur la
machine) : le module s'importe en 0,13 s, `store()` rend `"sqlite"` et la base
locale est trouvée. Avant correctif, et sur le même interpréteur, l'import
échouait exactement comme en production.

CE QUE CE TEST VÉRIFIE
Que `study/run_study.py` s'importe même quand `psycopg` est **introuvable**.
Il ne se contente pas de l'état de la machine du jour : il **rend psycopg
indisponible de force**, pour rester valable sur un poste où la DLL fonctionne
(PC1) et pour échouer si quelqu'un remet un import de tête.

Il n'exécute PAS l'étude : `run_study.py` a une garde `__main__`, et lancer une
édition hors cycle écrirait un instantané et un fichier daté en production.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_study_sans_psycopg.py
"""
import importlib.util
import os
import sys

for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CIBLE = os.path.join(ROOT, "study", "run_study.py")

_ECHECS: list[str] = []


def verifie(condition: bool, libelle: str) -> None:
    print(("  ✓ " if condition else "  ✗ ") + libelle)
    if not condition:
        _ECHECS.append(libelle)


class _BloquePsycopg:
    """Rend `import psycopg` impossible, quoi qu'il y ait sur la machine.

    Reproduit l'effet du blocage de la DLL sans dépendre de l'humeur de Smart
    App Control : le test doit dire la même chose sur PC1 (où psycopg marche)
    et sur PC2 un jour où il remarcherait.
    """

    def find_module(self, nom, chemin=None):            # API historique
        return self if nom == "psycopg" or nom.startswith("psycopg.") else None

    def find_spec(self, nom, chemin=None, cible=None):  # API moderne
        if nom == "psycopg" or nom.startswith("psycopg."):
            raise ImportError("no pq wrapper available. (simulé par le test)")
        return None


def main() -> int:
    print(__doc__.strip().splitlines()[0])

    # On écarte un psycopg déjà chargé, sinon le blocage serait sans effet.
    sauvegarde = {k: v for k, v in sys.modules.items() if k.startswith("psycopg")}
    for k in sauvegarde:
        del sys.modules[k]
    garde = _BloquePsycopg()
    sys.meta_path.insert(0, garde)
    if os.path.join(ROOT, "scraper") not in sys.path:
        sys.path.insert(0, os.path.join(ROOT, "scraper"))

    try:
        # Le blocage mord-il vraiment ? Sans cette vérification, un test qui
        # passe ne prouverait rien (règle 2 : un garde-fou doit pouvoir échouer).
        try:
            import psycopg  # noqa: F401
            verifie(False, "le blocage simulé est effectif (psycopg importable !)")
        except ImportError:
            verifie(True, "le blocage simulé est effectif (psycopg introuvable)")

        spec = importlib.util.spec_from_file_location("run_study_sous_test", CIBLE)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
            importe, cause = True, ""
        except ImportError as exc:
            importe, cause = False, str(exc).splitlines()[0]

        verifie(importe,
                "study/run_study.py s'importe sans psycopg"
                + ("" if importe else f" — {cause}"))

        if importe:
            # L'étude doit viser la base locale : c'est la référence depuis le
            # 2026-08-23, et c'est ce qui rend psycopg inutile ici.
            verifie(module.store() == "sqlite",
                    f'store() rend "sqlite" par défaut (vu : {module.store()!r})')
    finally:
        sys.meta_path.remove(garde)
        sys.modules.update(sauvegarde)

    print()
    if _ECHECS:
        print(f"ÉCHEC — {len(_ECHECS)} vérification(s) : " + " | ".join(_ECHECS))
        return 1
    print("OK — un blocage de la DLL libpq n'emporte plus le rapport.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
