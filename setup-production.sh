#!/bin/bash
# Copyright (c) 2025 Mikel Smart
# OpenEye Surveillance System - Production Setup Script
#
# This script automates the complete production setup:
# 1. Checks system requirements
# 2. Creates virtual environment
# 3. Installs dependencies
# 4. Generates all secret keys automatically
# 5. Initializes database
# 6. Runs migrations
# 7. Builds frontend
# 8. Verifies installation

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
MIN_PYTHON_VERSION="3.9"
OPENCV_DIR="opencv_surveillance"
ENV_FILE="$OPENCV_DIR/.env"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}OpenEye Production Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Change to script directory
cd "$(dirname "$0")"
PROJECT_ROOT=$(pwd)

# Function to compare versions
version_ge() {
    printf '%s\n%s\n' "$2" "$1" | sort -V -C
}

# Function to check Python version
check_python() {
    echo -e "${BLUE}[1/9] Checking Python installation...${NC}"

    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3 not found!${NC}"
        echo "Please install Python 3.9 or higher"
        exit 1
    fi

    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    echo "  Found: Python $PYTHON_VERSION"

    if ! version_ge "$PYTHON_VERSION" "$MIN_PYTHON_VERSION"; then
        echo -e "${RED}❌ Python $MIN_PYTHON_VERSION or higher required${NC}"
        exit 1
    fi

    echo -e "${GREEN}  ✓ Python version OK${NC}"
    echo ""
}

# Function to create virtual environment
create_venv() {
    echo -e "${BLUE}[2/9] Creating virtual environment...${NC}"

    cd "$OPENCV_DIR"

    if [ -d ".venv" ]; then
        echo -e "${YELLOW}  ⚠ Virtual environment already exists${NC}"
        read -p "  Remove and recreate? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf .venv
        else
            echo "  Skipping venv creation"
            cd "$PROJECT_ROOT"
            echo ""
            return
        fi
    # Migrate old venv/ to .venv/
    elif [ -d "venv" ]; then
        echo -e "${YELLOW}  ⚠ Found legacy venv/ — migrating to .venv/${NC}"
        mv venv .venv
    fi

    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
    fi
    echo -e "${GREEN}  ✓ Virtual environment created${NC}"

    cd "$PROJECT_ROOT"
    echo ""
}

# Function to install dependencies
install_dependencies() {
    echo -e "${BLUE}[3/9] Installing Python dependencies...${NC}"

    cd "$OPENCV_DIR"
    source .venv/bin/activate

    echo "  Upgrading pip..."
    pip install --upgrade pip > /dev/null 2>&1

    # PortAudio backs two-way audio via sounddevice. A missing library no longer
    # breaks the install — sounddevice ships pure-Python wheels that never
    # compile, so pip succeeds either way and the feature degrades with a clear
    # message. This check exists so the degradation is noticed NOW, at install
    # time, rather than discovered later when someone tries to use the intercom.
    if ! pkg-config --exists portaudio-2.0 2>/dev/null \
       && [ ! -f /opt/homebrew/lib/libportaudio.dylib ] \
       && [ ! -f /usr/local/lib/libportaudio.dylib ]; then
        echo -e "${YELLOW}  ⚠ PortAudio not found — two-way audio will be disabled.${NC}"
        echo "     The rest of the install is unaffected. To enable it:"
        echo "       ./install-deps.sh"
    fi

    # This is the phase most likely to fail on a fresh Linux box (dlib and
    # OpenCV need system libraries that install-deps.sh provides). Discarding
    # the output left the user with only a downstream import error and no
    # cause, so keep the log and surface the tail.
    echo "  Installing requirements..."
    PIP_LOG="$(mktemp)"
    if ! pip install -r requirements.txt > "$PIP_LOG" 2>&1; then
        echo -e "${RED}  ❌ Dependency installation failed${NC}"
        tail -25 "$PIP_LOG" | sed 's/^/     /'
        echo "     Full log: $PIP_LOG"
        echo "     Missing system libraries are the usual cause — try:"
        echo "       ./install-deps.sh"
        deactivate
        cd "$PROJECT_ROOT"
        exit 1
    fi
    rm -f "$PIP_LOG"

    # Shared ecosystem packages are an OPT-IN add-on, published to PyPI as
    # appecosystem-client / -auth / -ai. Deliberately not installed here:
    # OpenEye runs standalone (guarded imports; the ecosystem routes answer 503
    # without them), so an install that will never join an ecosystem should not
    # carry the dependency. Mirrors opencv_surveillance/scripts/install-local.sh.
    #
    #   Enable later:  pip install -r opencv_surveillance/requirements-ecosystem.txt
    #
    # ECOSYSTEM_FROM_SOURCE=1 installs them EDITABLE from a local checkout, for
    # developing the packages themselves, and fails loudly if it is missing —
    # a silent fallback is how a stale copy gets mistaken for a working install.
    if [ -n "${ECOSYSTEM_FROM_SOURCE:-}" ]; then
        ECO_ROOT="${ECOSYSTEM_BASE_PATH:-$PROJECT_ROOT/..}/appEcosystem"
        if [ ! -d "$ECO_ROOT/auth/python" ]; then
            echo -e "${RED}  ❌ ECOSYSTEM_FROM_SOURCE=1 but no appEcosystem checkout at $ECO_ROOT${NC}"
            deactivate
            cd "$PROJECT_ROOT"
            exit 1
        fi
        echo "  Installing shared ecosystem packages EDITABLE from $ECO_ROOT..."
        if pip install -e "$ECO_ROOT/auth/python" \
                       -e "$ECO_ROOT/packages/ecosystem-client" \
                       -e "$ECO_ROOT/packages/ecosystem-ai" > /dev/null 2>&1; then
            echo -e "${GREEN}  ✓ Ecosystem packages installed (editable, from source)${NC}"
        else
            echo -e "${RED}  ❌ Editable ecosystem install failed${NC}"
            deactivate
            cd "$PROJECT_ROOT"
            exit 1
        fi
    fi

    echo -e "${GREEN}  ✓ Dependencies installed${NC}"

    deactivate
    cd "$PROJECT_ROOT"
    echo ""
}

# Function to generate secret keys
generate_secrets() {
    echo -e "${BLUE}[4/9] Generating secret keys...${NC}"

    if [ -f "$ENV_FILE" ]; then
        echo -e "${YELLOW}  ⚠ .env file already exists${NC}"

        # Check if keys exist
        if grep -q "SECRET_KEY=" "$ENV_FILE" && \
           grep -q "JWT_SECRET_KEY=" "$ENV_FILE" && \
           grep -q "NOTIFICATION_ENCRYPTION_KEY=" "$ENV_FILE"; then
            echo "  All keys already present"
            echo -e "${GREEN}  ✓ Using existing keys${NC}"
            echo ""
            return
        fi
    fi

    cd "$OPENCV_DIR"
    source .venv/bin/activate

    # Generate keys
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")

    # Generate notification encryption key (Fernet)
    NOTIFICATION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

    # Create or update .env file
    cat > .env << EOF
# Security Keys (Generated automatically - DO NOT COMMIT)
SECRET_KEY=$SECRET_KEY
JWT_SECRET_KEY=$JWT_SECRET
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Notification Encryption (Fernet)
NOTIFICATION_ENCRYPTION_KEY=$NOTIFICATION_KEY

# Database (default: SQLite)
DATABASE_URL=sqlite:///./surveillance.db

# CORS
CORS_ORIGINS=http://localhost:8000,http://localhost:3000

# Features (all enabled by default)
ENABLE_MOTION_DETECTION=true
ENABLE_FACE_RECOGNITION=true
ENABLE_RECORDING=true

# Logging
LOG_LEVEL=INFO
EOF

    echo -e "${GREEN}  ✓ Secret keys generated${NC}"
    echo -e "${CYAN}  → Keys saved to: opencv_surveillance/.env${NC}"

    deactivate
    cd "$PROJECT_ROOT"
    echo ""
}

# Function to initialize database
init_database() {
    echo -e "${BLUE}[5/9] Initializing database...${NC}"

    cd "$OPENCV_DIR"
    source .venv/bin/activate

    # Check if database exists
    if [ -f "surveillance.db" ]; then
        echo -e "${YELLOW}  ⚠ Database already exists${NC}"
        echo "  Skipping initialization"
    else
        echo "  Creating database tables..."
        # Database will be created automatically on first run
        echo -e "${GREEN}  ✓ Database will be initialized on first run${NC}"
    fi

    deactivate
    cd "$PROJECT_ROOT"
    echo ""
}

# Function to run migrations
run_migrations() {
    echo -e "${BLUE}[6/9] Running database migrations...${NC}"

    cd "$OPENCV_DIR"
    source .venv/bin/activate

    # Check for migration scripts
    MIGRATIONS=$(find scripts -name "migrate_*.py" 2>/dev/null | sort -V)

    if [ -z "$MIGRATIONS" ]; then
        echo "  No migrations found"
    else
        echo "  Found $(echo "$MIGRATIONS" | wc -l) migration(s)"

        # Run each migration
        for migration in $MIGRATIONS; do
            MIGRATION_NAME=$(basename "$migration")
            echo "  Running: $MIGRATION_NAME"
            python3 "$migration" > /dev/null 2>&1 || {
                echo -e "${YELLOW}    ⚠ Migration may have already run${NC}"
            }
        done
    fi

    echo -e "${GREEN}  ✓ Migrations complete${NC}"

    deactivate
    cd "$PROJECT_ROOT"
    echo ""
}

# Function to build frontend
build_frontend() {
    echo -e "${BLUE}[7/9] Building frontend...${NC}"

    cd "$OPENCV_DIR/frontend"

    # npm is not a Python dependency, so it is routinely absent on a server
    # that installed everything else fine. Check before using it.
    if ! command -v npm &> /dev/null; then
        echo -e "${RED}  ❌ npm not found — cannot build the web UI.${NC}"
        echo "     Install Node.js 18+ and re-run, e.g.:"
        echo "       Debian/Ubuntu: sudo apt-get install -y nodejs npm"
        echo "       Alpine:        apk add nodejs npm"
        echo "       macOS:         brew install node"
        FRONTEND_OK=false
        cd "$PROJECT_ROOT"
        echo ""
        return
    fi

    # Output goes to a log rather than /dev/null: on failure the reason is the
    # only thing that helps, and discarding it turned every frontend problem
    # into a silent success.
    BUILD_LOG="$(mktemp)"
    if [ ! -d "node_modules" ]; then
        echo "  Installing Node.js dependencies..."
        if ! npm install > "$BUILD_LOG" 2>&1; then
            echo -e "${RED}  ❌ npm install failed${NC}"
            tail -20 "$BUILD_LOG" | sed 's/^/     /'
            echo "     Full log: $BUILD_LOG"
            FRONTEND_OK=false
            cd "$PROJECT_ROOT"
            echo ""
            return
        fi
    fi

    echo "  Building production bundle..."
    if ! npm run build > "$BUILD_LOG" 2>&1; then
        echo -e "${RED}  ❌ npm run build failed${NC}"
        tail -20 "$BUILD_LOG" | sed 's/^/     /'
        echo "     Full log: $BUILD_LOG"
        FRONTEND_OK=false
        cd "$PROJECT_ROOT"
        echo ""
        return
    fi

    # A zero exit from a build tool is not proof it emitted anything.
    if [ ! -f "dist/index.html" ]; then
        echo -e "${RED}  ❌ Build reported success but dist/index.html is missing${NC}"
        FRONTEND_OK=false
        cd "$PROJECT_ROOT"
        echo ""
        return
    fi

    rm -f "$BUILD_LOG"
    echo -e "${GREEN}  ✓ Frontend built successfully${NC}"
    echo -e "${CYAN}  → Output: opencv_surveillance/frontend/dist/${NC}"

    cd "$PROJECT_ROOT"
    echo ""
}

# Function to create directories
create_directories() {
    echo -e "${BLUE}[8/9] Creating required directories...${NC}"

    cd "$OPENCV_DIR"

    # Create directories if they don't exist
    mkdir -p data/snapshots
    mkdir -p data/thumbnails
    mkdir -p faces
    mkdir -p recordings
    mkdir -p models

    echo -e "${GREEN}  ✓ Directories created${NC}"
    echo "  → data/snapshots/"
    echo "  → data/thumbnails/"
    echo "  → faces/"
    echo "  → recordings/"
    echo "  → models/"

    cd "$PROJECT_ROOT"
    echo ""
}

# Function to verify installation
verify_installation() {
    echo -e "${BLUE}[9/9] Verifying installation...${NC}"

    cd "$OPENCV_DIR"
    source .venv/bin/activate

    # Check critical imports
    echo "  Testing Python imports..."
    python3 -c "
import fastapi
import cv2
import face_recognition
import sqlalchemy
from cryptography.fernet import Fernet
print('  ✓ All critical imports OK')
" || {
        echo -e "${RED}  ❌ Import verification failed${NC}"
        deactivate
        cd "$PROJECT_ROOT"
        exit 1
    }

    # Check frontend build
    if [ ! -f "frontend/dist/index.html" ]; then
        echo -e "${RED}  ❌ Frontend build not found (frontend/dist/index.html)${NC}"
        FRONTEND_OK=false
    else
        echo "  ✓ Frontend build verified"
    fi

    # Check .env file — without it there is no JWT secret, so logins fail.
    if [ ! -f ".env" ]; then
        echo -e "${RED}  ❌ .env file missing — the app cannot start${NC}"
        ENV_OK=false
    else
        echo "  ✓ Environment configuration verified"
    fi

    deactivate
    cd "$PROJECT_ROOT"

    if [ "$FRONTEND_OK" = true ] && [ "$ENV_OK" = true ]; then
        echo -e "${GREEN}  ✓ Installation verified${NC}"
    else
        echo -e "${YELLOW}  ⚠ Installation incomplete — see above${NC}"
    fi
    echo ""
}

# Function to display summary
display_summary() {
    # Do not claim success when a required piece is missing: an install that
    # says "Complete!" and then serves a blank page is the worst outcome.
    if [ "$FRONTEND_OK" != true ] || [ "$ENV_OK" != true ]; then
        echo -e "${RED}========================================${NC}"
        echo -e "${RED}✗ OpenEye Setup INCOMPLETE${NC}"
        echo -e "${RED}========================================${NC}"
        echo ""
        [ "$FRONTEND_OK" != true ] && \
            echo -e "  ${RED}•${NC} The web UI was not built. The API will start, but"
        [ "$FRONTEND_OK" != true ] && \
            echo    "    http://localhost:8000 will not serve the interface."
        [ "$ENV_OK" != true ] && \
            echo -e "  ${RED}•${NC} .env is missing — the app cannot start."
        echo ""
        echo "  Fix the item(s) above and re-run ./setup-production.sh"
        echo ""
        return 1
    fi

    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✓ OpenEye Setup Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${CYAN}Next Steps:${NC}"
    echo ""
    echo "  1. Start the server:"
    echo -e "     ${YELLOW}./start-local.sh${NC}"
    echo ""
    echo "  2. Open your browser:"
    echo -e "     ${YELLOW}http://localhost:8000${NC}"
    echo ""
    echo "  3. Complete first-run setup:"
    echo "     • Create admin account"
    echo "     • Add cameras"
    echo "     • Configure notifications (optional)"
    echo ""
    echo -e "${CYAN}Useful Commands:${NC}"
    echo ""
    echo "  Stop server:    ./stop-server.sh"
    echo "  Kill server:    ./kill-server.sh"
    echo "  Deploy Docker:  ./deploy.sh"
    echo ""
    echo -e "${CYAN}Documentation:${NC}"
    echo ""
    echo "  User Guide:     opencv_surveillance/docs/USER_GUIDE.md"
    echo "  API Docs:       opencv_surveillance/docs/API_DOCUMENTATION.md"
    echo "  Systemd Setup:  opencv_surveillance/docs/LINUX_SYSTEMD_SERVICE.md"
    echo ""
    echo -e "${YELLOW}⚠ IMPORTANT:${NC}"
    echo "  • Never commit the .env file to version control"
    echo "  • Keep your secret keys secure"
    echo "  • Change default admin password on first login"
    echo ""
}

# Main execution
main() {
    # Tracked across phases so the final summary reflects what actually
    # happened. This script does not use `set -e` — phases are expected to
    # continue after a soft failure — so success has to be recorded, not assumed.
    FRONTEND_OK=true
    ENV_OK=true

    check_python
    create_venv
    install_dependencies
    generate_secrets
    create_directories
    init_database
    run_migrations
    build_frontend
    verify_installation
    display_summary
}

# Run main function, propagating a non-zero exit when the install is incomplete
# so callers and CI can tell the difference.
main
exit $?
