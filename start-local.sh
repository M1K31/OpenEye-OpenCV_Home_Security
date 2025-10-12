#!/bin/bash
# Start OpenEye locally with native installation

set -e

echo "🚀 Starting OpenEye (Native Installation)"
echo "========================================"
echo ""

# Navigate to opencv-surveillance
cd "$(dirname "$0")/opencv-surveillance"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Error: Virtual environment not found!"
    echo "   Run: ./fix-native-install.sh"
    exit 1
fi

# Activate venv
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Check Python version
PYTHON_VERSION=$(python --version)
echo "✅ $PYTHON_VERSION"
echo ""

# Generate secret keys if .env doesn't exist
if [ ! -f ".env" ]; then
    echo "🔐 Generating secret keys..."
    SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
    JWT_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
    
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

uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
