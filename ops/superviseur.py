"""superviseur.py — reprend le scrap tout seul apres une coupure.

CE QUI A MOTIVE CE FICHIER (2026-08-01). Une coupure internet a tue les quatre
scrapers. Les donnees etaient sauves (ecriture annonce par annonce), mais deux
choses manquaient :

  1. personne ne les relancait ;
  2. pire, `run.py` avait enregistre un scan_run marque **'full'** alors qu'il
     venait d'etre interrompu a 928 annonces sur ~5000. Une perte de reseau
     ressemblait a une fin de scan reussie — et un scan partiel pris pour
     complet peut declencher un delistage a tort.

Le superviseur ne fait donc PAS confiance au code retour seul : il compare le
volume ramene a ce qui est attendu, et relit le log a la recherche de traces
d'echec reseau.

GARANTIES
  · etat sur disque, ecrit a chaque transition -> survit a une coupure de courant
  · verification toutes les 30 s : internet, processus vivant, avancement
  · reprise automatique des sources non terminees, avec plafond de tentatives
  · aucune relance tant qu'internet n'est pas revenu (evite de bruler les essais)
  · un scrap deja termine n'est jamais relance

USAGE
    python ops/superviseur.py --dossier <dossier-scrap> [--local]
    python ops/superviseur.py --etat          # etat courant, puis sortie
Installation au demarrage de Windows : ops/install-superviseur.ps1
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, "scraper", ".venv", "Scripts", "python.exe")
RUN = os.path.join(ROOT, "scraper", "run.py")

INTERVALLE = 30           # secondes entre deux verifications
MAX_TENTATIVES = 12       # au-dela, on cesse et on le signale
INACTIVITE_MAX = 600      # 10 min sans nouvelle annonce = processus fige

# Le travail a accomplir. `min_attendu` sert a distinguer un scan COMPLET d'un
# scan tue en cours de route : c'est un plancher grossier, volontairement bas.
TRAVAIL = [
    {"source": "fazwaz", "deal": "sale", "min_attendu": 2500, "geocode": False},
    {"source": "fazwaz", "deal": "rent", "min_attendu": 2500, "geocode": False},
    {"source": "ddproperty", "deal": "sale", "min_attendu": 1500, "geocode": True},
    {"source": "ddproperty", "deal": "rent", "min_attendu": 1500, "geocode": True},
    {"source": "propertyscout", "deal": None, "min_attendu": 800, "geocode": False},
    {"source": "nestopa", "deal": None, "min_attendu": 400, "geocode": True},
]

MARQUEURS_RESEAU = ("échec GET", "echec GET", "ConnectionError", "Max retries",
                    "Connection aborted", "Read timed out", "getaddrinfo failed")


def maintenant() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cle(t: dict) -> str:
    return f"{t['source']}:{t['deal'] or 'both'}"


# ───────────────────────── etat persistant ─────────────────────────
class Etat:
    """Ecrit a chaque transition, de facon atomique : une coupure de courant au
    milieu d'une ecriture ne doit pas laisser un fichier tronque."""

    def __init__(self, dossier: str):
        self.chemin = os.path.join(dossier, "superviseur-etat.json")
        self.d = {"dossier": dossier, "demarre": maintenant(), "taches": {}}
        if os.path.exists(self.chemin):
            try:
                self.d = json.load(open(self.chemin, encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        for t in TRAVAIL:
            self.d["taches"].setdefault(cle(t), {
                "statut": "a_faire", "tentatives": 0, "scanned": 0,
                "derniere_erreur": None, "fini_le": None})

    def sauver(self) -> None:
        tmp = self.chemin + ".tmp"
        self.d["maj"] = maintenant()
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.d, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.chemin)      # atomique

    def tache(self, t: dict) -> dict:
        return self.d["taches"][cle(t)]


# ───────────────────────── sondes ─────────────────────────
def internet_ok(hotes=(("www.fazwaz.com", 443), ("www.ddproperty.com", 443)),
                timeout: float = 5.0) -> bool:
    """On sonde les SOURCES elles-memes, pas un serveur tiers : ce qui compte
    n'est pas d'avoir une route, c'est que les sites repondent."""
    for hote, port in hotes:
        try:
            with socket.create_connection((hote, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def annonces_en_base(dossier: str, source: str, deal: str | None) -> int:
    import sqlite3
    p = os.path.join(dossier, "bangkok.db")
    if not os.path.exists(p):
        return 0
    try:
        c = sqlite3.connect("file:" + p.replace("\\", "/") + "?mode=ro", uri=True, timeout=5)
        q = "select count(*) from listings where source=?"
        args: tuple = (source,)
        if deal:
            q += " and deal_type=?"
            args += (deal,)
        n = c.execute(q, args).fetchone()[0]
        c.close()
        return int(n)
    except Exception:      # noqa: BLE001 — la base est peut-etre en ecriture
        return 0


def log_montre_coupure(chemin_log: str) -> bool:
    if not os.path.exists(chemin_log):
        return False
    try:
        txt = open(chemin_log, encoding="utf-8", errors="replace").read()[-20000:]
    except OSError:
        return False
    return sum(txt.count(m) for m in MARQUEURS_RESEAU) >= 3


# ───────────────────────── lancement ─────────────────────────
def lancer(t: dict, dossier: str) -> subprocess.Popen:
    cmd = [PY, RUN, "--source", t["source"], "--full", "--store", "sqlite"]
    if t["deal"]:
        cmd += ["--deal-type", t["deal"]]
    if t["geocode"]:
        cmd += ["--geocode"]
    env = os.environ.copy()
    env["LOWI_OUTPUT_DIR"] = dossier
    log = os.path.join(dossier, f"sup-{t['source']}-{t['deal'] or 'both'}.log")
    fh = open(log, "a", encoding="utf-8", errors="replace")
    fh.write(f"\n===== lancement {maintenant()} =====\n")
    fh.flush()
    # CREATE_NO_WINDOW : sans ce drapeau, Windows ouvre une console par
    # sous-processus — quatre sources, quatre fenetres qui polluent l'ecran.
    # La sortie part deja dans le fichier de log, rien n'est perdu.
    sans_fenetre = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    p = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=fh,
                         stderr=subprocess.STDOUT, creationflags=sans_fenetre)
    p._log = log      # type: ignore[attr-defined]
    p._fh = fh        # type: ignore[attr-defined]
    return p


def journaliser(dossier: str, msg: str) -> None:
    ligne = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(ligne, flush=True)
    try:
        with open(os.path.join(dossier, "superviseur.log"), "a",
                  encoding="utf-8") as f:
            f.write(ligne + "\n")
    except OSError:
        pass


def boucle(dossier: str) -> int:
    os.makedirs(dossier, exist_ok=True)
    etat = Etat(dossier)
    etat.sauver()
    en_cours: dict[str, subprocess.Popen] = {}
    dernier_volume: dict[str, tuple[int, float]] = {}

    journaliser(dossier, f"superviseur demarre — dossier {os.path.basename(dossier)}")

    while True:
        restantes = [t for t in TRAVAIL if etat.tache(t)["statut"] != "fait"]
        if not restantes and not en_cours:
            journaliser(dossier, "toutes les sources sont terminees — arret du superviseur")
            etat.d["fini"] = maintenant()
            etat.sauver()
            # BILAN + JUGEMENT en fin de cycle. Ils etaient cables sur
            # lancement-complet.ps1, mais c'est le superviseur qui pilote des
            # qu'une reprise a eu lieu : sans ce bloc, un cycle repris apres
            # coupure se terminait en silence.
            # Le referentiel d'immeubles est recalcule ICI, sur les donnees
            # fraiches : l'annee de livraison est une propriete du BATIMENT,
            # elle se consolide par vote entre toutes les annonces qui le
            # citent. Sortie dans un fichier AUTONOME du dossier de scrap —
            # aucune ecriture dans listings, ni en local ni en ligne.
            for script, args in (("bilan-scrap.py", [dossier, "--md"]),
                                 ("referentiel-condos.py",
                                  ["--db", os.path.join(dossier, "bangkok.db")]),
                                 ("juge-test.py", [dossier])):
                chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)), script)
                if not os.path.exists(chemin):
                    continue
                sortie = os.path.join(dossier, script.replace(".py", ".txt"))
                try:
                    with open(sortie, "w", encoding="utf-8", errors="replace") as f:
                        subprocess.run([PY, chemin, *args], cwd=ROOT, stdout=f,
                                       stderr=subprocess.STDOUT, timeout=1800,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    journaliser(dossier, f"✓ {script} ecrit dans {os.path.basename(sortie)}")
                except Exception as e:                       # noqa: BLE001
                    journaliser(dossier, f"! {script} a echoue : {type(e).__name__} {e}")
            journaliser(dossier, "cycle complet — bilan disponible dans le dossier du scrap")
            return 0

        net = internet_ok()
        if not net:
            journaliser(dossier, "internet indisponible — en attente (aucune relance)")
            time.sleep(INTERVALLE)
            continue

        # ── processus termines ────────────────────────────────────────
        for k, p in list(en_cours.items()):
            code = p.poll()
            if code is None:
                continue
            t = next(x for x in TRAVAIL if cle(x) == k)
            info = etat.tache(t)
            try:
                p._fh.close()          # type: ignore[attr-defined]
            except Exception:          # noqa: BLE001
                pass
            n = annonces_en_base(dossier, t["source"], t["deal"])
            info["scanned"] = n
            coupure = log_montre_coupure(p._log)     # type: ignore[attr-defined]

            # CRITERE DE FIN — corrige le 2026-08-01.
            #
            # Premiere version : seuil ABSOLU (« au moins N annonces »). Mauvais.
            # La fenetre de 150 pages triee par fraicheur ne ramene pas tout le
            # catalogue d'un coup, et chaque passe en decouvre de nouvelles. Le
            # seuil n'etait jamais atteint -> FazWaz a ete re-scanne 4 fois pour
            # rien, ce qui explique a lui seul la duree du cycle.
            #
            # Bon critere : la CONVERGENCE. Une passe qui n'apporte quasiment
            # plus rien signifie qu'on a vu ce que la fenetre peut montrer.
            avant = info.get("scanned_precedent", 0)
            apport = n - avant
            info["scanned_precedent"] = n
            converge = info["tentatives"] >= 2 and apport < max(20, int(0.02 * max(n, 1)))
            assez = n >= t["min_attendu"]

            if code == 0 and not coupure and (assez or converge):
                info["statut"] = "fait"
                info["fini_le"] = maintenant()
                info["derniere_erreur"] = None      # ne pas garder une erreur perimee
                motif = "seuil atteint" if assez else f"converge (+{apport} seulement)"
                journaliser(dossier, f"✓ {k} termine — {n} annonces ({motif})")
            else:
                raison = ("coupure reseau detectee dans le log" if coupure
                          else f"volume {n}, +{apport} sur cette passe — on continue"
                          if not assez else f"code retour {code}")
                info["statut"] = "a_reprendre"
                info["derniere_erreur"] = raison
                journaliser(dossier, f"↻ {k} a reprendre — {raison} ({n} annonces gardees)")
            del en_cours[k]
            etat.sauver()

        # ── processus figes (aucune annonce nouvelle depuis 10 min) ────
        for k, p in list(en_cours.items()):
            t = next(x for x in TRAVAIL if cle(x) == k)
            n = annonces_en_base(dossier, t["source"], t["deal"])
            avant, quand = dernier_volume.get(k, (-1, time.time()))
            if n > avant:
                dernier_volume[k] = (n, time.time())
            elif time.time() - quand > INACTIVITE_MAX:
                journaliser(dossier, f"⏱ {k} fige depuis {INACTIVITE_MAX//60} min — on le tue")
                try:
                    p.kill()
                except Exception:      # noqa: BLE001
                    pass
                dernier_volume.pop(k, None)

        # ── lancements ────────────────────────────────────────────────
        # Les 4 sources sont 4 domaines distincts : les lancer ensemble ne change
        # rien a la cadence vue par chacune.
        for t in TRAVAIL:
            k = cle(t)
            info = etat.tache(t)
            if info["statut"] == "fait" or k in en_cours:
                continue
            # une seule tache par SOURCE a la fois (meme domaine = meme cadence)
            if any(cle(x).split(":")[0] == t["source"] for x in TRAVAIL
                   if cle(x) in en_cours):
                continue
            if info["tentatives"] >= MAX_TENTATIVES:
                if info["statut"] != "abandonne":
                    info["statut"] = "abandonne"
                    journaliser(dossier, f"✗ {k} abandonne apres "
                                         f"{MAX_TENTATIVES} tentatives")
                    etat.sauver()
                continue
            info["tentatives"] += 1
            info["statut"] = "en_cours"
            etat.sauver()
            en_cours[k] = lancer(t, dossier)
            dernier_volume[k] = (annonces_en_base(dossier, t["source"], t["deal"]),
                                 time.time())
            journaliser(dossier, f"▶ {k} lance (tentative {info['tentatives']})")

        time.sleep(INTERVALLE)


def afficher_etat(dossier: str) -> int:
    chemin = os.path.join(dossier, "superviseur-etat.json")
    if not os.path.exists(chemin):
        print("Aucun etat de superviseur dans", dossier)
        return 1
    d = json.load(open(chemin, encoding="utf-8"))
    print(f"dossier : {d.get('dossier')}\nmaj     : {d.get('maj')}\n")
    # Le champ `scanned` de l'etat date du dernier ARRET de processus. Pour une
    # tache en cours il est perime : on relit la base pour afficher le vrai
    # chiffre, et on montre l'ecart (= ce que la passe en cours a deja apporte).
    print(f"{'tache':<22}{'statut':<12}{'essais':>7}{'en base':>9}{'cette passe':>13}  note")
    total = 0
    for k, v in d["taches"].items():
        src, deal = k.split(":")
        vivant = annonces_en_base(dossier, src, None if deal == "both" else deal)
        total += vivant
        delta = vivant - v.get("scanned_precedent", v.get("scanned", 0))
        note = v.get("derniere_erreur") or ""
        if v["statut"] == "fait":
            note = ""                      # une tache finie n'a pas d'erreur en cours
        print(f"{k:<22}{v['statut']:<12}{v['tentatives']:>7}{vivant:>9}"
              f"{('+' + str(delta)) if delta else '—':>13}  {note}")
    print(f"\n{'TOTAL':<22}{'':<12}{'':>7}{total:>9}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dossier", default=None)
    ap.add_argument("--etat", action="store_true", help="affiche l'etat et sort")
    a = ap.parse_args()

    dossier = a.dossier
    if not dossier:
        import glob
        cands = sorted(glob.glob(os.path.join(ROOT, "tests-scrap", "*", "")),
                       key=os.path.getmtime, reverse=True)
        if not cands:
            sys.exit("Aucun dossier de scrap trouve — passer --dossier")
        dossier = cands[0].rstrip("\\/")
    dossier = os.path.abspath(dossier)

    sys.exit(afficher_etat(dossier) if a.etat else boucle(dossier))
