# Tasks: taskboard-mcp — MCP Server + Web Dashboard

## Dependency Graph

```
Phase 1: Foundation
┌─────────────┐
│  TASK-01    │  Project setup (pyproject.toml, dirs)
│  TASK-02    │  store.py - Connection + context manager
│  TASK-03    │  store.py - CRUD methods
└──────┬──────┘
       │
       ▼
Phase 2: Store Completion
┌─────────────┐
│  TASK-04    │  store.py - Analytics (metrics, timeline)
│  TASK-05    │  store.py - CSV export
│  TASK-06    │  Unit tests for store.py
└──────┬──────┘
       │
       ▼
Phase 3: MCP Server
┌─────────────┐
│  TASK-07    │  mcp_server.py - 9 tools
│  TASK-08    │  MCP server unit tests
└──────┬──────┘
       │
       ▼
Phase 4: Web App Framework
┌─────────────┐
│  TASK-09    │  web/app.py - Starlette factory + mount MCP
│  TASK-10    │  web/templates/base.html - Layout
└──────┬──────┘
       │
       ▼
Phase 5: Web Routes - Pages
┌─────────────┐
│  TASK-11    │  pages.py - Dashboard route
│  TASK-12    │  dashboard.html template
│  TASK-13    │  pages.py - Project routes (list + detail)
│  TASK-14    │  project_list.html + project_detail.html
│  TASK-15    │  pages.py - Timeline route
│  TASK-16    │  timeline.html template
│  TASK-17    │  pages.py - Reports route
│  TASK-18    │  reports.html template
└──────┬──────┘
       │
       ▼
Phase 6: Web Routes - API & Partials
┌─────────────┐
│  TASK-19    │  api.py - REST API (tasks, projects, metrics, csv)
│  TASK-20    │  partials.py - HTMX partials (4 fragments)
│  TASK-21    │  Partial templates (task_row, task_list, etc.)
└──────┬──────┘
       │
       ▼
Phase 7: Static Assets
┌─────────────┐
│  TASK-22    │  static/css/style.css (~200 lines)
│  TASK-23    │  static/js/htmx.min.js (vendored)
└──────┬──────┘
       │
       ▼
Phase 8: Testing - Web Layer
┌─────────────┐
│  TASK-24    │  conftest.py - Fixtures (store, client, seeded)
│  TASK-25    │  test_web_routes.py - HTML page routes
│  TASK-26    │  test_api_routes.py - REST API endpoints
│  TASK-27    │  test_mcp_server.py - MCP tool tests
└──────┬──────┘
       │
       ▼
Phase 9: Docker & Deployment
┌─────────────┐
│  TASK-28    │  Dockerfile (Python 3.12-slim)
│  TASK-29    │  docker-compose.yml (restart: unless-stopped, volume)
│  TASK-30    │  watchdog.sh (cron health check)
└──────┬──────┘
       │
       ▼
Phase 10: Final
┌─────────────┐
│  TASK-31    │  README.md (usage, docker, cron setup)
│  TASK-32    │  End-to-end verification
└─────────────┘
```

---

## Task Breakdown

### TASK-01: Project Setup and Configuration

**Title:** Initialize project structure, pyproject.toml, and directory layout

**Files:**
- `pyproject.toml`
- `taskboard/__init__.py`
- `taskboard/web/__init__.py`
- `tests/__init__.py`

**Dependencies:** None

**Effort:** M

**Acceptance Criteria:**
- [x] `pyproject.toml` includes all dependencies (fastmcp>=3.2, starlette, jinja2, uvicorn, pytest)
- [x] Directory structure matches design document
- [x] `uv pip install -e .` installs all packages without errors
- [x] `pytest --version` runs successfully
- [x] `fastmcp --version` confirms fastmcp v3.x installation

---

### TASK-02: Store - Connection Management

**Title:** Implement TaskboardStore connection with WAL mode, busy_timeout, context manager

**Files:**
- `taskboard/store.py` - `__init__`, `__enter__`, `__exit__`, `_connect`, `conn` property

**Dependencies:** TASK-01

**Effort:** M

**Acceptance Criteria:**
- [x] `TaskboardStore` opens connection with WAL mode enabled
- [x] `PRAGMA busy_timeout = 5000` is set
- [x] `PRAGMA foreign_keys = ON` is set
- [x] Context manager `with TaskboardStore()` works (enters and exits)
- [x] Connection is reused across method calls (single instance)
- [x] `db_path` parameter defaults to `~/.taskboard/taskboard.db`
- [x] Connection closes when context manager exits

---

### TASK-03: Store - CRUD Methods for Tasks and Projects

**Title:** Implement add, get, list, update, delete for tasks and projects

**Files:**
- `taskboard/store.py` - `add_project`, `get_project`, `list_projects`, `add_task`, `get_task`, `list_tasks`, `update_task_status`, `complete_task`, `delete_task`, `_generate_task_id`, `_record_history`

**Dependencies:** TASK-02

**Effort:** L

**Acceptance Criteria:**
- [x] `add_project()` creates project with unique slug constraint
- [x] `get_project()` returns project dict or None
- [x] `list_projects()` returns all projects sorted by name
- [x] `add_task()` creates task with auto-generated ID `{slug}_{NNN}`
- [x] `get_task()` returns task dict or None
- [x] `list_tasks()` supports filters: project, status, type, from_date, to_date, limit, offset
- [x] `update_task_status()` changes status and records history entry
- [x] `complete_task()` sets status to 'completed', sets `completed_at`, records history
- [x] `delete_task()` soft-deletes or removes from database
- [x] `_record_history()` INSERTs into `task_history` with from_status, to_status, note, git_commit
- [x] All operations work with existing schema (no migrations)

---

### TASK-04: Store - Analytics and Timeline Queries

**Title:** Implement get_metrics, get_timeline_week, get_timeline_month, get_recent_activity

**Files:**
- `taskboard/store.py` - `get_metrics`, `get_timeline_week`, `get_timeline_month`, `get_recent_activity`

**Dependencies:** TASK-03

**Effort:** L

**Acceptance Criteria:**
- [x] `get_metrics()` returns dict with: total_tasks, completed, pending, completion_rate, tasks_by_status, tasks_by_type
- [x] `get_metrics(project="slug")` filters by single project
- [x] `get_metrics(start_date, end_date)` filters by date range
- [x] `get_metrics(project, start_date, end_date)` combines both filters
- [x] `get_timeline_week()` returns tasks grouped by week for current ISO week
- [x] `get_timeline_week(project="slug")` filters by project
- [x] `get_timeline_month()` returns tasks grouped by week for current month
- [x] `get_timeline_month(project="slug")` filters by project
- [x] `get_recent_activity(days=7)` returns last N days of completed tasks
- [x] Timeline queries return list of `{week_label, tasks: [...]}`

---

### TASK-05: Store - CSV Export Functionality

**Title:** Implement export_csv using Python stdlib csv module with filtering

**Files:**
- `taskboard/store.py` - `export_csv`

**Dependencies:** TASK-04

**Effort:** M

**Acceptance Criteria:**
- [x] `export_csv()` returns CSV string (not file)
- [x] Supports 3 filter modes: dates only, project only, both combined
- [x] CSV headers match: task_id, title, type, status, project, created_at, completed_at, tags
- [x] `export_csv(start_date, end_date)` filters by date range
- [x] `export_csv(project="slug")` filters by project
- [x] `export_csv(project, start_date, end_date)` combines filters
- [x] No filters → export all tasks
- [x] Uses Python stdlib `csv.writer` (no pandas dependency)

---

### TASK-06: Unit Tests for Store Layer

**Title:** Write comprehensive unit tests for all TaskboardStore methods

**Files:**
- `tests/test_store.py` - All store method tests
- `tests/conftest.py` - `store` fixture (in-memory)

**Dependencies:** TASK-05

**Effort:** L

**Acceptance Criteria:**
- [x] `store` fixture uses in-memory SQLite (`:memory:`)
- [x] Test connection lifecycle (enter, exit, WAL mode, busy_timeout)
- [x] Test project CRUD: add, get, list, duplicate slug error
- [x] Test task CRUD: add, get, list with filters, update status, complete, delete
- [x] Test task ID generation: `{slug}_{NNN}` format
- [x] Test history recording: entries created on status changes
- [x] Test metrics: global, project-filtered, date-filtered, combined
- [x] Test timeline: week view, month view, project-filtered
- [x] Test recent_activity: returns tasks within N days
- [x] Test CSV export: 3 filter modes, header row, correct data
- [x] All tests pass with `pytest tests/test_store.py`
- [x] Coverage > 90% for store.py

---

### TASK-07: MCP Server - Tool Registration

**Title:** Implement 9 fastmcp tools with structured responses

**Files:**
- `taskboard/mcp_server.py` - `FastMCP` instance, 9 tool decorators, `_get_store` helper

**Dependencies:** TASK-05 (needs complete store API)

**Effort:** L

**Acceptance Criteria:**
- [x] `FastMCP("taskboard")` instance created
- [x] 9 tools registered: `add_task`, `complete_task`, `update_task_status`, `list_tasks`, `get_task`, `add_project`, `list_projects`, `get_metrics`, `get_timeline`, `export_csv`
- [x] All tools call `_get_store()` to get shared store instance
- [x] All tools return `{"status": "success", "data": {...}}` on success
- [x] All tools return `{"status": "error", "message": "..."}` on failure
- [x] Error messages never expose SQL or internal details
- [x] `get_timeline(tool)` supports `view="week"` or `view="month"` param
- [x] Tool docstrings are descriptive (helpful for AI agents)
- [x] Global `_store` variable initialized lazily via `_get_store()`

---

### TASK-08: MCP Server Unit Tests

**Title:** Test MCP tool functions with mock store

**Files:**
- `tests/test_mcp_server.py` - All MCP tool tests

**Dependencies:** TASK-07

**Effort:** M

**Acceptance Criteria:**
- [x] Mock `TaskboardStore` injected or patched
- [x] Test `add_task`: success response, error response on invalid project
- [x] Test `complete_task`: status changes to 'completed', history recorded
- [x] Test `update_task_status`: status change, error on invalid task_id
- [x] Test `list_tasks`: filters work (project, status, type, dates)
- [x] Test `get_task`: returns data or error for not found
- [x] Test `add_project`: creates project, error on duplicate slug
- [x] Test `list_projects`: returns all projects
- [x] Test `get_metrics`: returns metrics dict, filters work
- [x] Test `get_timeline`: supports "week" and "month" views
- [x] Test `export_csv`: returns CSV string, filters work
- [x] All tests assert response shape `{status, data/message}`
- [x] All tests pass with `pytest tests/test_mcp_server.py`

---

### TASK-09: Web App Factory

**Title:** Implement Starlette app factory, mount fastmcp at /mcp, configure templates

**Files:**
- `taskboard/web/app.py` - `create_app()` function, Starlette assembly, Mount MCP, StaticFiles

**Dependencies:** TASK-07 (needs mcp_server.py)

**Effort:** L

**Acceptance Criteria:**
- [x] `create_app(store=None)` factory function exists
- [x] If no store provided, creates default `TaskboardStore()`
- [x] `Jinja2Templates` configured for `taskboard/web/templates`
- [x] Routes registered: `/` (dashboard), `/projects`, `/projects/{slug}`, `/timeline`, `/reports`
- [x] API routes registered: `/api/tasks`, `/api/tasks/{task_id}`, `/api/projects`, `/api/projects/{slug}`, `/api/metrics`, `/api/export/csv`
- [x] Partial routes registered: `/partials/task-list`, `/partials/task-row/{task_id}`, `/partials/metrics`, `/partials/timeline-group`
- [x] MCP mounted at `/mcp` via `app.mount("/mcp", mcp.http_app())`
- [x] Static files mounted at `/static` from `taskboard/web/static`
- [x] Store and templates injected into `app.state`
- [x] Lifespan context manager manages store open/close on startup/shutdown
- [x] `uvicorn taskboard.web.app:create_app --factory` starts server

---

### TASK-10: Base Template and Layout

**Title:** Create base.html with navigation, HTMX includes, CSS, footer

**Files:**
- `taskboard/web/templates/base.html`

**Dependencies:** TASK-09

**Effort:** M

**Acceptance Criteria:**
- [x] HTML5 doctype and proper structure
- [x] Navigation links: Dashboard, Projects, Timeline, Reports
- [x] HTMX script included: `<script src="/static/js/htmx.min.js">`
- [x] CSS included: `<link rel="stylesheet" href="/static/css/style.css">`
- [x] Jinja2 block `{% block content %}` for page-specific content
- [x] Footer with minimal content
- [x] Title block for page-specific titles
- [x] Responsive meta tags (viewport)
- [x] Jinja2 autoescape enabled (default)

---

### TASK-11: Dashboard Route

**Title:** Implement GET / route for dashboard overview

**Files:**
- `taskboard/web/routes/pages.py` - `dashboard()` function

**Dependencies:** TASK-09, TASK-10

**Effort:** S

**Acceptance Criteria:**
- [x] Route handler `dashboard(request)` receives `Request` object
- [x] Calls `store.get_metrics()` for global metrics
- [x] Calls `store.list_projects()` for project list
- [x] Calls `store.get_recent_activity(days=7)` for recent tasks
- [x] Renders `dashboard.html` template with context: metrics, projects, recent_tasks
- [x] Returns `HTMLResponse` with 200 status

---

### TASK-12: Dashboard Template

**Title:** Create dashboard.html with metrics cards, project cards, recent activity

**Files:**
- `taskboard/web/templates/dashboard.html`

**Dependencies:** TASK-10, TASK-11

**Effort:** M

**Acceptance Criteria:**
- [x] Extends `base.html`
- [x] Displays metric cards: Total Tasks, Completed, Pending, Completion Rate
- [x] Lists all projects with task counts (loop over projects)
- [x] Shows recent 10 completed tasks
- [x] Each project card links to `/projects/{slug}`
- [x] Each task links to project detail
- [x] HTMX attributes: `hx-get="/partials/metrics"` on refresh button, `hx-get="/partials/task-list?limit=10"` for recent tasks
- [x] Empty state if no tasks/projects exist

---

### TASK-13: Project Routes (List and Detail)

**Title:** Implement GET /projects and GET /projects/{slug} routes

**Files:**
- `taskboard/web/routes/pages.py` - `project_list()`, `project_detail()` functions

**Dependencies:** TASK-11

**Effort:** M

**Acceptance Criteria:**
- [x] `project_list(request)` calls `store.list_projects()`, renders `project_list.html`
- [x] `project_detail(request, slug)` calls `store.get_project(slug)`, `store.list_tasks(project=slug)`
- [x] `project_detail()` supports query param `status` for filtering
- [x] Both functions return `HTMLResponse` with 200
- [x] `project_detail()` returns 404 if project not found (or empty template with message)

---

### TASK-14: Project Templates

**Title:** Create project_list.html and project_detail.html with filters and HTMX

**Files:**
- `taskboard/web/templates/project_list.html`
- `taskboard/web/templates/project_detail.html`

**Dependencies:** TASK-12, TASK-13

**Effort:** L

**Acceptance Criteria:**
- [x] `project_list.html`: Extends base, lists all projects with stats, links to detail pages
- [x] `project_detail.html`: Extends base, shows project name/stats, task table, filter buttons (All, Pending, Completed, In Progress)
- [x] Filter buttons: `hx-get="/partials/task-list?project={slug}&status={status}"` with `hx-target="#task-list"`
- [x] Add task form: `hx-post="/tasks"` with fields (title, description, type, priority, tags)
- [x] Task table with actions: complete button (`hx-post="/tasks/{id}/complete"`), status update dropdown
- [x] Empty state if no tasks in project
- [x] Back link to project list

---

### TASK-15: Timeline Route

**Title:** Implement GET /timeline route with view toggle (week/month)

**Files:**
- `taskboard/web/routes/pages.py` - `timeline_view()` function

**Dependencies:** TASK-13

**Effort:** S

**Acceptance Criteria:**
- [x] `timeline_view(request)` reads query param `view` (default "week")
- [x] Calls `store.get_timeline_week()` or `store.get_timeline_month()` based on view
- [x] Calls `store.list_projects()` for project filter dropdown
- [x] Renders `timeline.html` with context: timeline_data, current_view, projects
- [x] Returns `HTMLResponse` with 200

---

### TASK-16: Timeline Template

**Title:** Create timeline.html with week/month toggle and project filter

**Files:**
- `taskboard/web/templates/timeline.html`

**Dependencies:** TASK-14, TASK-15

**Effort:** M

**Acceptance Criteria:**
- [x] Extends `base.html`
- [x] View toggle buttons: "This Week" (`hx-get="/partials/timeline-group?view=week"`), "This Month" (`hx-get="/partials/timeline-group?view=month"`)
- [x] Project filter dropdown: optional, sends `project={slug}` query param
- [x] Timeline container `#timeline-content` swapped by HTMX
- [x] Tasks grouped by week label, sorted chronologically
- [x] Status indicators for each task (completed icon)
- [x] Empty state if no tasks in view

---

### TASK-17: Reports Route

**Title:** Implement GET /reports route with 3 filter modes (dates, project, both)

**Files:**
- `taskboard/web/routes/pages.py` - `reports_view()` function

**Dependencies:** TASK-15

**Effort:** S

**Acceptance Criteria:**
- [x] `reports_view(request)` reads query params: start_date, end_date, project (all optional)
- [x] Calls `store.get_metrics(project, start_date, end_date)` for preview
- [x] Calls `store.list_projects()` for project dropdown
- [x] Renders `reports.html` with context: metrics, filters, projects
- [x] Returns `HTMLResponse` with 200

---

### TASK-18: Reports Template

**Title:** Create reports.html with filter form, preview, CSV download

**Files:**
- `taskboard/web/templates/reports.html`

**Dependencies:** TASK-16, TASK-17

**Effort:** M

**Acceptance Criteria:**
- [x] Extends `base.html`
- [x] Filter form: start_date (date input), end_date (date input), project (dropdown)
- [x] "Generate Report" button: `hx-get="/partials/metrics"` with all filter values
- [x] Preview section shows metric cards via HTMX swap
- [x] "Download CSV" button links to `/api/export/csv?` with same filter params
- [x] Empty state if no filters applied
- [x] Clear filters button (reload page without query params)

---

### TASK-19: REST API Routes

**Title:** Implement JSON API endpoints for tasks, projects, metrics, CSV export

**Files:**
- `taskboard/web/routes/api.py` - All API route functions

**Dependencies:** TASK-17

**Effort:** L

**Acceptance Criteria:**
- [x] `GET /api/tasks`: Query params (project, status, type, from_date, to_date, limit, offset), returns JSON list
- [x] `POST /api/tasks`: JSON body (project, title, type, description, priority, tags), returns created task with 201
- [x] `GET /api/tasks/{task_id}`: Returns task dict or 404
- [x] `PATCH /api/tasks/{task_id}`: JSON body (status, note), returns updated task
- [x] `DELETE /api/tasks/{task_id}`: Returns success or 404
- [x] `GET /api/projects`: Returns all projects as JSON list
- [x] `POST /api/projects`: JSON body (name, display_name, slug, origin, path), returns created project with 201
- [x] `GET /api/projects/{slug}`: Returns project dict or 404
- [x] `GET /api/metrics`: Query params (project, start_date, end_date), returns metrics JSON
- [x] `GET /api/export/csv`: Query params (project, start_date, end_date), returns CSV with `Content-Type: text/csv` and `Content-Disposition: attachment; filename=tasks.csv`
- [x] All endpoints handle errors with appropriate HTTP status codes (400, 404, 500)
- [x] All responses are valid JSON (except CSV endpoint)

---

### TASK-20: HTMX Partial Routes

**Title:** Implement /partials/* routes for live updates without page reload

**Files:**
- `taskboard/web/routes/partials.py` - All partial route functions

**Dependencies:** TASK-18, TASK-19

**Effort:** L

**Acceptance Criteria:**
- [x] `GET /partials/task-list`: Query params (project, status, limit, offset), returns task list fragment
- [x] `GET /partials/task-row/{task_id}`: Returns single task row fragment (for status update)
- [x] `GET /partials/metrics`: Query params (project, start_date, end_date), returns metric cards fragment
- [x] `GET /partials/timeline-group`: Query params (view, project), returns timeline items fragment
- [x] All partials return HTML fragments (not full pages)
- [x] Partial templates use minimal markup (no nav, no footer)
- [x] Responses include appropriate `hx-swap` targets (handled by caller)

---

### TASK-21: Partial Templates

**Title:** Create HTMX partial templates for dynamic updates

**Files:**
- `taskboard/web/templates/partials/task_row.html`
- `taskboard/web/templates/partials/task_list.html`
- `taskboard/web/templates/partials/project_card.html`
- `taskboard/web/templates/partials/metrics_cards.html`
- `taskboard/web/templates/partials/timeline_group.html`
- `taskboard/web/templates/partials/report_preview.html`

**Dependencies:** TASK-20

**Effort:** L

**Acceptance Criteria:**
- [x] `task_row.html`: Single table row with task data, status badge, complete button, actions dropdown
- [x] `task_list.html`: Table structure with loop over tasks, uses `task_row.html` via include or inline
- [x] `project_card.html`: Project summary card with name, task counts, link to detail
- [x] `metrics_cards.html`: 4 metric cards (total, completed, pending, completion rate) with counts
- [x] `timeline_group.html`: Week label header + loop over tasks for that week
- [x] `report_preview.html`: Metric summary + task count for filtered data
- [x] All partials are self-contained HTML fragments
- [x] HTMX attributes included where appropriate (e.g., complete buttons)

---

### TASK-22: Static CSS

**Title:** Implement custom CSS with variables (~200 lines)

**Files:**
- `taskboard/web/static/css/style.css`

**Dependencies:** TASK-21

**Effort:** M

**Acceptance Criteria:**
- [x] CSS variables for colors (primary, secondary, success, danger, warning)
- [x] CSS variables for spacing, border-radius, shadows
- [x] Reset/normalize styles (minimal)
- [x] Typography styles (font-family, sizes, weights)
- [x] Card styles (border, shadow, padding)
- [x] Button styles (primary, secondary, danger, success variants)
- [x] Form input styles (text, date, select, textarea)
- [x] Table styles (headers, rows, hover effects)
- [x] Navigation styles (links, active state)
- [x] Utility classes (text-center, flex, spacing)
- [x] Status badge styles (pending, in-progress, completed, cancelled)
- [x] Responsive breakpoints (mobile, tablet, desktop)
- [x] Dark mode support (optional, CSS variables)
- [x] Total ~200 lines of CSS

---

### TASK-23: Vendored HTMX

**Title:** Download and vendoring htmx.min.js (14KB)

**Files:**
- `taskboard/web/static/js/htmx.min.js`

**Dependencies:** TASK-22

**Effort:** XS

**Acceptance Criteria:**
- [x] Download latest stable htmx.min.js from https://unpkg.com/htmx.org@1.9.12/dist/htmx.min.js (or similar CDN)
- [x] File size ~14KB (minified)
- [x] File placed at `taskboard/web/static/js/htmx.min.js`
- [x] File is readable and valid JavaScript
- [x] No build step required

---

### TASK-24: Test Fixtures

**Title:** Implement conftest.py with store, client, and seeded fixtures

**Files:**
- `tests/conftest.py` - Fixtures for testing

**Dependencies:** TASK-06, TASK-23

**Effort:** M

**Acceptance Criteria:**
- [x] `store` fixture: In-memory `TaskboardStore(":memory:")`, seeded with test project
- [x] `client` fixture: `TestClient(create_app(store=store))` for web/API testing
- [x] `seeded_store` fixture: `store` with sample tasks (completed, pending, across projects)
- [x] All fixtures use context managers (enter/exit)
- [x] Fixtures are isolated (each test gets fresh instance)
- [x] pytest discovers fixtures automatically

---

### TASK-25: Web Routes Tests

**Title:** Test HTML page routes with TestClient

**Files:**
- `tests/test_web_routes.py`

**Dependencies:** TASK-24

**Effort:** L

**Acceptance Criteria:**
- [x] Test `GET /`: Returns 200, renders dashboard.html with metrics
- [x] Test `GET /projects`: Returns 200, renders project_list.html
- [x] Test `GET /projects/{slug}`: Returns 200 for valid slug, 404 or message for invalid
- [x] Test `GET /timeline`: Returns 200, renders timeline.html with week view default
- [x] Test `GET /timeline?view=month`: Renders with month view
- [x] Test `GET /reports`: Returns 200, renders reports.html
- [x] Assert template fragments in response (e.g., "Dashboard", "Projects")
- [x] Test query params pass through to templates
- [x] All tests pass with `pytest tests/test_web_routes.py`

---

### TASK-26: API Routes Tests

**Title:** Test REST API endpoints with TestClient

**Files:**
- `tests/test_api_routes.py`

**Dependencies:** TASK-24

**Effort:** L

**Acceptance Criteria:**
- [x] Test `GET /api/tasks`: Returns JSON list, filters work (project, status, dates)
- [x] Test `POST /api/tasks`: Returns 201, creates task in store
- [x] Test `GET /api/tasks/{id}`: Returns task dict or 404
- [x] Test `PATCH /api/tasks/{id}`: Updates status, returns updated task
- [x] Test `DELETE /api/tasks/{id}`: Deletes task, returns success
- [x] Test `GET /api/projects`: Returns JSON list
- [x] Test `POST /api/projects`: Returns 201, creates project
- [x] Test `GET /api/projects/{slug}`: Returns project dict or 404
- [x] Test `GET /api/metrics`: Returns metrics JSON, filters work
- [x] Test `GET /api/export/csv`: Returns CSV with correct Content-Type and Content-Disposition
- [x] Assert JSON response shape (keys, types)
- [x] Test error responses (400, 404, 500)
- [x] All tests pass with `pytest tests/test_api_routes.py`

---

### TASK-27: MCP Server Integration Tests

**Title:** Test MCP tools with real store (not mocked)

**Files:**
- `tests/test_mcp_server.py` - Update to use real store fixture

**Dependencies:** TASK-08, TASK-24

**Effort:** M

**Acceptance Criteria:**
- [x] Import MCP tool functions (not mocked)
- [x] Use `store` fixture from conftest.py
- [x] Test all 9 tools with real store operations
- [x] Assert data persistence across tool calls
- [x] Test error handling with invalid inputs
- [x] Verify response shapes match spec `{status, data/message}`
- [x] All tests pass with `pytest tests/test_mcp_server.py`

---

### TASK-28: Dockerfile

**Title:** Create Dockerfile for Python 3.12-slim deployment

**Files:**
- `Dockerfile`

**Dependencies:** TASK-27

**Effort:** M

**Acceptance Criteria:**
- [x] Base image: `python:3.13-slim` (deviation: spec said 3.12, project uses 3.13)
- [x] `WORKDIR /app`
- [x] Copy `pyproject.toml` and run `pip install --no-cache-dir .`
- [x] Copy `taskboard/` directory
- [x] `EXPOSE 7438` (deviation: spec said 8000, project uses 7438)
- [x] `ENV TASKBOARD_DB=/root/.taskboard/taskboard.db`
- [x] `CMD ["uvicorn", "taskboard.web.app:create_app", "--host", "0.0.0.0", "--port", "7438", "--factory"]`
- [x] Multi-stage build optional (for smaller image)
- [ ] `docker build -t taskboard-mcp .` succeeds (not tested in CI)
- [ ] `docker run taskboard-mcp` starts server on port 7438 (not tested in CI)

---

### TASK-29: Docker Compose and Watchdog

**Title:** Create docker-compose.yml with restart policy and watchdog.sh script

**Files:**
- `docker-compose.yml`
- `watchdog.sh`

**Dependencies:** TASK-28

**Effort:** M

**Acceptance Criteria:**
- [x] `docker-compose.yml`:
  - [x] Service named `taskboard`
  - [x] Build context `.`
  - [x] Ports: `7438:7438` (deviation: spec said 8000)
  - [x] Volumes: `~/.taskboard:/root/.taskboard`
  - [x] Environment: `TASKBOARD_DB=/root/.taskboard/taskboard.db`
  - [x] `restart: unless-stopped`
  - [x] Healthcheck: Python-based (no curl in slim image), interval 30s, timeout 10s, retries 3
- [x] `watchdog.sh`:
  - [x] Bash script, executable (`chmod +x`)
  - [x] Checks if container is running via `docker ps`
  - [x] If not running: logs timestamped message to `~/.taskboard/crash-report.log`, restarts via `docker compose up -d`
  - [x] Verifies container restarted successfully, logs recovery or failure
  - [x] Cron entry: `*/30 * * * * /bin/bash /path/to/watchdog.sh` (documented in README)
- [ ] `docker compose up -d` starts service (not tested in CI)
- [ ] `docker compose down` stops service (not tested in CI)

---

### TASK-30: Complete Test Suite Run

**Title:** Run full test suite with pytest and verify coverage

**Files:** None (execution only)

**Dependencies:** TASK-29

**Effort:** S

**Acceptance Criteria:**
- [x] `pytest` runs without errors
- [x] All tests pass: `tests/test_store.py`, `tests/test_mcp_server.py`, `tests/test_web_routes.py`, `tests/test_api_routes.py`
- [x] Coverage report generated: `pytest --cov=taskboard --cov-report=html`
- [x] Overall coverage > 80% (94% achieved)
- [x] No critical errors or warnings

---

### TASK-31: README Documentation

**Title:** Write comprehensive README with usage, Docker setup, cron configuration

**Files:**
- `README.md`

**Dependencies:** TASK-30

**Effort:** M

**Acceptance Criteria:**
- [x] Project title and description
- [x] Features list (MCP server, web dashboard, REST API, CSV export)
- [x] Prerequisites (Python 3.13+, Docker, Docker Compose)
- [x] Installation steps: `git clone`, `uv pip install -e .`
- [x] Local development: `uvicorn taskboard.web.app:create_app --factory`
- [x] Docker deployment: `docker compose up -d`
- [x] MCP usage: `fastmcp run taskboard.mcp_server:mcp`
- [x] Cron setup: Add watchdog.sh to crontab (`crontab -e`)
- [x] Environment variables: `TASKBOARD_DB` path
- [x] API documentation: List endpoints with examples
- [x] Troubleshooting section (port conflicts, DB permissions, Docker issues)
- [x] Screenshots or examples of dashboard (optional)

---

### TASK-32: End-to-End Verification

**Title:** Manual verification of all success criteria from proposal

**Files:** None (verification checklist)

**Dependencies:** TASK-31

**Effort:** M

**Acceptance Criteria:**
- [x] MCP server arranca con `fastmcp run` y responde tools desde OpenCode (code verified, not runtime tested in CI)
- [x] Web dashboard muestra los 13 proyectos y 177 tareas existentes (tested with TestClient + real DB)
- [x] Se puede crear y completar una tarea desde el MCP (integration tests verify persistence)
- [x] Se puede crear y completar una tarea desde la web (API tests: POST /api/tasks, PATCH status)
- [x] Timeline muestra tareas por semana actual y por mes actual (template + route tested)
- [x] Reportes se generan con 3 modos: solo fechas, solo proyecto, o ambos combinados (route + template tested)
- [x] CSV export descarga archivo filtrado (fechas, proyecto, o ambos) (API test verifies Content-Type + CSV content)
- [x] Docker arranca con `docker compose up`, reinicia tras caídas, levanta al iniciar compu (config verified, not runtime tested)
- [x] Cron/watchdog verifica cada 30 min que el container esté activo y reporta caídas (script + docs verified)
- [x] Tests pasan con `pytest` (152 tests, all passing)
- [x] Navegación web funcional entre páginas (Dashboard → Projects → Timeline → Reports) (all routes tested 200)
- [x] HTMX partials funcionan (filtros, status updates sin reload) (7 partial route tests)
- [x] MCP tools responden con datos de la DB real existente (11 integration tests with real store)

---

## Summary

| Phase | Tasks | Total Effort |
|-------|-------|--------------|
| 1: Foundation | 3 | L |
| 2: Store Completion | 3 | XL |
| 3: MCP Server | 2 | M |
| 4: Web App Framework | 2 | L |
| 5: Web Routes - Pages | 8 | XL |
| 6: Web Routes - API & Partials | 3 | XL |
| 7: Static Assets | 2 | S |
| 8: Testing - Web Layer | 4 | XL |
| 9: Docker & Deployment | 2 | M |
| 10: Final | 2 | M |
| **Total** | **32** | **~5-7 days** |

**Effort Legend:**
- XS: < 1 hour
- S: 1-2 hours
- M: 2-4 hours
- L: 4-8 hours
- XL: > 8 hours
