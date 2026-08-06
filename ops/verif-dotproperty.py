"""verif-dotproperty.py — vérifie sur 3 runs espacés l'hypothèse de
resyndication FazWaz avant de trancher le ticket watch-sources.

CONTEXTE (voir agents/state/watch-sources/registre.json, entrée dotproperty,
et docs/journal-technique.md 2026-08-05/06). Un échantillonnage manuel a
trouvé 90/90 annonces chargeant leurs photos depuis cdn.fazwaz.com /
img.fazwaz.com. Ce script automatise la même vérification, répétée sur 3
cycles espacés (pas un seul run — un site pourrait mélanger agences FazWaz et
agences propres selon le moment), et écrit une conclusion.

N'utilise PAS run.py (pas de store, pas d'images, pas d'écriture DB) : on ne
veut compter que les hébergeurs d'images des pages de LISTE, rien de plus —
scraper/adapters/dotproperty.py expose déjà tout (prix, adresse, image) sans
visiter de fiche détail.

Après le 3e run : décide, met à jour le registre, ferme ou laisse ouvert le
ticket, et dépose une demande de mail (agents/core/alert) avec la conclusion.
Auto-limité : au-delà de 3 runs, ce script ne fait plus rien (idempotent) tant
que quelqu'un ne réinitialise pas l'état à la main.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scraper"))
sys.path.insert(0, ROOT)

from adapters.dotproperty import DotpropertyAdapter          # noqa: E402
from pipeline.fetch import Fetcher                             # noqa: E402
from agents.core import alert                                  # noqa: E402

ETAT_DIR = os.path.join(ROOT, "agents", "state", "verif-dotproperty")
ETAT_PATH = os.path.join(ETAT_DIR, "etat.json")
REGISTRE_PATH = os.path.join(ROOT, "agents", "state", "watch-sources", "registre.json")
TICKET_PATH = os.path.join(
    ROOT, "agents", "queue", "2026-08-01T030748-watch-sources-nouvelle_source.json")

N_RUNS_CIBLE = 3
SEUIL_CONCLUANT = 0.90     # >=90% des images chez FazWaz sur CHAQUE run -> conclusion nette
HOTES_FAZWAZ = ("cdn.fazwaz.com", "img.fazwaz.com")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _charger_etat() -> dict:
    if os.path.exists(ETAT_PATH):
        try:
            return json.load(open(ETAT_PATH, encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"runs": []}


def _sauver_etat(etat: dict) -> None:
    os.makedirs(ETAT_DIR, exist_ok=True)
    tmp = ETAT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(etat, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ETAT_PATH)


def sonder(limit: int = 60) -> dict:
    """Un run : échantillonne des annonces via la page de LISTE uniquement
    (list_urls donne déjà l'image, pas besoin de parse_listing/fiche détail),
    compte les hébergeurs d'images."""
    cfg = json.load(open(os.path.join(ROOT, "scraper", "config", "dotproperty.json"),
                        encoding="utf-8"))
    adapter = DotpropertyAdapter(cfg)
    fetcher = Fetcher(base_url=cfg["base_url"], user_agent=cfg["user_agent"],
                      rate_limit_seconds=cfg["rate_limit_seconds"],
                      timeout_seconds=cfg.get("timeout_seconds", 30),
                      respect_robots=cfg.get("respect_robots", True))

    n_total = n_fazwaz = n_sans_image = 0
    autres_hotes: dict[str, int] = {}
    for stub in adapter.list_urls(fetcher, limit=limit):
        imgs = stub.get("image_urls") or []
        n_total += 1
        if not imgs:
            n_sans_image += 1
            continue
        hote = urlparse(imgs[0]).hostname or ""
        if hote in HOTES_FAZWAZ:
            n_fazwaz += 1
        else:
            autres_hotes[hote] = autres_hotes.get(hote, 0) + 1

    pct = (n_fazwaz / n_total) if n_total else None
    return {
        "date": _now(), "n_total": n_total, "n_fazwaz": n_fazwaz,
        "n_sans_image": n_sans_image, "autres_hotes": autres_hotes,
        "pct_fazwaz": pct,
    }


def _maj_registre(verdict: str, note: str) -> None:
    if not os.path.exists(REGISTRE_PATH):
        return
    reg = json.load(open(REGISTRE_PATH, encoding="utf-8"))
    for r in reg.get("dernier_sondage", []):
        if r.get("nom") == "dotproperty":
            r["verdict_verification_3_runs"] = verdict
            r["note_verification_3_runs"] = note
            r["verification_terminee_le"] = _now()
    json.dump(reg, open(REGISTRE_PATH, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


def _maj_ticket(verdict: str, note: str) -> None:
    if not os.path.exists(TICKET_PATH):
        return
    t = json.load(open(TICKET_PATH, encoding="utf-8"))
    t["verification_3_runs"] = {"verdict": verdict, "note": note, "termine_le": _now()}
    json.dump(t, open(TICKET_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if verdict == "resyndication_confirmee":
        # Ticket tranché : on le deplace dans done/ nous-memes (pas de decision
        # produit restante, juste une hypothese qu'on avait promis de verifier).
        done_dir = os.path.join(ROOT, "agents", "queue", "done")
        os.makedirs(done_dir, exist_ok=True)
        os.replace(TICKET_PATH, os.path.join(done_dir, os.path.basename(TICKET_PATH)))


def run(led=None, run_id=None, lane=None, spec=None) -> dict:
    """Signature compatible agent T0-comme-module si jamais on le bascule en
    'module' plus tard ; utilisable aussi en script direct (cf. __main__)."""
    etat = _charger_etat()
    if len(etat["runs"]) >= N_RUNS_CIBLE:
        return {"statut": "deja_conclu", "n_runs": len(etat["runs"])}

    resultat = sonder()
    etat["runs"].append(resultat)
    _sauver_etat(etat)

    sortie = {"statut": "run_enregistre", "n_runs": len(etat["runs"]),
              "pct_fazwaz_ce_run": resultat["pct_fazwaz"]}

    if len(etat["runs"]) < N_RUNS_CIBLE:
        return sortie

    # 3e run : conclusion.
    pcts = [r["pct_fazwaz"] for r in etat["runs"] if r["pct_fazwaz"] is not None]
    tous_concluants = all(p >= SEUIL_CONCLUANT for p in pcts) if pcts else False
    aucun_concluant = all(p < 0.20 for p in pcts) if pcts else False

    lignes = "\n".join(
        f"  run {i+1} ({r['date']}) : {r['n_fazwaz']}/{r['n_total']} FazWaz"
        f" ({r['pct_fazwaz']:.0%})" + (f", autres hotes : {r['autres_hotes']}"
                                       if r["autres_hotes"] else "")
        for i, r in enumerate(etat["runs"]))

    if tous_concluants:
        verdict = "resyndication_confirmee"
        note = (f"3 runs independants, tous >={SEUIL_CONCLUANT:.0%} des images "
               f"chez FazWaz. Hypothese confirmee, ticket ferme.\n{lignes}")
    elif aucun_concluant:
        verdict = "resyndication_infirmee"
        note = (f"3 runs independants, tous <20% des images chez FazWaz — "
               f"l'echantillon manuel du 2026-08-05 (90/90) n'etait pas "
               f"representatif. A reconsiderer comme source independante.\n{lignes}")
    else:
        verdict = "resultats_mixtes"
        note = (f"3 runs independants aux resultats incoherents entre eux — "
               f"pas de conclusion nette, decision a prendre par Anthony.\n{lignes}")

    _maj_registre(verdict, note)
    _maj_ticket(verdict, note)
    alert.alert(
        "verif-dotproperty",
        f"DotProperty : verification 3 runs terminee ({verdict})",
        f"Verdict : {verdict}\n\n{note}\n\n"
        f"Details : agents/state/verif-dotproperty/etat.json\n"
        f"Registre : agents/state/watch-sources/registre.json (entree dotproperty)",
        severity="high" if verdict != "resultats_mixtes" else "medium")

    sortie["statut"] = "conclu"
    sortie["verdict"] = verdict
    return sortie


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
