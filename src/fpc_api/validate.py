"""Validación de datos generados: los datos NO se publican si no cuadran."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "v1"

# Inconsistencias aritméticas VERIFICADAS de la fuente (Wikipedia). Se publican
# tal cual (nunca se inventan datos) y se documentan aquí en vez de bloquear el build.
# Puntos: 2011-ii quindio (22 vs 3*7+4=25); 1995-96 santafe (50 vs 54);
#   1995 cortulua (35 vs 37); 1998 magdalena (50 vs 51).
# PJ: 1993 cucuta (44 vs 12+11+18=41).
# Sumas ΣGF!=ΣGC con plantillas completas y filas consistentes (typos de fuente):
#   1952 (+62), 1954 (+3), 1956 (+15), 1958 (+33), 1971 (+24), 1981 (+2),
#   1993 (-7), 1998 (+2), 2020 (+1: GC de Pasto 20 vs 19 en partidos).
KNOWN_POINTS_ISSUES = {("2011-ii", "quindio"), ("1995-96", "santafe"),
                       ("1995", "cortulua"), ("1998", "magdalena"),
                       # 1996-97: bonus de fase embebidos en Pts (solo top con bonus; resto exacto)
                       ("1996-97", "america"), ("1996-97", "nacional"),
                       ("1996-97", "cali"), ("1996-97", "junior")}
KNOWN_PJ_ISSUES = {("1993", "cucuta")}
KNOWN_SUMS_ISSUES = {"2020", "1952", "1954", "1956", "1958", "1971", "1981", "1993", "1998"}


class Warnings:
    def __init__(self):
        self.items: list[str] = []

    def warn(self, msg: str):
        self.items.append(msg)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_teams(data: dict, w: Warnings) -> list[str]:
    errors = []
    teams = data.get("teams", [])
    ids = [t["id"] for t in teams]
    if len(ids) != len(set(ids)):
        errors.append("teams: ids duplicados")
    active = [t for t in teams if t["active"]]
    if len(active) != 20:
        w.warn(f"teams: {len(active)} equipos activos (esperados 20)")
    for t in teams:
        if not re.fullmatch(r"[a-z0-9-]+", t["id"]):
            errors.append(f"teams: id inválido {t['id']!r}")
        if not t.get("name"):
            errors.append(f"teams: {t['id']} sin nombre")
    return errors


def validate_season(data: dict, w: Warnings) -> list[str]:
    errors = []
    sid = data["season"]["id"]
    standings = data.get("standings", [])
    matches = data.get("matches", [])
    teams = set(data.get("teams", []))

    if len(standings) not in (0, 8, 10, 12, 13, 14, 15, 16, 18, 19, 20):
        # 13/15/19 son conteos legítimos de varias eras (1963-65, 1952/1988/1990-91, 2021-i);
        # filas caídas las atrapa el chequeo duro standings-vs-partidos de abajo
        # 19 es legítimo en 2021-i (Cúcuta excluido); filas caídas las atrapa
        # el chequeo duro standings-vs-partidos de abajo
        w.warn(f"{sid}: {len(standings)} equipos en standings")

    pos = [s["position"] for s in standings]
    if pos != sorted(pos) or len(pos) != len(set(pos)):
        errors.append(f"{sid}: posiciones duplicadas o desordenadas")

    for s in standings:
        if s["won"] + s["drawn"] + s["lost"] != s["played"]:
            msg = f"{sid}: {s['team']} PG+PE+PP != PJ"
            if (sid, s["team"]) in KNOWN_PJ_ISSUES:
                w.warn(f"ISSUE CONOCIDO (fuente): {msg}")
            else:
                errors.append(msg)
        # 2 puntos por victoria hasta 1994; 3 desde 1995; bonus 1995-1998:
        # Pts = W*pts_per_win + empates + bonus
        try:
            year = int(str(data["season"].get("year") or data["season"]["id"])[:4])
        except (ValueError, TypeError):
            year = 2026
        pts_per_win = 2 if year < 1995 else 3
        expected = s["won"] * pts_per_win + s["drawn"] + (s.get("bonus") or 0)
        if abs(expected - (s["points"] or 0)) > 0.011:
            msg = f"{sid}: {s['team']} {pts_per_win}*PG+PE+bonus != puntos ({s['points']})"
            if (sid, s["team"]) in KNOWN_POINTS_ISSUES:
                w.warn(f"ISSUE CONOCIDO (fuente): {msg}")
            else:
                errors.append(msg)
        if s["team"] not in teams:
            errors.append(f"{sid}: equipo {s['team']} fuera de la lista de teams")

    if standings:
        gf = sum(s["goals_for"] or 0 for s in standings)
        ga = sum(s["goals_against"] or 0 for s in standings)
        if gf != ga:
            msg = f"{sid}: ΣGF({gf}) != ΣGC({ga})"
            if sid in KNOWN_SUMS_ISSUES:
                w.warn(f"ISSUE CONOCIDO (fuente): {msg}")
            else:
                errors.append(msg)

    reg = [m for m in matches if m["stage"] == "regular" and m["status"] == "played"]
    match_teams = {m["home"] for m in matches} | {m["away"] for m in matches}
    if standings and match_teams:
        missing = sorted(match_teams - {s["team"] for s in standings})
        extra = sorted({s["team"] for s in standings} - match_teams)
        if missing:
            errors.append(f"{sid}: equipos en partidos fuera del torneo: {missing}")
        if extra:
            w.warn(f"{sid}: sin partidos parseados para {extra} (cobertura parcial de la fuente?)")
    if standings and reg:
        # cruces standings vs partidos por equipo
        from collections import defaultdict

        pj, gf, ga = defaultdict(int), defaultdict(int), defaultdict(int)
        for m in reg:
            pj[m["home"]] += 1
            pj[m["away"]] += 1
            gf[m["home"]] += m["home_goals"]
            ga[m["away"]] += m["home_goals"]
            gf[m["away"]] += m["away_goals"]
            ga[m["home"]] += m["away_goals"]
        for s in standings:
            if pj[s["team"]] != s["played"]:
                w.warn(f"{sid}: {s['team']} PJ standings({s['played']}) != partidos({pj[s['team']]})")
            if gf[s["team"]] and gf[s["team"]] != s["goals_for"]:
                w.warn(f"{sid}: {s['team']} GF standings({s['goals_for']}) != partidos({gf[s['team']]})")

    rounds = {m["round"] for m in matches if m["stage"] == "regular" and m["round"]}
    if rounds and max(rounds) > 60:
        errors.append(f"{sid}: jornadas fuera de rango (max {max(rounds)})")

    for m in matches:
        if m["home"] not in teams or m["away"] not in teams:
            errors.append(f"{sid}: partido con equipo desconocido {m['id']}")
        if m["home_goals"] is not None and (m["home_goals"] < 0 or m["away_goals"] < 0):
            errors.append(f"{sid}: marcador negativo en {m['id']}")
    return errors


def validate_champions(data: dict, w: Warnings) -> list[str]:
    errors = []
    years = [c["year"] for c in data.get("champions", [])]
    if years != sorted(years):
        errors.append("champions: años desordenados")
    if years and years[0] != 1948:
        errors.append(f"champions: primer año {years[0]} (esperado 1948)")
    # clave única = season_id (años con dos ediciones: "1995" y "1995-96" son distintas;
    # 1989 no existe: torneo suspendido)
    ids = [c["season_id"] for c in data["champions"]]
    if len(ids) != len(set(ids)):
        errors.append("champions: season_id duplicados")
    for gap_year in (1989,):
        if any(c["year"] == gap_year for c in data["champions"]):
            w.warn(f"champions: {gap_year} existió pero el torneo fue suspendido — revisar")
    return errors


def validate_players(data: dict, w: Warnings) -> list[str]:
    errors = []
    players = data.get("players", [])
    ids = [p["id"] for p in players]
    if len(ids) != len(set(ids)):
        errors.append("players: ids duplicados")
    if len(players) < 200:
        w.warn(f"players: solo {len(players)} jugadores")
    return errors


def validate_all(out_dir: Path = OUT) -> tuple[list[str], list[str]]:
    """Devuelve (errors, warnings)."""
    w = Warnings()
    errors: list[str] = []
    if not out_dir.exists():
        return [f"{out_dir} no existe — ejecuta el build primero"], []

    teams_path = out_dir / "teams.json"
    if teams_path.exists():
        errors += validate_teams(_load(teams_path), w)

    champs = out_dir / "champions.json"
    if champs.exists():
        errors += validate_champions(_load(champs), w)

    players_path = out_dir / "players.json"
    if players_path.exists():
        errors += validate_players(_load(players_path), w)

    seasons_dir = out_dir / "seasons"
    teams_ids = {t["id"] for t in _load(teams_path)["teams"]} if teams_path.exists() else None
    if seasons_dir.exists():
        for f in sorted(seasons_dir.glob("*.json")):
            data = _load(f)
            errors += validate_season(data, w)
            if teams_ids is not None:
                unknown = set(data.get("teams", [])) - teams_ids
                if unknown:
                    errors.append(f"{data['season']['id']}: equipos no registrados en teams.json: {sorted(unknown)}")

    return errors, w.items


def main() -> int:
    errors, warnings = validate_all()
    for msg in warnings:
        print(f"⚠  {msg}")
    for msg in errors:
        print(f"✗  {msg}")
    if errors:
        print(f"FALLO: {len(errors)} errores de validación")
        return 1
    print("✓ Validación OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
