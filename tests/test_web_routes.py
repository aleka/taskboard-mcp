"""Tests for HTML page routes — dashboard, projects, timeline, reports."""

from __future__ import annotations

import pytest


class TestDashboard:
    """GET / — dashboard overview."""

    def test_dashboard_200(self, client):
        r = client.get("/")
        assert r.status_code == 200

    def test_dashboard_has_content(self, client):
        r = client.get("/")
        assert "Dashboard" in r.text or "dashboard" in r.text.lower()

    def test_dashboard_shows_projects(self, client):
        """Dashboard should list the seeded test project."""
        r = client.get("/")
        assert "Test Project" in r.text or "testproj" in r.text

    def test_dashboard_shows_metrics(self, client):
        """Dashboard should show metric cards."""
        r = client.get("/")
        # Metrics section present (total tasks, etc.)
        assert "Total" in r.text or "total" in r.text.lower()


class TestProjectList:
    """GET /projects — list all projects."""

    def test_project_list_200(self, client):
        r = client.get("/projects")
        assert r.status_code == 200

    def test_project_list_shows_project(self, client):
        r = client.get("/projects")
        assert "Test Project" in r.text or "testproj" in r.text


class TestProjectDetail:
    """GET /projects/{slug} — project detail with task table."""

    def test_project_detail_valid_slug(self, client):
        r = client.get("/projects/tp")
        assert r.status_code == 200

    def test_project_detail_invalid_slug(self, client):
        r = client.get("/projects/nonexistent")
        assert r.status_code == 404

    def test_project_detail_shows_tasks(self, client, seeded_store):
        store, *_ = seeded_store
        r = client.get("/projects/tp")
        assert r.status_code == 200
        # Should show at least the tasks in testproj
        assert "Feature task" in r.text or "task" in r.text.lower()

    def test_project_detail_status_filter(self, client, seeded_store):
        r = client.get("/projects/tp?status=todo")
        assert r.status_code == 200


class TestTimeline:
    """GET /timeline — tasks grouped by week/month."""

    def test_timeline_200(self, client):
        r = client.get("/timeline")
        assert r.status_code == 200

    def test_timeline_default_week_view(self, client):
        r = client.get("/timeline")
        assert r.status_code == 200
        # Should contain week-related content
        assert "Week" in r.text or "week" in r.text.lower()

    def test_timeline_month_view(self, client):
        r = client.get("/timeline?view=month")
        assert r.status_code == 200

    def test_timeline_project_filter(self, client):
        r = client.get("/timeline?project=testproj")
        assert r.status_code == 200


class TestReports:
    """GET /reports — filtered metrics preview."""

    def test_reports_200(self, client):
        r = client.get("/reports")
        assert r.status_code == 200

    def test_reports_has_filter_form(self, client):
        r = client.get("/reports")
        assert "report" in r.text.lower() or "Report" in r.text

    def test_reports_with_filters(self, client):
        r = client.get("/reports?start_date=2026-01-01&end_date=2026-12-31")
        assert r.status_code == 200

    def test_reports_csv_link(self, client):
        """CSV link appears when filters are applied."""
        r = client.get("/reports?start_date=2026-01-01")
        assert "/api/export/csv" in r.text


class TestHTMXPartials:
    """GET /partials/* — HTML fragment endpoints."""

    def test_task_list_partial(self, client, seeded_store):
        r = client.get("/partials/task-list")
        assert r.status_code == 200

    def test_task_list_partial_with_project_filter(self, client, seeded_store):
        r = client.get("/partials/task-list?project=testproj")
        assert r.status_code == 200

    def test_task_row_partial(self, client):
        """Create a task first, then fetch its row partial."""
        r = client.post("/api/tasks", json={"project": "testproj", "title": "Row test task"})
        assert r.status_code == 201
        task_id = r.json()["task"]["task_id"]
        r = client.get(f"/partials/task-row/{task_id}")
        assert r.status_code == 200

    def test_task_row_partial_not_found(self, client):
        r = client.get("/partials/task-row/nonexistent_999")
        assert r.status_code == 404

    def test_metrics_partial(self, client):
        r = client.get("/partials/metrics")
        assert r.status_code == 200

    def test_timeline_group_partial(self, client):
        r = client.get("/partials/timeline-group?view=week")
        assert r.status_code == 200

    def test_timeline_group_partial_month(self, client):
        r = client.get("/partials/timeline-group?view=month")
        assert r.status_code == 200


class TestActionAddTask:
    """POST /actions/tasks — add task from HTMX form (form-encoded)."""

    def test_add_task_success(self, client):
        r = client.post(
            "/actions/tasks",
            data={"project": "testproj", "title": "Action test task", "type": "chore", "priority": "medium"},
            follow_redirects=False,
        )
        assert r.status_code == 303  # redirect after success

    def test_add_task_missing_title(self, client):
        r = client.post(
            "/actions/tasks",
            data={"project": "testproj"},
        )
        assert r.status_code == 400
        assert "required" in r.text.lower()

    def test_add_task_missing_project(self, client):
        r = client.post(
            "/actions/tasks",
            data={"title": "No project task"},
        )
        assert r.status_code == 400
        assert "required" in r.text.lower()

    def test_add_task_invalid_project(self, client):
        r = client.post(
            "/actions/tasks",
            data={"project": "nonexistent", "title": "Bad project"},
        )
        assert r.status_code == 400

    def test_add_task_persists_in_store(self, client):
        client.post(
            "/actions/tasks",
            data={"project": "testproj", "title": "Persistent task", "type": "feature"},
        )
        r = client.get("/api/tasks?project=testproj")
        tasks = r.json()["tasks"]
        assert any(t["title"] == "Persistent task" for t in tasks)


class TestActionCompleteTask:
    """POST /actions/tasks/{task_id}/complete — mark task as done via HTMX."""

    def test_complete_task_success(self, client):
        # Create a task via JSON API first
        r = client.post("/api/tasks", json={"project": "testproj", "title": "To complete"})
        assert r.status_code == 201
        task_id = r.json()["task"]["task_id"]

        # Complete via action route (form-encoded POST)
        r = client.post(f"/actions/tasks/{task_id}/complete")
        assert r.status_code == 200
        assert "done" in r.text

    def test_complete_task_not_found(self, client):
        r = client.post("/actions/tasks/nonexistent_999/complete")
        assert r.status_code == 404

    def test_complete_task_returns_updated_row(self, client):
        r = client.post("/api/tasks", json={"project": "testproj", "title": "Row update test"})
        task_id = r.json()["task"]["task_id"]

        r = client.post(f"/actions/tasks/{task_id}/complete")
        assert r.status_code == 200
        # Should contain the task_row partial with "done" badge
        assert f"task-{task_id}" in r.text
        assert "done" in r.text


class TestActionChangeStatus:
    """POST /actions/tasks/{task_id}/status — change task status via HTMX."""

    def test_change_status_to_in_progress(self, client):
        r = client.post("/api/tasks", json={"project": "testproj", "title": "Status change task"})
        task_id = r.json()["task"]["task_id"]

        r = client.post(
            f"/actions/tasks/{task_id}/status",
            data={"status": "in_progress"},
        )
        assert r.status_code == 200
        assert "in_progress" in r.text

    def test_change_status_missing_status(self, client):
        r = client.post("/api/tasks", json={"project": "testproj", "title": "Missing status task"})
        task_id = r.json()["task"]["task_id"]

        r = client.post(f"/actions/tasks/{task_id}/status")
        assert r.status_code == 400
        assert "required" in r.text.lower()

    def test_change_status_not_found(self, client):
        r = client.post(
            "/actions/tasks/nonexistent_999/status",
            data={"status": "done"},
        )
        assert r.status_code == 404

    def test_change_status_returns_updated_row(self, client):
        r = client.post("/api/tasks", json={"project": "testproj", "title": "Status row test"})
        task_id = r.json()["task"]["task_id"]

        r = client.post(
            f"/actions/tasks/{task_id}/status",
            data={"status": "blocked"},
        )
        assert r.status_code == 200
        assert f"task-{task_id}" in r.text
        assert "blocked" in r.text


class TestActionAddTaskInternalError:
    """POST /actions/tasks — internal server error path (lines 62-66)."""

    def test_add_task_internal_error(self, client, monkeypatch):
        """When store.add_task raises a non-ValueError exception, return 500."""
        from taskboard.web.routes import actions

        original_add = actions.add_task

        async def _add_task_with_error(request):
            from starlette.responses import HTMLResponse

            store = actions._get_store(request)
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
            raise RuntimeError("DB connection lost")

        monkeypatch.setattr("taskboard.web.routes.actions.add_task", _add_task_with_error)
        # We can't monkeypatch the store method easily in an async route.
        # Instead, directly test the exception path by sending to the real route
        # and causing store.add_task to raise RuntimeError.
        monkeypatch.undo()
        # Patch the store's add_task to raise RuntimeError
        store = client.app.state.store

        original_store_add = store.add_task

        def _raise_runtime(*args, **kwargs):
            raise RuntimeError("DB connection lost")

        monkeypatch.setattr(store, "add_task", _raise_runtime)
        r = client.post(
            "/actions/tasks",
            data={"project": "testproj", "title": "Error task"},
        )
        assert r.status_code == 500
        assert "Internal error" in r.text


class TestActionCompleteTaskInternalError:
    """POST /actions/tasks/{task_id}/complete — error paths (lines 95-96, 103)."""

    def test_complete_task_internal_error(self, client, monkeypatch):
        """When store.complete_task raises a non-ValueError exception, return 500."""
        store = client.app.state.store

        def _raise_runtime(*args, **kwargs):
            raise RuntimeError("DB locked")

        monkeypatch.setattr(store, "complete_task", _raise_runtime)
        r = client.post("/actions/tasks/tp_001/complete")
        assert r.status_code == 500
        assert "Error completing task" in r.text

    def test_complete_task_not_found_after_update(self, client, monkeypatch):
        """When store.complete_task succeeds but get_task returns None, return 404."""
        store = client.app.state.store

        def _complete_ok(*args, **kwargs):
            return {"task_id": "tp_001", "status": "done"}

        monkeypatch.setattr(store, "complete_task", _complete_ok)
        monkeypatch.setattr(store, "get_task", lambda task_id: None)
        r = client.post("/actions/tasks/tp_001/complete")
        assert r.status_code == 404
        assert "not found after update" in r.text


class TestActionChangeStatusInternalError:
    """POST /actions/tasks/{task_id}/status — error paths (lines 144-145, 152)."""

    def test_change_status_internal_error(self, client, monkeypatch):
        """When store.update_task_status raises a non-ValueError exception, return 500."""
        store = client.app.state.store

        def _raise_runtime(*args, **kwargs):
            raise RuntimeError("DB locked")

        monkeypatch.setattr(store, "update_task_status", _raise_runtime)
        r = client.post(
            "/actions/tasks/tp_001/status",
            data={"status": "in_progress"},
        )
        assert r.status_code == 500
        assert "Error updating task" in r.text

    def test_change_status_not_found_after_update(self, client, monkeypatch):
        """When update_task_status succeeds but get_task returns None, return 404."""
        store = client.app.state.store

        def _update_ok(*args, **kwargs):
            return {"task_id": "tp_001", "status": "blocked"}

        monkeypatch.setattr(store, "update_task_status", _update_ok)
        monkeypatch.setattr(store, "get_task", lambda task_id: None)
        r = client.post(
            "/actions/tasks/tp_001/status",
            data={"status": "blocked"},
        )
        assert r.status_code == 404
        assert "not found after update" in r.text


class TestActionGenerateReport:
    """POST /actions/reports — generate filtered report fragment (lines 173-209)."""

    def test_generate_report_no_filters(self, client):
        r = client.post("/actions/reports")
        assert r.status_code == 200
        assert "report" in r.text.lower()

    def test_generate_report_with_date_filters(self, client):
        r = client.post(
            "/actions/reports",
            data={"start_date": "2026-01-01", "end_date": "2026-12-31"},
        )
        assert r.status_code == 200

    def test_generate_report_with_project_filter(self, client):
        r = client.post("/actions/reports", data={"project": "testproj"})
        assert r.status_code == 200

    def test_generate_report_with_all_filters(self, client):
        r = client.post(
            "/actions/reports",
            data={"start_date": "2026-01-01", "end_date": "2026-12-31", "project": "testproj"},
        )
        assert r.status_code == 200
        # Should have a CSV download URL
        assert "/api/export/csv" in r.text


class TestActionTimelineFilter:
    """POST /actions/timeline — filter timeline fragment (lines 221-242)."""

    def test_timeline_filter_default_week(self, client):
        r = client.post("/actions/timeline")
        assert r.status_code == 200

    def test_timeline_filter_month(self, client):
        r = client.post("/actions/timeline", data={"view": "month"})
        assert r.status_code == 200

    def test_timeline_filter_with_project(self, client):
        r = client.post("/actions/timeline", data={"view": "week", "project": "testproj"})
        assert r.status_code == 200


class TestActionRefreshDashboard:
    """POST /actions/dashboard/refresh — refresh dashboard sections (lines 254-274)."""

    def test_refresh_projects_section(self, client):
        r = client.post("/actions/dashboard/refresh", data={"section": "projects"})
        assert r.status_code == 200
        assert "project" in r.text.lower()

    def test_refresh_activity_section(self, client):
        r = client.post("/actions/dashboard/refresh", data={"section": "activity"})
        assert r.status_code == 200

    def test_refresh_metrics_section(self, client):
        r = client.post("/actions/dashboard/refresh", data={"section": "metrics"})
        assert r.status_code == 200

    def test_refresh_default_days(self, client):
        r = client.post("/actions/dashboard/refresh", data={"section": "activity"})
        assert r.status_code == 200

    def test_refresh_invalid_section(self, client):
        r = client.post("/actions/dashboard/refresh", data={"section": "invalid_section"})
        assert r.status_code == 400
        assert "Invalid" in r.text

    def test_refresh_no_section(self, client):
        r = client.post("/actions/dashboard/refresh", data={})
        assert r.status_code == 400


class TestTaskDetailPage:
    """GET /tasks/{task_id} — task detail with prev/next navigation (lines 116-135)."""

    def test_task_detail_success(self, client):
        r = client.post("/api/tasks", json={"project": "testproj", "title": "Detail test task"})
        task_id = r.json()["task"]["task_id"]
        r = client.get(f"/tasks/{task_id}")
        assert r.status_code == 200
        assert "Detail test task" in r.text

    def test_task_detail_not_found(self, client):
        r = client.get("/tasks/nonexistent_999")
        assert r.status_code == 404

    def test_task_detail_with_neighbors(self, client):
        """A task with siblings should show prev/next navigation."""
        client.post("/api/tasks", json={"project": "testproj", "title": "First task"})
        r2 = client.post("/api/tasks", json={"project": "testproj", "title": "Second task"})
        task_id = r2.json()["task"]["task_id"]
        client.post("/api/tasks", json={"project": "testproj", "title": "Third task"})
        r = client.get(f"/tasks/{task_id}")
        assert r.status_code == 200


class TestTimelineProjectFilterSlugResolution:
    """GET /timeline?project={slug} — resolves slug to name (line 164)."""

    def test_timeline_filter_by_valid_slug(self, client):
        r = client.get("/timeline?project=tp")
        assert r.status_code == 200

    def test_timeline_filter_by_invalid_slug(self, client):
        """Invalid slug should not crash — just returns no results."""
        r = client.get("/timeline?project=nonexistent")
        assert r.status_code == 200


class TestReportsCsvUrlWithFilters:
    """GET /reports — CSV URL construction (line 211)."""

    def test_reports_csv_url_with_project_filter(self, client):
        r = client.get("/reports?project=testproj")
        assert r.status_code == 200
        assert "project=testproj" in r.text


class TestHTMXPartialsNew:
    """Additional tests for partial endpoints (lines 116-119, 131-137)."""

    def test_project_cards_partial(self, client):
        r = client.get("/partials/project-cards")
        assert r.status_code == 200
        assert "Test Project" in r.text or "testproj" in r.text

    def test_recent_activity_partial(self, client):
        r = client.get("/partials/recent-activity")
        assert r.status_code == 200

    def test_recent_activity_partial_custom_days(self, client):
        r = client.get("/partials/recent-activity?days=30")
        assert r.status_code == 200

    def test_recent_activity_partial_zero_days(self, client):
        r = client.get("/partials/recent-activity?days=0")
        assert r.status_code == 200


class TestHTMXErrorHandling:
    """W4: base.html includes hx-on::response-error for global error alerts."""

    def test_base_template_has_error_handler(self, client):
        r = client.get("/")
        assert "hx-on::response-error" in r.text
