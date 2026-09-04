# Roadmap — FPC API (Fútbol Profesional Colombiano)

> La primera API pública, abierta y estandarizada de datos del fútbol profesional colombiano
> (Categoría Primera A — Liga BetPlay Dimayor), construida para servir como base de datos
> oficial de un futuro **FPC Fantasy** (estilo Fantasy Premier League).

---

## 1. Visión y objetivo

**Problema:** no existe una base de datos estandarizada, abierta y actualizable del fútbol
profesional colombiano. Los datos están dispersos en Wikipedia, DIMAYOR, Sofascore,
Transfermarkt, API-Football (de pago), etc., con formatos inconsistentes.

**Solución:** una **API estática hospedada en GitHub** (patrón "static JSON API", igual que
openfootball y football.db):

- Los datos viven como archivos JSON versionados en el repo.
- Scripts de Python los extraen de Wikipedia (fuente libre, estable, sin API key).
- GitHub Actions regenera los datos automáticamente (daily cron) y hace commit si cambian.
- GitHub Pages sirve el JSON con CORS habilitado → cualquier app puede consumirla directo.

**Por qué estática y no un servidor:**

| Criterio | API estática (JSON + Pages) | Servidor (FastAPI/Firebase) |
|---|---|---|
| Costo | $0 | $0–$$ |
| Mantenimiento | Cero (no hay proceso corriendo) | Deploys, uptime, DB |
| Versionado de datos | Git nativo (diff por commit) | Requiere diseño |
| Suficiente para el volumen? | Sí: 20 equipos × ~480 partidos/año → KB de JSON | Overkill |
| CORS | Sí (Pages lo habilita) | Config manual |

El volumen del FPC es pequeño (20 equipos, ~380 partidos por torneo, ~500 jugadores activos).
Un JSON filtrable del lado cliente es más rápido y barato que una API con servidor.

---

## 2. Alcance

### v1 (este repo, MVP funcional end-to-end)

- `teams.json` — los 20 clubes de Primera A: id, nombre, alias, ciudad, estadio, fundación,
  colores, Wikipedia.
- `players.json` — plantillas actuales (best-effort desde Wikipedia): id, nombre, equipo,
  posición, dorsal.
- `seasons/{año}-{torneo}.json` — por cada torneo (Apertura / Finalización): tabla de
  posiciones, resultados de partidos (marcador + jornada), goleadores, campeón.
- `champions.json` — todos los campeones de la era profesional (1948–hoy), con subcampeón.
- Validadores que garantizan consistencia (los datos NO entran si no cuadran: PG+PE+PP=PJ,
  goles a favor/contra coinciden con partidos, 20 equipos, etc.).
- CI/CD: tests + validación en cada PR; actualización diaria automática; Pages deploy.
- `docs/index.html` — navegador de la API (documentación viva, consume el JSON real).

### v1.5 (post-MVP, mismo repo)

- Backfill histórico: temporadas 2010–2023 (mismo pipeline, más alias).
- Stats por partido con fechas reales cuando existan en la fuente.
- Fuente secundaria opcional (TheSportsDB free tier) para enriquecer logos/metadatos.

### v2 — Fase Fantasy (base de datos lista para la app)

- **API-Football (api-football.com, tier gratuito: 100 req/día)** como fuente de stats que
  Wikipedia no tiene: asistencias, tarjetas, minutos, alineaciones, fechas exactas de fixture.
  - Sync semanal solo de la jornada en curso → cabe de sobra en el tier gratis.
  - Mapear jugadores API-Football ↔ jugadores de esta API por nombre normalizado.
- Modelo de puntuación fantasy (goles, asistencias, tarjetas, portería a cero, penal fallado…).
- Precios/ratings de jugadores para el juego.
- Datos por jornada (fecha exacta del partido) para cerrar alineaciones semanalmente.

---

## 3. Decisiones técnicas

- **Lenguaje:** Python 3.14 (stdlib-first). Única dependencia de scraping: `beautifulsoup4`
  (parseo robusto de tablas HTML; escribir esto con regex/stdlib sería frágil y más largo).
- **HTTP:** `urllib.request` (stdlib) con User-Agent identificable (cortesía de Wikipedia) y
  **caché en disco** (`data/raw/`) para no re-descargar en cada corrida ni en CI.
- **Fuentes (prioridad):**
  1. Wikipedia en español (`es.wikipedia.org/w/api.php`): equipos, temporadas, resultados,
     goleadores, plantillas, campeones. Libre, estable, sin key, con historial completo.
  2. (Fase v2) API-Football para stats fantasy no disponibles en Wikipedia.
- **IDs canónicos:** slugs ASCII estables por equipo (`nacional`, `millonarios`, `santafe`…).
  Un mapa de alias en código traduce las variantes que usa cada fuente ("Atl. Nacional",
  "Independiente Santa Fe", "Alianza Petrolera" → `alianza`, etc.). Si llega un nombre
  desconocido, el build **falla** en vez de silenciar datos sucios → se agrega el alias.
- **Formato de temporada:** `{año}-{apertura|finalizacion}` en archivos
  `seasons/{año}-{i|ii}.json`. Colombia juega dos campeones por año (desde 2002).
- **Tolerancia a datos faltantes:** `null` explícito (ej. `date: null` cuando la fuente no
  da fecha). Nunca se inventan datos.

---

## 4. Modelo de datos (contrato de la API)

### `GET /v1/teams.json`
```json
{
  "meta": { "version": 1, "updated": "2026-09-03T14:00:00Z", "source": "es.wikipedia.org" },
  "teams": [
    {
      "id": "nacional",
      "name": "Atlético Nacional",
      "short_name": "Nacional",
      "aliases": ["Atl. Nacional", "Nacional"],
      "city": "Medellín",
      "stadium": "Estadio Atanasio Girardot",
      "founded": 1947,
      "colors": { "primary": "#00B34B", "secondary": "#FFFFFF" },
      "wikipedia": "https://es.wikipedia.org/wiki/Atlético_Nacional",
      "active": true
    }
  ]
}
```

### `GET /v1/seasons/{año}-{i|ii}.json`
```json
{
  "meta": { "version": 1, "updated": "2026-09-03T14:00:00Z" },
  "season": { "id": "2026-ii", "year": 2026, "tournament": "finalizacion", "status": "in_progress" },
  "champion": null,
  "standings": [
    { "team": "nacional", "position": 1, "played": 10, "won": 7, "drawn": 2, "lost": 1,
      "goals_for": 19, "goals_against": 7, "goal_diff": 12, "points": 23 }
  ],
  "matches": [
    { "id": "2026-ii-r1-nacional-millonarios", "round": 1, "stage": "regular",
      "date": null, "home": "nacional", "away": "millonarios", "home_goals": 2, "away_goals": 1 }
  ],
  "scorers": [
    { "player_name": "Alfredo Morelos", "team": "millonarios", "goals": 8 }
  ]
}
```

### `GET /v1/players.json`
```json
{
  "meta": { "version": 1, "updated": "2026-09-03T14:00:00Z" },
  "players": [
    { "id": "david-ospina", "name": "David Ospina", "team": "nacional",
      "position": "GK", "shirt_number": 1, "source": "wikipedia" }
  ]
}
```

### `GET /v1/champions.json`
```json
{
  "meta": { "version": 1, "updated": "2026-09-03T14:00:00Z" },
  "champions": [
    { "year": 1948, "tournament": "liga", "champion": "santafe", "runner_up": "junior", "score": "4–1" }
  ]
}
```

### `GET /v1/index.json`
Catálogo auto-descriptivo: lista de endpoints, temporadas disponibles y timestamps.
`docs/index.html` lo consume y renderiza la documentación viva.

---

## 5. Fases de construcción (orden de implementación)

### Fase 0 — Fundaciones
- [x] `git init`, `.gitignore` (venv, caché), `LICENSE` (MIT), `requirements.txt`.
- [x] Estructura:
```
fpc-api/
├── docs/                  # GitHub Pages: la API vive aquí
│   ├── index.html         # navegador de la API
│   └── v1/                # ← salida de todos los builds (JSON)
├── src/fpc_api/           # el paquete Python
│   ├── http.py            # fetch con caché + UA
│   ├── wiki.py            # client API de MediaWiki (parse/search)
│   ├── tables.py          # extracción de wikitables (rowspan-aware)
│   ├── normalize.py       # slugs, alias de equipos, posiciones, fechas
│   ├── teams.py           # build teams.json
│   ├── seasons.py         # build seasons/*.json
│   ├── champions.py       # build champions.json
│   ├── players.py         # build players.json
│   ├── validate.py        # reglas de consistencia (CI bloqueante)
│   ├── build.py           # CLI: python -m fpc_api.build all
│   └── debug.py           # inspección de tablas al desarrollar
├── tests/                 # asserts sin framework
├── data/raw/              # caché de HTML descargado (git-ignored)
├── .github/workflows/     # ci.yml, update.yml, pages.yml
├── roadmap.md · README.md · LICENSE · requirements.txt
```

### Fase 1 — Normalización y clientes
- [x] `http.py`: GET con caché TTL + User-Agent + reintentos.
- [x] `wiki.py`: `page_html(título)` y `search(título)` sobre `es.wikipedia.org/w/api.php`.
- [x] `tables.py`: localizar wikitables por encabezados esperados; expandir `rowspan`;
      leer matrices de resultados (equipo×equipo → lista de partidos).
- [x] `normalize.py`: slugify ASCII + mapa de alias (los ~40 clubes históricos de Primera A)
      + posiciones (GK/DF/MF/FW) + parseo de marcadores "2–1".

### Fase 2 — Equipos (`teams.json`)
- [x] Fuente: tabla de equipos de la página *Categoría Primera A* (o de la temporada vigente).
- [x] Enriquecimiento: infobox de la página de cada club (fundación, estadio, ciudad).
- [x] Colores primarios curados a mano (20 clubes) — Wikipedia no los da estructurados.

### Fase 3 — Campeones históricos (`champions.json`)
- [x] Fuente: *Anexo:Campeones del fútbol profesional colombiano* (1948–hoy).
- [x] Mapeo de nombres históricos al slug canónico.

### Fase 4 — Temporadas (`seasons/*.json`) — el corazón
- [x] Resolver la página de cada torneo: `Torneo Apertura/Finalización {año} (Colombia)`
      (con fallback de búsqueda si el título cambia).
- [x] Parsear: tabla de posiciones (primera fase), matriz de resultados → partidos con
      jornada, cuadrangulares, goleadores, campeón/subcampeón.
- [x] Alcance inicial: **2024-I a 2026-II** (6 torneos). El resto es backfill progresivo.
- [x] Fechas de partido: `null` cuando la fuente no las da (se añaden en fase v2 con
      API-Football).

### Fase 5 — Plantillas (`players.json`) — best-effort
- [x] Fuente: sección "Plantilla" de la página Wikipedia de cada club.
- [x] Falla suave: si un club no parsea, se registra warning y sigue (no bloquea el build).

### Fase 6 — Validación (el escudo de calidad)
- [x] `validate.py`: 
  - teams: 20 activos, ids únicos, slugs ASCII.
  - standings: PG+PE+PP = PJ; 3×PG+PE = puntos; ΣGF = ΣGC; posiciones sin huecos.
  - matches: cada equipo juega 2×(n-1) partidos en fase regular; marcadores ≥ 0;
    goles de standings = goles de partidos (cuando ambos existen).
  - champions: años consecutivos 1948→hoy, campeón ∈ equipos conocidos.
- [x] `tests/`: asserts sin framework (corre con `python -m tests.run`), casos offline
      con HTML de ejemplo (no golpean la red).

### Fase 7 — La API servida
- [x] Salida del build → `docs/v1/*.json` (fuente única de verdad).
- [x] `docs/index.html`: navegador con endpoints, ejemplos curl y preview del JSON.
- [x] URLs de consumo: `https://raw.githubusercontent.com/<user>/fpc-api/main/docs/v1/…`
      y `https://<user>.github.io/fpc-api/v1/…` (una vez activado Pages).

### Fase 8 — Automatización (GitHub Actions)
- [x] `ci.yml`: tests + validación de datos comprometidos en cada push/PR.
- [x] `update.yml`: cron diario 14:00 UTC (09:00 Colombia) → build completo → si cambió
      algo, commit automático `data: update <fecha>` + push.
- [x] `pages.yml`: deploy de `docs/` a GitHub Pages en cada push a main.

### Fase 9 — Documentación
- [x] `README.md`: qué es, cómo consumirla (curl/JS/Python), modelo de datos, cómo
      actualizar, cómo contribuir un alias, disclaimer (no afiliada a DIMAYOR).

### Fase 10 — Lanzamiento (manual, del dueño del repo)
1. `git commit` inicial y `git push` a un repo nuevo en GitHub.
2. Settings → Pages → Source: **GitHub Actions**.
3. Verificar `https://<user>.github.io/fpc-api/v1/index.json`.
4. (Opcional) Proteger `main` con el check de CI.

---

## 6. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Wikipedia cambia el layout de una tabla | Validadores lo detectan en el cron → build rojo → se arregla el parser |
| Nombre de club nuevo/desconocido | Build falla a propósito; se agrega alias (1 línea) |
| Plantillas de clubes incompletas en Wikipedia | `players.json` es best-effort con warnings; fase v2 usa API-Football |
| Fechas de partidos no disponibles | `null` explícito; nunca inventar; v2 añade API-Football |
| Rate-limit de Wikipedia | Caché en disco + UA identificable + 20–30 requests/día (trivial) |
| Dependencia de un solo scraper | `match_team()` centralizado; añadir fuente = módulo nuevo con el mismo contrato |

---

## 7. Definición de "listo" (v1) — ESTADO: ✅ COMPLETADO

- [x] `python -m fpc_api.build all` produce JSON válido para teams (49 clubes, 20 activos),
      champions (101 ediciones, 1948–2026), seasons (6 torneos: 2024-I → 2026-II, con
      partidos, fechas reales, goleadores y asistencias) y players (600 jugadores).
- [x] `python -m fpc_api.validate` pasa 100% sobre lo generado.
- [x] 10 tests offline pasan (`python -m tests.run`).
- [x] `docs/index.html` navega la API.
- [x] Workflows listos (cron diario + CI + Pages).
- [x] README con instrucciones de consumo y lanzamiento.

### Pendiente del dueño (Fase 10)

1. Crear el repo en GitHub y hacer push.
2. Settings → Pages → Source: **GitHub Actions**.
3. Verificar `https://<user>.github.io/fpc-api/v1/index.json`.
4. (Opcional) Proteger `main` con el check de CI.

### Lecciones del build real (documentadas para el futuro)

- Wikipedia duplica tablas (versión móvil/desktop) → dedup por conjunto de equipos.
- Filas de partidos programados vienen truncadas (sin fecha/hora) → acceso seguro por celda.
- Formatos de fase final varían por año: cuadrangulares (2024–2025) vs llaves
  cuartos/semis/final (2026) → etapas inferidas desde el final (final=1 serie, semis=2…).
- Los validadores ya atraparon: alias duplicados (`fortaleza`/`fortaleza-fc`), clubes
  nuevos (Internacional de Bogotá, 2026), filas corruptas y partidos aplazados.
