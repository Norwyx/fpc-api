"""Normalización: slugs ASCII, alias de clubes, posiciones, marcadores."""
import re
import unicodedata

# slug canónico -> todas las variantes que pueden aparecer en cualquier fuente.
# Un nombre desconocido hace fallar el build a propósito (datos sucios no entran).
ALIASES: dict[str, list[str]] = {
    "nacional": ["atletico nacional", "atletico nacional sa", "nacional"],
    "millonarios": ["millonarios", "millonarios fc"],
    "santafe": ["independiente santa fe", "independiente santafe", "santa fe", "santafe"],
    "medellin": ["independiente medellin", "medellin", "deportivo independiente medellin"],
    "america": ["america de cali", "america", "corporacion deportiva america"],
    "cali": ["deportivo cali", "cali"],
    "junior": ["junior", "atletico junior", "junior de barranquilla", "junior fc"],
    "bucamanga": ["atletico bucaramanga", "bucaramanga"],
    "pasto": ["deportivo pasto"],
    "tolima": ["deportes tolima", "tolima"],
    "caldas": ["once caldas"],
    "envigado": ["envigado", "envigado fc", "envigado futbol club"],
    "equidad": ["la equidad", "la equidad seguros", "club la equidad seguros"],
    "pereira": ["deportivo pereira", "pereira"],
    "jaguares": ["jaguares de cordoba", "jaguares"],
    "alianza": ["alianza fc", "alianza petrolera", "alianza valledupar", "alianza"],
    "fortaleza": ["fortaleza cif", "fortaleza ceif", "fortaleza", "fortaleza futbol club"],
    "llaneros": ["llaneros", "llaneros fc"],
    "magdalena": ["union magdalena"],
    "chico": ["boyaca chico", "boyaca chico fc", "chico"],
    "patriotas": ["patriotas boyaca", "patriotas"],
    "aguilas": ["rionegro aguilas", "aguilas doradas", "rionegro aguilas doradas", "aguilas"],
    "cortulua": ["cortulua", "corporacion deportiva cortulua"],
    "huila": ["atletico huila", "huila"],
    "quindio": ["deportes quindio", "quindio"],
    "cucuta": ["cucuta deportivo", "cucuta"],
    "leones": ["leones fc", "leones"],
    "tigres": ["tigres fc", "tigres"],
    "real-cartagena": ["real cartagena", "real cartagena fc"],
    "valledupar": ["valledupar fc", "valledupar"],
    "real-soacha": ["real soacha cundinamarca", "real soacha", "soacha"],
    "barranquilla": ["barranquilla fc", "barranquilla"],
    "bogota": ["bogota fc", "bogota"],
    "internacional": ["internacional de palmira", "internacional fc de palmira"],
    "internacional-bogota": ["internacional de bogota", "internacional fc de bogota",
                             "internacional bogota", "internacional de bogota fc"],
    "oromana": ["oromana fc", "atletico oromana"],
    "uniautonoma": ["uniautonoma", "universidad autonoma del caribe"],
    "universitario": ["universitario de popayan", "universitario popayan"],
    "atletico": ["atletico fc", "atletico de cali"],
    "academia": ["academia fc", "academia"],
    "expreso-rojo": ["expreso rojo", "expreso rojo fc"],
    "real-santander": ["real santander", "real santander fc"],
    "deportivo-rionegro": ["deportivo rionegro", "rionegro"],
    "itague": ["itague ditaires", "itague", "itague ditaires deportivo"],
    "deportes-savio": ["deportes savio", "savio"],
    "centro-juvenil": ["centro juvenil padre luna", "centro juvenil"],
    "deportivo-antioquia": ["deportivo antioquia"],
    "atletico-de-la-sabana": ["atletico de la sabana", "de la sabana"],
}

# abreviaturas comunes antes de slugify
_ABBREV = [
    (r"\batl\.?\b", "atletico"),
    (r"\bdep\.?\b", "deportivo"),
    (r"\bind\.?\b", "independiente"),
    (r"\bclub\b", ""),
    (r"\bc\.?\s?d\.?\b", ""),
    (r"\bf\.?\s?c\.?\b", "fc"),
]


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    for pat, rep in _ABBREV:
        text = re.sub(pat, rep, text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


_ALIAS_INDEX: dict[str, str] | None = None


def _index() -> dict[str, str]:
    global _ALIAS_INDEX
    if _ALIAS_INDEX is None:
        _ALIAS_INDEX = {}
        for canon, variants in ALIASES.items():
            for v in [canon.replace("-", " ")] + variants:
                _ALIAS_INDEX.setdefault(slugify(v), canon)
    return _ALIAS_INDEX


def match_team(name: str) -> str:
    """Nombre del club (cualquier fuente) -> slug canónico. Falla si es desconocido."""
    s = slugify(name)
    idx = _index()
    hit = idx.get(s)
    if hit:
        return hit
    # "Club X F.C." y "Club X" son el mismo club en Colombia: prueba sin sufijo -fc
    hit = idx.get(s.removesuffix("-fc"))
    if hit:
        return hit
    raise ValueError(
        f"Club desconocido: {name!r} (slug={s!r}) — agrega el alias en normalize.py ALIASES"
    )


def is_known_team(name: str) -> bool:
    try:
        match_team(name)
        return True
    except ValueError:
        return False


# --- posiciones fantasy estándar ---

_POSITIONS = [
    (r"portero|arquero|guardameta", "GK"),
    (r"defensa|defensor|lateral|central|carrilero|zaguero", "DF"),
    (r"mediocampista|medio|volante|centrocampista|pivote|interior|medio?", "MF"),
    (r"delantero|extremo|punta|ariete|atacante", "FW"),
]


def match_position(raw: str | None) -> str | None:
    if not raw:
        return None
    t = slugify(raw)
    for pat, code in _POSITIONS:
        if re.search(pat, t):
            return code
    return None


_SCORE = re.compile(r"(\d+)\s*[–—:\-]\s*(\d+)")


def parse_score(text: str) -> tuple[int, int] | None:
    m = _SCORE.search(text or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def clean_name(raw: str) -> str:
    """Nombres de jugador: quita marcadores de capitán, notas y espacios dobles."""
    t = re.sub(r"\((c)\)|\[.*?\]|\u2020", "", raw or "")
    t = re.sub(r"\s+", " ", t).strip(" .")
    return t
