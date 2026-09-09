"""sqlite_store.py — Stockage LOCAL (SQLite) reflétant supabase/schema.sql.

Gère le diff (new/changed/unchanged), l'historique de prix, le passage en
inactif des annonces disparues, les scan_runs et les stats par khet.
"""
from __future__ import annotations

import json
import sqlite3
import zlib
from datetime import datetime, timezone
from pathlib import Path

from pipeline import details
from store.base import COLONNES_LISTING, COLONNES_LOCALES, BaseStore

_SCHEMA = """
create table if not exists listings (
  id text primary key, source text not null, source_url text not null,
  title text, deal_type text, quota text, tenure text default 'freehold',
  price real, currency text default 'THB',
  area_sqm real, price_per_sqm real, bedrooms integer, bathrooms integer,
  condo_name text, address_raw text, khet text, khwaeng text, street text,
  lat real, lng real, status text not null default 'active',
  first_seen text not null, last_seen text not null, delisted_at text, raw_data text,
  -- Délai de grâce avant délistage : une annonce doit manquer à N scans
  -- CONSÉCUTIFS. Sans ça, la troncature du scan à max_pages délistait à tort
  -- toute la queue de liste (cf. supabase/migrations/delisting_grace.sql).
  missed_count integer not null default 0, first_missed_at text
);
create table if not exists khet_snapshots (
  id integer primary key autoincrement, taken_at text not null, khet text not null,
  deal_type text, active_count integer, avg_price_per_sqm real, median_price_per_sqm real
);
create table if not exists listing_images (
  id integer primary key autoincrement, listing_id text not null,
  storage_path text not null, width integer, height integer, ord integer default 0
);
create table if not exists listing_amenities (
  id integer primary key autoincrement, listing_id text not null, name text not null
);
create table if not exists price_history (
  id integer primary key autoincrement, listing_id text not null,
  price real not null, observed_at text not null
);
-- Évolution de `posted_at` pour une MÊME annonce. Sert à trancher si le champ
-- est une date de publication (stable) ou de remontée en tête de liste (mobile).
-- Cf. SqliteStore._track_posted_at.
create table if not exists posted_at_history (
  id integer primary key autoincrement, listing_id text not null,
  posted_at text not null, observed_at text not null
);
create index if not exists idx_posted_hist on posted_at_history(listing_id);
create table if not exists scan_runs (
  id integer primary key autoincrement, started_at text not null, finished_at text,
  source text not null, scanned_count integer, new_count integer,
  removed_count integer, changed_count integer, notes text
);
create index if not exists idx_listings_khet on listings(khet);
create index if not exists idx_listings_status on listings(status);
create index if not exists idx_images_listing on listing_images(listing_id);
-- PERIMETRE ASSAINI — meme definition que la vue Postgres du meme nom
-- (supabase/migrations/plausibilite.sql) et que lib/market-bounds.ts. Les trois
-- doivent rester alignes : c'est la regle de la source unique de CLAUDE.md, et
-- une 3e definition divergente avait deja ete trouvee dans study/config.json le
-- 2026-08-03. Creee ici parce que le stockage de reference est passe en local
-- le 2026-08-23 : sans elle, l'etude de marche n'a plus de perimetre.
create view if not exists listings_sane as
select * from listings
where price is not null
  and (area_sqm is null or area_sqm between 15 and 500)
  and (
    (deal_type = 'sale' and price between 800000 and 100000000)
    or
    (deal_type = 'rent' and price between 3000 and 500000)
  );
"""


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


def _contenu_a_change(existing, col: str, valeur_liee) -> bool:
    """Le contenu synchronisable a-t-il vraiment bougé pour cette colonne ?

    Compare la valeur déjà stockée (`existing`, un `sqlite3.Row` — donc déjà
    dans la représentation SQLite : JSON pour les listes, 0/1 pour les
    booléens) à la valeur qui vient d'être liée par `_valeur()` — MÊME
    représentation des deux côtés, pas de conversion à inventer ici.
    Tolérance volontaire sur `None` vs valeur : deux façons différentes de
    dire "pas de valeur" (`None`, `""`) ne comptent pas comme un changement,
    sinon `dirty_since` se déclencherait sur du bruit de normalisation plutôt
    que sur un changement réel — en cas de doute persistant, on considère
    que ça a changé (mieux vaut une remontée inutile qu'une remontée manquée).
    """
    ancien = existing[col] if col in existing.keys() else None
    if ancien == valeur_liee:
        return False
    if not ancien and not valeur_liee:
        return False
    return True


def _median(valeurs) -> float | None:
    """Médiane, définie comme `percentile_cont(0.5)` de Postgres.

    SQLite n'a pas d'agrégat de médiane : les instantanés locaux enregistraient
    donc `avg(price)` dans une colonne nommée `median_price`. La même colonne
    portait ainsi une MOYENNE en local et une MÉDIANE en ligne — et la moyenne
    court 16 % au-dessus (mesuré sur 2 121 instantanés de quartier). Deux
    backends, deux vérités dans la même série temporelle.

    Pour un effectif pair, on prend la demi-somme des deux valeurs centrales,
    ce que fait `percentile_cont(0.5)` : les deux stores sont alors alignés.
    """
    v = sorted(x for x in valeurs if x is not None)
    if not v:
        return None
    m = len(v) // 2
    return float(v[m]) if len(v) % 2 else (v[m - 1] + v[m]) / 2.0


#: Attente d'un verrou avant d'abandonner. Le defaut de sqlite3 est 5 s.
#:
#: MESURE DU 2026-08-25, cycle de 08:26 : l'orchestrateur lance les CINQ
#: extracteurs EN PARALLELE — ce qui allait de soi tant que le stockage etait
#: Postgres, qui accepte cinq ecrivains. SQLite n'en accepte qu'UN. Resultat sur
#: le premier cycle apres la bascule locale du 2026-08-23 : 4 790 erreurs
#: « database is locked », FazWaz a enregistre 28 annonces pour 3 285 echecs,
#: PropertyScout est mort a l'ecriture de son scan_run. Aucune donnee perdue
#: (chaque echec est attrape annonce par annonce et l'annonce est retiree de
#: `seen_ids`, donc le garde-fou anti-delistage a tenu), mais le cycle etait
#: perdu a 99 %.
#:
#: 60 s : une transaction d'upsert dure quelques millisecondes ; il faudrait des
#: milliers d'ecrivains simultanes pour depasser ce delai. On attend son tour au
#: lieu d'abandonner.
#:
#: 2026-09-09 — PORTE A 300 s. La premisse ci-dessus a cesse d'etre vraie : une
#: ecriture coute desormais 0,99 s en moyenne (mesure du run du 08/09, table
#: « ou est passe le temps », 1 397 appels / 22,9 min) sur une base passee de
#: 1,19 Go (26/08) a 2,24 Go, et 5 extracteurs ecrivent en parallele. La nuit du
#: 08/09 : 6 747 « database is locked », dont 4 402 sur fazwaz et 2 345 sur
#: ddproperty — les deux seules etapes qui demarrent a la MEME seconde ; toutes
#: les etapes `then_*`, decalees, en ont eu ZERO. Les 7 cycles precedents : 0.
#: Effet de seuil, donc, sur une grandeur qui monte de ~75 Mo/jour.
#: 300 s ne corrige pas la latence d'ecriture — il empeche qu'une passe entiere
#: soit perdue le temps qu'elle soit traitee. Se defait en remettant 60.
ATTENTE_VERROU_S = 300


class SqliteStore(BaseStore):
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(db_path, timeout=ATTENTE_VERROU_S)
        self.db.row_factory = sqlite3.Row
        # WAL : les lecteurs cessent de bloquer l'ecrivain, et un commit n'a plus
        # a reecrire le journal complet. C'est ce qui rend la parallelisation des
        # extracteurs tenable — l'ecriture reste serialisee, mais chaque tour de
        # verrou dure des millisecondes au lieu de dizaines.
        # synchronous=NORMAL est le reglage SUR sous WAL (aucune corruption
        # possible en cas de plantage applicatif ; seule une coupure de courant
        # peut coûter les dernieres transactions, que le scrap suivant reprend).
        self.db.execute("pragma journal_mode=WAL")
        self.db.execute("pragma synchronous=NORMAL")
        self.db.execute(f"pragma busy_timeout={ATTENTE_VERROU_S * 1000}")
        self.db.executescript(_SCHEMA)
        self._migrate()
        self.db.commit()

    @staticmethod
    def _bind_value(v):
        """SQLite n'a pas de type tableau : photo_sizes est stocké en JSON."""
        return json.dumps(v, ensure_ascii=False) if isinstance(v, (list, tuple)) else v

    @classmethod
    def _valeur(cls, col: str, norm: dict):
        """Valeur prête à lier, par colonne.

        `page_text` passe par zlib. Sans ce détour la colonne était déclarée
        `blob` mais recevait la chaîne telle quelle — `compresser()` existait
        et n'était appelée nulle part, donc le gain annoncé n'était pas réalisé.
        Sur un texte de page réel : ~78 % de gain.
        """
        v = norm.get(col)
        return cls.compresser(v) if col == "page_text" else cls._bind_value(v)

    @staticmethod
    def compresser(texte: str | None) -> bytes | None:
        """Texte de page → BLOB zlib. ~50 % de gain mesuré, et le texte intégral
        de 15 000 pages tient alors dans ~34 Mo."""
        if not texte:
            return None
        return zlib.compress(texte.encode("utf-8"), 6)

    @staticmethod
    def decompresser(blob) -> str | None:
        """Rend le texte archivé. Tolère un texte stocké en clair (bases créées
        avant la compression) pour ne jamais faire échouer une relecture."""
        if blob is None:
            return None
        if isinstance(blob, str):
            return blob
        try:
            return zlib.decompress(blob).decode("utf-8")
        except (zlib.error, UnicodeDecodeError):
            return None

    def _migrate(self) -> None:
        """Migrations légères pour les bases créées avant un ajout de colonne."""
        cols = {r["name"] for r in self.db.execute("pragma table_info(khet_snapshots)")}
        if "deal_type" not in cols:
            self.db.execute("alter table khet_snapshots add column deal_type text")
        # Délai de grâce avant délistage (cf. delisting_grace.sql)
        lcols = {r["name"] for r in self.db.execute("pragma table_info(listings)")}
        if "missed_count" not in lcols:
            self.db.execute("alter table listings add column missed_count integer not null default 0")
        if "first_missed_at" not in lcols:
            self.db.execute("alter table listings add column first_missed_at text")
        # Cohorte, âge du bâtiment, empreinte photo (cf. unit_key_photo_sig.sql)
        for col, typ in (("unit_key", "text"), ("year_built", "integer"),
                         ("photo_count", "integer"), ("photo_sizes", "text"),
                         ("repost_of", "text"), ("repost_reason", "text"),
                         # provenance (cf. provenance_annonce.sql)
                         ("agent_id", "text"), ("agency_id", "text"),
                         ("posted_at", "text"), ("is_auto_repost", "integer"),
                         # vendu/loue dit par la source (cf. fazwaz.statut_marche)
                         # + date de PREMIERE apparition du marqueur : c'est elle
                         # qui porte la regle des 7 jours avant sortie du stock.
                         ("market_status", "text"), ("market_status_since", "text"),
                         # descriptif libre — seule matière textuelle de la base
                         ("description", "text"),
                         # MATIERE PREMIERE : texte integral compresse (zlib)
                         ("page_text", "blob"),
                         # détails extraits du descriptif (préfixe d_ pour les
                         # distinguer des champs de la source). Types déclarés
                         # dans details.COLONNES et JAMAIS recopiés ici : une
                         # liste tenue à la main en double finit par diverger.
                         *details.COLONNES):
            if col not in lcols:
                self.db.execute(f"alter table listings add column {col} {typ}")
        # `dirty_since` : marque locale des lignes dont le CONTENU synchronisable
        # (COLONNES_LISTING) a changé depuis le dernier envoi réussi vers
        # Supabase — ou dont le statut vient de basculer hors 'active'. Sert de
        # file d'attente pour `ops/remonter-local.py --delta` (2026-09-07) :
        # avant, chaque remontée réévaluait TOUTE la fenêtre active (81 889
        # lignes, 33 lots) pour laisser Postgres décider ce qui avait changé —
        # demandé par l'utilisateur en observant l'incident du jour (`remonter-
        # supabase` bloqué par le pooler Supabase, "ECIRCUITBREAKER: too many
        # authentication failures") : "only update what's new and remove what's
        # not updated anymore". `dirty_since` déplace le calcul du delta côté
        # local (déjà fait à l'écriture, gratuit) au lieu d'un aller-retour
        # réseau par lot pour le découvrir.
        if "dirty_since" not in lcols:
            self.db.execute("alter table listings add column dirty_since text")
            # Backfill : toute ligne active OU déjà délistée est marquée sale UNE
            # FOIS pour établir la base de référence sur Supabase (l'ancien
            # mécanisme n'a jamais suivi qui était déjà synchronisé) — la
            # prochaine remontée en mode --delta fait donc un dernier passage
            # complet, puis devient réellement incrémentale ensuite.
            self.db.execute(
                "update listings set dirty_since=? where status='active' or delisted_at is not null",
                (_now(),),
            )
        self.db.execute("create index if not exists idx_listings_dirty on listings (dirty_since)")
        self.db.execute("create index if not exists idx_listings_unit on listings (unit_key)")
        self.db.execute("""create table if not exists cohort_snapshots (
            id integer primary key autoincrement, taken_at text not null,
            unit_key text not null, condo_name text, khet text, deal_type text,
            bedrooms integer, area_bucket integer, active_count integer not null,
            median_price real, min_price real, max_price real)""")
        self.db.execute("create index if not exists idx_cohort_snap on cohort_snapshots (unit_key, taken_at)")

    def record_cohort_snapshots(self) -> int:
        """Stock actif par cohorte (immeuble × chambres × tranche × type).

        Mesure la tension sans être trompée par les republications : un repost
        fait mourir une annonce et en fait naître une autre dans la MÊME
        cohorte, donc le stock ne bouge pas.

        `median_price` est une VRAIE médiane, comme côté Supabase — calculée en
        Python faute d'agrégat SQLite (cf. `_median`).
        """
        now = _now()
        rows = self.db.execute("""
            select unit_key, max(condo_name) condo_name, max(khet) khet,
                   max(deal_type) deal_type, max(bedrooms) bedrooms,
                   cast(round(avg(area_sqm)/5)*5 as int) area_bucket,
                   count(*) n, min(price) mn, max(price) mx
            from listings
            where status='active' and unit_key is not null
            group by unit_key""").fetchall()
        prix = {}
        for uk, p in self.db.execute(
            "select unit_key, price from listings"
            " where status='active' and unit_key is not null and price is not null"
        ):
            prix.setdefault(uk, []).append(p)
        self.db.executemany(
            "insert into cohort_snapshots (taken_at, unit_key, condo_name, khet,"
            " deal_type, bedrooms, area_bucket, active_count, median_price,"
            " min_price, max_price) values (?,?,?,?,?,?,?,?,?,?,?)",
            [(now, r["unit_key"], r["condo_name"], r["khet"], r["deal_type"],
              r["bedrooms"], r["area_bucket"], r["n"],
              _median(prix.get(r["unit_key"], [])), r["mn"], r["mx"])
             for r in rows],
        )
        self.db.commit()
        return len(rows)

    def get_listing(self, listing_id: str) -> dict | None:
        row = self.db.execute("select * from listings where id=?", (listing_id,)).fetchone()
        return dict(row) if row else None

    def has_images(self, listing_id: str) -> bool:
        row = self.db.execute(
            "select 1 from listing_images where listing_id=? limit 1", (listing_id,)
        ).fetchone()
        return row is not None

    def touch_listing(self, listing_id: str) -> None:
        # Revue = série d'absences interrompue : on remet le compteur à zéro.
        # `dirty_since` : ne bouge QUE si la ligne n'était pas déjà active —
        # une résurrection change ce que Supabase doit savoir, un simple
        # "revu, rien de neuf" ne doit pas gonfler le paquet du jour.
        row = self.db.execute("select status from listings where id=?", (listing_id,)).fetchone()
        etait_active = row is not None and row["status"] == "active"
        now = _now()
        if etait_active:
            self.db.execute(
                "update listings set status='active', last_seen=?,"
                " missed_count=0, first_missed_at=null,delisted_at=null where id=?",
                (now, listing_id),
            )
        else:
            self.db.execute(
                "update listings set status='active', last_seen=?,"
                " missed_count=0, first_missed_at=null,delisted_at=null,dirty_since=? where id=?",
                (now, now, listing_id),
            )
        self.db.commit()

    def upsert_listing(self, norm: dict, images: list[dict] | None) -> tuple[str, float | None]:
        existing = self.get_listing(norm["id"])
        now = _now()
        # Exemplaire unique dans store/base.py (cf. le commentaire la-bas).
        # Le local ecrit EN PLUS `description` et `page_text` : depuis le
        # 2026-08-25 ils ne partent plus vers Supabase (l'app ne les lit jamais,
        # ils pesaient 290 Mo sur un quota gratuit de 500 deja depasse). Le
        # local est l'archive de reference, il garde tout.
        cols = COLONNES_LISTING + COLONNES_LOCALES

        if existing is None:
            self.db.execute(
                f"insert into listings (id,{','.join(cols)},status,first_seen,last_seen,raw_data,dirty_since) "
                f"values (?,{','.join('?' for _ in cols)},'active',?,?,?,?)",
                (norm["id"], *[self._valeur(c, norm) for c in cols], now, now,
                 json.dumps(norm.get("raw_data", {}), ensure_ascii=False), now),
            )
            if norm.get("price") is not None:
                self._add_price(norm["id"], norm["price"], now)
            if norm.get("posted_at"):
                self._add_posted_at(norm["id"], norm["posted_at"], now)
            self._set_images(norm["id"], images)
            self._set_amenities(norm["id"], norm.get("amenities", []))
            self.db.commit()
            return "new", None

        old_price = existing["price"]
        new_price = norm.get("price")
        # AVANT l'écrasement : `posted_at` change-t-il pour une MÊME annonce ?
        # C'est la seule façon de le prouver — l'update ci-dessous détruit
        # l'ancienne valeur, et un instantané ne dit rien d'une évolution.
        self._track_posted_at(existing, norm.get("posted_at"), now)
        self._suivre_statut_marche(existing, norm.get("market_status"), now)
        valeurs_liees = [self._valeur(c, norm) for c in cols]
        # Une résurrection (déjà inactive/sold, revue en scan) compte comme un
        # changement de contenu même si toutes les colonnes sont identiques :
        # Supabase doit apprendre que l'annonce est de nouveau active.
        contenu_change = existing["status"] != "active" or any(
            _contenu_a_change(existing, c, v)
            for c, v in zip(COLONNES_LISTING, valeurs_liees[:len(COLONNES_LISTING)])
        )
        dirty_since = now if contenu_change else existing["dirty_since"]
        self.db.execute(
            f"update listings set {','.join(c+'=?' for c in cols)},"
            f"status='active',last_seen=?,raw_data=?,"
            f"missed_count=0,first_missed_at=null,delisted_at=null,dirty_since=? where id=?",
            (*valeurs_liees, now,
             json.dumps(norm.get("raw_data", {}), ensure_ascii=False), dirty_since, norm["id"]),
        )
        status = "unchanged"
        if new_price is not None and old_price is not None and float(new_price) != float(old_price):
            self._add_price(norm["id"], new_price, now)
            status = "changed"
        if images is not None:
            self._set_images(norm["id"], images)
        self.db.commit()
        return status, old_price

    def _add_price(self, listing_id: str, price: float, when: str) -> None:
        self.db.execute(
            "insert into price_history (listing_id,price,observed_at) values (?,?,?)",
            (listing_id, price, when),
        )

    def _add_posted_at(self, listing_id: str, valeur: str, when: str) -> None:
        self.db.execute(
            "insert into posted_at_history (listing_id,posted_at,observed_at) values (?,?,?)",
            (listing_id, valeur, when),
        )

    def _track_posted_at(self, existing, nouveau: str | None, when: str) -> None:
        """Historise `posted_at` quand il CHANGE pour une annonce déjà connue.

        Mesuré sur la production le 2026-08-02 : l'écart médian
        `first_seen - posted_at` vaut **-16 jours** — on a vu l'annonce seize
        jours AVANT sa date de publication déclarée. Une date de mise en ligne
        ne peut pas être postérieure à notre propre observation : le champ
        avance donc dans le temps, et DDproperty y écrit vraisemblablement la
        date de dernière REMONTÉE en tête de liste, pas celle de publication.

        « Vraisemblablement » : on écrasait la valeur à chaque scan, donc on ne
        pouvait pas voir un identifiant donné changer. Cette table le prouvera
        — ou la démentira. Tant qu'elle est vide, la substitution de `posted_at`
        à `first_seen` dans le time-on-market reste PROSCRITE : elle
        raccourcirait la durée au lieu de l'allonger, et mesurerait l'assiduité
        des agents à rafraîchir plutôt que l'absorption du marché.

        Même forme que `price_history` : on n'écrit que sur changement réel.
        """
        if not nouveau:
            return
        try:
            ancien = existing["posted_at"]
        except (KeyError, IndexError):
            return                       # base créée avant la colonne
        if ancien and str(ancien) == str(nouveau):
            return
        self._add_posted_at(existing["id"], nouveau, when)

    def _set_images(self, listing_id: str, images: list[dict] | None) -> None:
        if images is None:
            return
        self.db.execute("delete from listing_images where listing_id=?", (listing_id,))
        for im in images:
            self.db.execute(
                "insert into listing_images (listing_id,storage_path,width,height,ord) "
                "values (?,?,?,?,?)",
                (listing_id, im["storage_path"], im.get("width"), im.get("height"), im.get("ord", 0)),
            )

    def _set_amenities(self, listing_id: str, amenities: list[str]) -> None:
        self.db.execute("delete from listing_amenities where listing_id=?", (listing_id,))
        for a in amenities:
            self.db.execute(
                "insert into listing_amenities (listing_id,name) values (?,?)", (listing_id, a)
            )

    def count_active(self, source: str, deal_type: str | None = None) -> int:
        q = "select count(*) c from listings where source=? and status='active'"
        params: list = [source]
        if deal_type:
            q += " and deal_type=?"
            params.append(deal_type)
        return self.db.execute(q, params).fetchone()["c"]

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
        self.db.execute("update listings set market_status_since=? where id=?", (quand, lid))

    def appliquer_ventes(self, jours: int = JOURS_AVANT_SORTIE_VENDU) -> int:
        """Sort du stock actif les annonces marquees vendues depuis `jours`.
        Voir SupabaseStore.appliquer_ventes pour le raisonnement."""
        from datetime import timedelta
        limite = (datetime.now(timezone.utc) - timedelta(days=jours)).isoformat()
        # `dirty_since` : la sortie du stock actif est un changement de statut
        # que --delta doit propager (retrait côté Supabase), même si aucune
        # colonne de contenu n'a bougé.
        cur = self.db.execute(
            "update listings set status='sold', delisted_at=market_status_since, dirty_since=? "
            "where market_status='sold' and status='active' "
            "  and market_status_since is not null and market_status_since <= ?",
            (_now(), limite))
        self.db.commit()
        return cur.rowcount

    def ids_actifs(self, source: str, deal_type: str | None = None) -> set[str]:
        q = "select id from listings where source=? and status='active'"
        params: list = [source]
        if deal_type:
            q += " and deal_type=?"
            params.append(deal_type)
        return {r[0] for r in self.db.execute(q, params).fetchall()}

    def toucher_lot(self, ids, quand: str) -> int:
        """Equivalent SQLite de la version Postgres (lots de 500 : limite de
        variables liees). Ne touche que les lignes deja 'active'."""
        ids = list(ids)
        if not ids:
            return 0
        touchees = 0
        for i in range(0, len(ids), 500):
            lot = ids[i:i + 500]
            trous = ",".join("?" * len(lot))
            cur = self.db.execute(
                f"update listings set last_seen=?, missed_count=0,"
                f" first_missed_at=null"
                f" where id in ({trous}) and status='active'",
                [quand] + lot,
            )
            touchees += cur.rowcount
        self.db.commit()
        return touchees

    def mark_missing_inactive(self, source: str, seen_ids: set[str],
                              deal_type: str | None = None,
                              grace: int = 2) -> list[str]:
        """Délistage avec délai de grâce (cf. supabase_store pour le détail) :
        une annonce doit manquer à `grace` scans CONSÉCUTIFS avant d'être
        marquée inactive, sinon la troncature du scan à max_pages déliste à
        tort toute la queue de liste."""
        q = "select id from listings where source=? and status='active'"
        params: list = [source]
        if deal_type:
            q += " and deal_type=?"
            params.append(deal_type)
        active = {r["id"] for r in self.db.execute(q, params).fetchall()}
        missing = list(active - seen_ids)
        now = _now()

        for lid in missing:
            self.db.execute(
                "update listings set missed_count = coalesce(missed_count,0) + 1,"
                " first_missed_at = coalesce(first_missed_at, ?) where id=?",
                (now, lid),
            )

        q2 = ("select id, first_missed_at from listings where source=? and status='active'"
              " and coalesce(missed_count,0) >= ?")
        p2: list = [source, grace]
        if deal_type:
            q2 += " and deal_type=?"
            p2.append(deal_type)
        rows = self.db.execute(q2, p2).fetchall()
        missing = []
        for r in rows:
            # Daté de la PREMIÈRE absence, sinon la durée de vie serait
            # surestimée d'un cycle de scan complet.
            self.db.execute(
                "update listings set status='inactive', delisted_at=?, dirty_since=? where id=?",
                (r["first_missed_at"] or now, now, r["id"]),
            )
            missing.append(r["id"])
        self.db.commit()
        return missing

    def get_image_paths(self, listing_id: str) -> list[str]:
        return [
            r["storage_path"]
            for r in self.db.execute(
                "select storage_path from listing_images where listing_id=?", (listing_id,)
            ).fetchall()
        ]

    def delete_images(self, listing_id: str) -> None:
        self.db.execute("delete from listing_images where listing_id=?", (listing_id,))
        self.db.commit()

    def record_scan_run(self, source: str, scanned: int, new: int,
                        removed: int, changed: int, notes: str = "") -> None:
        now = _now()
        self.db.execute(
            "insert into scan_runs (started_at,finished_at,source,scanned_count,"
            "new_count,removed_count,changed_count,notes) values (?,?,?,?,?,?,?,?)",
            (now, now, source, scanned, new, removed, changed, notes),
        )
        self.db.commit()

    def khet_stats(self) -> list[dict]:
        rows = self.db.execute(
            "select khet, count(*) as active_count, "
            "round(avg(price_per_sqm)) as avg_price_per_sqm "
            "from listings where status='active' and khet is not null "
            "group by khet order by active_count desc"
        ).fetchall()
        return [dict(r) for r in rows]

    def record_khet_snapshots(self) -> int:
        """Un snapshot par (quartier, deal_type) → tension vente/location séparée.

        `median_price_per_sqm` était laissé à NULL en local, alors que c'est LUI
        que le momentum prix de lib/tension.ts consomme : la série locale était
        donc muette sur sa composante la plus utile. Calculé en Python, comme
        `record_cohort_snapshots`.
        """
        now = _now()
        rows = self.db.execute(
            "select khet, deal_type, count(*) as active_count, "
            "round(avg(price_per_sqm)) as avg_price_per_sqm "
            "from listings where status='active' and khet is not null and deal_type is not null "
            "group by khet, deal_type"
        ).fetchall()
        psqm: dict[tuple, list] = {}
        for k, d, v in self.db.execute(
            "select khet, deal_type, price_per_sqm from listings"
            " where status='active' and khet is not null and deal_type is not null"
            " and price_per_sqm is not null"
        ):
            psqm.setdefault((k, d), []).append(v)
        for r in rows:
            self.db.execute(
                "insert into khet_snapshots (taken_at,khet,deal_type,active_count,"
                "avg_price_per_sqm,median_price_per_sqm) values (?,?,?,?,?,?)",
                (now, r["khet"], r["deal_type"], r["active_count"],
                 r["avg_price_per_sqm"], _median(psqm.get((r["khet"], r["deal_type"]), []))),
            )
        self.db.commit()
        return len(rows)

    def close(self) -> None:
        self.db.close()
