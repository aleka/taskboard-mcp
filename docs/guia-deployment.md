# Guía de Deployment y Actualización de Código

## Arquitectura de Runtime

Taskboard MCP corre en **dos procesos** que comparten la misma DB:

```
~/.taskboard/taskboard.db (SQLite)
        │
        ├── Proceso 1: Docker Container (web UI)
        │   └── uvicorn → localhost:7438
        │       ├── /          → Dashboard (HTML + HTMX)
        │       ├── /projects  → Páginas de proyecto
        │       ├── /tasks     → Detalle de tarea
        │       ├── /api/*     → REST API (JSON)
        │       ├── /actions/* → HTMX form handlers
        │       ├── /partials/* → HTMX fragments
        │       └── /mcp       → MCP HTTP endpoint
        │
        └── Proceso 2: MCP Server local (OpenCode)
            └── start-mcp.sh → .venv/bin/python (stdio)
            └── 12 tools MCP (add_task, delete_task, delete_project, tags, etc.)
```

## Cómo Actualizar Código

### Cambios de código Python, templates, CSS, JS

```bash
# 1. Docker (web UI) — solo restart, NO rebuild
docker compose restart

# 2. MCP (OpenCode tools) — reinstalar en el venv
uv pip install -e . --reinstall
```

Ambos pasos son necesarios porque los procesos usan copias distintas del código:
- Docker monta `./taskboard:/app/taskboard` como volumen
- MCP usa `.venv/` local

### Cambios en dependencias (pyproject.toml)

```bash
# Docker: rebuild completo
docker compose build --no-cache && docker compose up -d

# MCP: reinstalar
uv pip install -e . --reinstall
```

## Checklist Rápido

| Qué cambió | Docker | MCP |
|-----------|--------|-----|
| `.py` (routes, store) | `docker compose restart` | `uv pip install -e . --reinstall` |
| `.html` (templates) | `docker compose restart` | No aplica |
| `.css` / `.js` | `docker compose restart` | No aplica |
| `pyproject.toml` | `docker compose build` + `up` | `uv pip install -e . --reinstall` |

## Timezone

- El Docker container usa `TZ=America/Argentina/Buenos_Aires` (UTC-3)
- Los timestamps en la DB se guardan en hora local argentina
- **Nunca** usar `datetime.now(timezone.utc)` ni SQLite `datetime('now')` — ambos son UTC
- Usar `datetime.now()` para timestamps en Python
- `add_task()` pasa `created_at` explícitamente — no depende del default de SQLite

## Verificar que todo funciona

```bash
# Tests
uv run pytest

# Docker healthy
docker compose ps

# Web UI responde
curl -s -o /dev/null -w "%{http_code}" http://localhost:7438/

# Task detail responde
curl -s -o /dev/null -w "%{http_code}" http://localhost:7438/tasks/tb_001

# API responde
curl -s http://localhost:7438/api/tasks?limit=1 | python3 -m json.tool
```
