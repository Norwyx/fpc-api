"""Campeones de la era profesional (1948–hoy) desde la página Categoría Primera A."""
from datetime import datetime, timezone

from . import wiki
from .tables import rows, soup, team_from_cell, texts

PAGE = "Categoría Primera A"


def _champions_grid(html: str) -> list[list[dict]] | None:
    doc = soup(html)
    for t in doc.find_all("table"):
        grid = rows(t)
        if len(grid) < 50:
            continue
        h = " ".join(c["t"].lower() for c in grid[0])
        if "año" in h and "campeón" in h and "subcampeón" in h:
            return grid
    return None


def champions_raw() -> list[dict]:
    got = wiki.page_html(PAGE)
    if not got:
        raise RuntimeError(f"No se pudo cargar '{PAGE}'")
    grid = _champions_grid(got[1])
    if grid is None:
        raise RuntimeError("No se encontró la tabla de campeones")

    out = []
    for row in grid[1:]:
        cells = texts(row)
        if len(cells) < 9 or not cells[0].strip()[:1].isdigit():
            continue
        year_label = cells[0].strip()
        season_id = year_label.lower().replace(" ", "")
        year = int(year_label[:4])
        tournament = {"-i": "apertura", "-ii": "finalizacion"}.get(season_id[4:])
        champion = team_from_cell(row[2])
        if not champion:
            continue
        runner_up = team_from_cell(row[4]) if len(row) > 4 else None
        out.append({
            "season_id": season_id,
            "year": year,
            "tournament": tournament,
            "champion": champion,
            "champion_name": row[2]["t"].split(" (")[0].strip(),
            "runner_up": runner_up,
            "runner_up_name": row[4]["t"].split(" (")[0].strip() if runner_up else None,
            "score": None if (cells[3].lower().startswith("todos")) else cells[3].strip(),
            "top_scorer": cells[6].strip(),
        })
    return out


def build() -> dict:
    return {
        "meta": {
            "version": 1,
            "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "https://es.wikipedia.org/wiki/Categoría_Primera_A",
        },
        "champions": champions_raw(),
    }
