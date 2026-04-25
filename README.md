# Taskboard MCP

MCP server + web dashboard for personal task tracking. Track tasks across projects, view timelines, generate reports, and export data — all from your terminal via MCP or from a browser.

## Features

- **MCP Server** — 10 tools for AI agents (add/complete/update/list tasks, manage projects, metrics, timeline, CSV export)
- **Web Dashboard** — Browser-based UI with dashboard, project details, timeline, and reports pages
- **REST API** — Full JSON API for tasks, projects, metrics, and CSV export
- **HTMX Partials** — Live updates without page reloads (status changes, filters, metrics refresh)
- **CSV Export** — Download filtered task data with date/project/combined filters
- **Docker Deployment** — Single container with auto-restart and health checks
- **Watchdog Script** — Cron-based crash detection and automatic recovery

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (package manager)
- Docker & Docker Compose (optional, for containerized deployment)

## Installation

```bash
git clone <repo-url> taskboard-mcp
cd taskboard-mcp
uv pip install -e .
```

## Local Development

```bash
# Start the web server (port 7438)
uvicorn taskboard.web.app:create_app --host 0.0.0.0 --port 7438 --factory

# Start the MCP server
fastmcp run taskboard.mcp_server:mcp
```

## Docker Deployment

```bash
docker compose up -d
```

The dashboard is available at http://localhost:7438

### Auto-Restart

The container is configured with `restart: unless-stopped`, so it will restart automatically after system reboots or crashes.

### Watchdog (Cron)

For additional crash monitoring, add the watchdog to crontab:

```bash
crontab -e
```

Add this line (adjust the path):

```
*/30 * * * * /bin/bash /path/to/taskboard-mcp/watchdog.sh
```

The watchdog checks every 30 minutes if the container is running. If not, it logs to `~/.taskboard/crash-report.log` and attempts a restart.

## MCP Usage

When configured in your MCP client (e.g., OpenCode, Claude Desktop), the server provides these tools:

| Tool | Description |
|------|-------------|
| `add_task` | Create a new task |
| `complete_task` | Mark a task as done |
| `update_task_status` | Change task status (todo, in_progress, blocked, cancelled) |
| `list_tasks` | List tasks with filters (project, status, type, dates) |
| `get_task` | Get details of a specific task |
| `add_project` | Register a new project |
| `list_projects` | List all registered projects |
| `get_metrics` | Get completion stats with optional filters |
| `get_timeline` | View tasks by week or month |
| `export_csv` | Export tasks as CSV |

## API Documentation

### Tasks

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/tasks` | List tasks (query params: project, status, type, from_date, to_date, limit, offset) |
| POST | `/api/tasks` | Create task (JSON body: project, title, type, description, priority, tags) |
| GET | `/api/tasks/{task_id}` | Get task details |
| PATCH | `/api/tasks/{task_id}` | Update status (JSON body: status, note) |
| DELETE | `/api/tasks/{task_id}` | Delete a task |

### Projects

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects` | List all projects |
| POST | `/api/projects` | Create project (JSON body: name, display_name, slug, origin, path) |
| GET | `/api/projects/{slug}` | Get project details |

### Analytics & Export

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/metrics` | Get metrics (query params: project, start_date, end_date) |
| GET | `/api/export/csv` | Download CSV (query params: project, start_date, end_date) |

### Example

```bash
# Create a task
curl -X POST http://localhost:7438/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"project": "myproj", "title": "Build feature", "type": "feature"}'

# Get metrics
curl http://localhost:7438/api/metrics

# Export CSV
curl -o tasks.csv http://localhost:7438/api/export/csv?project=myproj
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TASKBOARD_DB` | `~/.taskboard/taskboard.db` | Path to the SQLite database file |

## Testing

```bash
# Run all tests with coverage
uv run pytest tests/ -v --cov=taskboard

# Run specific test file
uv run pytest tests/test_store.py -v
```

## Troubleshooting

### Port 7438 already in use

```bash
# Find what's using the port
lsof -i :7438

# Use a different port
uvicorn taskboard.web.app:create_app --port 8080 --factory
```

### Database permissions

```bash
mkdir -p ~/.taskboard
chmod 700 ~/.taskboard
```

### Docker container won't start

```bash
# Check logs
docker compose logs taskboard

# Rebuild
docker compose up -d --build
```

### Tests failing with thread errors

The web tests use `TestClient` which runs in a background thread. If you see SQLite thread errors, ensure the `client` fixture uses `check_same_thread=False`.
