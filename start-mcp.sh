#!/bin/bash
# Wrapper to start taskboard MCP server with correct working directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
exec "$SCRIPT_DIR/.venv/bin/python" -c "from taskboard.mcp_server import mcp; mcp.run()"
