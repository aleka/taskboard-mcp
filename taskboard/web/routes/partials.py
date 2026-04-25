"""HTMX partial route handlers — HTML fragments for live updates.

All handlers return HTML fragments (no base.html, no nav/footer).
Access store and templates via ``request.app.state``.
"""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.templating import Jinja2Templates


def _get_store(request: Request):
    return request.app.state.store


def _get_templates(request: Request) -> Jinja2Templates:
    return request.app.state.templates


# ── TASK-20: Task List Partial ───────────────────────────────────────


async def task_list(request: Request) -> HTMLResponse:
    """GET /partials/task-list — filtered task list fragment."""
    store = _get_store(request)
    templates = _get_templates(request)

    tasks = store.list_tasks(
        project=request.query_params.get("project") or None,
        status=request.query_params.get("status") or None,
        limit=int(request.query_params.get("limit", "20")),
    )

    return templates.TemplateResponse(
        request,
        "partials/task_list.html",
        {"tasks": tasks},
    )


# ── TASK-20: Single Task Row Partial ─────────────────────────────────


async def task_row(request: Request) -> HTMLResponse:
    """GET /partials/task-row/{task_id} — single task row for status updates."""
    store = _get_store(request)
    templates = _get_templates(request)

    task_id = request.path_params["task_id"]
    task = store.get_task(task_id)

    if task is None:
        return HTMLResponse(
            content=f'<tr><td colspan="7" class="empty-state">Task {task_id} not found</td></tr>',
            status_code=404,
        )

    return templates.TemplateResponse(
        request,
        "partials/task_row.html",
        {"task": task},
    )


# ── TASK-20: Metrics Cards Partial ───────────────────────────────────


async def metrics_cards(request: Request) -> HTMLResponse:
    """GET /partials/metrics — metric cards fragment."""
    store = _get_store(request)
    templates = _get_templates(request)

    metrics = store.get_metrics(
        project=request.query_params.get("project") or None,
        start_date=request.query_params.get("start_date") or None,
        end_date=request.query_params.get("end_date") or None,
    )

    return templates.TemplateResponse(
        request,
        "partials/metrics_cards.html",
        {"metrics": metrics},
    )


# ── TASK-20: Timeline Group Partial ──────────────────────────────────


async def timeline_group(request: Request) -> HTMLResponse:
    """GET /partials/timeline-group — timeline items fragment."""
    store = _get_store(request)
    templates = _get_templates(request)

    view = request.query_params.get("view", "week")
    project_filter = request.query_params.get("project", "")

    if view == "month":
        timeline_data = store.get_timeline_month(project=project_filter or None)
    else:
        timeline_data = store.get_timeline_week(project=project_filter or None)

    return templates.TemplateResponse(
        request,
        "partials/timeline_group.html",
        {"timeline_data": timeline_data},
    )
