"""test_log_au_fil_de_leau.py — le journal d'un agent doit se remplir PENDANT
qu'il tourne, pas seulement à sa mort.

POURQUOI CE TEST EXISTE (2026-10-23)
Mesuré ce jour-là, pendant un vrai cycle. Deux extracteurs partis à la même
seconde : au bout de 15 minutes, l'un avait écrit 200 ko dans son journal,
l'autre 0 octet — alors qu'il versait 23 annonces toutes les 50 secondes dans
la base, donc travaillait parfaitement. Son journal de l'avant-veille, lui,
pesait 298 ko : le texte arrive bien, mais tout à la fin.

CAUSE : le parent lit le tuyau ligne à ligne et vide son tampon à chaque ligne
(agents/core/shell.py). Mais l'ENFANT, lui, n'écrit pas vers un terminal : sous
Windows, Python groupe alors sa sortie par blocs de 8 ko avant de l'envoyer.
Un agent bavard franchit ce seuil toutes les trente secondes ; un agent sobre
peut mettre des heures. Les deux variables d'environnement déjà posées règlent
l'encodage, pas le groupage.

POURQUOI ÇA COMPTE : un extracteur peut tourner près de six heures. Pendant ce
temps, quiconque ouvre son journal pour savoir s'il est vivant — un humain, une
surveillance — lit un fichier vide et conclut à une panne. C'est précisément
l'enchaînement qui a coûté une fausse alerte le matin même (règle 2).

Ce que ce test vérifie, dans les conditions réelles (vrai sous-processus, vrai
tuyau, vrai fichier) : un enfant qui imprime peu, et lentement, apparaît dans
son journal AVANT d'avoir fini.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_log_au_fil_de_leau.py
"""
import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from agents.core import shell                               # noqa: E402

essais = 0


def verifie(nom, condition, detail=""):
    global essais
    essais += 1
    if not condition:
        raise AssertionError(f"{nom} : {detail}")


#: Enfant SOBRE à dessein : quelques dizaines d'octets, très loin des 8 ko qui
#: déclencheraient un envoi groupé. C'est le profil de l'extracteur mesuré.
ENFANT = (
    "import time\n"
    "print('depart')\n"
    "time.sleep(3)\n"
    "print('fin')\n"
)


def test_le_journal_se_remplit_avant_la_fin():
    tmp = tempfile.mkdtemp()
    script = os.path.join(tmp, "enfant.py")
    log = os.path.join(tmp, "agent.log")
    with open(script, "w", encoding="utf-8") as f:
        f.write(ENFANT)

    fini = threading.Event()

    def lance():
        shell.run(["@py", script], cwd=tmp, log=log, timeout=60)
        fini.set()

    t = threading.Thread(target=lance, daemon=True)
    t.start()
    # L'enfant imprime sa 1re ligne tout de suite puis dort 3 s. On regarde à
    # mi-parcours : le journal doit déjà la porter.
    vu = ""
    for _ in range(18):                       # jusqu'à ~1,8 s
        time.sleep(0.1)
        if fini.is_set():
            break
        try:
            vu = open(log, encoding="utf-8").read()
        except OSError:
            vu = ""
        if "depart" in vu:
            break
    verifie("pas déjà terminé", not fini.is_set(),
            "l'enfant a fini avant la mesure — le test ne prouve rien")
    verifie("1re ligne visible pendant le run", "depart" in vu,
            f"journal encore vide a mi-parcours (contenu : {vu!r}) — "
            "la sortie de l'enfant est groupee, cf. PYTHONUNBUFFERED")
    t.join(timeout=30)
    verifie("tout est la a la fin", "fin" in open(log, encoding="utf-8").read())


def test_lencodage_reste_force():
    """Le correctif ne doit pas defaire le garde-fou UTF-8 du 2026-08-22."""
    tmp = tempfile.mkdtemp()
    script = os.path.join(tmp, "enfant.py")
    log = os.path.join(tmp, "agent.log")
    with open(script, "w", encoding="utf-8") as f:
        f.write("print('\\u25b6 accentue : etude terminee')\n")
    code, texte = shell.run(["@py", script], cwd=tmp, log=log, timeout=60)
    verifie("code retour", code == 0, f"obtenu {code} — {texte[:200]}")
    verifie("caractere non ascii rendu", "▶" in texte, repr(texte))


if __name__ == "__main__":
    cas = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    for nom, fn in cas:
        fn()
    print(f"OK — test_log_au_fil_de_leau : {len(cas)}/{len(cas)} cas, {essais} verifications")
