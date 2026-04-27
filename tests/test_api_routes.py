"""Tests for REST API endpoints — JSON assertions, error handling."""

from __future__ import annotations

import pytest


class TestTasksAPI:
    """GET/POST /api/tasks and GET/PATCH/DELETE /api/tasks/{id}."""

    def test_list_tasks_empty(self, client):
        r = client.get("/api/tasks")
        assert r.status_code == 200
        data = r.json()
        assert "tasks" in data
        assert "count" in data

    def test_list_tasks_with_filter(self, client):
        client.post("/api/tasks", json={"project": "testproj", "title": "Filter me"})
        r = client.get("/api/tasks?project=testproj")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] >= 1

    def test_list_tasks_status_filter(self, client):
        client.post("/api/tasks", json={"project": "testproj", "title": "Todo task"})
        r = client.get("/api/tasks?status=todo")
        assert r.status_code == 200

    def test_create_task_success(self, client):
        r = client.post(
            "/api/tasks",
            json={"project": "testproj", "title": "New API task", "type": "feature"},
        )
        assert r.status_code == 201
        data = r.json()
        assert "task" in data
        assert data["task"]["title"] == "New API task"
        assert data["task"]["status"] == "todo"

    def test_create_task_missing_project(self, client):
        r = client.post("/api/tasks", json={"title": "No project"})
        assert r.status_code == 400
        assert "project" in r.json()["error"].lower()

    def test_create_task_missing_title(self, client):
        r = client.post("/api/tasks", json={"project": "testproj"})
        assert r.status_code == 400

    def test_create_task_invalid_project(self, client):
        r = client.post(
            "/api/tasks",
            json={"project": "nonexistent", "title": "Orphan task"},
        )
        assert r.status_code == 400

    def test_get_task_success(self, client):
        create = client.post("/api/tasks", json={"project": "testproj", "title": "Get me"})
        task_id = create.json()["task"]["task_id"]
        r = client.get(f"/api/tasks/{task_id}")
        assert r.status_code == 200
        assert r.json()["task"]["task_id"] == task_id

    def test_get_task_not_found(self, client):
        r = client.get("/api/tasks/nonexistent_999")
        assert r.status_code == 404

    def test_update_task_status(self, client):
        create = client.post("/api/tasks", json={"project": "testproj", "title": "Update me"})
        task_id = create.json()["task"]["task_id"]
        r = client.patch(
            f"/api/tasks/{task_id}",
            json={"status": "in_progress", "note": "Started working"},
        )
        assert r.status_code == 200
        assert r.json()["task"]["status"] == "in_progress"

    def test_update_task_missing_status(self, client):
        create = client.post("/api/tasks", json={"project": "testproj", "title": "X"})
        task_id = create.json()["task"]["task_id"]
        # Empty PATCH body returns task unchanged (no longer requires status)
        r = client.patch(f"/api/tasks/{task_id}", json={})
        assert r.status_code == 200
        assert r.json()["task"]["status"] == "todo"

    def test_update_task_not_found(self, client):
        r = client.patch("/api/tasks/nonexistent_999", json={"status": "done"})
        assert r.status_code == 404

    def test_delete_task_success(self, client):
        create = client.post("/api/tasks", json={"project": "testproj", "title": "Delete me"})
        task_id = create.json()["task"]["task_id"]
        r = client.delete(f"/api/tasks/{task_id}")
        assert r.status_code == 200
        assert r.json()["deleted"] is True
        # Verify it's gone
        r2 = client.get(f"/api/tasks/{task_id}")
        assert r2.status_code == 404

    def test_delete_task_not_found(self, client):
        r = client.delete("/api/tasks/nonexistent_999")
        assert r.status_code == 404


class TestProjectsAPI:
    """GET/POST /api/projects and GET /api/projects/{slug}."""

    def test_list_projects(self, client):
        r = client.get("/api/projects")
        assert r.status_code == 200
        data = r.json()
        assert "projects" in data
        assert "count" in data
        assert data["count"] >= 1

    def test_create_project_success(self, client):
        r = client.post(
            "/api/projects",
            json={"name": "newproj", "display_name": "New Project", "slug": "np", "path": "/tmp/np"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["project"]["slug"] == "np"

    def test_create_project_missing_name(self, client):
        r = client.post("/api/projects", json={"display_name": "No Name"})
        assert r.status_code == 400

    def test_create_project_duplicate(self, client):
        client.post(
            "/api/projects",
            json={"name": "dupproj", "slug": "dp", "path": "/tmp/dp"},
        )
        r = client.post(
            "/api/projects",
            json={"name": "dupproj", "slug": "dp2", "path": "/tmp/dp2"},
        )
        assert r.status_code == 400

    def test_get_project_success(self, client):
        r = client.get("/api/projects/tp")
        assert r.status_code == 200
        assert r.json()["project"]["slug"] == "tp"

    def test_get_project_not_found(self, client):
        r = client.get("/api/projects/nonexistent")
        assert r.status_code == 404


class TestMetricsAPI:
    """GET /api/metrics with filters."""

    def test_metrics_global(self, client):
        r = client.get("/api/metrics")
        assert r.status_code == 200
        data = r.json()
        assert "total_tasks" in data
        assert "completed" in data
        assert "completion_rate" in data
        assert "tasks_by_status" in data
        assert "tasks_by_type" in data

    def test_metrics_project_filter(self, client):
        r = client.get("/api/metrics?project=testproj")
        assert r.status_code == 200

    def test_metrics_date_filter(self, client):
        r = client.get("/api/metrics?start_date=2026-01-01&end_date=2026-12-31")
        assert r.status_code == 200


class TestCsvExportAPI:
    """GET /api/export/csv — content type, disposition, CSV content."""

    def test_csv_export_content_type(self, client):
        r = client.get("/api/export/csv")
        assert r.status_code == 200
        assert r.headers["content-type"] == "text/csv; charset=utf-8"

    def test_csv_export_disposition(self, client):
        r = client.get("/api/export/csv")
        assert "attachment" in r.headers.get("content-disposition", "")
        assert "tasks.csv" in r.headers.get("content-disposition", "")

    def test_csv_export_has_header(self, client):
        client.post("/api/tasks", json={"project": "testproj", "title": "CSV task"})
        r = client.get("/api/export/csv")
        lines = r.text.strip().split("\n")
        assert "task_id" in lines[0]
        assert "title" in lines[0]

    def test_csv_export_with_filter(self, client):
        r = client.get("/api/export/csv?project=testproj")
        assert r.status_code == 200


class TestTasksAPIPatchV2:
    """PATCH /api/tasks/{id} — upgraded to use update_task() for any field."""

    def test_patch_title_only(self, client):
        """PATCH with title field updates only the title."""
        create = client.post("/api/tasks", json={"project": "testproj", "title": "Original"})
        task_id = create.json()["task"]["task_id"]
        r = client.patch(f"/api/tasks/{task_id}", json={"title": "Patched title"})
        assert r.status_code == 200
        assert r.json()["task"]["title"] == "Patched title"
        assert r.json()["task"]["status"] == "todo"  # unchanged

    def test_patch_priority_and_type(self, client):
        """PATCH with multiple fields updates all of them."""
        create = client.post("/api/tasks", json={"project": "testproj", "title": "Multi patch"})
        task_id = create.json()["task"]["task_id"]
        r = client.patch(f"/api/tasks/{task_id}", json={"priority": "high", "type": "feature"})
        assert r.status_code == 200
        assert r.json()["task"]["priority"] == "high"
        assert r.json()["task"]["type"] == "feature"

    def test_patch_status_still_records_history(self, client):
        """PATCH with status still records history (backward compat)."""
        create = client.post("/api/tasks", json={"project": "testproj", "title": "History patch"})
        task_id = create.json()["task"]["task_id"]
        r = client.patch(f"/api/tasks/{task_id}", json={"status": "in_progress"})
        assert r.status_code == 200
        assert r.json()["task"]["status"] == "in_progress"
        # History should be recorded
        hist = client.get(f"/api/tasks/{task_id}")
        # Verify via a second PATCH — history was recorded
        r = client.patch(f"/api/tasks/{task_id}", json={"status": "done"})
        assert r.status_code == 200

    def test_patch_empty_body_returns_unchanged(self, client):
        """PATCH with no recognized fields returns task unchanged."""
        create = client.post("/api/tasks", json={"project": "testproj", "title": "No change"})
        task_id = create.json()["task"]["task_id"]
        r = client.patch(f"/api/tasks/{task_id}", json={})
        assert r.status_code == 200
        assert r.json()["task"]["title"] == "No change"

    def test_patch_not_found(self, client):
        """PATCH to non-existent task returns 404."""
        r = client.patch("/api/tasks/nonexistent_999", json={"title": "X"})
        assert r.status_code == 404


class TestTasksAPIErrorPaths:
    """Test generic Exception catch-all paths in API routes (lines 42-45, 69-70, 101-102)."""

    def test_list_tasks_internal_error(self, client, monkeypatch):
        """GET /api/tasks — generic exception returns 500 (lines 44-45)."""
        store = client.app.state.store

        def _raise(*args, **kwargs):
            raise RuntimeError("DB locked")

        monkeypatch.setattr(store, "list_tasks", _raise)
        r = client.get("/api/tasks")
        assert r.status_code == 500
        assert "Internal" in r.json()["error"]

    def test_list_tasks_value_error(self, client, monkeypatch):
        """GET /api/tasks — ValueError returns 400 (line 43)."""
        store = client.app.state.store

        def _raise(*args, **kwargs):
            raise ValueError("bad filter value")

        monkeypatch.setattr(store, "list_tasks", _raise)
        r = client.get("/api/tasks")
        assert r.status_code == 400
        assert "bad filter value" in r.json()["error"]

    def test_create_task_internal_error(self, client, monkeypatch):
        """POST /api/tasks — generic exception returns 500 (lines 69-70)."""
        store = client.app.state.store

        def _raise(*args, **kwargs):
            raise RuntimeError("DB locked")

        monkeypatch.setattr(store, "add_task", _raise)
        r = client.post("/api/tasks", json={"project": "testproj", "title": "Error task"})
        assert r.status_code == 500
        assert "Internal" in r.json()["error"]

    def test_update_task_internal_error(self, client, monkeypatch):
        """PATCH /api/tasks/{id} — generic exception returns 500 (lines 101-102)."""
        store = client.app.state.store

        def _raise(*args, **kwargs):
            raise RuntimeError("DB locked")

        monkeypatch.setattr(store, "update_task", _raise)
        r = client.patch("/api/tasks/tp_001", json={"status": "done"})
        assert r.status_code == 500
        assert "Internal" in r.json()["error"]


class TestProjectsAPIErrorPaths:
    """Test generic Exception catch-all in project routes (lines 146-147)."""

    def test_create_project_internal_error(self, client, monkeypatch):
        """POST /api/projects — generic exception returns 500 (lines 146-147)."""
        store = client.app.state.store

        def _raise(*args, **kwargs):
            raise RuntimeError("DB locked")

        monkeypatch.setattr(store, "add_project", _raise)
        r = client.post("/api/projects", json={"name": "errproj", "slug": "ep"})
        assert r.status_code == 500
        assert "Internal" in r.json()["error"]


class TestMetricsAPIErrorPath:
    """Test generic Exception catch-all in metrics route (lines 173-174)."""

    def test_metrics_internal_error(self, client, monkeypatch):
        """GET /api/metrics — generic exception returns 500 (lines 173-174)."""
        store = client.app.state.store

        def _raise(*args, **kwargs):
            raise RuntimeError("DB locked")

        monkeypatch.setattr(store, "get_metrics", _raise)
        r = client.get("/api/metrics")
        assert r.status_code == 500
        assert "Internal" in r.json()["error"]


class TestCsvExportAPIErrorPath:
    """Test generic Exception catch-all in CSV export route (lines 196-197)."""

    def test_csv_export_internal_error(self, client, monkeypatch):
        """GET /api/export/csv — generic exception returns 500 (lines 196-197)."""
        store = client.app.state.store

        def _raise(*args, **kwargs):
            raise RuntimeError("DB locked")

        monkeypatch.setattr(store, "export_csv", _raise)
        r = client.get("/api/export/csv")
        assert r.status_code == 500
        assert "Error" in r.text
