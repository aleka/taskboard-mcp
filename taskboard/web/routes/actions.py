"""HTMX action route handlers — form-encoded POST endpoints for web UI.

These routes accept ``application/x-www-form-urlencoded`` (HTMX default)
and return HTML fragments for DOM swap. They bridge the gap between
HTMX forms and the store layer, keeping /api/* routes unchanged for
programmatic JSON access.
"""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.templating import Jinja2Templates


def _get_store(request: Request):
    return request.app.state.store


def _get_templates(request: Request) -> Jinja2Templates:
    return request.app.state.templates


# ── Action: Add Task ────────────────────────────────────────────────


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
            content=f'<span class="error-msg">{str(exc)}</span>',
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


# ── Action: Complete Task ───────────────────────────────────────────


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
            content=f'<tr><td colspan="7" class="error-msg">Task {task_id} not found</td></tr>',
            status_code=404,
        )
    except Exception:
        return HTMLResponse(
            content=f'<tr><td colspan="7" class="error-msg">Error completing task {task_id}</td></tr>',
            status_code=500,
        )

    task = store.get_task(task_id)
    if task is None:
        return HTMLResponse(
            content=f'<tr><td colspan="7" class="error-msg">Task {task_id} not found after update</td></tr>',
            status_code=404,
        )

    return templates.TemplateResponse(
        request,
        "partials/task_row.html",
        {"task": task},
    )


# ── Action: Change Task Status ──────────────────────────────────────


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
            content=f'<tr><td colspan="7" class="error-msg">Task {task_id} not found</td></tr>',
            status_code=404,
        )
    except Exception:
        return HTMLResponse(
            content=f'<tr><td colspan="7" class="error-msg">Error updating task {task_id}</td></tr>',
            status_code=500,
        )

    task = store.get_task(task_id)
    if task is None:
        return HTMLResponse(
            content=f'<tr><td colspan="7" class="error-msg">Task {task_id} not found after update</td></tr>',
            status_code=404,
        )

    return templates.TemplateResponse(
        request,
        "partials/task_row.html",
        {"task": task},
    )
