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
- Las temporadas 2002+ son dos torneos por año: `{year}-i` (Apertura) y `{year}-ii`
  (Finalización). Años de torneo único (pre-2002, 1995-96, 1996-97, 2020) usan `{year}`
  con `tournament: liga`.
- Etapas de partido (el formato cambió por décadas): `regular`, `cuadrangulares`,
  `liguilla`, `octogonal`, `hexagonal`, `pentagonales`, `triangulares`, `octavos`,
  `cuartos`, `semifinales`, `final`, `playoffs`, más `apertura`/`finalizacion` como
  fases internas de un año pre-2002.
- `status` de temporada: `completed` | `in_progress` | `cancelled` (1989, torneo suspendido).
- `status` de partido: `played` | `scheduled` (incluye aplazados).
- **Puntos**: 2 por victoria hasta 1994, 3 desde 1995; la era 1995-1998 trae bonus
  (columna `bonus`). Ver `validate.py` → `KNOWN_*_ISSUES` para las inconsistencias
  verificadas de la fuente (se publican tal cual, documentadas).

## Dataset Kaggle

`export/kaggle/` contiene el dataset plano listo para subir: 9 CSVs (~25.000 filas) +
`dataset-metadata.json` + `README.md` (tarjeta en inglés). Se regenera con:

```bash
PYTHONPATH=src python -m fpc_api.build kaggle   # o `build all` (lo incluye)
```

Cobertura actual: **103 temporadas (1948–2026), ~20.900 partidos, 60 clubes,
600 jugadores (plantillas vigentes), 101 ediciones de campeón**. La cobertura a
nivel partido antes de 2002 es parcial según lo documentado en Wikipedia —
`seasons.csv` (`n_matches`, `n_played`) dice exactamente qué trae cada temporada.

Subida manual (así se acordó: automatizar después):

```bash
pip install kaggle
# configura ~/.kaggle/kaggle.json con tu API token (kaggle.com → Settings → API)
kaggle datasets create -p export/kaggle
# nuevas versiones:
kaggle datasets version -p export/kaggle -m "update YYYY-MM-DD"
```

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

`SEASON_RANGE` en `src/fpc_api/build.py` define qué temporadas se construyen:
**1948–2026 completo** (103 temporadas). Los campeones cubren 1948–hoy. Casos
especiales documentados en el código: 2020 (un solo torneo), 1995-96/1996-97
(calendario europeo), 1989 (suspendido), era bonus 1995-1998, 2 puntos por
victoria hasta 1994.

## Roadmap

Ver **[roadmap.md](roadmap.md)** — incluye la fase v2: integración con API-Football para
stats de fantasy que Wikipedia no da (asistencias por partido, tarjetas, minutos,
alineaciones, fechas exactas para cerrar jornadas).

## Licencias

- Código: [MIT](LICENSE)
- Datos: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) — derivados de
  Wikipedia en español. Cita la fuente al reutilizar.
