"""CLI de build: python -m fpc_api.build [all|teams|champions|seasons|players|index]"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "v1"

# Alcance inicial de temporadas (backfill progresivo: añadir años aquí)
SEASON_RANGE = [(2024, "apertura"), (2024, "finalizacion"),
                (2025, "apertura"), (2025, "finalizacion"),
                (2026, "apertura"), (2026, "finalizacion")]


def _write(rel: str, data: dict):
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"  → {path.relative_to(ROOT)}")


def build_teams():
    from . import teams

    print("Equipos…")
    data = teams.build()
    _write("teams.json", data)
    return data


def build_champions():
    from . import champions

    print("Campeones…")
    data = champions.build()
    _write("champions.json", data)
    return data


def build_seasons(years=None):
    from . import seasons

    data_by_id = {}
    plan = ([(y, t) for y, t in SEASON_RANGE if y in years] if years else SEASON_RANGE)
    for year, torneo in plan:
        sid = seasons.season_id(year, torneo)
        print(f"Temporada {sid}…")
        try:
            data = seasons.build_season(year, torneo)
        except Exception as e:  # una temporada que falla no tumba el resto
            print(f"  ⚠ {sid}: {e}", file=sys.stderr)
            continue
        data_by_id[sid] = data
        _write(f"seasons/{sid}.json", data)
    return data_by_id


def build_players(teams_data=None):
    from . import players

    print("Plantillas…")
    if teams_data is None:
        path = OUT / "teams.json"
        teams_data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else build_teams()
    pages = {t["id"]: (t["wikipedia"] or "").rsplit("/wiki/", 1)[-1].replace("_", " ")
             for t in teams_data["teams"] if t["active"]}
    data = players.build(pages)
    _write("players.json", data)
    if data["meta"]["warnings"]:
        for warn in data["meta"]["warnings"]:
            print(f"  ⚠ {warn}", file=sys.stderr)
    return data


def build_index(seasons_data=None):
    print("Índice…")
    seasons_list = []
    seasons_dir = OUT / "seasons"
    if seasons_dir.exists():
        for f in sorted(seasons_dir.glob("*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            seasons_list.append({
                "id": data["season"]["id"],
                "year": data["season"]["year"],
                "tournament": data["season"]["tournament"],
                "status": data["season"]["status"],
                "champion": data.get("champion"),
                "n_matches": len(data.get("matches", [])),
                "url": f"/v1/seasons/{data['season']['id']}.json",
            })
    idx = {
        "meta": {
            "version": 1,
            "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "name": "FPC API",
            "description": "API pública de datos del fútbol profesional colombiano (Categoría Primera A)",
            "license": "MIT (código) · CC BY-SA 4.0 (datos, de Wikipedia)",
        },
        "endpoints": [
            {"path": "/v1/teams.json", "description": "Clubes de Primera A (activos e históricos)"},
            {"path": "/v1/players.json", "description": "Plantillas actuales (best-effort)"},
            {"path": "/v1/champions.json", "description": "Campeones 1948–hoy"},
            {"path": "/v1/seasons.json", "description": "Índice de temporadas"},
            {"path": "/v1/seasons/{year}-{i|ii}.json",
             "description": "Temporada: standings, partidos, goleadores, asistencias"},
        ],
        "seasons": seasons_list,
    }
    _write("index.json", idx)
    _write("seasons.json", {"meta": idx["meta"], "seasons": seasons_list})
    return idx


def main(argv=None):
    parser = argparse.ArgumentParser(prog="fpc-api build")
    parser.add_argument("target", choices=["all", "teams", "champions", "seasons", "players", "index"])
    parser.add_argument("--years", type=int, nargs="*", default=None,
                        help="años a construir (con 'seasons')")
    parser.add_argument("--max-age-days", type=float, default=None,
                        help="forzar re-descarga si la caché es más vieja que esto")
    args = parser.parse_args(argv)

    if args.max_age_days is not None:
        import fpc_api.http as http

        orig = http.get

        def get_limited(url, cache_key=None, max_age_days=7.0):
            return orig(url, cache_key, min(max_age_days, args.max_age_days))

        http.get = get_limited

    if args.target in ("all", "teams"):
        teams_data = build_teams()
    else:
        teams_data = None
    if args.target in ("all", "champions"):
        build_champions()
    if args.target in ("all", "seasons"):
        seasons_data = build_seasons(args.years)
    else:
        seasons_data = None
    if args.target in ("all", "players"):
        build_players(teams_data)
    if args.target in ("all", "index"):
        build_index()
    print("Listo.")


if __name__ == "__main__":
    main()
