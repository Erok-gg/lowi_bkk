"""pg.py — connexion Postgres (Supabase) en Python pur, à la manière de psycopg.

POURQUOI CE MODULE EXISTE
Le 2026-10-09, Smart App Control a bloqué la DLL libpq de `psycopg_binary`
(remontée de la nuit morte en 9 s ; jugement de RÉPUTATION, qui bascule sans
préavis dans les deux sens). Le chemin d'écriture (`supabase_store.py`) est
passé à pg8000 le jour même ; ce module porte la même connexion pour les
outils manuels (`ops/verifie-synchro.py`, `ops/sync_supabase_local.py`,
`agents/core/db.py` en LOWI_STORE=supabase), qui retombaient sinon à la
prochaine bascule.

COMPATIBILITÉ — seul le sous-ensemble de psycopg que le dépôt utilise :
`connecter(dsn)` comme `psycopg.connect(dsn)` (transaction implicite,
`with` = commit si tout va bien / rollback sinon, puis fermeture),
`conn.execute()` qui rend le curseur, `conn.cursor()`, `commit`, `rollback`,
`close` ; curseur avec `execute` (rend le curseur), `fetchone/fetchall/
fetchmany` qui rendent des TUPLES (pg8000 rend des listes — non hachables,
une ligne servant de clé de set ou de dict aurait cassé), `description`,
`rowcount`, itération.
"""
from __future__ import annotations

import ssl
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


class Curseur:
    def __init__(self, brut):
        self.brut = brut

    def execute(self, sql: str, params=None):
        sql, params = _requete(sql, params)
        self.brut.execute(sql, params)
        return self

    @property
    def description(self):
        return self.brut.description

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

    def cursor(self) -> Curseur:
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
