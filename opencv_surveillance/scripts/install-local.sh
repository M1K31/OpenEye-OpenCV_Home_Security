#!/bin/bash
# OpenEye Surveillance System - Local Installation Script
# This script automates the complete installation process for a local machine
# Supports macOS and Linux

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Non-interactive mode: set ECOSYSTEM_NONINTERACTIVE=1, OPENEYE_NONINTERACTIVE=1,
# CI=true, or pass --yes/-y so unattended installs (e.g. the ecosystem smoke
# test) never block on a prompt.
NONINTERACTIVE="${ECOSYSTEM_NONINTERACTIVE:-${OPENEYE_NONINTERACTIVE:-${CI:-}}}"

# confirm "<prompt>" "<default-when-noninteractive: Y|N>" -> exit 0 for yes.
confirm() {
    local prompt="$1" default="${2:-N}"
    if [ -n "$NONINTERACTIVE" ]; then
        log_info "$prompt -> ${default} (non-interactive)"
        [[ "$default" =~ ^[Yy] ]]
        return
    fi
    read -p "$prompt " -n 1 -r; echo
    [[ $REPLY =~ ^[Yy]$ ]]
}

# Print banner
print_banner() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════╗"
    echo "║   OpenEye Surveillance System Installer       ║"
    echo "║   Local Machine Setup                         ║"
    echo "╚════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Check if running as root
check_root() {
    if [ "$EUID" -eq 0 ]; then 
        log_error "Please do not run this script as root/sudo"
        log_info "The script will ask for sudo permissions when needed"
        exit 1
    fi
}

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        log_info "Detected macOS"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
        log_info "Detected Linux"
    else
        log_error "Unsupported operating system: $OSTYPE"
        exit 1
    fi
}

# Check Python version
check_python() {
    log_info "Checking Python installation..."
    
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
        
        if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
            log_success "Python $PYTHON_VERSION found"
            PYTHON_CMD="python3"
        else
            log_error "Python 3.8+ required, found $PYTHON_VERSION"
            exit 1
        fi
    else
        log_error "Python 3 not found"
        log_info "Please install Python 3.8 or higher"
        exit 1
    fi
}

# Install system dependencies
install_system_deps() {
    log_info "Installing system dependencies..."
    
    if [ "$OS" == "macos" ]; then
        # Check if Homebrew is installed
        if ! command -v brew &> /dev/null; then
            log_warn "Homebrew not found. Installing Homebrew..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi
        
        log_info "Installing dependencies via Homebrew..."
        brew install opencv pkg-config cmake || log_warn "Some packages may already be installed"
        
    elif [ "$OS" == "linux" ]; then
        log_info "Installing dependencies via apt..."
        sudo apt-get update
        sudo apt-get install -y \
            python3-dev \
            python3-pip \
            python3-venv \
            build-essential \
            cmake \
            pkg-config \
            libopencv-dev \
            libavcodec-dev \
            libavformat-dev \
            libswscale-dev \
            libv4l-dev \
            libxvidcore-dev \
            libx264-dev \
            libatlas-base-dev \
            gfortran \
            libhdf5-dev \
            libhdf5-serial-dev \
            libatlas-base-dev \
            libjasper-dev \
            libqt5gui5 \
            libqt5webkit5 \
            libqt5test5
    fi
    
    log_success "System dependencies installed"
}

# Create virtual environment
setup_venv() {
    log_info "Setting up Python virtual environment..."
    
    cd "$PROJECT_DIR"
    
    if [ -d "venv" ]; then
        log_warn "Virtual environment already exists"
        # Idempotent default: keep the existing venv unless asked to recreate.
        if confirm "Do you want to recreate it? (y/N):" N; then
            log_info "Removing existing virtual environment..."
            rm -rf venv
        else
            log_info "Using existing virtual environment"
            return
        fi
    fi
    
    log_info "Creating virtual environment..."
    $PYTHON_CMD -m venv venv
    
    log_success "Virtual environment created"
}

# Install Python dependencies
install_python_deps() {
    log_info "Installing Python dependencies..."
    
    cd "$PROJECT_DIR"
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    log_info "Upgrading pip..."
    pip install --upgrade pip setuptools wheel

    # Ensure ffmpeg BEFORE pip: aiortc->av (WebRTC two-way audio) builds against
    # it. Without ffmpeg the av wheel fails and aborts the whole install.
    if ! command -v ffmpeg >/dev/null 2>&1; then
        log_warn "ffmpeg not found — required to build the WebRTC stack (av/aiortc)."
        if [ "$(uname -s)" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
            log_info "Installing ffmpeg via Homebrew..."; brew install ffmpeg || log_warn "brew install ffmpeg failed"
        elif command -v apt-get >/dev/null 2>&1; then
            log_info "Installing ffmpeg via apt..."; sudo apt-get install -y ffmpeg || log_warn "apt install ffmpeg failed"
        else
            log_warn "Install ffmpeg manually for two-way audio; continuing (feature will be disabled)."
        fi
    fi

    # Install requirements. If a native build (e.g. av without ffmpeg) fails,
    # retry without the WebRTC stack so the rest of the app still installs —
    # the backend degrades gracefully (WEBRTC_AVAILABLE=False).
    log_info "Installing required packages..."
    if ! pip install -r requirements.txt; then
        log_warn "Full install failed (likely the WebRTC/av native build)."
        log_warn "Retrying without av/aiortc — two-way audio will be disabled."
        grep -viE "^(av|aiortc|pyav)([=<>~! ]|\[|$)" requirements.txt > /tmp/oe_req_core.txt
        pip install -r /tmp/oe_req_core.txt
    fi

    # Shared ecosystem packages — enable inter-service auth + AI-profile sync.
    # Guarded imports mean a missing/failed install just runs standalone.
    ECO_ROOT="${ECOSYSTEM_BASE_PATH:-$PROJECT_DIR/../..}/appEcosystem"
    if [ -d "$ECO_ROOT/auth/python" ]; then
        log_info "Installing shared ecosystem packages from $ECO_ROOT..."
        pip install "$ECO_ROOT/auth/python" \
                    "$ECO_ROOT/packages/ecosystem-client" \
                    "$ECO_ROOT/packages/ecosystem-ai" \
            && log_success "Shared ecosystem packages installed" \
            || log_info "Shared-package install failed; running standalone (ecosystem sync disabled)"
    else
        log_info "appEcosystem not found at $ECO_ROOT — standalone (set ECOSYSTEM_BASE_PATH to enable sync)"
    fi

    log_success "Python dependencies installed"
}

# Generate secret keys
generate_secrets() {
    log_info "Generating secret keys..."
    
    cd "$PROJECT_DIR"
    source venv/bin/activate
    
    # Generate JWT secret key
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    
    # Generate admin token
    ADMIN_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    
    # Create .env file
    cat > .env << EOF
# OpenEye Surveillance System Configuration
# Generated on $(date)

# Security Keys - KEEP THESE SECRET!
JWT_SECRET_KEY=$JWT_SECRET
ADMIN_TOKEN=$ADMIN_TOKEN

# Database
DATABASE_URL=sqlite:///./surveillance.db

# Server Configuration
HOST=0.0.0.0
PORT=8000

# CORS Settings (adjust for production)
CORS_ORIGINS=http://localhost:8000,http://localhost:3000

# Feature Flags
ENABLE_MOTION_DETECTION=true
ENABLE_FACE_RECOGNITION=true
ENABLE_RECORDING=true

# Logging
LOG_LEVEL=INFO
EOF
    
    log_success "Secret keys generated and saved to .env"
    log_warn "Keep your .env file secure and do not commit it to version control!"
}

# Setup database
setup_database() {
    log_info "Setting up database..."
    
    cd "$PROJECT_DIR"
    source venv/bin/activate
    
    # Database will be created automatically on first run
    # We just need to ensure the directory exists
    mkdir -p data/faces data/thumbnails
    
    log_success "Database directories created"
}

# Create required directories
create_directories() {
    log_info "Creating required directories..."
    
    cd "$PROJECT_DIR"
    
    mkdir -p data/faces
    mkdir -p data/thumbnails
    mkdir -p models/face_detection_model
    mkdir -p frontend/dist
    
    log_success "Directories created"
}

# Build frontend
build_frontend() {
    log_info "Building frontend..."
    
    cd "$PROJECT_DIR/frontend"
    
    # Check if Node.js is installed
    if ! command -v npm &> /dev/null; then
        log_warn "Node.js/npm not found. Skipping frontend build."
        log_info "Install Node.js from https://nodejs.org/ to build the frontend"
        return
    fi
    
    # Install dependencies
    log_info "Installing frontend dependencies..."
    npm install
    
    # Build
    log_info "Building production bundle..."
    npm run build
    
    log_success "Frontend built successfully"
}

# Create an auto-start service: macOS launchd OR Linux systemd.
create_systemd_service() {
    # Non-interactive default: only create the service when explicitly requested
    # via OPENEYE_INSTALL_SERVICE=1, matching the interactive "N" default.
    local svc_default="N"; [ -n "${OPENEYE_INSTALL_SERVICE:-}" ] && svc_default="Y"
    if ! confirm "Do you want to create an auto-start service? (y/N):" "$svc_default"; then
        return
    fi

    local PORT="${ECOSYSTEM_SERVICE_PORT:-8200}"
    local UNAME; UNAME="$(uname -s)"

    if [ "$UNAME" = "Darwin" ]; then
        log_info "Creating launchd agent..."
        local LABEL="com.smartindustries.openeye"
        local PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
        local LOGDIR="$HOME/Library/Logs/OpenEye"
        mkdir -p "$LOGDIR" "$HOME/Library/LaunchAgents"
        cat > "$PLIST" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array>
    <string>$PROJECT_DIR/venv/bin/python3</string>
    <string>-m</string><string>uvicorn</string><string>backend.main:app</string>
    <string>--host</string><string>0.0.0.0</string>
    <string>--port</string><string>$PORT</string>
  </array>
  <key>WorkingDirectory</key><string>$PROJECT_DIR</string>
  <key>EnvironmentVariables</key><dict>
    <key>ECOSYSTEM_SERVICE_PORT</key><string>$PORT</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$LOGDIR/stdout.log</string>
  <key>StandardErrorPath</key><string>$LOGDIR/stderr.log</string>
</dict></plist>
PLIST_EOF
        launchctl unload "$PLIST" 2>/dev/null || true
        launchctl load "$PLIST"
        log_success "launchd agent $LABEL loaded (port $PORT)"
        log_info "Logs: $LOGDIR/{stdout,stderr}.log"
    else
        log_info "Creating systemd service..."
        sudo tee /etc/systemd/system/openeye.service > /dev/null << EOF
[Unit]
Description=OpenEye Surveillance System
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin"
Environment="ECOSYSTEM_SERVICE_PORT=$PORT"
ExecStart=$PROJECT_DIR/venv/bin/python3 -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
        sudo systemctl daemon-reload
        sudo systemctl enable openeye.service
        log_success "Systemd service created and enabled (port $PORT)"
        log_info "Start with: sudo systemctl start openeye"
    fi
}

# Create launch script
create_launch_script() {
    log_info "Creating launch scripts..."
    
    cd "$PROJECT_DIR"
    
    # Start script
    cat > start.sh << 'EOF'
#!/bin/bash
# Start OpenEye Surveillance System

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Starting OpenEye Surveillance System..."

# Activate virtual environment
source venv/bin/activate

# Start server
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
EOF
    
    # Stop script
    cat > stop.sh << 'EOF'
#!/bin/bash
# Stop OpenEye Surveillance System

echo "Stopping OpenEye Surveillance System..."

# Find and kill the uvicorn process
pkill -f "uvicorn backend.main:app"

echo "OpenEye Surveillance System stopped"
EOF
    
    chmod +x start.sh stop.sh
    
    log_success "Launch scripts created (start.sh, stop.sh)"
}

# Print completion message
print_completion() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   Installation Complete! 🎉                    ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
    echo ""
    log_info "Next steps:"
    echo ""
    echo "  1. Review your configuration in .env file"
    echo "  2. Start the server with: ./start.sh"
    echo "  3. Access the system at: http://localhost:8000"
    echo "  4. Stop the server with: ./stop.sh"
    echo ""
    log_info "Important Files:"
    echo "  - .env: Configuration and secret keys"
    echo "  - surveillance.db: Database file"
    echo "  - data/: Recorded videos and face data"
    echo ""
    log_warn "Security Reminders:"
    echo "  - Never commit .env file to version control"
    echo "  - Change default admin password on first login"
    echo "  - Keep your JWT_SECRET_KEY secure"
    echo "  - Regularly backup your surveillance.db"
    echo ""
    
    if [ "$OS" == "linux" ]; then
        log_info "Systemd Service Commands:"
        echo "  - Start:  sudo systemctl start openeye"
        echo "  - Stop:   sudo systemctl stop openeye"
        echo "  - Status: sudo systemctl status openeye"
        echo "  - Logs:   sudo journalctl -u openeye -f"
        echo ""
    fi
    
    log_info "Documentation:"
    echo "  - User Guide: docs/USER_GUIDE.md"
    echo "  - Setup Guide: docs/setup_guide.md"
    echo "  - API Reference: docs/api_reference.md"
    echo ""
}

# Main installation flow
main() {
    for arg in "$@"; do
        case "$arg" in
            -y|--yes|--non-interactive) NONINTERACTIVE=1 ;;
        esac
    done
    print_banner
    check_root
    detect_os
    
    log_info "Starting installation process..."
    echo ""
    
    check_python
    install_system_deps
    setup_venv
    install_python_deps
    create_directories
    generate_secrets
    setup_database
    build_frontend
    create_launch_script
    create_systemd_service
    
    print_completion
}

# Run main function
main "$@"
