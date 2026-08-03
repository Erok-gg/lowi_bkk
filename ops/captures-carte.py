"""captures-carte.py — série d'images DATÉES des cartes, une par édition mensuelle.

POURQUOI. L'évolution du marché ne se lit aujourd'hui qu'en tableaux. Or ce que
les colonnes ne montrent pas, c'est le DÉPLACEMENT GÉOGRAPHIQUE : une tension qui
migre d'un quartier à l'autre, un couloir de rendement qui s'étend. Une série
d'images datées le rend visible d'un coup d'œil.

Et ce n'est pas théorique : c'est en REGARDANT une capture du tableau des
rendements, le 2026-08-03, qu'on a vu « Bang Na » y figurer deux fois. Aucune
requête ne l'avait signalé. L'anomalie a mené à un défaut réel — le classement
n'était pas restreint aux 50 quartiers de Bangkok et incluait des annonces de
Samut Prakan.

ON ATTEND QUE LA CARTE LE DISE ELLE-MÊME.
MapLibre est en WebGL, et une capture prise trop tôt rend un cadre VIDE sans la
moindre erreur : en-tête et panneau de calques dessinés, carte noire. Première
tentative avec Chrome en ligne de commande : `--virtual-time-budget` fait avancer
une horloge VIRTUELLE qui dépasse les téléchargements réels — cadre vide à tous
les budgets essayés, et rien du tout au-delà de 45 s.

Playwright permet d'attendre l'événement `idle` que MapLibre émet quand il a fini
de dessiner. C'est un signal ÉMIS PAR LA CARTE, pas une temporisation devinée —
et c'est lui, pas la taille du fichier, qui atteste la capture.

⚠ La leçon du 2026-08-03 : le garde-fou précédent jugeait sur le POIDS du PNG
(> 25 Ko). Il a laissé passer une carte entièrement noire de 43 Ko, que seul un
examen visuel a démasquée. Un seuil de taille ne remplace pas un signal. Le poids
reste vérifié, mais en second — jamais seul.

NAVIGATEUR : le Chrome du système (`channel="chrome"`), donc aucun téléchargement.
AUTHENTIFICATION : aucune. Sans `BASIC_AUTH_PASSWORD`, `lib/auth.ts` laisse
l'accès ouvert en local.

Usage :
    python ops/captures-carte.py                    # mois courant
    python ops/captures-carte.py --mois 2026-08
    python ops/captures-carte.py --url http://localhost:3000
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: (nom de fichier, chemin, la vue porte-t-elle une carte ?)
VUES = (
    ("carte-generale", "/", True),
    ("rendements-carte", "/yields-map", True),
    ("tension-carte", "/tension", True),
    ("rendements-tableau", "/rendements", False),
    ("tension-tableau", "/tension-table", False),
)

LARGEUR, HAUTEUR = 1920, 1080

#: Au-delà, on considère que la carte ne viendra pas. Généreux à dessein : mieux
#: vaut une capture lente qu'une image trompeuse.
ATTENTE_CARTE_MS = 60_000

#: Plancher de vraisemblance, en SECOND rideau. Une carte rendue pèse ~1 Mo,
#: un cadre vide ~40 Ko.
POIDS_MIN_CARTE = 200_000
POIDS_MIN_TABLEAU = 40_000

#: Attendu par la carte pour se déclarer prête. Renvoie la raison, pas un booléen :
#: « delai_depasse » et « pas_de_carte » sont deux pannes différentes.
_ATTENDRE_IDLE = """() => new Promise(res => {
    const m = window.__map;
    if (!m) return res('pas_de_carte');
    if (m.loaded()) return res('deja_prete');
    const t = setTimeout(() => res('delai_depasse'), %d);
    m.once('idle', () => { clearTimeout(t); res('idle'); });
})""" % ATTENTE_CARTE_MS


def capturer(page, url: str, sortie: str, carte: bool) -> tuple[bool, str]:
    page.goto(url, wait_until="networkidle", timeout=90_000)
    etat = "—"
    if carte:
        etat = page.evaluate(_ATTENDRE_IDLE)
        if etat not in ("idle", "deja_prete"):
            return False, f"carte non rendue ({etat})"
        page.wait_for_timeout(2000)      # laisser le dernier cadre se composer
    else:
        page.wait_for_timeout(1500)

    page.screenshot(path=sortie)
    poids = os.path.getsize(sortie) if os.path.exists(sortie) else 0
    mini = POIDS_MIN_CARTE if carte else POIDS_MIN_TABLEAU
    if poids < mini:
        return False, f"{poids // 1024} Ko — sous le plancher ({mini // 1024} Ko)"
    return True, f"{etat}, {poids // 1024} Ko"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mois", default=date.today().strftime("%Y-%m"))
    ap.add_argument("--url", default="http://localhost:3000")
    a = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright absent — pip install playwright")
        return 2

    dossier = os.path.join(ROOT, "docs", "etudes", "captures", a.mois)
    os.makedirs(dossier, exist_ok=True)
    print(f"sortie : {dossier}\n")

    ok = 0
    with sync_playwright() as p:
        nav = p.chromium.launch(channel="chrome", headless=True,
                                args=["--enable-unsafe-swiftshader"])
        page = nav.new_page(viewport={"width": LARGEUR, "height": HAUTEUR},
                            device_scale_factor=1)
        for nom, chemin, carte in VUES:
            cible = os.path.join(dossier, f"{nom}.png")
            try:
                bon, detail = capturer(page, a.url.rstrip("/") + chemin, cible, carte)
            except Exception as e:                        # noqa: BLE001
                bon, detail = False, f"{type(e).__name__}: {str(e)[:70]}"
            print(f"  {'OK   ' if bon else 'ECHEC'} {nom:20s} {chemin:16s} {detail}")
            ok += bon
            # Ne JAMAIS laisser une image trompeuse dans la série : une capture
            # ratée qui reste sur le disque sera lue l'an prochain comme un fait.
            if not bon and os.path.exists(cible):
                os.remove(cible)
        nav.close()

    print(f"\n{ok}/{len(VUES)} captures retenues")
    return 0 if ok == len(VUES) else 1


if __name__ == "__main__":
    sys.exit(main())
