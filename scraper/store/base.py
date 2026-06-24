"""base.py — Interface de stockage.

Aujourd'hui : SqliteStore (local). Demain : SupabaseStore (online), même interface.
Le pipeline ne dépend que de cette interface → swap trivial.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseStore(ABC):
    @abstractmethod
    def get_listing(self, listing_id: str) -> dict | None: ...

    @abstractmethod
    def has_images(self, listing_id: str) -> bool: ...

    @abstractmethod
    def touch_listing(self, listing_id: str) -> None:
        """Marque une annonce vue (status active + last_seen=maintenant) sans
        re-télécharger la fiche/les images — pour la dédup incrémentale."""

    @abstractmethod
    def upsert_listing(self, norm: dict, images: list[dict] | None) -> tuple[str, float | None]:
        """Insère/maj une annonce. Retourne (statut, ancien_prix) où
        statut ∈ {"new","changed","unchanged"}. Enregistre price_history si besoin."""

    @abstractmethod
    def count_active(self, source: str, deal_type: str | None = None) -> int:
        """Nb d'annonces actives pour une source (et un deal_type si fourni).
        Sert au garde-fou anti-délistage massif."""

    @abstractmethod
    def mark_missing_inactive(self, source: str, seen_ids: set[str],
                              deal_type: str | None = None) -> list[str]:
        """Passe en inactive les annonces non revues. Retourne la liste des ids
        délistés (status→inactive, delisted_at=maintenant)."""

    @abstractmethod
    def get_image_paths(self, listing_id: str) -> list[str]:
        """Chemins Storage des images d'une annonce (pour suppression)."""

    @abstractmethod
    def delete_images(self, listing_id: str) -> None:
        """Supprime les lignes listing_images d'une annonce (fichiers délistés)."""

    @abstractmethod
    def record_scan_run(self, source: str, scanned: int, new: int,
                        removed: int, changed: int, notes: str = "") -> None: ...

    @abstractmethod
    def khet_stats(self) -> list[dict]: ...

    @abstractmethod
    def record_khet_snapshots(self) -> int:
        """Fige les stats par quartier dans khet_snapshots (comparaison par date)."""

    def close(self) -> None:  # optionnel
        pass
