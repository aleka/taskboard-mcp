"""TaskboardStore — SQLite persistence layer for the taskboard.

Single persistent connection with WAL mode, context manager lifecycle,
and full CRUD + analytics + CSV export over the existing schema.
"""

from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any


class TaskboardStore:
    """Manages a single SQLite connection to ~/.taskboard/taskboard.db.

    Usage::

        with TaskboardStore() as store:
            store.add_project(...)
            store.add_task(...)
    """

    def __init__(self, db_path: str = "~/.taskboard/taskboard.db") -> None:
        self._db_path = os.path.expanduser(db_path)
        self._conn: sqlite3.Connection | None = None

    # ── Connection lifecycle ──────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        """Open (or reuse) a connection with WAL, busy_timeout, FK."""
        if self._conn is not None:
            return self._conn
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        self._conn = conn
        return conn

    @property
    def conn(self) -> sqlite3.Connection:
        return self._connect()

    def __enter__(self) -> TaskboardStore:
        self._connect()
        return self

    def __exit__(self, *exc: object) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ── Helpers ──────────────────────────────────────────────────────

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return dict(row)

    def _generate_task_id(self, project_name: str) -> str:
        """Return ``{slug}_{NNN}`` for the given project."""
        slug = self.conn.execute(
            "SELECT slug FROM projects WHERE name = ?", (project_name,)
        ).fetchone()
        if slug is None:
            raise ValueError(f"Project '{project_name}' not found")
        slug_str = slug[0]
        count = self.conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE project_name = ?", (project_name,)
        ).fetchone()[0]
        return f"{slug_str}_{count + 1:03d}"

    def _record_history(
        self,
        task_id: str,
        to_status: str,
        from_status: str | None = None,
        note: str = "",
        git_commit: str | None = None,
    ) -> None:
        """INSERT into task_history (append-only, never UPDATE)."""
        self.conn.execute(
            "INSERT INTO task_history (task_id, from_status, to_status, note, git_commit) "
            "VALUES (?, ?, ?, ?, ?)",
            (task_id, from_status, to_status, note, git_commit),
        )
        self.conn.commit()

    # ── Project CRUD ─────────────────────────────────────────────────

    def add_project(
        self,
        name: str,
        display_name: str,
        slug: str,
        origin: str = "local",
        repo: str | None = None,
        path: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        tags_json = json.dumps(tags or [])
        try:
            self.conn.execute(
                "INSERT INTO projects (name, display_name, slug, origin, repo, path, tags) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, display_name, slug, origin, repo, path, tags_json),
            )
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                f"Project with name '{name}' or slug '{slug}' already exists"
            ) from exc
        return self.get_project(slug)  # type: ignore[return-value]

    def get_project(self, slug: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM projects WHERE slug = ?", (slug,)
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def get_project_by_name(self, name: str) -> dict[str, Any] | None:
        """Look up a project by its ``name`` (not slug)."""
        row = self.conn.execute(
            "SELECT * FROM projects WHERE name = ?", (name,)
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_projects(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM projects ORDER BY name"
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ── Task CRUD ────────────────────────────────────────────────────

    def add_task(
        self,
        project: str,
        title: str,
        type: str = "chore",
        description: str = "",
        tags: list[str] | None = None,
        priority: str = "medium",
        source: str = "manual",
    ) -> dict[str, Any]:
        task_id = self._generate_task_id(project)
        tags_json = json.dumps(tags or [])
        self.conn.execute(
            "INSERT INTO tasks "
            "(task_id, title, type, project_name, status, source, priority, summary, tags, notes) "
            "VALUES (?, ?, ?, ?, 'todo', ?, ?, '', ?, ?)",
            (task_id, title, type, project, source, priority, tags_json, description),
        )
        self.conn.commit()
        # Record creation in history (from_status=NULL per existing convention)
        self._record_history(task_id, to_status="todo", note="Creada")
        return self.get_task(task_id)  # type: ignore[return-value]

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_tasks(
        self,
        project: str | None = None,
        status: str | None = None,
        type: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []

        if project:
            clauses.append("project_name = ?")
            params.append(project)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if type:
            clauses.append("type = ?")
            params.append(type)
        if from_date:
            clauses.append("created_at >= ?")
            params.append(from_date)
        if to_date:
            clauses.append("created_at <= ?")
            params.append(to_date)

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.extend([limit, offset])

        rows = self.conn.execute(
            f"SELECT * FROM tasks{where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def update_task_status(
        self, task_id: str, status: str, note: str = ""
    ) -> dict[str, Any]:
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task '{task_id}' not found")
        old_status = task["status"]
        self.conn.execute(
            "UPDATE tasks SET status = ? WHERE task_id = ?", (status, task_id)
        )
        self.conn.commit()
        self._record_history(task_id, from_status=old_status, to_status=status, note=note)
        return self.get_task(task_id)  # type: ignore[return-value]

    def complete_task(
        self,
        task_id: str,
        summary: str = "",
        git_commit: str | None = None,
    ) -> dict[str, Any]:
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task '{task_id}' not found")
        old_status = task["status"]
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute(
            "UPDATE tasks SET status = 'done', completed_at = ?, summary = ?, git_commit = COALESCE(?, git_commit) "
            "WHERE task_id = ?",
            (now, summary or task["summary"], git_commit, task_id),
        )
        self.conn.commit()
        self._record_history(
            task_id,
            from_status=old_status,
            to_status="done",
            note=summary or "Completada",
            git_commit=git_commit,
        )
        return self.get_task(task_id)  # type: ignore[return-value]

    def delete_task(self, task_id: str) -> bool:
        task = self.get_task(task_id)
        if task is None:
            return False
        self.conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
        self.conn.commit()
        return True

    # ── Analytics ────────────────────────────────────────────────────

    def get_metrics(
        self,
        project: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Return task counts by status, completion rate, breakdowns.

        Filter modes:
        - All None → global stats
        - start_date/end_date only → date range
        - project only → single project
        - All three → combined
        """
        clauses: list[str] = []
        params: list[Any] = []

        if project:
            clauses.append("project_name = ?")
            params.append(project)
        if start_date:
            clauses.append("created_at >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("created_at <= ?")
            params.append(end_date)

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        where_and = f"{where} AND " if where else " WHERE "

        total = self.conn.execute(
            f"SELECT COUNT(*) FROM tasks{where}", params
        ).fetchone()[0]

        completed = self.conn.execute(
            f"SELECT COUNT(*) FROM tasks{where_and}status = 'done'", params
        ).fetchone()[0]

        # Tasks by status
        by_status_rows = self.conn.execute(
            f"SELECT status, COUNT(*) as cnt FROM tasks{where_and}1=1 GROUP BY status",
            params,
        ).fetchall()
        tasks_by_status = {r[0]: r[1] for r in by_status_rows}

        # Tasks by type
        by_type_rows = self.conn.execute(
            f"SELECT type, COUNT(*) as cnt FROM tasks{where_and}1=1 GROUP BY type",
            params,
        ).fetchall()
        tasks_by_type = {r[0]: r[1] for r in by_type_rows}

        completion_rate = round(completed / total * 100, 1) if total > 0 else 0.0

        return {
            "total_tasks": total,
            "completed": completed,
            "pending": tasks_by_status.get("todo", 0),
            "in_progress": tasks_by_status.get("in_progress", 0),
            "blocked": tasks_by_status.get("blocked", 0),
            "cancelled": tasks_by_status.get("cancelled", 0),
            "completion_rate": completion_rate,
            "tasks_by_status": tasks_by_status,
            "tasks_by_type": tasks_by_type,
        }

    def get_timeline_week(
        self, project: str | None = None
    ) -> list[dict[str, Any]]:
        """Tasks completed in the current ISO week, grouped by week label."""
        return self._get_timeline(
            project=project,
            since_expr="date('now', 'weekday 1', '-7 days')",
            group_by="week",
        )

    def get_timeline_month(
        self, project: str | None = None
    ) -> list[dict[str, Any]]:
        """Tasks completed in the current calendar month, grouped by week."""
        return self._get_timeline(
            project=project,
            since_expr="date('now', 'start of month')",
            group_by="week",
        )

    def _get_timeline(
        self,
        project: str | None,
        since_expr: str,
        group_by: str,
    ) -> list[dict[str, Any]]:
        clauses = ["status = 'done'", "completed_at IS NOT NULL"]
        params: list[Any] = []

        if project:
            clauses.append("project_name = ?")
            params.append(project)

        where = " WHERE " + " AND ".join(clauses)
        # since_expr is a trusted SQL expression (e.g. "date('now', 'weekday 1', '-7 days')")
        where += f" AND completed_at >= {since_expr}"

        rows = self.conn.execute(
            f"SELECT t.task_id, t.title, t.type, t.project_name, t.completed_at, p.slug "
            f"FROM tasks t JOIN projects p ON t.project_name = p.name"
            f"{where} ORDER BY t.completed_at DESC",
            params,
        ).fetchall()

        # Group by week
        groups: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            d = self._row_to_dict(r)
            # Compute ISO week label
            try:
                completed = datetime.strptime(d["completed_at"], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                # Skip entries with invalid datetime (e.g. literal "datetime('now')")
                continue
            iso_cal = completed.isocalendar()
            label = f"{iso_cal.year}-W{iso_cal.week:02d}"
            groups.setdefault(label, []).append(d)

        return [
            {"week_label": label, "tasks": tasks}
            for label, tasks in sorted(groups.items(), reverse=True)
        ]

    def get_recent_activity(self, days: int = 7) -> list[dict[str, Any]]:
        """Return completed tasks from the last N days."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = self.conn.execute(
            "SELECT t.* FROM tasks t "
            "WHERE t.status = 'done' AND t.completed_at >= ? "
            "ORDER BY t.completed_at DESC",
            (cutoff,),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ── CSV Export ───────────────────────────────────────────────────

    def export_csv(
        self,
        project: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> str:
        """Export tasks as CSV string. 3 filter modes: dates, project, both."""
        clauses: list[str] = []
        params: list[Any] = []

        if project:
            clauses.append("project_name = ?")
            params.append(project)
        if start_date:
            clauses.append("created_at >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("created_at <= ?")
            params.append(end_date)

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

        rows = self.conn.execute(
            f"SELECT task_id, title, type, status, project_name, created_at, completed_at, tags "
            f"FROM tasks{where} ORDER BY created_at DESC",
            params,
        ).fetchall()

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            ["task_id", "title", "type", "status", "project", "created_at", "completed_at", "tags"]
        )
        for r in rows:
            writer.writerow([r[i] for i in range(len(r))])
        return buf.getvalue()
