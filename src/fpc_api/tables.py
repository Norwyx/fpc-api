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
    # limpia notas al pie ("2020[83]" -> "2020") y espacios cero-width
    text = re.sub(r"\[\s*\d+\s*\]", "", td.get_text(" ", strip=True))
    text = " ".join(text.replace("\u200b", "").split())
    return {"t": text, "href": href}


def _span(td: Tag, attr: str) -> int:
    """rowspan/colspan tolerante a HTML roto (ej. colspan="1 align=center")."""
    try:
        return max(int(str(td.get(attr, 1) or 1).split()[0]), 1)
    except (ValueError, TypeError):
        return 1


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
            colspan = _span(td, "colspan")
            row.append(cell)
            for _ in range(colspan - 1):
                row.append({"t": "", "href": None})
                col += 1
            rowspan = _span(td, "rowspan")
            if rowspan > 1:
                pending[col] = (cell, rowspan - 1)
            col += 1
        out.append(row)
    return out


def texts(row: list[Cell]) -> list[str]:
    return [c["t"] for c in row]


def row_text(row: list[Cell]) -> str:
    return " ".join(c["t"].lower() for c in row)


def team_from_href(href: str | None) -> str | None:
    """Slug desde un href de Wikipedia (prueba sin paréntesis: 'Boca_Juniors_de_Cali_(1937)')."""
    if not href or not href.startswith("/wiki/"):
        return None
    from urllib.parse import unquote

    from .normalize import match_team

    title = unquote(href.split("/wiki/")[-1].replace("_", " "))
    for cand in (title, re.sub(r"\s*\(.*?\)\s*", "", title).strip()):
        try:
            return match_team(cand)
        except ValueError:
            continue
    return None


def team_from_cell(cell: Cell) -> str | None:
    """Slug canónico del club en una celda (href de Wikipedia primero)."""
    from .normalize import match_team

    hit = team_from_href(cell.get("href"))
    if hit:
        return hit
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


def as_number(text: str) -> int | float | None:
    """Entero o decimal ('14.5', '1,5') para puntos bonus de la era 1995-1998."""
    clean = re.sub(r"[\s\u00a0\u200b]", "", (text or ""))
    if "," in clean and "." not in clean:
        clean = clean.replace(",", ".")
    m = re.search(r"-?\d+(?:\.\d+)?", clean)
    if not m:
        return None
    return float(m.group()) if "." in m.group() else int(m.group())


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


def fixture_colmap(texts_lower: list[str]) -> dict:
    """Rol de cada columna por palabras clave (ES/EN: 'Equipo local', 'Home'...)."""
    colmap: dict[str, int] = {}
    for j, t in enumerate(texts_lower):
        if "visitante" in t or "away" in t:
            colmap.setdefault("visitante", j)
        elif "local" in t or "home" in t:
            colmap.setdefault("local", j)
        elif "resultado" in t or "score" in t or "marcador" in t:
            colmap.setdefault("resultado", j)
        elif "jornada" in t:
            colmap.setdefault("jornada", j)
        elif "fecha" in t or t.strip() == "date":
            colmap.setdefault("fecha", j)
    return colmap


def is_caption_row(row: list[Cell]) -> bool:
    """Fila de caption ('Fecha 5 ...', 'Jornada 3 ...', 'PRIMERA FECHA ...'):
    primera celda con fecha/jornada y resto vacío o captions."""
    import re

    if not row or not re.search(r"fecha|jornada", row[0]["t"].lower()):
        return False
    return all(not c["t"] or re.search(r"fecha|jornada", c["t"].lower()) for c in row[1:])


def _looks_match_row(row: list[Cell]) -> bool:
    """Fila con pinta de partido: [equipo, marcador, equipo] (tablas sin encabezado)."""
    from .normalize import parse_score

    return (len(row) >= 3 and team_from_cell(row[0]) is not None
            and team_from_cell(row[2]) is not None
            and parse_score(row[1]["t"]) is not None)


def is_fixture_header(texts_lower: list[str]) -> bool:
    h = " ".join(texts_lower)
    return (("local" in h or "home" in h) and ("visitante" in h or "away" in h)
            and ("resultado" in h or "score" in h or "marcador" in h)
            and "jugador" not in h)


def find_matrix_tables(doc: BeautifulSoup) -> list[Tag]:
    """Matrices de resultados (era pre-2002): tabla cuadrada con códigos de equipo
    en el header y celdas de marcador/vacías."""
    import re

    from .normalize import parse_score

    out = []
    for t in all_tables(doc):
        grid = rows(t)
        n = len(grid)
        if n < 8 or any(len(r) < 8 for r in grid[:8]):
            continue
        if abs(n - len(grid[0])) > 3:
            continue
        header = grid[0][1:]
        short = sum(1 for c in header if len(c["t"]) <= 5 or c.get("href"))
        if short < 0.6 * len(header):
            continue
        scored = empty = 0
        for r in grid[1:6]:
            for c in r[1:]:
                if not c["t"]:
                    empty += 1
                elif parse_score(c["t"]):
                    scored += 1
        total = scored + empty
        if total > 0 and scored / total >= 0.4:
            out.append(t)
    return out


def find_fixture_tables(doc: BeautifulSoup) -> list[Tag]:
    """Tablas de partidos: encabezado con local/visitante + resultado/marcador
    (sin columna jugador, para excluir la tabla de tripletas)."""
    out = []
    for t in all_tables(doc):
        grid = rows(t)
        if len(grid) < 2:
            continue
        found = False
        for row in grid[:3]:
            if is_fixture_header([c["t"].lower() for c in row]):
                out.append(t)
                found = True
                break
        if found:
            continue
        # tablas sin encabezado: [local, resultado, visitante] posicional
        start = 1 if is_caption_row(grid[0]) else 0
        probe = [r for r in grid[start:start + 2] if _looks_match_row(r)]
        if len(probe) >= 2:
            out.append(t)
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
