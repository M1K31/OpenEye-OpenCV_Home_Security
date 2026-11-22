#!/bin/bash
# Start OpenEye locally with native installation

set -e


SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/openeye-port.sh
source "$SCRIPT_DIR/scripts/lib/openeye-port.sh"
# The canonical port, resolved exactly as the application resolves it. This
# script used to launch uvicorn on 8000 while backend/core/config.py defaults to
# 8200, so the server ran on a different port from the one everything else
# advertised.
PORT="$(openeye_resolve_port)"
# Global variable to track uvicorn PID
UVICORN_PID=""

# Cleanup function for graceful shutdown
cleanup() {
    echo ""
    echo "🛑 Shutting down OpenEye..."

    # Kill the main uvicorn process
    if [ -n "$UVICORN_PID" ] && kill -0 "$UVICORN_PID" 2>/dev/null; then
        echo "   Sending SIGTERM to PID $UVICORN_PID..."
        kill -TERM "$UVICORN_PID" 2>/dev/null || true

        # Wait up to 5 seconds for graceful shutdown
        for i in {1..5}; do
            if ! kill -0 "$UVICORN_PID" 2>/dev/null; then
                echo "   ✓ Server stopped gracefully"
                break
            fi
            sleep 1
        done

        # Force kill if still running
        if kill -0 "$UVICORN_PID" 2>/dev/null; then
            echo "   ⚠ Force killing server..."
            kill -9 "$UVICORN_PID" 2>/dev/null || true
        fi
    fi

    # Kill any child processes (uvicorn --reload spawns workers)
    echo "   Cleaning up child processes..."
    pkill -9 -f "uvicorn backend.main:app" 2>/dev/null || true

    # Also kill by port to be sure — but only our own processes. Matching every
    # PID on the port would kill unrelated software that happens to use it.
    PORT_PIDS=$(openeye_service_pids "$PORT")
    if [ -n "$PORT_PIDS" ]; then
        echo "   Killing OpenEye processes on port $PORT..."
        for pid in $PORT_PIDS; do
            kill -9 "$pid" 2>/dev/null || true
        done
    fi

    echo "   ✓ Cleanup complete"
}

# Register cleanup trap for EXIT, INT (Ctrl+C), and TERM signals
trap cleanup EXIT INT TERM

echo "🚀 Starting OpenEye (Native Installation)"
echo "========================================"
echo ""

# Navigate to opencv_surveillance
cd "$(dirname "$0")/opencv_surveillance"

# Check if venv exists (.venv is preferred, fall back to legacy venv/)
if [ -d ".venv" ]; then
    VENV_DIR=".venv"
elif [ -d "venv" ]; then
    VENV_DIR="venv"
else
    echo "❌ Error: Virtual environment not found!"
    echo "   Run: ./setup-production.sh"
    exit 1
fi

# Activate venv
echo "🔌 Activating virtual environment ($VENV_DIR)..."
source "$VENV_DIR/bin/activate"

# Use the venv's python explicitly
PYTHON_CMD="./$VENV_DIR/bin/python3"

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD --version)
echo "✅ $PYTHON_VERSION"
echo ""



# Stop any launchd-managed OpenEye service so it does not compete with this
# foreground instance for port $PORT or local USB camera hardware every 10s.
LAUNCHD_LABEL="com.smartindustries.openeye"
LAUNCHD_PLIST="$HOME/Library/LaunchAgents/$LAUNCHD_LABEL.plist"
launchctl bootout "gui/$(id -u)/$LAUNCHD_LABEL" 2>/dev/null \
    || launchctl unload "$LAUNCHD_PLIST" 2>/dev/null \
    || true

# Also terminate any orphaned uvicorn reloader supervisor processes before
# checking the port, because killing only the child worker on $PORT leaves the
# parent reloader alive to respawn a competing worker.
pkill -f "uvicorn.*backend.main:app" 2>/dev/null || true

# Check if the service port is already in use (LISTEN only)
check_port() {
    if lsof -ti:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

if check_port; then
    echo "⚠️  Port $PORT is already in use!"
    echo ""
    echo "   Process(es) listening on port $PORT:"
    lsof -ti:"$PORT" -sTCP:LISTEN | head -5
    echo ""

    # Ask user what to do
    read -p "   Would you like to kill the process(es) listening on port $PORT? [y/N] " response
    case "$response" in
        [yY][eE][sS]|[yY])
            echo ""
            echo "   Killing server on port $PORT..."
            pkill -9 -f "uvicorn.*backend.main:app" 2>/dev/null || true
            # Get PIDs of processes listening on the port
            PIDS=$(lsof -ti:"$PORT" -sTCP:LISTEN 2>/dev/null)
            if [ -n "$PIDS" ]; then
                for pid in $PIDS; do
                    echo "   Killing PID $pid..."
                    kill -9 "$pid" 2>/dev/null || true
                done
                sleep 1
                echo "   ✓ Processes killed"
            fi
            echo ""
            ;;
        *)
            echo ""
            echo "   Please close the application using port $PORT and try again."
            exit 1
            ;;
    esac
fi

# Start the application
echo "🎯 Starting OpenEye on http://localhost:$PORT"
echo "   Press Ctrl+C to stop"
echo ""

# Suppress OpenMP duplicate library warning (common on macOS with numpy/scipy)
# These must be set before Python imports any library that uses OpenMP
export KMP_DUPLICATE_LIB_OK=TRUE
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export OPENCV_FFMPEG_CAPTURE_OPTIONS="rtsp_transport;tcp|stimeout;5000000"

# Start uvicorn in background and capture PID
# Scope --reload-dir strictly to "$APP_RUN_DIR/backend" so Uvicorn's file watcher
# only monitors backend Python source files and never sees runtime writes in
# data/, faces/, recordings/, logs/, or surveillance.db-wal.
APP_RUN_DIR="$(pwd)"
$PYTHON_CMD -m uvicorn backend.main:app --host 0.0.0.0 --port "$PORT" \
    --reload \
    --reload-dir "$APP_RUN_DIR/backend" \
    --reload-include "*.py" \
    --reload-exclude "*.pyc" \
    --reload-exclude "__pycache__" &
UVICORN_PID=$!

echo "   ✓ Server started with PID: $UVICORN_PID"
echo ""

# Wait for uvicorn process (will be interrupted by Ctrl+C)
wait "$UVICORN_PID" 2>/dev/null || true
