"""Temporadas de Primera A: posiciones, partidos, goleadores y asistencias."""
import re
from datetime import datetime, timezone
from urllib.parse import unquote

from . import wiki
from .normalize import match_team, parse_score
from .tables import (
    find_fixture_tables, find_standings_tables, find_stat_table,
    infobox_data, is_caption_row, rows, soup, team_from_cell, texts,
)

MONTHS = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
          "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11,
          "diciembre": 12}

ORDINALS = {"primera": 1, "segunda": 2, "tercera": 3, "cuarta": 4, "quinta": 5,
            "sexta": 6, "séptima": 7, "septima": 7, "octava": 8}


def _current_year() -> int:
    return datetime.now(timezone.utc).year


def season_id(year: int, torneo: str) -> str:
    if (year, torneo) in HYPHEN_SEASONS:
        return HYPHEN_SEASONS[(year, torneo)]
    if torneo == "apertura" and (year == 2020 or year < 2002):
        # un solo torneo por año: el COVID-2020 y toda la era pre-2002
        return str(year)
    return f"{year}-{'i' if torneo == 'apertura' else 'ii'}"


# segundos torneos con calendario europeo (transición 1995-1997)
HYPHEN_SEASONS = {(1995, "finalizacion"): "1995-96", (1996, "finalizacion"): "1996-97"}


def resolve_page(year: int, torneo: str) -> str:
    if (year, torneo) in HYPHEN_SEASONS:
        return f"Campeonato colombiano {HYPHEN_SEASONS[(year, torneo)]}"
    T = "Apertura" if torneo == "apertura" else "Finalización"
    # OJO: el "Torneo Apertura YYYY" sin país suele ser de otro país; para
    # años pre-2002 solo se acepta "(Colombia)" o "Campeonato colombiano".
    candidates = [f"Torneo {T} {year} (Colombia)"]
    if year >= 2002:
        candidates.append(f"Torneo {T} {year}")
    else:
        candidates += [f"Campeonato colombiano {year}", f"Torneo colombiano {year}"]
    title = wiki.resolve(candidates)
    if title:
        return title
    if year >= 2002:
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
        elif hl in ("dpg",):
            colmap["dpg"] = i
        elif hl in ("dpp",):
            colmap["dpp"] = i
        elif hl in ("bon",):
            colmap["bonus"] = i
        elif hl in ("p", "pp"):
            colmap["lost"] = i
        elif hl == "gf":
            colmap["goals_for"] = i
        elif hl == "gc":
            colmap["goals_against"] = i
    need = ("position", "team", "played", "points", "won", "lost")
    has_drawn = "drawn" in colmap or "dpg" in colmap or "dpp" in colmap
    return colmap if all(k in colmap for k in need) and has_drawn else None


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

        def num(key):
            from .tables import as_number

            return as_number(row[colmap[key]]["t"]) if key in colmap and colmap[key] < len(row) else None

        # era bonus (1995-1998): empates con definición por penales (DPG/DPP) y
        # puntos extra (Bon.); fórmula verificada: Pts = 3*PG + DPG*2 + DPP + Bon
        dpg = val("dpg") or 0
        dpp = val("dpp") or 0
        drawn = val("drawn")
        if drawn is None:
            drawn = (dpg + dpp) or 0
        bonus = num("bonus")
        if bonus is None and ("dpg" in colmap or "dpp" in colmap):
            bonus = dpg
        gf = val("goals_for")
        ga = val("goals_against")
        standings.append({
            "team": team,
            "position": pos,
            "played": val("played") or 0,
            "won": val("won") or 0,
            "drawn": drawn,
            "lost": val("lost") or 0,
            "goals_for": gf,
            "goals_against": ga,
            # calculado, no leído: en tablas viejas el Dif viene sin signo
            "goal_diff": (gf - ga) if gf is not None and ga is not None else None,
            "points": num("points"),
            "bonus": bonus,
        })
    return standings


def _int_from(text: str) -> int | None:
    from .tables import as_int

    return as_int(text)


def _cell(row: list[dict], j: int) -> dict:
    """Celda segura: filas programadas suelen venir truncadas (sin fecha/hora)."""
    return row[j] if j < len(row) else {"t": "", "href": None}


def _segments(grid: list[list[dict]]) -> list[tuple[str | None, list[list[dict]]]]:
    """Parte tablas compuestas (varias fechas en una tabla) por caption."""
    bounds = [i for i, row in enumerate(grid) if is_caption_row(row)]
    if not bounds:
        return [(None, grid)]
    segs = []
    for k, b in enumerate(bounds):
        end = bounds[k + 1] if k + 1 < len(bounds) else len(grid)
        segs.append((grid[b][0]["t"], grid[b:end]))
    return segs


# sección -> etapa (orden: primero el más específico). "Fase final"/"Cuadro final"
# son contenedores, no etapas: no aparecen aquí a propósito.
SECTION_STAGES = [
    ("repechaje|liguilla", "liguilla"),
    ("cuadrangular final", "cuadrangular-final"),
    ("cuadrangular", "cuadrangulares"),
    (r"\bgrupos?\b", "cuadrangulares"),
    ("pentagonal", "pentagonales"),
    ("triangular", "triangulares"),
    ("octogonal", "octogonal"),
    ("hexagonal", "hexagonal"),
    ("octavos?", "octavos"),
    ("cuartos?", "cuartos"),
    ("semifinal", "semifinales"),
    (r"^(final|gran final)\b", "final"),
    # fases internas de un torneo anual (era pre-2002): van después de "final"
    # para no robarle "Final del Torneo Finalización" etc.
    (r"\bapertura\b", "apertura"),
    (r"\bfinalizaci[oó]n\b", "finalizacion"),
]


def _section_stage(table) -> str:
    """Etapa desde los encabezados: h3 primero; si es genérico, contexto h2."""
    h3, h2 = "", ""
    for h in table.find_all_previous(["h2", "h3"], limit=4):
        if h.name == "h3" and not h3:
            h3 = h.get_text(" ", strip=True).lower()
        elif h.name == "h2" and not h2:
            h2 = h.get_text(" ", strip=True).lower()
        if h3 and h2:
            break
    if "liguilla" in h2 or "repechaje" in h2 or "eliminados" in h2:
        return "liguilla"
    for text in (h3, h2):
        for pat, stage in SECTION_STAGES:
            if re.search(pat, text):
                return stage
    return "playoffs"


def parse_matches(grid: list[list[dict]], season: str, stage: str, year: int,
                  fallback_cap: str | None = None) -> list[dict]:
    """Partidos desde una tabla tipo Fecha N / Resultados (parte compuestas por fecha).
    fallback_cap: caption en el h3 ('Fecha 5 — 4 de marzo') cuando la tabla no lo trae."""
    matches = []
    segs = _segments(grid)
    # si ningún segmento trae número (captions ordinales: "PRIMERA FECHA"...),
    # la jornada es la posición del segmento
    numbered = [re.search(r"(?:fecha|jornada)\s+(\d+)", (cap or "").lower()) for cap, _ in segs]
    autonumber = all(m is None for m in numbered)
    for pos, ((cap, seg), m) in enumerate(zip(segs, numbered), 1):
        cap = cap or fallback_cap
        if m:
            rnd = int(m.group(1))
        elif cap and re.search(r"(?:fecha|jornada)\s+(\d+)", cap.lower()):
            rnd = int(re.search(r"(?:fecha|jornada)\s+(\d+)", cap.lower()).group(1))
        elif autonumber and cap:
            rnd = pos
        else:
            rnd = None
        leg = None
        if cap:
            leg = 1 if "ida" in cap.lower() else 2 if "vuelta" in cap.lower() else None
        matches += _parse_segment(seg, season, stage, year, rnd, leg)
    return matches


def _parse_segment(grid: list[list[dict]], season: str, stage: str, year: int,
                   caption_round: int | None, leg: int | None) -> list[dict]:
    if not grid:
        return []
    from .tables import fixture_colmap, is_fixture_header

    header_idx, colmap = None, {}
    for i, row in enumerate(grid[:3]):
        texts_lower = [c["t"].lower() for c in row]
        if is_fixture_header(texts_lower):
            colmap = fixture_colmap(texts_lower)
            header_idx = i
            break
    start = 0
    if header_idx is None:
        # tablas sin encabezado (era 2002-2003): [local, resultado, visitante] posicional
        from .tables import _looks_match_row

        start = 1 if grid and is_caption_row(grid[0]) else 0
        probe = [r for r in grid[start:start + 2] if len(r) >= 3 and _looks_match_row(r)]
        if len(probe) < 2:
            return []
        colmap = {"local": 0, "resultado": 1, "visitante": 2}
        header_idx = start - 1
    if "local" not in colmap:
        return []
    # el marcador sigue el orden de columnas ("Local|Resultado|Visitante" o al
    # revés, como la Fecha 2 del Finalización 2023: "Visitante|Resultado|Local")
    home_first = colmap.get("visitante", 999) > colmap["local"]
    per_pair: dict[tuple, int] = {}
    matches = []
    for row in grid[header_idx + 1:]:
        home = team_from_cell(_cell(row, colmap["local"]))
        away = team_from_cell(_cell(row, colmap["visitante"])) if "visitante" in colmap else None
        if not home or not away or home == away:
            continue
        score_text = _cell(row, colmap["resultado"])["t"] if "resultado" in colmap else ""
        score = parse_score(score_text)
        if score and not home_first:
            score = (score[1], score[0])
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
            "leg": leg,
            "date": date,
            "home": home,
            "away": away,
            "home_goals": score[0] if score else None,
            "away_goals": score[1] if score else None,
            "penalties": None,  # solo en llaves definidas por penales
            "status": "played" if score else "scheduled",
        })
    return matches


def parse_matrix(grid: list[list[dict]], season: str, stage: str, year: int,
                 skip_pairs: set) -> list[dict]:
    """Matriz de resultados equipo×equipo (era pre-2002): fila=local por defecto.
    Omite pairings ya cubiertos por tablas lineales (tienen jornada)."""
    from .tables import team_from_href

    if not grid or len(grid[0]) < 2:
        return []
    cols = []
    for c in grid[0][1:]:
        team = team_from_href(c.get("href")) or team_from_cell(c)
        cols.append(team)
    matches, seen = [], set()
    for row in grid[1:]:
        if not row:
            continue
        home = team_from_href(row[0].get("href")) or team_from_cell(row[0])
        if not home:
            continue
        for j, cell in enumerate(row[1:]):
            if j >= len(cols) or not cols[j]:
                continue
            away = cols[j]
            if home == away:
                continue
            score = parse_score(cell["t"])
            if not score:
                continue
            if frozenset((home, away)) in skip_pairs:
                continue
            key = (stage, home, away, score)
            if key in seen:
                continue
            seen.add(key)
            matches.append({
                "id": f"{season}-{stage}-{home}-{away}",
                "stage": stage,
                "round": None,
                "leg": None,
                "date": None,
                "home": home,
                "away": away,
                "home_goals": score[0],
                "away_goals": score[1],
                "penalties": _parse_penalties(cell["t"]),
                "status": "played",
            })
    return matches


def _flip_matches(matches: list[dict]) -> list[dict]:
    """Invierte local/visitante (si la matriz resultara ser fila=visitante)."""
    out = []
    for m in matches:
        m = dict(m)
        m["home"], m["away"] = m["away"], m["home"]
        m["home_goals"], m["away_goals"] = m["away_goals"], m["home_goals"]
        m["id"] = m["id"].rsplit("-", 2)[0] + f"-{m['home']}-{m['away']}"
        out.append(m)
    return out


def _matrix_orientation(matrix_ms: list[dict], fixture_ms: list[dict], sid: str) -> tuple[bool, int, int]:
    """(voltear?, solapamiento, acuerdos): compara partidos comunes (par + marcador).
    Sin solapamiento asume fila=local (convención es.wiki)."""
    import sys

    if not matrix_ms or not fixture_ms:
        return False, 0, 0
    fix = {(m["home"], m["away"], m["home_goals"], m["away_goals"]) for m in fixture_ms
           if m["status"] == "played"}
    agree = sum(1 for m in matrix_ms
                if (m["home"], m["away"], m["home_goals"], m["away_goals"]) in fix)
    flipped = sum(1 for m in matrix_ms
                  if (m["away"], m["home"], m["away_goals"], m["home_goals"]) in fix)
    total = agree + flipped
    if total >= 5:
        if flipped > agree:
            print(f"  matriz {sid}: VOLTEADA (fila=visitante) {flipped}/{total}", file=sys.stderr)
            return True, total, agree
        return False, total, agree
    if matrix_ms:
        print(f"  matriz {sid}: sin solapamiento para verificar, asumo fila=local", file=sys.stderr)
    return False, total, agree
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


def _vevent_section(table) -> tuple[str, str]:
    """Textos (h3, h2) más cercanos antes de la tabla."""
    h3, h2 = "", ""
    for h in table.find_all_previous(["h2", "h3"], limit=4):
        if h.name == "h3" and not h3:
            h3 = h.get_text(" ", strip=True).lower()
        elif h.name == "h2" and not h2:
            h2 = h.get_text(" ", strip=True).lower()
        if h3 and h2:
            break
    return h3, h2


def _vevent_stage(h3: str, h2: str) -> str | None:
    """Etapa desde los encabezados; None si no se puede inferir (fallback global).
    OJO: 'Fase final'/'Cuadro final' son contenedores, no etapas."""
    if "liguilla" in h2 or "repechaje" in h2 or "eliminados" in h2:
        return "liguilla"
    if "octavos" in h3:
        return "octavos"
    if "cuartos" in h3:
        return "cuartos"
    if "semifinal" in h3:
        return "semifinales"
    if h3 == "final" or h3.startswith("final ") or "gran final" in h3:
        return "final"
    return None


_PENALTIES = re.compile(r"\((\d+)\s*:\s*(\d+)\s*p\.?\s*\)")


def _parse_penalties(score_text: str) -> list[int] | None:
    m = _PENALTIES.search(score_text or "")
    return [int(m.group(1)), int(m.group(2))] if m else None


def parse_playoffs(doc, season: str, year: int) -> list[dict]:
    """Partidos de fases finales (tablas vevent): etapa por sección; si la página
    no trae encabezados por etapa, se infiere desde el final (final=1 serie...)."""
    raw: list[tuple[str | None, dict]] = []
    for t in doc.find_all("table", class_=lambda c: c and "vevent" in c):
        h3, h2 = _vevent_section(t)
        hint = _vevent_stage(h3, h2)
        for row in rows(t):
            if len(row) < 4:
                continue
            score_text = row[2]["t"]
            score = parse_score(score_text)
            home = team_from_cell(row[1]) if len(row) > 1 else None
            away = team_from_cell(row[3]) if len(row) > 3 else None
            if not score or not home or not away:
                continue
            raw.append((hint, {
                "date": parse_date(row[0]["t"], year),
                "home": home,
                "away": away,
                "home_goals": score[0],
                "away_goals": score[1],
                "penalties": _parse_penalties(score_text),
            }))
    # rachas con la misma etapa: dentro de cada una se emparejan ida/vuelta
    out = []
    run: list[tuple[str | None, dict]] = []
    for item in raw + [(object(), {})]:
        if run and (item[0] != run[0][0]):
            out += _emit_ties(run, season)
            run = []
        if item[1]:
            run.append(item)
    return out


def _emit_ties(run: list[tuple[str | None, dict]], season: str) -> list[dict]:
    hint = run[0][0]
    ties: list[list[dict]] = []
    for _, m in run:
        pair = {m["home"], m["away"]}
        if ties and {ties[-1][-1]["home"], ties[-1][-1]["away"]} == pair and len(ties[-1]) == 1:
            ties[-1].append(m)
        else:
            ties.append([m])
    stages = _playoff_stages(len(ties)) if hint is None else [hint] * len(ties)
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
                "penalties": m["penalties"],
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
    # torneo: apertura/finalizacion solo para años de dos torneos; si no, liga
    torneo_out = torneo if re.fullmatch(r"\d{4}-(i|ii)", sid) else "liga"

    # --- clasificaciones: la más grande y consistente es la fase regular ---
    # (algunas páginas traen un grupo antes que la tabla principal, ej. 1985;
    # y la 1990 trae una fase corrupta en fuente: gana Reclasificación, intacta;
    # Wikipedia duplica tablas para móvil: dedup por conjunto de equipos)
    standings, groups = [], []
    seen_sets: list[frozenset] = []
    parsed_tables = []
    for t in find_standings_tables(doc):
        parsed = parse_standings(rows(t))
        if not parsed:
            continue
        # duplicados móvil/desktop tienen valores idénticos; fases distintas no
        key = frozenset((s["team"], s["points"], s["played"]) for s in parsed)
        if key in seen_sets:
            continue
        seen_sets.append(key)
        bad = sum(1 for s in parsed if s["won"] + s["drawn"] + s["lost"] != s["played"])
        parsed_tables.append((len(parsed), bad, t, parsed))
    if parsed_tables:
        parsed_tables.sort(key=lambda tp: (-tp[0], tp[1]))
        standings = parsed_tables[0][3]
        n = 0
        for _, _, t, parsed in parsed_tables[1:]:
            if 2 <= len(parsed) <= 8:
                groups.append({
                    "name": f"Grupo {'ABCDEF'[n] if n < 6 else n + 1}",
                    "stage": _section_stage(t),
                    "standings": parsed,
                })
                n += 1

    # --- partidos ---
    matches = []
    for t in find_fixture_tables(doc):
        grid = rows(t)
        if not grid:
            continue
        # caption en el h3 ('Fecha 5 — 4 de marzo') cuando la tabla no lo trae
        h3text = ""
        for h in t.find_all_previous(["h2", "h3"], limit=2):
            if h.name == "h3":
                h3text = h.get_text(" ", strip=True)
                break
        h3cap = h3text if re.search(r"(?:fecha|jornada)\s+\d+", h3text.lower()) else None
        sec_stage = _section_stage(t)
        first_cap = _segments(grid)[0][0] or h3cap
        if sec_stage == "playoffs" and not first_cap:
            stage = "playoffs"
        elif sec_stage == "playoffs":
            # fecha de fase regular ("Fecha 5", "Jornada 3", h3 "Fecha 5 — ...")
            stage = "regular"
        else:
            # fase con nombre (grupos, pentagonales, semifinales...): el N es su jornada
            stage = sec_stage
        matches += parse_matches(grid, sid, stage, year, h3cap)

    finals = parse_playoffs(doc, sid, year)
    matches += finals

    # matrices de resultados (era pre-2002): omiten pairings ya cubiertos por
    # tablas lineales DE LA MISMA FASE (tienen jornada); orientación verificada
    from .tables import find_matrix_tables

    skip_pairs = {(m["stage"], frozenset((m["home"], m["away"]))) for m in matches}
    for t in find_matrix_tables(doc):
        grid = rows(t)
        if not grid:
            continue
        title = grid[0][0]["t"].lower() if grid[0] else ""
        mstage = None
        for pat, st in SECTION_STAGES:
            if re.search(pat, title):
                mstage = st
                break
        mstage = mstage or "regular"
        mat = parse_matrix(grid, sid, mstage, year,
                           {p for (st, p) in skip_pairs if st == mstage})
        flip, overlap, agree = _matrix_orientation(mat, matches, sid)
        if flip:
            mat = _flip_matches(mat)
        matches += mat
        skip_pairs |= {(mstage, frozenset((m["home"], m["away"]))) for m in mat}

    # dedup de partidos (por si la fuente repite tablas)
    seen: set[str] = set()
    matches = [m for m in matches
               if (k := f"{m['stage']}-{m['round']}-{m['home']}-{m['away']}") not in seen
               and not seen.add(k)]

    # --- campeón: infobox, o la tabla histórica de campeones como respaldo ---
    champion = None
    if "campeón" in box:
        for href in box["campeón"].get("hrefs", []):
            try:
                champion = match_team(unquote(href.split("/wiki/")[-1].replace("_", " ")))
                break
            except ValueError:
                continue
    if champion is None:
        from .champions import champions_raw

        for c in champions_raw():
            if c["season_id"] == sid:
                champion = c["champion"]
                break

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
            "tournament": torneo_out,
            "wikipedia": final_title,
            "start_date": parse_date(box["fecha de inicio"]["t"], year) if "fecha de inicio" in box else None,
            "end_date": parse_date(box["fecha de cierre"]["t"], year) if "fecha de cierre" in box else None,
            # sin campeón en un año pasado = torneo suspendido (1989)
            "status": "completed" if champion else ("in_progress" if year >= _current_year() else "cancelled"),
        },
        "champion": champion,
        "teams": sorted({s["team"] for s in standings}),
        "standings": standings,
        "groups": groups,
        "matches": matches,
        "scorers": goleadores,
        "assists": asistencias,
    }
