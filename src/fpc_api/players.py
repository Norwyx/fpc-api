"""Plantillas actuales desde la sección 'Plantilla' de cada página de club (best-effort)."""
import re
from datetime import datetime, timezone
from urllib.parse import unquote

from . import wiki
from .normalize import clean_name, match_position
from .tables import as_int, rows, soup, texts

# nombres de sección/grupo -> posición
GROUP_POS = {"portero": "GK", "defensa": "DF", "mediocampista": "MF", "volante": "MF",
             "medio": "MF", "delantero": "FW"}
POS_CODES = {"por": "GK", "arq": "GK", "gk": "GK", "def": "DF", "dfc": "DF", "lat": "DF",
             "med": "MF", "vol": "MF", "cen": "MF", "mco": "MF", "del": "FW", "dc": "FW",
             "ext": "FW", "fw": "FW"}


def _plantilla_table(doc) -> list[dict] | None:
    """Primera tabla bajo un encabezado 'Plantilla ...'."""
    for h in doc.find_all(["h2", "h3"]):
        txt = h.get_text(" ", strip=True).lower()
        # "Plantilla 2026-II", "Jugadores 2026/2", "Jugadores" — pero no cedidos/selecciones
        if not (re.search(r"plantilla|jugadores\s*\d|^jugadores$", txt)):
            continue
        t = h.find_next("table")
        if t is None:
            continue
        grid = rows(t)
        header_idx, colmap = None, {}
        for i, row in enumerate(grid[:5]):
            ls = [c["t"].lower().strip(". ") for c in row]
            if any(x in ("n.º", "nº", "no.", "#") for x in ls) and any(
                    "nombre" in x or "jugador" in x for x in ls):
                for j, x in enumerate(ls):
                    if x in ("n.º", "nº", "no.", "#"):
                        colmap["number"] = j
                    elif "pos" in x:
                        colmap["position"] = j
                    elif "nombre" in x or "jugador" in x:
                        colmap["name"] = j
                    elif "edad" in x:
                        colmap["age"] = j
                header_idx = i
                break
        if header_idx is None or "name" not in colmap:
            continue
        return _parse_squad(grid[header_idx + 1:], colmap)
    return None


def _parse_squad(grid: list[list[dict]], colmap: dict) -> list[dict]:
    players, group = [], None
    for row in grid:
        cells = texts(row)
        if len(cells) <= max(colmap.values()):
            continue
        first = cells[0].lower().strip()
        if row[0]["t"] and not row[0]["t"][0].isdigit() and not any(
                c["t"] for c in row[1:max(colmap.values()) + 1]):
            group = GROUP_POS.get(first.rstrip("s"))
            continue
        name = clean_name(row[colmap["name"]]["t"])
        if not name or len(name) < 3:
            continue
        pos_raw = row[colmap["position"]]["t"] if "position" in colmap else ""
        pos = None
        code = re.sub(r"^\d+\s*", "", pos_raw.strip()).lower().strip(". ")
        pos = POS_CODES.get(code) if code else None
        if pos is None:
            pos = match_position(pos_raw)
        if pos is None and group:
            pos = group
        players.append({
            "name": name,
            "shirt_number": as_int(row[colmap["number"]]["t"]) if "number" in colmap else None,
            "position": pos,
            "age": as_int(row[colmap["age"]]["t"]) if "age" in colmap else None,
        })
    return players


def build(team_pages: dict[str, str], max_age_days: float = 2.0) -> dict:
    """team_pages: slug -> título de Wikipedia del club (de teams.json)."""
    players, warnings = [], []
    for slug, title in sorted(team_pages.items()):
        if not title:
            warnings.append(f"{slug}: sin página de Wikipedia")
            continue
        title = unquote(title)
        got = wiki.page_html(title, max_age_days=max_age_days)
        if not got:
            warnings.append(f"{slug}: página no encontrada ({title})")
            continue
        squad = _plantilla_table(soup(got[1]))
        if not squad:
            warnings.append(f"{slug}: sección 'Plantilla' no encontrada o vacía")
            continue
        seen = set()
        for p in squad:
            key = p["name"].lower()
            if key in seen:
                continue
            seen.add(key)
            players.append({
                "name": p["name"],
                "team": slug,
                "position": p["position"],
                "shirt_number": p["shirt_number"],
                "age": p["age"],
                "source": f"https://es.wikipedia.org/wiki/{title.replace(' ', '_')}",
            })
    assign_ids(players, warnings)
    return {
        "meta": {
            "version": 1,
            "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "es.wikipedia.org (secciones 'Plantilla' de cada club)",
            "warnings": warnings,
        },
        "players": players,
    }


def assign_ids(players: list[dict], warnings: list[str]) -> None:
    """ID = slug del nombre (estable ante traspasos). Solo si dos jugadores distintos
    comparten nombre se sufija con el club (y se avisa). v2 migrará a IDs API-Football."""
    # ponytail: la desambiguación por club re-churnea ese id si el homónimo se va;
    # identidad canónica estable llega con API-Football/Wikidata (fase v2)
    from collections import Counter

    from .normalize import slugify

    counts = Counter(slugify(p["name"]) or f"{slugify(p['team'])}-sin-nombre" for p in players)
    collisions = {s for s, c in counts.items() if c > 1}
    for p in players:
        s = slugify(p["name"]) or f"{slugify(p['team'])}-sin-nombre"
        p["id"] = f"{s}-{p['team']}" if s in collisions else s
    for s in sorted(collisions):
        teams = sorted(p["team"] for p in players
                       if (slugify(p["name"]) or f"{slugify(p['team'])}-sin-nombre") == s)
        warnings.append(f"homónimos {s!r} en {teams}: ids sufijados con el club")
