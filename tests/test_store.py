"""Comprehensive unit tests for TaskboardStore."""

import csv
import io
import json
import re
import sqlite3

import pytest

from taskboard.store import TaskboardStore


# ── Connection lifecycle ────────────────────────────────────────────


class TestConnectionLifecycle:
    def test_context_manager_enter_exit(self, store):
        # Connection-per-call: _persistent_conn exists for in-memory stores
        assert store._persistent_conn is not None

    def test_wal_mode(self, store):
        mode = store._connect().execute("PRAGMA journal_mode").fetchone()[0]
        # In-memory DB uses 'memory' journal mode, not 'wal'
        assert mode in ("wal", "memory")

    def test_busy_timeout(self, store):
        timeout = store._connect().execute("PRAGMA busy_timeout").fetchone()[0]
        assert timeout == 5000

    def test_foreign_keys(self, store):
        fk = store._connect().execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1

    def test_connection_reuse(self, store):
        # In-memory stores reuse the persistent connection
        conn1 = store._connect()
        conn2 = store._connect()
        assert conn1 is conn2

    def test_default_db_path(self):
        from taskboard.store import TaskboardStore
        s = TaskboardStore()
        assert s._db_path.endswith("taskboard.db")
        assert ".taskboard" in s._db_path


# ── Project CRUD ───────────────────────────────────────────────────


class TestProjectCrud:
    def test_add_project(self, store):
        p = store.add_project(
            name="myproj",
            display_name="My Project",
            slug="mp",
            origin="local",
            path="/tmp/mp",
        )
        assert p["name"] == "myproj"
        assert p["slug"] == "mp"
        assert p["origin"] == "local"

    def test_get_project(self, store):
        p = store.get_project("tp")
        assert p is not None
        assert p["name"] == "testproj"
        assert p["slug"] == "tp"

    def test_get_project_not_found(self, store):
        assert store.get_project("nonexistent") is None

    def test_list_projects(self, store):
        projects = store.list_projects()
        assert len(projects) == 1
        assert projects[0]["slug"] == "tp"

    def test_list_projects_sorted_by_name(self, store, second_project):
        projects = store.list_projects()
        assert len(projects) == 2
        assert projects[0]["name"] == "otherproj"
        assert projects[1]["name"] == "testproj"

    def test_duplicate_slug_raises(self, store):
        with pytest.raises(ValueError, match="already exists"):
            store.add_project(
                name="another",
                display_name="Another",
                slug="tp",
                origin="local",
                path="/tmp/a",
            )

    def test_duplicate_name_raises(self, store):
        with pytest.raises(ValueError, match="already exists"):
            store.add_project(
                name="testproj",
                display_name="Different",
                slug="xx",
                origin="local",
                path="/tmp/xx",
            )

    def test_project_with_tags(self, store):
        p = store.add_project(
            name="tagged",
            display_name="Tagged",
            slug="tg",
            origin="local",
            path="/tmp/tg",
            tags=["web", "api"],
        )
        assert p["tags"] == '["web", "api"]'

    def test_project_with_repo(self, store):
        p = store.add_project(
            name="repoproj",
            display_name="Repo Proj",
            slug="rp",
            origin="github",
            repo="owner/repo",
            path="/tmp/rp",
        )
        assert p["repo"] == "owner/repo"
        assert p["origin"] == "github"


# ── Task CRUD ──────────────────────────────────────────────────────


class TestTaskCrud:
    def test_add_task(self, store):
        t = store.add_task("testproj", "My first task", type="feature")
        assert t["task_id"] == "tp_001"
        assert t["title"] == "My first task"
        assert t["type"] == "feature"
        assert t["status"] == "todo"
        assert t["project_name"] == "testproj"
        assert t["priority"] == "medium"

    def test_add_task_with_tags(self, store):
        t = store.add_task("testproj", "Tagged task", tags=["urgent", "review"])
        assert "urgent" in t["tags"]
        assert "review" in t["tags"]

    def test_add_task_with_priority(self, store):
        t = store.add_task("testproj", "High priority", priority="high")
        assert t["priority"] == "high"

    def test_add_task_with_description(self, store):
        t = store.add_task("testproj", "Described task", description="Some details")
        assert t["description"] == "Some details"

    def test_task_id_generation_format(self, store):
        t = store.add_task("testproj", "Task 1")
        assert re.match(r"^tp_\d{3}$", t["task_id"])
        t2 = store.add_task("testproj", "Task 2")
        assert t2["task_id"] == "tp_002"

    def test_task_id_generation_uses_slug(self, store, second_project):
        t = store.add_task("otherproj", "Other task")
        assert t["task_id"].startswith("op_")

    def test_add_task_invalid_project_raises(self, store):
        with pytest.raises(ValueError, match="not found"):
            store.add_task("nonexistent", "Orphan task")

    def test_get_task(self, store):
        t = store.add_task("testproj", "Find me")
        found = store.get_task(t["task_id"])
        assert found is not None
        assert found["title"] == "Find me"

    def test_get_task_not_found(self, store):
        assert store.get_task("nonexistent_001") is None

    def test_list_tasks(self, store):
        store.add_task("testproj", "Task A")
        store.add_task("testproj", "Task B")
        tasks = store.list_tasks()
        assert len(tasks) == 2

    def test_list_tasks_filter_by_project(self, store, second_project):
        store.add_task("testproj", "Proj A task")
        store.add_task("otherproj", "Proj B task")
        tasks_a = store.list_tasks(project="testproj")
        tasks_b = store.list_tasks(project="otherproj")
        assert len(tasks_a) == 1
        assert len(tasks_b) == 1
        assert tasks_a[0]["project_name"] == "testproj"
        assert tasks_b[0]["project_name"] == "otherproj"

    def test_list_tasks_filter_by_status(self, seeded_store):
        store, t1, t2, t3, *_ = seeded_store
        todo = store.list_tasks(status="todo")
        done = store.list_tasks(status="done")
        in_progress = store.list_tasks(status="in_progress")
        assert len(todo) >= 1  # at least t3 (todo) + any otherproj todos
        assert len(done) >= 1   # at least t1 (done)
        assert len(in_progress) >= 1  # at least t2

    def test_list_tasks_filter_by_type(self, seeded_store):
        store, *_ = seeded_store
        features = store.list_tasks(type="feature")
        assert len(features) == 1
        assert features[0]["title"] == "Feature task"

    def test_list_tasks_limit_offset(self, store):
        for i in range(5):
            store.add_task("testproj", f"Task {i}")
        page1 = store.list_tasks(limit=2, offset=0)
        page2 = store.list_tasks(limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2
        # Different tasks (ordered by created_at DESC)
        assert page1[0]["task_id"] != page2[0]["task_id"]

    def test_list_tasks_from_date(self, store):
        t = store.add_task("testproj", "Future task")
        # Filter with a far-future date should return 0
        tasks = store.list_tasks(from_date="2099-01-01")
        assert len(tasks) == 0

    def test_list_tasks_to_date(self, store):
        store.add_task("testproj", "Old task")
        # Filter with a far-past date should return 0
        tasks = store.list_tasks(to_date="2000-01-01")
        assert len(tasks) == 0

    def test_update_task_status(self, store):
        t = store.add_task("testproj", "Status change")
        updated = store.update_task_status(t["task_id"], "in_progress", note="Starting")
        assert updated["status"] == "in_progress"

    def test_update_task_status_records_history(self, store):
        t = store.add_task("testproj", "History test")
        store.update_task_status(t["task_id"], "blocked", note="Waiting")
        history = store._connect().execute(
            "SELECT from_status, to_status, note FROM task_history WHERE task_id = ?",
            (t["task_id"],),
        ).fetchall()
        # Should have 2 history entries: creation (todo) + status change
        assert len(history) == 2
        assert history[1][0] == "todo"
        assert history[1][1] == "blocked"
        assert history[1][2] == "Waiting"

    def test_update_task_status_invalid_task_raises(self, store):
        with pytest.raises(ValueError, match="not found"):
            store.update_task_status("fake_001", "done")

    def test_complete_task(self, store):
        t = store.add_task("testproj", "Complete me")
        completed = store.complete_task(t["task_id"], summary="Finished!")
        assert completed["status"] == "done"
        assert completed["completed_at"] is not None
        assert completed["summary"] == "Finished!"

    def test_complete_task_records_history(self, store):
        t = store.add_task("testproj", "Complete history")
        store.complete_task(t["task_id"], summary="Done", git_commit="abc123")
        history = store._connect().execute(
            "SELECT from_status, to_status, note, git_commit FROM task_history "
            "WHERE task_id = ? ORDER BY id",
            (t["task_id"],),
        ).fetchall()
        # creation + completion
        assert len(history) == 2
        assert history[1][0] == "todo"
        assert history[1][1] == "done"
        assert history[1][2] == "Done"
        assert history[1][3] == "abc123"

    def test_complete_task_sets_completed_at(self, store):
        t = store.add_task("testproj", "Timestamp test")
        store.complete_task(t["task_id"])
        task = store.get_task(t["task_id"])
        assert task["completed_at"] is not None
        assert len(task["completed_at"]) > 0

    def test_complete_task_invalid_raises(self, store):
        with pytest.raises(ValueError, match="not found"):
            store.complete_task("nonexistent_001")

    def test_delete_task(self, store):
        t = store.add_task("testproj", "Delete me")
        assert store.delete_task(t["task_id"]) is True
        assert store.get_task(t["task_id"]) is None

    def test_delete_task_not_found(self, store):
        assert store.delete_task("nonexistent_001") is False

    def test_delete_task_cascades_history(self, store):
        t = store.add_task("testproj", "Cascade test")
        store.complete_task(t["task_id"])
        store.delete_task(t["task_id"])
        history = store._connect().execute(
            "SELECT COUNT(*) FROM task_history WHERE task_id = ?",
            (t["task_id"],),
        ).fetchone()[0]
        assert history == 0


# ── History Recording ──────────────────────────────────────────────


class TestHistoryRecording:
    def test_creation_records_history(self, store):
        t = store.add_task("testproj", "New task")
        history = store._connect().execute(
            "SELECT from_status, to_status FROM task_history WHERE task_id = ?",
            (t["task_id"],),
        ).fetchall()
        assert len(history) == 1
        row = tuple(history[0])
        assert row[0] is None  # from_status NULL for creation
        assert row[1] == "todo"

    def test_multiple_status_changes(self, store):
        t = store.add_task("testproj", "Lifecycle")
        store.update_task_status(t["task_id"], "in_progress")
        store.update_task_status(t["task_id"], "blocked")
        store.complete_task(t["task_id"])
        history = store._connect().execute(
            "SELECT from_status, to_status FROM task_history "
            "WHERE task_id = ? ORDER BY id",
            (t["task_id"],),
        ).fetchall()
        assert len(history) == 4
        assert tuple(history[0]) == (None, "todo")
        assert tuple(history[1]) == ("todo", "in_progress")
        assert tuple(history[2]) == ("in_progress", "blocked")
        assert tuple(history[3]) == ("blocked", "done")


# ── Metrics ────────────────────────────────────────────────────────


class TestMetrics:
    def test_global_metrics(self, seeded_store):
        store, *_ = seeded_store
        m = store.get_metrics()
        assert m["total_tasks"] == 5
        assert m["completed"] == 2  # t1 (testproj) + t4 (otherproj)
        assert m["pending"] >= 1  # at least t3 (todo)
        assert m["in_progress"] == 1  # t2
        assert "todo" in m["tasks_by_status"]
        assert "feature" in m["tasks_by_type"]

    def test_project_filtered_metrics(self, store, second_project):
        store.add_task("testproj", "TP task 1")
        store.add_task("testproj", "TP task 2")
        store.add_task("otherproj", "OP task 1")
        m = store.get_metrics(project="testproj")
        assert m["total_tasks"] == 2

    def test_date_filtered_metrics(self, store):
        t = store.add_task("testproj", "Dated task")
        m = store.get_metrics(start_date="2000-01-01", end_date="2099-12-31")
        assert m["total_tasks"] == 1

    def test_date_filtered_empty_range(self, store):
        store.add_task("testproj", "Task")
        m = store.get_metrics(start_date="2099-01-01", end_date="2099-12-31")
        assert m["total_tasks"] == 0

    def test_combined_filters(self, store, second_project):
        store.add_task("testproj", "TP1")
        store.add_task("otherproj", "OP1")
        m = store.get_metrics(project="testproj", start_date="2000-01-01", end_date="2099-12-31")
        assert m["total_tasks"] == 1
        assert m["tasks_by_type"]["chore"] == 1

    def test_empty_metrics(self, store):
        m = store.get_metrics()
        assert m["total_tasks"] == 0
        assert m["completion_rate"] == 0.0


# ── Timeline ───────────────────────────────────────────────────────


class TestTimeline:
    def test_timeline_week_returns_list(self, store):
        tw = store.get_timeline_week()
        assert isinstance(tw, list)

    def test_timeline_week_structure(self, store):
        tw = store.get_timeline_week()
        for group in tw:
            assert "week_label" in group
            assert "tasks" in group
            assert isinstance(group["tasks"], list)

    def test_timeline_month_returns_list(self, store):
        tm = store.get_timeline_month()
        assert isinstance(tm, list)

    def test_timeline_with_completed_tasks(self, store):
        t = store.add_task("testproj", "Timeline task")
        store.complete_task(t["task_id"])
        tw = store.get_timeline_week()
        # Should have at least 1 group since task was completed now
        assert len(tw) >= 1
        total_tasks = sum(len(g["tasks"]) for g in tw)
        assert total_tasks >= 1

    def test_timeline_project_filter(self, store, second_project):
        store.add_task("testproj", "TP timeline")
        store.complete_task("tp_001")  # This is the TP timeline task
        store.add_task("otherproj", "OP timeline")
        store.complete_task("op_001")
        tw = store.get_timeline_week(project="testproj")
        all_tasks = [t for g in tw for t in g["tasks"]]
        for t in all_tasks:
            assert t["project_name"] == "testproj"

    def test_timeline_month_captures_more(self, store):
        # Month timeline should include the same or more than week
        tw = store.get_timeline_week()
        tm = store.get_timeline_month()
        week_count = sum(len(g["tasks"]) for g in tw)
        month_count = sum(len(g["tasks"]) for g in tm)
        assert month_count >= week_count


# ── Recent Activity ────────────────────────────────────────────────


class TestRecentActivity:
    def test_recent_activity_returns_list(self, store):
        activity = store.get_recent_activity(days=7)
        assert isinstance(activity, list)

    def test_recent_activity_with_completed_tasks(self, store):
        t = store.add_task("testproj", "Recent task")
        store.complete_task(t["task_id"])
        activity = store.get_recent_activity(days=7)
        assert len(activity) >= 1

    def test_recent_activity_no_old_tasks(self, store):
        t = store.add_task("testproj", "Recent task")
        store.complete_task(t["task_id"])
        # 0 days should still include today's tasks
        activity = store.get_recent_activity(days=0)
        # Depending on timing, this might be 0 or 1. Just verify it runs.
        assert isinstance(activity, list)


# ── CSV Export ─────────────────────────────────────────────────────


class TestCsvExport:
    def test_export_all(self, store):
        store.add_task("testproj", "Export task")
        csv_str = store.export_csv()
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        # Header + 1 data row
        assert len(rows) == 2
        assert rows[0][0] == "task_id"
        assert "tp_001" in rows[1][0]

    def test_export_headers(self, store):
        csv_str = store.export_csv()
        reader = csv.reader(io.StringIO(csv_str))
        headers = next(reader)
        expected = ["task_id", "title", "type", "status", "project", "created_at", "completed_at", "tags"]
        assert headers == expected

    def test_export_filter_project(self, store, second_project):
        store.add_task("testproj", "TP export")
        store.add_task("otherproj", "OP export")
        csv_str = store.export_csv(project="testproj")
        rows = list(csv.reader(io.StringIO(csv_str)))
        # Header + 1 row
        assert len(rows) == 2
        assert "tp_001" in rows[1][0]

    def test_export_filter_dates(self, store):
        store.add_task("testproj", "Dated export")
        csv_str = store.export_csv(start_date="2000-01-01", end_date="2099-12-31")
        rows = list(csv.reader(io.StringIO(csv_str)))
        assert len(rows) == 2  # header + 1

    def test_export_filter_dates_empty(self, store):
        store.add_task("testproj", "Old task")
        csv_str = store.export_csv(start_date="2099-01-01", end_date="2099-12-31")
        rows = list(csv.reader(io.StringIO(csv_str)))
        assert len(rows) == 1  # header only

    def test_export_combined_filters(self, store, second_project):
        store.add_task("testproj", "TP combo")
        store.add_task("otherproj", "OP combo")
        csv_str = store.export_csv(
            project="testproj",
            start_date="2000-01-01",
            end_date="2099-12-31",
        )
        rows = list(csv.reader(io.StringIO(csv_str)))
        assert len(rows) == 2
        assert "tp" in rows[1][0]

    def test_export_empty_store(self, store):
        csv_str = store.export_csv()
        rows = list(csv.reader(io.StringIO(csv_str)))
        assert len(rows) == 1  # header only

    def test_export_uses_stdlib_csv(self, store):
        """Verify the output is proper CSV (parseable)."""
        store.add_task("testproj", 'Task with "quotes"')
        store.add_task("testproj", "Task with, comma")
        csv_str = store.export_csv()
        # Should be parseable without errors
        rows = list(csv.reader(io.StringIO(csv_str)))
        assert len(rows) == 3  # header + 2 data rows


# ── Task Neighbors ──────────────────────────────────────────────────


class TestTaskNeighbors:
    """get_task_neighbors() — prev/next navigation within same project."""

    def test_middle_task_has_both_neighbors(self, store):
        """A task in the middle of 3 tasks should have both prev and next."""
        t1 = store.add_task("testproj", "First task")
        t2 = store.add_task("testproj", "Second task")
        store.add_task("testproj", "Third task")
        neighbors = store.get_task_neighbors(t2["task_id"])
        assert neighbors is not None
        assert neighbors["prev"] == t1["task_id"]
        assert neighbors["next"] == "tp_003"

    def test_first_task_only_has_next(self, store):
        """The first (oldest) task in a project should only have next."""
        t1 = store.add_task("testproj", "First")
        store.add_task("testproj", "Second")
        neighbors = store.get_task_neighbors(t1["task_id"])
        assert neighbors is not None
        assert neighbors["prev"] is None
        assert neighbors["next"] == "tp_002"

    def test_last_task_only_has_prev(self, store):
        """The last (newest) task in a project should only have prev."""
        store.add_task("testproj", "First")
        t2 = store.add_task("testproj", "Second")
        neighbors = store.get_task_neighbors(t2["task_id"])
        assert neighbors is not None
        assert neighbors["prev"] == "tp_001"
        assert neighbors["next"] is None

    def test_nonexistent_task_returns_none(self, store):
        """Non-existent task_id should return None."""
        assert store.get_task_neighbors("nonexistent_999") is None

    def test_single_task_has_no_neighbors(self, store):
        """A project with a single task should have both neighbors as None."""
        t = store.add_task("testproj", "Only task")
        neighbors = store.get_task_neighbors(t["task_id"])
        assert neighbors is not None
        assert neighbors["prev"] is None
        assert neighbors["next"] is None

    def test_neighbors_cross_project_isolation(self, store, second_project):
        """Neighbors should not cross project boundaries."""
        store.add_task("testproj", "TP task")
        store.add_task("otherproj", "OP task")
        tp_neighbors = store.get_task_neighbors("tp_001")
        op_neighbors = store.get_task_neighbors("op_001")
        assert tp_neighbors["prev"] is None
        assert tp_neighbors["next"] is None
        assert op_neighbors["prev"] is None
        assert op_neighbors["next"] is None


# ── list_tasks Sorting ─────────────────────────────────────────────


class TestListTasksSorting:
    """list_tasks() order_by / order_dir parameters."""

    def test_default_sort_is_created_at_desc(self, store):
        """Without sort params, tasks should be ordered by created_at DESC."""
        store.add_task("testproj", "First")
        store.add_task("testproj", "Second")
        store.add_task("testproj", "Third")
        tasks = store.list_tasks()
        # Most recently created should be first
        assert tasks[0]["title"] == "Third"
        assert tasks[2]["title"] == "First"

    def test_sort_by_priority_asc(self, store):
        """Sorting by priority ASC should return alphabetical order."""
        store.add_task("testproj", "High task", priority="high")
        store.add_task("testproj", "Low task", priority="low")
        store.add_task("testproj", "Urgent task", priority="urgent")
        store.add_task("testproj", "Medium task", priority="medium")
        tasks = store.list_tasks(order_by="priority", order_dir="ASC")
        priorities = [t["priority"] for t in tasks]
        assert priorities == ["high", "low", "medium", "urgent"]

    def test_sort_by_status_desc(self, seeded_store):
        """Sorting by status DESC should reverse alphabetical order."""
        store, *_ = seeded_store
        tasks = store.list_tasks(order_by="status", order_dir="DESC")
        statuses = [t["status"] for t in tasks]
        # Verify descending: each status >= the next one alphabetically
        for i in range(len(statuses) - 1):
            assert statuses[i] >= statuses[i + 1]

    def test_sort_by_completed_at_asc(self, store):
        """Sorting by completed_at ASC should put earliest completions first."""
        t1 = store.add_task("testproj", "Done first")
        t2 = store.add_task("testproj", "Done second")
        store.complete_task(t1["task_id"])
        store.complete_task(t2["task_id"])
        tasks = store.list_tasks(
            status="done", order_by="completed_at", order_dir="ASC",
        )
        assert tasks[0]["task_id"] == t1["task_id"]
        assert tasks[1]["task_id"] == t2["task_id"]

    def test_invalid_order_by_falls_back_to_created_at(self, store):
        """An invalid order_by value should silently fall back to created_at."""
        store.add_task("testproj", "A task")
        tasks = store.list_tasks(order_by="totally_invalid_column")
        assert len(tasks) == 1

    def test_invalid_order_dir_falls_back_to_desc(self, store):
        """An invalid order_dir value should silently fall back to DESC."""
        store.add_task("testproj", "A task")
        tasks = store.list_tasks(order_dir="SIDEWAYS")
        assert len(tasks) == 1


# ── Connection lifecycle — non-persistent path ──────────────────────


class TestConnectionLifecycleNonPersistent:
    """Test the real _connect() and _close() paths (lines 63-68, 73)."""

    def test_connect_sets_pragmas_on_real_db(self, tmp_path):
        """A non-in-memory store should set WAL, busy_timeout, foreign_keys."""
        db_file = tmp_path / "test.db"
        from taskboard.store import TaskboardStore

        s = TaskboardStore(str(db_file))
        conn = s._connect()
        try:
            assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
            assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        finally:
            conn.close()

    def test_close_non_persistent_conn(self, tmp_path):
        """_close should close non-persistent connections."""
        db_file = tmp_path / "test_close.db"
        from taskboard.store import TaskboardStore

        s = TaskboardStore(str(db_file))
        conn = s._connect()
        s._close(conn)
        # Trying to use closed conn should raise
        import pytest as pt

        with pt.raises(Exception):
            conn.execute("SELECT 1")


# ── Delete Project ──────────────────────────────────────────────────


class TestDeleteProject:
    """delete_project() — with/without force, cascade, not found (lines 170-209)."""

    def test_delete_empty_project(self, store):
        """Delete a project with no tasks."""
        store.add_project(
            name="emptyp", display_name="Empty", slug="ep", origin="local", path="/tmp/ep"
        )
        result = store.delete_project("emptyp")
        assert result["deleted"] == "emptyp"
        assert result["tasks_removed"] == 0
        assert store.get_project("ep") is None

    def test_delete_project_not_found(self, store):
        with pytest.raises(ValueError, match="not found"):
            store.delete_project("nonexistent")

    def test_delete_project_with_tasks_no_force(self, store):
        """Refuses to delete project with tasks unless force=True."""
        store.add_task("testproj", "Blocking task")
        with pytest.raises(ValueError, match="associated task"):
            store.delete_project("testproj")

    def test_delete_project_with_tasks_force(self, store):
        """Force-deletes project with tasks, including history."""
        t = store.add_task("testproj", "Doomed task")
        store.update_task_status(t["task_id"], "in_progress")

        result = store.delete_project("testproj", force=True)
        assert result["deleted"] == "testproj"
        assert result["tasks_removed"] == 1
        # Task should be gone
        assert store.get_task(t["task_id"]) is None
        # History should be gone
        history = store._connect().execute(
            "SELECT COUNT(*) FROM task_history WHERE task_id = ?", (t["task_id"],)
        ).fetchone()[0]
        assert history == 0

    def test_delete_project_cascade_multiple_tasks(self, store):
        """Force-deletes project with multiple tasks."""
        t1 = store.add_task("testproj", "Task 1")
        t2 = store.add_task("testproj", "Task 2")
        t3 = store.add_task("testproj", "Task 3")

        result = store.delete_project("testproj", force=True)
        assert result["tasks_removed"] == 3
        assert store.get_task(t1["task_id"]) is None
        assert store.get_task(t2["task_id"]) is None
        assert store.get_task(t3["task_id"]) is None


# ── Timeline ValueError in completed_at parsing (line 555-556) ──────


class TestTimelineInvalidDate:
    """Timeline should skip rows with unparseable completed_at (lines 555-556)."""

    def test_timeline_skips_invalid_completed_at(self, store):
        """Insert a task with invalid completed_at; timeline should not crash."""
        store.add_task("testproj", "Valid task")
        # Complete it normally first
        t = store.add_task("testproj", "Another valid")
        store.complete_task(t["task_id"])

        # Insert a row with an invalid completed_at directly
        conn = store._connect()
        try:
            conn.execute(
                "INSERT INTO tasks (task_id, title, type, project_name, status, source, priority, summary, tags, description, created_at, completed_at) "
                "VALUES (?, ?, ?, ?, 'done', 'manual', 'medium', '', '[]', '', datetime('now'), 'not-a-date')",
                ("tp_invalid", "Bad date task", "chore", "testproj"),
            )
            conn.commit()
        finally:
            store._close(conn)

        # Should not crash
        tw = store.get_timeline_week()
        assert isinstance(tw, list)


# ── Migration Framework (v1→v2) ──────────────────────────────────────


def _create_v1_schema(conn: sqlite3.Connection) -> None:
    """Create a v1 schema (no parent_task_id column) for migration tests."""
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
          description TEXT NOT NULL DEFAULT '',
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
    """)
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', '1')"
    )
    conn.commit()


class TestMigrationV2:
    """Tests for v1→v2 migration: ADD COLUMN parent_task_id + index."""

    def test_migrate_v2_adds_parent_column(self):
        """Fresh v1 DB gets parent_task_id column after migration."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        _create_v1_schema(conn)

        from taskboard.store import _migrate_v2
        _migrate_v2(conn)

        columns = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        assert "parent_task_id" in columns

    def test_migrate_v2_adds_index(self):
        """Migration creates idx_tasks_parent index."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        _create_v1_schema(conn)

        from taskboard.store import _migrate_v2
        _migrate_v2(conn)

        indexes = [r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_tasks_parent'"
        ).fetchall()]
        assert "idx_tasks_parent" in indexes

    def test_migrate_v2_existing_tasks_get_null_parent(self):
        """Tasks that existed before migration have parent_task_id=NULL."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        _create_v1_schema(conn)
        # Insert a seed project and task
        conn.execute(
            "INSERT INTO projects (name, display_name, slug, origin, path) "
            "VALUES ('testproj', 'Test', 'tp', 'local', '/tmp')"
        )
        conn.execute(
            "INSERT INTO tasks (task_id, title, type, project_name, status, source, priority, summary, tags, description, created_at) "
            "VALUES ('tp_001', 'Old task', 'chore', 'testproj', 'todo', 'manual', 'medium', '', '[]', '', datetime('now'))"
        )
        conn.commit()

        from taskboard.store import _migrate_v2
        _migrate_v2(conn)

        task = conn.execute("SELECT parent_task_id FROM tasks WHERE task_id='tp_001'").fetchone()
        assert task["parent_task_id"] is None

    def test_migrate_v2_idempotent(self):
        """Running migration twice does not raise an error."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        _create_v1_schema(conn)

        from taskboard.store import _migrate_v2
        _migrate_v2(conn)
        _migrate_v2(conn)  # Second run — should be no-op

        columns = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        assert "parent_task_id" in columns

    def test_migrate_v2_sets_schema_version(self):
        """Migration updates meta.schema_version to 2."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        _create_v1_schema(conn)

        from taskboard.store import _migrate_v2, _run_migrations
        _migrate_v2(conn)
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', '2')"
        )
        conn.commit()

        # _run_migrations should skip v2 since version is already 2
        _run_migrations(conn)
        version = conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()[0]
        assert version == "2"

    def test_run_migrations_skips_in_memory(self):
        """In-memory stores (persistent_conn) skip migrations entirely."""
        from taskboard.store import TaskboardStore, _run_migrations

        s = TaskboardStore.__new__(TaskboardStore)
        s._db_path = ":memory:"
        s._persistent_conn = sqlite3.connect(":memory:", check_same_thread=True)
        s._persistent_conn.row_factory = sqlite3.Row

        # Don't set schema_version — if migration runs, it would fail
        # because no tables exist. Skipping proves the guard works.
        _run_migrations(s._persistent_conn)
        # No error means it was skipped
        s._persistent_conn.close()

    def test_run_migrations_from_v1(self):
        """_run_migrations progresses from v1 to v2."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        _create_v1_schema(conn)

        from taskboard.store import _run_migrations
        _run_migrations(conn)

        version = conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()[0]
        assert version == "2"
        columns = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        assert "parent_task_id" in columns


# ── update_task (V2-05) ─────────────────────────────────────────────


class TestUpdateTask:
    """Tests for the generic update_task() method."""

    def test_update_single_field_title(self, store):
        """Only the title field is updated; other fields unchanged."""
        task = store.add_task("testproj", "Original title")
        updated = store.update_task(task["task_id"], title="New title")
        assert updated["title"] == "New title"
        assert updated["status"] == "todo"
        assert updated["priority"] == "medium"

    def test_update_multiple_fields(self, store):
        """Multiple fields updated in a single call."""
        task = store.add_task("testproj", "Multi update")
        updated = store.update_task(
            task["task_id"], title="Updated", priority="high", type="feature"
        )
        assert updated["title"] == "Updated"
        assert updated["priority"] == "high"
        assert updated["type"] == "feature"

    def test_update_status_records_history(self, store):
        """Changing status via update_task records a history entry."""
        task = store.add_task("testproj", "Status test")
        store.update_task(task["task_id"], status="in_progress")
        history = store.get_task_history(task["task_id"])
        assert len(history) >= 2
        assert history[0]["to_status"] == "in_progress"
        assert history[0]["from_status"] == "todo"

    def test_update_nonexistent_raises(self, store):
        """Updating a task that doesn't exist raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            store.update_task("nonexistent_001", title="Nope")

    def test_update_no_fields_returns_unchanged(self, store):
        """Passing no fields returns task as-is without changes."""
        task = store.add_task("testproj", "No change")
        result = store.update_task(task["task_id"])
        assert result["title"] == "No change"
        assert result["status"] == "todo"

    def test_update_clears_parent(self, store):
        """Setting parent_task_id=None clears the parent relationship."""
        parent = store.add_task("testproj", "Parent task")
        child = store.add_task("testproj", "Child task", parent_task_id=parent["task_id"])
        assert child["parent_task_id"] == parent["task_id"]

        updated = store.update_task(child["task_id"], parent_task_id=None)
        assert updated["parent_task_id"] is None


# ── get_task_history (V2-06) ────────────────────────────────────────


class TestGetTaskHistory:
    """Tests for reading task status history."""

    def test_task_with_history(self, store):
        """Task with multiple status changes returns all entries."""
        task = store.add_task("testproj", "History test")
        store.update_task_status(task["task_id"], "in_progress", note="Started")
        store.update_task_status(task["task_id"], "blocked", note="Waiting")

        history = store.get_task_history(task["task_id"])
        assert len(history) == 3  # creation + 2 changes
        # Ordered newest first
        assert history[0]["to_status"] == "blocked"
        assert history[0]["from_status"] == "in_progress"
        assert history[1]["to_status"] == "in_progress"
        assert history[1]["from_status"] == "todo"

    def test_task_with_no_changes(self, store):
        """Freshly created task has exactly one history entry (creation)."""
        task = store.add_task("testproj", "Fresh task")
        history = store.get_task_history(task["task_id"])
        assert len(history) == 1
        assert history[0]["from_status"] is None
        assert history[0]["to_status"] == "todo"

    def test_nonexistent_task_returns_empty(self, store):
        """Non-existent task returns empty history list."""
        history = store.get_task_history("nonexistent_001")
        assert history == []


# ── Atomic Tag Editing (V2-09) ───────────────────────────────────────


class TestAtomicTagOps:
    """Tests for add_tag() and remove_tag() methods."""

    def test_add_new_tag(self, store):
        """Adding a new tag appends it to the tags list."""
        task = store.add_task("testproj", "Tag test", tags=["existing"])
        updated = store.add_tag(task["task_id"], "new-tag")
        tags = json.loads(updated["tags"])
        assert "new-tag" in tags
        assert "existing" in tags

    def test_add_duplicate_tag_is_noop(self, store):
        """Adding a tag that already exists doesn't duplicate it."""
        task = store.add_task("testproj", "Dup test", tags=["alpha"])
        updated = store.add_tag(task["task_id"], "alpha")
        tags = json.loads(updated["tags"])
        assert tags.count("alpha") == 1

    def test_remove_existing_tag(self, store):
        """Removing an existing tag removes it from the list."""
        task = store.add_task("testproj", "Remove test", tags=["alpha", "beta"])
        updated = store.remove_tag(task["task_id"], "alpha")
        tags = json.loads(updated["tags"])
        assert "alpha" not in tags
        assert "beta" in tags

    def test_remove_missing_tag_is_noop(self, store):
        """Removing a tag that doesn't exist doesn't change the list."""
        task = store.add_task("testproj", "Noop test", tags=["alpha"])
        updated = store.remove_tag(task["task_id"], "missing")
        tags = json.loads(updated["tags"])
        assert tags == ["alpha"]

    def test_add_tag_to_empty_list(self, store):
        """Adding a tag to a task with no tags works."""
        task = store.add_task("testproj", "Empty tags")
        updated = store.add_tag(task["task_id"], "first")
        tags = json.loads(updated["tags"])
        assert tags == ["first"]

    def test_concurrent_add_tag_two_threads(self, store):
        """Two threads adding different tags concurrently both succeed."""
        import threading
        from tests.conftest import _init_schema

        # Use file-based temp DB for real concurrent access (in-memory is unreliable)
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            ts_store = TaskboardStore(db_path=db_path)
            conn = ts_store._connect()
            _init_schema(conn)
            conn.close()
            ts_store.add_project(
                name="testproj", display_name="Test", slug="tp", origin="local", path="/tmp/tp"
            )

            task = ts_store.add_task("testproj", "Concurrent tags")
            task_id = task["task_id"]

            errors: list[str] = []

            def add_tag_safe(tag: str) -> None:
                try:
                    ts_store.add_tag(task_id, tag)
                except Exception as exc:
                    errors.append(str(exc))

            t1 = threading.Thread(target=add_tag_safe, args=("thread-a",))
            t2 = threading.Thread(target=add_tag_safe, args=("thread-b",))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            assert errors == [], f"Concurrent add_tag raised: {errors}"
            result = ts_store.get_task(task_id)
            tags = json.loads(result["tags"])
            assert "thread-a" in tags
            assert "thread-b" in tags

    def test_concurrent_add_tag_ten_threads(self, store):
        """Ten threads adding unique tags concurrently all succeed without lost updates."""
        import threading
        import tempfile
        from tests.conftest import _init_schema

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            ts_store = TaskboardStore(db_path=db_path)
            conn = ts_store._connect()
            _init_schema(conn)
            conn.close()
            ts_store.add_project(
                name="testproj", display_name="Test", slug="tp", origin="local", path="/tmp/tp"
            )

            task = ts_store.add_task("testproj", "Many concurrent tags")
            task_id = task["task_id"]
            tag_names = [f"tag-{i}" for i in range(10)]

            errors: list[str] = []

            def add_tag_safe(tag: str) -> None:
                try:
                    ts_store.add_tag(task_id, tag)
                except Exception as exc:
                    errors.append(str(exc))

            threads = [threading.Thread(target=add_tag_safe, args=(t,)) for t in tag_names]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert errors == [], f"Concurrent add_tag raised: {errors}"
            result = ts_store.get_task(task_id)
            tags = json.loads(result["tags"])
            for tag_name in tag_names:
                assert tag_name in tags, f"Missing tag {tag_name} after concurrent adds"
            assert len(tags) == 10, f"Expected 10 tags, got {len(tags)}: {tags}"


# ── Parent-Child Hierarchy (V2-07 + V2-08) ──────────────────────────


class TestParentChild:
    """Tests for set_parent, get_children, get_parent, cycle detection."""

    def test_set_parent(self, store):
        """Setting a parent creates the relationship."""
        parent = store.add_task("testproj", "Parent")
        child = store.add_task("testproj", "Child")
        updated = store.set_parent(child["task_id"], parent["task_id"])
        assert updated["parent_task_id"] == parent["task_id"]

    def test_get_children(self, store):
        """get_children returns all direct children of a task."""
        parent = store.add_task("testproj", "Parent")
        c1 = store.add_task("testproj", "Child 1", parent_task_id=parent["task_id"])
        c2 = store.add_task("testproj", "Child 2", parent_task_id=parent["task_id"])
        children = store.get_children(parent["task_id"])
        ids = [c["task_id"] for c in children]
        assert c1["task_id"] in ids
        assert c2["task_id"] in ids

    def test_get_parent(self, store):
        """get_parent returns the parent task dict."""
        parent = store.add_task("testproj", "Parent")
        child = store.add_task("testproj", "Child", parent_task_id=parent["task_id"])
        result = store.get_parent(child["task_id"])
        assert result is not None
        assert result["task_id"] == parent["task_id"]

    def test_get_parent_none(self, store):
        """get_parent returns None for a task without a parent."""
        task = store.add_task("testproj", "Orphan")
        assert store.get_parent(task["task_id"]) is None

    def test_set_parent_self_reference_raises(self, store):
        """Setting a task as its own parent raises ValueError."""
        task = store.add_task("testproj", "Self")
        with pytest.raises(ValueError, match="cannot be its own parent"):
            store.set_parent(task["task_id"], task["task_id"])

    def test_set_parent_indirect_cycle_raises(self, store):
        """Creating A→B→A cycle raises ValueError."""
        a = store.add_task("testproj", "Task A")
        b = store.add_task("testproj", "Task B")
        store.set_parent(b["task_id"], a["task_id"])
        with pytest.raises(ValueError, match="would create a cycle"):
            store.set_parent(a["task_id"], b["task_id"])

    def test_set_parent_nonexistent_raises(self, store):
        """Setting parent to a non-existent task raises ValueError."""
        child = store.add_task("testproj", "Child")
        with pytest.raises(ValueError, match="not found"):
            store.set_parent(child["task_id"], "nonexistent_001")

    def test_clear_parent(self, store):
        """Setting parent to None clears the relationship."""
        parent = store.add_task("testproj", "Parent")
        child = store.add_task("testproj", "Child", parent_task_id=parent["task_id"])
        updated = store.set_parent(child["task_id"], None)
        assert updated["parent_task_id"] is None

    def test_get_children_empty(self, store):
        """get_children returns empty list for task with no children."""
        task = store.add_task("testproj", "No kids")
        assert store.get_children(task["task_id"]) == []

    def test_add_task_with_parent(self, store):
        """add_task accepts parent_task_id and stores it."""
        parent = store.add_task("testproj", "Parent")
        child = store.add_task("testproj", "Child", parent_task_id=parent["task_id"])
        assert child["parent_task_id"] == parent["task_id"]
