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


def _message_trous(trous: int, derniere: int) -> str:
    """Message de conclusion quand le parcours est troué (cf. main()).

    Isolé du corps de main() pour être testable sans réseau — c'est ici que le
    2026-08-26 a plante en production (NameError: 'atteinte' n'existait pas,
    la variable s'appelle `derniere`) : then_2 de extract-ddproperty a échoué
    après 2 724 pages lues, sans qu'aucun test ne l'attrape avant le cycle réel."""
    return f"partielle — {trous} pages manquantes sur {derniere} : comparaison au stock impossible"


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
        # PLUSIEURS ESSAIS : cette requête unique commande tout l'arrêt du
        # parcours. Mesuré la nuit du 2026-08-26 : elle a échoué une fois, la
        # signature est restée vide, plus aucun onglet n'a su reconnaître la fin
        # — les deux flux ont couru jusqu'au plafond de 3 200 pages et le
        # recensement s'est abstenu pour rien. Un aléa d'une seconde coûtait
        # 1 h 37 de parcours inutile.
        for tentative in range(1, ESSAIS_PAR_PAGE + 1):
            html = f.get_text(url, referer=self.config["base_url"])
            if html:
                data = _next_data(html)
                stubs = self.adaptateur._parse_list(data, "sale") if data else []
                if stubs:
                    return tuple(sorted(str(s["source_id"]) for s in stubs))
            if tentative < ESSAIS_PAR_PAGE:
                time.sleep(2 * tentative)
        print("  [recense] signature de fin introuvable — le parcours ira "
              "jusqu'au plafond et s'abstiendra", flush=True)
        return None

    def _fetcher(self) -> Fetcher:
        f = Fetcher(base_url=self.config["base_url"],
                    user_agent=self.config["user_agent"],
                    rate_limit_seconds=self.config.get("rate_limit_seconds", 3.0),
                    timeout_seconds=self.config.get("timeout_seconds", 30),
                    respect_robots=self.config.get("respect_robots", True),
                    backend=self.config.get("fetcher_backend", "requests"))
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


def _rafraichir(store, vus: set[str], actives: set[str]) -> dict:
    """Rafraîchit `last_seen` des annonces CONFIRMÉES PRÉSENTES au catalogue.

    Séparé de `_comparer()` le 2026-09-09, et c'est tout l'objet du correctif.
    Les deux opérations étaient dans une seule fonction, appelée seulement après
    un `continue` qui l'écartait dès que le parcours avait le moindre trou — si
    bien qu'un recensement troué ne rafraîchissait RIEN.

    Or les deux n'ont pas les mêmes conditions de validité. **Voir une annonce
    dans le catalogue prouve qu'elle est vivante, trou ou pas** : un trou empêche
    de conclure sur ce qu'on n'a PAS vu, il ne dit rien de ce qu'on a vu.

    Ce que ça coûtait, mesuré le 2026-09-09 : chaque recensement DDproperty
    manque 1 à 6 pages sur ~2 600 (0,04 à 0,23 %), donc la confrontation était
    écartée à TOUS les runs. Résultat : **5,9 %** seulement des 69 149 actives
    DDproperty avaient un `last_seen` du dernier cycle, la plus ancienne
    remontait au 23/07, et 8,9 % des actives n'avaient pas été confirmées depuis
    plus de 30 jours. Le recensement existait précisément pour empêcher ça.

    AUCUNE écriture destructrice : on ne touche que `last_seen`, et seulement
    vers le haut. Le délistage reste l'affaire de run.py --full."""
    confirmees = actives & vus
    touchees = store.toucher_lot(confirmees, _maintenant()) if confirmees else 0
    return {"actives_en_base": len(actives), "confirmees": len(confirmees),
            "rafraichies": touchees}


#: Part maximale de pages trouées au-delà de laquelle on refuse de compter une
#: absence. Mesuré du 09 au 12/09 : 0 à 5 pages sur ~2 600 (≤ 0,2 %).
DELIST_MAX_TROUS = 0.01
#: Nuits CONSÉCUTIVES d'absence avant délistage. À 0,2 % de pages trouées, la
#: probabilité qu'une annonce vivante tombe dans un trou trois nuits de suite
#: est de l'ordre de 1e-8 — le délai absorbe les trous sans laisser traîner.
DELIST_GRACE = 3
#: Sous ce ratio vues/actives on ne délist rien (site en panne, parcours
#: tronqué) — même seuil que run.py (FULL_DELIST_MIN_RATIO).
DELIST_MIN_RATIO = 0.5


def _delister(store, source: str, deal: str, vus: set[str], actives: set[str],
              trous: int, derniere: int, fin_atteinte: bool) -> dict:
    """Délistage par le recensement, avec délai de grâce — ajouté le 2026-09-13.

    POURQUOI. run.py --full ne délist jamais DDproperty : son scan couvre 16 %
    des actives et le garde-fou des 50 % l'annule chaque nuit (documenté le
    2026-08-23). Mesuré au ledger le 2026-09-13 : `retirees: 0` sur 12/12 runs,
    +1 100 à 2 800 nouvelles par nuit, et 12 700 actives DDproperty (16 %) que le
    recensement n'avait pas revues depuis 3 à 60 jours. Le stock ne peut que
    monter : la base locale est passée de 1,19 à 2,56 Go en 18 j et Supabase de
    139 à 336 Mo (67 % du quota). Le recensement, lui, énumère le catalogue
    ENTIER chaque nuit : c'est le seul scan dont l'absence veut dire quelque
    chose.

    CE QUI EST ÉCRIT. `mark_missing_inactive` : +1 sur `missed_count` des
    actives non vues, `status='inactive'` + `delisted_at` (daté de la PREMIÈRE
    absence) quand `missed_count` ≥ DELIST_GRACE. Rien n'est supprimé, pas même
    les photos (contrairement à run.py --full). Une annonce revue ensuite est
    réactivée par `toucher_lot`/`touch_listing`, qui remettent `missed_count` à
    zéro.

    RETOUR EN ARRIÈRE. Les lignes délistées par ce chemin sont celles dont
    `dirty_since` = l'instant du run :
        update listings set status='active', delisted_at=null
         where source='ddproperty' and status='inactive'
           and dirty_since >= '<début du run>';

    QUAND ON S'ABSTIENT (et on le dit dans le bilan) : page terminale jamais
    vue (plafond atteint), trous > DELIST_MAX_TROUS des pages, ou moins de
    DELIST_MIN_RATIO des actives revues. Un trou de 1 % laisse passer l'absence
    d'une nuit ; le délai de grâce fait le reste."""
    if not fin_atteinte:
        return {"delistees": 0, "delistage": "abstention — page terminale non atteinte"}
    if derniere and trous / derniere > DELIST_MAX_TROUS:
        return {"delistees": 0,
                "delistage": f"abstention — {trous} pages trouées sur {derniere} "
                             f"(> {DELIST_MAX_TROUS:.0%})"}
    if actives and len(vus & actives) < DELIST_MIN_RATIO * len(actives):
        return {"delistees": 0,
                "delistage": f"abstention — {len(vus & actives)} actives revues sur "
                             f"{len(actives)} (< {DELIST_MIN_RATIO:.0%})"}
    delistees = store.mark_missing_inactive(source, vus, deal_type=deal, grace=DELIST_GRACE)
    return {"delistees": len(delistees), "absentes_cette_nuit": len(actives - vus),
            "delistage": f"grâce {DELIST_GRACE} nuits"}


def _comparer(vus: set[str], actives: set[str]) -> dict:
    """Le VERDICT de comparaison — n'a de sens que sur un parcours COMPLET.

    Sur un parcours troué, « absente du catalogue » ne distingue pas « retirée »
    de « pas regardée » (défaut mesuré le 2026-08-25 : 12 348 annonces déclarées
    absentes à tort). Ces deux compteurs restent donc réservés au cas complet —
    cette prudence-là est juste et ne change pas."""
    return {"absentes_du_catalogue": len(actives - vus),
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
    ap.add_argument("--delister", action="store_true",
                    help="marque inactives les actives absentes du catalogue "
                         f"{DELIST_GRACE} nuits de suite (cf. _delister) ; rien supprimé")
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

            # RAFRAÎCHISSEMENT D'ABORD, VERDICT ENSUITE (2026-09-09). Il est
            # placé AVANT les abstentions ci-dessous parce qu'il ne dépend pas
            # d'elles : ce qu'on a vu est vivant, que le parcours soit complet ou
            # non. Le laisser après les `continue` revenait à ne jamais
            # rafraîchir (cf. _rafraichir : 5,9 % des actives DDproperty à jour).
            actives: set[str] = set()
            if store:
                actives = store.ids_actifs(args.source, deal)
                if vus:
                    ligne.update(_rafraichir(store, vus, actives))
                    # DÉLISTAGE APRÈS RAFRAÎCHISSEMENT, AVANT LES ABSTENTIONS DE
                    # VERDICT : il tolère un parcours légèrement troué (délai de
                    # grâce), là où _comparer exige un parcours parfait.
                    if args.delister:
                        ligne.update(_delister(store, args.source, deal, vus, actives,
                                               trous, derniere, rec.fin is not None))

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
                ligne["conclusion"] = _message_trous(trous, derniere)
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
                ligne.update(_comparer(vus, actives))
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
    # Remonté à la racine du bilan pour être LISIBLE sans ouvrir les flux : c'est
    # le chiffre qui dit si le recensement a servi à quelque chose cette nuit.
    # Il valait 0 à tous les runs trouées avant le correctif du 2026-09-09.
    bilan["rafraichies"] = sum(f.get("rafraichies", 0) for f in bilan["flux"])
    bilan["delistees"] = sum(f.get("delistees", 0) for f in bilan["flux"])
    # Bilan JSON terminal : lu par agents/core/shell.py (_bilan_json) et vérifié
    # par l'overseer contre le contrat de sortie du SKILL.
    print(json.dumps(bilan, ensure_ascii=False, indent=1))
    # CODE RETOUR 0 MÊME QUAND ON S'ABSTIENT. Erreur de conception du
    # 2026-08-25, mesurée la nuit suivante : le recensement rendait 1 quand il
    # refusait de conclure, et l'orchestrateur marquait donc `extract-ddproperty`
    # EN ÉCHEC alors que ses trois passes de scrap avaient parfaitement réussi.
    # Une abstention honnête affichée comme une panne, chaque nuit, c'est le
    # garde-fou qui crie au loup (règle 2). L'abstention se lit dans
    # `flux_non_conclusifs` — c'est là qu'elle doit être regardée.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
