"""Normalización: slugs ASCII, alias de clubes, posiciones, marcadores."""
import re
import unicodedata

# slug canónico -> todas las variantes que pueden aparecer en cualquier fuente.
# Un nombre desconocido hace fallar el build a propósito (datos sucios no entran).
ALIASES: dict[str, list[str]] = {
    # NOTA: incluye typos reales de Wikipedia ("milonarios", "bucarramanga") para no perder partidos
    "nacional": ["atletico nacional", "atletico nacional sa", "nacional",
                 "atletico municipal", "atletico municipal de medellin"],
    "millonarios": ["millonarios", "millonarios fc", "milonarios"],
    "santafe": ["independiente santa fe", "independiente santafe", "santa fe", "santafe"],
    "medellin": ["independiente medellin", "medellin", "deportivo independiente medellin"],
    "america": ["america de cali", "america", "corporacion deportiva america"],
    "cali": ["deportivo cali", "cali"],
    "junior": ["junior", "atletico junior", "junior de barranquilla", "junior fc"],
    "bucaramanga": ["atletico bucaramanga", "bucaramanga", "bucamanga", "bucarramanga"],
    "pasto": ["deportivo pasto"],
    "tolima": ["deportes tolima", "tolima", "ibague"],
    "caldas": ["once caldas", "caldas", "manizales", "deportes caldas"],
    "barranquilla-fc": ["barranquilla fc"],
    # era El Dorado (1948-1953): clubes efímeros + "Barranquilla" solo = Deportivo Barranquilla
    # (el Barranquilla FC moderno siempre aparece con "FC"; verificado 2010+)
    "deportivo-barranquilla": ["deportivo barranquilla", "barranquilla"],
    "huracan": ["huracan", "huracan de medellin"],
    "samarios": ["samarios", "deportivo samarios"],
    "atletico-manizales": ["atletico manizales"],
    "oro-negro": ["oro negro", "club deportivo oro negro"],
    "deportivo-manizales": ["deportivo manizales"],
    "unicosta": ["unicosta", "deportivo unicosta", "unicosta de barranquilla"],
    "huila": ["atletico huila", "huila", "neiva"],
    "chico": ["boyaca chico", "boyaca chico fc", "chico", "bogota chico", "chico fc"],
    "centauros": ["centauros villavicencio", "centauros"],
    "envigado": ["envigado", "envigado fc", "envigado futbol club"],
    "equidad": ["la equidad", "la equidad seguros", "club la equidad seguros", "equidad"],
    "pereira": ["deportivo pereira", "pereira"],
    "jaguares": ["jaguares de cordoba", "jaguares"],
    "alianza": ["alianza fc", "alianza petrolera", "alianza valledupar", "alianza"],
    "fortaleza": ["fortaleza cif", "fortaleza ceif", "fortaleza", "fortaleza futbol club"],
    "llaneros": ["llaneros", "llaneros fc"],
    "magdalena": ["union magdalena", "magdalena"],
    "patriotas": ["patriotas boyaca", "patriotas"],
    "aguilas": ["rionegro aguilas", "aguilas doradas", "rionegro aguilas doradas", "aguilas",
                # misma franquicia reubicada: Itagüí (2011-2013) -> Águilas Pereira (2014)
                # ("Itagüí" lleva diéresis: slugifica a "itagui")
                "itagui", "itagui ditaires", "corporacion deportiva itagui ditaires",
                "aguilas pereira"],
    "cortulua": ["cortulua", "corporacion deportiva cortulua", "tulua"],
    "quindio": ["deportes quindio", "quindio", "atletico quindio"],
    "cucuta": ["cucuta deportivo", "cucuta", "deportivo cucuta"],
    "leones": ["leones fc", "leones", "itague leones", "itagui leones"],
    "tigres": ["tigres fc", "tigres"],
    "real-cartagena": ["real cartagena", "real cartagena fc", "cartagena"],
    "sporting": ["sporting", "sporting club", "sporting de barranquilla", "sporting barranquilla"],
    # era amateur/profesional temprana
    "universidad": ["universidad nacional", "universidad", "club universidad nacional",
                    "club universidad nacional de colombia"],
    "once-deportivo": ["once deportivo", "once deportivo de manizales"],
    "boca-cali": ["boca juniors de cali", "boca juniors", "boca de cali", "boca cali"],
    "valledupar": ["valledupar fc", "valledupar"],
    "real-soacha": ["real soacha cundinamarca", "real soacha", "soacha"],
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
    "deportes-savio": ["deportes savio", "savio"],
    "centro-juvenil": ["centro juvenil padre luna", "centro juvenil"],
    "deportivo-antioquia": ["deportivo antioquia"],
    "atletico-de-la-sabana": ["atletico de la sabana", "de la sabana"],
}

# abreviaturas comunes antes de slugify ("At. Nacional", "Dep. Cali", "Ind. Medellín")
_ABBREV = [
    (r"\batl?\.?\b", "atletico"),
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
    # "Club X F.C." / "Club X Fútbol Club" son el mismo club que "Club X" en Colombia
    for cand in (s, s.removesuffix("-fc"), s.removesuffix("-futbol")):
        hit = idx.get(cand)
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
    # quita penales y agregados ("1(1)-1(3)", "3:0 (3:0) (Global 4:2)") -> marcador del partido
    clean = re.sub(r"\([^)]*\)", "", text or "")
    m = _SCORE.search(clean)
    return (int(m.group(1)), int(m.group(2))) if m else None


def clean_name(raw: str) -> str:
    """Nombres de jugador: quita marcadores de capitán, notas, goles pegados y espacios."""
    t = re.sub(r"\((c)\)|\[.*?\]|\u2020", "", raw or "")
    t = re.sub(r"\s*\(\d+\)\s*$", "", t)  # "Felipe Marino (22)" -> nombre
    t = re.sub(r"\s+", " ", t).strip(" .")
    return t
