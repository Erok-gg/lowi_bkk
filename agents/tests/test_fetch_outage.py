"""test_fetch_outage.py — verrouiller la resilience a une coupure reseau.

POURQUOI CE TEST EXISTE
Le 2026-08-01, une coupure internet pendant un scan complet avait produit un
`scan_run` marque "full" alors qu'il s'etait arrete a 928/5000 annonces — "une
coupure reseau ressemblait a un scan reussi". Le correctif de l'epoque vivait
dans `ops/superviseur.py`, un script externe (sonde toutes les 30s, attente du
retour du reseau, aucune relance tant qu'il n'est pas revenu). Ce script a ete
retire sans remplacement lors du passage au systeme d'agents (2026-07-31) : la
capacite a disparu en silence. Ce test verrouille le remplacement, pose
directement dans `Fetcher` (scraper/pipeline/fetch.py) :
  1. une coupure DE CONNEXION (DNS, connexion refusee, timeout) declenche une
     attente avec sondage periodique, PAS un abandon immediat ;
  2. si le reseau revient pendant l'attente, la requete reprend normalement,
     sans lever `a_subi_coupure` ;
  3. si le reseau ne revient pas avant le plafond, `get_text()` rend None ET
     `fetcher.a_subi_coupure` passe a True (lu par scraper/run.py) ;
  4. une panne HTTP (5xx persistant, deja couverte par test_fetch_retry.py) ne
     doit PAS declencher ce chemin — c'est une reponse obtenue, pas une
     coupure, et ce test le confirme pour ne pas regresser le comportement
     "abandon rapide" deja verrouille ailleurs.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_fetch_outage.py
"""
import http.server
import os
import socket
import sys

# CE TEST NE POUVAIT PAS PASSER dans une console cp1252 (l'ACP de ce poste) :
# le code qu'il exerce journalise avec « ⚠ », et le test declenche exprès ce
# chemin — il mourait donc en UnicodeEncodeError AVANT d'atteindre la moindre
# assertion. Constate le 2026-09-09 en cherchant tout a fait autre chose. Un
# test qui plante toujours n'est pas un test (regle 2).
# La PRODUCTION n'est pas concernee : agents/core/shell.py force l'UTF-8 pour
# les sous-processus. C'est le lancement DIRECT qui manquait du reglage, comme
# ops/pouls.py le fait deja pour lui-meme.
for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "scraper"))

from pipeline.fetch import Fetcher                       # noqa: E402


def _port_libre() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _demarre_serveur_differe(port: int, delai: float):
    """Lance un HTTPServer sur `port` apres `delai` secondes (simule le retour
    du reseau en cours d'attente)."""
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            corps = b"<html>ok</html>"
            self.send_response(200)
            self.send_header("Content-Length", str(len(corps)))
            self.end_headers()
            self.wfile.write(corps)

        def log_message(self, *a):
            pass

    def cible():
        time.sleep(delai)
        srv = http.server.HTTPServer(("127.0.0.1", port), Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()

    threading.Thread(target=cible, daemon=True).start()


# --------------------------------- 1. coupure puis retour reseau -> recupere, pas de flag
port = _port_libre()  # rien n'ecoute encore -> ConnectionError immediate
_demarre_serveur_differe(port, delai=0.3)
base = f"http://127.0.0.1:{port}"
f = Fetcher(base_url=base, user_agent="test", rate_limit_seconds=0,
            image_rate_limit_seconds=0, respect_robots=False,
            outage_poll_seconds=0.2, outage_max_wait_seconds=5.0)
texte = f.get_text(base + "/liste")
assert texte == "<html>ok</html>", f"attendu succes apres retour reseau, recu {texte!r}"
assert f.a_subi_coupure is False, "le retour du reseau ne doit PAS lever a_subi_coupure"
print("coupure puis retour reseau pendant l'attente : reprise, OK")

# --------------------------------- 2. coupure persistante au-dela du plafond -> None + flag
port2 = _port_libre()  # rien n'ecoutera JAMAIS sur ce port dans ce test
f2 = Fetcher(base_url=f"http://127.0.0.1:{port2}", user_agent="test", rate_limit_seconds=0,
             image_rate_limit_seconds=0, respect_robots=False,
             outage_poll_seconds=0.15, outage_max_wait_seconds=0.5)
texte2 = f2.get_text(f"http://127.0.0.1:{port2}/liste")
assert texte2 is None, f"attendu None (coupure non resolue), recu {texte2!r}"
assert f2.a_subi_coupure is True, "coupure au-dela du plafond doit lever a_subi_coupure"
print("coupure persistante au-dela du plafond : None + a_subi_coupure=True, OK")

# --------------------------------- 3. panne HTTP (pas une coupure) -> pas d'attente, pas de flag
srv3_statuts = {"n": 0}


class Handler522(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        srv3_statuts["n"] += 1
        self.send_response(522)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *a):
        pass


srv3 = http.server.HTTPServer(("127.0.0.1", 0), Handler522)
threading.Thread(target=srv3.serve_forever, daemon=True).start()
try:
    base3 = f"http://127.0.0.1:{srv3.server_port}"
    # Le plafond de coupure est pose tres BAS (0.5s) : si le code se trompait
    # de branche (traitait le 522 comme une coupure), l'attente serait courte
    # et invisible au chrono — c'est `a_subi_coupure` qui tranche, pas la duree
    # (le backoff propre au HTTPAdapter existant, ~7s sur 3 essais, domine de
    # toute facon le temps total et rendrait un seuil de duree fragile ici).
    f3 = Fetcher(base_url=base3, user_agent="test", rate_limit_seconds=0,
                 image_rate_limit_seconds=0, respect_robots=False,
                 outage_poll_seconds=0.2, outage_max_wait_seconds=0.5)
    texte3 = f3.get_text(base3 + "/liste")
    assert texte3 is None, f"attendu None (panne HTTP persistante), recu {texte3!r}"
    assert f3.a_subi_coupure is False, "un 5xx persistant n'est PAS une coupure reseau"
finally:
    srv3.shutdown()
print("panne HTTP persistante (522) : pas traitee comme une coupure, OK")

print("test_fetch_outage : OK")
