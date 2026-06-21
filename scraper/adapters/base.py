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
