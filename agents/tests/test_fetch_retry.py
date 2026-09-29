"""test_fetch_retry.py — verrouiller le retry sur erreur 5xx transitoire.

POURQUOI CE TEST EXISTE
Le 2026-09-01, fazwaz (backend "requests", sans aucun retry) a essuye un 522
Cloudflare (origine indisponible) sur UNE seule etape d'un run a 3 etapes —
les 2 autres, juste avant et juste apres, ont reussi normalement. `get_text()`
renvoyait None des le premier echec, ce que `sonder()` traduit en "page de
liste inaccessible" -> ticket haute severite + mail, etiquete `parser_break`
alors qu'aucune structure n'avait change : un guet-fou qui crie au loup sur un
alea reseau isole (CLAUDE.md, regle 2). curl_cffi integre deja 3 retries
(backoff 1s) ; "requests" n'en avait aucun. Ce test verrouille que le backend
"requests" absorbe desormais un 5xx transitoire sans faire remonter d'echec,
et qu'il abandonne proprement (retourne None, ne leve pas) si l'origine reste
en panne au-dela du nombre d'essais.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_fetch_retry.py
"""
import http.server
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "scraper"))

from pipeline.fetch import Fetcher                       # noqa: E402


def _serveur(sequence_statuts):
    """Sert `sequence_statuts.pop(0)` a chaque requete GET (522 puis 522 puis
    200, par ex.) ; une fois la liste epuisee, sert 200 avec un corps fixe."""
    compte = {"n": 0}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            statut = sequence_statuts[compte["n"]] if compte["n"] < len(sequence_statuts) else 200
            compte["n"] += 1
            corps = b"<html>ok</html>"
            self.send_response(statut)
            self.send_header("Content-Length", str(len(corps)))
            self.end_headers()
            self.wfile.write(corps)

        def log_message(self, *a):  # silence le log par defaut
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, compte


# --------------------------------- 1. 2 echecs 522 puis succes -> retry absorbe
srv, compte = _serveur([522, 522])
try:
    base = f"http://127.0.0.1:{srv.server_port}"
    f = Fetcher(base_url=base, user_agent="test", rate_limit_seconds=0,
                image_rate_limit_seconds=0, respect_robots=False)
    texte = f.get_text(base + "/liste")
    assert texte == "<html>ok</html>", f"attendu un succes apres retry, recu {texte!r}"
    assert compte["n"] == 3, f"attendu 3 requetes (2 echecs + 1 succes), recu {compte['n']}"
finally:
    srv.shutdown()
print("2 x 522 puis succes : retry absorbe, OK")

# --------------------------------- 2. origine en panne au-dela du budget -> None, pas d'exception
srv, compte = _serveur([522, 522, 522, 522, 522])
try:
    base = f"http://127.0.0.1:{srv.server_port}"
    f = Fetcher(base_url=base, user_agent="test", rate_limit_seconds=0,
                image_rate_limit_seconds=0, respect_robots=False)
    texte = f.get_text(base + "/liste")
    assert texte is None, f"attendu None (echec propre) apres epuisement des retries, recu {texte!r}"
finally:
    srv.shutdown()
print("panne persistante au-dela du budget de retry : None sans exception, OK")

print("test_fetch_retry : OK")
