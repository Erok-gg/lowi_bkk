"""test_fetch_throttle.py — relances communes aux deux backends + cadence adaptative.

POURQUOI CE TEST EXISTE (2026-10-20)
1. Le backend curl_cffi (DDproperty depuis le 2026-08-29) était documenté avec
   « 3 retries intégrés ». Mesuré : `RetryStrategy(count=0)`. Sept semaines
   sans aucune relance, et aucun test ne le voyait — test_fetch_retry
   n'exerçait que "requests". On exerce ici LES DEUX backends.
2. Un 429 n'était relancé par personne : fiche perdue, cadence inchangée.
3. Le mode "adaptatif" doit (a) converger vers le plancher sur un serveur
   rapide, (b) ralentir sur 429 et suivre `Retry-After`, (c) ne jamais passer
   sous le plancher. Le mode "fixe" ne doit pas bouger (rien d'opt-in ne doit
   changer le comportement historique).

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_fetch_throttle.py
"""
import http.server
import os
import sys
import threading
import time

for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "scraper"))

from pipeline.fetch import Fetcher                       # noqa: E402


def _serveur(sequence):
    """`sequence` : liste de (statut, en-têtes) servis dans l'ordre, puis 200."""
    compte = {"n": 0}

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self):
            statut, entetes = sequence[compte["n"]] if compte["n"] < len(sequence) else (200, {})
            compte["n"] += 1
            corps = b"<html>ok</html>"
            self.send_response(statut)
            for k, v in entetes.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(corps)))
            self.end_headers()
            self.wfile.write(corps)

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, compte


def _fetcher(base, backend, **kw):
    return Fetcher(base_url=base, user_agent="test", respect_robots=False,
                   image_rate_limit_seconds=0, backend=backend, **kw)


for backend in ("requests", "curl_cffi"):
    # ---- 1. 522 transitoire : relancé par les DEUX backends
    srv, compte = _serveur([(522, {}), (522, {})])
    try:
        base = f"http://127.0.0.1:{srv.server_port}"
        f = _fetcher(base, backend, rate_limit_seconds=0)
        assert f.get_text(base + "/x") == "<html>ok</html>", backend
        assert compte["n"] == 3, f"{backend} : attendu 3 requêtes, {compte['n']}"
    finally:
        srv.shutdown()
    print(f"[{backend}] 2 x 522 puis succès : relancé, OK")

    # ---- 2. 429 + Retry-After : attendu, relancé, cadence ralentie
    srv, compte = _serveur([(429, {"Retry-After": "2"})])
    try:
        base = f"http://127.0.0.1:{srv.server_port}"
        f = _fetcher(base, backend, rate_limit_seconds=0.2, throttle="adaptatif",
                     rate_limit_floor_seconds=0.2)
        t0 = time.monotonic()
        assert f.get_text(base + "/x") == "<html>ok</html>", backend
        duree = time.monotonic() - t0
        assert duree >= 2.0, f"{backend} : Retry-After 2 s non respecté ({duree:.2f}s)"
        # 429 -> délai porté à 2 s (Retry-After), puis le succès qui suit le
        # ramène à mi-chemin de la latence (~0 ici) : ~1 s. C'est la règle
        # d'AutoThrottle — on vérifie qu'il reste 5× au-dessus du départ.
        assert f._delai >= 0.95, f"{backend} : cadence non ralentie après 429 ({f._delai})"
        assert f.statuts == {429: 1, 200: 1}, f.statuts
    finally:
        srv.shutdown()
    print(f"[{backend}] 429 + Retry-After : attente respectée, cadence ralentie à {f._delai:.2f}s, OK")

# ---- 3. adaptatif : converge vers le plancher sur un serveur rapide, jamais en dessous
srv, compte = _serveur([])
try:
    base = f"http://127.0.0.1:{srv.server_port}"
    f = _fetcher(base, "curl_cffi", rate_limit_seconds=0.8, throttle="adaptatif",
                 rate_limit_floor_seconds=0.1)
    suite = []
    for _ in range(6):
        f.get_text(base + "/x")
        suite.append(f._delai)
    assert all(a >= b for a, b in zip(suite, suite[1:])), f"non décroissant : {suite}"
    assert abs(suite[-1] - 0.1) < 0.05, f"plancher non atteint : {suite}"
    assert min(suite) >= 0.1, f"sous le plancher : {suite}"
finally:
    srv.shutdown()
print(f"adaptatif : 0.8 s -> {suite[-1]:.2f} s (plancher 0.1), OK")

# ---- 4. fixe : rien ne bouge
srv, compte = _serveur([(429, {"Retry-After": "0"})])
try:
    base = f"http://127.0.0.1:{srv.server_port}"
    f = _fetcher(base, "requests", rate_limit_seconds=0.05)
    f.get_text(base + "/x")
    assert f._delai == 0.05, f"le mode fixe a modifié la cadence : {f._delai}"
finally:
    srv.shutdown()
print("fixe : cadence inchangée après 429, OK")

print("test_fetch_throttle : OK")
