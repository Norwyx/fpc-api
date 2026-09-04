"""Clubes: tabla de participantes vigente + infobox de cada club + colores curados."""
import re
from datetime import datetime, timezone
from urllib.parse import unquote

from . import wiki
from .normalize import match_team
from .tables import infobox_data, rows, soup

PAGE = "Categoría Primera A"

# Colores primarios/secundarios curados a mano (Wikipedia no los da estructurados).
COLORS: dict[str, dict[str, str]] = {
    "nacional": {"primary": "#00A859", "secondary": "#FFFFFF"},
    "millonarios": {"primary": "#0B4EA2", "secondary": "#FFFFFF"},
    "santafe": {"primary": "#E31B23", "secondary": "#FFFFFF"},
    "medellin": {"primary": "#E4032E", "secondary": "#0B4EA2"},
    "america": {"primary": "#E30613", "secondary": "#FFFFFF"},
    "cali": {"primary": "#00954C", "secondary": "#FFFFFF"},
    "junior": {"primary": "#C8102E", "secondary": "#FFFFFF"},
    "bucamanga": {"primary": "#FFC72C", "secondary": "#006F44"},
    "pasto": {"primary": "#E4002B", "secondary": "#FFFFFF"},
    "tolima": {"primary": "#C8102E", "secondary": "#FFFFFF"},
    "caldas": {"primary": "#FFFFFF", "secondary": "#DA291C"},
    "envigado": {"primary": "#F58220", "secondary": "#FFFFFF"},
    "equidad": {"primary": "#00843D", "secondary": "#FFFFFF"},
    "pereira": {"primary": "#FFD200", "secondary": "#000000"},
    "jaguares": {"primary": "#C8102E", "secondary": "#000000"},
    "alianza": {"primary": "#FFC72C", "secondary": "#000000"},
    "fortaleza": {"primary": "#0B4EA2", "secondary": "#FFFFFF"},
    "llaneros": {"primary": "#00843D", "secondary": "#FFFFFF"},
    "magdalena": {"primary": "#CE1126", "secondary": "#FFFFFF"},
    "chico": {"primary": "#0B5ED7", "secondary": "#FFFFFF"},
    "patriotas": {"primary": "#FFD100", "secondary": "#00843D"},
    "aguilas": {"primary": "#EAAA00", "secondary": "#000000"},
    "cortulua": {"primary": "#F26522", "secondary": "#00843D"},
    "huila": {"primary": "#00843D", "secondary": "#FFFFFF"},
    "quindio": {"primary": "#C8102E", "secondary": "#0B4EA2"},
    "cucuta": {"primary": "#D6001C", "secondary": "#000000"},
}

SHORT_NAMES = {
    "nacional": "Nacional", "millonarios": "Millonarios", "santafe": "Santa Fe",
    "medellin": "Medellín", "america": "América", "cali": "Cali", "junior": "Junior",
    "bucamanga": "Bucaramanga", "pasto": "Pasto", "tolima": "Tolima",
    "caldas": "Once Caldas", "envigado": "Envigado", "equidad": "La Equidad",
    "pereira": "Pereira", "jaguares": "Jaguares", "alianza": "Alianza",
    "fortaleza": "Fortaleza", "llaneros": "Llaneros", "magdalena": "Unión Magdalena",
    "chico": "Chicó", "patriotas": "Patriotas", "aguilas": "Águilas",
    "cortulua": "Cortuluá", "huila": "Huila", "quindio": "Quindío", "cucuta": "Cúcuta",
    "real-cartagena": "Real Cartagena", "valledupar": "Valledupar",
    "real-soacha": "Real Soacha", "leones": "Leones", "tigres": "Tigres",
    "barranquilla": "Barranquilla", "bogota": "Bogotá", "internacional": "Palmira",
    "uniautonoma": "Uniautónoma", "universitario": "Universitario",
    "deportivo-rionegro": "Deportivo Rionegro", "itague": "Itagüí",
    "deportes-savio": "Savio", "expreso-rojo": "Expreso Rojo", "academia": "Academia",
    "atletico": "Atlético", "oromana": "Oromana", "real-santander": "Real Santander",
    "atletico-de-la-sabana": "De La Sabana", "centro-juvenil": "Centro Juvenil",
    "deportivo-antioquia": "Deportivo Antioquia", "fortaleza-fc": "Fortaleza",
    "internacional-bogota": "Internacional",
}


def _meta() -> dict:
    return {
        "version": 1,
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": f"https://es.wikipedia.org/wiki/{PAGE.replace(' ', '_')}",
    }


def _teams_table(doc) -> list[dict]:
    """Tabla 'Equipo Entrenador Ciudad Estadio Aforo' de la página principal."""
    out = []
    for t in doc.find_all("table"):
        grid = rows(t)
        if len(grid) < 15:
            continue
        header = [c["t"].lower() for c in grid[0]]
        col_eq = next((i for i, h in enumerate(header) if h.startswith("equipo")), None)
        col_city = next((i for i, h in enumerate(header) if "ciudad" in h), None)
        col_stad = next((i for i, h in enumerate(header) if "estadio" in h), None)
        col_aforo = next((i for i, h in enumerate(header) if "aforo" in h or "capacidad" in h), None)
        if col_eq is None:
            continue
        from .tables import as_int

        for row in grid[1:]:
            if len(row) <= col_eq:
                continue
            cell = row[col_eq]
            if not cell["t"]:
                continue
            slug = None
            for href in (cell.get("hrefs") or ([cell["href"]] if cell.get("href") else [])):
                try:
                    slug = match_team(unquote(href.split("/wiki/")[-1].replace("_", " ")))
                    break
                except ValueError:
                    continue
            if slug is None:
                try:
                    slug = match_team(cell["t"])
                except ValueError:
                    continue
            out.append({
                "slug": slug,
                "name": cell["t"],
                "wiki_title": cell.get("href"),
                "city": row[col_city]["t"] if col_city is not None and col_city < len(row) else None,
                "stadium": row[col_stad]["t"] if col_stad is not None and col_stad < len(row) else None,
                "capacity": as_int(row[col_aforo]["t"]) if col_aforo is not None and col_aforo < len(row) else None,
            })
        if out:
            break
    return out


def _club_extra(wiki_href: str | None) -> dict:
    """Fundación desde el infobox de la página del club."""
    if not wiki_href:
        return {}
    title = unquote(wiki_href.split("/wiki/")[-1]).replace("_", " ")
    got = wiki.page_html(title)
    if not got:
        return {}
    box = infobox_data(soup(got[1]))
    founded = None
    for key, val in box.items():
        if key.startswith("fund"):
            m = re.search(r"\b(18|19|20)\d{2}\b", val["t"])
            founded = int(m.group()) if m else None
            break
    return {"founded": founded}


def build() -> dict:
    got = wiki.page_html(PAGE)
    if not got:
        raise RuntimeError(f"No se pudo cargar '{PAGE}'")
    _, html = got
    doc = soup(html)

    teams: dict[str, dict] = {}
    for t in _teams_table(doc):
        slug = t["slug"]
        wiki_title = (unquote(t["wiki_title"].split("/wiki/")[-1]).replace("_", " ")
                      if t["wiki_title"] else None)
        teams[slug] = {
            "id": slug,
            "name": t["name"],
            "short_name": SHORT_NAMES.get(slug, slug.replace("-", " ").title()),
            "city": t["city"],
            "stadium": t["stadium"],
            "capacity": t["capacity"],
            **_club_extra(t["wiki_title"]),
            "colors": COLORS.get(slug),
            "wikipedia": f"https://es.wikipedia.org/wiki/{t['wiki_title']}" if t["wiki_title"] else None,
            "active": True,
        }

    # clubes históricos (de la lista de campeones) quedan como referencia mínima
    from .champions import champions_raw

    for c in champions_raw():
        for key in ("champion", "runner_up"):
            slug = c[key]
            if slug and slug not in teams:
                teams[slug] = {
                    "id": slug,
                    "name": c[f"{key}_name"] or SHORT_NAMES.get(slug, slug),
                    "short_name": SHORT_NAMES.get(slug, slug.replace("-", " ").title()),
                    "city": None, "stadium": None, "capacity": None, "founded": None,
                    "colors": COLORS.get(slug), "wikipedia": None, "active": False,
                }

    # resto del catálogo histórico (descendidos sin título, etc.)
    for slug, short in SHORT_NAMES.items():
        if slug not in teams:
            teams[slug] = {
                "id": slug, "name": short, "short_name": short,
                "city": None, "stadium": None, "capacity": None, "founded": None,
                "colors": COLORS.get(slug), "wikipedia": None, "active": False,
            }

    return {
        "meta": _meta(),
        "teams": sorted(teams.values(), key=lambda t: (not t["active"], t["id"])),
    }
