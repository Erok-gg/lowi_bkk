"""supabase_store.py — Stockage ONLINE (Postgres Supabase) via pg8000.

Même interface que SqliteStore (BaseStore) → le pipeline ne change pas.
Connexion Postgres directe (pooler session) → bypass RLS (utilisateur postgres).
DSN lu depuis SUPABASE_DB_URL.

POURQUOI pg8000 ET PLUS psycopg (2026-10-09)
La nuit du 09/10, `remonter-supabase` (#752) est mort en 9 s sur
« no pq wrapper available » : Smart App Control a bloqué la DLL libpq de
`psycopg_binary` (journal CodeIntegrity, événement 3077 à l'instant du run),
5 processus neufs sur 5, fichier inchangé depuis le 2026-08-21. Ce n'est pas
la signature qui est jugée (29/29 DLL du venv non signées, lxml et Pillow
passent) mais la RÉPUTATION, qui peut basculer sans préavis — le même jour à
13 h l'import repassait. pg8000 est en Python pur : aucune DLL native, donc
rien que Smart App Control puisse juger. Choix de l'utilisateur, option 1 du
mail d'alerte (les deux autres : libpq « signé », non pertinent ; désactiver
Smart App Control, irréversible).
"""
from __future__ import annotations

import json
import random
import threading
import time
from datetime import datetime, timezone

from pg8000.exceptions import DatabaseError, InterfaceError

from pipeline import details
from store import pg
from store.base import COLONNES_LISTING, BaseStore


def Json(valeur):
    """Équivalent de `psycopg.types.json.Json` : sérialise pour une colonne jsonb.

    pg8000 envoie une `str` en type `unknown` : Postgres la convertit lui-même
    vers le type de la colonne cible (vérifié contre le serveur le 2026-10-09,
    `%s::jsonb` et colonne `raw_data`)."""
    return json.dumps(valeur, ensure_ascii=False)


#: Classes SQLSTATE traitées comme une COUPURE (on se reconnecte et on
#: rejoue), c'est-à-dire ce que psycopg rangeait dans `OperationalError` et que
#: `_execute` rattrapait : 08 connexion, 53 ressources, 57 intervention
#: (arrêt admin, statement timeout), 58 erreur système. Les autres classes
#: (syntaxe, contrainte, 54 limite de programme…) sont déterministes : les
#: rejouer 20 min ne changerait rien, elles remontent tout de suite, comme avant.
SQLSTATE_COUPURE = ("08", "53", "57", "58")

#: Délai de socket : voir store/pg.py. La connexion, elle, reste bornée à 25 s
#: par le watchdog (`CONNECT_HARD_TIMEOUT`).
SOCKET_TIMEOUT = pg.SOCKET_TIMEOUT


def _code_sqlstate(exc: BaseException) -> str | None:
    """pg8000 porte l'erreur serveur dans un dict (`C` = SQLSTATE, `M` = message)."""
    arg = exc.args[0] if exc.args else None
    return arg.get("C") if isinstance(arg, dict) else None


def _message(exc: BaseException) -> str:
    """Message lisible d'une erreur pg8000 (le dict brut noierait le log)."""
    arg = exc.args[0] if exc.args else None
    if isinstance(arg, dict):
        return f"{arg.get('S', '')} {arg.get('C', '')} {arg.get('M', '')}".strip()
    return str(exc)


def _est_coupure(exc: BaseException) -> bool:
    """Faut-il se reconnecter et rejouer (cf. `SQLSTATE_COUPURE`) ?"""
    if isinstance(exc, (InterfaceError, OSError)):
        return True                         # réseau : socket, DNS, SSL, « network error »
    if isinstance(exc, DatabaseError):
        code = _code_sqlstate(exc)
        return bool(code) and code[:2] in SQLSTATE_COUPURE
    return False


class ErreurConnexion(Exception):
    """Échec d'ouverture de connexion (watchdog, ou erreur pg8000 enveloppée).

    À l'OUVERTURE, toute erreur est une coupure à réessayer : le pooler rend
    par exemple « Failed to connect to database: authentication did not
    complete within 15000ms » en FATAL XX000, qu'aucun code 08 ne signale."""


#: Paramètres de connexion et enveloppe « à la psycopg » : exemplaire unique
#: dans store/pg.py, partagé avec les outils manuels (2026-10-09). Alias
#: conservés : les tests et `_ouvre` les nomment ainsi.
_parametres = pg.parametres


#: Meme constat, meme remede que scraper/pipeline/fetch.py (2026-09-04) :
#: `_execute` ne faisait qu'UN reconnect avant d'abandonner, ce qui a fait
#: planter `remonter-local.py --synchro-statuts` la nuit du 03 au 04/09 sur
#: une resolution DNS qui echouait encore au moment precis du seul essai
#: ("failed to resolve host 'aws-1-....pooler.supabase.com'") — alors que le
#: reste du run avait deja absorbe plusieurs de ces memes coupures lot par
#: lot. Meme sonde (la reconnexion elle-meme, contre le vrai pooler, pas un
#: tiers), meme cadence (30s), meme plafond (20 min) avant d'abandonner pour
#: de bon.
OUTAGE_POLL_SECONDS = 30.0
OUTAGE_MAX_WAIT_SECONDS = 20 * 60.0

#: PLAFOND DU RECUL. La cadence CONSTANTE de 30 s s'est retournée contre nous le
#: 2026-09-06 : le pooler avait répondu « new connections are temporarily
#: blocked » et on l'a rappelé 37 fois de suite, toutes les 30 s, jusqu'à la fin
#: du budget de 20 min. Réessayer vite contre une protection qui vient de se
#: fermer, c'est la maintenir fermée. Le recul double à chaque échec (30, 60,
#: 120, 240, 300…) au lieu de rester plat.
OUTAGE_POLL_MAX = 300.0

#: Le pooler Supabase répond ECIRCUITBREAKER quand il BLOQUE volontairement les
#: nouvelles connexions — après « multiple attempts » de récupération des
#: identifiants. Ce n'est PAS une coupure réseau : le réseau va bien, c'est le
#: serveur qui nous ferme la porte. Les deux demandent l'inverse l'un de
#: l'autre : une coupure se re-sonde souvent (elle peut cesser à tout moment),
#: une protection ouverte se laisse respirer. D'où un palier plancher distinct.
CIRCUIT_OUVERT_MARQUEURS = ("ECIRCUITBREAKER", "temporarily blocked")
CIRCUIT_OUVERT_PALIER = 120.0

#: Jitter : 5 chemins d'écriture peuvent perdre la connexion à la même seconde
#: (même coupure). Sans désynchronisation, ils reviendraient tous frapper le
#: pooler ensemble — c'est précisément ce qui ouvre le disjoncteur.
JITTER = 0.25

#: `connect_timeout` de libpq ne borne PAS la résolution DNS (limite documentée
#: de libpq/psycopg, pas un bug de notre code) : un `getaddrinfo()` qui bloque
#: ignore ce paramètre. Mesuré le 2026-09-07 : `remonter-supabase` restée
#: bloquée >4h dans un SEUL appel `_reconnect()`, sans qu'aucune des lignes de
#: log attendues toutes les 30s (`OUTAGE_POLL_SECONDS`) ne sorte — la boucle de
#: `_execute()` ne peut compter le temps écoulé que si l'appel bloquant
#: lui-même est borné de l'extérieur. `CONNECT_HARD_TIMEOUT` fait ce travail
#: (thread-watchdog, pas signal.alarm — indisponible sur Windows).
#: Toujours nécessaire avec pg8000 : `socket.create_connection` résout le nom
#: AVANT d'appliquer son délai, la résolution reste donc non bornée.
CONNECT_HARD_TIMEOUT = 25.0


#: Attentes abandonnées par le watchdog dont le thread tourne ENCORE. On ne
#: peut pas tuer un thread Python, seulement cesser de l'attendre — puis
#: revenir le ramasser. Deux raisons, les deux MESURÉES le 2026-10-06 (cycle
#: de nuit : `remonter-supabase` abandonnée après 8 h 28, 5 500/113 978) :
#:
#: 1. LA VRAIE CAUSE ARRIVE APRÈS LE WATCHDOG, donc on la détruisait.
#:    `psycopg.connect` contre le pooler session a rendu son erreur en
#:    32,0 / 32,1 / 32,9 s (3 mesures consécutives) :
#:    « FATAL: Failed to connect to database: authentication did not complete
#:    within 15000ms » — c'est le POOLER qui n'arrive pas à s'authentifier
#:    auprès du Postgres, lui-même à genoux (dans `postgres_logs` le même
#:    jour : checkpoint d'UN buffer = 17 à 22 s, 250 buffers = 147 s,
#:    `pg_database_size('template1')` = 23 s, autovacuum « took too long to
#:    start »). Le watchdog tombe à 25 s, donc AVANT : les ~60 lignes de log
#:    de la nuit ont toutes annoncé « coupure ? » et « DNS ou TCP », alors que
#:    le DNS résolvait et que le TCP passait (vérifiés tous les deux). Un
#:    garde-fou qui nomme la mauvaise cause envoie l'enquête suivante dans le
#:    mur — c'est exactement ce que la règle 2 interdit, et ce qui explique
#:    que les commentaires de ce fichier parlent de DNS depuis un mois.
#:
#: 2. UNE CONNEXION QUI ATTERRIT EN RETARD RESTAIT OUVERTE. Si `connect()`
#:    réussit à 26 s, `resultat["db"]` tenait une connexion que personne ne
#:    fermait jamais. En mode SESSION chacune occupe un backend du pooler —
#:    et `supavisor_logs` montre précisément « (ECHECKOUTTIMEOUT) unable to
#:    check out connection from the pool after 15000ms in Session mode ». On
#:    aggravait donc, fuite par fuite, la panne qu'on réessayait.
#:
#: Le ramassage ne change AUCUN délai, aucun palier, aucun budget : il ferme
#: ce qui traîne et il dit la vérité. Les seuils restent l'arbitrage de
#: l'utilisateur.
_attentes_orphelines: list[dict] = []


def _ramasse_orphelines() -> str | None:
    """Ferme les connexions atterries en retard ; rend la vraie cause si connue.

    À appeler juste AVANT un nouvel essai : c'est le seul instant où le thread
    précédent a eu le temps de finir (le recul du backoff lui en laisse au
    minimum 30 s, là où le watchdog ne lui en laissait que 25).
    """
    vraie_cause: str | None = None
    for slot in list(_attentes_orphelines):
        if "db" in slot:
            try:
                slot["db"].close()
            except Exception:  # noqa: BLE001 — fermeture best-effort
                pass
        elif "erreur" in slot:
            # Première ligne seulement : psycopg empile « Multiple connection
            # attempts failed » + un bloc par IP (3 pour ce pooler), ce qui
            # noierait le log sans rien ajouter.
            vraie_cause = _message(slot["erreur"]).strip().splitlines()[0]
        else:
            continue                 # toujours en vol — on le reverra au tour suivant
        _attentes_orphelines.remove(slot)
    return vraie_cause


def _dis_la_vraie_cause() -> None:
    """Imprime la cause réelle d'une attente abandonnée, si elle est arrivée.

    Exemplaire unique : les DEUX boucles de reprise (ouverture initiale et
    reprise en cours de run) doivent dire la vérité de la même façon — c'est
    parce qu'elles divergeaient que `_recul` a dû être factorisé, même motif.
    """
    cause = _ramasse_orphelines()
    if cause:
        print(f"    ↳ cause réelle de l'attente précédente : {cause}", flush=True)


def _ouvre(dsn: str) -> pg.Connexion:
    """Point d'appel unique du pilote — c'est lui que les tests remplacent."""
    return pg.connecter(dsn, autocommit=True, application_name="lowi-remontee")


def _connect_borne(dsn: str) -> pg.Connexion:
    resultat: dict = {}

    def _cible() -> None:
        try:
            resultat["db"] = _ouvre(dsn)
        except BaseException as exc:  # noqa: BLE001 — remonté tel quel plus bas
            resultat["erreur"] = exc

    fil = threading.Thread(target=_cible, daemon=True)
    fil.start()
    fil.join(CONNECT_HARD_TIMEOUT)
    if fil.is_alive():
        # Le thread reste orphelin (daemon). On confie son `resultat` au
        # ramasseur : ce dict est le SEUL lien qui reste vers une connexion
        # qui atterrirait en retard (à fermer) ou vers la vraie cause de
        # l'échec (à dire). Sans cela, les deux étaient perdues — cf. le
        # commentaire de `_attentes_orphelines`.
        _attentes_orphelines.append(resultat)
        # Le message ne NOMME plus de cause : à 25 s on sait seulement que
        # l'appel n'a pas rendu la main. Prétendre « DNS ou TCP » était faux
        # le 2026-10-06, et c'est ce qui a fait chercher au mauvais endroit.
        raise ErreurConnexion(
            f"connect() n'a pas rendu la main en {CONNECT_HARD_TIMEOUT:.0f}s "
            "(cause pas encore connue — le serveur n'a pas fini de répondre) — abandon"
        )
    if "erreur" in resultat:
        exc = resultat["erreur"]
        if isinstance(exc, (DatabaseError, InterfaceError, OSError)):
            raise ErreurConnexion(_message(exc)) from exc
        raise exc
    return resultat["db"]


def _circuit_ouvert(exc: BaseException) -> bool:
    """Le pooler nous ferme-t-il la porte, plutôt que le réseau d'être coupé ?"""
    message = str(exc)
    return any(marqueur in message for marqueur in CIRCUIT_OUVERT_MARQUEURS)


def _recul(exc: BaseException, palier: float) -> tuple[float, float, str]:
    """Combien attendre avant le prochain essai, et quel palier ensuite.

    Exemplaire unique : les DEUX chemins de reconnexion (ouverture initiale et
    reprise en cours de run) doivent reculer de la même façon — c'est justement
    parce qu'ils divergeaient que l'un mourait en 25 s quand l'autre tenait
    20 min (cf. `_connect_resilient`)."""
    if _circuit_ouvert(exc):
        pause = max(palier, CIRCUIT_OUVERT_PALIER)
        motif = ("pooler Supabase en protection (ECIRCUITBREAKER) — il bloque "
                 "volontairement les nouvelles connexions, on le laisse respirer")
    else:
        pause = palier
        motif = "connexion Postgres perdue (coupure ?)"
    pause = min(pause, OUTAGE_POLL_MAX)
    pause += random.uniform(0.0, pause * JITTER)
    return pause, min(palier * 2, OUTAGE_POLL_MAX), motif


def _connect_resilient(dsn: str, plafond: float | None = None
                       ) -> pg.Connexion:
    """Ouvre la connexion en absorbant une coupure qui DURE.

    POURQUOI CETTE FONCTION EXISTE — asymétrie mesurée le 2026-09-09.
    `_execute()` encaissait jusqu'à 20 min de coupure en cours de run, mais
    `SupabaseStore.__init__` appelait `_connect_borne()` NU : un seul essai,
    borné à 25 s, sans la moindre reprise. Le résultat est indéfendable — la
    remontée survivait à une panne de vingt minutes au milieu du travail et
    mourait sur un hoquet de vingt-cinq secondes au démarrage.

    C'est ce qui a tué le run du 2026-09-09 (01:12:03 → 01:13:22, 79 s) :
    « connect() bloqué au-delà de 25s — abandon », et le site public est resté
    sur des données périmées une journée de plus pour cette seule raison.
    """
    # `plafond=None` et non `plafond=OUTAGE_MAX_WAIT_SECONDS` en défaut : une
    # valeur par défaut est figée à la DÉFINITION de la fonction, donc elle
    # ignorerait toute reconfiguration du module. Trouvé en écrivant le test —
    # qui, avec le budget de 20 min figé, ne rendait jamais la main.
    plafond = OUTAGE_MAX_WAIT_SECONDS if plafond is None else plafond
    attente = 0.0
    palier = OUTAGE_POLL_SECONDS
    while True:
        try:
            return _connect_borne(dsn)
        except ErreurConnexion as exc:
            if attente >= plafond:
                raise
            pause, palier, motif = _recul(exc, palier)
            print(f"  ⚠ {motif} — nouvel essai dans {pause:.0f}s "
                  f"(attente cumulée {attente:.0f}s/{plafond:.0f}s)", flush=True)
            # Après la pause, pas avant : le thread orphelin du tour précédent
            # a eu le temps de finir, donc c'est maintenant que sa vraie cause
            # est lisible. On la dit SANS toucher au recul déjà décidé.
            time.sleep(pause)
            _dis_la_vraie_cause()
            attente += pause

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


def _meme_instant(a, b) -> bool:
    """`posted_at` est-il inchangé ? Compare des INSTANTS, pas des chaînes.

    Le serveur rend un `timestamptz` (str → '2026-08-19 16:54:35+00:00'), le
    local stocke du texte ISO ('2026-08-19T16:54:35+00:00') : la comparaison de
    chaînes différait TOUJOURS. Mesuré le 2026-09-28 : 1,70 M lignes dans
    `posted_at_history` côté serveur contre 104 k en local, ~400 k ajoutées par
    semaine depuis que la remontée tourne (24/08), 196 Mo — la moitié du quota."""
    if a is None or b is None:
        return a is None and b is None
    def inst(x):
        if isinstance(x, datetime):
            return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
        t = datetime.fromisoformat(str(x).strip().replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    try:
        return inst(a) == inst(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


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
        # `_connect_resilient` et non `_connect_borne` : voir son docstring —
        # l'ouverture initiale n'avait AUCUNE reprise là où le reste du run en
        # avait vingt minutes, et c'est ce hoquet de 25 s qui a coûté la
        # remontée du 2026-09-09.
        self.db = _connect_resilient(dsn)
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
        self.db = _connect_borne(self.dsn)

    def _execute(self, sql: str, params=()):
        """execute avec reconnexion auto si la connexion Postgres a sauté
        (blip réseau / timeout pooler) → un blip ne tue plus le run.

        Un SEUL essai de reconnexion ne suffit pas à une coupure qui dure :
        mesuré le 2026-09-03/04, `synchroniser_statuts` a fini par lever
        malgré ce garde-fou parce que le réseau était encore coupé au moment
        précis de l'unique retry. On attend maintenant, en sondant la
        reconnexion elle-même, comme `Fetcher._attend_coupure` (fetch.py)."""
        try:
            return self.db.execute(sql, params)
        except Exception as exc:  # noqa: BLE001 — trié par _est_coupure
            if not _est_coupure(exc):
                raise
            attente = 0.0
            palier = OUTAGE_POLL_SECONDS
            while True:
                try:
                    self._reconnect()
                    return self.db.execute(sql, params)
                except Exception as exc:  # noqa: BLE001 — trié ci-dessous
                    if not (isinstance(exc, ErreurConnexion) or _est_coupure(exc)):
                        raise
                    if attente >= OUTAGE_MAX_WAIT_SECONDS:
                        raise
                    # Recul PROGRESSIF, et plus long encore si c'est le pooler
                    # qui nous ferme la porte : le 2026-09-06, 37 essais à
                    # cadence fixe de 30 s ont entretenu un ECIRCUITBREAKER
                    # jusqu'à épuisement du budget (cf. `_recul`).
                    pause, palier, motif = _recul(exc, palier)
                    print(f"  ⚠ {motif} — nouvel essai dans {pause:.0f}s "
                          f"(attente cumulée {attente:.0f}s"
                          f"/{OUTAGE_MAX_WAIT_SECONDS:.0f}s)", flush=True)
                    time.sleep(pause)
                    # Même raison qu'au démarrage : la vraie cause du tour
                    # précédent n'est lisible qu'après la pause, et une
                    # connexion atterrie en retard doit être rendue au pooler
                    # (mode session = un backend chacune).
                    _dis_la_vraie_cause()
                    attente += pause

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

    def upsert_listings_bulk(self, rows: list[dict],
                             images_by_id: dict[str, list[dict]] | None = None,
                             batch_size: int = 500) -> dict:
        """Même sémantique que `upsert_listing`, en aller-retour PAR LOT plutôt
        que par annonce — pour `ops/remonter-local.py` (tout est déjà en
        mémoire, rien n'est scrapé en flux). N'est PAS appelé par le scraper
        en ligne, qui traite une annonce à la fois par construction.

        Mesuré le 2026-08-26 sur remonter-local.py (chemin ligne à ligne,
        2 aller-retours/annonce — get_listing + upsert) : 4,1 annonces/s,
        ~4h20 pour 53 258. Cause : 2 aller-retours Bangkok↔Singapour par
        annonce, réseau-bound. Ici : 1 SELECT + 1 INSERT ON CONFLICT par lot
        de `batch_size` → le nombre d'allers-retours tombe d'un facteur
        ~2×batch_size (~1000× à batch_size=500).

        `INSERT ... ON CONFLICT DO UPDATE` plutôt que deux requêtes séparées
        (INSERT neuves / UPDATE existantes) : Postgres décide seul par ligne,
        pas besoin de scinder le lot en deux SQL différents. `first_seen`
        n'apparaît PAS dans la clause SET → une ligne déjà en base garde sa
        date d'origine (exactement le comportement de `upsert_listing`, où le
        SET de la branche UPDATE ne touche pas non plus `first_seen`).

        `DO UPDATE ... WHERE <rien n'a changé>` — ajouté le 2026-09-02. Sans
        ce garde-fou, l'upsert réécrivait TOUTES les colonnes de CHAQUE ligne
        à CHAQUE remontée, même quand la ligne était strictement identique à
        ce qui était déjà en base : `remonter-supabase` tourne en lane
        `daily` depuis le 2026-08-26 et repousse toute la fenêtre active
        (~98 000 lignes) sans filtre delta. Mesuré côté serveur le 2026-09-02
        (`pg_stat_user_tables`) : 733 375 UPDATE sur `listings` pour ~98 573
        lignes vivantes, 72 % non-HOT — donc touchant la plupart des 13 index
        de la table, tous les jours, pour une donnée inchangée dans l'immense
        majorité des cas. C'est la cause directe de l'alerte Supabase « Disk
        IO Budget depleting » : le volume de la base n'a pas bougé, seul le
        débit d'écriture explique la consommation.
        Quand la clause WHERE est fausse, Postgres traite la ligne comme un
        DO NOTHING — aucune nouvelle version de ligne, aucune écriture
        d'index, et la ligne n'apparaît pas dans RETURNING (d'où `maj` qui
        ne compte plus que les lignes RÉELLEMENT écrites, pas toutes celles
        renvoyées). `last_seen` est volontairement EXCLU de la comparaison :
        c'est justement la colonne qui changerait à chaque appel et annulerait
        le garde-fou — et `lastSeen` n'est lu nulle part côté app
        (`lib/listings-db.ts` la sélectionne, aucun composant ne la consomme).

        Retourne {'nouvelles', 'maj', 'changees'} — mêmes clés que le
        comptage fait par l'appelant autour de `upsert_listing`. `changees`
        (comptage Python, indépendant de ce garde-fou) reste le nombre de prix
        réellement modifiés — sous-ensemble de `maj`.
        """
        if not rows:
            return {"nouvelles": 0, "maj": 0, "changees": 0}
        images_by_id = images_by_id or {}
        now = _now()
        nouvelles = maj = changees = 0

        cols_sql = ",".join(_COLS)
        set_sql = ",".join(f"{c}=excluded.{c}" for c in _COLS)
        rien_change = " or ".join(f"listings.{c} is distinct from excluded.{c}" for c in _COLS)
        un_placeholder = "(" + ",".join(["%s"] * (len(_COLS) + 5)) + ")"
        insert_sql = (
            f"insert into listings (id,{cols_sql},status,first_seen,last_seen,raw_data) "
            f"values {{values}} "
            f"on conflict (id) do update set {set_sql},status='active',"
            f"last_seen=excluded.last_seen,raw_data=excluded.raw_data,"
            f"missed_count=0,first_missed_at=null,delisted_at=null "
            f"where listings.status is distinct from 'active'"
            f" or listings.missed_count is distinct from 0"
            f" or listings.first_missed_at is not null"
            f" or listings.delisted_at is not null"
            f" or listings.raw_data is distinct from excluded.raw_data"
            f" or {rien_change} "
            f"returning id, (xmax = 0) as est_nouvelle"
        )

        for i in range(0, len(rows), batch_size):
            lot = rows[i:i + batch_size]
            ids = [r["id"] for r in lot]

            # Pré-lu AVANT l'upsert du lot : après, l'ancien prix/statut a
            # disparu — c'est la même contrainte d'ordre que
            # `_track_posted_at`/`_suivre_statut_marche` sur le chemin ligne
            # à ligne (appelés avant l'UPDATE, pas après).
            existants: dict[str, dict] = {}
            for r in self._execute(
                "select id, price, posted_at, market_status, market_status_since "
                "from listings where id = any(%s)", (ids,),
            ).fetchall():
                existants[r[0]] = {"price": r[1], "posted_at": r[2],
                                   "market_status": r[3], "market_status_since": r[4]}

            params: list = []
            prix_a_historiser: list[tuple] = []
            posted_a_historiser: list[tuple] = []
            statuts_a_dater: list[tuple] = []
            for r in lot:
                lid = r["id"]
                existant = existants.get(lid)
                vals = [_coerce(c, r.get(c)) for c in _COLS]
                params += [lid, *vals, "active", now, now, Json(r.get("raw_data", {}))]

                nouveau_posted = r.get("posted_at")
                if existant is None:
                    if r.get("price") is not None:
                        prix_a_historiser.append((lid, r["price"], now))
                    if nouveau_posted:
                        posted_a_historiser.append((lid, nouveau_posted, now))
                    continue
                if nouveau_posted and not _meme_instant(existant.get("posted_at"), nouveau_posted):
                    posted_a_historiser.append((lid, nouveau_posted, now))
                nouveau_statut = r.get("market_status")
                if (existant.get("market_status") or None) != (nouveau_statut or None):
                    statuts_a_dater.append((lid, now if nouveau_statut else None))
                old_price, new_price = existant.get("price"), r.get("price")
                if new_price is not None and old_price is not None and float(new_price) != float(old_price):
                    prix_a_historiser.append((lid, new_price, now))
                    changees += 1

            values_sql = ",".join([un_placeholder] * len(lot))
            for est_nouvelle in (
                r[1] for r in self._execute(
                    insert_sql.format(values=values_sql), params).fetchall()
            ):
                nouvelles += est_nouvelle
                maj += not est_nouvelle

            if prix_a_historiser:
                ph_placeholder = ",".join(["(%s,%s,%s)"] * len(prix_a_historiser))
                self._execute(
                    "insert into price_history (listing_id,price,observed_at) "
                    f"values {ph_placeholder}",
                    [v for tup in prix_a_historiser for v in tup],
                )
            if posted_a_historiser:
                pa_placeholder = ",".join(["(%s,%s,%s)"] * len(posted_a_historiser))
                self._execute(
                    "insert into posted_at_history (listing_id,posted_at,observed_at) "
                    f"values {pa_placeholder}",
                    [v for tup in posted_a_historiser for v in tup],
                )
            for lid, quand in statuts_a_dater:      # rare : pas de lot dédié
                self._maj_since(lid, quand)

            if images_by_id:
                ids_avec_images = [lid for lid in ids if lid in images_by_id]
                if ids_avec_images:
                    self._execute(
                        "delete from listing_images where listing_id = any(%s)",
                        (ids_avec_images,),
                    )
                    lignes_img = [
                        (lid, im["storage_path"], im.get("width"), im.get("height"), im.get("ord", 0))
                        for lid in ids_avec_images for im in images_by_id[lid]
                    ]
                    if lignes_img:
                        img_placeholder = ",".join(["(%s,%s,%s,%s,%s)"] * len(lignes_img))
                        self._execute(
                            "insert into listing_images (listing_id,storage_path,width,height,ord) "
                            f"values {img_placeholder}",
                            [v for tup in lignes_img for v in tup],
                        )

        return {"nouvelles": nouvelles, "maj": maj, "changees": changees}

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
        if ancien and _meme_instant(ancien, nouveau):
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
