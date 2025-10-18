#!/bin/bash
# Fix Native Installation - Use Python 3.12 instead of 3.14
# This script recreates the venv with a compatible Python version

set -e  # Exit on error

echo "🔧 OpenEye Native Installation Fix Script"
echo "=========================================="
echo ""

# Navigate to opencv_surveillance directory
cd "$(dirname "$0")/opencv_surveillance"

echo "📁 Current directory: $(pwd)"
echo ""

# Check for Python 3.12
if command -v python3.12 &> /dev/null; then
    PYTHON_CMD="python3.12"
    echo "✅ Found Python 3.12"
elif command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
    echo "✅ Found Python 3.11"
elif command -v python3.10 &> /dev/null; then
    PYTHON_CMD="python3.10"
    echo "✅ Found Python 3.10"
else
    echo "❌ Error: Python 3.10, 3.11, or 3.12 not found!"
    echo ""
    echo "Please install a compatible Python version:"
    echo "  brew install python@3.12"
    exit 1
fi

# Show Python version
echo "🐍 Using: $($PYTHON_CMD --version)"
echo ""

# Check for CMake
if ! command -v cmake &> /dev/null; then
    echo "⚠️  Warning: CMake not found!"
    echo "   Installing CMake via Homebrew..."
    brew install cmake
    echo "✅ CMake installed"
else
    echo "✅ CMake found: $(cmake --version | head -1)"
fi
echo ""

# Backup old venv if exists
if [ -d "venv" ]; then
    echo "🗑️  Removing old venv (Python 3.14)..."
    rm -rf venv
    echo "✅ Old venv removed"
fi
echo ""

# Create new venv with Python 3.12
echo "📦 Creating new virtual environment with $PYTHON_CMD..."
$PYTHON_CMD -m venv venv
echo "✅ Virtual environment created"
echo ""

# Activate venv
echo "🔌 Activating virtual environment..."
source venv/bin/activate
echo "✅ Virtual environment activated"
echo ""

# Upgrade pip
echo "⬆️  Upgrading pip, setuptools, and wheel..."
pip install --upgrade pip setuptools wheel --quiet
echo "✅ Build tools upgraded"
echo ""

# Install dependencies
echo "📚 Installing Python dependencies..."
echo "   This may take several minutes (building dlib and OpenCV)..."
echo ""

# Install in order to avoid conflicts
echo "   [1/4] Installing numpy..."
pip install numpy --quiet

echo "   [2/4] Installing dlib (this takes a while)..."
pip install dlib --quiet

echo "   [3/4] Installing OpenCV..."
pip install opencv-contrib-python --quiet

echo "   [4/4] Installing remaining dependencies..."
pip install -r requirements.txt --quiet

echo ""
echo "✅ All dependencies installed successfully!"
echo ""
echo "=========================================="
echo "🎉 Native Installation Complete!"
echo "=========================================="
echo ""
echo "To activate the environment:"
echo "  cd opencv-surveillance"
echo "  source venv/bin/activate"
echo ""
echo "To run OpenEye:"
echo "  uvicorn backend.main:app --host 0.0.0.0 --port 8000"
echo ""
echo "Or simply run:"
echo "  ./start-local.sh"
echo ""
