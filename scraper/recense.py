"""recense.py — parcourir TOUT le catalogue d'une source, sans rien d'autre.

POURQUOI CE MODULE EXISTE
Mesuré le 2026-08-23 : notre fenêtre de scan couvre 2,7 % du catalogue
DDproperty (150 pages sur 2 748 en vente et 2 899 en location, soit ~113 000
annonces). Le garde-fou anti-accident de run.py annule donc le délistage à
chaque cycle — le scan voit 16 % des actives en base, très loin des 50 % exigés
— et le stock ne fait que croître : 6 671 actives le 2026-07-31, 32 142 le
2026-08-22.

Ce que ce module change : il énumère les IDENTIFIANTS de tout le catalogue sans
visiter une seule page détail, sans télécharger une image, sans écrire une
annonce. Une page de liste coûte le même prix quoi qu'on en fasse (1,2 Mo de
HTML, 5,24 s mesurées) ; ce qui coûtait les 5 h de cycle, c'étaient les 2 956
pages détail à ~5,9 s pièce.

CE QU'IL NE FAIT PAS, ET C'EST VOULU
  - aucun délistage (arbitrage du 2026-08-23 : « on ne purge pas la DB ») ; les
    actives absentes du catalogue sont COMPTÉES et rapportées, rien de plus ;
  - aucune insertion : les annonces inconnues partent dans une file
    (output/recensement/<source>-inconnues.jsonl) pour décision ultérieure —
    mesuré le 2026-08-23, les enregistrer toutes pèserait ~540 Mo sur une base
    déjà à 810 Mo en formule gratuite ;
  - aucune résurrection : seules les annonces DÉJÀ actives sont rafraîchies. Une
    annonce marquée vendue qui traîne encore dans le catalogue le reste.

Usage :
    scraper/.venv/Scripts/python.exe scraper/recense.py --source ddproperty --onglets 5
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

#: Tentatives par page avant de la déclarer ratée. Trois : une page de liste
#: pèse 1,2 Mo, un aléa réseau sur un transfert de cette taille n'est pas rare,
#: et l'abandon coûtait jusqu'ici un cinquième du catalogue (mesure du
#: 2026-08-25). Au-delà de trois, ce n'est plus un aléa.
ESSAIS_PAR_PAGE = 3

from adapters.ddproperty import _next_data                    # noqa: E402
from pipeline.fetch import Fetcher                            # noqa: E402
from run import ADAPTERS, CONFIG_DIR, OUTPUT_DIR, load_env    # noqa: E402


def _maintenant() -> str:
    return datetime.now(timezone.utc).isoformat()


class Recensement:
    """Un flux (source + deal_type) parcouru par N onglets en parallèle.

    Chaque onglet a SON PROPRE Fetcher : la session est distincte (le cookie
    Cloudflare __cf_bm est par session) et la cadence aussi. Le débit vers le
    site est donc multiplié par le nombre d'onglets — arbitrage de posture pris
    explicitement le 2026-08-23 : 5 onglets, soit ~1,7 requête/s au lieu de 0,33.
    """

    def __init__(self, source: str, config: dict, onglets: int, max_pages: int):
        self.source, self.config = source, config
        self.onglets, self.max_pages = onglets, max_pages
        self.adaptateur = ADAPTERS[source](config)
        self._verrou = threading.Lock()
        self.stubs: dict[str, dict] = {}      # source_id -> stub, dédupliqué entre onglets
        self.pages_lues = 0
        self.pages_vides = 0
        self.fin: int | None = None           # 1re page identique à la signature terminale
        self.terminale: tuple[str, ...] | None = None
        self.pages_utiles: set[int] = set()   # pages réellement dépouillées
        self.pages_ratees: set[int] = set()   # pages jamais obtenues, malgré les essais

    def signature_terminale(self, chemin: str) -> tuple[str, ...] | None:
        """Empreinte de la page servie AU-DELÀ de la fin du catalogue.

        Mesuré le 2026-08-23 : passé sa dernière page, DDproperty ne rend ni page
        vide ni 404, il ressert indéfiniment la même page (identique aux pages
        4100, 4200, 4500, 5000, 6000). Nestopa fait pareil en resservant sa page 1.
        On demande donc UNE page très au-delà, et toute page qui lui ressemble
        marque la fin — c'est une mesure, pas une inférence.

        POURQUOI PAS « une page sans sku nouveau » (première version, 2026-08-23)
        Parce qu'avec plusieurs onglets en tourniquet, les couvertures se
        chevauchent : un onglet pouvait tomber sur une page dont tous les sku
        avaient déjà été vus par un autre, et déclarer la fin du flux pour tout
        le monde. Résultat mesuré le 2026-08-25 sur la vente : 790 pages lues
        alors que le parcours était monté jusqu'à la 1495 — des trous au milieu,
        et 12 348 annonces déclarées « absentes du catalogue » qui n'avaient
        simplement jamais été regardées. Un chiffre faux est pire qu'absent.
        """
        f = self._fetcher()
        sep = "&" if "?" in chemin else "?"
        param = self.config.get("page_param", "page")
        url = f"{self.config['base_url']}{chemin}{sep}{param}={self.max_pages + 1000}"
        html = f.get_text(url, referer=self.config["base_url"])
        if not html:
            return None
        data = _next_data(html)
        stubs = self.adaptateur._parse_list(data, "sale") if data else []
        return tuple(sorted(str(s["source_id"]) for s in stubs)) or None

    def _fetcher(self) -> Fetcher:
        f = Fetcher(base_url=self.config["base_url"],
                    user_agent=self.config["user_agent"],
                    rate_limit_seconds=self.config.get("rate_limit_seconds", 3.0),
                    timeout_seconds=self.config.get("timeout_seconds", 30),
                    respect_robots=self.config.get("respect_robots", True))
        f.max_pages = self.max_pages
        # Réchauffe : la 1re requête d'une session prend le cookie Cloudflare.
        # Sans elle, les onglets supplémentaires se font servir un challenge.
        f.get_text(self.config["base_url"], referer=self.config["base_url"])
        return f

    def _une_page(self, fetcher: Fetcher, chemin: str, deal: str, page: int) -> bool:
        """Lit une page.

        Rend False UNIQUEMENT quand la fin du catalogue est atteinte. Un raté de
        lecture n'est plus une fin : on réessaie, puis on passe à la suivante.

        POURQUOI — mesuré le 2026-08-25, deuxième recensement complet : 885 pages
        manquantes sur la vente, 1 030 sur la location, au MILIEU du parcours.
        Cause : un onglet qui recevait une page vide (aléa réseau, temporisation)
        s'arrêtait définitivement, laissant une page sur cinq non lue jusqu'au
        bout du flux. Un incident d'une seconde coûtait un cinquième du
        catalogue — et le décompte « absentes » qui en découlait était faux de
        plusieurs milliers.
        """
        sep = "&" if "?" in chemin else "?"
        param = self.config.get("page_param", "page")
        url = f"{self.config['base_url']}{chemin}{sep}{param}={page}"

        html, stubs = None, []
        for tentative in range(1, ESSAIS_PAR_PAGE + 1):
            html = fetcher.get_text(url, referer=self.config["base_url"])
            if html:
                data = _next_data(html)
                stubs = self.adaptateur._parse_list(data, deal) if data else []
                if stubs:
                    break
            if tentative < ESSAIS_PAR_PAGE:
                time.sleep(2 * tentative)      # laisse passer un aléa court

        with self._verrou:
            if not stubs:
                # Ni fin de catalogue, ni page utile : un trou, qu'on NOMME.
                # Le bilan refusera de conclure tant qu'il en reste.
                self.pages_ratees.add(page)
                return True                    # ...et l'onglet continue
            self.pages_lues += 1
            # FIN DE PAGINATION PAR REJEU — mesuré le 2026-08-23 : au-delà de sa
            # dernière page, DDproperty ne rend ni page vide ni 404, il ressert
            # la même page indéfiniment (identique aux pages 4100, 4200, 4500,
            # 5000, 6000). Nestopa fait pareil en resservant sa page 1. Une
            # boucle qui n'attend qu'une page vide ne s'arrêterait jamais.
            empreinte = tuple(sorted(str(s["source_id"]) for s in stubs))
            if self.terminale and empreinte == self.terminale:
                self.fin = min(self.fin or page, page)
                return False
            for s in stubs:
                self.stubs.setdefault(s["source_id"], s)
            self.pages_utiles.add(page)
        return True

    def parcourir(self, chemin: str, deal: str) -> None:
        """Les onglets se partagent les pages en tourniquet (1,6,11… / 2,7,12…).

        Tourniquet et non blocs contigus : si le flux s'arrête plus tôt que le
        plafond, tous les onglets le constatent en même temps, au lieu qu'un
        seul travaille pendant que les autres tapent dans le vide.
        """
        self.terminale = self.signature_terminale(chemin)

        def onglet(rang: int) -> None:
            f = self._fetcher()
            for page in range(1 + rang, self.max_pages + 1, self.onglets):
                if self.fin is not None and page > self.fin:
                    return
                if not self._une_page(f, chemin, deal, page):
                    return

        with ThreadPoolExecutor(max_workers=self.onglets) as pool:
            list(pool.map(onglet, range(self.onglets)))


def _confronter(store, source: str, deal: str, vus: set[str], actives: set[str]) -> dict:
    """Compare le catalogue vu à ce que la base tient pour actif.

    AUCUNE écriture destructrice : on rafraîchit ce qui est confirmé présent, on
    compte le reste. Le délistage reste l'affaire de run.py --full."""
    confirmees = actives & vus
    touchees = store.toucher_lot(confirmees, _maintenant()) if confirmees else 0
    return {"actives_en_base": len(actives), "confirmees": len(confirmees),
            "rafraichies": touchees,
            "absentes_du_catalogue": len(actives - vus),
            "inconnues_de_la_base": len(vus - actives)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Recensement d'un catalogue, sans page détail.")
    ap.add_argument("--source", default="ddproperty", choices=list(ADAPTERS))
    ap.add_argument("--onglets", type=int, default=5,
                    help="requêtes simultanées, sessions distinctes (défaut 5)")
    ap.add_argument("--max-pages", type=int, default=None,
                    help="plafond de sécurité ; défaut : max_pages_recensement de la config")
    ap.add_argument("--deal-type", default=None, choices=["sale", "rent"])
    ap.add_argument("--store", default="sqlite", choices=["sqlite", "supabase"],
                    help="defaut local depuis la bascule du 2026-08-23")
    ap.add_argument("--sans-base", action="store_true",
                    help="parcours seul, sans lecture ni écriture en base (mesure)")
    args = ap.parse_args()

    config = json.loads((CONFIG_DIR / f"{args.source}.json").read_text(encoding="utf-8"))
    max_pages = (args.max_pages or config.get("max_pages_recensement")
                 or config.get("max_pages", 1))

    store = None
    if not args.sans_base:
        load_env()                       # SUPABASE_DB_URL vit dans scraper/.env
        if args.store == "supabase":
            from store.supabase_store import SupabaseStore
            dsn = os.environ.get("SUPABASE_DB_URL")
            if not dsn:
                sys.exit("SUPABASE_DB_URL manquant (scraper/.env)")
            store = SupabaseStore(dsn)
        else:
            from store.sqlite_store import SqliteStore
            store = SqliteStore(OUTPUT_DIR / "bangkok.db")

    file_inconnues = OUTPUT_DIR / "recensement" / f"{args.source}-inconnues.jsonl"
    file_inconnues.parent.mkdir(parents=True, exist_ok=True)

    bilan: dict = {"source": args.source, "onglets": args.onglets, "flux": []}
    t0 = time.perf_counter()
    with open(file_inconnues, "w", encoding="utf-8") as sortie:
        for search in config["searches"]:
            deal = search["deal_type"]
            if args.deal_type and deal != args.deal_type:
                continue
            print(f"== recensement {args.source}/{deal} "
                  f"({args.onglets} onglets, plafond {max_pages} pages)", flush=True)
            t1 = time.perf_counter()
            rec = Recensement(args.source, config, args.onglets, max_pages)
            rec.parcourir(search["path"], deal)

            vus = {f"{args.source}:{deal}:{sid}" for sid in rec.stubs}
            ligne = {"deal_type": deal, "pages_lues": rec.pages_lues,
                     "derniere_page": rec.fin, "annonces_vues": len(vus),
                     "secondes": round(time.perf_counter() - t1, 1)}
            # COUVERTURE, comptée sans complaisance : entre la page 1 et la
            # dernière page réelle, toute page qui n'a pas été dépouillée est un
            # trou — qu'elle ait été ratée trois fois ou jamais tentée.
            derniere = (rec.fin - 1) if rec.fin else (
                max(rec.pages_utiles) if rec.pages_utiles else 0)
            attendues = set(range(1, derniere + 1))
            trous = len(attendues - rec.pages_utiles)
            ligne["pages_utiles"] = len(rec.pages_utiles)
            ligne["page_la_plus_loin"] = derniere
            ligne["pages_ratees"] = len(rec.pages_ratees)
            ligne["pages_manquantes"] = trous

            if rec.fin is None and rec.pages_lues:
                # PLAFOND ATTEINT AVANT LA FIN DU CATALOGUE. On a lu ce qu'on
                # pouvait, mais on n'a jamais vu la page terminale : tout ce qui
                # vit au-delà est hors de vue. Comparer notre stock à cette
                # fraction dirait « absente » de milliers d'annonces bien
                # présentes, simplement plus loin dans la liste.
                ligne["conclusion"] = (f"partielle — plafond de {max_pages} pages atteint "
                                       f"avant la fin du catalogue")
                ligne["annonces_vues"] = len(vus)
                print(f"   {json.dumps(ligne, ensure_ascii=False)}", flush=True)
                bilan["flux"].append(ligne)
                continue

            if trous > 0:
                # PARCOURS TROUÉ : on a lu jusqu'à la page N sans avoir lu toutes
                # les pages avant elle. Les identifiants des pages sautées sont
                # inconnus, donc « absent du catalogue » ne veut plus rien dire —
                # on ne peut pas distinguer « retirée » de « pas regardée ».
                # Défaut mesuré le 2026-08-25 : 790 pages lues sur 1 495
                # atteintes, et 12 348 annonces déclarées absentes à tort.
                ligne["conclusion"] = (f"partielle — {trous} pages manquantes sur "
                                       f"{atteinte} : comparaison au stock impossible")
                ligne["annonces_vues"] = len(vus)
                print(f"   {json.dumps(ligne, ensure_ascii=False)}", flush=True)
                bilan["flux"].append(ligne)
                continue

            if rec.pages_lues == 0:
                # AUCUNE PAGE LUE : on ne conclut RIEN. Le 2026-08-25, une
                # coupure DNS a fait lire zéro page et le bilan a annoncé
                # « 32 262 annonces absentes du catalogue » — c'est-à-dire la
                # totalité du stock, présenté comme un constat. Aucune décision
                # n'en découlait (le recensement ne délist pas), mais un chiffre
                # faux dans un rapport finit toujours par être lu comme vrai.
                ligne["conclusion"] = "impossible — aucune page lue (site injoignable ?)"
                print(f"   {json.dumps(ligne, ensure_ascii=False)}", flush=True)
                bilan["flux"].append(ligne)
                continue
            if store:
                actives = store.ids_actifs(args.source, deal)
                ligne.update(_confronter(store, args.source, deal, vus, actives))
                for sid, stub in rec.stubs.items():
                    if f"{args.source}:{deal}:{sid}" not in actives:
                        sortie.write(json.dumps(stub, ensure_ascii=False, default=str) + "\n")
            bilan["flux"].append(ligne)
            print(f"   {json.dumps(ligne, ensure_ascii=False)}", flush=True)

    if store:
        store.close()
    bilan["secondes_total"] = round(time.perf_counter() - t0, 1)
    bilan["file_inconnues"] = str(file_inconnues)
    bilan["pages_lues"] = sum(f["pages_lues"] for f in bilan["flux"])
    bilan["flux_non_conclusifs"] = [f["deal_type"] for f in bilan["flux"] if f.get("conclusion")]
    bilan["annonces_vues"] = sum(f["annonces_vues"] for f in bilan["flux"])
    bilan["absentes_du_catalogue"] = sum(f.get("absentes_du_catalogue", 0) for f in bilan["flux"])
    bilan["inconnues_de_la_base"] = sum(f.get("inconnues_de_la_base", 0) for f in bilan["flux"])
    # Bilan JSON terminal : lu par agents/core/shell.py (_bilan_json) et vérifié
    # par l'overseer contre le contrat de sortie du SKILL.
    print(json.dumps(bilan, ensure_ascii=False, indent=1))
    # Sortie non nulle si un flux n'a rien pu lire : un recensement muet doit se
    # voir dans le code retour, pas seulement dans le corps du rapport.
    return 1 if bilan["flux_non_conclusifs"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
