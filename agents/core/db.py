"""db.py — accès Supabase pour les agents.

Reprend le pattern éprouvé de study/run_study.py : les variables viennent de
scraper/.env, la connexion passe par le pooler session (bypass RLS).
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.dirname(ROOT)
_LOADED = False


def load_env() -> None:
    global _LOADED
    if _LOADED:
        return
    for name in ("scraper/.env", ".env.local"):
        path = os.path.join(PROJECT, name)
        if not os.path.exists(path):
            continue
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    sys.path.insert(0, os.path.join(PROJECT, "scraper"))
    _LOADED = True


def store() -> str:
    """OÙ VIT LA DONNÉE. Local par défaut depuis le 2026-08-23.

    Constaté le 2026-08-25 : les trois agents d'analyse lisaient encore Supabase
    deux jours après la bascule. Ils n'ont pas produit de faux chiffres — une
    panne DNS les a fait tomber avant — mais c'était une chance : ils auraient
    analysé une base figée le 22/08 en la présentant comme l'état du jour. Un
    agent qui lit la mauvaise base ne se trompe pas bruyamment, il se trompe
    exactement comme s'il avait raison."""
    return os.environ.get("LOWI_STORE", "sqlite")


def chemin_sqlite() -> str:
    p = os.environ.get("LOWI_DB") or os.path.join(
        os.environ.get("LOWI_OUTPUT_DIR") or os.path.join(PROJECT, "scraper", "output"),
        "bangkok.db")
    if not os.path.exists(p):
        raise RuntimeError(f"base locale introuvable : {p} "
                           f"(LOWI_STORE=supabase pour relire le serveur)")
    return p


class _Mediane:
    """Médiane, en agrégat SQLite.

    SQLite n'a pas `percentile_cont`. Plutôt que de réécrire les requêtes des
    agents — et de risquer que les deux versions divergent, ce qui est arrivé
    trois fois dans ce dépôt — on enseigne la médiane à SQLite et les requêtes
    restent LES MÊMES des deux côtés, à un nom de fonction près (cf. MEDIANE)."""

    def __init__(self):
        self.valeurs = []

    def step(self, valeur):
        if valeur is not None:
            self.valeurs.append(float(valeur))

    def finalize(self):
        v = sorted(self.valeurs)
        if not v:
            return None
        m = len(v) // 2
        return v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2.0


def MEDIANE(expr: str) -> str:
    """Fragment SQL de médiane, dans le dialecte du stockage actif."""
    if store() == "sqlite":
        return f"mediane({expr})"
    return f"percentile_cont(0.5) within group (order by {expr})"


# ── LE RESTE DU DIALECTE ────────────────────────────────────────────────────
# Quatre fragments, et c'est tout ce qui séparait les requêtes des agents des
# deux moteurs. On les nomme ici plutôt que de tenir deux versions de chaque
# requête : deux versions finissent toujours par diverger — c'est arrivé trois
# fois dans ce dépôt (bornes de plausibilité, médiane vs moyenne, arrondi de
# tranche), et chaque fois le défaut a vécu des semaines.

def CLE_TEXTE(expr: str) -> str:
    """Nom d'immeuble réduit à ses lettres et chiffres, en minuscules.

    C'est la clé de regroupement des doublons : « The Line Asoke-Ratchada » et
    « The Line Asoke Ratchada » doivent tomber dans le même paquet."""
    if store() == "sqlite":
        return f"cle_texte({expr})"
    return f"lower(regexp_replace(coalesce({expr},''), '[^a-zA-Z0-9]', '', 'g'))"


def PLUS_GRAND(a: str, b: str) -> str:
    """max() de SQLite prend deux arguments scalaires ; Postgres dit greatest."""
    return f"max({a}, {b})" if store() == "sqlite" else f"greatest({a}, {b})"


def REEL(expr: str) -> str:
    """Force une division en flottant (SQLite divise deux entiers en entier)."""
    return f"cast({expr} as real)" if store() == "sqlite" else f"{expr}::float"


def ECART_JOURS(fin: str, debut: str) -> str:
    """Nombre de jours entre deux horodatages ISO."""
    if store() == "sqlite":
        return f"(julianday({fin}) - julianday({debut}))"
    return f"extract(epoch from ({fin} - {debut})) / 86400.0"


def definition_vue(nom: str) -> str | None:
    """Texte SQL d'une vue — sert au contrôle d'alignement des bornes.

    Les deux moteurs le rangent ailleurs : catalogue système pour SQLite,
    fonction dédiée pour Postgres."""
    if store() == "sqlite":
        rows = query("select sql from sqlite_master where type='view' and name=%s", (nom,))
        return rows[0]["sql"] if rows else None
    return scalar(f"select pg_get_viewdef('{nom}'::regclass, true)")


def _cle_texte(valeur) -> str:
    """Implémentation Python de CLE_TEXTE, enseignée à SQLite."""
    if not valeur:
        return ""
    return "".join(c for c in str(valeur) if c.isalnum()).lower()


def connect():
    load_env()
    if store() == "sqlite":
        import sqlite3
        conn = sqlite3.connect(f"file:{chemin_sqlite()}?mode=ro", uri=True)
        conn.create_aggregate("mediane", 1, _Mediane)
        conn.create_function("cle_texte", 1, _cle_texte, deterministic=True)
        return conn
    # pg8000 (Python pur) et non psycopg depuis le 2026-10-09 : Smart App
    # Control bloquait la DLL libpq. Importé après load_env pour le sys.path.
    from store.pg import connecter
    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        raise RuntimeError("SUPABASE_DB_URL absent de scraper/.env et .env.local")
    return connecter(url)


def query(sql: str, params: tuple = ()) -> list[dict]:
    if store() == "sqlite":
        # Les agents écrivent leurs paramètres au format psycopg (%s) ; SQLite
        # attend `?`. La traduction vit ICI, pas dans chaque agent.
        conn = connect()
        try:
            cur = conn.execute(sql.replace("%s", "?"), params)
            if cur.description is None:
                return []
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            conn.close()
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        if cur.description is None:
            return []
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def scalar(sql: str, params: tuple = ()):
    rows = query(sql, params)
    if not rows:
        return None
    return next(iter(rows[0].values()))
