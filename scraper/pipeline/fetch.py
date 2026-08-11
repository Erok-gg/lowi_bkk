"""fetch.py — Couche HTTP : session navigateur, robots.txt, rate limiting.

Une seule Session persistante (cookies) : parcourir la liste AVANT les fiches
réchauffe les cookies anti-bot (ex. Cloudflare __cf_bm de DDproperty), ce qui
débloque les pages de détail. En-têtes navigateur réalistes ; pas de brotli
forcé (requests ne décode que gzip/deflate par défaut).
"""
from __future__ import annotations

import random
import re
import time
import urllib.robotparser
from urllib.parse import urljoin

import requests

from pipeline import chrono

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
                 image_rate_limit_seconds: float = 0.4):
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.rate_limit = rate_limit_seconds
        self.image_rate_limit = image_rate_limit_seconds
        self.timeout = timeout_seconds
        self.respect_robots = respect_robots
        self._last_request = 0.0
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
        except requests.RequestException:
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
        if allow_long_pause and random.random() < _LONG_PAUSE_PROB:
            delay += random.uniform(*_LONG_PAUSE_RANGE)
        elapsed = time.time() - self._last_request
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_request = time.time()

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
        with chrono.mesure(poste):
            self._throttle(self.rate_limit, allow_long_pause=True)
        headers = {"Referer": referer, "Sec-Fetch-Site": "same-origin"} if referer else {}
        try:
            with chrono.mesure("reseau_liste" if est_liste else "reseau_fiche"):
                r = self._session.get(url, headers=headers, timeout=self.timeout)
                r.raise_for_status()
                return r.text
        except requests.RequestException as e:
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
        except (requests.RequestException, ValueError):
            return None

    def get_bytes(self, url: str) -> bytes | None:
        # images CDN : débit plus rapide (hors site principal)
        with chrono.mesure("attente_image"):
            self._throttle(self.image_rate_limit)
        try:
            with chrono.mesure("reseau_image"):
                r = self._session.get(url, timeout=self.timeout)
                r.raise_for_status()
                return r.content
        except requests.RequestException as e:
            print(f"  échec GET (bytes) {url} : {e}")
            return None
