# FPC API ⚽🇨🇴

**La primera API pública, abierta y estandarizada de datos del fútbol profesional colombiano
(Categoría Primera A — Liga BetPlay Dimayor).**

No existe una base de datos estandarizada del FPC. Esta API la crea: datos estructurados en
JSON, actualizados automáticamente cada día desde Wikipedia, servidos gratis vía GitHub Pages
y versionados en Git. Pensada como base de datos para una futura app de **FPC Fantasy**
(estilo Fantasy Premier League) — y para cualquier desarrollador, periodista o analista.

> Proyecto independiente, no afiliado a DIMAYOR ni a la Federación Colombiana de Fútbol.

---

## Consumo rápido

Una vez publicado el repo (con GitHub Pages activado):

```bash
# Catálogo de la API
curl -s https://Norwyx.github.io/fpc-api/v1/index.json

# Clubes (activos e históricos, con ciudad, estadio, fundación y colores)
curl -s https://Norwyx.github.io/fpc-api/v1/teams.json

# Una temporada: standings, partidos con fecha y marcador, goleadores, asistencias
curl -s https://Norwyx.github.io/fpc-api/v1/seasons/2026-i.json

# Campeones de toda la era profesional (1948–hoy)
curl -s https://Norwyx.github.io/fpc-api/v1/champions.json
```

Sin Pages también funciona (CORS incluido en `raw.githubusercontent.com`):

```bash
curl -s https://raw.githubusercontent.com/Norwyx/fpc-api/main/docs/v1/teams.json
```

JavaScript:

```js
const seasons = await fetch("https://Norwyx.github.io/fpc-api/v1/seasons.json").then(r => r.json());
const season  = await fetch(`https://Norwyx.github.io/fpc-api/v1/seasons/2026-ii.json`).then(r => r.json());
season.matches.filter(m => m.status === "played" && m.round === 7);
```

Navegador visual de la API: **`docs/index.html`** (se sirve en la raíz de Pages).

## Modelo de datos

| Endpoint | Contenido |
|---|---|
| `/v1/index.json` | Catálogo: endpoints, temporadas, timestamps |
| `/v1/teams.json` | Clubes: id, nombre, ciudad, estadio, capacidad, fundación, colores, Wikipedia, `active` |
| `/v1/players.json` | Plantillas vigentes (best-effort): nombre, equipo, posición GK/DF/MF/FW, dorsal, edad |
| `/v1/seasons.json` | Índice de temporadas |
| `/v1/seasons/{año}-{i\|ii}.json` | Posiciones, partidos (marcador, jornada, etapa, fecha), goleadores y asistencias, campeón |
| `/v1/champions.json` | Campeón, subcampeón, marcador de final y goleador por edición desde 1948 |

Reglas del modelo:

- **IDs canónicos** de clubes: slugs ASCII estables (`nacional`, `millonarios`, `santafe`…).
- **IDs de jugadores**: slug del nombre (`javier-burrai`) — **estable ante traspasos** (el
  club vive en el campo `team`, no en el id). Si dos jugadores distintos comparten nombre,
  ambos llevan sufijo del club (`luis-palacios-pereira`, `luis-palacios-santafe`) y se
  reporta en `meta.warnings`. En v2 se migrará a IDs numéricos de API-Football como clave
  canónica para el historial de fantasy.
- `null` explícito cuando la fuente no da un dato (ej. `date` de partidos aplazados). Nunca se inventa.
- Las temporadas colombianas son dos torneos por año: `{year}-i` (Apertura) y `{year}-ii` (Finalización).
- Etapas de partido: `regular`, `cuadrangulares`, `octavos`, `cuartos`, `semifinales`, `final` (según el formato del torneo).
- `status` de partido: `played` | `scheduled` (incluye aplazados).

## Cómo se actualiza

1. **GitHub Actions** corre `python -m fpc_api.build all` todos los días a las 9:00 a.m. (Colombia).
2. Si los datos cambiaron, hace commit automático (`data: update <fecha>`).
3. GitHub Pages publica el JSON nuevo en minutos.

Los datos son **validados antes de publicarse**: PG+PE+PP=PJ, 3·PG+PE=puntos, ΣGF=ΣGC,
equipos de standings ⇄ partidos, claves únicas, etc. Si Wikipedia cambia de formato y el
parser se rompe, la validación falla y el build queda rojo (no se publica basura).

## Desarrollo local

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

PYTHONPATH=src python -m fpc_api.build all      # genera docs/v1/*.json (cachea en data/raw/)
PYTHONPATH=src python -m fpc_api.build seasons --years 2025   # solo un año
PYTHONPATH=src python -m fpc_api.validate       # valida lo generado
PYTHONPATH=src python -m tests.run              # tests offline
PYTHONPATH=src python -m fpc_api.debug "Torneo Apertura 2026 (Colombia)" tables  # inspección
```

Única dependencia: `beautifulsoup4`. El HTTP es `urllib` (stdlib) con caché en disco.

## Backfill histórico

`SEASON_RANGE` en `src/fpc_api/build.py` define qué temporadas se construyen. Hoy: 2024–2026.
Para ampliar hacia atrás, añade años a la lista (el pipeline resuelve las páginas
`Torneo Apertura/Finalización {año} (Colombia)` automáticamente). Los campeones ya cubren
1948–hoy completos.

## Roadmap

Ver **[roadmap.md](roadmap.md)** — incluye la fase v2: integración con API-Football para
stats de fantasy que Wikipedia no da (asistencias por partido, tarjetas, minutos,
alineaciones, fechas exactas para cerrar jornadas).

## Licencias

- Código: [MIT](LICENSE)
- Datos: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) — derivados de
  Wikipedia en español. Cita la fuente al reutilizar.
