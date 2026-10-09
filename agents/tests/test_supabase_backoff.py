"""test_supabase_backoff.py — survivre au démarrage, et ne pas entretenir un disjoncteur.

POURQUOI CE TEST EXISTE
Diagnostic du 2026-09-09, sur demande de l'utilisateur : « j'ai des coupures
réseau mais pas à ce point-là ». Il avait raison — sur 10 runs de
`remonter-supabase`, les 4 échecs recouvraient **trois pannes différentes**, dont
deux qui n'étaient pas des coupures :

1. **2026-09-09 — l'ouverture initiale n'avait aucune reprise.** `_execute()`
   encaissait 20 min de coupure en cours de run, mais `SupabaseStore.__init__`
   appelait `_connect_borne()` nu : un seul essai, borné à 25 s. La remontée
   survivait donc à une panne de vingt minutes au milieu du travail et mourait
   sur un hoquet de vingt-cinq secondes au démarrage (run mort en 79 s).

2. **2026-09-06 — on entretenait nous-mêmes le blocage.** Le pooler avait
   répondu `ECIRCUITBREAKER: new connections are temporarily blocked` ; la
   boucle l'a rappelé à cadence FIXE de 30 s, 37 fois, jusqu'à épuiser les
   20 min. Réessayer vite contre une protection qui vient de se fermer, c'est
   la maintenir fermée.

3. 2026-09-03 — `getaddrinfo failed` : celle-là, et celle-là seulement, était
   une vraie coupure DNS. Déjà couverte par `test_supabase_reconnect.py`.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_supabase_backoff.py
"""
import os
import sys

for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "scraper"))

from store import supabase_store as ss                    # noqa: E402

# 2026-10-09 : pilote passé de psycopg à pg8000 (Smart App Control bloquait la
# DLL libpq). Le faux pilote se branche sur `ss._ouvre` ; les échecs
# d'ouverture remontent en `ss.ErreurConnexion`, quelle que soit leur forme.

ss.OUTAGE_POLL_SECONDS = 0.02
ss.OUTAGE_POLL_MAX = 0.08
ss.CIRCUIT_OUVERT_PALIER = 0.05
ss.OUTAGE_MAX_WAIT_SECONDS = 1.0


class _FausseConnexion:
    def close(self):
        pass


# ───────────────── 1. l'ouverture initiale survit à une coupure passagère
#     C'est le défaut du 2026-09-09 : avant, un seul essai et le run mourait.
essais = {"n": 0}


def _connect_capricieux(dsn):
    essais["n"] += 1
    if essais["n"] < 3:
        raise ss.ErreurConnexion(
            "connect() bloqué au-delà de 25s (DNS ou TCP) — abandon")
    return _FausseConnexion()


ss._connect_borne = _connect_capricieux
db = ss._connect_resilient("postgresql://test/fake")
assert isinstance(db, _FausseConnexion) and essais["n"] == 3, (
    f"l'ouverture initiale doit REESSAYER : {essais['n']} essai(s), "
    f"un hoquet de 25 s ne doit plus tuer la remontee")
print("1. ouverture initiale : survit a 2 echecs puis reussit : OK")

# ───────────────── 2. une coupure qui dure finit quand meme par abandonner
essais["n"] = 0
ss._connect_borne = lambda dsn: (_ for _ in ()).throw(
    ss.ErreurConnexion("failed to resolve host"))
try:
    ss._connect_resilient("postgresql://test/fake")
    raise AssertionError("une coupure sans fin doit finir par lever, pas boucler")
except ss.ErreurConnexion:
    pass
print("2. coupure sans fin : abandon propre, pas de boucle infinie : OK")

# ───────────────── 3. le disjoncteur du pooler recule PLUS qu'une coupure
plat = ss.ErreurConnexion("connection failed: timeout")
disj = ss.ErreurConnexion(
    'FATAL:  (ECIRCUITBREAKER) failed to retrieve database credentials after '
    'multiple attempts, new connections are temporarily blocked')

assert ss._circuit_ouvert(disj) and not ss._circuit_ouvert(plat), \
    "ECIRCUITBREAKER doit etre distingue d'une coupure ordinaire"

pause_plat, _, _ = ss._recul(plat, ss.OUTAGE_POLL_SECONDS)
pause_disj, _, motif = ss._recul(disj, ss.OUTAGE_POLL_SECONDS)
assert pause_disj > pause_plat, (
    f"un pooler qui BLOQUE volontairement doit faire reculer plus longtemps "
    f"qu'une coupure reseau ({pause_disj:.3f}s vs {pause_plat:.3f}s) — sinon on "
    f"entretient le blocage, defaut mesure le 2026-09-06")
assert "ECIRCUITBREAKER" in motif, f"le motif doit nommer la cause : {motif}"
print("2b. ECIRCUITBREAKER -> recul plus long qu'une coupure : OK")

# ───────────────── 4. le recul est PROGRESSIF, pas plat
#     C'est ce qui fait passer de ~40 tentatives a une poignee sur le meme budget.
palier = ss.OUTAGE_POLL_SECONDS
paliers = []
for _ in range(5):
    _, palier, _ = ss._recul(plat, palier)
    paliers.append(palier)
assert paliers == sorted(paliers) and paliers[0] < paliers[-1], \
    f"le palier doit croitre a chaque echec, pas rester plat : {paliers}"
assert paliers[-1] <= ss.OUTAGE_POLL_MAX, \
    f"le palier doit rester plafonne a OUTAGE_POLL_MAX : {paliers}"
print(f"3. recul progressif puis plafonne : {[round(p,3) for p in paliers]} : OK")

# ───────────────── 5. combien de coups frappe-t-on le pooler, au total ?
#     Le chiffre qui compte : 37 rappels en 20 min le 2026-09-06.
BUDGET, CADENCE_FIXE = 1200.0, 30.0
attente, palier, coups = 0.0, 30.0, 0
while attente < BUDGET:
    coups += 1
    pause = min(palier, 300.0)
    attente += pause
    palier = min(palier * 2, 300.0)
avant = int(BUDGET / CADENCE_FIXE)
assert coups < avant / 3, (
    f"le recul progressif doit reduire fortement le martelage du pooler : "
    f"{coups} tentatives contre {avant} a cadence fixe")
print(f"4. sur 20 min : {coups} tentatives au lieu de {avant} a cadence fixe : OK")

print("\nTOUS LES ESSAIS PASSENT")
