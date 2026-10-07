"""Fenêtre de maintenance : le cycle s'abstient, les surveillances se taisent,
nRejeu :  scraper/.venv/Scripts/python.exe agents/tests/test_maintenance.py
et un fichier absent/illisible ne suspend RIEN (mieux vaut une fausse alerte
qu'un cycle sauté en silence)."""
import json
from datetime import datetime, timedelta, timezone

import sys
from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parents[2]))
from agents.core import maintenance  # noqa: E402

BKK = timezone(timedelta(hours=7))


def _ecrit(tmp_path, **d):
    p = tmp_path / "maintenance.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    return p


def test_dans_la_fenetre(tmp_path):
    p = _ecrit(tmp_path, debut="2026-10-08T00:00:00+07:00",
               fin="2026-10-09T00:00:00+07:00", motif="test")
    assert maintenance.active(datetime(2026, 10, 8, 2, 30, tzinfo=BKK), p)


def test_hors_fenetre(tmp_path):
    p = _ecrit(tmp_path, debut="2026-10-08T00:00:00+07:00",
               fin="2026-10-09T00:00:00+07:00", motif="test")
    assert maintenance.active(datetime(2026, 10, 7, 23, 59, tzinfo=BKK), p) is None
    assert maintenance.active(datetime(2026, 10, 9, 2, 30, tzinfo=BKK), p) is None


def test_fichier_absent_ou_casse(tmp_path):
    assert maintenance.active(chemin=tmp_path / "absent.json") is None
    p = tmp_path / "m.json"
    p.write_text("{pas du json", encoding="utf-8")
    assert maintenance.active(chemin=p) is None


def test_dates_sans_fuseau_refusees(tmp_path):
    p = _ecrit(tmp_path, debut="2026-10-08T00:00:00", fin="2026-10-09T00:00:00")
    assert maintenance.fenetre(p) is None


if __name__ == "__main__":
    import tempfile
    from pathlib import Path
    for nom, f in list(globals().items()):
        if nom.startswith("test_"):
            with tempfile.TemporaryDirectory() as d:
                f(Path(d))
            print(f"ok  {nom}")
