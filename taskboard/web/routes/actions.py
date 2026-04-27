"""HTMX action route handlers — form-encoded POST endpoints for web UI.

These routes accept ``application/x-www-form-urlencoded`` (HTMX default)
and return HTML fragments for DOM swap. They bridge the gap between
HTMX forms and the store layer, keeping /api/* routes unchanged for
programmatic JSON access.
"""

from __future__ import annotations

import html
import json

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


# ── Action: Edit Task (V2-15) ────────────────────────────────────────


async def edit_task(request: Request) -> HTMLResponse | RedirectResponse:
    """POST /actions/tasks/{task_id}/edit — update task fields from edit form.

    Accepts form-encoded data: title, description, type, priority, status,
    git_commit, tags, parent_task_id.
    Redirects to task detail page on success.
    """
    store = _get_store(request)
    task_id = request.path_params["task_id"]
    form = await request.form()

    try:
        update_kwargs: dict[str, str | None] = {}
        if form.get("title"):
            update_kwargs["title"] = str(form["title"])
        if form.get("description") is not None:
            update_kwargs["description"] = str(form["description"])
        if form.get("type"):
            update_kwargs["type"] = str(form["type"])
        if form.get("priority"):
            update_kwargs["priority"] = str(form["priority"])
        if form.get("status"):
            update_kwargs["status"] = str(form["status"])
        if form.get("git_commit"):
            update_kwargs["git_commit"] = str(form["git_commit"])

        # Parent: empty string means clear
        parent_raw = str(form.get("parent_task_id", ""))
        update_kwargs["parent_task_id"] = parent_raw if parent_raw else None

        store.update_task(task_id=task_id, **update_kwargs)

        # Tags: comma-separated string → atomic add_tag/remove_tag operations
        # Do this AFTER update_task since it doesn't accept tags param
        tags_raw = str(form.get("tags", ""))
        if tags_raw.strip():
            new_tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
            # Get current tags
            task = store.get_task(task_id)
            if task:
                current_tags: list[str] = json.loads(task["tags"])
                # Remove old tags not in new list
                for old_tag in current_tags:
                    if old_tag not in new_tags:
                        store.remove_tag(task_id, old_tag)
                # Add new tags not already present
                for new_tag in new_tags:
                    if new_tag not in current_tags:
                        store.add_tag(task_id, new_tag)
        else:
            # Empty tags field → clear all tags
            task = store.get_task(task_id)
            if task:
                current_tags = json.loads(task["tags"])
                for old_tag in current_tags:
                    store.remove_tag(task_id, old_tag)
    except ValueError as exc:
        return HTMLResponse(
            content=f'<span class="error-msg">{html.escape(str(exc))}</span>',
            status_code=404,
        )
    except Exception:
        return HTMLResponse(
            content='<span class="error-msg">Internal error updating task.</span>',
            status_code=500,
        )

    return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)


# ── Action: Delete Task (V2-16) ──────────────────────────────────────


async def delete_task(request: Request) -> HTMLResponse | RedirectResponse:
    """POST /actions/tasks/{task_id}/delete — delete task with confirmation.

    Requires hx-confirm on the triggering element. Redirects to the
    project page on success.
    """
    store = _get_store(request)
    task_id = request.path_params["task_id"]

    try:
        task = store.get_task(task_id)
        if task is None:
            return HTMLResponse(
                content=f'<span class="error-msg">Task {html.escape(task_id)} not found</span>',
                status_code=404,
            )
        project_name = task["project_name"]
        store.delete_task(task_id=task_id)
    except Exception as exc:
        return HTMLResponse(
            content=f'<span class="error-msg">Error deleting task: {html.escape(str(exc))}</span>',
            status_code=500,
        )

    # Redirect to project page
    proj = store.get_project_by_name(project_name)
    slug = proj["slug"] if proj else project_name
    return RedirectResponse(url=f"/projects/{slug}", status_code=303)
