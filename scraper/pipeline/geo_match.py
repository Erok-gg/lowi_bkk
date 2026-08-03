"""geo_match.py — Associe un point (lat/lng) à un Khet via point-in-polygon,
contre public/data/bangkok-khet.geojson. Sans dépendance (ray casting).
"""
from __future__ import annotations

import json
from pathlib import Path

_GEOJSON = (
    Path(__file__).resolve().parents[2] / "public" / "data" / "bangkok-khet.geojson"
)


class KhetMatcher:
    def __init__(self, geojson_path: Path = _GEOJSON):
        self.khets: list[tuple[str, list]] = []  # (name, list[ring polygons])
        if geojson_path.exists():
            data = json.loads(geojson_path.read_text(encoding="utf-8"))
            for f in data.get("features", []):
                name = (f.get("properties") or {}).get("name_en") or (
                    f.get("properties") or {}
                ).get("name")
                geom = f.get("geometry") or {}
                polys = self._extract_polygons(geom)
                if name and polys:
                    self.khets.append((name, polys))

    @staticmethod
    def _extract_polygons(geom: dict) -> list:
        t = geom.get("type")
        coords = geom.get("coordinates")
        if t == "Polygon":
            return [coords]  # 1 polygon = [outer_ring, holes...]
        if t == "MultiPolygon":
            return coords  # list of polygons
        return []

    @staticmethod
    def _point_in_ring(x: float, y: float, ring: list) -> bool:
        inside = False
        n = len(ring)
        j = n - 1
        for i in range(n):
            xi, yi = ring[i][0], ring[i][1]
            xj, yj = ring[j][0], ring[j][1]
            if ((yi > y) != (yj > y)) and (
                x < (xj - xi) * (y - yi) / (yj - yi + 1e-15) + xi
            ):
                inside = not inside
            j = i
        return inside

    def _point_in_polygon(self, x: float, y: float, polygon: list) -> bool:
        if not polygon or not self._point_in_ring(x, y, polygon[0]):
            return False
        # exclut les trous
        for hole in polygon[1:]:
            if self._point_in_ring(x, y, hole):
                return False
        return True

    def match(self, lat: float | None, lng: float | None) -> str | None:
        if lat is None or lng is None:
            return None
        for name, polys in self.khets:
            for polygon in polys:
                if self._point_in_polygon(lng, lat, polygon):
                    return name
        return None

    @staticmethod
    def _cle(texte: str) -> str:
        """Forme comparable d'un nom de quartier : casse, espaces, suffixe."""
        import re
        s = re.sub(r"\s+", " ", (texte or "").strip().lower())
        return re.sub(r"\s*district\s*$", "", s).strip()

    def canoniser(self, texte: str | None) -> str | None:
        """Ramène un libellé de source au nom du découpage, ou None si inconnu.

        POURQUOI. Quand `match()` échoue — point hors polygone, coordonnées
        absentes — le libellé brut de la source passait TEL QUEL en base. Les
        sources écrivent « Bang Na », le découpage dit « Bang Na District » :
        deux valeurs pour un même quartier.

        Constaté le 2026-08-03 en regardant une capture du tableau des
        rendements : « Bang Na » y figurait DEUX FOIS, à 6,1 % sur 3 immeubles
        et à 5,6 % sur 45. L'affichage retire le suffixe, donc les deux lignes
        deviennent identiques à l'œil — un quartier fantôme dans le palmarès,
        qu'un lecteur ne peut pas interpréter.

        Sept quartiers étaient touchés (Khlong Toei, Pathum Wan, Huai Khwang,
        Sathon, Bang Rak, Chatuchak, Bang Na) pour 34 annonces. Six anecdotiques,
        Bang Na non : ses 27 annonces suffisaient à produire une ligne complète.

        On rend None plutôt qu'une approximation quand le nom est inconnu :
        l'appelant garde alors le texte d'origine. Perdre une information vaut
        mieux que la remplacer par une autre.
        """
        if not texte:
            return None
        if not hasattr(self, "_index"):
            self._index = {self._cle(n): n for n, _ in self.khets}
        return self._index.get(self._cle(texte))
