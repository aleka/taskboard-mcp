#!/usr/bin/env bash
# watchdog.sh — Check if taskboard container is running, restart if crashed.
#
# Cron entry (every 30 minutes):
#   */30 * * * * /bin/bash /path/to/taskboard-mcp/watchdog.sh
#
# Requires: docker, docker compose

set -euo pipefail

CONTAINER_NAME="taskboard-mcp"
LOG_DIR="$HOME/.taskboard"
LOG_FILE="$LOG_DIR/crash-report.log"
COMPOSE_DIR="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$LOG_DIR"

# Check if container is running
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    exit 0  # All good
fi

# Container not running — log and restart
echo "[$(date '+%Y-%m-%d %H:%M:%S')] WATCHDOG: Container '$CONTAINER_NAME' is NOT running. Attempting restart..." >> "$LOG_FILE"

cd "$COMPOSE_DIR"
docker compose up -d >> "$LOG_FILE" 2>&1

# Verify restart succeeded
sleep 5
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WATCHDOG: Container '$CONTAINER_NAME' restarted successfully." >> "$LOG_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WATCHDOG: FAILED to restart container '$CONTAINER_NAME'!" >> "$LOG_FILE"
fi
