"""Shared test fixtures for taskboard store and web tests."""

import sqlite3

import pytest
from starlette.testclient import TestClient

from taskboard.store import TaskboardStore
from taskboard.web.app import create_app


@pytest.fixture
def store():
    """In-memory store with schema initialized for testing."""
    s = _create_in_memory_store()
    yield s


@pytest.fixture
def second_project(store):
    """Add a second project for multi-project tests."""
    return store.add_project(
        name="otherproj",
        display_name="Other Project",
        slug="op",
        origin="local",
        path="/tmp/otherproj",
    )


@pytest.fixture
def seeded_store(store, second_project):
    """Store pre-populated with sample tasks across statuses and projects."""
    # testproj tasks
    t1 = store.add_task("testproj", "Feature task", type="feature")
    t2 = store.add_task("testproj", "Bug task", type="bugfix")
    t3 = store.add_task("testproj", "Chore task", type="chore")
    store.complete_task(t1["task_id"], summary="Done")
    store.update_task_status(t2["task_id"], "in_progress", note="Working on it")
    # otherproj tasks
    t4 = store.add_task("otherproj", "Refactor task", type="refactor")
    t5 = store.add_task("otherproj", "Docs task", type="docs")
    store.complete_task(t4["task_id"], summary="Refactored")
    return store, t1, t2, t3, t4, t5


@pytest.fixture
def client():
    """TestClient with thread-safe in-memory store — fresh per test."""
    s = _create_in_memory_store(check_same_thread=False)
    app = create_app(store=s)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def seeded_client():
    """TestClient with pre-seeded store (projects + tasks across statuses)."""
    s = _create_in_memory_store(check_same_thread=False)
    # Seed second project
    s.add_project(
        name="otherproj",
        display_name="Other Project",
        slug="op",
        origin="local",
        path="/tmp/otherproj",
    )
    # Seed tasks
    s.add_task("testproj", "Feature task", type="feature")
    s.add_task("testproj", "Bug task", type="bugfix")
    s.add_task("testproj", "Chore task", type="chore")
    s.add_task("otherproj", "Refactor task", type="refactor")
    s.add_task("otherproj", "Docs task", type="docs")
    app = create_app(store=s)
    with TestClient(app) as c:
        yield c


def _create_in_memory_store(check_same_thread: bool = True) -> TaskboardStore:
    """Create an in-memory store with a persistent connection.

    For TestClient (which runs in a separate thread), pass
    check_same_thread=False.
    """
    s = TaskboardStore.__new__(TaskboardStore)
    s._db_path = ":memory:"
    s._persistent_conn = sqlite3.connect(":memory:", check_same_thread=check_same_thread)
    s._persistent_conn.row_factory = sqlite3.Row
    _init_schema(s._persistent_conn)
    # Seed default test project
    s.add_project(
        name="testproj",
        display_name="Test Project",
        slug="tp",
        origin="local",
        path="/tmp/testproj",
    )
    return s


def _init_schema(conn: sqlite3.Connection) -> None:
    """Create the taskboard schema in an in-memory DB."""
    conn.executescript("""
        PRAGMA journal_mode = WAL;
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS projects (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          display_name TEXT NOT NULL,
          slug TEXT NOT NULL UNIQUE,
          origin TEXT NOT NULL CHECK(origin IN ('github', 'gitlab', 'local')),
          repo TEXT,
          path TEXT NOT NULL,
          tags TEXT NOT NULL DEFAULT '[]',
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS tasks (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          task_id TEXT NOT NULL UNIQUE,
          title TEXT NOT NULL,
          type TEXT NOT NULL CHECK(type IN (
            'feature', 'bugfix', 'refactor', 'config', 'chore', 'docs', 'testing', 'infra'
          )),
          project_name TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'todo' CHECK(status IN (
            'todo', 'in_progress', 'blocked', 'done', 'cancelled'
          )),
          source TEXT NOT NULL DEFAULT 'manual' CHECK(source IN ('sdd', 'manual', 'detected')),
          priority TEXT NOT NULL DEFAULT 'medium' CHECK(priority IN ('low', 'medium', 'high', 'urgent')),
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          completed_at TEXT,
          git_commit TEXT,
          git_branch TEXT,
          summary TEXT NOT NULL DEFAULT '',
          tags TEXT NOT NULL DEFAULT '[]',
          notes TEXT NOT NULL DEFAULT '',
          FOREIGN KEY (project_name) REFERENCES projects(name) ON UPDATE CASCADE
        );

        CREATE TABLE IF NOT EXISTS task_history (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          task_id TEXT NOT NULL,
          from_status TEXT,
          to_status TEXT NOT NULL,
          note TEXT NOT NULL DEFAULT '',
          git_commit TEXT,
          at TEXT NOT NULL DEFAULT (datetime('now')),
          FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS meta (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_name);
        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks(type);
        CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at);
        CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(completed_at);
        CREATE INDEX IF NOT EXISTS idx_tasks_source ON tasks(source);
        CREATE INDEX IF NOT EXISTS idx_history_task ON task_history(task_id);
        CREATE INDEX IF NOT EXISTS idx_history_at ON task_history(at);
    """)
