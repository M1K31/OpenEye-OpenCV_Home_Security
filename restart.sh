#!/usr/bin/env bash
# OpenEye Surveillance System — Restart.
#
# Stops any running instance (managed launchd service AND stray foreground/manual
# uvicorn processes holding the port), syncs code changes if needed, and starts
# OpenEye fresh.
#
# Why Terminal-spawned background mode is preferred on macOS when run from a shell:
#   macOS Sonoma/Sequoia TCC blocks background `launchd` agents running an unsigned
#   Homebrew Python binary from accessing BOTH local cameras (AVFoundation TCC) AND
#   Local Network RTSP cameras (192.168.x.x EHOSTUNREACH). Spawning uvicorn from the
#   active Terminal session (detached via nohup) inherits Terminal's Local Network
#   and Camera permissions so both USB and RTSP cameras (like TP-Link Tapo) stay Live!
#
# Usage:
#   ./restart.sh            # sync & restart (inherits Terminal TCC permissions)
#   ./restart.sh --launchd  # force restart via background launchd agent
#   ./restart.sh --foreground # run attached in foreground
#   ./restart.sh --status   # just show current status, don't restart
#
# Env overrides: OPENEYE_PORT (default 8200), OPENEYE_DATA_ROOT.
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_APP_DIR="$SCRIPT_DIR/opencv_surveillance"
LABEL="com.smartindustries.openeye"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PORT="${OPENEYE_PORT:-8200}"
DATA_ROOT="${OPENEYE_DATA_ROOT:-$HOME/.local/share/openeye}"
GUI="gui/$(id -u)"

show_status() {
    if launchctl print "$GUI/$LABEL" >/dev/null 2>&1 || launchctl list 2>/dev/null | grep -q "$LABEL"; then
        echo -e "  launchd: ${GREEN}loaded${NC} ($LABEL)"
    else
        echo -e "  launchd: ${YELLOW}not loaded (using Terminal-inherited background process)${NC}"
    fi
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

stop_existing() {
    echo -e "${BLUE}[1/3] Stopping any existing launchd or uvicorn instance...${NC}"
    launchctl bootout "$GUI/$LABEL" 2>/dev/null \
        || launchctl unload "$PLIST" 2>/dev/null \
        || true
    for _ in {1..4}; do
        launchctl print "$GUI/$LABEL" >/dev/null 2>&1 || break
        sleep 0.4
    done

    # Send graceful SIGTERM first so OpenCV/FFmpeg sends RTSP TEARDOWN to IP cameras
    pkill -TERM -f 'uvicorn.*backend.main:app' 2>/dev/null || true
    for _ in {1..6}; do
        [ -z "$(lsof -ti:"$PORT" -sTCP:LISTEN 2>/dev/null || true)" ] && break
        sleep 0.5
    done

    LISTEN_PIDS="$(lsof -ti:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
    if [ -n "$LISTEN_PIDS" ]; then
        echo "  stopping lingering server pids: $LISTEN_PIDS"
        # shellcheck disable=SC2086
        kill -TERM $LISTEN_PIDS 2>/dev/null || true
        sleep 1.5
        LISTEN_PIDS="$(lsof -ti:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
        if [ -n "$LISTEN_PIDS" ]; then
            # shellcheck disable=SC2086
            kill -9 $LISTEN_PIDS 2>/dev/null || true
            sleep 1
        fi
    fi
}

# --foreground: run OpenEye attached in THIS terminal.
if [ "${1:-}" = "--foreground" ] || [ "${1:-}" = "-f" ]; then
    echo -e "${BLUE}=== Starting OpenEye in the FOREGROUND ===${NC}"
    stop_existing
    cd "$REPO_APP_DIR"
    PYTHON_BIN="$REPO_APP_DIR/.venv/bin/python"
    [ ! -x "$PYTHON_BIN" ] && PYTHON_BIN="$DATA_ROOT/venv/bin/python"
    exec "$PYTHON_BIN" -m uvicorn backend.main:app --host 0.0.0.0 --port "$PORT"
fi

# --launchd: explicitly use the launchd agent
if [ "${1:-}" = "--launchd" ]; then
    stop_existing
    echo -e "${BLUE}[2/3] Starting launchd service...${NC}"
    launchctl enable "$GUI/$LABEL" 2>/dev/null || true
    launchctl bootstrap "$GUI" "$PLIST" 2>/dev/null \
        || launchctl load "$PLIST" 2>/dev/null \
        || { echo -e "${RED}Failed to load $PLIST${NC}"; exit 1; }
    launchctl kickstart -k "$GUI/$LABEL" 2>/dev/null || true
else
    # Default: Start from the repository working tree in a Terminal-inherited
    # background process so macOS Local Network (RTSP) and Camera TCC permissions
    # are preserved and the active surveillance.db is used directly.
    stop_existing
    echo -e "${BLUE}[2/3] Starting OpenEye server on port $PORT (Terminal-inherited permissions)...${NC}"
    mkdir -p "$HOME/Library/Logs/OpenEye"
    PYTHON_BIN="$REPO_APP_DIR/.venv/bin/python"
    [ ! -x "$PYTHON_BIN" ] && PYTHON_BIN="$DATA_ROOT/venv/bin/python"
    (
        cd "$REPO_APP_DIR"
        nohup "$PYTHON_BIN" -m uvicorn backend.main:app --host 0.0.0.0 --port "$PORT" \
            >>"$HOME/Library/Logs/OpenEye/stdout.log" \
            2>>"$HOME/Library/Logs/OpenEye/stderr.log" </dev/null &
    )
fi

echo -e "${BLUE}[3/3] Waiting for the server on port $PORT...${NC}"
for _ in $(seq 1 30); do
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

echo -e "${YELLOW}Server started but port $PORT is not listening yet.${NC}"
echo "Check logs: tail -n 50 \"$HOME/Library/Logs/OpenEye/stderr.log\""
exit 1
