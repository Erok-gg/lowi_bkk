"""test_sitemap_lastmod_futur.py — un lastmod aberrant dans le futur ne fige pas la détection.

Le 2026-10-19, le sitemap FazWaz régénéré portait UNE entrée (u6802908) à
2026-11-22 : plus_frais() = max() restait dans le futur, regenere_depuis() faux
pour toujours (165 min d'attente par nuit, faux constat, mail « 0 annonce »).
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "scraper"))
from pipeline import sitemap  # noqa: E402

ANCIEN = [{"url": "a", "lastmod": "2026-10-14T01:30:43+07:00"}]
NOUVEAU = [{"url": "a", "lastmod": "2026-10-19T03:42:31+07:00"},
           {"url": "b", "lastmod": "2026-11-22T00:00:00+07:00"}]      # anomalie du site


def test_futur_ignore():
    assert sitemap.plus_frais(NOUVEAU).isoformat().startswith("2026-10-19")


def test_regeneration_detectee_malgre_lanomalie():
    assert sitemap.regenere_depuis(ANCIEN, NOUVEAU)
    assert not sitemap.regenere_depuis(NOUVEAU, NOUVEAU)    # même sitemap relu : toujours « figé »


if __name__ == "__main__":
    test_futur_ignore(); test_regeneration_detectee_malgre_lanomalie()
    print("OK — test_sitemap_lastmod_futur : 2/2")
