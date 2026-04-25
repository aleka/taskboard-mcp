# Taskboard MCP — Code Review Rules

## General

- Use conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`, `ci:`
- No AI attribution or "Co-Authored-By" in commits
- Python 3.13+ — use modern syntax (type hints, `X | Y` unions, f-strings)
- All public functions must have docstrings
- No `print()` in production code — use logging if needed

## Architecture

- Single process: Starlette mounts fastmcp at `/mcp`, serves web at `/`, API at `/api/`
- `TaskboardStore` is the single source of truth — all routes/tools delegate to it
- Zero schema changes — the SQLite schema is production data, never modify it
- `store.py` owns all SQL — no raw SQL in routes, templates, or MCP tools
- Web routes in `taskboard/web/routes/`: `pages.py` (HTML), `api.py` (JSON), `actions.py` (HTMX form handlers), `partials.py` (HTMX fragments)

## HTMX / Templates

- HTMX forms MUST POST to `/actions/*` routes (form-encoded), NOT `/api/*` routes (JSON)
- API routes (`/api/*`) accept and return JSON only
- Action routes (`/actions/*`) accept `application/x-www-form-urlencoded` and return HTML fragments
- Partial routes (`/partials/*`) return HTML fragments for HTMX swaps
- Templates use Jinja2 with autoescape (always on)
- All HTML must have `hx-on::response-error` handler for error feedback

## Database

- SQLite with WAL mode, busy_timeout 5000ms, foreign_keys ON
- Status values: `pending`, `in-progress`, `done`, `cancelled` (NOT `completed`)
- Task IDs follow `{slug}_{NNN}` format
- Use parameterized queries — NEVER string concatenation in SQL
- Store class uses context manager pattern (`with TaskboardStore() as store`)

## Testing

- In-memory SQLite (`:memory:`) for unit tests — never touch production DB
- Starlette TestClient for route tests
- All new features must include tests
- Test file naming: `test_*.py` in `tests/` directory
- Coverage target: > 90%

## Security

- Jinja2 autoescape must be ON (default)
- No raw user input in SQL — always parameterized
- No secrets or credentials in code
- Error messages must not expose SQL or internal details

## Style

- Imports: stdlib → third-party → local, blank line between groups
- Max line length: 120 characters
- Use `pathlib` or `os.path.dirname(__file__)` for file paths — never relative paths that break from CWD
- CSS variables in `style.css` — no inline styles in templates
