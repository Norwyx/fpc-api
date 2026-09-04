"""Cliente mínimo de la API de MediaWiki (es.wikipedia.org)."""
import json
from urllib.parse import quote, urlencode

from .http import get, json_get

API = "https://es.wikipedia.org/w/api.php"


def page_html(title: str, max_age_days: float = 7.0) -> tuple[str, str] | None:
    """(título resuelto, HTML del cuerpo) o None si la página no existe."""
    from .normalize import slugify

    params = urlencode({
        "action": "parse", "page": title, "prop": "text",
        "format": "json", "formatversion": "2", "redirects": "1",
    })
    data = json_get(f"{API}?{params}", cache_key=f"page_{slugify(title)}", max_age_days=max_age_days)
    if "error" in data:
        return None
    return data["parse"]["title"], data["parse"]["text"]


def search(query: str, limit: int = 5) -> list[str]:
    """Títulos que coinciden con una búsqueda (para resolver nombres de artículos)."""
    params = urlencode({
        "action": "query", "list": "search", "srsearch": query,
        "srlimit": limit, "format": "json", "formatversion": "2",
    })
    data = json_get(f"{API}?{params}", cache_key=f"search_{quote(query)}", max_age_days=7.0)
    return [hit["title"] for hit in data.get("query", {}).get("search", [])]


def resolve(title_candidates: list[str]) -> str | None:
    """Prueba títulos candidatos (redirects incluidos); devuelve el primero que exista."""
    for t in title_candidates:
        if page_html(t, max_age_days=30.0) is not None:
            return t
    return None
