"""fetch.py — Couche HTTP : session navigateur, robots.txt, rate limiting.

Une seule Session persistante (cookies) : parcourir la liste AVANT les fiches
réchauffe les cookies anti-bot (ex. Cloudflare __cf_bm de DDproperty), ce qui
débloque les pages de détail. En-têtes navigateur réalistes ; pas de brotli
forcé (requests ne décode que gzip/deflate par défaut).

Deux backends de session, choisis par site via `fetcher_backend` dans
`config/<source>.json` (défaut "requests", inchangé) :
  - "requests"  : comportement historique, en-têtes Chrome-126 statiques.
  - "curl_cffi" : empreinte TLS/JA3 usurpée (impersonation Chrome réelle,
    en-têtes générés par curl_cffi lui-même — cohérents avec la version
    impersonée, donc PAS mélangés avec `_BROWSER_HEADERS`).
    ⚠ CORRIGÉ le 2026-10-20 : il était écrit ici « retries intégrés (3,
    backoff 1 s) ». FAUX — mesuré : `Session(impersonate="chrome").retry` =
    `RetryStrategy(count=0)`. Les 3 retries étaient ceux de
    `scrapling.FetcherSession`, abandonné le 29/08 ; DDproperty a tourné
    sept semaines sans aucune relance. Les relances vivent désormais dans
    `Fetcher._get()`, identiques pour les deux backends.
    Mesuré le 2026-08-29 : `curl_cffi.requests.Session` seul (sans passer
    par `scrapling.fetchers`, qui embarque patchright/browserforge en
    dépendance "fetchers" — inutile ici et ~110 Mo de plus) — API quasi
    identique à `requests` (`.get/.head`, `raise_for_status`, `.text`),
    donc aucune autre méthode de cette classe n'a besoin de brancher sur le
    backend. `scrapling` (sans extra) reste utilisé ailleurs (adaptateurs
    FazWaz/LivingInsider) pour le parsing adaptatif — capacité indépendante
    de ce module.

Deux modes de cadence, choisis par `throttle` dans la config (défaut "fixe") :
  - "fixe"      : délai = rate_limit × (1 + jitter), + pause longue 1 fois
    sur 25 — comportement historique.
  - "adaptatif" : délai piloté par la latence mesurée (algorithme
    `AutoThrottle` de scrapling 0.4.15, `spiders/throttle.py`, recopié plutôt
    qu'importé : son `Spider` est asynchrone et réécrirait les 5 adaptateurs).
    Part de `rate_limit_seconds`, converge vers max(latence, plancher), double
    sur 429/5xx ou suit `Retry-After`. Plus de pause longue. Le jitter reste.
    Pourquoi (mesuré le 2026-10-19) : ~52 min de sommeil volontaire par nuit
    contre ~11 min de réseau réel ; la latence des sites est de 0,3–0,7 s.
"""
from __future__ import annotations

import random
import re
import time
import urllib.robotparser
from urllib.parse import urljoin

import requests

from pipeline import chrono

# Relances sur réponse HTTP transitoire, UNE politique pour les deux backends.
# Historique : le 2026-09-02, un 522 Cloudflare isolé sur fazwaz ("requests",
# alors sans aucun retry) a fait échouer `sonder()` -> ticket `parser_break`
# haute sévérité alors qu'aucune structure n'avait changé (règle 2). La
# correction d'alors (urllib3 `Retry`) ne couvrait que "requests" — et
# curl_cffi, qu'on croyait doté de 3 retries, n'en avait aucun (count=0,
# mesuré le 2026-10-20). D'où une boucle unique dans `Fetcher._get()`.
# 429 ajouté le 2026-10-20 : un rate-limit perdait la fiche, sans recul.
_RETRY_STATUS = (429, 500, 502, 503, 504, 520, 521, 522, 523, 524, 525, 526, 527, 530)
#: Relances après le 1er essai (soit 4 requêtes au plus) — même budget que
#: l'urllib3 `Retry(total=3)` qu'elle remplace, verrouillé par test_fetch_retry.
_RETRY_COUNT = 3
_RETRY_BACKOFF = 1.0             # 1 s, 2 s, 4 s
#: Plafond d'un `Retry-After` honoré : au-delà, on rend la main (fiche perdue
#: pour ce run, reprise au suivant) plutôt que de geler le scan.
_RETRY_AFTER_MAX = 120.0

# Exceptions réseau à traiter comme un échec de requête récupérable, quel que
# soit le backend actif. curl_cffi n'est importé ici que si présent — le
# backend "requests" (par défaut, 5 sites sur 6) ne doit jamais l'exiger.
_REQUEST_EXC: tuple[type[Exception], ...] = (requests.RequestException,)
try:
    from curl_cffi.requests.exceptions import RequestException as _CurlRequestException
    _REQUEST_EXC = (requests.RequestException, _CurlRequestException)
except ImportError:
    pass

# Sous-ensemble de _REQUEST_EXC qui signifie « on n'a même pas atteint le
# site » (DNS, connexion refusée/impossible, délai dépassé) — PAR OPPOSITION à
# une réponse HTTP obtenue mais mauvaise (404, ou 5xx déjà épuisé par
# `_get()` : HTTPError). Distinction
# mesurée nécessaire : la coupure internet du script d'origine (`ops/
# superviseur.py`, retiré le 2026-07-31 lors du passage au système d'agents,
# sans remplacement — capacité perdue en silence, pas une decision) attendait
# le retour du réseau ; un 404 ou un 522 persistant, eux, n'ont RIEN à voir
# avec le réseau et ne doivent pas déclencher une attente de 20 minutes
# (verrouillé par test_fetch_retry.py : panne HTTP persistante -> None vite).
_COUPURE_EXC: tuple[type[Exception], ...] = (
    requests.exceptions.ConnectionError, requests.exceptions.Timeout,
)
try:
    from curl_cffi.requests.exceptions import ConnectionError as _CurlConnErr
    from curl_cffi.requests.exceptions import Timeout as _CurlTimeout
    _COUPURE_EXC = _COUPURE_EXC + (_CurlConnErr, _CurlTimeout)
except ImportError:
    pass

#: Cadence de sonde pendant une coupure — mêmes 30 s que l'ancien superviseur
#: (2026-08-01). La sonde EST la requête elle-même : "ce qui compte n'est pas
#: d'avoir une route, c'est que les sites répondent" (principe déjà posé).
OUTAGE_POLL_SECONDS = 30.0
#: Plafond d'attente INLINE avant d'abandonner cette URL et de laisser
#: `run.py` consigner un scan coupé plutôt que "complet" — 20 min : assez pour
#: un routeur qui redémarre, borné pour ne pas manger le budget de 6 h du
#: sous-processus (agents/core/shell.py) sur une seule page si la coupure est
#: bien plus longue. Une coupure qui dépasse ce plafond est reprise au
#: prochain déclenchement de l'orchestrateur (agents/orchestrator.py détecte
#: le marqueur [COUPURE-RESEAU] et redéclare la source due immédiatement),
#: pas par une attente indéfinie dans ce process.
OUTAGE_MAX_WAIT_SECONDS = 20 * 60.0

# Jitter anti-ban : chaque attente = délai de base × (1 + [0..JITTER_RATIO]).
# Jamais plus rapide que le débit configuré, mais variable au-dessus → cadence
# moins « robotique ». + pause longue occasionnelle (mime une lecture humaine).
_JITTER_RATIO = 0.8
_LONG_PAUSE_PROB = 0.04          # ~1 requête sur 25
_LONG_PAUSE_RANGE = (4.0, 9.0)   # secondes

_BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
              "image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
    "sec-ch-ua": '"Chromium";v="126", "Not:A-Brand";v="24", "Google Chrome";v="126"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}


class Robots:
    """Lecteur de robots.txt conforme au RFC 9309 — parce que la bibliotheque
    standard ne l'est pas, et que ca s'est vu.

    DEUX DEFAUTS DE `urllib.robotparser`, mesures le 2026-08-11 sur nestopa.com :

    1. UN SEUL BLOC `User-agent: *` EST RETENU.
           if "*" in entry.useragents:
               if self.default_entry is None:      # <- seulement si vide
                   self.default_entry = entry
       Les suivants sont jetes en silence. Or les robots.txt geres par Cloudflare
       ajoutent un bloc `*` en TETE (`Content-Signal`, `Allow: /`) avant celui du
       site. On ne voyait donc que le `Allow: /`.

    2. LA PREMIERE REGLE QUI CORRESPOND GAGNE, et les jokers ne sont pas geres :
       `/*?page=` etait encode en `/%2A%3Fpage%3D`, qui ne correspond a rien.

    Resultat : `respect_robots=True` autorisait `/dashboard`, `/api/` et
    `/*?page=` — tous interdits. Le scraper demandait ~300 URL interdites par
    cycle. Un garde-fou qui ne garde rien est pire que pas de garde-fou : il
    donne la conscience tranquille.

    Le RFC 9309 dit : la regle au chemin le PLUS LONG l'emporte ; a egalite,
    `Allow` gagne. C'est ce qui est implemente ici.
    """

    def __init__(self, texte: str, agent: str):
        self.regles: list[tuple[str, bool]] = []      # (motif, autorise)
        groupes: dict[str, list[tuple[str, bool]]] = {}
        agents_courants: list[str] = []
        attend_regles = False
        for ligne in texte.splitlines():
            nu = ligne.split("#")[0].strip()
            if not nu or ":" not in nu:
                continue
            cle, _, val = nu.partition(":")
            cle, val = cle.strip().lower(), val.strip()
            if cle == "user-agent":
                if attend_regles:
                    agents_courants = []
                    attend_regles = False
                agents_courants.append(val.lower())
            elif cle in ("allow", "disallow") and agents_courants:
                attend_regles = True
                for a in agents_courants:
                    groupes.setdefault(a, []).append((val, cle == "allow"))

        # Un groupe nomme qui nous vise l'emporte sur `*` (RFC 9309 §2.2.1).
        court = agent.split("/")[0].strip().lower()
        vise = [a for a in groupes if a != "*" and a and (a in court or court in a)]
        self.regles = groupes.get(vise[0], []) if vise else groupes.get("*", [])

    @staticmethod
    def _correspond(motif: str, chemin: str) -> bool:
        """`*` = n'importe quelle suite, `$` = fin de chaine. Le reste est litteral."""
        if not motif:
            return False
        fin = motif.endswith("$")
        m = motif[:-1] if fin else motif
        morceaux = m.split("*")
        pos = 0
        for i, mo in enumerate(morceaux):
            if not mo:
                continue
            if i == 0:
                if not chemin.startswith(mo):
                    return False
                pos = len(mo)
            else:
                j = chemin.find(mo, pos)
                if j < 0:
                    return False
                pos = j + len(mo)
        if fin:
            return pos == len(chemin) and (len(morceaux) == 1 or True) and chemin.endswith(morceaux[-1])
        return True

    def autorise(self, url: str) -> bool:
        from urllib.parse import urlsplit
        d = urlsplit(url)
        chemin = d.path + (("?" + d.query) if d.query else "")
        meilleure: tuple[int, bool] | None = None
        for motif, ok in self.regles:
            if not self._correspond(motif, chemin):
                continue
            poids = len(motif.replace("*", "").replace("$", ""))
            # a longueur egale, Allow l'emporte (RFC 9309)
            if meilleure is None or poids > meilleure[0] or (poids == meilleure[0] and ok):
                meilleure = (poids, ok)
        return meilleure[1] if meilleure else True


class Fetcher:
    def __init__(self, base_url: str, user_agent: str, rate_limit_seconds: float = 2.5,
                 timeout_seconds: int = 30, respect_robots: bool = True,
                 image_rate_limit_seconds: float = 0.4, backend: str = "requests",
                 outage_poll_seconds: float = OUTAGE_POLL_SECONDS,
                 outage_max_wait_seconds: float = OUTAGE_MAX_WAIT_SECONDS,
                 throttle: str = "fixe", rate_limit_floor_seconds: float = 1.0,
                 rate_limit_max_seconds: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.rate_limit = rate_limit_seconds
        self.image_rate_limit = image_rate_limit_seconds
        self.timeout = timeout_seconds
        self.respect_robots = respect_robots
        self.backend = backend
        self.outage_poll_seconds = outage_poll_seconds
        self.outage_max_wait_seconds = outage_max_wait_seconds
        # Posé à True dès qu'UNE requête a dû attendre le plafond ci-dessus
        # sans que le réseau revienne — lu par run.py en fin de scan pour
        # distinguer "coupure" de "fin de liste normale" (voir _COUPURE_EXC).
        self.a_subi_coupure = False
        self._last_request = 0.0
        if throttle not in ("fixe", "adaptatif"):
            raise ValueError(f"throttle inconnu : {throttle!r} (fixe|adaptatif)")
        self.throttle = throttle
        self.floor = rate_limit_floor_seconds
        self.max_delay = max(rate_limit_max_seconds, rate_limit_seconds)
        # Délai courant du mode adaptatif. Démarre au débit configuré (prudent),
        # puis suit la latence — comme AutoThrottle.start_delay.
        self._delai = rate_limit_seconds
        #: Statuts HTTP vus, pour le bilan de fin de run et le test longue série.
        self.statuts: dict[int, int] = {}
        if backend == "curl_cffi":
            from curl_cffi.requests import Session as CurlSession
            # Pas de `_BROWSER_HEADERS` ici : curl_cffi génère déjà un jeu
            # d'en-têtes cohérent avec la version Chrome qu'il impersone
            # (sec-ch-ua, Accept, Accept-Encoding avec brotli qu'il décode
            # nativement — vérifié le 2026-08-29). Les mélanger figerait
            # sec-ch-ua sur Chrome 126 pendant que la signature TLS avance,
            # un décalage que les anti-bots regardent justement.
            self._session = CurlSession(impersonate="chrome")
        else:
            self._session = requests.Session()
            self._session.headers.update({"User-Agent": user_agent, **_BROWSER_HEADERS})
        self._robots = self._load_robots() if respect_robots else None

    def _load_robots(self):
        # On récupère robots.txt via NOTRE session (en-têtes navigateur) : le
        # robotparser natif fait une requête urllib brute qui se fait souvent
        # servir un challenge Cloudflare, mal parsé → tout interdit (faux négatif).
        url = urljoin(self.base_url + "/", "robots.txt")
        try:
            r = self._session.get(url, timeout=self.timeout)
            text = r.text if r.status_code == 200 else ""
        except _REQUEST_EXC:
            text = ""
        low = text.lower()
        looks_like_robots = "disallow" in low or "user-agent" in low
        if not looks_like_robots or "just a moment" in low or "<html" in low[:200]:
            print("  robots.txt illisible (challenge/erreur) → accès autorisé par défaut (RFC)")
            return None
        return Robots(text, self.user_agent)

    def allowed(self, url: str) -> bool:
        if not self._robots:
            return True
        return self._robots.autorise(url)

    def _throttle(self, base_delay: float, allow_long_pause: bool = False):
        # délai cible randomisé (jitter), jamais sous le débit configuré
        delay = base_delay * (1.0 + random.random() * _JITTER_RATIO)
        if allow_long_pause and self.throttle == "fixe" and random.random() < _LONG_PAUSE_PROB:
            delay += random.uniform(*_LONG_PAUSE_RANGE)
        elapsed = time.time() - self._last_request
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_request = time.time()

    def _ajuste(self, latence: float, ok: bool, retry_after: float | None) -> None:
        """AutoThrottle (scrapling 0.4.15, `spiders/throttle.py::record`),
        concurrence cible 1 : chaque Fetcher est un onglet séquentiel.
        Succès : moyenne entre le délai courant et la latence, jamais sous la
        latence (le serveur dit lui-même ce qu'il encaisse). Échec : jamais
        plus rapide — `Retry-After` s'il est donné, sinon délai × 2."""
        if self.throttle != "adaptatif":
            return
        cur = self._delai
        nouveau = max((cur + latence) / 2, latence)
        if not ok:
            penalite = retry_after if retry_after is not None else cur * 2.0
            nouveau = max(nouveau, penalite, cur)
        self._delai = min(max(nouveau, self.floor), self.max_delay)

    @staticmethod
    def _retry_after(r) -> float | None:
        v = (r.headers.get("retry-after") or "").strip()
        if not v:
            return None
        try:
            return max(float(v), 0.0)
        except ValueError:
            pass
        try:  # date HTTP plutôt qu'un nombre de secondes
            from email.utils import parsedate_to_datetime
            from datetime import datetime, timezone
            return max((parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds(), 0.0)
        except (TypeError, ValueError):
            return None

    def _get(self, url: str, poste: str, ajuste: bool = True, **kw):
        """GET avec la politique de relance commune (voir `_RETRY_STATUS`).
        Lève l'exception réseau telle quelle (le chemin coupure la traite) ;
        lève HTTPError si le statut reste mauvais après les relances.
        `ajuste=False` pour les images : elles viennent d'un CDN, leur latence
        ne dit rien de ce qu'encaisse le site, et ne doit pas régler sa cadence."""
        for essai in range(_RETRY_COUNT + 1):
            t0 = time.perf_counter()
            with chrono.mesure(poste):
                r = self._session.get(url, timeout=self.timeout, **kw)
            latence = time.perf_counter() - t0
            self.statuts[r.status_code] = self.statuts.get(r.status_code, 0) + 1
            if r.status_code not in _RETRY_STATUS:
                if ajuste:
                    self._ajuste(latence, r.status_code < 400, None)
                r.raise_for_status()
                return r
            ra = self._retry_after(r)
            if ajuste:
                self._ajuste(latence, False, ra)
            if essai == _RETRY_COUNT:
                r.raise_for_status()
            if ra is not None and ra > _RETRY_AFTER_MAX:
                print(f"  {r.status_code} sur {url} : Retry-After {ra:.0f}s > plafond, abandon")
                r.raise_for_status()
            attente = ra if ra is not None else _RETRY_BACKOFF * (2 ** essai)
            print(f"  {r.status_code} sur {url} — relance {essai + 1}/{_RETRY_COUNT} dans {attente:.0f}s",
                  flush=True)
            time.sleep(attente)
        raise AssertionError("inatteignable")

    def _attend_coupure(self, url: str) -> None:
        """Bloque jusqu'au retour du réseau (sonde = re-essayer `url` elle-même,
        toutes les `outage_poll_seconds`), ou jusqu'à `outage_max_wait_seconds`.

        Appelé UNIQUEMENT sur une exception de `_COUPURE_EXC` (DNS, connexion
        refusée/impossible, timeout) — jamais sur un 4xx/5xx, qui prouve déjà
        que le site est joignable. Repris de `ops/superviseur.py` (2026-08-01,
        retiré depuis), mais posé DANS le code du fetcher plutôt que dans un
        script wrapper externe — pour ne plus dépendre de l'existence d'un
        superviseur séparé."""
        attente = 0.0
        while attente < self.outage_max_wait_seconds:
            print(f"  ⚠ coupure réseau supposée sur {url} — sonde dans "
                  f"{self.outage_poll_seconds:.0f}s (attente cumulée {attente:.0f}s"
                  f"/{self.outage_max_wait_seconds:.0f}s)", flush=True)
            time.sleep(self.outage_poll_seconds)
            attente += self.outage_poll_seconds
            try:
                self._session.get(url, timeout=min(self.timeout, 10))
                print(f"  ✓ réseau revenu après {attente:.0f}s — reprise", flush=True)
                return
            except _COUPURE_EXC:
                continue
        self.a_subi_coupure = True
        print(f"  ✗ coupure réseau non résolue après {attente:.0f}s — abandon de {url}",
              flush=True)

    def get_text(self, url: str, referer: str | None = None) -> str | None:
        if self.respect_robots and not self.allowed(url):
            print(f"  robots.txt interdit : {url}")
            return None
        # Trace de PAGE DE LISTE. Sans elle, impossible de savoir ou en est un
        # scan : les logs ne montraient que `max_pages=150` au demarrage, puis
        # des milliers de lignes d'annonces sans aucun reperage.
        m = re.search(r"[?&](?:page|p)=(\d+)", url)
        if m:
            print(f"  ── page {m.group(1)}/{getattr(self, 'max_pages', '?')} "
                  f"({url.split('?')[0].rsplit('/', 1)[-1] or 'liste'})", flush=True)
        elif re.search(r"/page-(\d+)", url):
            n = re.search(r"/page-(\d+)", url).group(1)
            print(f"  ── page {n}/{getattr(self, 'max_pages', '?')}", flush=True)
        # `est_liste` sert UNIQUEMENT au chronomètre : la page de liste et la
        # fiche de détail ont des coûts très différents, et les confondre a
        # produit une estimation fausse le 2026-08-11.
        est_liste = bool(m) or bool(re.search(r"/page-(\d+)", url)) or "?" in url
        poste = "attente_liste" if est_liste else "attente_fiche"
        base = self._delai if self.throttle == "adaptatif" else self.rate_limit
        with chrono.mesure(poste):
            self._throttle(base, allow_long_pause=True)
        headers = {"Referer": referer, "Sec-Fetch-Site": "same-origin"} if referer else {}
        reseau = "reseau_liste" if est_liste else "reseau_fiche"
        try:
            return self._get(url, reseau, headers=headers).text
        except _COUPURE_EXC as e:
            print(f"  échec GET {url} (coupure ?) : {e}")
            self._attend_coupure(url)
            if self.a_subi_coupure:
                return None
            try:  # réseau revenu pendant l'attente -> un seul nouvel essai
                return self._get(url, reseau, headers=headers).text
            except _REQUEST_EXC as e2:
                print(f"  échec GET {url} (après retour réseau) : {e2}")
                return None
        except _REQUEST_EXC as e:
            print(f"  échec GET {url} : {e}")
            return None

    def head_size(self, url: str) -> int | None:
        """Poids d'un fichier distant sans le télécharger (Content-Length).

        Sert à empreinter les photos d'une annonce : un agent qui republie
        réutilise les mêmes fichiers, donc les mêmes poids. Aucun octet
        transféré, aucun stockage — contrainte du plan gratuit.
        """
        with chrono.mesure("attente_empreinte"):
            self._throttle(self.image_rate_limit)
        try:
            with chrono.mesure("reseau_empreinte"):
                r = self._session.head(url, timeout=self.timeout, allow_redirects=True)
            if r.status_code >= 400 or "content-length" not in r.headers:
                return None
            return int(r.headers["content-length"])
        except (*_REQUEST_EXC, ValueError):
            return None

    def get_bytes(self, url: str) -> bytes | None:
        # images CDN : débit plus rapide (hors site principal)
        with chrono.mesure("attente_image"):
            self._throttle(self.image_rate_limit)
        try:
            return self._get(url, "reseau_image", ajuste=False).content
        except _COUPURE_EXC as e:
            print(f"  échec GET (bytes) {url} (coupure ?) : {e}")
            self._attend_coupure(url)
            if self.a_subi_coupure:
                return None
            try:
                return self._get(url, "reseau_image", ajuste=False).content
            except _REQUEST_EXC as e2:
                print(f"  échec GET (bytes) {url} (après retour réseau) : {e2}")
                return None
        except _REQUEST_EXC as e:
            print(f"  échec GET (bytes) {url} : {e}")
            return None
