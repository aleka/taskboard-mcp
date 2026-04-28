"""TaskboardStore — SQLite persistence layer for the taskboard.

Connection-per-operation with write serialization via threading.Lock,
WAL mode, and full CRUD + analytics + CSV export over the existing schema.

Pattern mirrors Go's database/sql: each call opens a connection, does its
work, and closes it. WAL mode handles concurrent readers; a write lock
serializes writers.
"""

from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import threading
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Callable


# ── Sentinel for distinguishing "not passed" from "set to None" ──────

_SENTINEL = object()

# ── Migration Framework ──────────────────────────────────────────────


def _migrate_v2(conn: sqlite3.Connection) -> None:
    """Add parent_task_id column and index for task hierarchy (v1→v2).

    Idempotent: checks if column already exists before ALTER TABLE.
    """
    columns = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
    if "parent_task_id" not in columns:
        conn.execute(
            "ALTER TABLE tasks ADD COLUMN parent_task_id TEXT REFERENCES tasks(task_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_task_id)"
        )


_MIGRATIONS: OrderedDict[int, Callable[[sqlite3.Connection], None]] = OrderedDict(
    {2: _migrate_v2}
)


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Run pending schema migrations based on meta.schema_version.

    For in-memory databases (testing), this is a no-op since the
    persistent connection check in `_connect()` skips migration.
    """
    # Check if meta table exists (might not on raw in-memory DBs)
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='meta'"
    ).fetchall()]
    if "meta" not in tables:
        return
    row = conn.execute(
        "SELECT value FROM meta WHERE key = 'schema_version'"
    ).fetchone()
    current = int(row[0]) if row else 1
    for version in sorted(_MIGRATIONS):
        if version > current:
            _MIGRATIONS[version](conn)
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
                (str(version),),
            )
            conn.commit()


class TaskboardStore:
    """Manages short-lived SQLite connections to ~/.taskboard/taskboard.db.

    Each public method opens a fresh connection, performs its work inside
    a single transaction, commits, and closes. A ``threading.Lock``
    serializes writes so only one thread writes at a time.

    Reads are concurrent (WAL mode allows many readers + one writer).
    Writes are serialized (Lock ensures queue, not contention).

    Usage::

        with TaskboardStore() as store:
            store.add_project(...)
            store.add_task(...)
    """

    _write_lock = threading.Lock()

    def __init__(self, db_path: str = "~/.taskboard/taskboard.db") -> None:
        """Open the SQLite store at *db_path* (expanded via ``os.path.expanduser``).

        For in-memory testing, pass ``":memory:"`` and set
        ``_persistent_conn`` externally.
        """
        self._db_path = os.path.expanduser(db_path)
        # For in-memory testing: hold a persistent connection so :memory: data
        # survives across calls. Production code leaves this as None.
        self._persistent_conn: sqlite3.Connection | None = None

    # ── Connection lifecycle ──────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        """Open a fresh connection with WAL, busy_timeout, FK.

        For in-memory databases (testing), returns a persistent connection
        so the data survives across calls. Migrations are skipped for
        in-memory databases since conftest creates the schema directly.
        """
        if self._persistent_conn is not None:
            return self._persistent_conn
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        _run_migrations(conn)
        return conn

    def _close(self, conn: sqlite3.Connection) -> None:
        """Close a connection unless it's the persistent test connection."""
        if conn is not self._persistent_conn:
            conn.close()

    def __enter__(self) -> TaskboardStore:
        return self

    def __exit__(self, *exc: object) -> None:
        pass  # No persistent connection to close

    # ── Helpers ──────────────────────────────────────────────────────

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return dict(row)

    def _generate_task_id(self, conn: sqlite3.Connection, project_name: str) -> str:
        """Return ``{slug}_{NNN}`` for the given project.

        Uses the highest existing sequence number (not row count) so that
        deletions don't cause ID collisions.  For example if tasks
        ``mag_001`` through ``mag_056`` exist and ``mag_055`` is deleted,
        the next task will be ``mag_057`` — not a colliding ``mag_056``.
        """
        slug = conn.execute(
            "SELECT slug FROM projects WHERE name = ?", (project_name,)
        ).fetchone()
        if slug is None:
            raise ValueError(f"Project '{project_name}' not found")
        slug_str = slug[0]
        # Find the highest NNN among existing task IDs for this project
        max_row = conn.execute(
            "SELECT task_id FROM tasks WHERE project_name = ? AND task_id LIKE ?",
            (project_name, f"{slug_str}_%"),
        ).fetchall()
        max_seq = 0
        for row in max_row:
            # Extract the numeric suffix: "mag_056" → 56
            suffix = row[0].split("_", 1)[-1]
            try:
                seq = int(suffix)
                if seq > max_seq:
                    max_seq = seq
            except ValueError:
                continue
        return f"{slug_str}_{max_seq + 1:03d}"

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
        """Create a new project. Raises ``ValueError`` on duplicate name/slug."""
        tags_json = json.dumps(tags or [])
        with self._write_lock:
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO projects (name, display_name, slug, origin, repo, path, tags) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (name, display_name, slug, origin, repo, path, tags_json),
                )
                conn.commit()
            except sqlite3.IntegrityError as exc:
                raise ValueError(
                    f"Project with name '{name}' or slug '{slug}' already exists"
                ) from exc
            finally:
                self._close(conn)
        return self.get_project(slug)  # type: ignore[return-value]

    def get_project(self, slug: str) -> dict[str, Any] | None:
        """Return a project dict by slug, or ``None`` if not found."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM projects WHERE slug = ?", (slug,)
            ).fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            self._close(conn)

    def get_project_by_name(self, name: str) -> dict[str, Any] | None:
        """Look up a project by its ``name`` (not slug)."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM projects WHERE name = ?", (name,)
            ).fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            self._close(conn)

    def list_projects(self) -> list[dict[str, Any]]:
        """Return all projects sorted by name."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM projects ORDER BY name"
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            self._close(conn)

    def delete_project(self, name: str, force: bool = False) -> dict[str, Any]:
        """Delete a project by name.

        Raises ``ValueError`` if the project has associated tasks and
        ``force`` is ``False``.  Use ``force=True`` to cascade-delete
        all associated tasks and their history first.
        """
        with self._write_lock:
            conn = self._connect()
            try:
                project = conn.execute(
                    "SELECT * FROM projects WHERE name = ?", (name,)
                ).fetchone()
                if project is None:
                    raise ValueError(f"Project '{name}' not found")

                task_count = conn.execute(
                    "SELECT COUNT(*) FROM tasks WHERE project_name = ?", (name,)
                ).fetchone()[0]

                if task_count > 0 and not force:
                    raise ValueError(
                        f"Project '{name}' has {task_count} associated task(s). "
                        f"Use force=True to delete them as well."
                    )

                if task_count > 0:
                    task_ids = [
                        r["task_id"]
                        for r in conn.execute(
                            "SELECT task_id FROM tasks WHERE project_name = ?", (name,)
                        ).fetchall()
                    ]
                    for tid in task_ids:
                        conn.execute(
                            "DELETE FROM task_history WHERE task_id = ?", (tid,)
                        )
                    conn.execute(
                        "DELETE FROM tasks WHERE project_name = ?", (name,)
                    )

                conn.execute("DELETE FROM projects WHERE name = ?", (name,))
                conn.commit()
            finally:
                self._close(conn)

        return {
            "deleted": name,
            "tasks_removed": task_count,
        }

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
        git_commit: str | None = None,
        parent_task_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new task with auto-generated ``{slug}_{NNN}`` ID."""
        tags_json = json.dumps(tags or [])
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._write_lock:
            conn = self._connect()
            try:
                task_id = self._generate_task_id(conn, project)
                conn.execute(
                    "INSERT INTO tasks "
                    "(task_id, title, type, project_name, status, source, priority, "
                    "summary, tags, description, created_at, git_commit, parent_task_id) "
                    "VALUES (?, ?, ?, ?, 'todo', ?, ?, '', ?, ?, ?, ?, ?)",
                    (task_id, title, type, project, source, priority,
                     tags_json, description, now, git_commit, parent_task_id),
                )
                conn.execute(
                    "INSERT INTO task_history (task_id, from_status, to_status, note, git_commit) "
                    "VALUES (?, NULL, 'todo', 'Creada', NULL)",
                    (task_id,),
                )
                conn.commit()
            finally:
                self._close(conn)
        return self.get_task(task_id)  # type: ignore[return-value]

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        """Return a task dict by ID, or ``None`` if not found."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            self._close(conn)

    def get_task_neighbors(self, task_id: str) -> dict[str, str | None] | None:
        """Return prev/next task IDs for navigation within the same project.

        Uses created_at ordering (with ``id`` as tiebreaker when timestamps
        match) to determine adjacency.
        Returns ``{"prev": "xx_NNN" | None, "next": "xx_NNN" | None}``
        or ``None`` if task_id doesn't exist.
        """
        conn = self._connect()
        try:
            current = conn.execute(
                "SELECT project_name, created_at, id FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if current is None:
                return None

            project_name = current["project_name"]
            created_at = current["created_at"]
            row_id = current["id"]

            prev_row = conn.execute(
                "SELECT task_id FROM tasks "
                "WHERE project_name = ? AND (created_at < ? OR (created_at = ? AND id < ?)) "
                "ORDER BY created_at DESC, id DESC LIMIT 1",
                (project_name, created_at, created_at, row_id),
            ).fetchone()

            next_row = conn.execute(
                "SELECT task_id FROM tasks "
                "WHERE project_name = ? AND (created_at > ? OR (created_at = ? AND id > ?)) "
                "ORDER BY created_at ASC, id ASC LIMIT 1",
                (project_name, created_at, created_at, row_id),
            ).fetchone()

            return {
                "prev": prev_row["task_id"] if prev_row else None,
                "next": next_row["task_id"] if next_row else None,
            }
        finally:
            self._close(conn)

    _ALLOWED_ORDER = {"created_at", "completed_at", "status", "priority", "type", "title"}
    _ALLOWED_DIR = {"ASC", "DESC"}

    def list_tasks(
        self,
        project: str | None = None,
        status: str | None = None,
        type: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at",
        order_dir: str = "DESC",
    ) -> list[dict[str, Any]]:
        """Return tasks matching filters, sorted by *order_by* column.

        Parameters ``order_by`` and ``order_dir`` are validated against
        hardcoded whitelists to prevent SQL injection — they are
        interpolated into the ORDER BY clause, NOT parameterised.
        """
        if order_by not in self._ALLOWED_ORDER:
            order_by = "created_at"
        if order_dir not in self._ALLOWED_DIR:
            order_dir = "DESC"

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

        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT * FROM tasks{where} ORDER BY {order_by} {order_dir} LIMIT ? OFFSET ?",
                params,
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            self._close(conn)

    def update_task_status(
        self, task_id: str, status: str, note: str = "", git_commit: str | None = None
    ) -> dict[str, Any]:
        """Change task status, update completed_at, and record a history entry."""
        with self._write_lock:
            conn = self._connect()
            try:
                task = conn.execute(
                    "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
                ).fetchone()
                if task is None:
                    raise ValueError(f"Task '{task_id}' not found")
                old_status = task["status"]
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Update status + completed_at (set on done, clear on reopen)
                if status == "done":
                    conn.execute(
                        "UPDATE tasks SET status = ?, completed_at = ?, "
                        "git_commit = COALESCE(?, git_commit) WHERE task_id = ?",
                        (status, now, git_commit, task_id),
                    )
                elif old_status == "done" and status != "done":
                    conn.execute(
                        "UPDATE tasks SET status = ?, completed_at = NULL WHERE task_id = ?",
                        (status, task_id),
                    )
                else:
                    conn.execute(
                        "UPDATE tasks SET status = ? WHERE task_id = ?", (status, task_id)
                    )

                conn.execute(
                    "INSERT INTO task_history (task_id, from_status, to_status, note, git_commit) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (task_id, old_status, status, note, git_commit),
                )
                conn.commit()
            finally:
                self._close(conn)
        return self.get_task(task_id)  # type: ignore[return-value]

    def complete_task(
        self,
        task_id: str,
        summary: str = "",
        git_commit: str | None = None,
    ) -> dict[str, Any]:
        """Mark a task as done, set completed_at, and record history."""
        with self._write_lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
                ).fetchone()
                if row is None:
                    raise ValueError(f"Task '{task_id}' not found")
                old_status = row["status"]
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                conn.execute(
                    "UPDATE tasks SET status = 'done', completed_at = ?, summary = ?, "
                    "git_commit = COALESCE(?, git_commit) WHERE task_id = ?",
                    (now, summary or row["summary"], git_commit, task_id),
                )
                conn.execute(
                    "INSERT INTO task_history (task_id, from_status, to_status, note, git_commit) "
                    "VALUES (?, ?, 'done', ?, ?)",
                    (task_id, old_status, summary or "Completada", git_commit),
                )
                conn.commit()
            finally:
                self._close(conn)
        return self.get_task(task_id)  # type: ignore[return-value]

    def delete_task(self, task_id: str) -> bool:
        """Delete a task. Returns ``True`` if deleted, ``False`` if not found."""
        with self._write_lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT task_id FROM tasks WHERE task_id = ?", (task_id,)
                ).fetchone()
                if row is None:
                    return False
                conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
                conn.commit()
            finally:
                self._close(conn)
        return True

    # ── Generic update (V2-05) ────────────────────────────────────────

    def update_task(
        self,
        task_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        priority: str | None = None,
        type: str | None = None,
        status: str | None = None,
        git_commit: str | None = None,
        parent_task_id: str | None | object = _SENTINEL,
    ) -> dict[str, Any]:
        """Update editable fields on a task.

        Only non-None params become SET clauses. Use ``parent_task_id=None``
        to clear the parent (``_SENTINEL`` means "not passed").
        Records history if status changes.
        """
        with self._write_lock:
            conn = self._connect()
            try:
                task = conn.execute(
                    "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
                ).fetchone()
                if task is None:
                    raise ValueError(f"Task '{task_id}' not found")

                set_clauses: list[str] = []
                params: list[Any] = []

                field_map = {
                    "title": title,
                    "description": description,
                    "priority": priority,
                    "type": type,
                    "status": status,
                    "git_commit": git_commit,
                }
                for col, val in field_map.items():
                    if val is not None:
                        set_clauses.append(f"{col} = ?")
                        params.append(val)

                # parent_task_id uses sentinel — None means "clear"
                if parent_task_id is not _SENTINEL:
                    set_clauses.append("parent_task_id = ?")
                    params.append(parent_task_id)

                if not set_clauses:
                    return self._row_to_dict(task)

                # If status is changing, record history and update completed_at
                new_status = field_map["status"]
                if new_status is not None and new_status != task["status"]:
                    conn.execute(
                        "INSERT INTO task_history "
                        "(task_id, from_status, to_status, note, git_commit) "
                        "VALUES (?, ?, ?, 'Updated', ?)",
                        (task_id, task["status"], new_status, git_commit),
                    )
                    # Set completed_at on done, clear on reopen
                    if new_status == "done":
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        set_clauses.append("completed_at = ?")
                        params.append(now)
                    elif task["status"] == "done" and new_status != "done":
                        set_clauses.append("completed_at = NULL")

                params.append(task_id)
                conn.execute(
                    f"UPDATE tasks SET {', '.join(set_clauses)} WHERE task_id = ?",
                    params,
                )
                conn.commit()
            finally:
                self._close(conn)
        return self.get_task(task_id)  # type: ignore[return-value]

    # ── History read (V2-06) ──────────────────────────────────────────

    def get_task_history(self, task_id: str) -> list[dict[str, Any]]:
        """Return status transition history ordered by timestamp DESC."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT from_status, to_status, at, note, git_commit "
                "FROM task_history WHERE task_id = ? ORDER BY at DESC, id DESC",
                (task_id,),
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            self._close(conn)

    # ── Atomic tag operations (V2-09) ─────────────────────────────────

    def add_tag(self, task_id: str, tag: str) -> dict[str, Any]:
        """Atomically add a tag under write lock. No-op if already present."""
        with self._write_lock:
            conn = self._connect()
            try:
                task = conn.execute(
                    "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
                ).fetchone()
                if task is None:
                    raise ValueError(f"Task '{task_id}' not found")

                tags: list[str] = json.loads(task["tags"])
                if tag not in tags:
                    tags.append(tag)
                    conn.execute(
                        "UPDATE tasks SET tags = ? WHERE task_id = ?",
                        (json.dumps(tags), task_id),
                    )
                    conn.commit()
            finally:
                self._close(conn)
        return self.get_task(task_id)  # type: ignore[return-value]

    def remove_tag(self, task_id: str, tag: str) -> dict[str, Any]:
        """Atomically remove a tag under write lock. No-op if not present."""
        with self._write_lock:
            conn = self._connect()
            try:
                task = conn.execute(
                    "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
                ).fetchone()
                if task is None:
                    raise ValueError(f"Task '{task_id}' not found")

                tags: list[str] = json.loads(task["tags"])
                if tag in tags:
                    tags.remove(tag)
                    conn.execute(
                        "UPDATE tasks SET tags = ? WHERE task_id = ?",
                        (json.dumps(tags), task_id),
                    )
                    conn.commit()
            finally:
                self._close(conn)
        return self.get_task(task_id)  # type: ignore[return-value]

    # ── Parent-child hierarchy (V2-07 + V2-08) ───────────────────────

    def set_parent(
        self, task_id: str, parent_task_id: str | None
    ) -> dict[str, Any]:
        """Set or clear parent. Raises ValueError on cycle or missing parent."""
        with self._write_lock:
            conn = self._connect()
            try:
                task = conn.execute(
                    "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
                ).fetchone()
                if task is None:
                    raise ValueError(f"Task '{task_id}' not found")

                if parent_task_id is not None:
                    # Check self-reference
                    if task_id == parent_task_id:
                        raise ValueError(
                            f"Task '{task_id}' cannot be its own parent"
                        )
                    # Check parent exists
                    parent = conn.execute(
                        "SELECT task_id FROM tasks WHERE task_id = ?",
                        (parent_task_id,),
                    ).fetchone()
                    if parent is None:
                        raise ValueError(
                            f"Parent task '{parent_task_id}' not found"
                        )
                    # Check for cycles via recursive CTE
                    self._check_cycle(conn, task_id, parent_task_id)

                conn.execute(
                    "UPDATE tasks SET parent_task_id = ? WHERE task_id = ?",
                    (parent_task_id, task_id),
                )
                conn.commit()
            finally:
                self._close(conn)
        return self.get_task(task_id)  # type: ignore[return-value]

    def get_children(self, parent_task_id: str) -> list[dict[str, Any]]:
        """Return all direct children of a task."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE parent_task_id = ?",
                (parent_task_id,),
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            self._close(conn)

    def get_parent(self, task_id: str) -> dict[str, Any] | None:
        """Return the parent task dict, or None if no parent."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT p.* FROM tasks t "
                "JOIN tasks p ON t.parent_task_id = p.task_id "
                "WHERE t.task_id = ?",
                (task_id,),
            ).fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            self._close(conn)

    def _check_cycle(
        self, conn: sqlite3.Connection, task_id: str, proposed_parent: str
    ) -> None:
        """Raise ValueError if setting proposed_parent would create a cycle.

        Uses recursive CTE to walk ancestor chain from proposed_parent upward.
        If task_id appears in the ancestor chain, it's a cycle.
        """
        ancestors = conn.execute("""
            WITH RECURSIVE ancestors(tid) AS (
                VALUES(?)
                UNION ALL
                SELECT t.parent_task_id
                FROM tasks t
                INNER JOIN ancestors a ON t.task_id = a.tid
                WHERE t.parent_task_id IS NOT NULL
                LIMIT 20
            )
            SELECT tid FROM ancestors
        """, (proposed_parent,)).fetchall()

        if any(r["tid"] == task_id for r in ancestors):
            raise ValueError(
                f"Setting parent to '{proposed_parent}' would create a cycle"
            )

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

        conn = self._connect()
        try:
            total = conn.execute(
                f"SELECT COUNT(*) FROM tasks{where}", params
            ).fetchone()[0]

            completed = conn.execute(
                f"SELECT COUNT(*) FROM tasks{where_and}status = 'done'", params
            ).fetchone()[0]

            by_status_rows = conn.execute(
                f"SELECT status, COUNT(*) as cnt FROM tasks{where_and}1=1 GROUP BY status",
                params,
            ).fetchall()
            tasks_by_status = {r[0]: r[1] for r in by_status_rows}

            by_type_rows = conn.execute(
                f"SELECT type, COUNT(*) as cnt FROM tasks{where_and}1=1 GROUP BY type",
                params,
            ).fetchall()
            tasks_by_type = {r[0]: r[1] for r in by_type_rows}
        finally:
            self._close(conn)

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

    def get_timeline(
        self, view: str = "week", project: str | None = None
    ) -> list[dict[str, Any]]:
        """Return timeline data for the given view ('week' or 'month')."""
        if view == "month":
            return self.get_timeline_month(project=project)
        return self.get_timeline_week(project=project)

    def get_timeline_week(
        self, project: str | None = None
    ) -> list[dict[str, Any]]:
        """Tasks completed in the current ISO week, grouped by week label."""
        return self._get_timeline(
            project=project,
            since_expr="date('now', 'weekday 1', '-7 days')",
        )

    def get_timeline_month(
        self, project: str | None = None
    ) -> list[dict[str, Any]]:
        """Tasks completed in the current calendar month, grouped by week."""
        return self._get_timeline(
            project=project,
            since_expr="date('now', 'start of month')",
        )

    def _get_timeline(
        self,
        project: str | None,
        since_expr: str,
    ) -> list[dict[str, Any]]:
        clauses = ["status = 'done'", "completed_at IS NOT NULL"]
        params: list[Any] = []

        if project:
            clauses.append("project_name = ?")
            params.append(project)

        where = " WHERE " + " AND ".join(clauses)
        # since_expr is a trusted SQL expression (e.g. "date('now', 'weekday 1', '-7 days')")
        where += f" AND completed_at >= {since_expr}"

        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT t.task_id, t.title, t.type, t.project_name, t.completed_at, p.slug "
                f"FROM tasks t JOIN projects p ON t.project_name = p.name"
                f"{where} ORDER BY t.completed_at DESC",
                params,
            ).fetchall()
        finally:
            self._close(conn)

        # Group by week
        groups: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            d = self._row_to_dict(r)
            try:
                completed = datetime.strptime(d["completed_at"], "%Y-%m-%d %H:%M:%S")
            except ValueError:
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
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT t.* FROM tasks t "
                "WHERE t.status = 'done' AND t.completed_at >= ? "
                "ORDER BY t.completed_at DESC",
                (cutoff,),
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            self._close(conn)

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

        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT task_id, title, type, status, project_name, created_at, completed_at, tags "
                f"FROM tasks{where} ORDER BY created_at DESC",
                params,
            ).fetchall()
        finally:
            self._close(conn)

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            ["task_id", "title", "type", "status", "project", "created_at", "completed_at", "tags"]
        )
        for r in rows:
            writer.writerow([r[i] for i in range(len(r))])
        return buf.getvalue()
