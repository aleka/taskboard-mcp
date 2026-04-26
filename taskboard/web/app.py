"""Starlette application factory — assembles web dashboard, REST API, and MCP.

Usage::

    uvicorn taskboard.web.app:create_app --factory
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from taskboard.mcp_server import mcp
from taskboard.store import TaskboardStore

# Absolute paths based on this file's location (works regardless of cwd)
_WEB_DIR = os.path.dirname(__file__)
_TEMPLATES_DIR = os.path.join(_WEB_DIR, "templates")
_STATIC_DIR = os.path.join(_WEB_DIR, "static")

# Cache-Control max-age for static assets (24 hours)
_STATIC_CACHE_MAX_AGE = 86400


@asynccontextmanager
async def lifespan(app: Starlette) -> AsyncGenerator[None, None]:
    """Open the store on startup, close on shutdown."""
    store: TaskboardStore = app.state.store
    store._connect()
    yield
    store.__exit__(None, None, None)


class StaticCacheMiddleware(BaseHTTPMiddleware):
    """Add Cache-Control headers to static asset responses.

    Starlette's StaticFiles does not set cache headers by default.
    This middleware adds ``Cache-Control: public, max-age=86400`` to
    responses whose path starts with ``/static/``.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = (
                f"public, max-age={_STATIC_CACHE_MAX_AGE}"
            )
        return response


def create_app(store: TaskboardStore | None = None) -> Starlette:
    """Build and return the fully-assembled Starlette application.

    Args:
        store: Optional pre-configured store. If None, creates a default
               TaskboardStore pointing to ~/.taskboard/taskboard.db.

    Returns:
        A Starlette application with pages, API, partials, actions, MCP,
        and static file serving configured.
    """
    if store is None:
        store = TaskboardStore()

    templates = Jinja2Templates(directory=_TEMPLATES_DIR)

    # Import route handlers
    from .routes import actions  # noqa: E402
    from .routes import api  # noqa: E402
    from .routes import pages  # noqa: E402
    from .routes import partials  # noqa: E402

    routes: list[Mount | Route] = [
        # ── HTML pages ──
        Route("/", pages.dashboard, name="dashboard"),
        Route("/projects", pages.project_list, name="projects"),
        Route("/projects/{slug:path}", pages.project_detail, name="project-detail"),
        Route("/timeline", pages.timeline_view, name="timeline"),
        Route("/reports", pages.reports_view, name="reports"),

        # ── HTMX partials (read-only fragments) ──
        Route("/partials/task-list", partials.task_list, name="partial-task-list"),
        Route("/partials/task-row/{task_id}", partials.task_row, name="partial-task-row"),
        Route("/partials/metrics", partials.metrics_cards, name="partial-metrics"),
        Route("/partials/timeline-group", partials.timeline_group, name="partial-timeline"),

        # ── HTMX actions (form-encoded POST, returns HTML) ──
        Route("/actions/tasks", actions.add_task, methods=["POST"], name="action-add-task"),
        Route(
            "/actions/tasks/{task_id}/complete",
            actions.complete_task,
            methods=["POST"],
            name="action-complete-task",
        ),
        Route(
            "/actions/tasks/{task_id}/status",
            actions.change_status,
            methods=["POST"],
            name="action-change-status",
        ),

        # ── REST API (JSON) ──
        Route("/api/tasks", api.tasks_list, methods=["GET"], name="api-tasks-list"),
        Route("/api/tasks", api.tasks_create, methods=["POST"], name="api-tasks-create"),
        Route("/api/tasks/{task_id}", api.task_detail, methods=["GET"], name="api-task-detail"),
        Route("/api/tasks/{task_id}", api.task_update, methods=["PATCH"], name="api-task-update"),
        Route("/api/tasks/{task_id}", api.task_delete, methods=["DELETE"], name="api-task-delete"),
        Route("/api/projects", api.projects_list, methods=["GET"], name="api-projects-list"),
        Route("/api/projects", api.projects_create, methods=["POST"], name="api-projects-create"),
        Route("/api/projects/{slug}", api.project_detail, methods=["GET"], name="api-project-detail"),
        Route("/api/metrics", api.metrics, methods=["GET"], name="api-metrics"),
        Route("/api/export/csv", api.csv_export, methods=["GET"], name="api-csv-export"),

        # ── MCP sub-app ──
        Mount("/mcp", app=mcp.http_app()),

        # ── Static files ──
        Mount("/static", app=StaticFiles(directory=_STATIC_DIR), name="static"),
    ]

    app = Starlette(routes=routes, lifespan=lifespan)
    app.add_middleware(StaticCacheMiddleware)

    # Inject shared dependencies into app.state for route handlers
    app.state.store = store
    app.state.templates = templates

    return app
