"""dashboard.py — ce que fait le scrap EN COURS, et rien d'autre.

Réécrit le 2026-08-25. La version précédente montrait l'état GÉNÉRAL de la base
(typologie par quartier, tranches de prix) et faisait tourner l'affichage entre
plusieurs sources de données à la touche [S] — dont « SUPABASE (production) »,
placée en tête. Deux défauts mesurés le jour de la réécriture :

1. **Elle regardait le mauvais endroit.** Depuis le 2026-08-23 la base de
   référence est LOCALE : les cinq extracteurs tournent en `--store sqlite` et
   le serveur est figé. Ouvert par défaut sur Supabase, le dashboard montrait
   donc un instantané mort pendant qu'un scrap écrivait à côté.
2. **Elle ne répondait pas à la question posée.** « Où en est le scrap ? » ne se
   lit pas dans des tranches de prix : il faut savoir QUI tourne, DEPUIS QUAND,
   à QUELLE ÉTAPE, ce qui a été écrit depuis le départ, et si ça avance encore.

Une seule source (`scraper/output/bangkok.db`), aucune rotation. Tant qu'un
extracteur tourne : sa progression. Quand plus rien ne tourne : le RÉSULTAT du
dernier cycle, qui reste affiché.

Lecture strictement SEULE (`mode=ro`) : le scrap écrit pendant qu'on lit.

Lancement : double-clic sur ops\\Dashboard.bat
            ou  scraper\\.venv\\Scripts\\python.exe ops/dashboard.py

Touches :  F  plein écran / fenêtre     R  rafraîchir maintenant
           Échap / Q  quitter
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import tkinter as tk
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: LA base du cycle. Chemin unique et en dur À DESSEIN : c'est celle que visent
#: les cinq extracteurs (`--store sqlite`, cf. agents/agents.json). Un dashboard
#: qui « cherche une base » finit par en trouver une périmée et l'afficher sans
#: le dire — c'est exactement ce qui s'était produit avec Supabase.
BASE = os.path.join(ROOT, "scraper", "output", "bangkok.db")
LEDGER = os.path.join(ROOT, "agents", "ledger.db")
AGENTS_JSON = os.path.join(ROOT, "agents", "agents.json")

#: Témoin de présence. L'orchestrateur ouvre le dashboard au départ du scrap
#: (cf. run_lane) ; sans ce fichier il empilerait une fenêtre par cycle, y
#: compris par-dessus celle qu'on a ouverte soi-même au double-clic.
TEMOIN = os.path.join(ROOT, "agents", "state", "dashboard.pid")

# Palette phosphore : fond anthracite, ambre dominant, violet pour les accents
# (repris des tokens du projet), vert pour ce qui va bien, rouge pour l'anomalie.
BG = "#0b0d10"
FG = "#ffb000"      # ambre
DIM = "#6b5a2e"
OK = "#48d17a"
WARN = "#ff5f5f"
ACC = "#b06cff"     # violet Lowi
WHITE = "#e8e8e8"

POLICE = ("Consolas", 14)
POLICE_T = ("Consolas", 16, "bold")
POLICE_XL = ("Consolas", 9)

BANNIERE = [
    "██      ████  ██   ██ ██ ",
    "██     ██  ██ ██   ██ ██ ",
    "██     ██  ██ ██ █ ██ ██ ",
    "██     ██  ██ ███████ ██ ",
    "██████  ████  ███ ███ ██ ",
]

#: Le scrap est jugé VIVANT si son journal a bougé dans ce délai. Un extracteur
#: passe des minutes sur une page lourde (fiche + galerie webp) : trop court, le
#: dashboard crierait « bloqué » à chaque photo (règle 2).
SILENCE_SUSPECT_S = 600


def duree(sec: float) -> str:
    sec = max(0, int(sec))
    if sec < 90:
        return f"{sec} s"
    if sec < 5400:
        return f"{sec // 60} min"
    return f"{sec // 3600} h {(sec % 3600) // 60:02d}"


def _lire(chemin: str, sql: str, params=()) -> list[dict]:
    """Lecture seule, jamais bloquante pour l'affichage."""
    try:
        uri = "file:" + chemin.replace("\\", "/") + "?mode=ro"
        c = sqlite3.connect(uri, uri=True, timeout=2)
        c.row_factory = sqlite3.Row
        r = [dict(x) for x in c.execute(sql, params)]
        c.close()
        return r
    except sqlite3.Error:
        return []


def etapes_attendues() -> dict[str, int]:
    """Nombre de passes par extracteur : la commande principale + ses `then`
    (sale, puis rent, puis la passe ciblée « corridors »). Sert à afficher
    « passe 2/4 » — sans quoi un extracteur à 4 passes semble figé pendant des
    heures alors qu'il enchaîne."""
    try:
        reg = json.load(open(AGENTS_JSON, encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {a["name"]: 1 + len(a.get("then") or []) for a in reg["agents"]}


def derniers_runs(limite: int = 40) -> list[dict]:
    """40 et pas 14 : un cycle complet compte jusqu'à 17 runs, plus les reprises
    d'un extracteur qui a échoué au premier essai (4 le 2026-08-25). Trop court,
    le tableau de résultat coupait le début du cycle — donc les extracteurs, donc
    les seules lignes qui portent des chiffres."""
    return _lire(LEDGER,
                 "select agent,status,started_at,ended_at,metrics,log_path "
                 "from agent_runs order by id desc limit ?", (limite,))


def etape_courante(log_path: str | None) -> tuple[int, str | None]:
    """Passe en cours et fichier journal correspondant.

    `run_agent` écrit la commande principale dans `<log>` puis chaque `then`
    dans `<log>.then_0`, `.then_1`… La passe en cours est donc le dernier
    fichier de la série qui existe."""
    if not log_path or not os.path.exists(log_path):
        return 0, None
    courant, n = log_path, 0
    while os.path.exists(f"{log_path}.then_{n}"):
        courant, n = f"{log_path}.then_{n}", n + 1
    return n, courant


class Dashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LOWI BKK — scrap en cours")
        self.configure(bg=BG)
        self.geometry("1920x1080")
        self.plein = False
        self.etapes = etapes_attendues()
        self.zone = tk.Text(self, bg=BG, fg=FG, font=POLICE, bd=0,
                            highlightthickness=0, wrap="none",
                            insertbackground=BG, padx=26, pady=14)
        self.zone.pack(fill="both", expand=True)
        for nom, col in (("dim", DIM), ("ok", OK), ("warn", WARN),
                         ("acc", ACC), ("w", WHITE), ("t", FG)):
            self.zone.tag_configure(nom, foreground=col)
        self.zone.tag_configure("t", font=POLICE_T)
        self.zone.tag_configure("banniere", foreground=ACC, font=POLICE_XL)

        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("q", lambda e: self.destroy())
        self.bind("f", lambda e: self.bascule_plein())
        self.bind("r", lambda e: self.rafraichir())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.pose_temoin()
        self.rafraichir()

    def pose_temoin(self):
        try:
            os.makedirs(os.path.dirname(TEMOIN), exist_ok=True)
            with open(TEMOIN, "w", encoding="utf-8") as f:
                f.write(str(os.getpid()))
        except OSError:
            pass          # jamais bloquant : le témoin est un confort, pas un dû

    def destroy(self):
        try:
            if os.path.exists(TEMOIN):
                os.remove(TEMOIN)
        except OSError:
            pass
        super().destroy()

    def bascule_plein(self):
        self.plein = not self.plein
        self.attributes("-fullscreen", self.plein)

    # ── rendu ────────────────────────────────────────────────────────────
    def ecrire(self, texte: str, tag: str = "t"):
        self.zone.insert("end", texte, tag)

    def barre(self, n: int, total: int, largeur: int = 30) -> str:
        if total <= 0:
            return "░" * largeur
        plein = int(largeur * min(1.0, n / total))
        return "█" * plein + "░" * (largeur - plein)

    def rafraichir(self):
        self.zone.delete("1.0", "end")
        for ligne in BANNIERE:
            self.ecrire("  " + ligne + "\n", "banniere")

        maint = datetime.now().strftime("%d/%m %H:%M:%S")
        self.ecrire(f"  BANGKOK · scrap en cours{' ' * 34}{maint}\n", "w")
        if os.path.exists(BASE):
            mo = os.path.getsize(BASE) / 1e6
            ecrit = duree(datetime.now().timestamp() - os.path.getmtime(BASE))
            self.ecrire(f"  base : scraper/output/bangkok.db  ({mo:.0f} Mo, "
                        f"écrite il y a {ecrit})\n", "dim")
        else:
            self.ecrire(f"  base INTROUVABLE : {BASE}\n", "warn")
        self.ecrire("  " + "─" * 140 + "\n\n", "dim")

        runs = derniers_runs()
        en_cours = [r for r in runs if r["status"] == "running"]
        if en_cours:
            self.vue_en_cours(en_cours)
        else:
            self.vue_resultat(runs)

        self.ecrire("\n  " + "─" * 140 + "\n", "dim")
        self.ecrire("  [F] plein écran   [R] rafraîchir   [Q] quitter"
                    "        lecture seule — aucun impact sur le scrap\n", "dim")
        self.after(5000, self.rafraichir)

    # ── pendant le scrap ─────────────────────────────────────────────────
    def vue_en_cours(self, en_cours: list[dict]):
        depart = min(r["started_at"] for r in en_cours)
        self.ecrire("  ▐ EN COURS\n", "t")
        journal = None
        for r in en_cours:
            t0 = datetime.fromisoformat(r["started_at"])
            n, log = etape_courante(r["log_path"])
            total = self.etapes.get(r["agent"], 1)
            journal = journal or log
            ecoule = duree((datetime.now(timezone.utc) - t0).total_seconds())
            self.ecrire(f"    {r['agent']:<24}", "w")
            self.ecrire(f"depuis {ecoule:<10}", "acc")
            self.ecrire(f"passe {n + 1}/{total}   ", "w")
            if log and os.path.exists(log):
                mut = datetime.now().timestamp() - os.path.getmtime(log)
                vivant = mut < SILENCE_SUSPECT_S
                self.ecrire(f"dernière ligne il y a {duree(mut):<8}", "dim")
                self.ecrire("[ACTIF]\n" if vivant else "[SILENCIEUX]\n",
                            "ok" if vivant else "warn")
            else:
                self.ecrire("(journal pas encore ouvert)\n", "dim")

        # Ce que CE scrap a écrit, pas l'état général de la base : les compteurs
        # sont bornés au départ du run. C'est la seule mesure qui répond à
        # « est-ce que ça avance ? » — un total de 72 695 ne bouge pas à l'œil.
        self.ecrire(f"\n  ▐ ÉCRIT DEPUIS LE DÉPART ({depart[11:16]} UTC)\n", "t")
        lignes = _lire(BASE,
                       "select source, deal_type, "
                       " sum(case when last_seen  >= ? then 1 else 0 end) vues, "
                       " sum(case when first_seen >= ? then 1 else 0 end) neuves, "
                       " count(*) tot "
                       "from listings group by source, deal_type order by vues desc",
                       (depart, depart))
        actives = [x for x in lignes if x["vues"]]
        if not actives:
            self.ecrire("    aucune annonce encore touchée par ce cycle\n", "dim")
        else:
            self.ecrire(f"    {'source':<16}{'deal':<7}{'revues':>8}{'nouvelles':>11}"
                        f"   {'part du stock de la source':<32}{'stock':>8}\n", "dim")
            for x in actives:
                self.ecrire(f"    {x['source']:<16}{x['deal_type']:<7}"
                            f"{x['vues']:>8}{x['neuves']:>11}   "
                            f"{self.barre(x['vues'], max(1, x['tot']))}  "
                            f"{x['tot']:>8}\n", "w")
            self.ecrire(f"    {'TOTAL':<23}{sum(x['vues'] for x in actives):>8}"
                        f"{sum(x['neuves'] for x in actives):>11}\n", "acc")

        if journal:
            self.ecrire(f"\n  ▐ JOURNAL — {os.path.basename(journal)}\n", "t")
            for ligne in self.queue_journal(journal, 14):
                self.ecrire(f"    {ligne}\n", "dim")

    def queue_journal(self, chemin: str, n: int) -> list[str]:
        """Dernières lignes du journal en cours. Les logs d'extraction pèsent
        des centaines de kilo-octets (mesuré : 365 ko pour UNE passe) : on lit
        la fin du fichier, pas le fichier."""
        try:
            with open(chemin, "rb") as f:
                f.seek(0, os.SEEK_END)
                f.seek(max(0, f.tell() - 16384))
                brut = f.read().decode("utf-8", "replace")
        except OSError:
            return ["(journal illisible)"]
        lignes = [x.rstrip()[:150] for x in brut.splitlines() if x.strip()]
        return lignes[-n:]

    # ── après le scrap ───────────────────────────────────────────────────
    def vue_resultat(self, runs: list[dict]):
        """Aucun scrap en vol : on montre le RÉSULTAT du dernier cycle et on le
        laisse à l'écran. C'est ce qu'on vient lire le matin."""
        self.ecrire("  ▐ AUCUN SCRAP EN COURS — RÉSULTAT DU DERNIER CYCLE\n", "t")
        if not runs:
            self.ecrire("    le ledger ne contient aucun run.\n", "warn")
            return
        jour = runs[0]["started_at"][:10]
        cycle = [r for r in runs if r["started_at"][:10] == jour]
        self.ecrire(f"    cycle du {jour}\n\n", "dim")
        self.ecrire(f"    {'agent':<24}{'état':<12}{'début':<8}{'durée':<10}"
                    f"{'scannées':>9}{'nouvelles':>10}{'changées':>9}"
                    f"{'retirées':>9}{'erreurs':>8}\n", "dim")
        cumul = {"scannees": 0, "nouvelles": 0, "changees": 0, "retirees": 0}
        for r in reversed(cycle):
            try:
                m = json.loads(r["metrics"] or "{}")
            except ValueError:
                m = {}
            for k in cumul:
                if isinstance(m.get(k), int):
                    cumul[k] += m[k]
            fin = r["ended_at"]
            d = duree((datetime.fromisoformat(fin)
                       - datetime.fromisoformat(r["started_at"])).total_seconds()) \
                if fin else "…"
            err = (m.get("erreurs_http") or 0) + (m.get("erreurs_images") or 0)
            tag = {"ok": "w", "failed": "warn", "interrompu": "warn"}.get(
                r["status"], "dim")

            def col(cle, largeur=9):
                v = m.get(cle)
                return f"{v:>{largeur}}" if isinstance(v, int) else " " * largeur

            self.ecrire(f"    {r['agent']:<24}{r['status']:<12}"
                        f"{r['started_at'][11:16]:<8}{d:<10}"
                        f"{col('scannees')}{col('nouvelles', 10)}{col('changees')}"
                        f"{col('retirees')}{err if err else '':>8}\n", tag)
        self.ecrire(f"\n    {'CUMUL DU CYCLE':<44}"
                    f"{cumul['scannees']:>9}{cumul['nouvelles']:>10}"
                    f"{cumul['changees']:>9}{cumul['retirees']:>9}\n", "acc")

        tot = _lire(BASE, "select count(*) n from listings")
        if tot:
            self.ecrire(f"\n    base : {tot[0]['n']} annonces au total\n", "w")

        rates = [r for r in cycle if r["status"] in ("failed", "interrompu")]
        if rates:
            self.ecrire(f"\n    ⚠ {len(rates)} agent(s) en échec : "
                        f"{', '.join(r['agent'] for r in rates)}\n", "warn")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--plein", action="store_true", help="démarrer en plein écran")
    a = ap.parse_args()
    app = Dashboard()
    if a.plein:
        app.bascule_plein()
    app.mainloop()
