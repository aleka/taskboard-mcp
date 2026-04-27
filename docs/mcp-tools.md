# Herramientas MCP — Referencia completa

12 herramientas disponibles para agentes de IA via MCP (OpenCode, Claude Desktop, etc.). Todas delegan a `TaskboardStore` y devuelven JSON.

---

## Valores válidos

### Status

| Valor | Descripción |
|-------|-------------|
| `todo` | Pendiente (default al crear) |
| `in_progress` | En progreso |
| `blocked` | Bloqueada |
| `done` | Completada |
| `cancelled` | Cancelada |

### Tipo de tarea

| Valor | Descripción |
|-------|-------------|
| `feature` | Nueva funcionalidad |
| `bugfix` | Corrección de bug |
| `refactor` | Refactorización |
| `config` | Cambio de configuración |
| `chore` | Tarea de mantenimiento (default) |
| `docs` | Documentación |
| `testing` | Tests |
| `infra` | Infraestructura |

### Prioridad

| Valor | Descripción |
|-------|-------------|
| `low` | Baja |
| `medium` | Media (default) |
| `high` | Alta |
| `urgent` | Urgente |

### Origen del proyecto

| Valor | Descripción |
|-------|-------------|
| `github` | Repositorio GitHub |
| `gitlab` | Repositorio GitLab |
| `local` | Proyecto local (default) |

---

## 1. `add_task` — Crear tarea

Crea una nueva tarea en un proyecto existente. El status inicial es siempre `todo`.

### Parámetros

| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `project` | `str` | Sí | — | Nombre del proyecto (debe existir previamente) |
| `title` | `str` | Sí | — | Título de la tarea |
| `type` | `str` | No | `"chore"` | Tipo de tarea (ver tabla arriba) |
| `description` | `str` | No | `""` | Descripción o notas |
| `tags` | `list[str] \| None` | No | `None` | Tags para agrupar (ej: `["refactor-ui", "compliance-fix"]`) |
| `priority` | `str` | No | `"medium"` | Prioridad de la tarea |

### Ejemplo de respuesta

```json
{
  "status": "success",
  "data": {
    "task_id": "myproj_001",
    "title": "Configurar CI/CD",
    "type": "config",
    "project_name": "myproj",
    "status": "todo",
    "source": "manual",
    "priority": "medium",
    "summary": "",
    "tags": "[\"ci\", \"infra\"]",
    "notes": "Usar GitHub Actions",
    "git_commit": null,
    "created_at": "2026-04-26 14:30:00",
    "completed_at": null
  }
}
```

### Notas

- El `task_id` se genera automáticamente con formato `{slug}_{NNN}` (slug del proyecto + número secuencial).
- El `source` siempre queda en `"manual"` desde MCP (no se pasa como parámetro).
- Si el proyecto no existe, devuelve `{"status": "error", "message": "..."}`.
- Los `tags` se almacenan como JSON en la columna `tags`. Útiles para agrupar tareas en métricas (ej: por sprint, por categoría).

---

## 2. `complete_task` — Completar tarea

Marca una tarea como completada (`status = "done"`) y registra el timestamp de completitud.

### Parámetros

| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `task_id` | `str` | Sí | — | ID de la tarea (ej: `"myproj_001"`) |
| `summary` | `str` | No | `""` | Resumen de lo realizado al completar |

### Ejemplo de respuesta

```json
{
  "status": "success",
  "data": {
    "task_id": "myproj_001",
    "title": "Configurar CI/CD",
    "status": "done",
    "completed_at": "2026-04-26 15:00:00",
    "summary": "Pipeline configurado con tests y deploy automático"
  }
}
```

### Notas

- Se registra entrada en `task_history` con transición de status.
- Si la tarea ya estaba en `done`, actualiza el `completed_at` de todas formas.
- Si el `task_id` no existe, devuelve error.

---

## 3. `update_task_status` — Cambiar status

Actualiza el status de una tarea a cualquier valor válido.

### Parámetros

| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `task_id` | `str` | Sí | — | ID de la tarea |
| `status` | `str` | Sí | — | Nuevo status (ver tabla de valores válidos) |
| `note` | `str` | No | `""` | Nota explicando el cambio de status |

### Ejemplo de respuesta

```json
{
  "status": "success",
  "data": {
    "task_id": "myproj_001",
    "title": "Configurar CI/CD",
    "status": "blocked",
    "completed_at": null
  }
}
```

### Notas

- Para completar una tarea, preferí `complete_task` que además setea `completed_at` y `summary`.
- Cada cambio de status se registra en `task_history` con el `from_status` y `to_status`.
- Pasar un status inválido no da error a nivel MCP (se inserta directamente en la DB) — el store no valida contra un enum.

---

## 4. `list_tasks` — Listar tareas

Lista tareas con filtros opcionales. Soporta paginación.

### Parámetros

| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `project` | `str \| None` | No | `None` | Filtrar por nombre de proyecto |
| `status` | `str \| None` | No | `None` | Filtrar por status |
| `type` | `str \| None` | No | `None` | Filtrar por tipo de tarea |
| `from_date` | `str \| None` | No | `None` | Tareas creadas en o después de esta fecha (`YYYY-MM-DD`) |
| `to_date` | `str \| None` | No | `None` | Tareas creadas en o antes de esta fecha (`YYYY-MM-DD`) |
| `limit` | `int` | No | `100` | Máximo de tareas a devolver |
| `offset` | `int` | No | `0` | Cantidad de tareas a saltear (paginación) |

### Ejemplo de respuesta

```json
{
  "status": "success",
  "data": [
    {
      "task_id": "myproj_003",
      "title": "Agregar tests de integración",
      "type": "testing",
      "project_name": "myproj",
      "status": "in_progress",
      "created_at": "2026-04-25 10:00:00",
      "completed_at": null
    },
    {
      "task_id": "myproj_002",
      "title": "Fix login redirect",
      "type": "bugfix",
      "project_name": "myproj",
      "status": "done",
      "completed_at": "2026-04-24 18:30:00"
    }
  ]
}
```

### Notas

- Los resultados están ordenados por `created_at DESC` (más recientes primero).
- Sin filtros, devuelve todas las tareas (hasta el `limit`).
- Las fechas usan formato `YYYY-MM-DD`. El store compara contra `created_at` que tiene formato `YYYY-MM-DD HH:MM:SS`, pero SQLite maneja la comparación correctamente.

---

## 5. `get_task` — Detalle de tarea

Obtiene el detalle completo de una tarea por su ID.

### Parámetros

| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `task_id` | `str` | Sí | — | ID de la tarea (ej: `"myproj_001"`) |

### Ejemplo de respuesta

```json
{
  "status": "success",
  "data": {
    "task_id": "myproj_001",
    "title": "Configurar CI/CD",
    "type": "config",
    "project_name": "myproj",
    "status": "done",
    "source": "manual",
    "priority": "medium",
    "summary": "Pipeline configurado",
    "tags": "[]",
    "notes": "Usar GitHub Actions",
    "git_commit": null,
    "created_at": "2026-04-26 14:30:00",
    "completed_at": "2026-04-26 15:00:00"
  }
}
```

### Notas

- Si la tarea no existe: `{"status": "error", "message": "Task 'tp_001' not found"}`.
- Devuelve todos los campos de la fila `tasks` como dict.

---

## 6. `delete_task` — Eliminar tarea

Elimina una tarea del taskboard (y su historial asociado).

### Parámetros

| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `task_id` | `str` | Sí | — | ID de la tarea (ej: `"myproj_001"`) |

### Ejemplo de respuesta

```json
{
  "status": "success",
  "data": {
    "deleted": "myproj_001"
  }
}
```

### Notas

- Si la tarea no existe: `{"status": "error", "message": "Task 'myproj_001' not found"}`.
- La eliminación es permanente — no hay soft delete ni undo.
- También elimina las entradas en `task_history` asociadas a la tarea.

---

## 7. `add_project` — Registrar proyecto

Registra un nuevo proyecto en el taskboard.

### Parámetros

| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `name` | `str` | Sí | — | Nombre interno del proyecto (único, se usa como FK) |
| `display_name` | `str` | Sí | — | Nombre legible para humanos |
| `slug` | `str` | Sí | — | Identificador corto para URLs (único) |
| `origin` | `str` | No | `"local"` | Origen del proyecto: `github`, `gitlab`, `local` |
| `path` | `str` | No | `""` | Path al filesystem del proyecto |

### Ejemplo de respuesta

```json
{
  "status": "success",
  "data": {
    "name": "myproj",
    "display_name": "Mi Proyecto",
    "slug": "myproj",
    "origin": "github",
    "path": "/home/user/repos/myproj",
    "tags": null
  }
}
```

### Notas

- Tanto `name` como `slug` deben ser únicos — si ya existen, SQLite lanza error de constraint.
- El `name` es el que se usa en `add_task` como `project` parameter (FK reference).
- El `slug` es el que se usa en las URLs del dashboard (`/projects/{slug}`).

---

## 8. `list_projects` — Listar proyectos

Lista todos los proyectos registrados, ordenados alfabéticamente por nombre.

### Parámetros

Ninguno.

### Ejemplo de respuesta

```json
{
  "status": "success",
  "data": [
    {
      "name": "myproj",
      "display_name": "Mi Proyecto",
      "slug": "myproj",
      "origin": "github",
      "path": "/home/user/repos/myproj",
      "tags": null
    },
    {
      "name": "sideproj",
      "display_name": "Side Project",
      "slug": "sideproj",
      "origin": "local",
      "path": "",
      "tags": null
    }
  ]
}
```

---

## 9. `delete_project` — Eliminar proyecto

Elimina un proyecto del taskboard. Requiere `force=True` si el proyecto tiene tareas asociadas.

### Parámetros

| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `name` | `str` | Sí | — | Nombre del proyecto a eliminar |
| `force` | `bool` | No | `false` | Si `true`, elimina también todas las tareas e historial asociado |

### Ejemplo de respuesta

```json
{
  "status": "success",
  "data": {
    "deleted": "myproj",
    "tasks_removed": 3
  }
}
```

### Notas

- Si el proyecto tiene tareas asociadas y `force=False` (default): devuelve error indicando cuántas tareas tiene.
- Con `force=True`: elimina primero el historial (`task_history`), luego las tareas, y finalmente el proyecto.
- Si el proyecto no existe: `{"status": "error", "message": "Project 'name' not found"}`.
- La eliminación es permanente — no hay undo.

---

## 10. `get_metrics` — Métricas y analytics

Obtiene métricas de tareas con filtros opcionales por proyecto y/o rango de fechas.

### Parámetros

| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `project` | `str \| None` | No | `None` | Filtrar por nombre de proyecto |
| `start_date` | `str \| None` | No | `None` | Tareas creadas en o después de esta fecha (`YYYY-MM-DD`) |
| `end_date` | `str \| None` | No | `None` | Tareas creadas en o antes de esta fecha (`YYYY-MM-DD`) |

### Ejemplo de respuesta

```json
{
  "status": "success",
  "data": {
    "total_tasks": 42,
    "completed": 28,
    "pending": 5,
    "in_progress": 6,
    "blocked": 2,
    "cancelled": 1,
    "completion_rate": 66.7,
    "tasks_by_status": {
      "todo": 5,
      "in_progress": 6,
      "blocked": 2,
      "done": 28,
      "cancelled": 1
    },
    "tasks_by_type": {
      "feature": 12,
      "bugfix": 8,
      "chore": 10,
      "testing": 7,
      "docs": 3,
      "refactor": 2
    }
  }
}
```

### Notas

- `completion_rate` es un porcentaje redondeado a 1 decimal. Si no hay tareas, devuelve `0.0`.
- Los cuatro modos de filtro: (1) sin filtros = global, (2) solo fechas = rango, (3) solo proyecto = single project, (4) todos = combinado.
- `pending` mapea internamente al status `todo`.

---

## 11. `get_timeline` — Timeline de completadas

Obtiene tareas completadas agrupadas por semana, con opción de vista semanal o mensual.

### Parámetros

| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `project` | `str \| None` | No | `None` | Filtrar por nombre de proyecto |
| `view` | `str` | No | `"week"` | Granularidad: `"week"` (semana ISO actual), `"month"` (mes calendario actual) |

### Ejemplo de respuesta

```json
{
  "status": "success",
  "data": [
    {
      "week_label": "2026-W17",
      "tasks": [
        {
          "task_id": "myproj_003",
          "title": "Agregar tests de integración",
          "type": "testing",
          "project_name": "myproj",
          "completed_at": "2026-04-25 16:00:00",
          "slug": "myproj"
        }
      ]
    },
    {
      "week_label": "2026-W16",
      "tasks": [
        {
          "task_id": "myproj_002",
          "title": "Fix login redirect",
          "type": "bugfix",
          "project_name": "myproj",
          "completed_at": "2026-04-24 18:30:00",
          "slug": "myproj"
        }
      ]
    }
  ]
}
```

### Notas

- `view="week"`: muestra tareas completadas desde el lunes de la semana ISO anterior hasta ahora.
- `view="month"`: muestra tareas completadas desde el primer día del mes calendario actual hasta ahora.
- Siempre agrupa por semana ISO (`YYYY-WNN`), independientemente del `view`. La diferencia es el rango temporal de búsqueda.
- Las semanas se ordenan de más reciente a más antigua (`reverse=True`).
- Cada tarea incluye el `slug` del proyecto (via JOIN) para facilitar links en el dashboard.

---

## 12. `export_csv` — Exportar CSV

Exporta tareas como string CSV con filtros opcionales.

### Parámetros

| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `project` | `str \| None` | No | `None` | Filtrar por nombre de proyecto |
| `start_date` | `str \| None` | No | `None` | Tareas creadas en o después de esta fecha (`YYYY-MM-DD`) |
| `end_date` | `str \| None` | No | `None` | Tareas creadas en o antes de esta fecha (`YYYY-MM-DD`) |

### Ejemplo de respuesta

```json
{
  "status": "success",
  "data": "task_id,title,type,status,project,created_at,completed_at,tags\nmyproj_003,Agregar tests,testing,done,myproj,2026-04-25 10:00:00,2026-04-25 16:00:00,\"[]\"\nmyproj_002,Fix login,bugfix,done,myproj,2026-04-23 09:00:00,2026-04-24 18:30:00,\"[]\"\n"
}
```

### Notas

- El CSV se devuelve como string dentro del campo `data`. El agente puede guardarlo a archivo si necesita.
- Columnas: `task_id`, `title`, `type`, `status`, `project`, `created_at`, `completed_at`, `tags`.
- Los mismos filtros que `get_metrics`: sin filtros = todo, fechas = rango, proyecto = single, ambos = combinado.
- Para descargar el CSV desde el navegador, usá `GET /api/export/csv` (devuelve archivo con header `Content-Disposition`).
