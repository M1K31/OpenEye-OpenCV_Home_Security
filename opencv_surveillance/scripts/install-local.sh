#!/bin/bash
# OpenEye Surveillance System - Local Installation Script
# This script automates the complete installation process for a local machine
# Supports macOS and Linux
#
# Environment variables:
#   OPENEYE_NONINTERACTIVE=1  Skip prompts (also: ECOSYSTEM_NONINTERACTIVE, CI, -y/--yes)
#   OPENEYE_SKIP_SERVICE=1    Do not create/register an auto-start service
#   OPENEYE_VENV=<path>       Override the venv location (default: ~/.local/share/openeye/venv)
#   OPENEYE_DATA_ROOT=<path>  Override the data root (default: ~/.local/share/openeye)
#   OPENEYE_RECREATE_VENV=1   Delete and rebuild the venv instead of reusing it

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

# Runtime venv lives on the INTERNAL disk. The repo may sit on an external
# volume (/Volumes/...); a force-unmount there makes mmap'd C-extensions
# (opencv, av, face_recognition) fault with SIGBUS and kills the daemon.
VENV="${OPENEYE_VENV:-$HOME/.local/share/openeye/venv}"

# The service must not depend on the repo volume. macOS TCC denies launchd-spawned
# binaries access to /Volumes unless individually granted, and an external volume can
# vanish mid-run. Code is snapshotted into APP_DIR; db + media live under DATA_ROOT.
DATA_ROOT="${OPENEYE_DATA_ROOT:-$HOME/.local/share/openeye}"
APP_DIR="$DATA_ROOT/app"

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
            rsync \
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
    log_info "Creating virtual environment at $VENV (internal disk)..."
    mkdir -p "$(dirname "$VENV")"
    if [ -d "$VENV" ]; then
        # Idempotent default: keep the existing venv unless asked to recreate.
        if [ -n "${OPENEYE_RECREATE_VENV:-}" ]; then
            log_info "Removing existing virtual environment..."
            rm -rf "$VENV"
            $PYTHON_CMD -m venv "$VENV"
        else
            log_info "Using existing virtual environment"
        fi
    else
        $PYTHON_CMD -m venv "$VENV"
    fi
    source "$VENV/bin/activate"

    log_success "Virtual environment ready"
}

# Install Python dependencies
install_python_deps() {
    log_info "Installing Python dependencies..."
    
    cd "$PROJECT_DIR"
    
    # Activate virtual environment
    source "$VENV/bin/activate"
    
    # Upgrade pip
    log_info "Upgrading pip..."
    pip install --upgrade pip setuptools wheel

    # Ensure ffmpeg BEFORE pip: aiortc->av (WebRTC two-way audio) builds against
    # it. Without a usable ffmpeg the av wheel fails and would abort the install.
    #
    # PyAV's native build does NOT support ffmpeg 8 yet — it needs ffmpeg 7. On
    # macOS `brew install ffmpeg` installs v8, so a plain `command -v ffmpeg` may
    # "find" ffmpeg yet still break the av build. Prefer the versioned ffmpeg@7
    # formula and expose it to the build via PKG_CONFIG_PATH/PATH.
    if [ "$(uname -s)" = "Darwin" ]; then
        if command -v brew >/dev/null 2>&1; then
            if ! brew list ffmpeg@7 >/dev/null 2>&1; then
                log_info "Installing ffmpeg@7 (PyAV/WebRTC needs ffmpeg 7, not 8)..."
                brew install ffmpeg@7 || log_warn "brew install ffmpeg@7 failed"
            fi
            FFMPEG7_PREFIX="$(brew --prefix ffmpeg@7 2>/dev/null)"
            if [ -n "$FFMPEG7_PREFIX" ] && [ -d "$FFMPEG7_PREFIX" ]; then
                # ffmpeg@7 is keg-only — surface it for the av build and at runtime.
                export PKG_CONFIG_PATH="$FFMPEG7_PREFIX/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
                export PATH="$FFMPEG7_PREFIX/bin:$PATH"
                log_info "Using ffmpeg@7 at $FFMPEG7_PREFIX for the av/WebRTC build"
            else
                log_warn "ffmpeg@7 unavailable; two-way audio (WebRTC) may be disabled."
            fi
        else
            log_warn "Homebrew not found — install ffmpeg@7 manually for two-way audio; continuing (feature will be disabled)."
        fi
    elif ! command -v ffmpeg >/dev/null 2>&1; then
        log_warn "ffmpeg not found — required to build the WebRTC stack (av/aiortc)."
        if command -v apt-get >/dev/null 2>&1; then
            log_info "Installing ffmpeg via apt..."; sudo apt-get install -y ffmpeg || log_warn "apt install ffmpeg failed"
        else
            log_warn "Install ffmpeg manually for two-way audio; continuing (feature will be disabled)."
        fi
    fi

    # Install requirements. If a native build (e.g. av without ffmpeg) fails,
    # retry without the WebRTC stack so the rest of the app still installs —
    # the backend degrades gracefully (WEBRTC_AVAILABLE=False).
    # The base set only. Object detection and the ecosystem libraries are
    # separate files, because most installations never enable either and object
    # detection alone pulls several gigabytes (torch and, on Linux, the CUDA
    # stack it depends on). Both are reported to the user at the end.
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

    # Cyber Agents — an independent project that also integrates with the
    # ecosystem. Installed alongside the shared packages so its security agents
    # and the AegisSIEM daemon are available to OpenEye. Runtime only: the daemon
    # is NOT started here (launchd owns it; a second start vector would let two
    # daemons share one SQLite state dir). Never fatal.
    CYBER="${CYBER_AGENTS_PATH:-${ECOSYSTEM_BASE_PATH:-$PROJECT_DIR/../..}/CybersecurityTeam/cyber-agents}"
    if [ -n "${OPENEYE_SKIP_CYBER_AGENTS:-}" ]; then
        log_info "OPENEYE_SKIP_CYBER_AGENTS=1 — skipping cyber-agents setup"
    elif [ -x "$CYBER/scripts/install-local.sh" ]; then
        log_info "Preparing cyber-agents runtime (opt-in; enable its service with --plist)..."
        ECOSYSTEM_BASE_PATH="${ECOSYSTEM_BASE_PATH:-$PROJECT_DIR/../..}" \
            "$CYBER/scripts/install-local.sh" >/dev/null 2>&1 \
            && log_success "cyber-agents runtime ready (not started)" \
            || log_info "cyber-agents setup skipped (non-fatal)"
    else
        log_info "cyber-agents not present at $CYBER — skipping (optional component)"
    fi

    log_success "Python dependencies installed"
}

# Copy the runnable application to the internal disk. This is a snapshot: changes in
# the repo require re-running this installer, the same non-editable tradeoff the
# ecosystem registry already makes.
# A launchd agent has no application bundle, so macOS denies it camera access
# and never shows a permission prompt. USB discovery therefore returns nothing
# until the user grants access to a process that CAN prompt. Nothing in this
# installer can grant it, so say so plainly instead of shipping a service that
# silently finds no cameras.
warn_macos_camera_permission() {
    [ "$(uname -s)" = "Darwin" ] || return 0

    local CAMERAS
    CAMERAS=$(system_profiler SPCameraDataType 2>/dev/null | grep -c ":" || echo 0)
    [ "$CAMERAS" -gt 0 ] || return 0

    echo ""
    log_warn "macOS: USB / built-in cameras need camera permission"
    echo "  macOS only lets a process a user launched from a Terminal open the"
    echo "  camera. A background/launchd service can't, so USB camera discovery"
    echo "  will find nothing until access is granted."
    echo ""
    echo "  Start OpenEye from a Terminal window so it can request access:"
    echo "    cd \"$APP_DIR\" && ./start.sh"
    echo ""
    echo "  Approve the macOS camera prompt when it appears, then scan for USB"
    echo "  cameras in the UI. If no prompt appears, enable your terminal app"
    echo "  under System Settings > Privacy & Security > Camera, then restart."
    echo ""
}

# Build OpenEye.app on macOS. This is what makes local cameras usable without the
# Terminal workaround: the bundle embeds the interpreter and carries its own
# NSCameraUsageDescription, so macOS can attribute the camera grant to OpenEye
# instead of to Apple's python binary. Non-fatal — a failure here just means the
# user falls back to running ./start.sh from a Terminal.
build_macos_app() {
    # macOS only, and purely ADDITIVE: the terminal workflow (./start.sh, ./stop.sh,
    # ./restart.sh --foreground) and the Linux/systemd path are unchanged and remain
    # fully supported. Set OPENEYE_SKIP_APP_BUNDLE=1 to opt out entirely.
    [ "$(uname -s)" = "Darwin" ] || return 0
    [ "${OPENEYE_SKIP_APP_BUNDLE:-0}" = "1" ] && {
        log_info "Skipping OpenEye.app (OPENEYE_SKIP_APP_BUNDLE=1); use ./start.sh from a Terminal."
        return 0
    }
    local builder="$SCRIPT_DIR/build-macos-app.sh"
    [ -x "$builder" ] || return 0

    log_info "Building OpenEye.app (gives the camera permission a home)..."
    if OPENEYE_DATA_ROOT="$DATA_ROOT" OPENEYE_VENV="$VENV" PORT="$PORT" \
        "$builder" >/dev/null 2>&1; then
        log_success "OpenEye.app created in ~/Applications"
        echo "  Launch it from ~/Applications (or Spotlight) and approve the camera"
        echo "  prompt once — the grant then persists across restarts."
    else
        log_warn "Could not build OpenEye.app (continuing)."
        echo "  Run scripts/build-macos-app.sh manually, or start OpenEye from a"
        echo "  Terminal with ./start.sh so the camera can be authorised."
    fi
}

sync_app_to_internal() {
    log_info "Syncing application code to $APP_DIR (internal disk)..."
    mkdir -p "$APP_DIR"

    if command -v rsync >/dev/null 2>&1; then
        rsync -a --delete \
            --exclude 'venv/' --exclude '.venv/' \
            --exclude 'frontend/node_modules/' \
            --exclude '__pycache__/' --exclude '*.pyc' \
            --exclude '.git/' \
            --exclude 'recordings/' --exclude 'faces/' --exclude 'data/' \
            --exclude 'surveillance.db*' \
            --exclude '.env' \
            "$PROJECT_DIR/" "$APP_DIR/"
    elif command -v tar >/dev/null 2>&1; then
        log_warn "rsync not found; falling back to a tar-based copy."
        rm -rf "$APP_DIR"
        mkdir -p "$APP_DIR"
        (cd "$PROJECT_DIR" && tar \
            --exclude='venv' --exclude='.venv' \
            --exclude='frontend/node_modules' \
            --exclude='__pycache__' --exclude='*.pyc' \
            --exclude='.git' \
            --exclude='recordings' --exclude='faces' --exclude='data' \
            --exclude='surveillance.db*' \
            --exclude='.env' \
            -cf - .) | (cd "$APP_DIR" && tar -xf -)
    else
        log_error "Neither rsync nor tar is available — cannot sync the application to $APP_DIR."
        log_info "Install rsync (e.g. 'apt-get install rsync') and re-run this installer."
        exit 1
    fi

    log_success "Application synced to $APP_DIR"
}

# Generate secret keys
generate_secrets() {
    cd "$PROJECT_DIR"

    # Data directories are needed regardless of whether .env is regenerated.
    mkdir -p "$DATA_ROOT/data/snapshots" "$DATA_ROOT/data/thumbnails" \
             "$DATA_ROOT/recordings" "$DATA_ROOT/faces"

    # Preserve an existing .env (and thus JWT_SECRET_KEY / ADMIN_TOKEN) across
    # reinstalls, e.g. uninstall-keep-data.sh -> install-local.sh. Regenerating
    # unconditionally would mint new secrets every run and invalidate exactly
    # the sessions/tokens a keep-data reinstall promises to preserve. Matches
    # the pattern AI-for-Survival's bin/install-local.sh uses for its env file.
    if [[ -f "$PROJECT_DIR/.env" ]]; then
        log_info ".env already exists — preserving existing secret keys (not regenerating)."
        # Close the world-readable-secrets exposure even on the preserve path:
        # older installs (pre-fix) may have left .env at 0644, and secrets must
        # be owner-only regardless of whether this run generated them.
        chmod 600 "$PROJECT_DIR/.env"
        return
    fi

    log_info "Generating secret keys..."

    source "$VENV/bin/activate"

    # Generate the primary app secret (used for sessions and, by default, JWTs).
    SECRET_KEY_VAL=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")

    # Generate a SEPARATE JWT secret (security isolation from SECRET_KEY).
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")

    # Generate admin token
    ADMIN_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

    # Create .env file. Truncate and lock it down to owner-only BEFORE any
    # secret is written, so SECRET_KEY/JWT_SECRET_KEY/ADMIN_TOKEN never exist
    # in a world-readable file, even momentarily (umask 022 would otherwise
    # yield 0644 for the brief window between creation and a trailing chmod).
    : > .env
    chmod 600 .env
    cat > .env << EOF
# OpenEye Surveillance System Configuration
# Generated on $(date)

# Security Keys - KEEP THESE SECRET!
# SECRET_KEY is the primary app secret; auth.py reads it at import, so start.sh
# exports this file into the environment before launching uvicorn.
SECRET_KEY=$SECRET_KEY_VAL
JWT_SECRET_KEY=$JWT_SECRET
ADMIN_TOKEN=$ADMIN_TOKEN

# Absolute internal paths so the service never touches the repo volume.
DATABASE_URL=sqlite:///$DATA_ROOT/surveillance.db
OPENEYE_DATA_DIR=$DATA_ROOT/data
OPENEYE_RECORDINGS_DIR=$DATA_ROOT/recordings
OPENEYE_SNAPSHOTS_DIR=$DATA_ROOT/data/snapshots
OPENEYE_THUMBNAILS_DIR=$DATA_ROOT/data/thumbnails
OPENEYE_FACES_DIR=$DATA_ROOT/faces

# Server Configuration
HOST=0.0.0.0
PORT=8200

# CORS Settings (adjust for production)
CORS_ORIGINS=http://localhost:8200,http://localhost:3000

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
    source "$VENV/bin/activate"
    
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
    # An unsupervised install does not survive a reboot, so a service is the
    # default. Opt out with OPENEYE_SKIP_SERVICE=1 (e.g. for CI or a dev box
    # that starts the app by hand with ./start.sh).
    if [ -n "${OPENEYE_SKIP_SERVICE:-}" ]; then
        log_info "OPENEYE_SKIP_SERVICE=1 — not creating an auto-start service."
        return
    fi
    local svc_default="Y"
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
    <string>$VENV/bin/python3</string>
    <string>-m</string><string>uvicorn</string><string>backend.main:app</string>
    <string>--host</string><string>0.0.0.0</string>
    <string>--port</string><string>$PORT</string>
  </array>
  <key>WorkingDirectory</key><string>$APP_DIR</string>
  <key>EnvironmentVariables</key><dict>
    <key>ECOSYSTEM_SERVICE_PORT</key><string>$PORT</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <!-- Restart only on a CRASH (non-zero exit), not on a clean stop. Unconditional
       KeepAlive respawned the service after intentional stops and hid crashes. -->
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>StandardOutPath</key><string>$LOGDIR/stdout.log</string>
  <key>StandardErrorPath</key><string>$LOGDIR/stderr.log</string>
</dict></plist>
PLIST_EOF
        launchctl unload "$PLIST" 2>/dev/null || true
        launchctl load "$PLIST"
        log_success "launchd agent $LABEL loaded (port $PORT)"
        log_info "Logs: $LOGDIR/{stdout,stderr}.log"
        # (camera-permission note is printed once for all install modes near the end)
    else
        log_info "Creating systemd service..."
        sudo tee /etc/systemd/system/openeye.service > /dev/null << EOF
[Unit]
Description=OpenEye Surveillance System
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$VENV/bin"
Environment="ECOSYSTEM_SERVICE_PORT=$PORT"
ExecStart=$VENV/bin/python3 -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT
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

# Run from the internal-disk snapshot, not the script's own location — the
# service must not depend on the repo volume (see install-local.sh).
cd "@@APP_DIR@@"

echo "Starting OpenEye Surveillance System..."

# Activate virtual environment (runtime venv lives on the internal disk —
# see opencv_surveillance/scripts/install-local.sh for why).
source "@@VENV@@/bin/activate"

# Load .env into the environment BEFORE importing the app. backend/core/auth.py
# reads SECRET_KEY / JWT_SECRET_KEY at import time, which happens before main.py
# calls load_dotenv(); exporting here guarantees os.getenv() sees them regardless
# of import order (otherwise the app silently falls back to a weak dev secret).
set -a
[ -f .env ] && . ./.env
set +a

# Quiet the FFmpeg encoder's benign, per-frame "mpeg4 Invalid pts" WARNINGS (the
# mp4 still writes fine). 16 = AV_LOG_ERROR: real errors still show, warnings don't.
export OPENCV_FFMPEG_LOGLEVEL=16

# Start server (OpenEye's documented port is 8200; 8000 belongs to AI-for-Survival).
# -u = unbuffered stdout/stderr so foreground logs stream live (otherwise print()
# output block-buffers and the app looks "stuck" while it is actually running).
python3 -u -m uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8200}"
EOF
    # Portable placeholder substitution. Do NOT use `sed -i`: BSD/macOS requires a
    # detached backup suffix (-i '') while GNU/Linux forbids it, and this installer
    # supports both. Redirect-and-move works identically everywhere.
    sed -e "s|@@VENV@@|$VENV|g" -e "s|@@APP_DIR@@|$APP_DIR|g" start.sh > start.sh.tmp \
        && mv start.sh.tmp start.sh
    chmod +x start.sh

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
    echo "     (on macOS, run it from a Terminal window so the camera works — see below)"
    echo "  3. Access the system at: http://localhost:${PORT:-8200}"
    echo "  4. Stop the server with: ./stop.sh"
    echo ""
    # Always surface the macOS camera-permission note (not just for the --plist
    # service), since USB cameras silently fail without it.
    warn_macos_camera_permission
    build_macos_app
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
    # Both optional sets are named here rather than left to be discovered. The
    # base install deliberately omits them, and someone who wanted object
    # detection would otherwise conclude it was broken rather than not installed.
    echo ""
    echo "Optional add-ons (not installed):"
    echo "  Object detection (YOLO — several GB, needs ENABLE_OBJECT_DETECTION=true):"
    echo "      source \"$VENV_DIR/bin/activate\" && pip install -r requirements-object-detection.txt"
    echo "  appEcosystem integration (registry, events, peer auth):"
    echo "      source \"$VENV_DIR/bin/activate\" && pip install -r requirements-ecosystem.txt"

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
    sync_app_to_internal
    cp "$PROJECT_DIR/.env" "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
    create_launch_script
    # create_launch_script only (re)writes start.sh/stop.sh into $PROJECT_DIR (it
    # already ran after the sync above), so mirror the freshly generated,
    # already-resolved scripts into $APP_DIR too — otherwise a manual
    # $APP_DIR/start.sh would still carry whatever start.sh existed at sync time.
    cp "$PROJECT_DIR/start.sh" "$APP_DIR/start.sh"
    cp "$PROJECT_DIR/stop.sh" "$APP_DIR/stop.sh"
    chmod +x "$APP_DIR/start.sh" "$APP_DIR/stop.sh"
    create_systemd_service
    
    print_completion
}

# Run main function
main "$@"
