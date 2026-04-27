"""REST API route handlers — JSON endpoints for tasks, projects, metrics, CSV.

All handlers access the store via ``request.app.state.store``.
Returns JSON (except CSV export) with proper error handling.
"""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse


def _get_store(request: Request):
    return request.app.state.store


def _json(data, status: int = 200) -> JSONResponse:
    return JSONResponse(data, status_code=status)


def _error(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


# ── TASK-19: Tasks CRUD ──────────────────────────────────────────────


async def tasks_list(request: Request) -> JSONResponse:
    """GET /api/tasks — list tasks with optional filters."""
    store = _get_store(request)
    try:
        tasks = store.list_tasks(
            project=request.query_params.get("project") or None,
            status=request.query_params.get("status") or None,
            type=request.query_params.get("type") or None,
            from_date=request.query_params.get("from_date") or None,
            to_date=request.query_params.get("to_date") or None,
            limit=int(request.query_params.get("limit", "100")),
            offset=int(request.query_params.get("offset", "0")),
        )
        return _json({"tasks": tasks, "count": len(tasks)})
    except ValueError as exc:
        return _error(str(exc), 400)
    except Exception as exc:
        return _error("Internal server error", 500)


async def tasks_create(request: Request) -> JSONResponse:
    """POST /api/tasks — create a new task, return 201."""
    store = _get_store(request)
    try:
        body = await request.json()
        project = body.get("project")
        title = body.get("title")
        if not project or not title:
            return _error("Fields 'project' and 'title' are required", 400)

        task = store.add_task(
            project=project,
            title=title,
            type=body.get("type", "chore"),
            description=body.get("description", ""),
            tags=body.get("tags"),
            priority=body.get("priority", "medium"),
        )
        return _json({"task": task}, status=201)
    except ValueError as exc:
        return _error(str(exc), 400)
    except Exception as exc:
        return _error("Internal server error", 500)


async def task_detail(request: Request) -> JSONResponse:
    """GET /api/tasks/{task_id} — return a single task or 404."""
    store = _get_store(request)
    task_id = request.path_params["task_id"]
    task = store.get_task(task_id)
    if task is None:
        return _error(f"Task '{task_id}' not found", 404)
    return _json({"task": task})


async def task_update(request: Request) -> JSONResponse:
    """PATCH /api/tasks/{task_id} — update task fields.

    Accepts JSON body with any updatable fields: title, description, type,
    priority, status, git_commit, parent_task_id. At least one field is
    recommended but not required (empty body returns unchanged task).
    Status changes are recorded in task history.
    """
    store = _get_store(request)
    task_id = request.path_params["task_id"]
    try:
        body = await request.json()

        update_kwargs: dict[str, str | None] = {}
        if body.get("title"):
            update_kwargs["title"] = str(body["title"])
        if body.get("description") is not None:
            update_kwargs["description"] = str(body["description"])
        if body.get("type"):
            update_kwargs["type"] = str(body["type"])
        if body.get("priority"):
            update_kwargs["priority"] = str(body["priority"])
        if body.get("status"):
            update_kwargs["status"] = str(body["status"])
        if body.get("git_commit") is not None:
            update_kwargs["git_commit"] = str(body["git_commit"])
        if "parent_task_id" in body:
            update_kwargs["parent_task_id"] = body["parent_task_id"]

        task = store.update_task(task_id=task_id, **update_kwargs)
        return _json({"task": task})
    except ValueError as exc:
        return _error(str(exc), 404)
    except Exception as exc:
        return _error("Internal server error", 500)


async def task_delete(request: Request) -> JSONResponse:
    """DELETE /api/tasks/{task_id} — delete a task."""
    store = _get_store(request)
    task_id = request.path_params["task_id"]
    deleted = store.delete_task(task_id)
    if not deleted:
        return _error(f"Task '{task_id}' not found", 404)
    return _json({"deleted": True})


# ── TASK-19: Projects ────────────────────────────────────────────────


async def projects_list(request: Request) -> JSONResponse:
    """GET /api/projects — list all projects."""
    store = _get_store(request)
    projects = store.list_projects()
    return _json({"projects": projects, "count": len(projects)})


async def projects_create(request: Request) -> JSONResponse:
    """POST /api/projects — create a new project, return 201."""
    store = _get_store(request)
    try:
        body = await request.json()
        name = body.get("name")
        if not name:
            return _error("Field 'name' is required", 400)

        project = store.add_project(
            name=name,
            display_name=body.get("display_name", name),
            slug=body.get("slug", name.lower().replace(" ", "-")),
            origin=body.get("origin", "local"),
            repo=body.get("repo"),
            path=body.get("path", ""),
            tags=body.get("tags"),
        )
        return _json({"project": project}, status=201)
    except ValueError as exc:
        return _error(str(exc), 400)
    except Exception as exc:
        return _error("Internal server error", 500)


async def project_detail(request: Request) -> JSONResponse:
    """GET /api/projects/{slug} — return a project or 404."""
    store = _get_store(request)
    slug = request.path_params["slug"]
    project = store.get_project(slug)
    if project is None:
        return _error(f"Project '{slug}' not found", 404)
    return _json({"project": project})


# ── TASK-19: Metrics ─────────────────────────────────────────────────


async def metrics(request: Request) -> JSONResponse:
    """GET /api/metrics — return metrics with optional filters."""
    store = _get_store(request)
    try:
        data = store.get_metrics(
            project=request.query_params.get("project") or None,
            start_date=request.query_params.get("start_date") or None,
            end_date=request.query_params.get("end_date") or None,
        )
        return _json(data)
    except Exception as exc:
        return _error("Internal server error", 500)


# ── TASK-19: CSV Export ──────────────────────────────────────────────


async def csv_export(request: Request) -> PlainTextResponse:
    """GET /api/export/csv — return CSV file with proper headers."""
    store = _get_store(request)
    try:
        csv_content = store.export_csv(
            project=request.query_params.get("project") or None,
            start_date=request.query_params.get("start_date") or None,
            end_date=request.query_params.get("end_date") or None,
        )
        return PlainTextResponse(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=tasks.csv",
            },
        )
    except Exception as exc:
        return PlainTextResponse(
            content="Error generating CSV",
            status_code=500,
            media_type="text/plain",
        )
