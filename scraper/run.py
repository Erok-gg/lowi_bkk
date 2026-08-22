"""run.py — Orchestrateur du scraper (LOCAL).

Enchaîne : adaptateur (liste→détail) → normalisation → matching khet →
images webp 1024×768 → store SQLite (diff + price_history) → fiches HTML →
scan_run + stats.

Exemples :
  python run.py --source fazwaz --limit 5
  python run.py --source fazwaz --full          # marque les disparues inactives
  python run.py --source fazwaz --fetch-detail  # galerie + SDB via page détail

Demain (online) : ajouter --store supabase (SupabaseStore, même interface).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# imports relatifs au dossier scraper/
sys.path.insert(0, str(Path(__file__).resolve().parent))

from adapters.fazwaz import FazwazAdapter  # noqa: E402
from adapters.ddproperty import DdpropertyAdapter  # noqa: E402
from adapters.propertyscout import PropertyscoutAdapter  # noqa: E402
from adapters.nestopa import NestopaAdapter  # noqa: E402
from adapters.livinginsider import LivinginsiderAdapter  # noqa: E402
from pipeline.fetch import Fetcher  # noqa: E402
from pipeline.normalize import normalize  # noqa: E402
from pipeline.geo_match import KhetMatcher  # noqa: E402
from pipeline import chrono  # noqa: E402
from pipeline.images import process_images  # noqa: E402
from pipeline import photo_sig  # noqa: E402
from pipeline.fiche import write_fiche  # noqa: E402
from pipeline.keepawake import prevent_sleep  # noqa: E402
from store.sqlite_store import SqliteStore  # noqa: E402

ADAPTERS = {
    "fazwaz": FazwazAdapter,
    "ddproperty": DdpropertyAdapter,
    "propertyscout": PropertyscoutAdapter,
    "nestopa": NestopaAdapter,
    "livinginsider": LivinginsiderAdapter,
}
ROOT = Path(__file__).resolve().parent
CONFIG_DIR = ROOT / "config"
# Surcharge par LOWI_OUTPUT_DIR : permet d'isoler entièrement un scrap de test
# (base SQLite, images, fiches) dans un dossier dédié, sans toucher à la
# production. Sans la variable, comportement inchangé.
OUTPUT_DIR = Path(os.environ.get("LOWI_OUTPUT_DIR") or (ROOT / "output"))

# Garde-fou --full : on n'autorise le délistage que si le scan a vu au moins
# cette fraction des annonces actives déjà en base (sinon : site en panne/scan
# partiel → on annule pour ne pas vider la base).
FULL_DELIST_MIN_RATIO = 0.5



def load_env() -> None:
    """Charge scraper/.env (simple) dans os.environ (sans dépendance)."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def load_config(source: str, override: str | None = None) -> dict:
    """Config du site. `override` = chemin d'un JSON alternatif (scrap ciblé :
    mêmes clés, souvent des `searches` restreintes à des districts)."""
    path = Path(override) if override else CONFIG_DIR / f"{source}.json"
    if not path.is_absolute() and not path.exists():
        path = ROOT / path  # chemin relatif au dossier scraper/
    if not path.exists():
        sys.exit(f"Config introuvable : {path}")
    cfg = json.loads(path.read_text(encoding="utf-8"))
    if override and cfg.get("source") != source:
        sys.exit(f"--config {path} : source '{cfg.get('source')}' ≠ --source {source}")
    return cfg


def load_excludes() -> list[str]:
    """Fragments de nom à exclure (toutes sources). Voir config/exclude.json."""
    path = CONFIG_DIR / "exclude.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [s.lower() for s in data.get("condo_name_contains", [])]


def is_excluded(excludes: list[str], *fields: str | None) -> bool:
    blob = " ".join(f.lower() for f in fields if f)
    return any(frag in blob for frag in excludes)


def make_store(kind: str):
    if kind == "supabase":
        load_env()
        dsn = os.environ.get("SUPABASE_DB_URL")
        if not dsn:
            sys.exit("SUPABASE_DB_URL manquant (scraper/.env)")
        from store.supabase_store import SupabaseStore
        print("→ store : Supabase (Postgres)")
        return SupabaseStore(dsn)
    print("→ store : SQLite local")
    return SqliteStore(OUTPUT_DIR / "bangkok.db")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="fazwaz", choices=list(ADAPTERS))
    ap.add_argument("--limit", type=int, default=None, help="nb max d'annonces (test)")
    ap.add_argument("--full", action="store_true",
                    help="scan complet : marque les annonces disparues comme inactives")
    ap.add_argument("--fetch-detail", action="store_true",
                    help="récupère galerie + SDB via la page de détail")
    ap.add_argument("--no-images", action="store_true", help="saute le traitement des images")
    ap.add_argument("--store", default="sqlite", choices=["sqlite", "supabase"],
                    help="destination : SQLite local (défaut) ou Supabase")
    ap.add_argument("--deal-type", default=None, choices=["sale", "rent"],
                    help="ne scraper qu'une catégorie (vente ou location)")
    ap.add_argument("--geocode", action="store_true",
                    help="complète street/coords manquants via Nominatim (1 req/s, caché)")
    ap.add_argument("--config", default=None,
                    help="config JSON alternative (scrap ciblé, ex. config/targets/…)")
    args = ap.parse_args()

    prevent_sleep()  # pas de veille système pendant le scrap (écran libre)

    cfg = load_config(args.source, args.config)
    if args.fetch_detail:
        cfg["fetch_detail"] = True
    # filtre les recherches selon le deal_type (jour vente / jour location)
    if args.deal_type:
        cfg["searches"] = [s for s in cfg.get("searches", [])
                           if s.get("deal_type") == args.deal_type]
        if not cfg["searches"]:
            sys.exit(f"Aucune recherche '{args.deal_type}' dans la config {args.source}")

    adapter = ADAPTERS[args.source](cfg)
    fetcher = Fetcher(
        base_url=cfg["base_url"], user_agent=cfg["user_agent"],
        rate_limit_seconds=cfg.get("rate_limit_seconds", 2.5),
        timeout_seconds=cfg.get("timeout_seconds", 30),
        respect_robots=cfg.get("respect_robots", True),
        image_rate_limit_seconds=cfg.get("image_rate_limit_seconds", 0.4),
    )
    matcher = KhetMatcher()
    geocoder = None
    if args.geocode:
        from pipeline.geocode import Geocoder
        geocoder = Geocoder()
        print("→ géocodage Nominatim activé (street/coords manquants)")
    load_env()  # SUPABASE_* pour le store et le Storage
    store = make_store(args.store)

    from pipeline.storage import SupabaseStorage
    storage = SupabaseStorage.from_env() if args.store == "supabase" else None
    if storage:
        print(f"→ images : upload Storage (bucket '{storage.bucket}')")

    # Sonde de structure AVANT le scan complet : un marqueur absent (JSON-LD,
    # __NEXT_DATA__…) est aujourd'hui indiscernable d'une recherche vide dans
    # le reste du pipeline — watch-health finit par le voir, mais seulement
    # après 2 runs consécutifs à zéro (jusqu'à 8 j de scans pour rien). Ici,
    # une seule requête tranche avant de lancer 150 pages pour rien.
    sonde_ok, sonde_diag = adapter.sonder(fetcher)
    print(f"→ sonde structure : {'OK' if sonde_ok else 'ÉCHEC'} — {sonde_diag}")
    if not sonde_ok:
        # Marqueur repris tel quel par orchestrator.py (run_agent) pour
        # escalader vers Claude sans attendre watch-health, qui lui reste
        # à sa place normale, en fin de cycle.
        print(f"[SONDE-ECHEC] {args.source} : {sonde_diag}")
        store.close()
        sys.exit(2)

    print(f"▶ Scan {args.source} (max_pages={cfg.get('max_pages')}, limit={args.limit})")

    excludes = load_excludes()
    if excludes:
        print(f"→ exclusions actives : {', '.join(excludes)}")

    n_new = n_changed = n_unchanged = n_skipped = n_total = n_excluded = n_errors = 0
    seen_ids: set[str] = set()
    price_alerts: list[str] = []
    completed = False  # True si le scan est allé au bout (cond. au délistage --full)

    for stub in adapter.list_urls(fetcher, limit=args.limit):
        # Exclusion à la source (avant dédup/délistage) : on ne l'ajoute pas à
        # seen_ids → avec --full une annonce exclue déjà en base sera délistée.
        if is_excluded(excludes, stub.get("condo_name"), stub.get("title")):
            n_excluded += 1
            continue
        lid = f"{args.source}:{stub.get('deal_type') or 'sale'}:{stub.get('source_id')}"
        seen_ids.add(lid)
        n_total += 1

        # Une erreur isolée (réseau, parse, image, DB momentanée) ne doit PAS
        # tuer tout le run : on logue, on saute l'annonce, on continue.
        try:
            # ── Dédup incrémentale : on évite de re-visiter la fiche d'une annonce
            # déjà connue dont le prix (lu dans la liste) n'a pas bougé. Raccourcit
            # fortement les scraps futurs.
            existing = store.get_listing(lid)
            stub_price = stub.get("price")
            if (existing is not None and stub_price is not None
                    and existing["price"] is not None
                    and float(existing["price"]) == float(stub_price)
                    and store.has_images(lid)):
                store.touch_listing(lid)
                n_unchanged += 1
                n_skipped += 1
                print(f"  [skip-dedup] {lid} — {stub.get('condo_name')} (prix inchangé)")
                continue

            # Nouvelle annonce ou prix changé → on visite la fiche (détail + galerie)
            rec = adapter.parse_listing(fetcher, stub)
            if not rec:
                continue
            norm = normalize(rec)
            # filet de sécurité : nom de condo connu seulement via la fiche détail
            if is_excluded(excludes, norm.get("condo_name"), norm.get("title")):
                n_excluded += 1
                seen_ids.discard(lid)
                continue
            # matching khet par lat/lng ; à défaut, on CANONISE le district
            # texte de la source au lieu de le prendre tel quel — sinon
            # « Bang Na » et « Bang Na District » cohabitent en base et le
            # quartier apparaît deux fois dans les classements (cf.
            # KhetMatcher.canoniser).
            khet = matcher.match(norm.get("lat"), norm.get("lng")) \
                or matcher.canoniser(norm.get("khet"))
            if khet:
                norm["khet"] = khet

            # géocodage optionnel : complète street/coords manquants (ex. Nestopa)
            if geocoder and norm.get("condo_name") and (
                not norm.get("street") or norm.get("lat") is None
            ):
                with chrono.mesure("geocodage"):
                    res = geocoder.lookup(norm["condo_name"], norm.get("khet"))
                if res:
                    if res.get("street") and not norm.get("street"):
                        norm["street"] = res["street"]
                    if res.get("lat") and norm.get("lat") is None:
                        norm["lat"], norm["lng"] = res["lat"], res["lng"]
                        m2 = matcher.match(norm["lat"], norm["lng"])
                        if m2 and not norm.get("khet"):
                            norm["khet"] = m2

            # Empreinte photo : poids des fichiers relevés par HEAD, sans les
            # télécharger (une seule image, la couverture, est stockée). Deux
            # annonces qui réutilisent les mêmes fichiers sont le même lot —
            # c'est ce qui démasque une republication sous un nouvel identifiant.
            # Relevée uniquement pour les NOUVELLES annonces : les autres ont
            # déjà la leur, et c'est là que la question du repost se pose.
            if existing is None and norm.get("image_urls"):
                try:
                    with chrono.mesure("empreinte_photo"):
                        norm["photo_count"], norm["photo_sizes"] = photo_sig.relever(
                            fetcher, norm["image_urls"])
                except Exception as e:  # une empreinte manquante n'est pas bloquante
                    print(f"  (empreinte photo ignorée : {e})")

            # DEUX interrupteurs distincts, et la distinction compte :
            #   image.telecharger : recuperer et convertir en webp SUR LE DISQUE
            #   image.televerser  : pousser le fichier vers Supabase Storage
            # Mesure du 2026-08-22 : le bucket pesait 1 610 Mo (157 % du quota
            # free tier de 1 Go) alors que les metadonnees ne font que 11 Mo en
            # base. C'est le TELEVERSEMENT qui coute, pas la collecte. Le poste
            # coureur continue donc de constituer sa reserve locale d'images ;
            # seule la mise en ligne est suspendue. La structure est intacte :
            # remettre televerser a true puis lancer scraper/upload_images.py
            # remet tout en ligne depuis le disque, sans re-scraper.
            images_actives = cfg.get("image", {}).get("telecharger", True)
            need_images = (not args.no_images) and images_actives and bool(
                norm.get("image_urls")) and (
                existing is None or not store.has_images(norm["id"])
            )
            images = None
            if need_images:
                with chrono.mesure("traitement_images"):
                    images = process_images(fetcher, norm["id"], norm["image_urls"],
                                            OUTPUT_DIR, cfg["image"])

            # upload des images vers Storage (object path = storage_path)
            # Suspendu par `image.televerser: false` — cf. le commentaire ci-dessus.
            if storage and images and cfg.get("image", {}).get("televerser", True):
                for im in images:
                    with chrono.mesure("transfert_storage"):
                        storage.upload(str(OUTPUT_DIR / im["storage_path"]), im["storage_path"])

            with chrono.mesure("ecriture_base"):
                status, old_price = store.upsert_listing(norm, images)
            if status == "new":
                n_new += 1
            elif status == "changed":
                n_changed += 1
                price_alerts.append(
                    f"  ⚠ prix changé {norm['id']}: {old_price} → {norm['price']} {norm['currency']}"
                )
            else:
                n_unchanged += 1

            # fiche HTML (relit les images stockées si on n'en a pas reprocessé)
            imgs_for_fiche = images or [
                {"storage_path": f"images/{norm['id'].replace(':', '_')}/0.webp"}
            ] if norm.get("image_urls") else []
            write_fiche(norm, imgs_for_fiche, OUTPUT_DIR)

            print(f"  [{status:9}] {norm['id']} — {norm.get('condo_name')} "
                  f"({norm.get('price')} {norm['currency']}, {norm.get('khet')})")
        except Exception as e:
            n_errors += 1
            seen_ids.discard(lid)  # pas vu correctement → ne pas le compter pour le délistage
            print(f"  [erreur] {lid} : {e}")
            continue

    completed = True  # boucle allée au bout

    removed = 0
    if completed and args.full:
        # Garde-fou anti-accident : si le scan a trouvé anormalement peu d'annonces
        # (site en panne, pagination cassée, blocage…), on ANNULE le délistage pour
        # ne pas vider la base. Seuil : < 50 % des actives en base pour ce scope.
        active_n = store.count_active(args.source, args.deal_type)
        if active_n > 0 and len(seen_ids) < FULL_DELIST_MIN_RATIO * active_n:
            print(f"  ⚠ GARDE-FOU : scan {len(seen_ids)} annonces < "
                  f"{int(FULL_DELIST_MIN_RATIO * 100)} % des {active_n} actives en base "
                  f"→ délistage ANNULÉ (site en panne / scan partiel ?). Relance un scan complet.")
        else:
            # VENDUES depuis 7 jours → sortie du stock actif, AVANT le délistage.
            # L'ordre compte : une annonce vendue qui disparaît ensuite doit être
            # comptée comme vendue, pas comme retirée. C'est toute la différence
            # que ce marqueur apporte — le délistage confond vente, retrait et
            # artefact de fenêtre, `market_status` les sépare.
            vendues = store.appliquer_ventes()
            if vendues:
                print(f"  {vendues} annonce(s) marquée(s) vendues depuis ≥7 j → sorties du stock")

            # scope l'inactivation au deal_type scrapé (sinon on délisterait l'autre catégorie)
            delisted = store.mark_missing_inactive(args.source, seen_ids, deal_type=args.deal_type)
            removed = len(delisted)
            # Délistés → on supprime leurs photos (Storage + lignes images), on garde
            # l'annonce en DB (inactive + delisted_at) pour l'historique/comparaison.
            for lid in delisted:
                if storage:
                    for path in store.get_image_paths(lid):
                        storage.delete(path)
                store.delete_images(lid)
            if delisted:
                print(f"  ↓ {removed} délistées → photos supprimées, conservées en DB (inactive)")

    # OÙ EST PASSÉ LE TEMPS. Imprimé dans le journal du run, donc relu par
    # `metrics_from_output` et conservé au ledger : la répartition devient une
    # série, pas une observation ponctuelle.
    print(chrono.rapport(), flush=True)

    store.record_scan_run(args.source, n_total, n_new, removed, n_changed,
                          notes="full" if args.full else "partial")
    # Snapshot des stats par quartier (séries temporelles)
    try:
        store.record_khet_snapshots()
    except Exception as e:
        print(f"  (snapshot khet ignoré : {e})")
    # Snapshot du stock par COHORTE : c'est cette série qui mesure la tension.
    # Un repost ne la modifie pas (une annonce meurt, une autre naît dans la
    # même cohorte) — la variation traduit donc une vraie absorption.
    try:
        n = store.record_cohort_snapshots()
        print(f"  cohortes : {n} instantané(s) de stock")
    except Exception as e:
        print(f"  (snapshot cohortes ignoré : {e})")

    print("\n── Résumé ──")
    print(f"  scannées : {n_total} | nouvelles : {n_new} | changées : {n_changed} "
          f"| inchangées : {n_unchanged} (dont {n_skipped} dédup, fiche non re-visitée) "
          f"| retirées : {removed} | exclues : {n_excluded} | erreurs : {n_errors}")
    if price_alerts:
        print("\nAlertes prix :")
        print("\n".join(price_alerts))

    stats = store.khet_stats()
    if stats:
        print("\n── Stats par khet (actives) ──")
        for s in stats[:15]:
            print(f"  {s['khet']:<22} {s['active_count']:>4} annonces | "
                  f"prix/m² moyen : {s['avg_price_per_sqm']}")

    print(f"\n✓ DB : {OUTPUT_DIR / 'bangkok.db'}")
    print(f"✓ Fiches : {OUTPUT_DIR / 'fiches'}  |  Images : {OUTPUT_DIR / 'images'}")
    store.close()


if __name__ == "__main__":
    main()
