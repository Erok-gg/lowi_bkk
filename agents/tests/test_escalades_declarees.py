"""Tout ticket d'escalade doit être DÉCLARÉ au ledger, pas seulement écrit.

POURQUOI CE TEST EXISTE (2026-10-23)
`escalation.create()` n'inscrit l'escalade au ledger que si on lui passe
`ledger=`. Les agents du cycle le faisaient ; les trois surveillances qui
regardent DEPUIS L'EXTÉRIEUR du cycle — le battement de fin de cycle, la
veille de Claude et le contrôle de fraîcheur — ne le faisaient pas. Or
`orchestrator status` lit le ledger et non la file : il annonçait donc
« Escalades ouvertes : 0 ».

Mesuré ce jour-là : 46 tickets de sévérité haute déposés par ces trois
outils depuis la mise en place, 0 déclaré au ledger. Le 2026-10-23 à 04:30,
`status` affichait 0 alors qu'un ticket haut attendait depuis 7 h. Un
garde-fou muet est le défaut jumeau de celui qui crie au loup (règle 2) ;
trois s'étaient déjà révélés inertes le même jour en août.

Ce test lit les APPELS dans les sources plutôt que de les exécuter : c'est
le seul moyen d'attraper un QUATRIÈME appelant qui oublierait, sans avoir à
déclencher une vraie panne.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_escalades_declarees.py
"""
import ast
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: Fichiers passés au crible : tout le code de production du dépôt qui peut
#: escalader. Les tests eux-mêmes sont exclus (ils passent un ledger factice,
#: et certains n'en veulent pas).
DOSSIERS = ("agents", "ops", "scraper", "study", "bilan_RE")
#: Dossiers de DONNÉES, pas de code : les traverser faisait durer ce test plus
#: de 2 min (scraper/output pèse 1,2 Go). Un test lent finit par être sauté.
EXCLUS = ("tests", ".venv", "node_modules", "__pycache__", "Archives",
          "output", "logs", "snapshots", "archive", "migrations", ".git",
          ".next", "queue", "state", "audits", "docs")


def sources():
    for d in DOSSIERS:
        for racine, dirs, fichiers in os.walk(os.path.join(RACINE, d)):
            dirs[:] = [x for x in dirs if x not in EXCLUS]
            for f in fichiers:
                if f.endswith(".py"):
                    yield os.path.join(racine, f)
    # Les scripts d'ops à tiret ne sont pas importables mais sont du code de
    # production : veille-cycle.py est précisément celui qui avait oublié.
    for f in os.listdir(os.path.join(RACINE, "ops")):
        if f.endswith(".py") and "-" in f:
            yield os.path.join(RACINE, "ops", f)


def appels_sans_ledger():
    """(fichier, ligne) de chaque escalation.create() sans argument ledger."""
    manquants = []
    vus = 0
    for chemin in set(sources()):
        try:
            arbre = ast.parse(open(chemin, encoding="utf-8").read())
        except (SyntaxError, UnicodeDecodeError):
            continue
        for n in ast.walk(arbre):
            if not isinstance(n, ast.Call):
                continue
            f = n.func
            nom = (f.attr if isinstance(f, ast.Attribute) else
                   getattr(f, "id", None))
            if nom != "create":
                continue
            # escalation.create(...) ou escalade.create(...) — pas n'importe
            # quel .create() (Ledger, Path, etc.).
            if isinstance(f, ast.Attribute) and getattr(f.value, "id", "") not in (
                    "escalation", "escalade"):
                continue
            vus += 1
            # 7e position ou mot-clé : les deux formes sont valides.
            if any(k.arg == "ledger" for k in n.keywords) or len(n.args) >= 7:
                continue
            manquants.append((os.path.relpath(chemin, RACINE), n.lineno))
    return vus, manquants


def test_tous_les_appels_declarent_au_ledger():
    vus, manquants = appels_sans_ledger()
    # Contrôle que la mesure mesure : un test qui ne trouve aucun appel
    # passerait vert en ne vérifiant rien (défaut d'août 2026, sept fois).
    assert vus >= 8, f"seulement {vus} appel(s) trouvé(s) — la détection est cassée"
    assert not manquants, (
        "escalation.create() sans ledger= : le ticket serait écrit mais jamais "
        "déclaré, donc invisible de `orchestrator status` :\n  "
        + "\n  ".join(f"{f}:{l}" for f, l in manquants))


def test_la_detection_attrape_bien_un_oubli():
    """Contre-épreuve : sur un appel volontairement fautif, on doit râler."""
    faux = ast.parse("escalation.create('a', 'b', 'high', 's', {}, 'q')")
    n = next(x for x in ast.walk(faux) if isinstance(x, ast.Call))
    assert not any(k.arg == "ledger" for k in n.keywords) and len(n.args) < 7
    bon = ast.parse("escalation.create('a', 'b', 'high', 's', {}, 'q', ledger=L())")
    n = next(x for x in ast.walk(bon) if isinstance(x, ast.Call)
             and getattr(x.func, "attr", "") == "create")
    assert any(k.arg == "ledger" for k in n.keywords)


if __name__ == "__main__":
    cas = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    for nom, fn in cas:
        fn()
    vus, _ = appels_sans_ledger()
    print(f"OK — test_escalades_declarees : {len(cas)}/{len(cas)} "
          f"({vus} appels a escalation.create verifies)")
