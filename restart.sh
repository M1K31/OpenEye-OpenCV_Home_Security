#!/usr/bin/env bash
# OpenEye Surveillance System — Restart.
#
# Stops any running instance (managed launchd service AND stray foreground/manual
# uvicorn processes holding the port), then starts the launchd service fresh from
# the installed internal-disk snapshot (~/.local/share/openeye/app). Use this after
# syncing code changes or granting camera permission from a manual run.
#
# Usage:
#   ./restart.sh            # restart the managed service
#   ./restart.sh --status   # just show current status, don't restart
#
# Env overrides: OPENEYE_PORT (default 8200), OPENEYE_DATA_ROOT.
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'

LABEL="com.smartindustries.openeye"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PORT="${OPENEYE_PORT:-8200}"
DATA_ROOT="${OPENEYE_DATA_ROOT:-$HOME/.local/share/openeye}"
GUI="gui/$(id -u)"

show_status() {
    if launchctl list 2>/dev/null | grep -q "$LABEL"; then
        echo -e "  service: ${GREEN}loaded${NC} ($LABEL)"
    else
        echo -e "  service: ${YELLOW}not loaded${NC}"
    fi
    # Only LISTENers are the server; clients (browser, ecosystem apps) also have
    # sockets on this port and must not be counted or killed.
    local pids; pids="$(lsof -ti:"$PORT" -sTCP:LISTEN 2>/dev/null | tr '\n' ' ' || true)"
    if [ -n "$pids" ]; then
        echo -e "  port $PORT: ${GREEN}listening${NC} (server pids: $pids)"
    else
        echo -e "  port $PORT: ${YELLOW}free${NC}"
    fi
}

if [ "${1:-}" = "--status" ]; then
    echo -e "${BLUE}=== OpenEye status ===${NC}"; show_status; exit 0
fi

# --foreground: run OpenEye in THIS terminal instead of the launchd service.
# On macOS the background service cannot access the local camera (TCC/F-10), so
# USB/built-in cameras only work when OpenEye is started from a terminal.
if [ "${1:-}" = "--foreground" ] || [ "${1:-}" = "-f" ]; then
    echo -e "${BLUE}=== Starting OpenEye in the FOREGROUND (camera-capable) ===${NC}"
    echo -e "${BLUE}[1/2] Stopping the launchd service...${NC}"
    launchctl bootout "$GUI/$LABEL" 2>/dev/null || launchctl unload "$PLIST" 2>/dev/null || true
    sleep 1
    LP="$(lsof -ti:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"; [ -n "$LP" ] && kill -9 $LP 2>/dev/null || true
    START="$DATA_ROOT/app/start.sh"
    if [ ! -x "$START" ]; then
        echo -e "${RED}No start script at $START${NC}"; exit 1
    fi
    echo -e "${BLUE}[2/2] Launching in foreground (Ctrl+C to stop). Approve the camera prompt if asked.${NC}"
    exec "$START"
fi

if [ ! -f "$PLIST" ]; then
    echo -e "${RED}No launchd plist at $PLIST${NC}"
    echo "Install/enable the service first: ./opencv_surveillance/scripts/install-local.sh"
    exit 1
fi

echo -e "${BLUE}=== Restarting OpenEye ===${NC}"

# 1. Stop the managed service (modern bootout, fall back to legacy unload).
echo -e "${BLUE}[1/4] Stopping launchd service...${NC}"
launchctl bootout "$GUI/$LABEL" 2>/dev/null \
    || launchctl unload "$PLIST" 2>/dev/null \
    || true

# 2. Clear any stray OpenEye server still holding the port. IMPORTANT: only kill
#    processes LISTENing on the port (the server). Clients connected to it — your
#    browser, ecosystem apps — also appear in a plain `lsof -ti`, and must NOT be
#    killed. Match the uvicorn command precisely, then fall back to the listener.
echo -e "${BLUE}[2/4] Clearing port $PORT (server only)...${NC}"
pkill -f 'uvicorn.*backend.main:app' 2>/dev/null || true
sleep 1
LISTEN_PIDS="$(lsof -ti:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
if [ -n "$LISTEN_PIDS" ]; then
    echo "  killing lingering server (listener) pids: $LISTEN_PIDS"
    # shellcheck disable=SC2086
    kill -9 $LISTEN_PIDS 2>/dev/null || true
    sleep 1
fi

# 3. Start the service fresh (modern bootstrap, fall back to legacy load).
#    Re-enable first in case the unit was previously `launchctl disable`d (a
#    disabled unit bootstraps but never actually starts → port stays closed).
echo -e "${BLUE}[3/4] Starting launchd service...${NC}"
launchctl enable "$GUI/$LABEL" 2>/dev/null || true
launchctl bootstrap "$GUI" "$PLIST" 2>/dev/null \
    || launchctl load "$PLIST" 2>/dev/null \
    || { echo -e "${RED}Failed to load $PLIST${NC}"; exit 1; }
launchctl kickstart -k "$GUI/$LABEL" 2>/dev/null || true

# 4. Wait for the port to come up (backend runs DB migrations on start).
echo -e "${BLUE}[4/4] Waiting for the server on port $PORT...${NC}"
for i in $(seq 1 30); do
    if lsof -ti:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
        echo -e "${GREEN}OpenEye is up on http://localhost:$PORT${NC}"
        echo "  UI:   http://localhost:$PORT"
        echo "  Docs: http://localhost:$PORT/api/docs"
        echo "  Logs: $HOME/Library/Logs/OpenEye/{stdout,stderr}.log"
        show_status
        exit 0
    fi
    sleep 1
done

echo -e "${YELLOW}Service loaded but port $PORT is not listening yet.${NC}"
echo "Check logs: tail -n 50 \"$HOME/Library/Logs/OpenEye/stderr.log\""
exit 1
