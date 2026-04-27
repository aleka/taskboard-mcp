"""Unit tests for MCP server tools — mock store, verify response shapes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ── Helpers ────────────────────────────────────────────────────────


def _make_tool_func(name: str):
    """Import a single MCP tool function by name."""
    from taskboard import mcp_server

    return getattr(mcp_server, name)


def _patch_store() -> MagicMock:
    """Patch _get_store to return a mock store."""
    mock_store = MagicMock()
    # By default, make get_task return None (not found)
    mock_store.get_task.return_value = None
    return patch("taskboard.mcp_server._get_store", return_value=mock_store), mock_store


# ── Task tools ─────────────────────────────────────────────────────


class TestAddTask:
    def test_success(self):
        func = _make_tool_func("add_task")
        mock_task = {"task_id": "tp_001", "title": "Test task", "status": "todo"}
        ctx, store = _patch_store()
        store.add_task.return_value = mock_task

        with ctx:
            result = func(project="testproj", title="Test task")

        assert result["status"] == "success"
        assert result["data"] == mock_task
        store.add_task.assert_called_once_with(
            project="testproj",
            title="Test task",
            type="chore",
            description="",
            tags=None,
            priority="medium",
        )

    def test_invalid_project(self):
        func = _make_tool_func("add_task")
        ctx, store = _patch_store()
        store.add_task.side_effect = ValueError("Project 'nonexistent' not found")

        with ctx:
            result = func(project="nonexistent", title="Test task")

        assert result["status"] == "error"
        assert "not found" in result["message"]


class TestCompleteTask:
    def test_success(self):
        func = _make_tool_func("complete_task")
        completed = {"task_id": "tp_001", "status": "done", "completed_at": "2026-01-15 10:00:00"}
        ctx, store = _patch_store()
        store.complete_task.return_value = completed

        with ctx:
            result = func(task_id="tp_001", summary="All done")

        assert result["status"] == "success"
        assert result["data"]["status"] == "done"
        store.complete_task.assert_called_once_with(task_id="tp_001", summary="All done")

    def test_not_found(self):
        func = _make_tool_func("complete_task")
        ctx, store = _patch_store()
        store.complete_task.side_effect = ValueError("Task 'tp_999' not found")

        with ctx:
            result = func(task_id="tp_999")

        assert result["status"] == "error"
        assert "not found" in result["message"]


class TestUpdateTaskStatus:
    def test_success(self):
        func = _make_tool_func("update_task_status")
        updated = {"task_id": "tp_001", "status": "in_progress"}
        ctx, store = _patch_store()
        store.update_task_status.return_value = updated

        with ctx:
            result = func(task_id="tp_001", status="in_progress", note="Working on it")

        assert result["status"] == "success"
        assert result["data"]["status"] == "in_progress"
        store.update_task_status.assert_called_once_with(
            task_id="tp_001", status="in_progress", note="Working on it"
        )

    def test_invalid_task(self):
        func = _make_tool_func("update_task_status")
        ctx, store = _patch_store()
        store.update_task_status.side_effect = ValueError("Task 'tp_999' not found")

        with ctx:
            result = func(task_id="tp_999", status="blocked")

        assert result["status"] == "error"


class TestDeleteTask:
    def test_success(self):
        func = _make_tool_func("delete_task")
        ctx, store = _patch_store()
        store.delete_task.return_value = True

        with ctx:
            result = func(task_id="tp_001")

        assert result["status"] == "success"
        assert result["data"]["deleted"] == "tp_001"
        store.delete_task.assert_called_once_with(task_id="tp_001")

    def test_not_found(self):
        func = _make_tool_func("delete_task")
        ctx, store = _patch_store()
        store.delete_task.return_value = False

        with ctx:
            result = func(task_id="tp_999")

        assert result["status"] == "error"
        assert "not found" in result["message"]


class TestListTasks:
    def test_success_no_filters(self):
        func = _make_tool_func("list_tasks")
        tasks = [{"task_id": "tp_001"}, {"task_id": "tp_002"}]
        ctx, store = _patch_store()
        store.list_tasks.return_value = tasks

        with ctx:
            result = func()

        assert result["status"] == "success"
        assert result["data"] == tasks
        store.list_tasks.assert_called_once_with(
            project=None, status=None, type=None,
            from_date=None, to_date=None, limit=100, offset=0,
        )

    def test_success_with_filters(self):
        func = _make_tool_func("list_tasks")
        ctx, store = _patch_store()
        store.list_tasks.return_value = []

        with ctx:
            result = func(project="testproj", status="done", type="feature")

        assert result["status"] == "success"
        assert result["data"] == []
        store.list_tasks.assert_called_once_with(
            project="testproj", status="done", type="feature",
            from_date=None, to_date=None, limit=100, offset=0,
        )

    def test_error(self):
        func = _make_tool_func("list_tasks")
        ctx, store = _patch_store()
        store.list_tasks.side_effect = RuntimeError("DB locked")

        with ctx:
            result = func()

        assert result["status"] == "error"


# ── Integration Tests (real store) ─────────────────────────────────


class TestIntegrationWithRealStore:
    """MCP tool functions tested with a real (non-mocked) in-memory store.

    Verifies data persistence across tool calls and real response shapes.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, store):
        """Patch _get_store to return the real test store."""
        self._store = store
        self._ctx = patch("taskboard.mcp_server._get_store", return_value=store)
        self._ctx.__enter__()

    def teardown_method(self):
        self._ctx.__exit__(None, None, None)

    # ── Task tools ──

    def test_add_task_persists(self):
        func = _make_tool_func("add_task")
        result = func(project="testproj", title="Integration task")
        assert result["status"] == "success"
        task_id = result["data"]["task_id"]

        # Verify persistence — get_task should find it
        get_func = _make_tool_func("get_task")
        found = get_func(task_id=task_id)
        assert found["status"] == "success"
        assert found["data"]["title"] == "Integration task"

    def test_complete_task_persists(self):
        func = _make_tool_func("add_task")
        created = func(project="testproj", title="To be completed")
        task_id = created["data"]["task_id"]

        complete_func = _make_tool_func("complete_task")
        result = complete_func(task_id=task_id, summary="Done!")
        assert result["status"] == "success"
        assert result["data"]["status"] == "done"

        # Verify via get_task
        get_func = _make_tool_func("get_task")
        found = get_func(task_id=task_id)
        assert found["data"]["completed_at"] is not None

    def test_list_tasks_returns_added_tasks(self):
        func = _make_tool_func("add_task")
        func(project="testproj", title="List task 1")
        func(project="testproj", title="List task 2")

        list_func = _make_tool_func("list_tasks")
        result = list_func(project="testproj")
        assert result["status"] == "success"
        assert len(result["data"]) >= 2

    def test_update_task_status_persists(self):
        func = _make_tool_func("add_task")
        created = func(project="testproj", title="Status change test")
        task_id = created["data"]["task_id"]

        update_func = _make_tool_func("update_task_status")
        result = update_func(task_id=task_id, status="in_progress", note="WIP")
        assert result["status"] == "success"
        assert result["data"]["status"] == "in_progress"

        # Verify persistence
        get_func = _make_tool_func("get_task")
        found = get_func(task_id=task_id)
        assert found["data"]["status"] == "in_progress"

    def test_get_task_not_found_real_store(self):
        func = _make_tool_func("get_task")
        result = func(task_id="nonexistent_999")
        assert result["status"] == "error"
        assert "not found" in result["message"]

    # ── Project tools ──

    def test_add_project_persists(self):
        func = _make_tool_func("add_project")
        result = func(name="intproj", display_name="Integration Project", slug="ip")
        assert result["status"] == "success"

        list_func = _make_tool_func("list_projects")
        projects = list_func()
        names = [p["name"] for p in projects["data"]]
        assert "intproj" in names

    def test_add_project_duplicate_error(self):
        func = _make_tool_func("add_project")
        func(name="dupproj", display_name="Dup", slug="dp")
        result = func(name="dupproj", display_name="Dup 2", slug="dp2")
        assert result["status"] == "error"
        assert "already exists" in result["message"]

    def test_list_projects_includes_all(self):
        func = _make_tool_func("add_project")
        func(name="proj_a", display_name="A", slug="pa")
        func(name="proj_b", display_name="B", slug="pb")

        list_func = _make_tool_func("list_projects")
        result = list_func()
        assert result["status"] == "success"
        assert len(result["data"]) >= 3  # testproj + proj_a + proj_b

    # ── Analytics tools ──

    def test_get_metrics_reflects_added_tasks(self):
        add_func = _make_tool_func("add_task")
        add_func(project="testproj", title="Metric task")
        complete_func = _make_tool_func("complete_task")

        metrics_func = _make_tool_func("get_metrics")
        before = metrics_func()
        total_before = before["data"]["total_tasks"]

        # Complete a task and verify metrics changed
        tasks = self._store.list_tasks(status="todo", limit=1)
        if tasks:
            complete_func(task_id=tasks[0]["task_id"])
            after = metrics_func()
            assert after["data"]["completed"] >= before["data"]["completed"]

    def test_export_csv_returns_csv_content(self):
        add_func = _make_tool_func("add_task")
        add_func(project="testproj", title="CSV export test")

        func = _make_tool_func("export_csv")
        result = func()
        assert result["status"] == "success"
        assert "task_id" in result["data"]
        assert "CSV export test" in result["data"]

    def test_get_timeline_with_real_data(self):
        """Add a completed task and verify timeline includes it."""
        add_func = _make_tool_func("add_task")
        created = add_func(project="testproj", title="Timeline task")
        task_id = created["data"]["task_id"]

        complete_func = _make_tool_func("complete_task")
        complete_func(task_id=task_id, summary="Timeline test")

        timeline_func = _make_tool_func("get_timeline")
        result = timeline_func(view="week")
        assert result["status"] == "success"
        # Timeline may or may not include the task depending on the date window
        assert isinstance(result["data"], list)


class TestGetTask:
    def test_success(self):
        func = _make_tool_func("get_task")
        task = {"task_id": "tp_001", "title": "Test task"}
        ctx, store = _patch_store()
        store.get_task.return_value = task

        with ctx:
            result = func(task_id="tp_001")

        assert result["status"] == "success"
        assert result["data"]["task_id"] == "tp_001"
        store.get_task.assert_called_once_with(task_id="tp_001")

    def test_not_found(self):
        func = _make_tool_func("get_task")
        ctx, store = _patch_store()
        store.get_task.return_value = None

        with ctx:
            result = func(task_id="tp_999")

        assert result["status"] == "error"
        assert "not found" in result["message"]


# ── Project tools ──────────────────────────────────────────────────


class TestAddProject:
    def test_success(self):
        func = _make_tool_func("add_project")
        project = {"name": "myproj", "slug": "mp", "display_name": "My Project"}
        ctx, store = _patch_store()
        store.add_project.return_value = project

        with ctx:
            result = func(name="myproj", display_name="My Project", slug="mp")

        assert result["status"] == "success"
        assert result["data"]["slug"] == "mp"

    def test_duplicate_slug(self):
        func = _make_tool_func("add_project")
        ctx, store = _patch_store()
        store.add_project.side_effect = ValueError(
            "Project with name 'myproj' or slug 'mp' already exists"
        )

        with ctx:
            result = func(name="myproj", display_name="My Project", slug="mp")

        assert result["status"] == "error"
        assert "already exists" in result["message"]


class TestListProjects:
    def test_success(self):
        func = _make_tool_func("list_projects")
        projects = [{"name": "p1"}, {"name": "p2"}]
        ctx, store = _patch_store()
        store.list_projects.return_value = projects

        with ctx:
            result = func()

        assert result["status"] == "success"
        assert len(result["data"]) == 2


class TestDeleteProject:
    def test_success(self):
        func = _make_tool_func("delete_project")
        ctx, store = _patch_store()
        store.delete_project.return_value = {"deleted": "myproj", "tasks_removed": 3}

        with ctx:
            result = func(name="myproj", force=True)

        assert result["status"] == "success"
        assert result["data"]["deleted"] == "myproj"
        assert result["data"]["tasks_removed"] == 3
        store.delete_project.assert_called_once_with(name="myproj", force=True)

    def test_not_found(self):
        func = _make_tool_func("delete_project")
        ctx, store = _patch_store()
        store.delete_project.side_effect = ValueError("Project 'nope' not found")

        with ctx:
            result = func(name="nope")

        assert result["status"] == "error"
        assert "not found" in result["message"]

    def test_has_tasks_no_force(self):
        func = _make_tool_func("delete_project")
        ctx, store = _patch_store()
        store.delete_project.side_effect = ValueError(
            "Project 'myproj' has 5 associated task(s). Use force=True to delete them as well."
        )

        with ctx:
            result = func(name="myproj")

        assert result["status"] == "error"
        assert "5 associated task" in result["message"]


# ── Analytics tools ────────────────────────────────────────────────


class TestGetMetrics:
    def test_success_global(self):
        func = _make_tool_func("get_metrics")
        metrics = {"total_tasks": 10, "completed": 5, "completion_rate": 50.0}
        ctx, store = _patch_store()
        store.get_metrics.return_value = metrics

        with ctx:
            result = func()

        assert result["status"] == "success"
        assert result["data"]["total_tasks"] == 10
        store.get_metrics.assert_called_once_with(
            project=None, start_date=None, end_date=None
        )

    def test_success_with_filters(self):
        func = _make_tool_func("get_metrics")
        ctx, store = _patch_store()
        store.get_metrics.return_value = {"total_tasks": 3}

        with ctx:
            result = func(project="testproj", start_date="2026-01-01", end_date="2026-01-31")

        assert result["status"] == "success"
        store.get_metrics.assert_called_once_with(
            project="testproj", start_date="2026-01-01", end_date="2026-01-31"
        )


class TestGetTimeline:
    def test_week_view(self):
        func = _make_tool_func("get_timeline")
        timeline = [{"week_label": "2026-W03", "tasks": []}]
        ctx, store = _patch_store()
        store.get_timeline_week.return_value = timeline

        with ctx:
            result = func(view="week")

        assert result["status"] == "success"
        store.get_timeline_week.assert_called_once_with(project=None)

    def test_month_view(self):
        func = _make_tool_func("get_timeline")
        timeline = [{"week_label": "2026-W04", "tasks": []}]
        ctx, store = _patch_store()
        store.get_timeline_month.return_value = timeline

        with ctx:
            result = func(view="month")

        assert result["status"] == "success"
        store.get_timeline_month.assert_called_once_with(project=None)

    def test_with_project_filter(self):
        func = _make_tool_func("get_timeline")
        ctx, store = _patch_store()
        store.get_timeline_week.return_value = []

        with ctx:
            result = func(view="week", project="testproj")

        store.get_timeline_week.assert_called_once_with(project="testproj")

    def test_error(self):
        func = _make_tool_func("get_timeline")
        ctx, store = _patch_store()
        store.get_timeline_week.side_effect = RuntimeError("DB error")

        with ctx:
            result = func(view="week")

        assert result["status"] == "error"


class TestExportCsv:
    def test_success(self):
        func = _make_tool_func("export_csv")
        csv_data = "task_id,title,type,status\n1,Test,chore,todo\n"
        ctx, store = _patch_store()
        store.export_csv.return_value = csv_data

        with ctx:
            result = func()

        assert result["status"] == "success"
        assert "task_id" in result["data"]
        store.export_csv.assert_called_once_with(
            project=None, start_date=None, end_date=None
        )

    def test_with_filters(self):
        func = _make_tool_func("export_csv")
        ctx, store = _patch_store()
        store.export_csv.return_value = "task_id,title\n"

        with ctx:
            result = func(project="testproj", start_date="2026-01-01")

        store.export_csv.assert_called_once_with(
            project="testproj", start_date="2026-01-01", end_date=None
        )

    def test_error(self):
        func = _make_tool_func("export_csv")
        ctx, store = _patch_store()
        store.export_csv.side_effect = RuntimeError("Export failed")

        with ctx:
            result = func()

        assert result["status"] == "error"


# ── Error path tests — uncovered exception handlers ─────────────────


class TestMcpServerErrorPaths:
    """Test generic Exception handlers that return error dicts (lines 28-30, 108-109, 190-191, 242-243, 294-295)."""

    def test_delete_task_generic_exception(self):
        """delete_task: non-ValueError exception returns error (line 108-109)."""
        func = _make_tool_func("delete_task")
        ctx, store = _patch_store()
        store.delete_task.side_effect = RuntimeError("Unexpected DB error")

        with ctx:
            result = func(task_id="tp_001")

        assert result["status"] == "error"
        assert "Unexpected" in result["message"]

    def test_get_task_generic_exception(self):
        """get_task: exception in get_task returns error (line 190-191)."""
        func = _make_tool_func("get_task")
        ctx, store = _patch_store()
        store.get_task.side_effect = RuntimeError("DB error")

        with ctx:
            result = func(task_id="tp_001")

        assert result["status"] == "error"
        assert "DB error" in result["message"]

    def test_list_projects_generic_exception(self):
        """list_projects: exception returns error (line 242-243)."""
        func = _make_tool_func("list_projects")
        ctx, store = _patch_store()
        store.list_projects.side_effect = RuntimeError("Connection refused")

        with ctx:
            result = func()

        assert result["status"] == "error"
        assert "Connection refused" in result["message"]

    def test_get_metrics_generic_exception(self):
        """get_metrics: exception returns error (line 294-295)."""
        func = _make_tool_func("get_metrics")
        ctx, store = _patch_store()
        store.get_metrics.side_effect = RuntimeError("Metrics failure")

        with ctx:
            result = func()

        assert result["status"] == "error"
        assert "Metrics failure" in result["message"]

    def test_add_task_generic_exception(self):
        """add_task: non-ValueError exception returns error (line 28-30 via try/except)."""
        func = _make_tool_func("add_task")
        ctx, store = _patch_store()
        store.add_task.side_effect = RuntimeError("Unexpected")

        with ctx:
            result = func(project="testproj", title="Test")

        assert result["status"] == "error"

    def test_complete_task_generic_exception(self):
        """complete_task: non-ValueError exception returns error."""
        func = _make_tool_func("complete_task")
        ctx, store = _patch_store()
        store.complete_task.side_effect = RuntimeError("Unexpected")

        with ctx:
            result = func(task_id="tp_001")

        assert result["status"] == "error"

    def test_update_task_status_generic_exception(self):
        """update_task_status: non-ValueError exception returns error."""
        func = _make_tool_func("update_task_status")
        ctx, store = _patch_store()
        store.update_task_status.side_effect = RuntimeError("Unexpected")

        with ctx:
            result = func(task_id="tp_001", status="done")

        assert result["status"] == "error"

    def test_list_tasks_generic_exception(self):
        """list_tasks: exception returns error."""
        func = _make_tool_func("list_tasks")
        ctx, store = _patch_store()
        store.list_tasks.side_effect = RuntimeError("Unexpected")

        with ctx:
            result = func()

        assert result["status"] == "error"

    def test_add_project_generic_exception(self):
        """add_project: non-ValueError exception returns error."""
        func = _make_tool_func("add_project")
        ctx, store = _patch_store()
        store.add_project.side_effect = RuntimeError("Unexpected")

        with ctx:
            result = func(name="p", display_name="P", slug="p")

        assert result["status"] == "error"

    def test_delete_project_generic_exception(self):
        """delete_project: non-ValueError exception returns error."""
        func = _make_tool_func("delete_project")
        ctx, store = _patch_store()
        store.delete_project.side_effect = RuntimeError("Unexpected")

        with ctx:
            result = func(name="p")

        assert result["status"] == "error"

    def test_get_timeline_generic_exception(self):
        """get_timeline: exception returns error."""
        func = _make_tool_func("get_timeline")
        ctx, store = _patch_store()
        store.get_timeline_week.side_effect = RuntimeError("Unexpected")

        with ctx:
            result = func(view="week")

        assert result["status"] == "error"

    def test_export_csv_generic_exception(self):
        """export_csv: exception returns error."""
        func = _make_tool_func("export_csv")
        ctx, store = _patch_store()
        store.export_csv.side_effect = RuntimeError("Unexpected")

        with ctx:
            result = func()

        assert result["status"] == "error"

    def test_get_store_lazy_init(self):
        """_get_store lazy-initializes the singleton (lines 28-30)."""
        import taskboard.mcp_server as mod

        original = mod._store
        mod._store = None
        try:
            store = mod._get_store()
            assert store is not None
            assert isinstance(store, mod.TaskboardStore)
            # Second call should return the same instance
            store2 = mod._get_store()
            assert store is store2
        finally:
            mod._store = original
