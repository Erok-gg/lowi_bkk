"""supabase_store.py — Stockage ONLINE (Postgres Supabase) via psycopg.

Même interface que SqliteStore (BaseStore) → le pipeline ne change pas.
Connexion Postgres directe (pooler session) → bypass RLS (utilisateur postgres).
DSN lu depuis SUPABASE_DB_URL.
"""
from __future__ import annotations

from datetime import datetime, timezone

import psycopg
from psycopg.types.json import Json

from pipeline import details
from store.base import COLONNES_LISTING, BaseStore

#: Exemplaire unique dans store/base.py — la liste etait tenue a la main ici ET
#: dans sqlite_store.upsert_listing (identiques a la mesure du 2026-08-25, mais
#: rien ne l'imposait). Alias conserve : `_COLS` est utilise plus bas.
_COLS = COLONNES_LISTING


#: Colonnes BOOLÉENNES côté Postgres. SQLite n'a pas de type booléen et y range
#: des entiers 0/1 : les transférer tels quels casse l'écriture en ligne
#: (« column d_animaux_ok is of type boolean but expression is of type smallint »).
#: C'est la même famille de divergence entre les deux stores que `median_price`
#: (moyenne en SQLite, médiane en Postgres) corrigée le 2026-07-28.
#: La conversion est faite ICI plutôt que chez l'appelant : tout chemin d'écriture
#: en profite, y compris `ops/remonter-local.py`.
_BOOLEENNES = ("is_auto_repost", "d_animaux_ok", "d_livre")


def _coerce(col: str, v):
    if v is None or col not in _BOOLEENNES:
        return v
    return bool(v)


#: Jours pendant lesquels une annonce doit rester marquee vendue avant de
#: quitter le stock actif. Decide le 2026-08-03.
#:
#: Le delai n'est pas de la prudence de facade : un badge « Sold » peut etre
#: transitoire — vente qui capote, erreur d'agent. Sept jours de persistance en
#: font une preuve. Meme principe que `missed_count`, ou une annonce doit
#: manquer a plusieurs scans CONSECUTIFS avant d'etre delistee : on exige de la
#: DUREE, jamais une observation isolee.
JOURS_AVANT_SORTIE_VENDU = 7


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SupabaseStore(BaseStore):
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.db = psycopg.connect(dsn, connect_timeout=20, autocommit=True)
        self._migrate()

    def _migrate(self) -> None:
        """Migrations légères idempotentes (colonnes ajoutées après coup)."""
        try:
            self._execute(
                "alter table khet_snapshots add column if not exists deal_type text"
            )
        except Exception:
            pass

    def _reconnect(self) -> None:
        try:
            self.db.close()
        except Exception:
            pass
        self.db = psycopg.connect(self.dsn, connect_timeout=20, autocommit=True)

    def _execute(self, sql: str, params=()):
        """execute avec reconnexion auto si la connexion Postgres a sauté
        (blip réseau / timeout pooler) → un blip ne tue plus le run."""
        try:
            return self.db.execute(sql, params)
        except (psycopg.OperationalError, psycopg.InterfaceError):
            self._reconnect()
            return self.db.execute(sql, params)

    def get_listing(self, listing_id: str) -> dict | None:
        row = self._execute(
            "select id, price from listings where id=%s", (listing_id,)
        ).fetchone()
        return {"id": row[0], "price": row[1]} if row else None

    def has_images(self, listing_id: str) -> bool:
        return self._execute(
            "select 1 from listing_images where listing_id=%s limit 1", (listing_id,)
        ).fetchone() is not None

    def touch_listing(self, listing_id: str) -> None:
        # Revue = série d'absences interrompue : on remet le compteur à zéro.
        self._execute(
            "update listings set status='active', last_seen=%s,"
            " missed_count=0, first_missed_at=null,delisted_at=null where id=%s",
            (_now(), listing_id),
        )

    def upsert_listing(self, norm: dict, images: list[dict] | None) -> tuple[str, float | None]:
        existing = self.get_listing(norm["id"])
        now = _now()
        vals = [_coerce(c, norm.get(c)) for c in _COLS]

        if existing is None:
            placeholders = ",".join(["%s"] * (len(_COLS) + 5))  # id + cols + status + 2 dates + raw_data
            self._execute(
                f"insert into listings (id,{','.join(_COLS)},status,first_seen,last_seen,raw_data) "
                f"values ({placeholders})",
                (norm["id"], *vals, "active", now, now, Json(norm.get("raw_data", {}))),
            )
            if norm.get("price") is not None:
                self._add_price(norm["id"], norm["price"], now)
            if norm.get("posted_at"):
                self._add_posted_at(norm["id"], norm["posted_at"], now)
            self._set_images(norm["id"], images)
            # amenities NON poussees depuis le 2026-08-25 : l'app renvoie
            # `amenities: []` en dur (lib/listings-db.ts:95) et ne lit donc
            # jamais cette table, qui pesait 70 Mo en ligne. Elle continue
            # d'etre remplie en local.
            return "new", None

        old_price = existing["price"]
        new_price = norm.get("price")
        # AVANT l'écrasement — cf. SqliteStore._track_posted_at pour le pourquoi.
        self._track_posted_at(existing, norm.get("posted_at"), now)
        self._suivre_statut_marche(existing, norm.get("market_status"), now)
        set_clause = ",".join(f"{c}=%s" for c in _COLS)
        self._execute(
            f"update listings set {set_clause},status='active',last_seen=%s,raw_data=%s,"
            f"missed_count=0,first_missed_at=null,delisted_at=null where id=%s",
            (*vals, now, Json(norm.get("raw_data", {})), norm["id"]),
        )
        status = "unchanged"
        if new_price is not None and old_price is not None and float(new_price) != float(old_price):
            self._add_price(norm["id"], new_price, now)
            status = "changed"
        if images is not None:
            self._set_images(norm["id"], images)
        return status, old_price

    def _add_price(self, listing_id: str, price: float, when: str) -> None:
        self._execute(
            "insert into price_history (listing_id,price,observed_at) values (%s,%s,%s)",
            (listing_id, price, when),
        )

    def _add_posted_at(self, listing_id: str, valeur, when: str) -> None:
        self._execute(
            "insert into posted_at_history (listing_id,posted_at,observed_at) "
            "values (%s,%s,%s)", (listing_id, valeur, when),
        )

    def _track_posted_at(self, existing, nouveau, when: str) -> None:
        """Historise `posted_at` quand il CHANGE — cf. SqliteStore._track_posted_at.

        Tant que `posted_at_history` est vide, `posted_at` NE remplace PAS
        `first_seen` dans le time-on-market : mesuré à -16 jours d'écart médian,
        il se comporte comme une date de remontée, pas de publication.
        """
        if not nouveau:
            return
        try:
            ancien = existing["posted_at"]
        except (KeyError, IndexError):
            return
        if ancien and str(ancien) == str(nouveau):
            return
        self._add_posted_at(existing["id"], nouveau, when)

    def _set_images(self, listing_id: str, images: list[dict] | None) -> None:
        if images is None:
            return
        self._execute("delete from listing_images where listing_id=%s", (listing_id,))
        for im in images:
            self._execute(
                "insert into listing_images (listing_id,storage_path,width,height,ord) "
                "values (%s,%s,%s,%s,%s)",
                (listing_id, im["storage_path"], im.get("width"), im.get("height"), im.get("ord", 0)),
            )

    def _set_amenities(self, listing_id: str, amenities: list[str]) -> None:
        self._execute("delete from listing_amenities where listing_id=%s", (listing_id,))
        for a in amenities:
            self._execute(
                "insert into listing_amenities (listing_id,name) values (%s,%s)", (listing_id, a)
            )

    def count_active(self, source: str, deal_type: str | None = None) -> int:
        q = "select count(*) from listings where source=%s and status='active'"
        params: list = [source]
        if deal_type:
            q += " and deal_type=%s"
            params.append(deal_type)
        return self._execute(q, params).fetchone()[0]

    def _suivre_statut_marche(self, existant, nouveau, maintenant) -> None:
        """Date la PREMIERE apparition de la valeur courante de market_status.

        Ne bouge que sur CHANGEMENT. Sans ca, `market_status_since` suivrait
        `last_seen` et la regle des sept jours ne se declencherait jamais : elle
        compterait toujours zero jour d'anciennete.
        """
        try:
            ancien = existant["market_status"]
        except (KeyError, IndexError, TypeError):
            return
        if (ancien or None) == (nouveau or None):
            return
        self._maj_since(existant["id"], maintenant if nouveau else None)

    def _maj_since(self, lid, quand) -> None:
        self._execute("update listings set market_status_since=%s where id=%s", (quand, lid))

    def appliquer_ventes(self, jours: int = JOURS_AVANT_SORTIE_VENDU) -> int:
        """Sort du stock actif les annonces marquees vendues depuis `jours`.

        `status='sold'` est DISTINCT de `'inactive'` : l'annonce n'a pas disparu,
        la source dit qu'elle est vendue. Confondre les deux ferait perdre
        exactement l'information qu'on vient de gagner — le delistage confond
        vente, retrait et artefact de fenetre, ce marqueur les separe.

        `delisted_at` recoit la date de PREMIERE apparition du marqueur, pas
        celle du jour : c'est la date ou le lot a quitte le marche, et c'est elle
        qui doit compter dans les analyses de tension.
        """
        cur = self._execute(
            "update listings set status='sold', delisted_at=market_status_since "
            "where market_status='sold' and status='active' "
            "  and market_status_since is not null "
            f"  and market_status_since <= now() - interval '{int(jours)} days'")
        return cur.rowcount if cur is not None else 0

    def ids_actifs(self, source: str, deal_type: str | None = None) -> set[str]:
        q = "select id from listings where source=%s and status='active'"
        params: list = [source]
        if deal_type:
            q += " and deal_type=%s"
            params.append(deal_type)
        return {r[0] for r in self._execute(q, params).fetchall()}

    def toucher_lot(self, ids, quand: str) -> int:
        """Un seul aller-retour pour ~30 000 identifiants.

        `touch_listing` en boucle aurait coute autant de requetes que d'annonces
        confirmees — sur un recensement, c'est le tiers du temps total pour un
        travail que Postgres fait en une passe."""
        ids = list(ids)
        if not ids:
            return 0
        touchees = 0
        for i in range(0, len(ids), 5000):          # lot borne : evite un array geant
            rows = self._execute(
                "update listings set last_seen=%s, missed_count=0,"
                " first_missed_at=null"
                " where id = any(%s) and status='active' returning id",
                (quand, ids[i:i + 5000]),
            ).fetchall()
            touchees += len(rows)
        return touchees

    def mark_missing_inactive(self, source: str, seen_ids: set[str],
                              deal_type: str | None = None,
                              grace: int = 2) -> list[str]:
        """Délistage avec délai de grâce : une annonce doit manquer à `grace`
        scans CONSÉCUTIFS avant d'être marquée inactive.

        Sans ce délai, la troncature du scan à max_pages délistait à tort toute
        la queue de liste, puis la passe ciblée suivante la réactivait : la
        durée de vie mesurée valait la cadence de scan (4,7 j médians pour
        toutes les strates), ce qui rendait la tension locative et la liquidité
        de revente non mesurables.
        """
        q = "select id from listings where source=%s and status='active'"
        params: list = [source]
        if deal_type:
            q += " and deal_type=%s"
            params.append(deal_type)
        active = {r[0] for r in self._execute(q, params).fetchall()}
        missing = list(active - seen_ids)
        now = _now()

        # 1re absence : on note la date, on n'agit pas encore.
        for lid in missing:
            self._execute(
                "update listings set missed_count = missed_count + 1,"
                " first_missed_at = coalesce(first_missed_at, %s) where id=%s",
                (now, lid),
            )

        # Seuil atteint → délistage daté de la PREMIÈRE absence (sinon la durée
        # de vie serait surestimée d'un cycle de scan complet).
        rows = self._execute(
            "update listings set status='inactive',"
            " delisted_at = coalesce(first_missed_at, %s)"
            " where source=%s and status='active' and missed_count >= %s"
            + (" and deal_type=%s" if deal_type else "")
            + " returning id",
            ([now, source, grace] + ([deal_type] if deal_type else [])),
        ).fetchall()
        return [r[0] for r in rows]

    def get_image_paths(self, listing_id: str) -> list[str]:
        return [
            r[0] for r in self._execute(
                "select storage_path from listing_images where listing_id=%s", (listing_id,)
            ).fetchall()
        ]

    def delete_images(self, listing_id: str) -> None:
        self._execute("delete from listing_images where listing_id=%s", (listing_id,))

    def record_scan_run(self, source: str, scanned: int, new: int,
                        removed: int, changed: int, notes: str = "") -> None:
        now = _now()
        self._execute(
            "insert into scan_runs (started_at,finished_at,source,scanned_count,"
            "new_count,removed_count,changed_count,notes) values (%s,%s,%s,%s,%s,%s,%s,%s)",
            (now, now, source, scanned, new, removed, changed, notes),
        )

    def khet_stats(self) -> list[dict]:
        rows = self._execute(
            "select khet, count(*) filter (where status='active') as active_count, "
            "round(avg(price_per_sqm) filter (where status='active')) as avg_price_per_sqm "
            "from listings where khet is not null group by khet order by active_count desc"
        ).fetchall()
        return [{"khet": r[0], "active_count": r[1], "avg_price_per_sqm": r[2]} for r in rows]

    def record_cohort_snapshots(self) -> int:
        """NE FAIT PLUS RIEN cote serveur depuis le 2026-08-25 — retourne 0.

        La serie de cohortes (stock actif par immeuble x chambres x tranche x
        type) sert a l'ETUDE, pas a l'app : aucun fichier .ts/.tsx ne lit
        `cohort_snapshots`, et `study/run_study.py` comme les agents tournent en
        local (`agents/core/db.py` : LOWI_STORE vaut « sqlite » par defaut).
        Elle pesait 218 Mo en ligne, deuxieme poste de la base, sur un quota
        gratuit de 500 Mo deja depasse a 162 %.

        Elle continue d'etre ecrite INTEGRALEMENT en local par SqliteStore —
        verifie avant la bascule : 842 738 lignes serveur toutes retrouvees
        parmi les 1 182 220 du local (ops/verifie-avant-degraissage.py).

        Le no-op est ICI plutot que chez l'appelant : `scraper/run.py` appelle la
        methode quel que soit le store, et un `if store == ...` chez lui serait
        un deuxieme endroit ou la regle pourrait diverger.
        """
        return 0

    def _record_cohort_snapshots_ancien(self) -> int:
        """Conserve pour rollback — voir la migration 2026-08-25_degraissage.sql."""
        # Le compte vient du RETURNING, pas d'une fenêtre temporelle : compter
        # les lignes « de la dernière minute » ramassait celles du run précédent
        # s'il venait de tourner, et en ratait si l'insertion dépassait la minute.
        return self._execute("""
            with insere as (
              insert into cohort_snapshots (unit_key, condo_name, khet, deal_type,
                  bedrooms, area_bucket, active_count, median_price, min_price, max_price)
              select unit_key, max(condo_name), max(khet), max(deal_type), max(bedrooms),
                     (round(avg(area_sqm) / 5) * 5)::int,
                     count(*),
                     percentile_cont(0.5) within group (order by price),
                     min(price), max(price)
              from listings
              where status = 'active' and unit_key is not null
              group by unit_key
              returning 1
            )
            select count(*) from insere""").fetchone()[0]

    def record_khet_snapshots(self) -> int:
        """Un snapshot par (quartier, deal_type) → tension vente/location séparée."""
        now = _now()
        rows = self._execute(
            "select khet, deal_type, "
            "count(*) filter (where status='active') as ac, "
            "round(avg(price_per_sqm) filter (where status='active')) as avg, "
            "percentile_cont(0.5) within group (order by price_per_sqm) "
            "  filter (where status='active') as med "
            "from listings where khet is not null and deal_type is not null "
            "group by khet, deal_type"
        ).fetchall()
        for khet, deal_type, ac, avg, med in rows:
            self._execute(
                "insert into khet_snapshots (taken_at,khet,deal_type,active_count,"
                "avg_price_per_sqm,median_price_per_sqm) values (%s,%s,%s,%s,%s,%s)",
                (now, khet, deal_type, ac, avg, med),
            )
        return len(rows)

    def close(self) -> None:
        self.db.close()
