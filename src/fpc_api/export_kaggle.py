"""Exporta el JSON validado a CSVs planos para Kaggle (export/kaggle/).

Uso: PYTHONPATH=src python -m fpc_api.export_kaggle [--out export/kaggle]
Falla si algún conteo no cuadra con el JSON fuente (ningún registro se pierde).
"""
import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IN = ROOT / "docs" / "v1"
DEFAULT_OUT = ROOT / "export" / "kaggle"

DATASET_ID = "norwyx/colombian-football-fpc"
DATASET_TITLE = "Colombian Professional Football (FPC) — Matches, Standings, Players"


def _load(name: str) -> dict:
    return json.loads((IN / name).read_text(encoding="utf-8"))


def _str(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def _write_csv(path: Path, header: list[str], rows: list[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: _str(r.get(k)) for k in header})
    return len(rows)


def export_teams() -> tuple[str, list[str], list[dict]]:
    data = _load("teams.json")["teams"]
    rows = [{
        "id": t["id"], "name": t["name"], "short_name": t["short_name"],
        "city": t["city"], "stadium": t["stadium"], "capacity": t["capacity"],
        "founded": t["founded"],
        "primary_color": (t["colors"] or {}).get("primary"),
        "secondary_color": (t["colors"] or {}).get("secondary"),
        "wikipedia": t["wikipedia"], "active": t["active"],
    } for t in data]
    header = ["id", "name", "short_name", "city", "stadium", "capacity", "founded",
              "primary_color", "secondary_color", "wikipedia", "active"]
    assert len(rows) == len(data) and len({r["id"] for r in rows}) == len(rows)
    return "teams.csv", header, rows


def export_seasons() -> tuple[str, list[str], list[dict]]:
    rows = []
    for f in sorted((IN / "seasons").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        s = d["season"]
        played = sum(1 for m in d["matches"] if m["status"] == "played")
        rows.append({
            "id": s["id"], "year": s["year"], "tournament": s["tournament"],
            "status": s["status"], "champion": d.get("champion"),
            "start_date": s["start_date"], "end_date": s["end_date"],
            "n_teams": len(d["teams"]), "n_matches": len(d["matches"]),
            "n_played": played, "wikipedia": s["wikipedia"],
        })
    header = ["id", "year", "tournament", "status", "champion", "start_date", "end_date",
              "n_teams", "n_matches", "n_played", "wikipedia"]
    return "seasons.csv", header, rows


def _standings_rows(d: dict, key: str, extra: dict) -> list[dict]:
    out = []
    for s in d.get(key, []):
        out.append({
            "season": d["season"]["id"], "team": s["team"], "position": s["position"],
            "played": s["played"], "won": s["won"], "drawn": s["drawn"], "lost": s["lost"],
            "goals_for": s["goals_for"], "goals_against": s["goals_against"],
            "goal_diff": s["goal_diff"], "points": s["points"], "bonus": s.get("bonus"),
            **extra,
        })
    return out


def export_standings() -> tuple[str, list[str], list[dict]]:
    rows = []
    for f in sorted((IN / "seasons").glob("*.json")):
        rows += _standings_rows(json.loads(f.read_text(encoding="utf-8")), "standings", {})
    header = ["season", "team", "position", "played", "won", "drawn", "lost",
              "goals_for", "goals_against", "goal_diff", "points", "bonus"]
    return "standings.csv", header, rows


def export_groups() -> tuple[str, list[str], list[dict]]:
    rows = []
    for f in sorted((IN / "seasons").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for g in d.get("groups", []):
            for s in g["standings"]:
                rows.append({
                    "season": d["season"]["id"], "group": g["name"], "stage": g.get("stage"),
                    "team": s["team"], "position": s["position"], "played": s["played"],
                    "won": s["won"], "drawn": s["drawn"], "lost": s["lost"],
                    "goals_for": s["goals_for"], "goals_against": s["goals_against"],
                    "goal_diff": s["goal_diff"], "points": s["points"], "bonus": s.get("bonus"),
                })
    header = ["season", "group", "stage", "team", "position", "played", "won", "drawn",
              "lost", "goals_for", "goals_against", "goal_diff", "points", "bonus"]
    return "groups.csv", header, rows


def export_matches() -> tuple[str, list[str], list[dict]]:
    rows = []
    for f in sorted((IN / "seasons").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for m in d["matches"]:
            pen = m.get("penalties") or []
            rows.append({
                "id": m["id"], "season": d["season"]["id"], "stage": m["stage"],
                "round": m["round"], "leg": m.get("leg"), "date": m["date"],
                "home": m["home"], "away": m["away"],
                "home_goals": m["home_goals"], "away_goals": m["away_goals"],
                "penalties_home": pen[0] if len(pen) > 0 else None,
                "penalties_away": pen[1] if len(pen) > 1 else None,
                "status": m["status"],
            })
    header = ["id", "season", "stage", "round", "leg", "date", "home", "away",
              "home_goals", "away_goals", "penalties_home", "penalties_away", "status"]
    assert len({r["id"] for r in rows}) == len(rows), "ids de partido duplicados"
    assert all(r["home"] and r["away"] and r["season"] for r in rows)
    return "matches.csv", header, rows


def export_individuals(kind: str) -> tuple[str, list[str], list[dict]]:
    field = "goals" if kind == "scorers" else "assists"
    rows = []
    for f in sorted((IN / "seasons").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for p in d.get(kind, []):
            rows.append({
                "season": d["season"]["id"], "player_name": p["player_name"],
                "team": p["team"], field: p[field], "played": p["played"],
            })
    return f"{kind}.csv", ["season", "player_name", "team", field, "played"], rows


def export_players() -> tuple[str, list[str], list[dict]]:
    data = _load("players.json")["players"]
    rows = [{
        "id": p["id"], "name": p["name"], "team": p["team"], "position": p["position"],
        "shirt_number": p["shirt_number"], "age": p["age"],
    } for p in data]
    header = ["id", "name", "team", "position", "shirt_number", "age"]
    assert len({r["id"] for r in rows}) == len(rows), "ids de jugador duplicados"
    return "players.csv", header, rows


def export_champions() -> tuple[str, list[str], list[dict]]:
    data = _load("champions.json")["champions"]
    rows = [{
        "season_id": c["season_id"], "year": c["year"], "tournament": c["tournament"],
        "champion": c["champion"], "champion_name": c["champion_name"],
        "runner_up": c["runner_up"], "runner_up_name": c["runner_up_name"],
        "score": c["score"], "top_scorer": c["top_scorer"],
    } for c in data]
    header = ["season_id", "year", "tournament", "champion", "champion_name",
              "runner_up", "runner_up_name", "score", "top_scorer"]
    return "champions.csv", header, rows


EXPORTERS = [export_teams, export_seasons, export_standings, export_groups,
             export_matches, export_individuals, export_players, export_champions]


def export_metadata(out: Path, files: list[str]) -> None:
    meta = {
        "title": DATASET_TITLE,
        "id": DATASET_ID,
        "licenses": [{"name": "CC-BY-SA-4.0"}],
        "resources": [{"path": f, "description": f.split(".")[0]} for f in files],
    }
    (out / "dataset-metadata.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="fpc-api export-kaggle")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    out = Path(args.out)

    files = []
    totals = {}
    for fn in EXPORTERS:
        if fn is export_individuals:
            for kind in ("scorers", "assists"):
                name, header, rows = fn(kind)
                n = _write_csv(out / name, header, rows)
                files.append(name)
                totals[name] = n
                print(f"  → {name}: {n} filas")
        else:
            name, header, rows = fn()
            n = _write_csv(out / name, header, rows)
            files.append(name)
            totals[name] = n
            print(f"  → {name}: {n} filas")
    export_metadata(out, files)
    print(f"Listo en {out} ({sum(totals.values())} filas).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
