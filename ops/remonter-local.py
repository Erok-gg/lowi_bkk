"""remonter-local.py — pousse un scrap LOCAL validé vers Supabase.

Raison d'être : un cycle complet dure 6 à 10 heures. Le refaire en ligne après
validation gaspillerait ce temps et solliciterait les sources une seconde fois
sans raison. Ce script transfère ce qui a déjà été collecté.

Il réutilise `SupabaseStore.upsert_listing` — le MÊME chemin d'écriture que le
scraper. Rien de spécifique n'est réinventé : l'historique de prix, les images et
les amenities suivent la même logique qu'un scrap en ligne.

CE QU'IL NE FAIT PAS, volontairement :
  - aucune suppression, aucun écrasement de champ par une valeur vide.
  - aucun délistage DÉDUIT. Un transfert n'est pas un scan : il ne peut pas
    conclure qu'une annonce absente a disparu du marché. Il peut en revanche
    RECOPIER un délistage déjà tranché en local (voir --synchro-statuts).

────────────────────────────────────────────────────────────────────────────
PÉRIMÈTRE DE REMONTÉE — pourquoi `--statut actives` (arbitrage du 2026-08-26)
────────────────────────────────────────────────────────────────────────────
Le serveur est une FENÊTRE CHAUDE : il sert le marché consultable. L'historique
des annonces mortes reste local, où il alimente les statistiques d'évolution
dans le temps (study/run_study.py, snapshots).

CE QUI REND LE FILTRE OBLIGATOIRE, et pas seulement souhaitable :
`SupabaseStore.upsert_listing` force `status='active'` et remet `delisted_at` à
null (supabase_store.py, l. 134-135) — c'est correct pour un scrap, qui n'upsert
que ce qu'il vient de voir en ligne. Mais remonter TOUTE la base par ce chemin
RESSUSCITERAIT les 23 684 annonces délistées en actives sur le site public.
Mesuré le 2026-08-26. Le périmètre « actives seules » n'est donc pas seulement
le plus léger (132 Mo contre 157) : c'est le seul qui ne corrompt pas le serveur.

CONTREPARTIE, mesurée elle aussi : un transfert d'actives ne PROPAGE PAS les
morts. Les annonces délistées en local depuis le dernier envoi restent `active`
côté serveur — vérifié sur 400 identifiants tirés au sort : 400/400 encore
actives en ligne, soit ~1 876 annonces fantômes affichées comme disponibles, et
ce chiffre croît à chaque cycle. D'où `--synchro-statuts`, qui recopie le statut
local (status + delisted_at) sur les lignes que le serveur croit encore vivantes.
Il ne DÉDUIT rien : le délai de grâce a déjà été appliqué par le vrai scan, en
local. C'est une recopie, pas un jugement.

Usage :
    python ops/remonter-local.py <dossier> --dry-run              # compte, n'écrit rien
    python ops/remonter-local.py <dossier> --statut actives       # scénario A
    python ops/remonter-local.py <dossier> --statut actives --synchro-statuts
    python ops/remonter-local.py <dossier> --avec-images          # + upload Storage
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scraper"))

for _l in open(os.path.join(ROOT, "scraper", ".env"), encoding="utf-8"):
    _l = _l.strip()
    if _l and not _l.startswith("#") and "=" in _l:
        _k, _v = _l.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip())


def charger(db_path: str, statut: str = "tout") -> list[dict]:
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    # PAS de `select *` : depuis le degraissage du 2026-08-25, la base locale
    # porte `page_text` (453 Mo) et `description` (137 Mo) que le serveur n'a
    # plus. Un `select *` sur 72 000 annonces chargeait ~600 Mo de texte en
    # memoire pour le jeter aussitot — le store ne les ecrit plus. On ne lit que
    # le socle commun, augmente des colonnes de service dont l'upsert a besoin.
    from store.base import COLONNES_LISTING
    colonnes = ("id", *COLONNES_LISTING, "status", "first_seen", "last_seen", "raw_data")
    # `actives` = scénario A. Le filtre est au SELECT et non après coup : sur
    # 76 942 lignes, charger puis jeter 23 684 dicts coûte pour rien.
    where = " where status='active'" if statut == "actives" else ""
    lignes = [dict(r) for r in db.execute(
        f"select {','.join(colonnes)} from listings{where}")]
    for l in lignes:
        # raw_data est stocké en TEXT côté SQLite, en jsonb côté Postgres
        if isinstance(l.get("raw_data"), str):
            try:
                l["raw_data"] = json.loads(l["raw_data"])
            except json.JSONDecodeError:
                l["raw_data"] = {}
        # is_auto_repost : integer côté SQLite, boolean côté Postgres
        if l.get("is_auto_repost") is not None:
            l["is_auto_repost"] = bool(l["is_auto_repost"])
        # photo_sizes : TEXT JSON côté SQLite, ARRAY côté Postgres
        if isinstance(l.get("photo_sizes"), str):
            try:
                l["photo_sizes"] = json.loads(l["photo_sizes"])
            except json.JSONDecodeError:
                l["photo_sizes"] = None
        l["amenities"] = []
        l["image_urls"] = []
    return lignes


def images_de(db_path: str) -> dict[str, list[dict]]:
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    out: dict[str, list[dict]] = {}
    try:
        for r in db.execute("select * from listing_images order by listing_id, \"order\""):
            out.setdefault(r["listing_id"], []).append(dict(r))
    except sqlite3.OperationalError:
        pass
    return out


def statuts_morts(db_path: str) -> list[tuple[str, str, str | None]]:
    """Les annonces que le LOCAL sait mortes : (id, status, delisted_at).

    `status` distingue 'inactive' (disparue de la source) de 'sold' (marqueur
    vendu observé sur la fiche) — la nuance est portée jusqu'au serveur, elle
    ne se recalcule pas.
    """
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    return [
        (r[0], r[1], r[2])
        for r in db.execute(
            "select id, status, delisted_at from listings where status<>'active'"
        )
    ]


def synchroniser_statuts(store, morts, dry_run: bool) -> int:
    """Recopie le statut local sur les lignes que le serveur croit ACTIVES.

    Volontairement un UPDATE ciblé et non un upsert : l'upsert forcerait
    `status='active'`, soit exactement l'inverse. La clause `and status='active'`
    rend l'opération IDEMPOTENTE et sans effet sur ce qui est déjà à jour.
    """
    if dry_run:
        return 0
    touchees = 0
    for i, (lid, statut, delisted) in enumerate(morts, 1):
        r = store._execute(
            "update listings set status=%s, delisted_at=coalesce(%s, delisted_at, now())"
            " where id=%s and status='active' returning id",
            (statut, delisted, lid),
        ).fetchall()
        touchees += len(r)
        if i % 2000 == 0:
            print(f"  … statuts {i}/{len(morts)} ({touchees} corrigés)")
    return touchees


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dossier")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limite", type=int, default=None,
                    help="ne traiter que les N premieres annonces (mesure de debit)")
    ap.add_argument("--avec-images", action="store_true",
                    help="upload aussi les fichiers vers Supabase Storage")
    # Defaut `tout` : le comportement historique ne change pas sans qu'on le
    # demande. Un appelant existant continue de faire exactement ce qu'il faisait.
    ap.add_argument("--statut", choices=("tout", "actives"), default="tout",
                    help="perimetre remonte. `actives` = scenario A (2026-08-26) : "
                         "le serveur est une fenetre chaude, l'historique reste local")
    ap.add_argument("--synchro-statuts", action="store_true",
                    help="recopie les delistages deja tranches en local sur les "
                         "lignes que le serveur croit encore actives")
    a = ap.parse_args()

    db_path = os.path.join(a.dossier, "bangkok.db")
    if not os.path.exists(db_path):
        print(f"ERREUR - base introuvable : {db_path}")
        return 2

    lignes = charger(db_path, a.statut)
    morts = statuts_morts(db_path) if a.synchro_statuts else []
    if a.limite:
        lignes = lignes[:a.limite]
    imgs = images_de(db_path)
    par_source: dict[str, int] = {}
    for l in lignes:
        par_source[l["source"]] = par_source.get(l["source"], 0) + 1

    print(f"Source     : {db_path}")
    print(f"Périmètre  : --statut {a.statut}"
          + ("  (scénario A — le serveur ne porte que le marché consultable)"
             if a.statut == "actives" else
             "  ⚠ upsert force status='active' : les délistées seraient RESSUSCITÉES"))
    print(f"À remonter : {len(lignes)} annonces — " +
          ", ".join(f"{s} {n}" for s, n in sorted(par_source.items())))
    print(f"Images     : {sum(len(v) for v in imgs.values())} pour {len(imgs)} annonces")
    if a.synchro_statuts:
        print(f"Statuts    : {len(morts)} annonces mortes en local à recopier "
              f"(seules celles encore 'active' en ligne seront touchées)")

    if a.dry_run:
        print("\n[dry-run] rien n'a été écrit.")
        print("Retirer --dry-run pour transférer vers Supabase.")
        return 0

    dsn = os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        print("ERREUR - SUPABASE_DB_URL manquant (scraper/.env)")
        return 2

    from store.supabase_store import SupabaseStore
    store = SupabaseStore(dsn)

    storage = None
    if a.avec_images:
        try:
            from pipeline import storage as storage_mod
            storage = storage_mod.SupabaseStorage.from_env()
            print(f"Storage    : bucket '{storage.bucket}'")
        except Exception as e:  # noqa: BLE001
            print(f"! upload Storage indisponible ({e}) — métadonnées seulement")

    # VERROU D'INSTANCE UNIQUE. Le 2026-08-03, deux exemplaires de ce script ont
    # tourné en concurrence sur la MÊME base : le premier n'avait pas été arrêté
    # avant le lancement du second, après correction d'un conflit de type. Sans
    # dommage durable — les deux écrivaient par upsert — mais 16 990 écritures
    # perdues et une charge inutile sur Supabase. Rien ne l'empêchait.
    sys.path.insert(0, ROOT)
    from agents.core.gpu import Verrou

    # Pris pour toute la durée du processus. Pas de `with` : le verrou est posé
    # par le SYSTÈME sur un descripteur ouvert, donc il se relâche tout seul à la
    # mort du processus — plantage compris. C'est exactement ce qu'on veut ici.
    Verrou("remonter-local").__enter__()

    nouvelles = maj = erreurs = 0
    for i, l in enumerate(lignes, 1):
        try:
            existant = store.get_listing(l["id"])
            store.upsert_listing(l, imgs.get(l["id"]))
            if existant:
                maj += 1
            else:
                nouvelles += 1
            if storage:
                for im in imgs.get(l["id"], []):
                    chemin = os.path.join(a.dossier, im["storage_path"])
                    if os.path.exists(chemin):
                        storage.upload(chemin, im["storage_path"])
        except Exception as e:  # noqa: BLE001
            erreurs += 1
            if erreurs <= 5:
                print(f"  [erreur] {l['id']} : {type(e).__name__} {e}")
        if i % 500 == 0:
            print(f"  … {i}/{len(lignes)} ({nouvelles} nouvelles, {maj} mises à jour)")

    print(f"\nOK - Terminé — {nouvelles} nouvelles, {maj} mises à jour, {erreurs} erreur(s)")

    if a.synchro_statuts:
        print(f"\nRecopie des statuts ({len(morts)} candidates)…")
        corriges = synchroniser_statuts(store, morts, a.dry_run)
        print(f"OK - {corriges} annonces fantômes corrigées "
              f"(les autres étaient déjà à jour côté serveur)")
    else:
        print("  Aucun délistage propagé : les annonces mortes depuis le dernier")
        print("  envoi restent 'active' en ligne. Utiliser --synchro-statuts.")
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
