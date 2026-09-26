"""remonter-local.py — pousse un scrap LOCAL validé vers Supabase.

Raison d'être : un cycle complet dure 6 à 10 heures. Le refaire en ligne après
validation gaspillerait ce temps et solliciterait les sources une seconde fois
sans raison. Ce script transfère ce qui a déjà été collecté.

Écrit PAR LOTS depuis le 2026-08-28 (`SupabaseStore.upsert_listings_bulk`,
--lot annonces par aller-retour, défaut 500) — PAS `upsert_listing`, le chemin
ligne à ligne du scraper en ligne (qui, lui, n'a rien à batcher : il découvre
les annonces une à une). Même sémantique malgré tout (mêmes colonnes, mêmes
règles first_seen/price_history/posted_at_history) : agents/tests/
test_remonter_bulk.py compare explicitement les deux chemins. Raison du
changement : le chemin ligne à ligne (2 allers-retours Bangkok↔Singapour par
annonce) mesurait 4,1 annonces/s le 2026-08-26, soit ~4h20 pour 53 258 — assez
pour faire déborder `ExecutionTimeLimit` de `LowiBKK-Agents` 3 nuits de suite
(26 au 28/08, agents/audits/reparations-2026-08-2{7,8}.md). Par lots :
~250 annonces/s mesuré le 2026-08-28, ~4 min pour 61 246.

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
    python ops/remonter-local.py <dossier> --delta                # (2026-09-07) nouveau/sorti uniquement
    python ops/remonter-local.py <dossier> --avec-images          # + upload Storage
    python ops/remonter-local.py <dossier> --lot 200              # taille de lot (défaut 500)
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


def charger(db_path: str, statut: str = "tout", delta: bool = False) -> list[dict]:
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
    conditions = []
    if statut == "actives":
        conditions.append("status='active'")
    if delta:
        # --delta (2026-09-07) : ne remonter que ce qui a réellement changé
        # depuis le dernier envoi réussi (`dirty_since` posé par
        # SqliteStore.upsert_listing/mark_missing_inactive/appliquer_ventes),
        # au lieu de réévaluer toute la fenêtre active chaque jour.
        conditions.append("dirty_since is not null")
    where = (" where " + " and ".join(conditions)) if conditions else ""
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


def statuts_morts(db_path: str, delta: bool = False) -> list[tuple[str, str, str | None]]:
    """Les annonces que le LOCAL sait mortes : (id, status, delisted_at).

    `status` distingue 'inactive' (disparue de la source) de 'sold' (marqueur
    vendu observé sur la fiche) — la nuance est portée jusqu'au serveur, elle
    ne se recalcule pas.

    `delta=True` (2026-09-07) : ne prendre que celles délistées DEPUIS le
    dernier envoi réussi (`dirty_since is not null`), pas tout l'historique
    des mortes — sinon le lot croît indéfiniment (30 491 candidates mesurées
    le 2026-09-06 pour un stock qui n'en a délisté qu'une poignée ce jour-là).
    """
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    where = "status<>'active'" + (" and dirty_since is not null" if delta else "")
    return [
        (r[0], r[1], r[2])
        for r in db.execute(f"select id, status, delisted_at from listings where {where}")
    ]


def marquer_synchronise(db_path: str, ids: list[str]) -> None:
    """Efface `dirty_since` pour les lignes qu'on vient de pousser avec succès
    — qu'elles aient ou non déclenché une écriture réelle côté Postgres (le
    garde-fou `WHERE <rien n'a changé>` peut avoir fait un no-op, ça reste un
    envoi réussi : local et distant sont désormais alignés).

    Seul point d'écriture de ce script sur la base locale (tout le reste est
    lu en `mode=ro`) — nécessaire pour que le delta ne repousse pas demain ce
    qui vient d'être confirmé aujourd'hui. `busy_timeout` aligné sur
    `ATTENTE_VERROU_S` de SqliteStore : ce script tourne APRÈS les extracteurs
    dans la lane (jamais en parallèle d'une écriture), mais un verrou WAL
    résiduel ne doit pas faire échouer la mise à jour pour rien.
    """
    if not ids:
        return
    db = sqlite3.connect(db_path, timeout=60)
    db.execute("pragma busy_timeout=60000")
    for i in range(0, len(ids), 500):
        lot = ids[i:i + 500]
        trous = ",".join("?" * len(lot))
        db.execute(f"update listings set dirty_since=null where id in ({trous})", lot)
    db.commit()
    db.close()


def synchroniser_statuts(store, morts, dry_run: bool, batch_size: int = 5000,
                          apres_lot=None) -> int:
    """Recopie le statut local sur les lignes que le serveur croit ACTIVES.

    Volontairement un UPDATE ciblé et non un upsert : l'upsert forcerait
    `status='active'`, soit exactement l'inverse. La clause `and status='active'`
    rend l'opération IDEMPOTENTE et sans effet sur ce qui est déjà à jour.

    Par lot via `unnest` (3 tableaux → une "table" éphémère côté serveur) :
    un aller-retour pour `batch_size` lignes au lieu d'un par annonce — même
    logique de mise en lots que `upsert_listings_bulk`, mesurée le 2026-08-28
    (débit ligne à ligne réseau-bound, ~2 allers-retours Bangkok↔Singapour
    par annonce).

    `apres_lot(ids)`, si fourni, est appelé avec la liste COMPLÈTE des ids du
    lot une fois l'aller-retour réussi (`--delta` : efface `dirty_since` en
    local) — même si `RETURNING` n'en renvoie aucun (déjà à jour côté serveur
    est un succès de synchronisation, pas un échec).
    """
    if dry_run or not morts:
        return 0
    touchees = 0
    for i in range(0, len(morts), batch_size):
        lot = morts[i:i + batch_size]
        ids = [m[0] for m in lot]
        statuts = [m[1] for m in lot]
        delistes = [m[2] for m in lot]
        r = store._execute(
            "update listings as l set status=m.status,"
            " delisted_at=coalesce(m.delisted_at::timestamptz, l.delisted_at, now())"
            " from (select unnest(%s::text[]) as id, unnest(%s::text[]) as status,"
            "       unnest(%s::text[]) as delisted_at) as m"
            " where l.id=m.id and l.status='active' returning l.id",
            (ids, statuts, delistes),
        ).fetchall()
        touchees += len(r)
        if apres_lot:
            apres_lot(ids)
        print(f"  … statuts {min(i + batch_size, len(morts))}/{len(morts)} ({touchees} corrigés)")
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
    ap.add_argument("--delta", action="store_true",
                    help="(2026-09-07) ne remonte QUE ce qui a change depuis le "
                         "dernier envoi reussi (dirty_since), au lieu de "
                         "reevaluer toute la fenetre active chaque jour. Implique "
                         "--statut actives + --synchro-statuts (les deux sont le "
                         "meme mecanisme : nouveau contenu / sortie du stock)")
    ap.add_argument("--lot", type=int, default=500,
                    help="taille de lot pour l'upsert par lots (defaut 500 ; "
                         "voir SupabaseStore.upsert_listings_bulk)")
    # 3 : chaque lot épuise jusqu'à 1 200 s d'attente avant d'échouer, donc ~1 h
    # de panne continue avant d'abandonner. Une coupure brève (1 lot perdu, cas
    # du 18/09) ne déclenche rien. Seuil PROPOSÉ le 2026-09-26, à arbitrer.
    ap.add_argument("--max-lots-en-echec", type=int, default=3,
                    help="lots consecutifs en echec avant abandon (defaut 3, "
                         "~1 h de panne Supabase)")
    a = ap.parse_args()
    if a.delta:
        a.statut = "actives"
        a.synchro_statuts = True

    db_path = os.path.join(a.dossier, "bangkok.db")
    if not os.path.exists(db_path):
        print(f"ERREUR - base introuvable : {db_path}")
        return 2

    lignes = charger(db_path, a.statut, delta=a.delta)
    morts = statuts_morts(db_path, delta=a.delta) if a.synchro_statuts else []
    if a.limite:
        lignes = lignes[:a.limite]
    imgs = images_de(db_path)
    par_source: dict[str, int] = {}
    for l in lignes:
        par_source[l["source"]] = par_source.get(l["source"], 0) + 1

    print(f"Source     : {db_path}")
    print(f"Périmètre  : --statut {a.statut}" + (" --delta" if a.delta else "")
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

    # Par lots (SupabaseStore.upsert_listings_bulk), pas ligne à ligne : mesuré
    # le 2026-08-26 à 4,1 annonces/s en ligne à ligne (2 allers-retours
    # Bangkok↔Singapour/annonce, réseau-bound) → ~4h20 pour 53 258, cause
    # directe de la troncature du cycle par `ExecutionTimeLimit` 3 jours de
    # suite (2026-08-26 à 28). Un lot = 1 SELECT + 1 upsert pour `--lot`
    # annonces (défaut 500) → le nombre d'allers-retours tombe d'un facteur
    # ~1000.
    nouvelles = maj = changees = erreurs = 0
    # DISJONCTEUR. Chaque lot a son propre budget d'attente réseau (1 200 s dans
    # SupabaseStore) : sur une panne longue du pooler, ce budget se rejoue lot
    # après lot. Mesuré le 2026-09-19 : 204 lots, 51 500 erreurs, **69 h** de
    # run — le process orchestrateur est resté pris, la tâche planifiée
    # (MultipleInstances=IgnoreNew) a refusé les cycles des 19, 20 et 21/09 :
    # 3 nuits sans aucun extracteur. Abandonner ne perd rien : sans --delta, le
    # passage suivant réévalue toute la fenêtre active ; avec --delta, un lot
    # non envoyé n'est pas marqué synchronisé et repart la nuit suivante.
    echecs_consecutifs = 0
    abandon = False
    for i in range(0, len(lignes), a.lot):
        lot = lignes[i:i + a.lot]
        try:
            imgs_lot = {l["id"]: imgs[l["id"]] for l in lot if l["id"] in imgs} if storage else None
            resultat = store.upsert_listings_bulk(lot, imgs_lot, batch_size=a.lot)
            nouvelles += resultat["nouvelles"]
            maj += resultat["maj"]
            changees += resultat["changees"]
            if storage:
                for l in lot:
                    for im in imgs.get(l["id"], []):
                        chemin = os.path.join(a.dossier, im["storage_path"])
                        if os.path.exists(chemin):
                            storage.upload(chemin, im["storage_path"])
            echecs_consecutifs = 0
            if a.delta:
                # Envoi reussi (meme si le garde-fou anti-reecriture de
                # Postgres a fait un no-op pour certaines lignes identiques) :
                # local et distant sont alignes, plus besoin de repousser demain.
                marquer_synchronise(db_path, [l["id"] for l in lot])
        except Exception as e:  # noqa: BLE001
            erreurs += len(lot)
            echecs_consecutifs += 1
            if erreurs <= 5 * a.lot:
                print(f"  [erreur lot {i}-{i + len(lot)}] {type(e).__name__} {e}")
            if echecs_consecutifs >= a.max_lots_en_echec:
                print(f"\n✗ ABANDON : {echecs_consecutifs} lots d'affilée en échec — "
                      f"Supabase est indisponible, on rend la main au cycle. "
                      f"{len(lignes) - i - len(lot)} annonces non tentées, "
                      f"repoussées au prochain passage.")
                abandon = True
                break
        fait = min(i + a.lot, len(lignes))
        print(f"  … {fait}/{len(lignes)} ({nouvelles} nouvelles, {maj} mises à jour, {changees} prix changés)")

    print(f"\nOK - Terminé — {nouvelles} nouvelles, {maj} mises à jour, {erreurs} erreur(s)")

    if abandon:
        # Ni recopie des statuts ni scan_run : le serveur est injoignable, et un
        # scan_run écrit maintenant (s'il passait) ferait croire à
        # verifie-synchro.py que le serveur a été rafraîchi.
        return 1

    corriges = 0
    if a.synchro_statuts:
        print(f"\nRecopie des statuts ({len(morts)} candidates)…")
        apres_lot = (lambda ids: marquer_synchronise(db_path, ids)) if a.delta else None
        corriges = synchroniser_statuts(store, morts, a.dry_run, apres_lot=apres_lot)
        print(f"OK - {corriges} annonces fantômes corrigées "
              f"(les autres étaient déjà à jour côté serveur)")
    else:
        print("  Aucun délistage propagé : les annonces mortes depuis le dernier")
        print("  envoi restent 'active' en ligne. Utiliser --synchro-statuts.")

    # scan_runs ne recevait plus AUCUNE écriture depuis la bascule SQLite du
    # 2026-08-25 (les vrais scraps n'écrivent plus sur Supabase) : la table
    # restait figée au 22/08 même quand la remontée rafraîchissait `listings`
    # le jour même — un outil qui lit scan_runs pour juger la fraîcheur du
    # serveur (ops/verifie-synchro.py) se trompait. Ce n'est PAS un scan : le
    # `source` distinct ('remonter-supabase') empêche de le confondre avec un
    # vrai passage d'extracteur dans les stats par source.
    store.record_scan_run("remonter-supabase", scanned=len(lignes), new=nouvelles,
                          removed=corriges, changed=changees,
                          notes="remontée PC2→Supabase, pas un scrape")

    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
