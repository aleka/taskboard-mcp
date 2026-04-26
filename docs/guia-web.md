# Guía del web dashboard

Referencia completa de páginas, acciones HTMX, partials y REST API del dashboard web de Taskboard MCP.

---

## Páginas (GET)

Todas las páginas se sirven via Jinja2 con layout `base.html`. Las rutas están en `taskboard/web/routes/pages.py`.

### `/` — Dashboard

Página principal con vista general del sistema.

**Contenido:**
- Métricas globales (total tareas, completadas, pendientes, tasa de completitud)
- Lista de proyectos activos
- Actividad reciente: últimas 10 tareas completadas en los últimos 7 días
- Links a `/projects/{slug}` desde las tareas recientes

**Datos inyectados al template:**

| Variable | Tipo | Descripción |
|----------|------|-------------|
| `metrics` | `dict` | Métricas globales via `store.get_metrics()` |
| `projects` | `list[dict]` | Todos los proyectos via `store.list_projects()` |
| `recent_tasks` | `list[dict]` | Últimas 10 tareas completadas (7 días) |
| `project_slugs` | `dict[str, str]` | Mapa `name → slug` para links |

---

### `/projects` — Lista de proyectos

Muestra todos los proyectos con sus métricas individuales.

**Contenido:**
- Tabla de proyectos con nombre, slug, origen, path
- Métricas por proyecto: total tareas, completadas, pendientes

**Datos inyectados al template:**

| Variable | Tipo | Descripción |
|----------|------|-------------|
| `projects` | `list[dict]` | Proyectos con `metrics` enrichido por `store.get_metrics(project=p["name"])` |

---

### `/projects/{slug}` — Detalle de proyecto

Detalle de un proyecto con su tabla de tareas y filtros.

**Contenido:**
- Info del proyecto (nombre, slug, origen, path)
- Tabla de tareas del proyecto con acciones (completar, cambiar status)
- Filtro por status via query param `?status=in_progress`

**Query params:**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `status` | `str` | `""` | Filtrar por status. Valores: `todo`, `in_progress`, `blocked`, `done`, `cancelled` |

**Datos inyectados al template:**

| Variable | Tipo | Descripción |
|----------|------|-------------|
| `project` | `dict \| None` | Datos del proyecto (`None` si no existe, devuelve 404) |
| `tasks` | `list[dict]` | Tareas del proyecto (hasta 500) |
| `slug` | `str` | Slug desde la URL |
| `status_filter` | `str` | Status activo del filtro |

**Gotchas:**
- Si el slug no existe, renderiza con `project=None` y status 404 (no lanza excepción).
- El store filtra por `project_name` (nombre interno), pero la ruta recibe `slug`. Se resuelve via `store.get_project(slug)`.

---

### `/timeline` — Timeline de tareas completadas

Vista cronológica de tareas completadas, agrupadas por semana.

**Contenido:**
- Toggle entre vista semana y mes
- Filtro por proyecto via query param
- Grupos de semanas con tareas completadas en cada una

**Query params:**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `view` | `str` | `"week"` | Granularidad: `"week"` o `"month"` |
| `project` | `str` | `""` | Slug del proyecto para filtrar |

**Datos inyectados al template:**

| Variable | Tipo | Descripción |
|----------|------|-------------|
| `timeline_data` | `list[dict]` | Grupos semanales con `week_label` y `tasks` |
| `current_view` | `str` | Vista activa (`week` o `month`) |
| `project_filter` | `str` | Slug del proyecto activo en el filtro |
| `projects` | `list[dict]` | Todos los proyectos (para el selector) |

**Notas:**
- El `project` query param recibe un slug, que se resuelve a `name` internamente para el store.

---

### `/reports` — Reportes con filtros

Métricas filtradas con preview en pantalla y link de descarga CSV.

**Contenido:**
- Cards de métricas (total, completadas, tasa)
- Desglose por status y tipo
- Link de descarga CSV con los mismos filtros aplicados

**Query params:**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `start_date` | `str` | `""` | Fecha desde (`YYYY-MM-DD`) |
| `end_date` | `str` | `""` | Fecha hasta (`YYYY-MM-DD`) |
| `project` | `str` | `""` | Nombre del proyecto para filtrar |

**Datos inyectados al template:**

| Variable | Tipo | Descripción |
|----------|------|-------------|
| `metrics` | `dict` | Métricas filtradas |
| `projects` | `list[dict]` | Todos los proyectos (para el selector) |
| `start_date` | `str` | Fecha desde del filtro activo |
| `end_date` | `str` | Fecha hasta del filtro activo |
| `project` | `str` | Proyecto activo en el filtro |
| `csv_url` | `str` | URL de descarga CSV con los filtros aplicados |
| `has_filters` | `bool` | `True` si hay al menos un filtro activo |

**Notas:**
- El `csv_url` se construye dinámicamente con los mismos query params: `/api/export/csv?start_date=...&end_date=...&project=...`.
- Si no hay filtros, `csv_url` apunta a `/api/export/csv` sin parámetros (exporta todo).

---

## Acciones HTMX (POST `/actions/*`)

Endpoints que aceptan `application/x-www-form-urlencoded` y devuelven HTML o redirigen. Definidos en `taskboard/web/routes/actions.py`.

> **Regla de oro:** Los forms HTMX POSTean a `/actions/*`, NUNCA a `/api/*` (que espera JSON).

---

### `POST /actions/tasks/add` — Crear tarea

Crea una tarea desde el form del dashboard y redirige al proyecto.

**Campos del form:**

| Campo | Tipo | Requerido | Default | Descripción |
|-------|------|-----------|---------|-------------|
| `project` | `str` | Sí | — | Nombre del proyecto |
| `title` | `str` | Sí | — | Título de la tarea |
| `type` | `str` | No | `"chore"` | Tipo de tarea |
| `priority` | `str` | No | `"medium"` | Prioridad |

**Respuestas:**

| Caso | Status | Contenido |
|------|--------|-----------|
| Éxito | 303 | Redirect a `/projects/{slug}` |
| Faltan campos | 400 | `<span class="error-msg">Project and title are required.</span>` |
| ValueError | 400 | `<span class="error-msg">{mensaje del store}</span>` |
| Error interno | 500 | `<span class="error-msg">Internal error creating task.</span>` |

**Notas:**
- El redirect usa `303 See Other` (HTMX lo sigue correctamente).
- Resuelve el slug del proyecto via `store.get_project_by_name()` para construir la URL de redirect.

---

### `POST /actions/tasks/{task_id}/complete` — Completar tarea

Marca una tarea como completada y devuelve la fila actualizada.

**Path params:**

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `task_id` | `str` | ID de la tarea |

**Respuestas:**

| Caso | Status | Contenido |
|------|--------|-----------|
| Éxito | 200 | Partial `partials/task_row.html` con la tarea actualizada |
| No encontrada | 404 | `<tr><td colspan="7" class="error-msg">Task {id} not found</td></tr>` |
| Error interno | 500 | `<tr><td colspan="7" class="error-msg">Error completing task {id}</td></tr>` |

**Uso HTMX:**
```html
<button hx-post="/actions/tasks/{{ task.task_id }}/complete"
        hx-target="closest tr"
        hx-swap="outerHTML">
  Completar
</button>
```

---

### `POST /actions/tasks/{task_id}/status` — Cambiar status

Actualiza el status de una tarea y devuelve la fila actualizada.

**Path params:**

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `task_id` | `str` | ID de la tarea |

**Campos del form:**

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `status` | `str` | Sí | Nuevo status (`todo`, `in_progress`, `blocked`, `done`, `cancelled`) |

**Respuestas:**

| Caso | Status | Contenido |
|------|--------|-----------|
| Éxito | 200 | Partial `partials/task_row.html` con la tarea actualizada |
| Falta status | 400 | `<tr><td colspan="7" class="error-msg">Status field is required</td></tr>` |
| No encontrada | 404 | `<tr><td colspan="7" class="error-msg">Task {id} not found</td></tr>` |
| Error interno | 500 | `<tr><td colspan="7" class="error-msg">Error updating task {id}</td></tr>` |

---

## HTMX Partials (GET `/partials/*`)

Fragments HTML para swaps dinámicos sin recargar la página. Definidos en `taskboard/web/routes/partials.py`.

> Los partials NO incluyen `base.html` — son fragmentos sueltos para inyectar en el DOM.

---

### `GET /partials/task-list` — Lista filtrada de tareas

Devuelve una tabla HTML con las tareas que matchean los filtros.

**Query params:**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `project` | `str` | `""` | Filtrar por nombre de proyecto |
| `status` | `str` | `""` | Filtrar por status |
| `limit` | `int` | `20` | Máximo de tareas |

**Template:** `partials/task_list.html`

---

### `GET /partials/task-row/{task_id}` — Fila individual de tarea

Devuelve una sola fila `<tr>` para reemplazar una fila existente (ej: después de cambiar status).

**Path params:**

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `task_id` | `str` | ID de la tarea |

**Respuesta:** `partials/task_row.html` o error 404 si no existe.

---

### `GET /partials/metrics` — Cards de métricas

Devuelve las cards de métricas como fragmento HTML.

**Query params:**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `project` | `str` | `""` | Filtrar por proyecto |
| `start_date` | `str` | `""` | Fecha desde (`YYYY-MM-DD`) |
| `end_date` | `str` | `""` | Fecha hasta (`YYYY-MM-DD`) |

**Template:** `partials/metrics_cards.html`

---

### `GET /partials/timeline-group` — Grupo de timeline

Devuelve los grupos de timeline como fragmento HTML.

**Query params:**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `view` | `str` | `"week"` | Granularidad: `"week"` o `"month"` |
| `project` | `str` | `""` | Filtrar por nombre de proyecto |

**Template:** `partials/timeline_group.html`

---

## REST API (`/api/*`)

Endpoints JSON para acceso programático. Definidos en `taskboard/web/routes/api.py`.

> Para detalle completo de cada endpoint, ver el código fuente en `taskboard/web/routes/api.py`.

### Resumen de endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/tasks` | Listar tareas con filtros (query params) |
| `POST` | `/api/tasks` | Crear tarea (JSON body) → 201 |
| `GET` | `/api/tasks/{task_id}` | Detalle de tarea → 404 si no existe |
| `PATCH` | `/api/tasks/{task_id}` | Actualizar status (JSON body con `status`) |
| `DELETE` | `/api/tasks/{task_id}` | Eliminar tarea → `{"deleted": true}` |
| `GET` | `/api/projects` | Listar todos los proyectos |
| `POST` | `/api/projects` | Crear proyecto (JSON body) → 201 |
| `GET` | `/api/projects/{slug}` | Detalle de proyecto → 404 si no existe |
| `GET` | `/api/metrics` | Métricas con filtros (query params) |
| `GET` | `/api/export/csv` | Descargar CSV con header `Content-Disposition: attachment` |

### Diferencias clave vs acciones HTMX

| Aspecto | `/api/*` | `/actions/*` |
|---------|----------|--------------|
| Content-Type request | `application/json` | `application/x-www-form-urlencoded` |
| Content-Type response | `application/json` | `text/html` (fragments) |
| Autenticación | Ninguna | Ninguna |
| Uso | Scripts, integraciones, curl | Formularios del dashboard web |

### Notas de la API

- Todas las respuestas de error siguen el formato `{"error": "mensaje"}`.
- `POST /api/tasks` acepta campos adicionales: `description`, `tags` (array), `source`.
- `POST /api/projects` acepta campos adicionales: `display_name`, `slug`, `origin`, `repo`, `path`, `tags`.
- `GET /api/export/csv` devuelve `text/csv` con header de descarga, a diferencia del tool MCP que devuelve el CSV como string JSON.
