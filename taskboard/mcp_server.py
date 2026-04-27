"""MCP Server — 10 fastmcp tools for taskboard operations.

Exposes the TaskboardStore API as MCP tools for AI agents.
Run with: ``fastmcp run taskboard.mcp_server:mcp``
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from taskboard.store import TaskboardStore

mcp = FastMCP("taskboard")

# ── Lazy store singleton ──────────────────────────────────────────

_store: TaskboardStore | None = None


def _get_store() -> TaskboardStore:
    """Return the shared store instance, initializing lazily.

    No ``__enter__`` needed — the store uses connection-per-operation.
    """
    global _store
    if _store is None:
        _store = TaskboardStore()
    return _store


# ── Task tools ────────────────────────────────────────────────────


@mcp.tool()
def add_task(
    project: str,
    title: str,
    type: str = "chore",
    description: str = "",
    tags: list[str] | None = None,
    priority: str = "medium",
) -> dict[str, Any]:
    """Create a new task in the taskboard.

    Args:
        project: Project name (must already exist).
        title: Task title.
        type: Task type — one of feature, bugfix, refactor, config, chore, docs, testing, infra.
        description: Optional description/notes.
        tags: Optional list of tags for grouping (e.g. ["refactor-ui", "compliance-fix"]).
        priority: Task priority — one of low, medium, high, urgent.

    Returns:
        The created task dict with task_id, status, timestamps, etc.
    """
    try:
        store = _get_store()
        task = store.add_task(
            project=project,
            title=title,
            type=type,
            description=description,
            tags=tags,
            priority=priority,
        )
        return {"status": "success", "data": task}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def complete_task(task_id: str, summary: str = "") -> dict[str, Any]:
    """Mark a task as completed (status set to 'done').

    Args:
        task_id: The task ID (e.g. 'tp_001').
        summary: Optional completion summary.

    Returns:
        The updated task dict with completed_at timestamp.
    """
    try:
        store = _get_store()
        task = store.complete_task(task_id=task_id, summary=summary)
        return {"status": "success", "data": task}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def delete_task(task_id: str) -> dict[str, Any]:
    """Delete a task from the taskboard.

    Args:
        task_id: The task ID (e.g. 'tp_001').

    Returns:
        Dict confirming deletion or error if task not found.
    """
    try:
        store = _get_store()
        deleted = store.delete_task(task_id=task_id)
        if not deleted:
            return {"status": "error", "message": f"Task '{task_id}' not found"}
        return {"status": "success", "data": {"deleted": task_id}}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def update_task_status(
    task_id: str, status: str, note: str = ""
) -> dict[str, Any]:
    """Update a task's status.

    Args:
        task_id: The task ID (e.g. 'tp_001').
        status: New status — one of todo, in_progress, blocked, done, cancelled.
        note: Optional note explaining the change.

    Returns:
        The updated task dict.
    """
    try:
        store = _get_store()
        task = store.update_task_status(task_id=task_id, status=status, note=note)
        return {"status": "success", "data": task}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def list_tasks(
    project: str | None = None,
    status: str | None = None,
    type: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """List tasks with optional filters.

    Args:
        project: Filter by project name.
        status: Filter by status (todo, in_progress, blocked, done, cancelled).
        type: Filter by task type.
        from_date: Filter tasks created on or after this date (YYYY-MM-DD).
        to_date: Filter tasks created on or before this date (YYYY-MM-DD).
        limit: Max number of tasks to return (default 100).
        offset: Number of tasks to skip (for pagination).

    Returns:
        List of task dicts matching the filters.
    """
    try:
        store = _get_store()
        tasks = store.list_tasks(
            project=project,
            status=status,
            type=type,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            offset=offset,
        )
        return {"status": "success", "data": tasks}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def get_task(task_id: str) -> dict[str, Any]:
    """Get details of a specific task by its ID.

    Args:
        task_id: The task ID (e.g. 'tp_001').

    Returns:
        The task dict, or an error if not found.
    """
    try:
        store = _get_store()
        task = store.get_task(task_id=task_id)
        if task is None:
            return {"status": "error", "message": f"Task '{task_id}' not found"}
        return {"status": "success", "data": task}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── Project tools ─────────────────────────────────────────────────


@mcp.tool()
def add_project(
    name: str,
    display_name: str,
    slug: str,
    origin: str = "local",
    path: str = "",
) -> dict[str, Any]:
    """Register a new project in the taskboard.

    Args:
        name: Internal project name (unique, used as FK reference).
        display_name: Human-readable project name.
        slug: URL-friendly short identifier (unique).
        origin: Project origin — one of github, gitlab, local.
        path: Filesystem path to the project.

    Returns:
        The created project dict.
    """
    try:
        store = _get_store()
        project = store.add_project(
            name=name,
            display_name=display_name,
            slug=slug,
            origin=origin,
            path=path,
        )
        return {"status": "success", "data": project}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def list_projects() -> dict[str, Any]:
    """List all registered projects.

    Returns:
        List of project dicts sorted by name.
    """
    try:
        store = _get_store()
        projects = store.list_projects()
        return {"status": "success", "data": projects}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def delete_project(name: str, force: bool = False) -> dict[str, Any]:
    """Delete a project from the taskboard.

    Args:
        name: Project name to delete.
        force: If True, also delete all associated tasks and their history.
               If False (default), refuses to delete projects with tasks.

    Returns:
        Dict with deleted project name and count of tasks removed.
    """
    try:
        store = _get_store()
        result = store.delete_project(name=name, force=force)
        return {"status": "success", "data": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── Analytics tools ───────────────────────────────────────────────


@mcp.tool()
def get_metrics(
    project: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Get task metrics and analytics with optional filters.

    Args:
        project: Filter by project name.
        start_date: Filter tasks created on or after this date (YYYY-MM-DD).
        end_date: Filter tasks created on or before this date (YYYY-MM-DD).

    Returns:
        Metrics dict with total_tasks, completed, pending, completion_rate,
        tasks_by_status, and tasks_by_type breakdowns.
    """
    try:
        store = _get_store()
        metrics = store.get_metrics(
            project=project,
            start_date=start_date,
            end_date=end_date,
        )
        return {"status": "success", "data": metrics}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def get_timeline(
    project: str | None = None, view: str = "week"
) -> dict[str, Any]:
    """Get timeline view of completed tasks.

    Args:
        project: Filter by project name.
        view: Timeline granularity — 'week' for current ISO week,
              'month' for current calendar month.

    Returns:
        List of week groups, each containing tasks completed in that week.
    """
    try:
        store = _get_store()
        if view == "month":
            timeline = store.get_timeline_month(project=project)
        else:
            timeline = store.get_timeline_week(project=project)
        return {"status": "success", "data": timeline}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def export_csv(
    project: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Export tasks as CSV string with optional filters.

    Args:
        project: Filter by project name.
        start_date: Filter tasks created on or after this date (YYYY-MM-DD).
        end_date: Filter tasks created on or before this date (YYYY-MM-DD).

    Returns:
        CSV string with headers: task_id, title, type, status, project,
        created_at, completed_at, tags.
    """
    try:
        store = _get_store()
        csv_data = store.export_csv(
            project=project,
            start_date=start_date,
            end_date=end_date,
        )
        return {"status": "success", "data": csv_data}
    except Exception as e:
        return {"status": "error", "message": str(e)}
