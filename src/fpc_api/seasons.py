"""Temporadas de Primera A: posiciones, partidos, goleadores y asistencias."""
import re
from datetime import datetime, timezone
from urllib.parse import unquote

from . import wiki
from .normalize import match_team, parse_score
from .tables import (
    find_fixture_tables, find_standings_tables, find_stat_table,
    infobox_data, rows, soup, team_from_cell, texts,
)

MONTHS = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
          "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11,
          "diciembre": 12}

ORDINALS = {"primera": 1, "segunda": 2, "tercera": 3, "cuarta": 4, "quinta": 5,
            "sexta": 6, "séptima": 7, "septima": 7, "octava": 8}


def season_id(year: int, torneo: str) -> str:
    return f"{year}-{'i' if torneo == 'apertura' else 'ii'}"


def resolve_page(year: int, torneo: str) -> str:
    T = "Apertura" if torneo == "apertura" else "Finalización"
    title = wiki.resolve([f"Torneo {T} {year} (Colombia)", f"Torneo {T} {year}"])
    if title:
        return title
    for hit in wiki.search(f"Torneo {T} {year} Colombia"):
        if str(year) in hit and ("Colombia" in hit or T in hit):
            return hit
    raise RuntimeError(f"No encontré la página de {T} {year}")


def parse_date(text: str, year: int) -> str | None:
    m = re.search(r"(\d{1,2}) de (\w+)(?: de (\d{4}))?", text or "")
    if not m:
        return None
    month = MONTHS.get(m.group(2).lower())
    if not month:
        return None
    y = int(m.group(3)) if m.group(3) else year
    return f"{y:04d}-{month:02d}-{int(m.group(1)):02d}"


def _classify_standings(header: list[str]) -> dict[str, int] | None:
    colmap: dict[str, int] = {}
    for i, h in enumerate(header):
        hl = h.lower().strip(". ")
        if hl.startswith("pos"):
            colmap["position"] = i
        elif "equipo" in hl or "club" in hl:
            colmap["team"] = i
        elif hl in ("pj", "pj."):
            colmap["played"] = i
        elif hl.startswith("pts"):
            colmap["points"] = i
        elif hl in ("g", "pg"):
            colmap["won"] = i
        elif hl in ("e", "pe"):
            colmap["drawn"] = i
        elif hl in ("p", "pp"):
            colmap["lost"] = i
        elif hl == "gf":
            colmap["goals_for"] = i
        elif hl == "gc":
            colmap["goals_against"] = i
        elif hl.startswith("dif") or hl == "dg":
            colmap["goal_diff"] = i
    need = ("position", "team", "played", "points", "won", "drawn", "lost")
    return colmap if all(k in colmap for k in need) else None


def parse_standings(grid: list[list[dict]]) -> list[dict]:
    """Parsea una tabla de clasificación a filas de standings."""
    colmap = None
    start = 0
    for i, row in enumerate(grid[:3]):
        colmap = _classify_standings(texts(row))
        if colmap:
            start = i + 1
            break
    if colmap is None:
        return []
    standings = []
    for row in grid[start:]:
        if len(row) <= max(colmap.values()):
            continue
        pos = None
        if "position" in colmap:
            pos = _int_from(row[colmap["position"]]["t"])
        team = team_from_cell(row[colmap["team"]])
        if team is None or pos is None:
            continue

        def val(key):
            return _int_from(row[colmap[key]]["t"]) if key in colmap and colmap[key] < len(row) else None

        standings.append({
            "team": team,
            "position": pos,
            "played": val("played") or 0,
            "won": val("won") or 0,
            "drawn": val("drawn") or 0,
            "lost": val("lost") or 0,
            "goals_for": val("goals_for"),
            "goals_against": val("goals_against"),
            "goal_diff": val("goal_diff"),
            "points": val("points"),
        })
    return standings


def _int_from(text: str) -> int | None:
    from .tables import as_int

    return as_int(text)


def _cell(row: list[dict], j: int) -> dict:
    """Celda segura: filas programadas suelen venir truncadas (sin fecha/hora)."""
    return row[j] if j < len(row) else {"t": "", "href": None}


def parse_matches(grid: list[list[dict]], season: str, stage: str, year: int,
                  caption_round: int | None) -> list[dict]:
    """Partidos desde una tabla tipo Fecha N / Resultados de cuadrangulares."""
    header_idx, colmap = None, {}
    for i, row in enumerate(grid[:3]):
        texts_lower = [c["t"].lower() for c in row]
        if any("local" == t.strip(". ") for t in texts_lower):
            for j, t in enumerate(texts_lower):
                key = t.strip(". ")
                if key in ("local", "resultado", "visitante", "estadio", "fecha", "jornada"):
                    colmap[key] = j
            header_idx = i
            break
    if header_idx is None or "local" not in colmap:
        return []
    per_pair: dict[tuple, int] = {}
    matches = []
    for row in grid[header_idx + 1:]:
        home = team_from_cell(_cell(row, colmap["local"]))
        away = team_from_cell(_cell(row, colmap["visitante"]))
        if not home or not away or home == away:
            continue
        score_text = _cell(row, colmap["resultado"])["t"] if "resultado" in colmap else ""
        score = parse_score(score_text)
        if "jornada" in colmap:
            jtxt = _cell(row, colmap["jornada"])["t"].lower().strip()
            rnd = ORDINALS.get(jtxt) or _int_from(jtxt)
        else:
            rnd = caption_round
        date = parse_date(_cell(row, colmap["fecha"])["t"], year) if "fecha" in colmap else None
        pair = (stage, rnd, home, away)
        per_pair[pair] = per_pair.get(pair, 0) + 1
        suffix = f"-{per_pair[pair]}" if per_pair[pair] > 1 else ""
        rid = f"{season}-{stage}" + (f"-r{rnd}" if rnd else "") + f"-{home}-{away}{suffix}"
        matches.append({
            "id": rid,
            "stage": stage,
            "round": rnd,
            "date": date,
            "home": home,
            "away": away,
            "home_goals": score[0] if score else None,
            "away_goals": score[1] if score else None,
            "status": "played" if score else "scheduled",
        })
    return matches


def _playoff_stages(n_ties: int) -> list[str]:
    """Llaves desde el final hacia atrás: final=1, semifinales=2, cuartos=4, octavos=8…"""
    plan = [("final", 1), ("semifinales", 2), ("cuartos", 4), ("octavos", 8), ("dieciseisavos", 16)]
    stages: list[str] = []
    remaining = n_ties
    for name, size in plan:
        take = min(size, remaining)
        stages = [name] * take + stages
        remaining -= take
        if remaining <= 0:
            break
    return ["playoffs"] * max(remaining, 0) + stages


def parse_playoffs(doc, season: str, year: int) -> list[dict]:
    """Partidos de la fase final (tablas vevent): ida/vuelta consecutivas por llave."""
    raw = []
    for t in doc.find_all("table", class_=lambda c: c and "vevent" in c):
        grid = rows(t)
        for row in grid:
            if len(row) < 4:
                continue
            score = parse_score(row[2]["t"])
            home = team_from_cell(row[1]) if len(row) > 1 else None
            away = team_from_cell(row[3]) if len(row) > 3 else None
            if not score or not home or not away:
                continue
            raw.append({
                "date": parse_date(row[0]["t"], year),
                "home": home,
                "away": away,
                "home_goals": score[0],
                "away_goals": score[1],
            })
    # agrupar llaves: partidos consecutivos con el mismo par de equipos (ida/vuelta)
    ties: list[list[dict]] = []
    for m in raw:
        pair = {m["home"], m["away"]}
        if ties and {ties[-1][-1]["home"], ties[-1][-1]["away"]} == pair and len(ties[-1]) == 1:
            ties[-1].append(m)
        else:
            ties.append([m])
    stages = _playoff_stages(len(ties))
    out = []
    for tie, stage in zip(ties, stages):
        for leg, m in enumerate(tie, 1):
            out.append({
                "id": f"{season}-{stage}-{m['home']}-{m['away']}-{leg}",
                "stage": stage,
                "round": None,
                "leg": leg,
                "date": m["date"],
                "home": m["home"],
                "away": m["away"],
                "home_goals": m["home_goals"],
                "away_goals": m["away_goals"],
                "status": "played",
            })
    return out


def parse_individuals(grid: list[list[dict]], pattern: str, field: str) -> list[dict]:
    """Goleadores o asistencias: Jugador | Equipo | <col que matchea pattern> | PJ..."""
    colmap = {}
    for j, h in enumerate(texts(grid[0])):
        hl = h.lower()
        if hl == "jugador":
            colmap["player"] = j
        elif hl == "equipo":
            colmap["team"] = j
        elif re.search(pattern, hl):
            colmap["stat"] = j
        elif hl == "pj":
            colmap["pj"] = j
    if "player" not in colmap or "stat" not in colmap:
        return []
    out = []
    for row in grid[1:]:
        if len(row) <= max(colmap.values()):
            continue
        from .normalize import clean_name

        name = clean_name(row[colmap["player"]]["t"])
        if not name:
            continue
        team = team_from_cell(row[colmap["team"]]) if "team" in colmap else None
        stat = _int_from(row[colmap["stat"]]["t"])
        if stat is None:
            continue
        out.append({
            "player_name": name,
            "team": team,
            field: stat,
            "played": _int_from(row[colmap["pj"]]["t"]) if "pj" in colmap else None,
        })
    return out


def build_season(year: int, torneo: str, max_age_days: float = 2.0) -> dict:
    sid = season_id(year, torneo)
    title = resolve_page(year, torneo)
    got = wiki.page_html(title, max_age_days=max_age_days)
    if not got:
        raise RuntimeError(f"No se pudo cargar '{title}'")
    final_title, html = got
    doc = soup(html)
    box = infobox_data(doc)

    # --- clasificaciones: la 1ª es la fase regular; las de 4 equipos son grupos ---
    # (Wikipedia duplica tablas para móvil: dedup por conjunto de equipos)
    standings, groups = [], []
    seen_sets: list[frozenset] = []
    for i, t in enumerate(find_standings_tables(doc)):
        parsed = parse_standings(rows(t))
        if not parsed:
            continue
        key = frozenset(s["team"] for s in parsed)
        if key in seen_sets:
            continue
        seen_sets.append(key)
        if i == 0 or not standings:
            standings = parsed
        elif len(parsed) == 4:
            groups.append({
                "name": f"Grupo {'AB'[len(groups)] if len(groups) < 2 else len(groups)+1}",
                "standings": parsed,
            })

    # --- partidos ---
    matches = []
    for t in find_fixture_tables(doc):
        grid = rows(t)
        caption_round = None
        first = texts(grid[0])[0].lower()
        m = re.match(r"fecha\s+(\d+)", first)
        if m:
            caption_round = int(m.group(1))
        stage = "regular" if caption_round else "cuadrangulares"
        matches += parse_matches(grid, sid, stage, year, caption_round)

    finals = parse_playoffs(doc, sid, year)
    matches += finals

    # dedup de partidos (por si la fuente repite tablas)
    seen: set[str] = set()
    matches = [m for m in matches
               if (k := f"{m['stage']}-{m['round']}-{m['home']}-{m['away']}") not in seen
               and not seen.add(k)]

    # --- campeón y metadatos del infobox ---
    champion = None
    if "campeón" in box:
        for href in box["campeón"].get("hrefs", []):
            try:
                champion = match_team(unquote(href.split("/wiki/")[-1].replace("_", " ")))
                break
            except ValueError:
                continue

    scorers_t = find_stat_table(doc, r"goles")
    assists_t = find_stat_table(doc, r"asistencias")
    goleadores = parse_individuals(rows(scorers_t), r"goles", "goals") if scorers_t else []
    asistencias = parse_individuals(rows(assists_t), r"asistencias", "assists") if assists_t else []

    return {
        "meta": {
            "version": 1,
            "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": f"https://es.wikipedia.org/wiki/{final_title.replace(' ', '_')}",
        },
        "season": {
            "id": sid,
            "year": year,
            "tournament": torneo,
            "wikipedia": final_title,
            "start_date": parse_date(box["fecha de inicio"]["t"], year) if "fecha de inicio" in box else None,
            "end_date": parse_date(box["fecha de cierre"]["t"], year) if "fecha de cierre" in box else None,
            "status": "completed" if champion else "in_progress",
        },
        "champion": champion,
        "teams": sorted({s["team"] for s in standings}),
        "standings": standings,
        "groups": groups,
        "matches": matches,
        "scorers": goleadores,
        "assists": asistencias,
    }
