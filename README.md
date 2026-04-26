# Taskboard MCP

Servidor MCP + web dashboard para tracking personal de tareas. Registrá tareas desde tu agent de IA via MCP o desde el navegador, visualizá timelines, generá reportes y exportá datos — todo en un solo proceso Python con SQLite.

```
Agente IA (OpenCode, Claude, etc.)
    ↓ MCP (stdio, fastmcp)
┌───────────────────────────┐
│   Starlette (port 7438)   │
│  ┌─────┐ ┌─────┐ ┌─────┐ │
│  │ MCP │ │ API │ │ Web │ │
│  └──┬──┘ └──┬──┘ └──┬──┘ │
│     └───────┼───────┘     │
│          store.py          │
└─────────────┬──────────────┘
              ↓
     ~/.taskboard/taskboard.db
```

Un solo proceso Starlette sirve las tres interfaces: MCP (via fastmcp), REST API (JSON) y Web (Jinja2 + HTMX). Todas delegan a `store.py`, la única fuente de verdad.

---

## Features

- **10 herramientas MCP** — add/complete/update/list tasks, proyectos, métricas, timeline, CSV export
- **Web dashboard** — UI completa con dashboard, proyectos, timeline y reportes
- **REST API** — JSON endpoints para tareas, proyectos, métricas y exportación
- **HTMX partials** — Updates en tiempo real sin recargar la página (cambio de status, filtros, métricas)
- **CSV export** — Descargá datos filtrados por proyecto, fechas o combinados
- **Docker** — Un solo container con auto-restart y health checks
- **Watchdog** — Monitoreo via cron con detección de crashes y recuperación automática
- **Thread safety** — Connection-per-call + write lock (inspirado en Go's `database/sql`)
- **Paleta Engram Elephant** — Dark theme consistente en todo el dashboard

---

## Herramientas MCP

10 herramientas disponibles para agentes de IA via MCP (OpenCode, Claude Desktop, etc.):

| Herramienta | Parámetros | Descripción |
|-------------|-----------|-------------|
| `add_task` | project, title, type, description, tags, priority | Crear una nueva tarea en un proyecto |
| `complete_task` | task_id, summary | Marcar tarea como completada |
| `update_task_status` | task_id, status, note | Cambiar estado (todo, in_progress, blocked, cancelled) |
| `list_tasks` | project, status, type, from_date, to_date, limit, offset | Listar tareas con filtros opcionales |
| `get_task` | task_id | Obtener detalle de una tarea por ID |
| `add_project` | name, display_name, slug, origin, path, tags | Registrar un nuevo proyecto |
| `list_projects` | — | Listar todos los proyectos registrados |
| `get_metrics` | project, start_date, end_date | Métricas y analytics (tasas de completitud, desglose por status/tipo) |
| `get_timeline` | project, view (week/month) | Timeline de tareas completadas agrupadas por semana o mes |
| `export_csv` | project, start_date, end_date | Exportar tareas como CSV con filtros |

---

## Quick Start

### Desarrollo local

```bash
# Clonar
git clone git@github.com:aleka/taskboard-mcp.git
cd taskboard-mcp

# Instalar dependencias
uv pip install -e ".[dev]"

# Crear directorio de datos
mkdir -p ~/.taskboard

# Iniciar el servidor (port 7438)
uvicorn taskboard.web.app:create_app --host 0.0.0.0 --port 7438 --factory
```

El dashboard está en http://localhost:7438

### Docker

```bash
docker compose up -d
```

### Watchdog (cron)

Para monitoreo adicional de crashes:

```bash
crontab -e
# Agregar (ajustar path):
*/30 * * * * /bin/bash /path/to/taskboard-mcp/watchdog.sh
```

El watchdog chequea cada 30 minutos si el container está corriendo. Si no, loguea a `~/.taskboard/crash-report.log` e intenta reiniciar.

---

## Documentación

| Tema | Descripción |
|------|-------------|
| [Guía de desarrollo](docs/guia-desarrollo.md) | Setup local, tests, Docker, estructura, cómo contribuir |
| [Procedimiento de release](docs/release-procedure.md) | SemVer, flujo git tag → GitHub release, checklist |
| [Investigación Engram Cloud](docs/investigacion-engram-cloud.md) | Arquitectura y patrones extraídos de Engram |
| [Coding standards](AGENTS.md) | Convenciones de código Python |

---

## Stack

| Capa | Tecnología |
|------|------------|
| MCP Server | fastmcp (Python) |
| Web Framework | Starlette |
| Templates | Jinja2 |
| Interactividad | HTMX |
| Base de datos | SQLite (WAL mode) |
| Runtime | Python 3.13+ |
| Infra | Docker + docker-compose |
| Paleta visual | Engram Elephant (dark theme) |

---

## Estructura del proyecto

```
taskboard-mcp/
├── taskboard/
│   ├── __init__.py
│   ├── store.py                  # Core: SQLite (fuente de verdad, todas las interfaces delegan acá)
│   ├── mcp_server.py             # MCP server via fastmcp (10 herramientas)
│   └── web/
│       ├── __init__.py
│       ├── app.py                # Starlette app (monta MCP, API, Web)
│       ├── routes/
│       │   ├── pages.py          # GET rutas HTML (dashboard, proyectos, timeline, reportes)
│       │   ├── api.py            # REST API JSON (CRUD tareas, proyectos, métricas, CSV)
│       │   ├── actions.py        # HTMX form handlers (POST /actions/*)
│       │   └── partials.py       # HTMX fragments (GET /partials/*)
│       ├── templates/
│       │   ├── base.html         # Layout principal
│       │   ├── dashboard.html    # Dashboard con métricas
│       │   ├── project_list.html # Lista de proyectos
│       │   ├── project_detail.html # Detalle de proyecto con tareas
│       │   ├── timeline.html     # Timeline cronológica
│       │   ├── reports.html      # Reportes con filtros
│       │   └── partials/         # HTMX partials
│       └── static/
│           ├── css/              # Estilos (Engram Elephant palette)
│           ├── js/               # JavaScript mínimo
│           └── favicon.svg       # Favicon
├── tests/
│   ├── conftest.py               # Fixtures compartidas (store in-memory)
│   ├── test_store.py             # Tests del store (CRUD, métricas, timeline, CSV)
│   ├── test_mcp_server.py        # Tests de las 10 herramientas MCP
│   ├── test_web_routes.py        # Tests de rutas web (HTML + HTMX)
│   └── test_api_routes.py        # Tests de la REST API (JSON)
├── docs/
│   ├── guia-desarrollo.md        # Guía de desarrollo
│   ├── release-procedure.md      # Procedimiento de release
│   └── investigacion-engram-cloud.md # Investigación de arquitectura
├── Dockerfile                    # Imagen Python 3.13-slim + uv
├── docker-compose.yml            # Container con health check + auto-restart
├── watchdog.sh                   # Script de monitoreo via cron
├── start-mcp.sh                  # Script para iniciar MCP server
├── pyproject.toml                # Dependencias y configuración
├── AGENTS.md                     # Coding standards
└── README.md                     # Este archivo
```

---

## Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `TASKBOARD_DB` | `~/.taskboard/taskboard.db` | Path a la base de datos SQLite |

---

## Testing

```bash
# Todos los tests con coverage
uv run pytest tests/ -v --cov=taskboard

# Un archivo específico
uv run pytest tests/test_store.py -v
```

165 tests, 94% coverage. Todos usan SQLite in-memory — nunca tocan la DB de producción.

---

## License

MIT
