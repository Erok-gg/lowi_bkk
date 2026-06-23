"""geocode.py — Géocodage des condos via Nominatim (OpenStreetMap).

But : compléter `street` (+ `lat`/`lng`/`khet` si absents) à partir du nom du
condo. Gratuit, mais **1 req/s** obligatoire (politique d'usage Nominatim) et UA
honnête. Un **cache disque** (clé = condo normalisé + khet) évite toute requête
répétée — on ne sollicite Nominatim qu'une fois par condo, jamais davantage.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "lowi-bkk/1.0 (personal real-estate map; contact: schoenauer.anthony@gmail.com)"
_CACHE_PATH = Path(__file__).resolve().parents[1] / "output" / "geocode-cache.json"
_MIN_INTERVAL = 1.1  # secondes entre deux requêtes Nominatim


def _norm(condo: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", condo.split(",")[0].lower())).strip()


class Geocoder:
    def __init__(self, cache_path: Path = _CACHE_PATH):
        self.cache_path = cache_path
        self.cache: dict[str, dict | None] = {}
        if cache_path.exists():
            try:
                self.cache = json.loads(cache_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.cache = {}
        self._last = 0.0

    def _save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=0), encoding="utf-8")

    def _throttle(self) -> None:
        dt = time.monotonic() - self._last
        if dt < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - dt)
        self._last = time.monotonic()

    def _query(self, q: str) -> dict | None:
        self._throttle()
        url = f"{NOMINATIM}?{urlencode({'q': q, 'format': 'jsonv2', 'addressdetails': 1, 'limit': 1, 'countrycodes': 'th'})}"
        req = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en"})
        try:
            with urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception:
            return None
        if not data:
            return None
        hit = data[0]
        addr = hit.get("address", {})
        street = addr.get("road") or addr.get("neighbourhood") or addr.get("suburb")
        return {
            "street": street,
            "lat": float(hit["lat"]) if hit.get("lat") else None,
            "lng": float(hit["lon"]) if hit.get("lon") else None,
        }

    def lookup(self, condo_name: str | None, khet: str | None) -> dict | None:
        """Retourne {street, lat, lng} (valeurs possiblement None) ou None si rien.

        Met en cache même les échecs (valeur None) pour ne jamais re-tenter.
        """
        if not condo_name:
            return None
        key = f"{_norm(condo_name)}|{khet or ''}"
        if key in self.cache:
            return self.cache[key]
        q = condo_name.split(",")[0]
        if khet:
            q = f"{q}, {khet.replace(' District', '')}, Bangkok"
        else:
            q = f"{q}, Bangkok"
        res = self._query(q)
        self.cache[key] = res
        self._save()
        return res
