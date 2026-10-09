"""pg.py — connexion Postgres (Supabase) en Python pur, à la manière de psycopg.

POURQUOI CE MODULE EXISTE
Le 2026-10-09, Smart App Control a bloqué la DLL libpq de `psycopg_binary`
(remontée de la nuit morte en 9 s ; jugement de RÉPUTATION, qui bascule sans
préavis dans les deux sens). Le chemin d'écriture (`supabase_store.py`) est
passé à pg8000 le jour même, puis TOUT le dépôt : outils manuels, scripts
ponctuels, étude en LOWI_STORE=supabase. psycopg n'est plus importé nulle part.

COMPATIBILITÉ — seul le sous-ensemble de psycopg que le dépôt utilise :
`connecter(dsn)` comme `psycopg.connect(dsn)` (transaction implicite,
`with` = commit si tout va bien / rollback sinon, puis fermeture),
`conn.execute()` qui rend le curseur, `conn.cursor()`, `commit`, `rollback`,
`close` ; curseur avec `execute` (rend le curseur), `fetchone/fetchall/
fetchmany` qui rendent des TUPLES (pg8000 rend des listes — non hachables,
une ligne servant de clé de set ou de dict aurait cassé), `executemany`,
`description` (colonnes avec `.name`), `rowcount`, itération, et
`cursor(name=...)` en curseur serveur (DECLARE / FETCH).
"""
from __future__ import annotations

import ssl
from collections import namedtuple
from urllib.parse import unquote, urlsplit

import pg8000.dbapi

#: Délai de chaque opération de socket. pg8000 n'a qu'UN réglage (connexion ET
#: requêtes), là où libpq n'avait que `connect_timeout`. 20-30 s aurait coupé
#: des requêtes légitimes : le 2026-10-06 un checkpoint d'un buffer prenait
#: 17 à 22 s côté serveur. 300 s borne une socket morte sans couper une requête
#: lente — le `statement_timeout` du serveur tombe avant.
SOCKET_TIMEOUT = 300.0


def parametres(dsn: str, timeout: float = SOCKET_TIMEOUT,
               application_name: str = "lowi") -> dict:
    """DSN `postgresql://user:pwd@host:port/db` → arguments de pg8000.connect.

    SSL : chiffré SANS vérification du certificat, exactement ce que faisait
    libpq avec ce DSN (pas de `sslmode` → `prefer`). Mesuré le 2026-10-09 :
    la vérification échoue (« self-signed certificate in certificate chain »),
    le pooler présente un certificat de la CA propre à Supabase. Vérifier
    exigerait d'embarquer cette CA — amélioration possible, pas une régression."""
    u = urlsplit(dsn)
    contexte = ssl.create_default_context()
    contexte.check_hostname = False
    contexte.verify_mode = ssl.CERT_NONE
    return {"user": unquote(u.username or ""), "password": unquote(u.password or ""),
            "host": u.hostname, "port": u.port or 5432,
            "database": unquote(u.path.lstrip("/")) or "postgres",
            "ssl_context": contexte, "timeout": timeout,
            "application_name": application_name}


def _requete(sql: str, params):
    """Aligne la substitution des `%` sur psycopg.

    psycopg interprète les `%` dès que `params` n'est pas None, même vide
    (`%%` → `%`) ; pg8000 seulement s'il y a au moins un paramètre. Sans ce
    pont, un `like 'a%%'` passé avec `()` partirait tel quel au serveur."""
    if params is None:
        return sql, ()
    params = tuple(params)
    if not params and "%%" in sql:
        sql = sql.replace("%%", "%")
    return sql, params


#: Colonne de `description` : indexable (`c[0]`) ET nommée (`c.name`), comme
#: celle de psycopg — `study/run_study.py` et un test lisent `c.name`.
Colonne = namedtuple("Colonne", "name type_code display_size internal_size "
                                "precision scale null_ok")


def _description(brute):
    if brute is None:
        return None
    return [Colonne(*(tuple(d) + (None,) * 7)[:7]) for d in brute]


class Curseur:
    def __init__(self, brut):
        self.brut = brut

    def execute(self, sql: str, params=None):
        sql, params = _requete(sql, params)
        self.brut.execute(sql, params)
        return self

    def executemany(self, sql: str, lots) -> "Curseur":
        self.brut.executemany(sql, [tuple(p) for p in lots])
        return self

    @property
    def description(self):
        return _description(self.brut.description)

    @property
    def rowcount(self) -> int:
        return self.brut.rowcount

    def fetchone(self):
        ligne = self.brut.fetchone()
        return tuple(ligne) if ligne is not None else None

    def fetchall(self) -> list[tuple]:
        return [tuple(r) for r in self.brut.fetchall()]

    def fetchmany(self, taille: int | None = None) -> list[tuple]:
        lignes = self.brut.fetchmany(taille) if taille else self.brut.fetchmany()
        return [tuple(r) for r in lignes]

    def __iter__(self):
        return (tuple(r) for r in self.brut)

    def close(self) -> None:
        self.brut.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class CurseurNomme:
    """Curseur SERVEUR, comme `conn.cursor(name=...)` de psycopg.

    pg8000 charge tout le résultat en mémoire à l'`execute`. Les scripts qui
    balaient une table entière par `fetchmany` (`ops/rapatrie-textes.py`,
    `ops/verifie-avant-degraissage.py` : jusqu'à 613 000 lignes) comptaient
    sur un flux. On le rend avec DECLARE / FETCH, exactement ce que fait
    psycopg sous le capot. Exige une transaction (connexion non autocommit,
    le défaut de `connecter`)."""

    def __init__(self, brute, nom: str):
        self.brute = brute
        self.nom = '"' + nom.replace('"', '""') + '"'
        self.itersize = 2000
        self.description = None
        self.ouvert = False

    def _fetch(self, quantite: str) -> list[tuple]:
        cur = self.brute.cursor()
        cur.execute(f"fetch {quantite} from {self.nom}")
        self.description = _description(cur.description)
        return [tuple(r) for r in cur.fetchall()]

    def execute(self, sql: str, params=None) -> "CurseurNomme":
        if self.ouvert:
            self.close()
        sql, params = _requete(sql, params)
        self.brute.cursor().execute(f"declare {self.nom} no scroll cursor for {sql}", params)
        self.ouvert = True
        return self

    def fetchone(self):
        lignes = self._fetch("next")
        return lignes[0] if lignes else None

    def fetchmany(self, taille: int | None = None) -> list[tuple]:
        return self._fetch(f"forward {int(taille or self.itersize)}")

    def fetchall(self) -> list[tuple]:
        return self._fetch("all")

    def __iter__(self):
        while True:
            lot = self.fetchmany()
            if not lot:
                return
            yield from lot

    def close(self) -> None:
        if self.ouvert:
            try:
                self.brute.cursor().execute(f"close {self.nom}")
            except Exception:  # noqa: BLE001 — transaction déjà close : rien à fermer
                pass
            self.ouvert = False

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class Connexion:
    def __init__(self, brute, autocommit: bool = False):
        self.brute = brute
        self.brute.autocommit = autocommit

    @property
    def autocommit(self) -> bool:
        return self.brute.autocommit

    @autocommit.setter
    def autocommit(self, valeur: bool) -> None:
        self.brute.autocommit = valeur

    def cursor(self, name: str | None = None):
        if name:
            return CurseurNomme(self.brute, name)
        return Curseur(self.brute.cursor())

    def execute(self, sql: str, params=None) -> Curseur:
        return self.cursor().execute(sql, params)

    def commit(self) -> None:
        self.brute.commit()

    def rollback(self) -> None:
        self.brute.rollback()

    def close(self) -> None:
        self.brute.close()

    def __enter__(self):
        return self

    def __exit__(self, type_exc, exc, tb) -> None:
        # Même sémantique que `with psycopg.connect(...)` : valide si le bloc
        # s'est bien passé, annule sinon, et ferme dans les deux cas.
        try:
            if not self.autocommit:
                if type_exc is None:
                    self.commit()
                else:
                    self.rollback()
        finally:
            self.close()


def connecter(dsn: str, autocommit: bool = False, timeout: float = SOCKET_TIMEOUT,
              application_name: str = "lowi") -> Connexion:
    """Équivalent de `psycopg.connect(dsn)` sans DLL native."""
    return Connexion(pg8000.dbapi.connect(**parametres(dsn, timeout, application_name)),
                     autocommit=autocommit)
