"""Tests del paquete fpc_api."""
from fpc_api.normalize import match_position, match_team, parse_score, slugify
from fpc_api.players import assign_ids
from fpc_api.tables import rows, soup
from fpc_api.seasons import _playoff_stages, parse_matches, parse_playoffs
from fpc_api.validate import Warnings, validate_season


def test_slugify():
    assert slugify("Atlético Nacional") == "atletico-nacional"
    assert slugify("Atl. Nacional") == "atletico-nacional"
    assert slugify("Cúcuta Deportivo") == "cucuta-deportivo"
    assert slugify("Envigado F. C.") == "envigado-fc"


def test_match_team():
    assert match_team("Atl. Nacional") == "nacional"
    assert match_team("Independiente Santa Fe") == "santafe"
    assert match_team("Alianza Petrolera") == "alianza"
    assert match_team("Internacional de Bogotá") == "internacional-bogota"
    assert match_team("Fortaleza F. C.") == "fortaleza"
    try:
        match_team("Club Desconocido FC")
        assert False, "debió fallar"
    except ValueError:
        pass


def test_parse_score():
    assert parse_score("2–1") == (2, 1)
    assert parse_score("0 : 0") == (0, 0)
    assert parse_score("3:0 (3:0) (Global 4:2)") == (3, 0)
    assert parse_score("vs.") is None
    assert parse_score("") is None


def test_match_position():
    assert match_position("Portero") == "GK"
    assert match_position("Defensa central") == "DF"
    assert match_position("Volante ofensivo") == "MF"
    assert match_position("Delantero centro") == "FW"


HTML_STANDINGS = """
<table><tr><th>Pos.</th><th>Equipo</th><th>Pts.</th><th>PJ</th><th>G</th><th>E</th><th>P</th><th>GF</th><th>GC</th><th>Dif.</th></tr>
<tr><td>1</td><td><a href="/wiki/Atl%C3%A9tico_Nacional">Atlético Nacional</a></td><td>40</td><td>19</td><td>13</td><td>1</td><td>5</td><td>35</td><td>15</td><td>+20</td></tr>
<tr><td>2</td><td rowspan="2"><a href="/wiki/Junior_de_Barranquilla">Junior</a></td><td>35</td><td>19</td><td>11</td><td>2</td><td>6</td><td>31</td><td>24</td><td>+7</td></tr>
<tr><td>3</td><td>34</td><td>19</td><td>10</td><td>4</td><td>5</td><td>29</td><td>25</td><td>+4</td></tr>
</table>"""


def test_rows_rowspan():
    grid = rows(soup(HTML_STANDINGS).find("table"))
    assert len(grid) == 4
    # fila 3: el rowspan del equipo ocupa la col 1 con el valor "Junior"
    assert grid[3][0]["t"] == "3"
    assert grid[3][1]["t"] == "Junior"


def test_playoff_stages():
    assert _playoff_stages(1) == ["final"]
    assert _playoff_stages(3) == ["semifinales", "semifinales", "final"]
    assert _playoff_stages(7) == ["cuartos"] * 4 + ["semifinales"] * 2 + ["final"]
    assert _playoff_stages(0) == []


HTML_FIXTURE = """
<table>
<tr><td>Fecha 1</td><td></td><td></td></tr>
<tr><td>Local</td><td>Resultado</td><td>Visitante</td><td>Estadio</td><td>Fecha</td></tr>
<tr><td><a href="/wiki/Atl%C3%A9tico_Nacional">Nacional</a></td><td>2 : 0</td><td><a href="/wiki/Millonarios_F%C3%BAtbol_Club">Millonarios</a></td><td>Atanasio</td><td>16 de enero de 2026</td></tr>
<tr><td><a href="/wiki/Junior_de_Barranquilla">Junior</a></td><td>vs.</td><td><a href="/wiki/Deportes_Tolima">Tolima</a></td><td>Metropolitano</td></tr>
</table>"""


def test_parse_matches_truncated_row():
    grid = rows(soup(HTML_FIXTURE).find("table"))
    ms = parse_matches(grid, "2026-i", "regular", 2026, 1)
    assert len(ms) == 2
    played = [m for m in ms if m["status"] == "played"][0]
    assert played["home"] == "nacional" and played["away"] == "millonarios"
    assert played["home_goals"] == 2 and played["date"] == "2026-01-16"
    sched = [m for m in ms if m["status"] == "scheduled"][0]
    assert sched["home"] == "junior" and sched["home_goals"] is None


HTML_FINAL = """
<table class="vevent"><tr><td>12 de diciembre de 2025</td><td><a href="/wiki/Junior_de_Barranquilla">Junior</a></td><td>3:0 (3:0)</td><td><a href="/wiki/Deportes_Tolima">Tolima</a></td><td>Estadio</td><td></td></tr></table>
<table class="vevent"><tr><td>16 de diciembre de 2025</td><td><a href="/wiki/Deportes_Tolima">Tolima</a></td><td>0:1 (0:1)</td><td><a href="/wiki/Junior_de_Barranquilla">Junior</a></td><td>Estadio</td><td></td></tr></table>"""


def test_parse_playoffs_pairing():
    doc = soup(HTML_FINAL)
    ms = parse_playoffs(doc, "2025-ii", 2025)
    assert len(ms) == 2
    assert ms[0]["stage"] == "final" and ms[0]["leg"] == 1
    assert ms[1]["stage"] == "final" and ms[1]["leg"] == 2
    assert ms[1]["home_goals"] == 0 and ms[1]["away_goals"] == 1


def test_player_ids_stable_across_transfers():
    # el id es el nombre: si el jugador cambia de club, el id NO cambia
    w = []
    players = [{"name": "Javier Burrai", "team": "millonarios"}]
    assign_ids(players, w)
    players[0]["team"] = "nacional"  # traspaso
    assign_ids(players, w)
    assert players[0]["id"] == "javier-burrai"
    assert w == []


def test_player_ids_homonym_collision():
    w = []
    players = [
        {"name": "Kevin Pérez", "team": "equidad"},
        {"name": "Kevin Pérez", "team": "llaneros"},
        {"name": "Otro Jugador", "team": "cali"},
    ]
    assign_ids(players, w)
    assert players[0]["id"] == "kevin-perez-equidad"
    assert players[1]["id"] == "kevin-perez-llaneros"
    assert players[2]["id"] == "otro-jugador"
    assert any("homónimos" in x for x in w)


def make_season_data(**over):
    base = {
        "season": {"id": "2026-i"},
        "teams": ["a", "b"],
        "standings": [
            {"team": "a", "position": 1, "played": 2, "won": 2, "drawn": 0, "lost": 0,
             "goals_for": 4, "goals_against": 0, "goal_diff": 4, "points": 6},
            {"team": "b", "position": 2, "played": 2, "won": 0, "drawn": 0, "lost": 2,
             "goals_for": 0, "goals_against": 4, "goal_diff": -4, "points": 0},
        ],
        "matches": [
            {"id": "m1", "stage": "regular", "round": 1, "home": "a", "away": "b",
             "home_goals": 2, "away_goals": 0, "status": "played"},
            {"id": "m2", "stage": "regular", "round": 2, "home": "b", "away": "a",
             "home_goals": 0, "away_goals": 2, "status": "played"},
        ],
    }
    base.update(over)
    return base


def test_validate_ok():
    w = Warnings()
    assert validate_season(make_season_data(), w) == []


def test_validate_detects_corruption():
    data = make_season_data()
    data["standings"][0]["points"] = 5  # 3*PG+PE != puntos
    assert any("puntos" in e for e in validate_season(data, Warnings()))

    data = make_season_data()
    data["matches"][0]["away"] = "fantasma"  # equipo fuera del torneo
    errs = validate_season(data, Warnings())
    assert any("desconocido" in e for e in errs)

    data = make_season_data()
    data["matches"] = [m for m in data["matches"] if m["round"] != 2]  # desbalance standings
    w = Warnings()
    validate_season(data, w)
    assert any("PJ" in x for x in w.items)
