"""HTMX action route handlers — form-encoded POST endpoints for web UI.

These routes accept ``application/x-www-form-urlencoded`` (HTMX default)
and return HTML fragments for DOM swap. They bridge the gap between
HTMX forms and the store layer, keeping /api/* routes unchanged for
programmatic JSON access.
"""

from __future__ import annotations

import html

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.templating import Jinja2Templates


def _get_store(request: Request):
    return request.app.state.store


def _get_templates(request: Request) -> Jinja2Templates:
    return request.app.state.templates


# ── Action: Add Task ──────────


async def add_task(request: Request) -> HTMLResponse | RedirectResponse:
    """POST /actions/tasks — create task from web form, redirect to project page.

    Accepts form-encoded data: title, project, type, priority.
    Redirects back to the project detail page on success.
    On error, renders an inline error message.
    """
    store = _get_store(request)
    form = await request.form()

    project = form.get("project", "")
    title = form.get("title", "")
    task_type = form.get("type", "chore")
    priority = form.get("priority", "medium")

    if not project or not title:
        return HTMLResponse(
            content='<span class="error-msg">Project and title are required.</span>',
            status_code=400,
        )

    try:
        store.add_task(
            project=str(project),
            title=str(title),
            type=str(task_type),
            priority=str(priority),
        )
    except ValueError as exc:
        return HTMLResponse(
            content=f'<span class="error-msg">{html.escape(str(exc))}</span>',
            status_code=400,
        )
    except Exception:
        return HTMLResponse(
            content='<span class="error-msg">Internal error creating task.</span>',
            status_code=500,
        )

    # Redirect to the project page so the user sees the updated task list
    # We need the project slug for the redirect — look it up
    proj = store.get_project_by_name(str(project))
    slug = proj["slug"] if proj else str(project)
    return RedirectResponse(url=f"/projects/{slug}", status_code=303)


# ── Action: Complete Task ──────


async def complete_task(request: Request) -> HTMLResponse:
    """POST /actions/tasks/{task_id}/complete — mark task as done.

    Returns the updated task_row partial for HTMX outerHTML swap.
    """
    store = _get_store(request)
    templates = _get_templates(request)

    task_id = request.path_params["task_id"]

    try:
        store.complete_task(task_id=task_id)
    except ValueError:
        return HTMLResponse(
            content=f'<tr><td colspan="7" class="error-msg">Task {html.escape(task_id)} not found</td></tr>',
            status_code=404,
        )
    except Exception:
        return HTMLResponse(
            content=f'<tr><td colspan="7" class="error-msg">Error completing task {html.escape(task_id)}</td></tr>',
            status_code=500,
        )

    task = store.get_task(task_id)
    if task is None:
        return HTMLResponse(
            content=f'<tr><td colspan="7" class="error-msg">Task not found after update</td></tr>',
            status_code=404,
        )

    return templates.TemplateResponse(
        request,
        "partials/task_row.html",
        {"task": task},
    )


# ── Action: Change Task Status ──


async def change_status(request: Request) -> HTMLResponse:
    """POST /actions/tasks/{task_id}/status — update task status.

    Accepts form-encoded data: status.
    Returns the updated task_row partial for HTMX outerHTML swap.
    """
    store = _get_store(request)
    templates = _get_templates(request)

    task_id = request.path_params["task_id"]
    form = await request.form()
    status = form.get("status", "")

    if not status:
        return HTMLResponse(
            content=f'<tr><td colspan="7" class="error-msg">Status field is required</td></tr>',
            status_code=400,
        )

    try:
        store.update_task_status(task_id=task_id, status=str(status))
    except ValueError:
        return HTMLResponse(
            content=f'<tr><td colspan="7" class="error-msg">Task {html.escape(task_id)} not found</td></tr>',
            status_code=404,
        )
    except Exception:
        return HTMLResponse(
            content=f'<tr><td colspan="7" class="error-msg">Error updating task {html.escape(task_id)}</td></tr>',
            status_code=500,
        )

    task = store.get_task(task_id)
    if task is None:
        return HTMLResponse(
            content=f'<tr><td colspan="7" class="error-msg">Task not found after update</td></tr>',
            status_code=404,
        )

    return templates.TemplateResponse(
        request,
        "partials/task_row.html",
        {"task": task},
    )


# ── Action: Generate Report ─────


async def generate_report(request: Request) -> HTMLResponse:
    """POST /actions/reports — generate filtered report fragment.

    Accepts form-encoded data: start_date, end_date, project.
    Returns the report_content partial for HTMX swap.
    """
    store = _get_store(request)
    templates = _get_templates(request)

    form = await request.form()
    start_date = str(form.get("start_date", ""))
    end_date = str(form.get("end_date", ""))
    project = str(form.get("project", ""))

    metrics = store.get_metrics(
        project=project or None,
        start_date=start_date or None,
        end_date=end_date or None,
    )

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
        "reports.html",  # We reuse the full template but HTMX will select the fragment
        {
            "metrics": metrics,
            "projects": store.list_projects(),
            "start_date": start_date,
            "end_date": end_date,
            "project": project,
            "csv_url": csv_url,
            "has_filters": bool(start_date or end_date or project),
        },
    )


# ── Action: Timeline Filter ──────


async def timeline_filter(request: Request) -> HTMLResponse:
    """POST /actions/timeline — filter timeline fragment.

    Accepts: view (week/month), project (slug).
    Returns the timeline-content partial.
    """
    store = _get_store(request)
    templates = _get_templates(request)

    form = await request.form()
    view = str(form.get("view", "week"))
    project_filter = str(form.get("project", ""))

    timeline_data = store.get_timeline(
        view=view,
        project=project_filter or None,
    )

    return templates.TemplateResponse(
        request,
        "timeline.html",
        {
            "timeline_data": timeline_data,
            "projects": store.list_projects(),
            "current_view": view,
            "project_filter": project_filter,
        },
    )


# ── Action: Dashboard Refresh ───


async def refresh_dashboard_section(request: Request) -> HTMLResponse:
    """POST /actions/dashboard/refresh — refresh a dashboard section.

    Accepts: section (projects/activity/metrics).
    Returns the corresponding partial.
    """
    store = _get_store(request)
    templates = _get_templates(request)

    form = await request.form()
    section = form.get("section", "")

    if section == "projects":
        return templates.TemplateResponse(
            request, "partials/project_cards.html", {"projects": store.list_projects()}
        )
    elif section == "activity":
        days = int(form.get("days", "7"))
        return templates.TemplateResponse(
            request, "partials/recent_activity.html", {"tasks": store.get_recent_activity(days=days)}
        )
    elif section == "metrics":
        return templates.TemplateResponse(
            request, "partials/metrics_cards.html", {"metrics": store.get_metrics()}
        )

    return HTMLResponse("Invalid section", status_code=400)
