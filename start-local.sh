#!/bin/bash
# Start OpenEye locally with native installation

set -e

# Global variable to track uvicorn PID
UVICORN_PID=""

# Cleanup function for graceful shutdown
cleanup() {
    echo ""
    echo "🛑 Shutting down OpenEye..."
    
    if [ -n "$UVICORN_PID" ] && kill -0 "$UVICORN_PID" 2>/dev/null; then
        echo "   Sending SIGTERM to PID $UVICORN_PID..."
        kill -TERM "$UVICORN_PID" 2>/dev/null || true
        
        # Wait up to 10 seconds for graceful shutdown
        for i in {1..10}; do
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
    
    echo "   ✓ Cleanup complete"
}

# Register cleanup trap for EXIT, INT (Ctrl+C), and TERM signals
trap cleanup EXIT INT TERM

echo "🚀 Starting OpenEye (Native Installation)"
echo "========================================"
echo ""

# Navigate to opencv_surveillance
cd "$(dirname "$0")/opencv_surveillance"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Error: Virtual environment not found!"
    echo "   Run: ./fix-native-install.sh"
    exit 1
fi

# Activate venv
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Use the venv's python explicitly
PYTHON_CMD="./venv/bin/python3"

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

# Start the application
echo "🎯 Starting OpenEye on http://localhost:8000"
echo "   Press Ctrl+C to stop"
echo ""

# Start uvicorn in background and capture PID
# Use venv's python to run uvicorn module
$PYTHON_CMD -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
UVICORN_PID=$!

echo "   ✓ Server started with PID: $UVICORN_PID"
echo ""

# Wait for uvicorn process (will be interrupted by Ctrl+C)
wait "$UVICORN_PID" 2>/dev/null || true
