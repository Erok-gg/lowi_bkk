"""fetch.py — Couche HTTP : session navigateur, robots.txt, rate limiting.

Une seule Session persistante (cookies) : parcourir la liste AVANT les fiches
réchauffe les cookies anti-bot (ex. Cloudflare __cf_bm de DDproperty), ce qui
débloque les pages de détail. En-têtes navigateur réalistes ; pas de brotli
forcé (requests ne décode que gzip/deflate par défaut).
"""
from __future__ import annotations

import random
import time
import urllib.robotparser
from urllib.parse import urljoin

import requests

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
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(text.splitlines())
        return rp

    def allowed(self, url: str) -> bool:
        if not self._robots:
            return True
        return self._robots.can_fetch(self.user_agent, url)

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
        self._throttle(self.rate_limit, allow_long_pause=True)
        headers = {"Referer": referer, "Sec-Fetch-Site": "same-origin"} if referer else {}
        try:
            r = self._session.get(url, headers=headers, timeout=self.timeout)
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            print(f"  échec GET {url} : {e}")
            return None

    def get_bytes(self, url: str) -> bytes | None:
        # images CDN : débit plus rapide (hors site principal)
        self._throttle(self.image_rate_limit)
        try:
            r = self._session.get(url, timeout=self.timeout)
            r.raise_for_status()
            return r.content
        except requests.RequestException as e:
            print(f"  échec GET (bytes) {url} : {e}")
            return None
