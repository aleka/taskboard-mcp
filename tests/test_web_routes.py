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


class TestHTMXErrorHandling:
    """W4: base.html includes hx-on::response-error for global error alerts."""

    def test_base_template_has_error_handler(self, client):
        r = client.get("/")
        assert "hx-on::response-error" in r.text
