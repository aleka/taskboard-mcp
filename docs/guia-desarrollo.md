# Guía de Desarrollo

> Setup local, tests, Docker, estructura del proyecto y cómo contribuir a Taskboard MCP.

---

## Requisitos

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (gestor de paquetes)
- Docker & Docker Compose (opcional, para deployment containerizado)

---

## Setup Local

```bash
# 1. Clonar
git clone git@github.com:aleka/taskboard-mcp.git
cd taskboard-mcp

# 2. Crear entorno e instalar dependencias
uv pip install -e ".[dev]"

# 3. Crear directorio de datos
mkdir -p ~/.taskboard

# 4. Iniciar el servidor
uvicorn taskboard.web.app:create_app --host 0.0.0.0 --port 7438 --factory
```

Abrir http://localhost:7438 en el navegador.

---

## Estructura del Proyecto

```
taskboard-mcp/
├── taskboard/
│   ├── store.py              # FUENTE DE VERDAD — todas las interfaces delegan acá
│   ├── mcp_server.py         # 16 herramientas MCP via fastmcp
│   └── web/
│       ├── app.py            # Starlette app factory (monta MCP + API + Web)
│       ├── routes/
│       │   ├── pages.py      # Rutas HTML (GET)
│       │   ├── api.py        # REST API (JSON)
│       │   ├── actions.py    # HTMX form handlers (POST /actions/*)
│       │   └── partials.py   # HTMX fragments (GET /partials/*)
│       ├── templates/        # Jinja2 templates
│       └── static/           # CSS, JS, favicon
├── tests/                    # 297 tests, 97% coverage
└── docs/                     # Documentación
```

### Arquitectura

Un solo proceso Starlette (puerto 7438) sirve tres interfaces:

| Interface | Ruta | Formato |
|-----------|------|---------|
| **MCP** | `/mcp` | fastmcp (stdio) |
| **REST API** | `/api/*` | JSON |
| **Web** | `/` y rutas HTML | Jinja2 + HTMX |

Todas las interfaces delegan a `TaskboardStore` — el store es la única fuente de verdad. No hay SQL fuera de `store.py`.

### Schema Versioning

El store usa migrations versionadas en `_connect()`. La tabla `meta` almacena `schema_version`.

| Versión | Cambios |
|---------|---------|
| v1 | Schema original (projects, tasks, task_history, meta) |
| v2 | `ALTER TABLE tasks ADD COLUMN parent_task_id TEXT DEFAULT NULL` + index |

Las migrations corren idempotentemente al conectar. Tests usan schema v2 directamente (no migrations en `:memory:`).

### Convenciones de Rutas

- `/api/*` → JSON endpoints (acceptan y retornan JSON)
- `/actions/*` → HTMX form handlers (acceptan `application/x-www-form-urlencoded`, retornan HTML fragments)
- `/partials/*` → HTMX fragments (GET, retornan HTML)

---

## Testing

### Ejecutar tests

```bash
# Todos los tests con coverage
uv run pytest tests/ -v --cov=taskboard

# Un archivo específico
uv run pytest tests/test_store.py -v

# Solo tests de un módulo
uv run pytest tests/test_store.py::TestAddTask -v

# Con output detallado
uv run pytest tests/ -vv -s
```

### Convenciones de tests

- **SQLite in-memory**: Todos los tests usan `:memory:`, nunca tocan la DB de producción
- **Fixtures**: `conftest.py` tiene fixtures compartidas (store in-memory, client HTTP)
- **Naming**: `test_*.py` en `tests/`, clases `Test*`, métodos `test_*`
- **Coverage target**: > 90% (actual: 99%)
- **Nuevas features**: Todo nuevo código debe incluir tests

### Archivos de tests

| Archivo | Qué prueba |
|---------|------------|
| `test_store.py` | CRUD, métricas, timeline, CSV, migrations, update_task, history, parent-child, cycle detection, atomic tags |
| `test_mcp_server.py` | Las 16 herramientas MCP (incluyendo update_task, tag ops, history) |
| `test_web_routes.py` | Rutas web (HTML + HTMX) incluyendo edit, delete, history |
| `test_api_routes.py` | REST API endpoints (JSON) incluyendo PATCH full update |

---

## Docker

### Build y run

```bash
# Construir y levantar
docker compose up -d

# Ver logs
docker compose logs -f taskboard

# Rebuild después de cambios
docker compose up -d --build

# Bajar
docker compose down
```

### Health check

El container tiene health check automático (cada 30s). Verificar estado:

```bash
docker inspect --format='{{.State.Health.Status}}' taskboard-mcp
```

---

## Variables de Entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `TASKBOARD_DB` | `~/.taskboard/taskboard.db` | Path a la base de datos SQLite |

---

## Convenciones de Código

Ver [AGENTS.md](../AGENTS.md) para las convenciones completas. Resumen:

- Python 3.13+ — type hints, `X | Y` unions, f-strings
- Imports: stdlib → third-party → local, línea en blanco entre grupos
- Max 120 caracteres por línea
- `pathlib` para paths, nunca rutas relativas al CWD
- CSS variables en `style.css` — no inline styles
- `print()` prohibido en producción — usar `logging`
- SQL solo en `store.py` — nunca en routes, templates o MCP tools
- Queries siempre parametrizadas (`?`) — nunca concatenación de strings

---

## Cómo Contribuir

### Flujo de trabajo

1. **Crear una rama** desde `main`
2. **Escribir tests** para la funcionalidad nueva
3. **Implementar** la funcionalidad
4. **Verificar** que todos los tests pasan con coverage >= 90%
5. **Commitear** con conventional commits (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`)
6. **Abrir PR** con descripción clara de los cambios

### Commits

```
feat: add timeline week view to dashboard
fix: resolve thread safety issue in concurrent writes
refactor: extract metrics calculation to store method
docs: update README with Docker instructions
test: add coverage for CSV export edge cases
chore: bump version to 0.2.0
```

### PR Template

Usar el template en [`.github/PULL_REQUEST_TEMPLATE.md`](../.github/PULL_REQUEST_TEMPLATE.md).

---

## Troubleshooting

### Puerto 7438 en uso

```bash
lsof -i :7438
uvicorn taskboard.web.app:create_app --port 8080 --factory
```

### Permisos de la DB

```bash
mkdir -p ~/.taskboard
chmod 700 ~/.taskboard
```

### Tests fallan con errores de thread

Los tests web usan `TestClient` en un thread background. Asegurar que el fixture `client` usa `check_same_thread=False`.

### Docker no arranca

```bash
docker compose logs taskboard
docker compose up -d --build
```
