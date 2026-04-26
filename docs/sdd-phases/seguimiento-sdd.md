# Taskboard MCP — Documento de Seguimiento SDD

**Fecha de creación:** 25/04/2026  
**Proyecto:** taskboard-mcp  
**Estado:** 🔄 Propuesta — Exploración completada, pasando a propuesta.

---

## Índice

1. [Objetivo](#objetivo)
2. [Estado Actual del Sistema](#estado-actual-del-sistema)
3. [Investigación Previa](#investigación-previa)
4. [Exploración](#exploración)
5. [Propuesta](#propuesta)
6. [Especificaciones](#especificaciones)
7. [Diseño Técnico](#diseño-técnico)
8. [Tasks de Implementación](#tasks-de-implementación)
9. [Implementación](#implementación)
10. [Verificación](#verificación)
11. [Fases SDD — Progreso](#fases-sdd--progreso)
12. [Archivos Relevantes](#archivos-relevantes)

---

## Objetivo

Evolucionar el skill **taskboard** (actualmente basado en SQLite + Python one-liners vía Bash) hacia un **MCP server con web dashboard liviano**, deployable via Docker para uso local o en VPS. El sistema debe permitir:

- Registrar tareas desde el agente AI (OpenCode) vía MCP
- Visualizar tareas por proyecto en una interfaz web
- Generar reportes por proyecto y rango de fechas
- Exportar datos a CSV desde la interfaz web
- Mantener la misma base SQLite existente (~/.taskboard/taskboard.db)

---

## Estado Actual del Sistema

### Datos existentes

| Dato | Valor |
|------|-------|
| Ubicación DB | `~/.taskboard/taskboard.db` |
| Proyectos registrados | 13 |
| Tareas registradas | 175 |
| Entradas en historial | 271 |
| Interface actual | Skill + Python one-liners via Bash |

### Proyectos activos

| Proyecto | Slug | Origen |
|----------|------|--------|
| C Study | cs | local |
| Gentle AI | gai | github |
| Guardian Angel | gga | github |
| Hermes Finanzas | hf | github |
| Hermes OdontoIA | ho | github |
| Odonto IA | od | github |
| OpenClaw | oc | github |
| OpenClaw Extensions | oce | github |
| OpenClaw Finanzas | ocf | github |
| TaskBoard | tb | github |
| Maguen | mag | github |
| LaSalle | ls | github |
| OpenCode Config | occ | local |

### Stack actual

- **DB**: SQLite (WAL mode, foreign keys ON)
- **Acceso**: Python `sqlite3` stdlib module via Bash one-liners
- **Schema**: 4 tablas (projects, tasks, task_history, meta) + 8 indexes
- **Skill**: `~/.config/opencode/skills/taskboard/SKILL.md` (v2.0)

### Limitaciones actuales

1. **Sin interfaz web** — Solo se puede consultar desde el agente AI
2. **Sin export CSV** — Los reportes son markdown generados por el agente
3. **Sin API** — No hay forma de integrar con otras herramientas
4. **Sin MCP** — El agente ejecuta Python directamente, no via protocolo MCP

---

## Investigación Previa

> **Fecha:** 25/04/2026  
> **Documento completo:** `/home/aleka/DEV/PER/taskboard-mcp/INVESTIGACION-ENGRAM-CLOUD.md`

Se analizó la arquitectura de [Engram Cloud](https://github.com/Gentleman-Programming/engram) (releases v1.10.x a v1.13.1) para extraer patrones aplicables.

### Lecciones clave de Engram Cloud

| Lección | Aplicación a Taskboard |
|---------|----------------------|
| **Multi-interface**: CLI + MCP + HTTP + Web sobre el mismo store | `store.py` compartido entre MCP server y web app |
| **HTMX + server-rendered HTML**: 14KB JS, sin React/Vue, sin build step | Dashboard web liviano con Jinja2 + HTMX |
| **Single binary + SQLite**: Docker deployment trivial | Python slim + SQLite volume |
| **Store como núcleo**: Todas las interfaces son adaptadores delgados | Patrón idéntico con `store.py` |

### Stack seleccionado

| Componente | Tecnología | Justificación |
|-----------|-----------|---------------|
| MCP Server | `fastmcp` (Python) | Mismo framework que drupal-scout-mcp |
| Web Framework | **Starlette** (confirmado por exploración) | Compatible nativamente con fastmcp |
| Templates | Jinja2 | Server-rendered, estándar Python |
| Interactividad | HTMX (14KB) | Sin framework JS, partial updates |
| DB | SQLite (misma schema) | Ya funciona, no cambia |
| Docker | Python 3.12 slim | ~50MB imagen |

---

## Exploración

> **Fecha:** 25/04/2026  
> **Agente:** sdd-explore-glm-5-1-strategic  
> **Artifact engram:** `sdd/taskboard-mcp/explore`

### Assessment del Sistema Actual

| Aspecto | Estado |
|---------|--------|
| Skill SKILL.md | 421 líneas, 9 workflows documentados |
| Data model | 4 tablas, 8 indexes, schema v1 |
| DB productiva | 177 tareas, 13 proyectos, 271 entradas de historial |
| Template de reportes | 3 formatos (full, timeline, metrics) |
| WAL mode | Activo |
| Schema versioning | Tabla `meta` con `schema_version = 1` |

### 🔥 Descubrimiento Crítico: fastmcp + Starlette

**fastmcp se monta nativamente como sub-app de Starlette** via `mcp.http_app(path='/mcp')`. Esto implica:

```
UN proceso Python → Starlette app
  ├── /mcp/*     → fastmcp (protocolo MCP para OpenCode/Claude)
  ├── /*         → Web dashboard (Jinja2 + HTMX)
  └── /api/*     → REST API (JSON)
       ↓
  store.py → ~/.taskboard/taskboard.db
```

**Consecuencias:**
- **Un solo proceso** — no hay procesos separados ni IPC
- **Starlette sobre Flask** — fastmcp usa Starlette internamente, usar Flask crearía fricción
- **Deployment simple** — un solo `uvicorn` sirve todo

### Decisiones Tecnológicas

| Decisión | Opción elegida | Alternativa descartada | Justificación |
|----------|---------------|----------------------|---------------|
| Web framework | **Starlette** | Flask | Consistencia nativa con fastmcp |
| store.py | **Clase** | Funciones module-level | Encapsula conexión, facilita testing, API surface limpia |
| Procesos | **Uno solo** | MCP + Web separados | Sin IPC, sin coordinación, más simple |
| Schema DB | **Sin cambios** | Migración | Las 177 tareas existentes funcionan tal cual |
| Scope del change | **Un solo change** | Múltiples changes | Piezas chicas y acopladas, separar agrega complejidad |

### Riesgos Identificados

| Riesgo | Severidad | Mitigación |
|--------|-----------|------------|
| No hay pip/uv instalado en el sistema | Alta | Instalar `uv` antes de codear: `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Timestamps inconsistentes en task_history | Media | ISO vs space format mezclados — normalizar en store.py |
| fastmcp v3.x estabilidad API | Media | Fijar versión en pyproject.toml |
| SQLite single-writer | Baja | Agregar `PRAGMA busy_timeout = 5000` |

### Arquitectura Recomendada

```python
# Un solo proceso, una app Starlette
app = Starlette(routes=[...])

# fastmcp se monta como sub-app
mcp = FastMCP("taskboard")
app.mount("/mcp", mcp.http_app())

# Rutas web (Jinja2 + HTMX)
app.add_route("/", dashboard)
app.add_route("/projects/{name}", project_detail)
app.add_route("/timeline", timeline_view)
app.add_route("/reports", reports_view)

# API REST (JSON)
app.add_route("/api/tasks", tasks_api)
app.add_route("/api/export/csv", csv_export)

# Todo comparte el mismo store
store = TaskboardStore("~/.taskboard/taskboard.db")
```

---

## Propuesta

> **Fecha:** 25/04/2026  
> **Agente:** sdd-propose-glm-5-1-strategic  
> **Artifact engram:** `sdd/taskboard-mcp/proposal`

### Intent

Evolucionar taskboard de Python one-liners a un MCP server + web dashboard. Un solo proceso Starlette sirve MCP (agentes AI vía fastmcp), REST API (JSON) y HTML dashboard (Jinja2 + HTMX) sobre la misma clase `TaskboardStore` y los 177 tareas existentes en SQLite. Sin cambios de schema.

### Scope — Incluido (9 entregables)

| # | Entregable | Descripción |
|---|-----------|-------------|
| 1 | `store.py` | Clase con todas las operaciones SQLite (CRUD, metrics, timeline, CSV) |
| 2 | MCP server | fastmcp con tools: add_task, complete_task, list_tasks, get_metrics, get_timeline, add_project, list_projects |
| 3 | Web dashboard | Jinja2 + HTMX: overview, proyectos, timeline, reportes, CRUD |
| 4 | REST API | JSON endpoints: CRUD tasks/projects, metrics, CSV export |
| 5 | CSV export | stdlib `csv`, filtrado por proyecto y rango de fechas |
| 6 | Docker | Dockerfile (Python 3.12 slim) + docker-compose.yml |
| 7 | Project setup | pyproject.toml, pytest, estructura de directorios |
| 8 | Entry points | `mcp.run()` (stdio para AI) + `uvicorn` (HTTP para web) |
| 9 | Templates HTMX | base.html, partials para actualizaciones parciales |

### Scope — Excluido (8 items)

| Item | Razón |
|------|-------|
| Auth/seguridad | Futuro — single user por ahora |
| Auto-detect git log | Phase 5 del roadmap |
| VPS sync | Phase 6 del roadmap |
| TUI terminal | No es prioridad |
| Búsqueda full-text (FTS5) | Queries son por project/status/date, no contenido |
| Migración de schema | No necesaria — schema actual funciona |
| pandas | stdlib `csv` alcanza |
| Multi-usuario | Single user por diseño |

### Approach

1. **Un proceso, una app, un store** — Starlette monta fastmcp en `/mcp`, sirve Jinja2+HTMX en `/`, devuelve JSON en `/api/`
2. **Dos entry points** — `mcp.run()` (stdio) para OpenCode/Claude, `uvicorn` para web dashboard
3. **Zero schema changes** — las 177 tareas existentes funcionan tal cual
4. **Skill actual intacto** — no se modifica hasta que el MCP esté verificado

### Rollback Plan

Detener el server. La DB existente no se toca. El skill actual en `~/.config/opencode/skills/taskboard/` sigue funcionando. Revertir el commit es suficiente.

### Criterios de Éxito

- [ ] MCP server arranca con `fastmcp` y responde tools desde OpenCode
- [ ] Web dashboard muestra los 13 proyectos y 177 tareas existentes
- [ ] Se puede crear y completar una tarea desde el MCP
- [ ] Se puede crear y completar una tarea desde la web
- [ ] Timeline muestra tareas por semana actual y por mes actual
- [ ] Reportes se generan con 3 modos: solo fechas, solo proyecto, o ambos combinados
- [ ] CSV export descarga archivo filtrado (fechas, proyecto, o ambos)
- [ ] Docker arranca con `docker-compose up`, reinicia tras caídas, levanta al iniciar compu
- [ ] Cron/watchdog verifica cada 30 min que el container esté activo y reporta caídas
- [ ] Tests pasan con `pytest`

---

## Especificaciones

> **Fecha:** 25/04/2026  
> **Agente:** sdd-spec-glm-5-1-strategic  
> **Artifact engram:** `sdd/taskboard-mcp/spec`

### Resumen de Cobertura

| Dominio | Requisitos | Escenarios |
|---------|-----------|------------|
| Store (store.py) | 5 | 15 |
| MCP Server (fastmcp) | 2 | 3 |
| Web Dashboard (HTMX) | 5 | 12 |
| REST API (JSON) | 4 | 12 |
| Docker & Setup | 4 | 8 |
| **Total** | **20** | **50** |

### REQ-01 a REQ-05: Store (store.py)

| REQ | Descripción | Criterios clave |
|-----|-------------|-----------------|
| REQ-01 | Conexión con WAL + busy_timeout | WAL mode, busy_timeout 5000ms, foreign_keys ON |
| REQ-02 | CRUD de tareas | add, complete, update_status, get, list con filtros |
| REQ-03 | CRUD de proyectos | add, get, list, auto-detect origin |
| REQ-04 | Analytics (metrics, timeline, activity) | Queries agregadas por fecha, proyecto, tipo |
| REQ-05 | CSV export | Filtrado por proyecto + rango de fechas, stdlib csv |

### REQ-06 a REQ-07: MCP Server

| REQ | Descripción | Criterios clave |
|-----|-------------|-----------------|
| REQ-06 | 9 tools fastmcp | add_task, complete_task, update_task_status, list_tasks, get_task, add_project, list_projects, get_metrics, get_timeline, export_csv |
| REQ-07 | Respuestas estructuradas | Success con data, error con mensaje, IDs en responses |

### REQ-08 a REQ-12: Web Dashboard

| REQ | Descripción | Criterios clave |
|-----|-------------|-----------------|
| REQ-08 | Dashboard overview | Métricas globales, proyectos activos, actividad reciente |
| REQ-09 | Detalle de proyecto | Tasks filtradas, filtros HTMX por status/type, paginación |
| REQ-10 | Timeline | Agrupado por semana y por mes, vista "semana actual" y "mes actual", orden cronológico, status indicators |
| REQ-11 | Reportes + CSV | Filtros combinables: rango de fechas solo, proyecto solo, o ambos. Preview del reporte, botón export CSV |
| REQ-12 | HTMX partials | Actualización parcial sin reload, formularios con hx-post |

> **Clarificación (post-specs):** Los reportes deben soportar 3 modos de filtrado: (1) solo fechas, (2) solo proyecto, (3) fechas + proyecto combinados. El timeline debe tener dos vistas: "semana actual" y "mes actual".

### REQ-13 a REQ-16: REST API

| REQ | Descripción | Criterios clave |
|-----|-------------|-----------------|
| REQ-13 | CRUD tasks | POST /api/tasks, GET /api/tasks?filters, PATCH /api/tasks/{id} |
| REQ-14 | CRUD projects | POST /api/projects, GET /api/projects |
| REQ-15 | Metrics API | GET /api/metrics?from=X&to=Y&project=Z |
| REQ-16 | CSV download | GET /api/export/csv?filters → Content-Disposition attachment |

### REQ-17 a REQ-20: Docker & Setup

| REQ | Descripción | Criterios clave |
|-----|-------------|-----------------|
| REQ-17 | Dockerfile | Python 3.12-slim, copy + install, expose port |
| REQ-18 | docker-compose.yml | Volume para SQLite, env vars, `restart: unless-stopped` (reinicio automático tras caída) |
| REQ-19 | pyproject.toml | fastmcp, starlette, uvicorn, jinja2, pytest, ruff |
| REQ-20 | Entry points | mcp stdio para AI + uvicorn HTTP para web |
| REQ-21 | Health check + watchdog | Cron cada 30 min verifica que el container esté activo, si no lo levanta y registra caída en log |

> **Clarificación (post-specs):** Docker debe tener `restart: unless-stopped` para levantar automáticamente al iniciar la compu. Además, un cron/healthcheck externo cada 30 minutos verifica que el servicio esté activo; si no, lo levanta y guarda un reporte de caída en `~/.taskboard/crash-report.log`.

---

## Diseño Técnico

> **Fecha:** 25/04/2026  
> **Agente:** sdd-design-glm-5-1-strategic  
> **Artifact engram:** `sdd/taskboard-mcp/design`

### Decisiones de Arquitectura (AD-01 a AD-14)

| ID | Decisión | Elección | Racional |
|----|----------|----------|----------|
| AD-01 | Framework web | Starlette | Nativo con fastmcp, un solo ASGI app |
| AD-02 | Store pattern | Clase con conexión persistente | API limpia, testable, injectable |
| AD-03 | Conexión SQLite | Single persistent connection + context manager | Cleanup garantizado, WAL mode |
| AD-04 | Templates | Jinja2 con autoescape | Estándar Python, server-rendered |
| AD-05 | Interactividad | HTMX 14KB (sin build step) | Progressive enhancement, sin JS framework |
| AD-06 | CSS | Custom con CSS variables (~200 líneas) | Sin Tailwind build, sin framework CSS |
| AD-07 | CSV export | stdlib `csv.writer` | Sin pandas, datos simples tabulares |
| AD-08 | Config DB path | Env var `TASKBOARD_DB` | Flexibilidad local vs Docker |
| AD-09 | Procesos | Un solo proceso Starlette | Sin IPC, deploy simple |
| AD-10 | Entry points | `mcp.run()` (stdio) + `uvicorn` (HTTP) | AI agents → stdio, humanos → HTTP |
| AD-11 | Timeline | Dos vistas: semana actual + mes actual | Toggle entre vistas, mismo query pattern |
| AD-12 | Reportes | 3 modos: fechas / proyecto / ambos | Filtros combinables dinámicamente |
| AD-13 | Docker resiliencia | `restart: unless-stopped` + cron watchdog 30min | Reinicio auto + crash logging |
| AD-14 | Testing | In-memory SQLite + Starlette TestClient | Unit tests sin tocar DB real |

### Estructura del Proyecto

```
taskboard-mcp/
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── watchdog.sh                       # Cron health check cada 30 min
├── taskboard/
│   ├── __init__.py
│   ├── store.py                      # TaskboardStore (core)
│   ├── app.py                        # Starlette factory + fastmcp mount
│   ├── mcp_server.py                 # 10 MCP tools via fastmcp
│   └── web/
│       ├── __init__.py
│       ├── routes/
│       │   ├── pages.py              # HTML pages (/, /projects, /timeline, /reports)
│       │   ├── api.py                # REST API (/api/*)
│       │   └── partials.py           # HTMX fragments (/partials/*)
│       ├── templates/
│       │   ├── base.html             # Layout con HTMX, nav, footer
│       │   ├── dashboard.html        # Overview con métricas globales
│       │   ├── project_detail.html   # Tareas de un proyecto
│       │   ├── timeline.html         # Vista semana/mes con toggle
│       │   ├── report.html           # Filtros combinables + preview
│       │   └── partials/
│       │       ├── task_list.html
│       │       ├── metrics_cards.html
│       │       ├── timeline_items.html
│       │       └── report_preview.html
│       └── static/
│           ├── css/style.css
│           └── js/htmx.min.js        # 14KB vendored
├── tests/
│   ├── conftest.py                   # Fixtures (in-memory store, TestClient)
│   ├── test_store.py
│   ├── test_mcp_server.py
│   ├── test_web_routes.py
│   └── test_api.py
└── sdd-phases/
    └── seguimiento-sdd.md
```

### Store — Firmas de Métodos Clave

```python
class TaskboardStore:
    def __init__(self, db_path: str): ...
    def __enter__(self) -> "TaskboardStore": ...
    def __exit__(self, *exc): ...
    
    # Projects
    def add_project(self, name, display_name, slug, origin, path, **kw) -> dict
    def get_project(self, name: str) -> dict | None
    def list_projects(self) -> list[dict]
    
    # Tasks
    def add_task(self, task_id, title, type, project_name, **kw) -> dict
    def get_task(self, task_id: str) -> dict | None
    def list_tasks(self, project=None, status=None, type=None, from_date=None, to_date=None) -> list[dict]
    def update_task_status(self, task_id, new_status, note="", git_commit=None) -> dict
    def complete_task(self, task_id, summary="", git_commit=None) -> dict
    
    # Analytics — 3 modos de filtro (dates / project / both)
    def get_metrics(self, project=None, from_date=None, to_date=None) -> dict
    def get_timeline_week(self, project=None) -> list[dict]
    def get_timeline_month(self, project=None) -> list[dict]
    def get_recent_activity(self, days=7) -> list[dict]
    
    # Export
    def export_csv(self, output_path, project=None, from_date=None, to_date=None) -> str
```

### Tabla de Rutas

**Web (HTML + HTMX):**

| Método | Ruta | Template | Descripción |
|--------|------|----------|-------------|
| GET | `/` | dashboard.html | Overview con métricas globales |
| GET | `/projects/{name}` | project_detail.html | Tareas de un proyecto |
| GET | `/timeline` | timeline.html | Vista semana/mes con toggle |
| GET | `/reports` | report.html | Filtros combinables + preview |
| POST | `/tasks` | redirect | Crear tarea |
| POST | `/tasks/{id}/status` | HTMX swap | Cambiar status |
| POST | `/tasks/{id}/complete` | HTMX swap | Completar tarea |
| GET | `/partials/task-list` | partial | Lista filtrada (HTMX) |
| GET | `/partials/metrics` | partial | Cards de métricas (HTMX) |
| GET | `/partials/timeline` | partial | Items timeline (HTMX) |

**API (JSON):**

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/projects` | Lista proyectos |
| POST | `/api/projects` | Crear proyecto |
| GET | `/api/tasks` | Lista tareas con filtros |
| POST | `/api/tasks` | Crear tarea |
| PATCH | `/api/tasks/{id}` | Actualizar tarea |
| POST | `/api/tasks/{id}/complete` | Completar tarea |
| GET | `/api/metrics` | Métricas con filtros |
| GET | `/api/export/csv` | Download CSV |

### Docker + Watchdog

**docker-compose.yml** con `restart: unless-stopped` + healthcheck.

**watchdog.sh** (cron `*/30 * * * *`): verifica si container está corriendo, si no → reinicia + log a `~/.taskboard/crash-report.log`.

### Testing Strategy

| Componente | Approach | Fixture |
|-----------|----------|---------|
| `store.py` | In-memory SQLite (`:memory:`) | DB vacía + datos seed |
| MCP tools | Llamadas directas a funciones | Store in-memory |
| Web routes | Starlette `TestClient` | App con store in-memory |
| API routes | Starlette `TestClient` | App con store in-memory |

### Open Questions

- [ ] Verificar que `fastmcp.http_app()` mount path funciona con latest stable
- [ ] Confirmar patrón `create_app()` factory con uvicorn CLI

---

## Tasks de Implementación

> **Fecha:** 25/04/2026  
> **Agente:** sdd-tasks-glm-5-1-strategic  
> **Artifact engram:** `sdd/taskboard-mcp/tasks`  
> **Detalle completo:** `sdd-phases/tasks-breakdown.md`

### Grafo de Dependencias

```
Phase 1: Foundation
  TASK-01 (setup) → TASK-02 (store conn) → TASK-03 (store CRUD)
        │
Phase 2: Store Completion
  TASK-04 (analytics) → TASK-05 (CSV) → TASK-06 (store tests)
        │
Phase 3: MCP Server
  TASK-07 (9 tools) → TASK-08 (MCP tests)
        │
Phase 4: Web App Framework
  TASK-09 (Starlette factory) → TASK-10 (base.html)
        │
Phase 5: Web Routes - Pages (paralelizables)
  TASK-11/12 (dashboard) → TASK-13/14 (projects) → TASK-15/16 (timeline) → TASK-17/18 (reports)
        │
Phase 6: API & Partials (paralelizables)
  TASK-19 (API) → TASK-20 (partials routes) → TASK-21 (partial templates)
        │
Phase 7: Static Assets
  TASK-22 (CSS) → TASK-23 (HTMX vendor)
        │
Phase 8: Testing - Web Layer (paralelizables)
  TASK-24 (conftest) → TASK-25 (web tests) / TASK-26 (API tests) / TASK-27 (MCP integration)
        │
Phase 9: Docker & Deployment
  TASK-28 (Dockerfile) → TASK-29 (compose + watchdog)
        │
Phase 10: Final
  TASK-30 (full test run) → TASK-31 (README) → TASK-32 (e2e verification)
```

### Resumen

| Phase | Tasks | Effort | Paralelizable |
|-------|-------|--------|---------------|
| 1: Foundation | 3 | L | No |
| 2: Store Completion | 3 | XL | No |
| 3: MCP Server | 2 | M | No |
| 4: Web App Framework | 2 | L | No |
| 5: Web Routes - Pages | 8 | XL | Parcial |
| 6: API & Partials | 3 | XL | Parcial |
| 7: Static Assets | 2 | S | No |
| 8: Testing - Web Layer | 4 | XL | Sí |
| 9: Docker & Deployment | 2 | M | No |
| 10: Final | 2 | M | No |
| **Total** | **32** | **~5-7 días** | |

> Ver detalle completo de cada task en [`tasks-breakdown.md`](tasks-breakdown.md)

---

## Implementación

> **Fecha:** 25/04/2026  
> **Agente:** sdd-apply-glm-5-1-strategic (5 batches)  
> **Artifact engram:** `sdd/taskboard-mcp/apply-progress`

### Resumen

| Métrica | Resultado |
|---------|-----------|
| Tasks completadas | 32/32 |
| Tests | 152, todos pasando |
| Coverage | 94% |
| Tiempo total de aplicación | ~40 minutos (5 batches) |
| Archivos creados | ~20 |
| Archivos modificados | 0 (zero schema changes) |

### Batches de Implementación

| Batch | Tasks | Descripción | Tests |
|-------|-------|-------------|-------|
| 1 | TASK-01 a TASK-06 | Foundation + Store + Tests | 66 |
| 2 | TASK-07 a TASK-10 | MCP Server + App Factory + Base Template | +23 = 89 |
| 3 | TASK-11 a TASK-18 | Web Pages + Templates (dashboard, projects, timeline, reports) | 89 (sin regresión) |
| 4 | TASK-19 a TASK-23 | REST API + HTMX Partials + CSS + HTMX vendor | 89 (sin regresión) |
| 5 | TASK-24 a TASK-32 | Tests Web/API/MCP + Docker + Watchdog + README + E2E | +63 = 152 |

### Desviaciones del Diseño

| Desviación | Detalle |
|-----------|---------|
| HTMX v2.0.4 (~51KB) | Diseño estimaba v1.9.x (~14KB). 2.x es el estable actual. |
| Port 7438 | Diseño decía 8000, pero el usuario especificó 7438 |
| Python 3.13 | Diseño decía 3.12, pero el sistema tiene 3.13 |
| Status 'done' | Spec decía 'completed', pero el schema real usa 'done' — se sigue el schema |
| Docker healthcheck con Python | python:3.13-slim no tiene curl, se usó urllib.request |
| 10 tools MCP (no 9) | El criterio de aceptación listaba 10, el título decía 9 — se implementaron los 10 |
| datetime.now(timezone.utc) | En vez de datetime.utcnow() (deprecado en 3.12+) |

### Archivos Finales

```
taskboard-mcp/
├── pyproject.toml                     # fastmcp, starlette, jinja2, uvicorn, pytest
├── Dockerfile                         # python:3.13-slim, EXPOSE 7438
├── docker-compose.yml                 # restart: unless-stopped, volume, healthcheck
├── watchdog.sh                        # Cron cada 30 min, crash log
├── README.md                          # Docs completos
├── taskboard/
│   ├── __init__.py
│   ├── store.py                       # TaskboardStore (426 LOC, CRUD + analytics + CSV)
│   ├── mcp_server.py                  # 10 fastmcp tools
│   └── web/
│       ├── __init__.py
│       ├── app.py                     # Starlette factory + MCP mount
│       ├── routes/
│       │   ├── __init__.py
│       │   ├── pages.py               # 5 page routes (/, /projects, /timeline, /reports)
│       │   ├── api.py                 # 10 REST API endpoints
│       │   └── partials.py            # 4 HTMX partial endpoints
│       ├── templates/
│       │   ├── base.html              # Layout con nav, HTMX, blocks
│       │   ├── dashboard.html         # Overview con métricas
│       │   ├── project_list.html      # Lista de proyectos
│       │   ├── project_detail.html    # Tareas de un proyecto con filtros
│       │   ├── timeline.html          # Vista semana/mes con toggle
│       │   ├── reports.html           # Filtros combinables + CSV download
│       │   └── partials/
│       │       ├── task_row.html
│       │       ├── task_list.html
│       │       ├── metrics_cards.html
│       │       ├── timeline_group.html
│       │       └── report_preview.html
│       └── static/
│           ├── css/style.css          # ~250 líneas, CSS variables
│           └── js/htmx.min.js         # v2.0.4 vendored
├── tests/
│   ├── conftest.py                    # Fixtures: store, client, seeded_store
│   ├── test_store.py                  # 66 tests
│   ├── test_mcp_server.py             # 34 tests
│   ├── test_web_routes.py             # 25 tests
│   └── test_api_routes.py             # 27 tests
└── sdd-phases/
    ├── seguimiento-sdd.md             # Este documento
    └── tasks-breakdown.md             # Detalle de 32 tasks
```

### Test Breakdown

| Suite | Tests | Cubre |
|-------|-------|-------|
| test_store.py | 66 | CRUD, analytics (3 filtros), timeline (week/month), CSV, history |
| test_mcp_server.py | 34 | 10 tools con mock + 11 integration tests con store real |
| test_web_routes.py | 25 | Dashboard, projects, timeline, reports, HTMX partials |
| test_api_routes.py | 27 | Tasks CRUD, projects CRUD, metrics, CSV export, errores |
| **Total** | **165** | **94% coverage** |

---

## Verificación

> **Fecha:** 25/04/2026  
> **Agente:** sdd-verify-glm-5-1-strategic  
> **Veredicto:** ✅ PASS — Post-hotfix, todos los issues resueltos

### Primera Pasada (25/04/2026)

| Métrica | Resultado |
|---------|-----------|
| Tests | 152/152 pasando |
| Coverage | 94% |
| Spec compliance | 62/64 scenarios (96.9%) |
| Criterios de éxito | 7.5/10 |
| Issues | 1 CRITICAL, 4 WARNINGS, 4 SUGGESTIONS |

### Hotfix Aplicado (25/04/2026)

| Fix | Descripción |
|-----|-------------|
| CRITICAL | Creadas rutas `/actions/*` dedicadas que aceptan form-encoded data y devuelven HTML fragments |
| CRITICAL | Templates actualizados: `project_detail.html`, `task_row.html`, `task_list.html` → `/actions/*` |
| CRITICAL | Rutas registradas en `app.py` |
| W1 | `chmod 755 watchdog.sh` |
| W2 | `report_preview.html` eliminado (dead code) |
| W3 | `create_app()` usa `os.path.dirname(__file__)` para paths absolutos |
| W4 | `hx-on::response-error` en `<body>` de `base.html` + CSS `.error-msg` |
| Extra | `get_project_by_name()` en store para redirect de add_task |
| Extra | 13 tests nuevos para action routes + error handling |

### Resultado Post-Hotfix

| Métrica | Resultado |
|---------|-----------|
| Tests | **165/165 pasando** |
| Criterios de éxito | **10/10 PASS** |
| CRITICAL issues | **0** |
| WARNING issues | **0** |

### Criterios de Éxito — Veredicto Final

| # | Criterio | Estado |
|---|----------|--------|
| 1 | MCP server arranca y responde tools | ✅ PASS |
| 2 | Web dashboard muestra 13 proyectos y 177 tareas | ✅ PASS |
| 3 | Crear y completar tarea desde MCP | ✅ PASS |
| 4 | Crear y completar tarea desde web | ✅ PASS |
| 5 | Timeline por semana y por mes | ✅ PASS |
| 6 | Reportes con 3 modos de filtro | ✅ PASS |
| 7 | CSV export filtrado | ✅ PASS |
| 8 | Docker con restart + watchdog | ✅ PASS |
| 9 | Tests pasan con pytest | ✅ PASS |
| 10 | Navegación web funcional + HTMX | ✅ PASS |

### SUGGESTIONS (no blocking)

1. Agregar favicon
2. Cache-Control headers para static
3. Timeline filter por slug (no name)
4. `hx-indicator` para loading states

---

## Lecciones Aprendidas (Post-Implementación)

> **Fecha:** 26/04/2026

### 1. Threading en MCP Servers — Fallo de Arquitectura

**Problema:** El `TaskboardStore` se diseñó con un patrón singleton (`self._conn`) asumiendo uso single-threaded. Cuando `fastmcp` despacha tool calls concurrentemente en threads distintos del pool, SQLite rechaza que un objeto creado en thread A se use en thread B.

**Síntomas:**
- Primer tool call funciona (crea la conexión en thread A)
- Calls subsiguientes fallan con `"SQLite objects created in a thread can only be used in that same thread"`
- Thread IDs diferentes en cada error

**Evolución del fix:**
1. `check_same_thread=False` (tb_022) — parche superficial, desactiva el check de Python pero no hace que compartir una conexión sea thread-safe
2. `threading.local()` (tb_023) — cada thread obtiene su propia conexión, pero se acumulan sin cerrarse → `database is locked`
3. `atexit` cleanup + stale detection (tb_025) — trackea conexiones globalmente, pero no cierra las de threads que siguen vivos
4. `threading.Lock` sobre conexión compartida (tb_038 inicial) — Lock solo protegía `_connect()`, no las operaciones SQL → `cannot commit - no transaction is active`
5. **Connection-per-call + _write_lock** (tb_038 final) — **fix definitivo**: cada método público abre conexión, hace su trabajo, cierra. Escrituras serializadas con Lock. Inspirado en Go's `database/sql` (patrón de Engram)

**Raíz del problema:** No se investigó cómo `fastmcp` despacha requests antes de diseñar la capa de persistencia. Los 165 tests corrían en un único thread (`pytest` secuencial) y nunca expusieron el bug.

**Lección clave:** Antes de diseñar la capa de persistencia, preguntar *"¿cómo va a ser invocado este código en producción?"*. Para cualquier server (MCP, HTTP, etc.), asumir multi-threading desde el diseño.

### 2. Tests Unitarios ≠ Tests de Runtime

**Problema:** 165 tests, 94% coverage, todos pasando — pero el MCP server crasheaba en producción.

**Por qué:** Los tests validan lógica CRUD en un único thread con SQLite in-memory. Nunca probaron concurrencia ni el runtime real de fastmcp.

**Lección clave:** Para código que corre detrás de un server, los tests unitarios no alcanzan. Hace falta al menos un smoke test que levante el server y haga llamadas reales (o simule concurrencia con `threading.Thread`).

### 3. Tres Bugs Raíz en la Capa de Persistencia

**Investigación:** El análisis de Engram Cloud (Go) reveló que Go's `database/sql` da automáticamente una conexión por goroutine desde un pool — zero mutexes. En Python hay que hacerlo explícito.

Los tres bugs raíz eran:
1. **Lock inútil** — `threading.Lock` solo protegía `_connect()`, no las operaciones SQL reales. El Lock se adquiría, obtenía la conexión, se liberaba, y luego el SQL corría sin protección.
2. **Transacciones rotas** — Métodos como `add_task` hacían `commit()` y luego llamaban `_record_history()` que hacía otro `commit()`. El segundo fallaba con "no transaction is active" porque ya se hizo commit.
3. **Context leaked** — `_get_store()` llamaba `__enter__()` sin `__exit__()`. La conexión se abría pero nunca se cerraba.

**Fix definitivo:** Connection-per-call (cada método abre, opera, cierra) + `_write_lock` solo para escrituras. Un solo `commit()` por operación atómica dentro del Lock.

### 4. replaceAll Ciega Causa Recursión

**Problema:** El `replaceAll` de `conn.close()` → `self._close(conn)` también reemplazó la línea dentro del propio método `_close()`, convirtiendo `conn.close()` en `self._close(conn)` → recursión infinita.

**Lección clave:** NUNCA usar `replaceAll` ciegamente. Verificar que el patrón no aparece dentro del propio método que lo contiene.

### 3. Paleta de Colores — Alineación con Engram Cloud

**Decisión:** El CSS usa la paleta **Engram Elephant** (tema oscuro), inspirada en los colores de Engram Cloud (`internal/tui/styles.go`):

| Variable | Color | Uso |
|----------|-------|-----|
| `--color-bg` | `#191724` | Deep purple/black base |
| `--color-surface` | `#1f1d2e` | Panel backgrounds |
| `--color-text` | `#e0def4` | Light lavender text |
| `--color-primary` | `#c4a7e7` | Lavender — brand purple |
| `--color-success` | `#9ccfd8` | Teal/Cyan |
| `--color-danger` | `#eb6f92` | Soft red |
| `--color-warning` | `#f6c177` | Peach — warm accent |
| `--color-accent` | `#ebbcba` | Soft pink/mauve |

Esto da una identidad visual coherente con el ecosistema Gentleman Programming.

---

## Fases SDD — Progreso

| Fase | Estado | Fecha |
|------|--------|-------|
| Investigación previa | ✅ Completada | 25/04/2026 |
| Init | ✅ Completada | 25/04/2026 |
| Exploración | ✅ Completada | 25/04/2026 |
| Propuesta | ✅ Completada | 25/04/2026 |
| Specs | ✅ Completada | 25/04/2026 |
| Diseño | ✅ Completada | 25/04/2026 |
| Tasks | ✅ Completada | 25/04/2026 |
| Implementación | ✅ Completada (32/32 tasks, 152 tests, 94% coverage) + Hotfix (+13 tests = 165 total) | 25/04/2026 |
| Verificación (1ra pasada) | ⚠️ FAIL — 1 CRITICAL fix requerido | 25/04/2026 |
| Hotfix | ✅ Aplicado — action routes + 13 tests nuevos | 25/04/2026 |
| Verificación (2da pasada) | ✅ PASS — 165/165 tests, 10/10 criterios | 25/04/2026 |
| Post-impl fix: check_same_thread | ✅ Aplicado — tb_022 | 26/04/2026 |
| Post-impl fix: threading.local() | ✅ Aplicado — tb_023 | 26/04/2026 |
| Post-impl fix: atexit cleanup | ✅ Aplicado — tb_025 (no resolvió database is locked) | 26/04/2026 |
| Post-impl fix: threading.Lock | ✅ Aplicado (Lock solo protegía _connect, no SQL) | 26/04/2026 |
| Post-impl fix: connection-per-call + write lock | ✅ Definitivo — tb_038 (inspirado en Go/Engram) | 26/04/2026 |
| MCP verificado en producción | ✅ PASS — tools funcionan sin errores de concurrencia | 26/04/2026 |
| Docs: README + guías + templates GitHub | ✅ tb_028, tb_029, tb_031, tb_030, tb_035 | 26/04/2026 |
| Docs: MCP tools + guía web | ✅ tb_042, tb_043 | 26/04/2026 |
| .gitignore para repo público | ✅ .atl/, .gga/, sdd-phases/, INVESTIGACION-* | 26/04/2026 |
| Repo GitHub + tag v0.1.0 + release | ✅ https://github.com/aleka/taskboard-mcp | 26/04/2026 |
| Archivo | ✅ Completado | 26/04/2026 |

---

## Archivos Relevantes

| Archivo | Rol |
|---------|-----|
| `~/.taskboard/taskboard.db` | Base de datos SQLite actual |
| `~/.config/opencode/skills/taskboard/SKILL.md` | Skill actual (v3.0 — MCP + SQL fallback) |
| `~/.config/opencode/skills/taskboard/assets/data-model.md` | Schema SQL actual |
| `~/.config/opencode/skills/taskboard/assets/dashboard-template.md` | Templates de reportes |
| `start-mcp.sh` | Wrapper script para MCP (cd + exec python) |
| `taskboard/store.py` | TaskboardStore — connection-per-call + _write_lock (thread-safe) |
| `docs/mcp-tools.md` | Documentación de las 10 herramientas MCP |
| `docs/guia-web.md` | Guía del web dashboard (páginas, HTMX, REST API) |
| `docs/guia-desarrollo.md` | Setup local, tests, Docker, convenciones |
| `docs/release-procedure.md` | SemVer, flujo git tag, checklist |

---

> **Nota:** Este documento se actualiza en cada fase del SDD. No editar manualmente sin coordinar con el workflow.
