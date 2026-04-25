"""HTML page route handlers — serve full pages rendered via Jinja2.

All handlers access the store and templates via ``request.app.state``.
"""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.templating import Jinja2Templates


def _get_store(request: Request):
    return request.app.state.store


def _get_templates(request: Request) -> Jinja2Templates:
    return request.app.state.templates


# ── TASK-11: Dashboard ──────────────────────────────────────────────


async def dashboard(request: Request) -> HTMLResponse:
    """GET / — overview with global metrics, project list, recent activity."""
    store = _get_store(request)
    templates = _get_templates(request)

    metrics = store.get_metrics()
    projects = store.list_projects()
    recent_tasks = store.get_recent_activity(days=7)[:10]

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "metrics": metrics,
            "projects": projects,
            "recent_tasks": recent_tasks,
        },
    )


# ── TASK-13: Project List & Detail ──────────────────────────────────


async def project_list(request: Request) -> HTMLResponse:
    """GET /projects — list all projects with task counts."""
    store = _get_store(request)
    templates = _get_templates(request)

    projects = store.list_projects()
    # Enrich each project with metrics
    for p in projects:
        p["metrics"] = store.get_metrics(project=p["name"])

    return templates.TemplateResponse(
        request,
        "project_list.html",
        {"projects": projects},
    )


async def project_detail(request: Request) -> HTMLResponse:
    """GET /projects/{slug} — project detail with task table and filters."""
    store = _get_store(request)
    templates = _get_templates(request)

    slug = request.path_params["slug"]
    project = store.get_project(slug)

    if project is None:
        return templates.TemplateResponse(
            request,
            "project_detail.html",
            {"project": None, "tasks": [], "slug": slug, "status_filter": ""},
            status_code=404,
        )

    status_filter = request.query_params.get("status", "")
    tasks = store.list_tasks(
        project=project["name"],
        status=status_filter or None,
        limit=500,
    )

    return templates.TemplateResponse(
        request,
        "project_detail.html",
        {
            "project": project,
            "tasks": tasks,
            "slug": slug,
            "status_filter": status_filter,
        },
    )


# ── TASK-15: Timeline ───────────────────────────────────────────────


async def timeline_view(request: Request) -> HTMLResponse:
    """GET /timeline — tasks grouped by week, with view toggle (week/month)."""
    store = _get_store(request)
    templates = _get_templates(request)

    view = request.query_params.get("view", "week")
    project_filter = request.query_params.get("project", "")

    if view == "month":
        timeline_data = store.get_timeline_month(project=project_filter or None)
    else:
        timeline_data = store.get_timeline_week(project=project_filter or None)

    projects = store.list_projects()

    return templates.TemplateResponse(
        request,
        "timeline.html",
        {
            "timeline_data": timeline_data,
            "current_view": view,
            "project_filter": project_filter,
            "projects": projects,
        },
    )


# ── TASK-17: Reports ────────────────────────────────────────────────


async def reports_view(request: Request) -> HTMLResponse:
    """GET /reports — filtered metrics preview with CSV download link."""
    store = _get_store(request)
    templates = _get_templates(request)

    start_date = request.query_params.get("start_date", "")
    end_date = request.query_params.get("end_date", "")
    project = request.query_params.get("project", "")

    metrics = store.get_metrics(
        project=project or None,
        start_date=start_date or None,
        end_date=end_date or None,
    )
    projects = store.list_projects()

    # Build CSV download URL with the same filters
    csv_params: list[str] = []
    if start_date:
        csv_params.append(f"start_date={start_date}")
    if end_date:
        csv_params.append(f"end_date={end_date}")
    if project:
        csv_params.append(f"project={project}")
    csv_url = f"/api/export/csv?{'&'.join(csv_params)}" if csv_params else "/api/export/csv"

    return templates.TemplateResponse(
        request,
        "reports.html",
        {
            "metrics": metrics,
            "projects": projects,
            "start_date": start_date,
            "end_date": end_date,
            "project": project,
            "csv_url": csv_url,
            "has_filters": bool(start_date or end_date or project),
        },
    )
