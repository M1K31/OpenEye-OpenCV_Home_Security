#!/bin/bash
# Start OpenEye locally with native installation

set -e

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

    # Also kill by port to be sure
    PORT_PIDS=$(lsof -ti :8000 2>/dev/null || true)
    if [ -n "$PORT_PIDS" ]; then
        echo "   Killing processes on port 8000..."
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

# Generate secret keys if .env doesn't exist
if [ ! -f ".env" ]; then
    echo "🔐 Generating secret keys..."
    SECRET_KEY=$($PYTHON_CMD -c "import secrets; print(secrets.token_hex(32))")
    JWT_SECRET=$($PYTHON_CMD -c "import secrets; print(secrets.token_hex(32))")
    
    cat > .env << EOF
SECRET_KEY=$SECRET_KEY
JWT_SECRET_KEY=$JWT_SECRET
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
EOF
    echo "✅ Secret keys generated in .env"
    echo ""
fi

# Check if port 8000 is already in use
PORT=8000
check_port() {
    if lsof -i :$PORT >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

if check_port; then
    echo "⚠️  Port $PORT is already in use!"
    echo ""
    echo "   Process(es) using port $PORT:"
    lsof -i :$PORT | head -5
    echo ""

    # Ask user what to do
    read -p "   Would you like to kill the process(es) using port $PORT? [y/N] " response
    case "$response" in
        [yY][eE][sS]|[yY])
            echo ""
            echo "   Killing processes on port $PORT..."
            # Get PIDs of processes using the port (skip header line)
            PIDS=$(lsof -ti :$PORT 2>/dev/null)
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
echo "🎯 Starting OpenEye on http://localhost:8000"
echo "   Press Ctrl+C to stop"
echo ""

# Suppress OpenMP duplicate library warning (common on macOS with numpy/scipy)
# These must be set before Python imports any library that uses OpenMP
export KMP_DUPLICATE_LIB_OK=TRUE
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

# Start uvicorn in background and capture PID
# Use venv's python to run uvicorn module
$PYTHON_CMD -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
UVICORN_PID=$!

echo "   ✓ Server started with PID: $UVICORN_PID"
echo ""

# Wait for uvicorn process (will be interrupted by Ctrl+C)
wait "$UVICORN_PID" 2>/dev/null || true
