"""test_watch_health_mail_zero.py — un extracteur à 0 annonce = mail direct.

POURQUOI : FazWaz a ramené 0 nouvelle annonce les nuits des 16, 17 et 18/10/2026
(médiane ~280) ; le constat `sitemap_non_regenere` passait en sévérité haute mais
aucun mail ne partait (seul `parseur_casse` alertait, au 2e run). Règle posée par
l'utilisateur le 2026-10-19 : 0 annonce → mail, sans condition de cause.

Vérifie : (1) 0 nouvelle → un mail dans la boîte, quelle que soit la cause ;
(2) des nouvelles → aucun mail (le garde-fou se tait quand tout va bien, règle 2) ;
(3) `parseur_casse` au 2e run → UN seul mail, pas deux.

Rejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_watch_health_mail_zero.py
"""
import json
import os
import sys
import tempfile

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RACINE)

from agents.bots import watch_health as wh                    # noqa: E402


def _run(nouvelles_courantes, log_texte, zeros_precedents=0):
    with tempfile.TemporaryDirectory() as tmp:
        log = os.path.join(tmp, "x.log")
        open(log, "w", encoding="utf-8").write(log_texte)
        boite = os.path.join(tmp, "mail")
        wh.alert.MAILBOX = boite
        wh.alert.AUDITS = os.path.join(tmp, "audits")
        wh.alert.CHANGELOG = os.path.join(wh.alert.AUDITS, "CHANGELOG.md")
        wh.local_llm.ask_safe = lambda *a, **k: None
        wh.escalation.create = lambda **k: "t"

        def ligne(n):
            return {"id": 1, "log_path": log, "metrics": json.dumps(
                {"nouvelles": n, "traces_erreur": 0, "erreurs_images": 0})}

        courant = ligne(nouvelles_courantes)
        recents = [courant] + [ligne(0)] * zeros_precedents + [ligne(200)] * 5

        class Led:
            def last_run(self, name, only_ok=True): return courant
            def recent_runs(self, name, n): return recents[:n]
            def finding(self, *a, **k): pass

        wh.EXTRACTEURS = [{"name": "extract-fazwaz"}]
        wh.run(Led(), 1, "daily", {})
        return sorted(os.listdir(boite)) if os.path.isdir(boite) else []


def test_zero_sitemap_fige_envoie_un_mail():
    assert len(_run(0, "[sitemap-non-regenere] plus frais lastmod toujours")) == 1


def test_zero_sans_cause_envoie_un_mail():
    assert len(_run(0, "rien de particulier")) == 1


def test_des_nouvelles_pas_de_mail():
    assert _run(150, "RAS") == []


def test_parseur_casse_deuxieme_run_un_seul_mail():
    assert len(_run(0, "RAS", zeros_precedents=1)) == 1


if __name__ == "__main__":
    test_zero_sitemap_fige_envoie_un_mail()
    test_zero_sans_cause_envoie_un_mail()
    test_des_nouvelles_pas_de_mail()
    test_parseur_casse_deuxieme_run_un_seul_mail()
    print("OK — test_watch_health_mail_zero : 4/4")
