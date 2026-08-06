"""dashboard.py — suivi live du scrap, style terminal / pixel art, 1920x1080.

Lit directement les bases SQLite des scraps LOCAUX de test (aucune requête
réseau, aucun impact sur le scrap) et le ledger des agents. Depuis le
2026-08-06, l'archi de test locale (tests-scrap/) est abandonnée au profit de
agents/orchestrator.py qui écrit DIRECTEMENT dans Supabase (--store supabase) —
sans ça, ce dashboard ne montrait plus jamais un scrap réel : il ne savait lire
que des bases SQLite locales, qu'un scrap en ligne n'écrit jamais. La source
"SUPABASE (production)" ci-dessous corrige ça, en lecture seule (SELECT
uniquement, jamais d'écriture). Rafraîchi toutes les 5 secondes.

Lancement : double-clic sur ops\\Dashboard.bat
            ou  scraper\.venv\Scripts\python.exe ops/dashboard.py [--db <chemin>]

Touches :  F  plein écran / fenêtre      R  rafraîchir maintenant
           S  source de données suivante  Échap / Q  quitter
"""
from __future__ import annotations

import argparse
import glob
import os
import sqlite3
import tkinter as tk
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUPABASE = "SUPABASE (production)"   # pseudo-chemin : marqueur de la source en ligne


def _supabase_dsn() -> str | None:
    """Lit SUPABASE_DB_URL depuis scraper/.env, sans dépendance (même motif que
    scraper/run.py:load_env / ops/remonter-local.py)."""
    env = os.path.join(ROOT, "scraper", ".env")
    if not os.path.exists(env):
        return None
    for ligne in open(env, encoding="utf-8"):
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        k, v = ligne.split("=", 1)
        if k.strip() == "SUPABASE_DB_URL":
            return v.strip()
    return None

# Palette phosphore : fond anthracite, ambre dominant, violet pour les accents
# (repris des tokens du projet), vert pour ce qui va bien, rouge pour l'anomalie.
BG = "#0b0d10"
FG = "#ffb000"      # ambre
DIM = "#6b5a2e"
OK = "#48d17a"
WARN = "#ff5f5f"
ACC = "#b06cff"     # violet Lowi
WHITE = "#e8e8e8"

POLICE = ("Consolas", 13)
POLICE_T = ("Consolas", 15, "bold")
POLICE_XL = ("Consolas", 9)

# Bannière pixel : blocs pleins, lisible en 1920 de large
BANNIERE = [
    "██      ████  ██   ██ ██ ",
    "██     ██  ██ ██   ██ ██ ",
    "██     ██  ██ ██ █ ██ ██ ",
    "██     ██  ██ ███████ ██ ",
    "██████  ████  ███ ███ ██ ",
]

TRANCHES_VENTE = [(0, 3e6), (3e6, 6e6), (6e6, 12e6), (12e6, 25e6), (25e6, 1e12)]
TRANCHES_LOYER = [(0, 15e3), (15e3, 30e3), (30e3, 60e3), (60e3, 120e3), (120e3, 1e12)]


def thb(x: float) -> str:
    if x >= 1e12:
        return "∞"
    if x >= 1e6:
        return f"{x / 1e6:g}M"
    if x >= 1e3:
        return f"{x / 1e3:g}k"
    return f"{x:g}"


def bases_disponibles() -> list[str]:
    """SUPABASE (si SUPABASE_DB_URL est configuré) en premier — c'est la
    production, ce qu'un scrap --store supabase écrit réellement — puis les
    bases SQLite locales trouvées (tests-scrap/ hérité, scraper/output/ pour un
    run --store sqlite ponctuel), la plus récemment modifiée d'abord."""
    out = [SUPABASE] if _supabase_dsn() else []
    trouvees = glob.glob(os.path.join(ROOT, "tests-scrap", "*", "bangkok.db"))
    trouvees += glob.glob(os.path.join(ROOT, "scraper", "output", "bangkok.db"))
    out += sorted((f for f in trouvees if os.path.exists(f)),
                  key=os.path.getmtime, reverse=True)
    return out


class Source:
    """Accès en LECTURE SEULE : le scrap écrit pendant qu'on lit."""

    def __init__(self, chemin: str):
        self.chemin = chemin

    def _q(self, sql: str, params=()):
        try:
            uri = "file:" + self.chemin.replace("\\", "/") + "?mode=ro"
            c = sqlite3.connect(uri, uri=True, timeout=2)
            c.row_factory = sqlite3.Row
            r = [dict(x) for x in c.execute(sql, params)]
            c.close()
            return r
        except sqlite3.Error:
            return []

    def total(self) -> int:
        r = self._q("select count(*) n from listings")
        return r[0]["n"] if r else 0

    def par_source(self):
        return self._q("select source, deal_type, count(*) n, "
                       "count(description) d, count(lat) g from listings "
                       "group by source, deal_type order by n desc")

    def chambres_par_khet(self, deal: str, limite: int = 14):
        return self._q(
            "select khet, "
            " sum(case when bedrooms=0 then 1 else 0 end) st, "
            " sum(case when bedrooms=1 then 1 else 0 end) b1, "
            " sum(case when bedrooms=2 then 1 else 0 end) b2, "
            " sum(case when bedrooms>=3 then 1 else 0 end) b3, "
            " count(*) tot "
            "from listings where khet is not null and deal_type=? "
            "group by khet order by tot desc limit ?", (deal, limite))

    def tranches(self, deal: str, bornes):
        out = []
        for lo, hi in bornes:
            r = self._q("select count(*) n from listings "
                        "where deal_type=? and price>=? and price<?", (deal, lo, hi))
            out.append((lo, hi, r[0]["n"] if r else 0))
        return out

    def cadence(self):
        r = self._q("select min(first_seen) a, max(first_seen) b, count(*) n from listings")
        if not r or not r[0]["a"]:
            return None
        try:
            d0 = datetime.fromisoformat(r[0]["a"])
            d1 = datetime.fromisoformat(r[0]["b"])
        except (TypeError, ValueError):
            return None
        sec = (d1 - d0).total_seconds()
        n = r[0]["n"]
        return {"n": n, "sec": sec, "par_h": (n / sec * 3600) if sec > 0 else 0,
                "dernier": d1}


class SourceSupabase:
    """Même interface que Source, mais lit Postgres (production) — SELECT
    uniquement, jamais d'écriture. Une connexion par appel : le dashboard
    tourne des heures, une connexion persistante finirait par expirer ou
    laisser un idle-in-transaction inutile sur un pooler partagé."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    def _q(self, sql: str, params=()):
        try:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(self.dsn, connect_timeout=5, autocommit=True,
                                 row_factory=dict_row) as c:
                with c.cursor() as cur:
                    cur.execute(sql, params)
                    return cur.fetchall()
        except Exception:      # noqa: BLE001 — jamais bloquant pour l'affichage
            return []

    def total(self) -> int:
        r = self._q("select count(*) n from listings")
        return r[0]["n"] if r else 0

    def par_source(self):
        return self._q("select source, deal_type, count(*) n, "
                       "count(description) d, count(lat) g from listings "
                       "group by source, deal_type order by n desc")

    def chambres_par_khet(self, deal: str, limite: int = 14):
        return self._q(
            "select khet, "
            " sum(case when bedrooms=0 then 1 else 0 end) st, "
            " sum(case when bedrooms=1 then 1 else 0 end) b1, "
            " sum(case when bedrooms=2 then 1 else 0 end) b2, "
            " sum(case when bedrooms>=3 then 1 else 0 end) b3, "
            " count(*) tot "
            "from listings where khet is not null and deal_type=%s "
            "group by khet order by tot desc limit %s", (deal, limite))

    def tranches(self, deal: str, bornes):
        out = []
        for lo, hi in bornes:
            r = self._q("select count(*) n from listings "
                        "where deal_type=%s and price>=%s and price<%s", (deal, lo, hi))
            out.append((lo, hi, r[0]["n"] if r else 0))
        return out

    def cadence(self):
        r = self._q("select min(first_seen) a, max(first_seen) b, count(*) n "
                    "from listings")
        if not r or not r[0]["a"]:
            return None
        d0, d1 = r[0]["a"], r[0]["b"]
        # psycopg rend des datetime natifs (tz-aware) pour un timestamptz —
        # contrairement à sqlite3 qui rend le TEXT ISO stocké tel quel.
        if isinstance(d0, str):
            d0 = datetime.fromisoformat(d0)
        if isinstance(d1, str):
            d1 = datetime.fromisoformat(d1)
        sec = (d1 - d0).total_seconds()
        n = r[0]["n"]
        return {"n": n, "sec": sec, "par_h": (n / sec * 3600) if sec > 0 else 0,
                "dernier": d1}


def runs_agents(limite: int = 7):
    p = os.path.join(ROOT, "agents", "ledger.db")
    if not os.path.exists(p):
        return []
    try:
        uri = "file:" + p.replace("\\", "/") + "?mode=ro"
        c = sqlite3.connect(uri, uri=True, timeout=2)
        c.row_factory = sqlite3.Row
        r = [dict(x) for x in c.execute(
            "select agent,status,started_at,ended_at from agent_runs "
            "order by id desc limit ?", (limite,))]
        c.close()
        return r
    except sqlite3.Error:
        return []


class Dashboard(tk.Tk):
    def __init__(self, db: str | None):
        super().__init__()
        self.title("LOWI BKK — supervision du scrap")
        self.configure(bg=BG)
        self.geometry("1920x1080")
        self.plein = False
        self.bases = bases_disponibles()
        if db:
            self.bases = [db] + [b for b in self.bases if b != db]
        self.idx = 0
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
        self.bind("s", lambda e: self.source_suivante())
        self.rafraichir()

    def bascule_plein(self):
        self.plein = not self.plein
        self.attributes("-fullscreen", self.plein)

    def source_suivante(self):
        if self.bases:
            self.idx = (self.idx + 1) % len(self.bases)
        self.rafraichir()

    # ── rendu ────────────────────────────────────────────────────────────
    def ecrire(self, texte: str, tag: str = "t"):
        self.zone.insert("end", texte, tag)

    def barre(self, n: int, total: int, largeur: int = 34) -> str:
        if total <= 0:
            return "░" * largeur
        plein = int(largeur * min(1.0, n / total))
        return "█" * plein + "░" * (largeur - plein)

    def rafraichir(self):
        self.zone.delete("1.0", "end")
        if not self.bases:
            self.ecrire("\n  Aucune base de scrap trouvée.\n", "warn")
            self.after(5000, self.rafraichir)
            return
        chemin = self.bases[self.idx]
        en_ligne = (chemin == SUPABASE)
        s = SourceSupabase(_supabase_dsn()) if en_ligne else Source(chemin)

        for ligne in BANNIERE:
            self.ecrire("  " + ligne + "\n", "banniere")
        maint = datetime.now().strftime("%d/%m %H:%M:%S")
        self.ecrire(f"  BANGKOK · supervision du scrap{' ' * 26}{maint}\n", "w")
        nom_source = "SUPABASE — PRODUCTION (en ligne)" if en_ligne \
            else os.path.basename(os.path.dirname(chemin))
        self.ecrire(f"  source : {nom_source}"
                    f"   [S] changer · {len(self.bases)} base(s)\n",
                    "ok" if en_ligne else "dim")
        self.ecrire("  " + "─" * 150 + "\n\n", "dim")

        # ── progression ──
        cad = s.cadence()
        total = s.total()
        self.ecrire("  ▐ PROGRESSION\n", "t")
        if cad and cad["sec"] > 0:
            ecoule = cad["sec"] / 3600
            frais = (datetime.now(timezone.utc) - cad["dernier"].replace(
                tzinfo=cad["dernier"].tzinfo or timezone.utc)).total_seconds()
            etat, tag = ("EN COURS", "ok") if frais < 300 else ("À L'ARRÊT", "warn")
            self.ecrire(f"    {total:>6d} annonces   {cad['par_h']:>5.0f}/h   "
                        f"écoulé {ecoule:>4.1f} h   ", "w")
            self.ecrire(f"[{etat}]\n", tag)
            self.ecrire(f"    dernière annonce il y a {frais / 60:.0f} min\n", "dim")
        else:
            self.ecrire(f"    {total} annonces\n", "w")

        for r in s.par_source():
            pc_d = 100 * r["d"] / r["n"] if r["n"] else 0
            pc_g = 100 * r["g"] / r["n"] if r["n"] else 0
            self.ecrire(f"    {r['source']:<14}{r['deal_type']:<6}{r['n']:>6d}  "
                        f"{self.barre(r['n'], max(1, total))}  "
                        f"desc {pc_d:>5.1f}%  géo {pc_g:>5.1f}%\n", "w")
        self.ecrire("\n")

        # ── chambres x khet, vente et location cote a cote ──
        # Positions CALCULEES : les espacements en dur se desalignaient des que
        # la largeur d'une colonne changeait.
        MARGE, GAP = 4, 6
        LARG = 24 + 5 + 5 + 5 + 6 + 7          # largeur d'un demi-tableau
        col1, col2 = MARGE, MARGE + LARG + GAP

        self.ecrire("  ▐ TYPOLOGIE PAR QUARTIER\n", "t")
        # Libelles CENTRES au-dessus de leur propre tableau
        def centre(txt: str, debut: int) -> int:
            return debut + max(0, (LARG - len(txt)) // 2)
        ligne = " " * centre("── VENTE ──", col1) + "── VENTE ──"
        ligne = ligne.ljust(centre("── LOCATION ──", col2)) + "── LOCATION ──"
        self.ecrire(ligne + "\n", "acc")

        v = s.chambres_par_khet("sale")
        l = s.chambres_par_khet("rent")
        entete = (f"{'quartier':<24}{'STU':>5}{'1BR':>5}{'2BR':>5}"
                  f"{'3BR+':>6}{'tot':>7}")
        self.ecrire(" " * col1 + entete + " " * GAP + entete + "\n", "dim")

        for i in range(max(len(v), len(l))):
            self.ecrire(" " * col1)          # meme marge que l'en-tete
            for col, tab in ((0, v), (1, l)):
                if i < len(tab):
                    r = tab[i]
                    nom = (r["khet"] or "?").replace(" District", "")[:23]
                    self.ecrire(f"{nom:<24}{r['st'] or 0:>5}{r['b1'] or 0:>5}"
                                f"{r['b2'] or 0:>5}{r['b3'] or 0:>6}{r['tot']:>7}",
                                "w" if col == 0 else "acc")
                else:
                    self.ecrire(" " * LARG)
                if col == 0:
                    self.ecrire(" " * GAP)
            self.ecrire("\n")
        self.ecrire("\n")

        # ── tranches de prix ──
        self.ecrire("  ▐ TRANCHES DE PRIX\n", "t")
        tv = s.tranches("sale", TRANCHES_VENTE)
        tl = s.tranches("rent", TRANCHES_LOYER)
        mv = max([x[2] for x in tv] or [1])
        ml = max([x[2] for x in tl] or [1])
        # Memes positions calculees que la typologie : largeur de bloc + ecart,
        # libelles centres au-dessus de LEUR bloc.
        LARG_P = 12 + 6 + 2 + 22        # tranche + effectif + barre
        GAP_P = 6
        p1, p2 = MARGE, MARGE + LARG_P + GAP_P
        t1, t2 = "── VENTE (THB) ──", "── LOCATION (THB/mois) ──"
        ligne = " " * (p1 + max(0, (LARG_P - len(t1)) // 2)) + t1
        ligne = ligne.ljust(p2 + max(0, (LARG_P - len(t2)) // 2)) + t2
        self.ecrire(ligne + "\n", "dim")
        for (lo, hi, n), (lo2, hi2, n2) in zip(tv, tl):
            e1 = f"{thb(lo)}–{thb(hi)}"
            e2 = f"{thb(lo2)}–{thb(hi2)}"
            self.ecrire(" " * p1 + f"{e1:<12}{n:>6}  {self.barre(n, mv, 22)}", "w")
            self.ecrire(" " * GAP_P + f"{e2:<12}{n2:>6}  {self.barre(n2, ml, 22)}\n", "acc")
        self.ecrire("\n")

        # ── agents ──
        self.ecrire("  ▐ AGENTS (ledger)\n", "t")
        for r in runs_agents():
            tag = {"ok": "ok", "running": "acc", "failed": "warn",
                   "interrompu": "warn"}.get(r["status"], "dim")
            fin = (r["ended_at"] or "")[11:19] or "……"
            self.ecrire(f"    {r['agent']:<24}{r['status']:<12}"
                        f"{r['started_at'][11:19]} → {fin}\n", tag)

        self.ecrire("\n  " + "─" * 150 + "\n", "dim")
        self.ecrire("  [F] plein écran   [R] rafraîchir   [S] source   [Q] quitter"
                    "        lecture seule — aucun impact sur le scrap\n", "dim")
        self.after(5000, self.rafraichir)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None, help="chemin d'une base précise")
    ap.add_argument("--plein", action="store_true", help="démarrer en plein écran")
    a = ap.parse_args()
    app = Dashboard(a.db)
    if a.plein:
        app.bascule_plein()
    app.mainloop()
