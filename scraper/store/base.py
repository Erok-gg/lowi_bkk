"""base.py — Interface de stockage.

Aujourd'hui : SqliteStore (local). Demain : SupabaseStore (online), même interface.
Le pipeline ne dépend que de cette interface → swap trivial.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from pipeline import details

#: Colonnes de `listings` ecrites par les stores — EXEMPLAIRE UNIQUE.
#:
#: Elles etaient tenues a la main en DEUX exemplaires : `_COLS` dans
#: supabase_store.py et un tuple local a `upsert_listing` dans sqlite_store.py.
#: Mesure du 2026-08-25 avant de les fusionner : les deux listes etaient
#: identiques (49 colonnes de part et d'autre), donc la fusion est un no-op
#: semantique — mais rien ne garantissait qu'elles le restent, et la regle 6 du
#: CLAUDE.md (« une migration s'applique avec sa contrepartie cote code ») n'etait
#: appliquee par aucun controle. Une colonne ajoutee d'un seul cote fait echouer
#: le scrap suivant sur « column ... does not exist », cote online seulement.
#:
#: Les colonnes de detail viennent de `details.COLONNES` et ne sont JAMAIS
#: recopiees : une troisieme liste tenue a la main serait une troisieme facon de
#: diverger.
#:
#: Verifie par agents/tests/test_stores_alignes.py — qui compare cette liste aux
#: colonnes REELLES des deux bases, pas les deux listes entre elles.
#:
#: Depuis le 2026-08-25 cette liste est le SOCLE COMMUN : SQLite y ajoute
#: COLONNES_LOCALES (voir plus bas), Supabase non.
COLONNES_LISTING = (
    "source", "source_url", "title", "deal_type", "quota", "tenure", "price",
    "currency", "area_sqm", "price_per_sqm", "bedrooms", "bathrooms", "condo_name",
    "address_raw", "khet", "khwaeng", "street", "lat", "lng",
    # cohorte (robuste aux republications), age du batiment, empreinte photo
    "unit_key", "year_built", "photo_count", "photo_sizes",
    # provenance : qui publie, quand, et republication signalee par la source
    "agent_id", "agency_id", "posted_at", "is_auto_repost",
    # vendu/loue dit par la source, avant disparition (cf. fazwaz.statut_marche)
    "market_status",
    # details extraits du descriptif, derives de details.COLONNES (jamais recopies)
    *(c for c, _ in details.COLONNES),
)

#: Colonnes ecrites UNIQUEMENT en local (SQLite), jamais poussees vers Supabase.
#:
#: Decision du 2026-08-25. Ce sont les deux plus gros postes de la base et l'app
#: ne les lit JAMAIS — verifie fichier par fichier : aucun .ts/.tsx ne les
#: reference (le seul resultat, app/layout.tsx, est la balise meta HTML). Mesure
#: du jour : l'app lit ~22 Mo (listings utiles 18,6 + images 1,8 + prix 0,6 +
#: khet_snapshots 1,0) sur une base locale de 1,04 Go ; `page_text` pese a lui
#: seul 453,6 Mo en local et `description` 137,7 Mo.
#:
#: Les garder en ligne coutait 290 Mo sur un quota gratuit de 500 deja depasse
#: (810 Mo, soit 162 %). Ils restent la MATIERE PREMIERE qui permet de rejouer
#: une extraction sans re-scraper — d'ou leur conservation integrale en local,
#: qui est l'archive de reference. Le serveur n'est qu'une fenetre chaude.
#:
#: ATTENTION : PC2 en devient le seul detenteur. Le rapatriement prealable est
#: fait par ops/rapatrie-textes.py et la couverture verifiee par
#: ops/verifie-avant-degraissage.py — a rejouer avant toute suppression serveur.
COLONNES_LOCALES = ("description", "page_text")




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
    def ids_actifs(self, source: str, deal_type: str | None = None) -> set[str]:
        """Identifiants actifs d'une source. Le recensement (scraper/recense.py)
        s'en sert pour confronter le catalogue du site a ce que la base tient
        pour actif, SANS rien delister."""

    @abstractmethod
    def toucher_lot(self, ids, quand: str) -> int:
        """Rafraichit last_seen d'annonces confirmees presentes, en un appel.

        NE RESSUSCITE RIEN : seules les lignes deja 'active' sont touchees. Une
        annonce marquee vendue qui traine encore dans le catalogue le reste."""

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
