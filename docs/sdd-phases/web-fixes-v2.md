# Web UI Fixes & Enhancements v2

**Fecha:** 26/04/2026
**Proyecto:** taskboard-mcp
**Estado:** ✅ Completado — 186 tests, 0 failures

---

## Índice

1. [Resumen](#resumen)
2. [Cambio 1: Página de Detalle de Tarea](#cambio-1-página-de-detalle-de-tarea)
3. [Cambio 2: Sorting en Tabla de Proyecto](#cambio-2-sorting-en-tabla-de-proyecto)
4. [Cambio 3: BUG — Projects Section Refresh](#cambio-3-bug--projects-section-refresh)
5. [Cambio 4: BUG — Recent Activity Refresh](#cambio-4-bug--recent-activity-refresh)
6. [Orden de Ejecución](#orden-de-ejecución)
7. [Seguimiento de Progreso](#seguimiento-de-progreso)

---

## Resumen

| Cambio | Tipo | Severidad | Archivos nuevos | Archivos modif |
|--------|------|-----------|-----------------|----------------|
| 1. Task detail page | Feature | — | 1 template | store.py, pages.py, app.py, 4 templates |
| 2. Sorting proyecto | Enhancement | — | 0 | store.py, pages.py, project_detail.html |
| 3. Projects refresh | BUG | High | 1 template | dashboard.html, partials.py |
| 4. Recent activity refresh | BUG | High | 1 template | dashboard.html, partials.py |

**Total:** 3 templates nuevos, ~10 archivos modificados, ~2 archivos de tests

---

## Cambio 1: Página de Detalle de Tarea

### Objetivo

Acceder a cada tarea individualmente desde `/tasks/{task_id}`, ver todos sus campos, navegar al proyecto, y navegar a la tarea anterior/siguiente dentro del mismo proyecto.

### Análisis

**Campos del schema real** (tabla `tasks`):
```
id, task_id, title, type, project_name, status, source, priority,
created_at, completed_at, git_commit, git_branch, summary, tags, description
```

**No existe** ninguna ruta ni template para vista individual de tarea hoy.

### Plan de Implementación

#### 1a. Store: nuevo método `get_task_neighbors()`

**Archivo:** `taskboard/store.py`

```python
def get_task_neighbors(self, task_id: str) -> dict[str, Any] | None:
    """Return {prev_task_id, next_task_id} for navigation within the same project.

    Uses the current task's created_at to determine order.
    Returns None if task_id doesn't exist.
    """
```

**Lógica SQL:**
- Obtener `project_name` y `created_at` de la tarea actual
- `prev`: `SELECT task_id FROM tasks WHERE project_name = ? AND created_at < ? ORDER BY created_at DESC LIMIT 1`
- `next`: `SELECT task_id FROM tasks WHERE project_name = ? AND created_at > ? ORDER BY created_at ASC LIMIT 1`
- Retorna `{"prev": "tb_044" | None, "next": "tb_046" | None}`

**Tests:**
- Tarea en el medio → tiene prev y next
- Primera tarea del proyecto → solo next
- Última tarea del proyecto → solo prev
- Tarea inexistente → None

#### 1b. Route handler: `task_detail()`

**Archivo:** `taskboard/web/routes/pages.py`

```python
async def task_detail(request: Request) -> HTMLResponse:
    """GET /tasks/{task_id} — full task detail with navigation."""
```

**Datos que pasa al template:**
- `task`: dict completa de `store.get_task(task_id)`
- `project`: dict del proyecto via `store.get_project_by_name(task.project_name)`
- `neighbors`: dict de `store.get_task_neighbors(task_id)` con `{prev, next}`

#### 1c. Template: `task_detail.html`

**Archivo:** `taskboard/web/templates/task_detail.html` (NUEVO)

**Layout tipo "ficha":**

```
← Back to [Project Name]          tb_045 — Investigación (research)
                                   ─────────────────────────────
                                   [← Prev: tb_044]  [Next: tb_046 →]

┌─────────────────────────────────────────────────────────────────┐
│ Campo          │ Valor                                         │
│ ─────────────  │ ─────────────────────────────────────────────  │
│ task_id        │ tb_045                                        │
│ title          │ Investigar y documentar mapeo columnas...     │
│ type           │ chore                                         │
│ status         │ done (badge)                                  │
│ priority       │ high                                          │
│ source         │ manual                                        │
│ project        │ taskboard → link a /projects/tb               │
│ created_at     │ 2026-04-26 19:59:55                           │
│ completed_at   │ 2026-04-26 20:09:16                           │
│ git_commit     │ abc123 (si existe)                            │
│ git_branch     │ main (si existe)                              │
│ description    │ (texto multilinea si existe)                   │
│ summary        │ (texto multilinea si existe)                   │
│ tags           │ [tag1, tag2] (parsear JSON)                   │
└─────────────────────────────────────────────────────────────────┘
```

**Elementos interactivos:**
- Breadcrumb: `Dashboard > [Project Name] > tb_045`
- Link al proyecto: click en el nombre del proyecto → `/projects/{slug}`
- Botón "← Anterior": solo visible si `neighbors.prev` existe → `/tasks/{prev}`
- Botón "Siguiente →": solo visible si `neighbors.next` existe → `/tasks/{next}`
- Status badge con color (igual que project_detail)
- Tags renderizadas como badges
- Description y summary en bloques tipo `<pre>` o `<div class="long-text">`

#### 1d. Registrar ruta

**Archivo:** `taskboard/web/app.py`

Agregar:
```python
Route("/tasks/{task_id}", pages.task_detail, name="task-detail"),
```

#### 1e. Actualizar links existentes

**Archivos a modificar (task_id links):**

| Archivo | Cambio |
|---------|--------|
| `project_detail.html` | `<td>{{ task.task_id }}</td>` → `<td><a href="/tasks/{{ task.task_id }}">{{ task.task_id }}</a></td>` |
| `partials/task_list.html` | `<a href="/projects/{{ task.project_name }}">` → `<a href="/tasks/{{ task.task_id }}">` |
| `partials/task_row.html` | `<a href="/projects/{{ task.project_name }}">` → `<a href="/tasks/{{ task.task_id }}">` |
| `dashboard.html` (Recent Activity) | Agregar link `/tasks/{{ task.task_id }}` al task_id en la tabla |

#### 1f. Tests

**Archivo:** `tests/test_store.py` — tests de `get_task_neighbors()`
**Archivo:** `tests/test_web_routes.py` — test de `GET /tasks/{task_id}` (200, 404, contenido)

---

## Cambio 2: Sorting en Tabla de Proyecto

### Objetivo

Columnas sortables en `/projects/{slug}`: `created_at`, `completed_at`, `status`, `priority`.

### Análisis

- `store.list_tasks()` tiene `ORDER BY created_at DESC` hardcodeado
- No hay parámetros de sort en ningún handler

### Plan de Implementación

#### 2a. Store: parámetros `order_by` y `order_dir` en `list_tasks()`

**Archivo:** `taskboard/store.py`

```python
def list_tasks(
    self,
    project: str | None = None,
    status: str | None = None,
    type: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 100,
    offset: int = 0,
    order_by: str = "created_at",   # NUEVO
    order_dir: str = "DESC",         # NUEVO
) -> list[dict[str, Any]]:
```

**Whitelist de columnas permitidas:**
```python
_ALLOWED_ORDER = {"created_at", "completed_at", "status", "priority", "type", "title"}
_ALLOWED_DIR = {"ASC", "DESC"}
```

**Validación:**
- Si `order_by` no está en whitelist → usar default `created_at`
- Si `order_dir` no es ASC/DESC → usar default `DESC`

#### 2b. Page handler: pasar sort params

**Archivo:** `taskboard/web/routes/pages.py`

En `project_detail()`:
```python
sort_by = request.query_params.get("sort", "created_at")
sort_dir = request.query_params.get("dir", "DESC")
tasks = store.list_tasks(
    project=project["name"],
    status=status_filter or None,
    limit=500,
    order_by=sort_by,
    order_dir=sort_dir,
)
```

#### 2c. Template: headers interactivos

**Archivo:** `taskboard/web/templates/project_detail.html`

Headers de tabla con HTMX:
```html
<th>
    <button hx-get="/projects/{{ slug }}?sort=created_at&dir={toggle}&status={{ status_filter }}"
            hx-target="#task-list" hx-push-url="true">
        Created {% if sort_by == 'created_at' %}{{ sort_icon }}{% endif %}
    </button>
</th>
```

**Comportamiento:**
- Click en columna activa → invierte dirección (ASC↔DESC)
- Click en otra columna → esa columna ASC por defecto
- Indicador visual: ▲ (ASC) o ▼ (DESC)
- El `hx-push-url="true"` actualiza la URL para que se mantenga el estado del sort

#### 2d. Tests

**Archivo:** `tests/test_store.py`
- Test default sort (created_at DESC)
- Test sort by priority ASC
- Test sort by completed_at DESC
- Test invalid column → fallback a created_at
- Test invalid direction → fallback a DESC

---

## Cambio 3: BUG — Projects Section Refresh

### Problema

El botón "Refresh" de Projects dispara `hx-get="/partials/metrics"` y carga las **metric cards** dentro de la sección de Projects. Esto:
1. Muestra las 4 metric cards (Total, Completed, Pending, Rate) en vez de los project cards
2. Rompe el layout horizontal del project-grid

### Causa Raíz

```html
<!-- dashboard.html líneas 33-39 — INCORRECTO -->
<button hx-get="/partials/metrics" hx-target="#metrics-refresh">
    Refresh
</button>
<div id="metrics-refresh"></div>  <!-- ← target es un div vacío AQUÍ -->
```

### Fix

#### 3a. Nuevo partial: `project_cards()`

**Archivo:** `taskboard/web/routes/partials.py`

```python
async def project_cards(request: Request) -> HTMLResponse:
    """GET /partials/project-cards — project grid fragment."""
    store = _get_store(request)
    templates = _get_templates(request)
    projects = store.list_projects()
    return templates.TemplateResponse(request, "partials/project_cards.html", {"projects": projects})
```

#### 3b. Nuevo template: `partials/project_cards.html`

**Archivo:** `taskboard/web/templates/partials/project_cards.html` (NUEVO)

Contenido: el `<div class="project-grid">` loop que ya existe en `dashboard.html`, extraído como partial.

#### 3c. Fix dashboard.html

**Archivo:** `taskboard/web/templates/dashboard.html`

Cambios:
1. El botón Refresh → `hx-get="/partials/project-cards"` y `hx-target="#project-grid"`
2. Envolver el grid en `<div id="project-grid">`
3. Eliminar `<div id="metrics-refresh"></div>`

#### 3d. Registrar ruta

**Archivo:** `taskboard/web/app.py`

```python
Route("/partials/project-cards", partials.project_cards, name="partial-project-cards"),
```

---

## Cambio 4: BUG — Recent Activity Refresh

### Problema

El render inicial usa la tabla inline de `dashboard.html` con columnas `Task | Project | Type | Completed`. Al hacer Refresh, se carga `partials/task_list.html` con columnas completamente distintas: `ID | Title | Type | Status | Priority | Created | Completed | Actions`.

### Causa Raíz

```html
<!-- dashboard.html líneas 60-67 — INCORRECTO -->
<button hx-get="/partials/task-list?limit=10" hx-target="#recent-tasks">
    Refresh
</button>
```

`/partials/task-list` usa `store.list_tasks()` (todas las tasks, sin filtrar por completadas recientes) y renderiza con `task_list.html` (formato genérico).

### Fix

#### 4a. Nuevo partial: `recent_activity()`

**Archivo:** `taskboard/web/routes/partials.py`

```python
async def recent_activity(request: Request) -> HTMLResponse:
    """GET /partials/recent-activity — recent completed tasks fragment."""
    store = _get_store(request)
    templates = _get_templates(request)
    days = int(request.query_params.get("days", "7"))
    recent_tasks = store.get_recent_activity(days=days)[:10]
    projects = store.list_projects()
    project_slugs = {p["name"]: p["slug"] for p in projects}
    return templates.TemplateResponse(
        request, "partials/recent_activity.html",
        {"recent_tasks": recent_tasks, "project_slugs": project_slugs},
    )
```

#### 4b. Nuevo template: `partials/recent_activity.html`

**Archivo:** `taskboard/web/templates/partials/recent_activity.html` (NUEVO)

Mismas columnas que el render inicial: `Task | Project | Type | Completed`
- Task: `<a href="/tasks/{task_id}">{task_id} — {title}</a>`
- Project: `project_name`
- Type: `type`
- Completed: `completed_at`

#### 4c. Fix dashboard.html

**Archivo:** `taskboard/web/templates/dashboard.html`

Cambios:
1. Botón Refresh → `hx-get="/partials/recent-activity?days=7"` y `hx-target="#recent-tasks"`
2. Extraer la tabla inline a un `{% include "partials/recent_activity.html" %}` para DRY (misma data, mismo partial)

#### 4d. Registrar ruta

**Archivo:** `taskboard/web/app.py`

```python
Route("/partials/recent-activity", partials.recent_activity, name="partial-recent-activity"),
```

---

## Orden de Ejecución

```
Phase A: BUG fixes (sin dependencias)
  ├── Cambio 3: Projects refresh fix
  └── Cambio 4: Recent Activity refresh fix
      │
Phase B: Nueva funcionalidad
  ├── Cambio 1: Task detail page (con neighbors)
  │     ├── store.py: get_task_neighbors()
  │     ├── pages.py: task_detail()
  │     ├── task_detail.html (nuevo)
  │     ├── app.py: nueva ruta
  │     ├── Links en templates existentes
  │     └── Tests
  │
Phase C: Enhancement
  └── Cambio 2: Sorting en tabla de proyecto
        ├── store.py: order_by/order_dir en list_tasks()
        ├── pages.py: pasar sort params
        ├── project_detail.html: headers interactivos
        └── Tests
```

**Rationale:** Los bugs primero porque son fixes rápidos y mejoran la experiencia inmediata. Task detail segundo porque es la feature más pedida. Sorting último porque es un enhancement sobre la tabla que ya existe.

---

## Seguimiento de Progreso

### Phase A: BUG Fixes

| Tarea | Estado | Notas |
|-------|--------|-------|
| A1. Store: sin cambios necesarios | ✅ Confirmado | — |
| A2. Partial `project_cards` (handler + template) | ✅ Completado | Nuevo partial + template |
| A3. Fix dashboard.html Projects section | ✅ Completado | hx-get corregido, #metrics-refresh eliminado |
| A4. Registrar ruta `/partials/project-cards` | ✅ Completado | app.py actualizado |
| A5. Partial `recent_activity` (handler + template) | ✅ Completado | Nuevo partial + template |
| A6. Fix dashboard.html Recent Activity section | ✅ Completado | {% include %} para DRY |
| A7. Registrar ruta `/partials/recent-activity` | ✅ Completado | app.py actualizado |
| A8. Tests de nuevos partials | ✅ Completado | 165 tests pasando |

### Phase B: Task Detail Page

| Tarea | Estado | Notas |
|-------|--------|-------|
| B1. Store: `get_task_neighbors()` + tests | ✅ Completado | 6 tests, usa id como tiebreaker |
| B2. Route handler `task_detail()` | ✅ Completado | Con project, neighbors, tags parseados |
| B3. Template `task_detail.html` | ✅ Completado | Breadcrumb + prev/next + all fields |
| B4. Registrar ruta `/tasks/{task_id}` | ✅ Completado | app.py actualizado |
| B5. Actualizar links en `project_detail.html` | ✅ Completado | task_id → /tasks/{id} |
| B6. Actualizar links en `partials/task_list.html` | ✅ Completado | task_id → /tasks/{id} |
| B7. Actualizar links en `partials/task_row.html` | ✅ Completado | task_id → /tasks/{id} |
| B8. Actualizar links en `dashboard.html` | ✅ Completado | Via partial recent_activity |
| B9. Tests route `GET /tasks/{task_id}` | ✅ Completado | 6 tests (200, 404, breadcrumb, neighbors) |

### Phase C: Sorting

| Tarea | Estado | Notas |
|-------|--------|-------|
| C1. Store: `order_by`/`order_dir` en `list_tasks()` + tests | ✅ Completado | Whitelist validation, 6 tests |
| C2. Page handler: pasar sort params | ✅ Completado | sort_by + sort_dir en contexto |
| C3. Template: headers interactivos con HTMX | ✅ Completado | 4 columnas: Created, Completed, Status, Priority |
| C4. CSS para headers sortables | ✅ Completado | .sortable button, hover, active |
| C5. Tests de sorting en web routes | ✅ Completado | 3 tests (sort params, con filtros) |

### Test Results

| Suite | Tests | Estado |
|-------|-------|--------|
| test_store.py | 72 (+6 neighbors, +6 sorting) | ✅ 186 total |
| test_mcp_server.py | 34 | ✅ |
| test_web_routes.py | 31 (+6 task detail, +3 sorting) | ✅ |
| test_api_routes.py | 27 | ✅ |
| **Total** | **186** | **0 failures** |

---

## Archivos Nuevos

| Archivo | Propósito |
|---------|-----------|
| `taskboard/web/templates/task_detail.html` | Vista individual de tarea |
| `taskboard/web/templates/partials/project_cards.html` | Partial para refresh de projects |
| `taskboard/web/templates/partials/recent_activity.html` | Partial para refresh de recent activity |

## Archivos Modificados

| Archivo | Cambios |
|---------|---------|
| `taskboard/store.py` | `get_task_neighbors()`, `order_by`/`order_dir` en `list_tasks()` |
| `taskboard/web/routes/pages.py` | `task_detail()` handler, sort params en `project_detail()` |
| `taskboard/web/routes/partials.py` | `project_cards()`, `recent_activity()` |
| `taskboard/web/app.py` | 3 rutas nuevas |
| `taskboard/web/templates/dashboard.html` | Fix sections + include partials |
| `taskboard/web/templates/project_detail.html` | Links + sort headers |
| `taskboard/web/templates/partials/task_list.html` | Link task_id → `/tasks/{id}` |
| `taskboard/web/templates/partials/task_row.html` | Link task_id → `/tasks/{id}` |

## Tests

| Archivo | Tests nuevos estimados |
|---------|----------------------|
| `tests/test_store.py` | +12 (neighbors: 6, sort: 6) |
| `tests/test_web_routes.py` | +9 (task detail: 6, sort: 3) |
| **Total nuevos** | **21 tests** (165 → 186) |
