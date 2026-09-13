"""Tests del exportador Kaggle (offline, contra docs/v1 generado)."""
import csv
import json
from pathlib import Path

from fpc_api import export_kaggle as ex

V1 = Path(__file__).resolve().parents[1] / "docs" / "v1"


def _json_seasons():
    out = []
    for f in sorted((V1 / "seasons").glob("*.json")):
        out.append(json.loads(f.read_text(encoding="utf-8")))
    return out


def test_counts_match_source():
    seasons = _json_seasons()
    assert len(ex.export_seasons()[2]) == len(seasons)
    assert len(ex.export_matches()[2]) == sum(len(d["matches"]) for d in seasons)
    assert len(ex.export_standings()[2]) == sum(len(d["standings"]) for d in seasons)
    assert len(ex.export_groups()[2]) == sum(len(d.get("groups", [])) and sum(len(g["standings"]) for g in d["groups"]) for d in seasons)
    assert len(ex.export_individuals("scorers")[2]) == sum(len(d.get("scorers", [])) for d in seasons)
    assert len(ex.export_individuals("assists")[2]) == sum(len(d.get("assists", [])) for d in seasons)
    assert len(ex.export_teams()[2]) == len(json.loads((V1 / "teams.json").read_text())["teams"])
    assert len(ex.export_players()[2]) == len(json.loads((V1 / "players.json").read_text())["players"])
    assert len(ex.export_champions()[2]) == len(json.loads((V1 / "champions.json").read_text())["champions"])


def test_matches_schema_and_penalties():
    _, header, rows = ex.export_matches()
    assert header[0] == "id" and "penalties_home" in header
    by_id = {r["id"]: r for r in rows}
    assert len(by_id) == len(rows)
    assert all(r["home"] and r["away"] and r["season"] and r["status"] in ("played", "scheduled") for r in rows)
    # semifinal Apertura 2026 definida por penales 5-4
    pen = [r for r in rows if r["penalties_home"] not in ("", None)]
    assert pen, "se esperaba al menos un partido con penales"
    assert all(set(r.keys()) == set(header) for r in rows)


def test_csv_roundtrip(tmp_path=None):
    import tempfile

    _, header, rows = ex.export_champions()
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "champions.csv"
        assert ex._write_csv(p, header, rows) == len(rows)
        back = list(csv.DictReader(p.open(encoding="utf-8")))
        assert len(back) == len(rows)
        assert back[0]["season_id"] == "1948"
        assert back[-1]["season_id"] == "2026-i"
        # UTF-8 intacto
        assert any("é" in r["champion_name"] or "í" in r["champion_name"] for r in back)


def test_str_helper():
    assert ex._str(None) == ""
    assert ex._str(True) == "true"
    assert ex._str(82.5) == "82.5"
    assert ex._str("Nacional") == "Nacional"
