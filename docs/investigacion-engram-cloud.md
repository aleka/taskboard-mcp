# Investigación: Engram Cloud → Taskboard MCP + Web Dashboard

> **Fecha:** 25 de abril de 2026  
> **Autor:** Aleka  
> **Proyecto:** taskboard-mcp  
> **Fuente de investigación:** [Gentleman-Programming/engram](https://github.com/Gentleman-Programming/engram) — releases v1.10.x a v1.13.1

---

## Objetivo

Investigar la arquitectura de Engram Cloud para extraer patrones, decisiones de diseño y lecciones aplicables a la evolución del skill **taskboard** (actualmente basado en SQLite + Python one-liners) hacia un **MCP server con web dashboard liviano**, deployable via Docker para uso local o en VPS.

---

## Estado Actual del Taskboard

| Dato | Valor |
|------|-------|
| Ubicación | `~/.taskboard/taskboard.db` |
| Proyectos registrados | 13 |
| Tareas registradas | 175 |
| Entradas en historial | 271 |
| Interface actual | Skill + Python one-liners via Bash |
| Stack | SQLite (WAL) + Python `sqlite3` stdlib |

### Proyectos activos

| Proyecto | Slug |
|----------|------|
| C Study | cs |
| Gentle AI | gai |
| Guardian Angel | gga |
| Hermes Finanzas | hf |
| Hermes OdontoIA | ho |
| Odonto IA | od |
| OpenClaw | oc |
| OpenClaw Extensions | oce |
| OpenClaw Finanzas | ocf |
| TaskBoard | tb |
| Maguen | mag |
| LaSalle | ls |
| OpenCode Config | occ |

---

## Arquitectura de Engram Cloud (Lo que analizamos)

### Visión General

Engram es un sistema de memoria persistente para agentes de AI. Es un **binario Go único** con SQLite + FTS5, expuesto a través de múltiples interfaces:

```
Agente (OpenCode / Claude Code / Cursor / etc.)
    ↓ (plugin o MCP)
Engram Go Binary
    ↓
SQLite + FTS5 (~/.engram/engram.db)
```

### Interfaces que expone

| Interface | Tecnología | Propósito |
|-----------|-----------|-----------|
| **CLI** | Go `cobra`-like | Uso directo en terminal (`engram search`, `engram save`) |
| **MCP Server** | stdio transport | Integración con agentes AI (13 tools) |
| **HTTP REST API** | `net/http` (Go 1.22+ routing) | Plugins e integraciones (port 7437) |
| **TUI** | Bubbletea + Lipgloss | Browsing interactivo en terminal |
| **Web Dashboard** | HTMX + server-rendered HTML | Visualización en navegador |

**Lección clave:** El `store` es el núcleo. Todo lo demás son **interfaces delgadas** que hablan al mismo store. No hay duplicación de datos.

### Estructura del proyecto Engram

```
engram/
├── cmd/engram/main.go              # CLI entrypoint
├── internal/
│   ├── store/store.go              # Core: SQLite + FTS5 + operaciones
│   ├── server/server.go            # HTTP REST API server (port 7437)
│   ├── mcp/mcp.go                  # MCP stdio server (13 tools)
│   ├── sync/sync.go                # Git sync: manifest + chunks (gzipped JSONL)
│   ├── tui/                        # Bubbletea terminal UI
│   │   ├── model.go                # Pantallas, Model struct, Init()
│   │   ├── styles.go               # Lipgloss (Catppuccin Mocha)
│   │   ├── update.go               # Update(), handleKeyPress()
│   │   └── view.go                 # View(), renderers por pantalla
│   └── version/check.go            # Version check
├── skills/                         # Skills para contribución con AI
├── plugin/                         # Plugins por agente (OpenCode, Claude Code)
└── docs/
```

### Server Architecture (HTTP API)

Del skill `engram-server-api`:

- Cada endpoint nuevo **debe tener tests** (success + error paths)
- Scripts y docs alineados con handlers reales
- No referenciar endpoints inexistentes en plugins/hooks

### Dashboard Web (HTMX)

Del skill `engram-dashboard-htmx`:

> *"Server-rendered HTML is the product; htmx enhances it, it does not replace it."*

Reglas de interacción HTMX en Engram:

1. **Server-rendered HTML es el producto** — HTMX lo mejora, no lo reemplaza
2. **Preferir `hx-get` y `hx-include` simples** sobre estado custom del lado del cliente
3. **Filtros deben preservar el estado activo** que el usuario espera entre interacciones
4. **Forms que mutan estado del sistema deben funcionar como HTTP POST normales**
5. **Partial endpoints devuelven HTML significativo por sí solos**, no fragments que dependen de JS oculto
6. **Search y filter controls deben componer limpiamente**
7. **Toggle actions deben reflejar visiblemente el estado resultante del server**
8. **Navegación conectada debe mantener URLs significativas y compartibles**
9. **Usar HTMX para velocidad, no para esconder business logic en el navegador**

### Sistema de Sync (Chunks + Git)

Engram usa un sistema de sincronización basado en chunks:

```
.engram/
├── manifest.json          ← índice de chunks (git-mergeable, append-only)
└── chunks/
    ├── a3f8c1d2.jsonl.gz ← chunk 1 (gzipped JSONL)
    └── b7d2e4f1.jsonl.gz ← chunk 2
```

- Cada chunk tiene hash SHA-256 como ID
- Append-only — nunca se modifican chunks existentes
- Manifest es el único archivo que git diff-ea (pequeño)
- Comprimidos: un chunk con 8 sesiones + 10 observaciones ≈ 2KB
- Import idempotente: `sync_chunks` table previene re-imports

### Cloud Features (v1.13.0)

Engram Cloud agrega:

- **Hosted sync** — push/pull flows para replicación local-first
- **Autosync** — sincronización automática en background
- **Project-scoped controls** — allowed-project enforcement, sync pause
- **Audit log** — visibilidad de intentos de sync rechazados
- **Obsidian Brain** (beta) — export de memoria como vault de Obsidian con graph view

### Características Técnicas Destacadas

| Característica | Implementación |
|---------------|---------------|
| Búsqueda full-text | FTS5 con sanitización de queries |
| Timeline | Progressive disclosure: search → timeline → full observation |
| Privacidad | Tags `<private>` stripped en plugin layer + store layer |
| Prompts de usuario | Tabla separada captura qué preguntó el usuario |
| Export/Import | JSON dump completo, atomic transaction |
| Compresión | Agent-driven — el agente ya tiene LLM, no se necesita servicio separado |
| No auto-capture | Raw tool calls NO se guardan — solo curated summaries del agente |

### Decisiones de Diseño de Engram

1. **Go sobre TypeScript** — Single binary, cross-platform, no runtime
2. **SQLite + FTS5 sobre vector DB** — FTS5 cubre 95% de use cases sin ChromaDB/Pinecone
3. **Agent-agnostic core** — Go binary es el cerebro, plugins delgados por agente
4. **Agent-driven compression** — El agente ya tiene LLM, no hace falta servicio separado
5. **Privacy a dos capas** — Strip en plugin Y en store
6. **Pure Go SQLite (modernc.org/sqlite)** — No CGO = true cross-platform binary
7. **No raw auto-capture** — Raw tool calls son ruidosos, agent salva curated summaries
8. **TUI con Bubbletea** — Interactive terminal UI siguiendo Elm architecture

---

## Qué Aprender de Engram Cloud para Taskboard

### 1. Multi-Interface Pattern

Engram expone la MISMA data a través de múltiples interfaces. Taskboard debe hacer lo mismo:

```
taskboard-mcp (Python)
├── MCP Server (stdio) → OpenCode agent registra tareas
├── HTTP REST API      → Web dashboard lee/escribe
├── CLI                → Uso rápido en terminal (opcional)
└── Web Dashboard      → Visualización + reportes + CSV export
    ↓
store.py (SQLite operations)
    ↓
~/.taskboard/taskboard.db
```

### 2. HTMX + Server-Rendered HTML (NO React/Vue)

**Esta es la lección más importante.** React consume mucha memoria, necesita build step, npm, node_modules, y para un proyecto personal es overkill total.

HTMX ofrece:
- **14KB de JS** vs React (~130KB solo el core + DOM virtual)
- **Sin build step** — no hay npm, webpack, vite, NADA
- **Server-rendered** — el servidor genera HTML, el navegador solo muestra
- **Progressive enhancement** — los forms funcionan como HTTP POST normales
- **Deployment trivial** — un solo contenedor Docker
- **Mantenible** — Python + templates HTML, un solo lenguaje

### 3. Docker Deployment Simple

Engram corre como un solo binario + SQLite. Taskboard puede hacer lo mismo:

```yaml
services:
  taskboard:
    build: .
    ports:
      - "7438:7438"
    volumes:
      - taskboard-data:/app/data
    environment:
      - TASKBOARD_DB=/app/data/taskboard.db
```

Sin Postgres, sin Node.js, sin Redis — solo Python + SQLite.

### 4. Store como Núcleo Compartido

El patrón clave: `store.py` es usado por TODOS los interfaces. No hay duplicación:

```python
# store.py — usado por MCP, Web, CLI
class TaskboardStore:
    def add_task(self, ...) -> str: ...
    def complete_task(self, ...) -> None: ...
    def get_timeline(self, ...) -> list: ...
    def get_metrics(self, ...) -> dict: ...
    def export_csv(self, ...) -> str: ...
```

### 5. Sync Simplificado

Engram usa chunks + git para sync multi-user. Taskboard tiene necesidades más simples:

- **Local mode**: MCP agent escribe directo a SQLite (como ahora)
- **Docker mode**: MCP agent llama HTTP API, web dashboard lee del mismo SQLite
- **VPS mode**: Mismo Docker, accesible desde cualquier lugar

---

## Arquitectura Propuesta para Taskboard MCP

### Stack

| Componente | Tecnología | Justificación |
|-----------|-----------|---------------|
| **MCP Server** | `fastmcp` (Python) | Mismo framework que drupal-scout-mcp, ecosistema unificado |
| **Web Framework** | `starlette` o `flask` | Ultraliviano, perfecto para HTMX |
| **Templates** | Jinja2 | Estándar de Python, server-rendered |
| **Interactividad** | HTMX (14KB) | Sin framework JS, partial updates |
| **Base de datos** | SQLite (misma schema actual) | Ya funciona, no cambia |
| **Docker** | Python 3.12 slim | ~50MB imagen, sin Node.js |
| **CSS** | Minimal custom o Pico CSS | Sin Tailwind build, sin framework CSS |

### Estructura de Archivos

```
taskboard-mcp/
├── taskboard/
│   ├── __init__.py
│   ├── store.py                  ← Core: SQLite operations (compartido)
│   ├── mcp_server.py             ← MCP server via fastmcp (stdio)
│   ├── web/
│   │   ├── __init__.py
│   │   ├── app.py                ← Flask/Starlette app
│   │   ├── routes/
│   │   │   ├── dashboard.py      ← GET / → overview
│   │   │   ├── projects.py       ← /projects, /projects/{name}
│   │   │   ├── tasks.py          ← /tasks CRUD + filtros
│   │   │   ├── timeline.py       ← /timeline view
│   │   │   ├── reports.py        ← /reports + CSV export
│   │   │   └── api.py            ← REST API endpoints
│   │   ├── templates/
│   │   │   ├── base.html         ← Layout con HTMX
│   │   │   ├── dashboard.html
│   │   │   ├── project_detail.html
│   │   │   ├── task_list.html
│   │   │   ├── timeline.html
│   │   │   ├── report.html
│   │   │   └── partials/         ← HTMX partials
│   │   │       ├── task_row.html
│   │   │       ├── project_card.html
│   │   │       └── metrics_cards.html
│   │   └── static/
│   │       ├── css/style.css
│   │       └── htmx.min.js       ← 14KB, sin build
│   ├── cli.py                    ← CLI commands (opcional)
│   └── sync.py                   ← Sync para futuro VPS push
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

### Flujo de Datos

```
┌─────────────────┐     MCP (stdio)      ┌──────────────┐
│  OpenCode Agent  │ ──── fastmcp ───────→ │              │
│  (Sesión de AI)  │                       │              │
└─────────────────┘                        │   store.py   │
                                           │   (SQLite)   │
┌─────────────────┐     HTTP API          │              │
│  Web Dashboard   │ ←── Flask/Starlette ─→│              │
│  (HTMX + HTML)   │                       │              │
└─────────────────┘                        └──────┬───────┘
                                                  │
                                           ┌──────▼───────┐
                                           │ taskboard.db │
                                           │ (SQLite)     │
                                           └──────────────┘
```

### Funcionalidades del Dashboard

1. **Dashboard principal** — Overview con métricas globales (total, completadas, pendientes)
2. **Vista por proyecto** — Click en proyecto → tareas, filtros por status/type
3. **Timeline** — Vista cronológica agrupada por semana
4. **Reportes** — Selector de rango de fechas → genera informe completo
5. **CSV Export** — Botón que genera y descarga CSV filtrado por proyecto/fechas
6. **CRUD de tareas** — Alta/baja/modificación desde la web
7. **Historial** — Ver el lifecycle completo de una tarea

### Endpoints HTTP Propuestos

```
# Web (HTML)
GET  /                          Dashboard overview
GET  /projects                  Lista de proyectos
GET  /projects/{name}           Detalle de proyecto con tareas
GET  /tasks                     Lista de tareas con filtros
GET  /timeline                  Timeline cronológico
GET  /reports                   Generador de reportes

# API (JSON)
GET  /api/projects              List projects
GET  /api/tasks?project=X&status=Y&from=DATE&to=DATE
POST /api/tasks                 Create task
PATCH /api/tasks/{id}           Update task
POST /api/tasks/{id}/complete   Complete task
GET  /api/metrics?from=DATE&to=DATE
GET  /api/export/csv?project=X&from=DATE&to=DATE

# HTMX Partials
GET  /partials/task-list?project=X&status=Y
GET  /partials/metrics-cards?from=DATE&to=DATE
GET  /partials/timeline-week?week=N
```

---

## Decisiones Diferentes a Engram

| Decisión | Engram | Taskboard | Por qué |
|----------|--------|-----------|---------|
| Lenguaje | Go | Python | Ecosistema unificado con drupal-scout-mcp, `fastmcp` nativo |
| FTS5 | Sí (búsqueda full-text) | No necesario | Queries son por project/status/date, no contenido textual |
| Auth | JWT + bcrypt | API key o basic auth | Un solo usuario, no multi-user |
| DB Cloud | Postgres option | SQLite siempre | Un solo usuario, SQLite es suficiente |
| Sync | Chunks + git + cloud | HTTP directo (futuro) | Single-user, no necesita git-based sync |
| Runtime | Single binary | Docker + Python | Más flexible para iterar, Python más accesible |

---

## Plan de Evolución por Fases

| Fase | Qué | Estado | Dependencias |
|------|-----|--------|-------------|
| **Phase 1** | Skill + SQLite + Python one-liners | ✅ HECHO | — |
| **Phase 2** | MCP server con `fastmcp` + store.py | 🔲 Siguiente | Python, fastmcp |
| **Phase 3** | HTTP API endpoints | 🔲 | Phase 2 |
| **Phase 4** | Web Dashboard con HTMX + Jinja2 | 🔲 | Phase 3 |
| **Phase 5** | Docker + docker-compose | 🔲 | Phase 4 |
| **Phase 6** | CSV Export + Report Generator web | 🔲 | Phase 4 |
| **Phase 7** | Auto-detect desde git log | 🔲 Futuro | Phase 2 |
| **Phase 8** | VPS deployment + sync | 🔲 Futuro | Phase 5 |

---

## Recursos y Referencias

- **Engram repo**: https://github.com/Gentleman-Programming/engram
- **Engram docs**: https://github.com/Gentleman-Programming/engram/blob/main/DOCS.md
- **HTMX**: https://htmx.org — 14KB, sin dependencias, progressive enhancement
- **fastmcp**: Framework Python para MCP servers (mismo que drupal-scout-mcp)
- **Skill actual**: `~/.config/opencode/skills/taskboard/SKILL.md`
- **Schema actual**: `~/.config/opencode/skills/taskboard/assets/data-model.md`
