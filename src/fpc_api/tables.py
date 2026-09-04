"""Extracción de wikitables: filas aplanadas con rowspan, celdas con texto+href."""
import re
from urllib.parse import unquote

from bs4 import BeautifulSoup, Tag

Cell = dict  # {"t": texto plano, "href": primer href de /wiki/ que no sea un archivo}


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def all_tables(doc: BeautifulSoup) -> list[Tag]:
    return doc.find_all("table")


def cell_of(td: Tag) -> Cell:
    href = None
    for a in td.find_all("a", href=True):
        if a["href"].startswith("/wiki/") and not a["href"].startswith("/wiki/Archivo:"):
            href = a["href"]
            break
    return {"t": td.get_text(" ", strip=True), "href": href}


def rows(table: Tag) -> list[list[Cell]]:
    """Filas de una tabla expandiendo rowspan y rellenando colspan."""
    pending: dict[int, tuple[Cell, int]] = {}
    out = []
    for tr in table.find_all("tr"):
        cells = tr.find_all(["td", "th"], recursive=False)
        if not cells:
            continue
        row: list[Cell] = []
        col = 0
        ci = 0
        while True:
            if col in pending:
                cell, remaining = pending.pop(col)
                row.append(cell)
                if remaining - 1 > 0:
                    pending[col] = (cell, remaining - 1)
                col += 1
                continue
            if ci >= len(cells):
                break
            td = cells[ci]
            ci += 1
            cell = cell_of(td)
            colspan = int(td.get("colspan", 1) or 1)
            row.append(cell)
            for _ in range(colspan - 1):
                row.append({"t": "", "href": None})
                col += 1
            rowspan = int(td.get("rowspan", 1) or 1)
            if rowspan > 1:
                pending[col] = (cell, rowspan - 1)
            col += 1
        out.append(row)
    return out


def texts(row: list[Cell]) -> list[str]:
    return [c["t"] for c in row]


def row_text(row: list[Cell]) -> str:
    return " ".join(c["t"].lower() for c in row)


def team_from_cell(cell: Cell) -> str | None:
    """Slug canónico del club en una celda (href de Wikipedia primero)."""
    from .normalize import match_team, slugify

    if cell.get("href"):
        try:
            return match_team(unquote(cell["href"].split("/wiki/")[-1].replace("_", " ")))
        except ValueError:
            pass
    t = cell["t"]
    for candidate in [t.split(" (")[0], t]:
        try:
            return match_team(candidate)
        except ValueError:
            continue
    return None


def as_int(text: str) -> int | None:
    clean = re.sub(r"[\s\u00a0,.\u200b]", "", (text or ""))
    m = re.search(r"-?\d+", clean)
    return int(m.group()) if m else None


def find_standings_tables(doc: BeautifulSoup) -> list[Tag]:
    """Tablas de clasificación: encabezado con pos/equipo/pj/pts."""
    out = []
    for t in all_tables(doc):
        trs = t.find_all("tr")
        if not trs:
            continue
        h = row_text(rows(t)[0]) if trs[0].find_all(["td", "th"]) else ""
        if re.search(r"\bpos", h) and "equipo" in h and "pj" in h and re.search(r"\bpts", h):
            out.append(t)
    return out


def find_fixture_tables(doc: BeautifulSoup) -> list[Tag]:
    """Tablas de partidos: encabezado local/resultado/visitante/estadio/fecha."""
    out = []
    for t in all_tables(doc):
        grid = rows(t)
        if len(grid) < 3:
            continue
        for row in grid[:2]:
            h = row_text(row)
            if ("local" in h and "resultado" in h and "visitante" in h
                    and "estadio" in h and "fecha" in h):
                out.append(t)
                break
    return out


def find_stat_table(doc: BeautifulSoup, keyword: str) -> Tag | None:
    """Tabla de estadísticas individuales ('jugador' + keyword en encabezado)."""
    for t in all_tables(doc):
        grid = rows(t)
        if len(grid) < 2:
            continue
        h = row_text(grid[0])
        if "triplete" in h:
            continue
        if "jugador" in h and re.search(keyword, h):
            return t
    return None


def infobox_data(doc: BeautifulSoup) -> dict[str, dict]:
    """Infobox de una página: clave -> {"t": texto, "hrefs": [hrefs /wiki/]}."""
    box = doc.find("table", class_=lambda c: c and "infobox" in c)
    if not box:
        return {}
    out = {}
    for tr in box.find_all("tr"):
        th, td = tr.find("th"), tr.find("td")
        if not th or not td:
            continue
        hrefs = [a["href"] for a in td.find_all("a", href=True)
                 if a["href"].startswith("/wiki/") and not a["href"].startswith("/wiki/Archivo:")]
        out[th.get_text(" ", strip=True).lower()] = {
            "t": td.get_text(" ", strip=True), "hrefs": hrefs,
        }
    return out


def teams_in_cell(cell: dict) -> list[str]:
    """Todos los clubes reconocibles dentro de una celda (por href o texto)."""
    from urllib.parse import unquote

    from .normalize import match_team

    slugs = []
    for href in cell.get("hrefs", []):
        try:
            s = match_team(unquote(href.split("/wiki/")[-1].replace("_", " ")))
        except ValueError:
            continue
        if s not in slugs:
            slugs.append(s)
    if not slugs:
        s = team_from_cell(cell)
        if s:
            slugs.append(s)
    return slugs
