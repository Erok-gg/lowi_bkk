"""base.py — Interface commune des adaptateurs de site.

Ajouter un site = créer un module dans adapters/ qui sous-classe BaseAdapter
et implémente list_urls() + parse_listing(). Aucune autre partie du pipeline
ne dépend du site.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

from pipeline.fetch import Fetcher


class BaseAdapter(ABC):
    #: identifiant court du site (= colonne `source`)
    source: str = "base"

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def list_urls(self, fetcher: Fetcher, limit: int | None = None) -> Iterator[dict]:
        """Génère des "stubs" d'annonces (dicts) depuis les pages de liste.

        Chaque stub DOIT contenir au minimum `source_url`. Il peut déjà porter
        des champs pré-parsés (nom, prix, surface, lat/lng…) pour éviter une
        requête de détail.
        """
        raise NotImplementedError

    @abstractmethod
    def parse_listing(self, fetcher: Fetcher, stub: dict) -> dict | None:
        """Transforme un stub en enregistrement brut (proche du schéma normalisé).

        Peut enrichir via la page de détail si nécessaire. Retourne None si
        l'annonce doit être ignorée.
        """
        raise NotImplementedError

    def sonder(self, fetcher: Fetcher) -> tuple[bool, str]:
        """Test de structure AVANT le scan complet (page 1 seulement).

        2026-08-17 : jusqu'ici, un marqueur de structure absent (JSON-LD,
        __NEXT_DATA__…) se traduit par un simple `break` silencieux dans
        `list_urls` — 0 annonce, indiscernable d'une recherche réellement
        vide. `watch-health` finit par le voir, mais seulement après 2 runs
        consécutifs à zéro (pour ne pas crier au loup sur un aléa isolé) —
        jusqu'à 8 jours de scans pour rien avant qu'un ticket parte à Claude.

        Implémentation par défaut : réutilise `list_urls` (le VRAI parseur,
        pas une copie qui pourrait diverger) avec `limit=1`. Chaque
        adaptateur SURCHARGE cette méthode pour vérifier d'abord la présence
        de son marqueur de structure spécifique — le diagnostic doit nommer
        CE marqueur, pas juste dire "ça ne marche pas", pour que le ticket
        remonté à Claude pointe déjà la bonne piste."""
        try:
            stub = next(self.list_urls(fetcher, limit=1), None)
        except Exception as e:                                  # noqa: BLE001
            return False, f"{type(e).__name__}: {e}"
        if stub is None:
            return False, "page 1 : 0 annonce reconnue (liste vide ou structure changée)"
        if not stub.get("source_id"):
            return False, "page 1 : stub sans source_id — la page répond mais l'identifiant n'est pas extrait"
        return True, f"page 1 ok — 1 stub obtenu ({stub['source_id']})"
