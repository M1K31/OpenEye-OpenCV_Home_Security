#!/bin/bash
# Copyright (c) 2025 Mikel Smart
# OpenEye — Smart Dependency Installer
#
# Detects OS/architecture and installs optional heavy dependencies
# (dlib, torch, ultralytics, face_recognition, aiortc, pyaudio)
# using the preferred method for each platform.
#
# Falls back through multiple install strategies:
#   1. System package manager (apt, brew)
#   2. pip install (pre-built wheel)
#   3. pip install from source (compile)
#
# If a dependency cannot be installed, shows affected features
# and lets the user choose to continue or cancel.

set -euo pipefail

# ── Colors ────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── Configuration ─────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OPENCV_DIR="$SCRIPT_DIR/opencv_surveillance"
VENV_DIR="$OPENCV_DIR/.venv"
PIP="$VENV_DIR/bin/pip"
PYTHON="$VENV_DIR/bin/python3"

# Track what we couldn't install
declare -a FAILED_DEPS=()
declare -a DISABLED_FEATURES=()

# ── OS / Architecture Detection ───────────────────────────────────────
detect_platform() {
    OS="$(uname -s)"
    ARCH="$(uname -m)"

    case "$OS" in
        Darwin)
            PLATFORM="macos"
            if command -v brew &>/dev/null; then
                PKG_MGR="brew"
            else
                PKG_MGR="none"
            fi
            ;;
        Linux)
            PLATFORM="linux"
            if command -v apt-get &>/dev/null; then
                PKG_MGR="apt"
            elif command -v dnf &>/dev/null; then
                PKG_MGR="dnf"
            elif command -v pacman &>/dev/null; then
                PKG_MGR="pacman"
            else
                PKG_MGR="none"
            fi
            ;;
        *)
            PLATFORM="unknown"
            PKG_MGR="none"
            ;;
    esac

    IS_ARM=false
    case "$ARCH" in
        aarch64|arm64|armv7l|armv6l) IS_ARM=true ;;
    esac

    IS_PI=false
    if [ -f /proc/device-tree/model ] && grep -qi "raspberry" /proc/device-tree/model 2>/dev/null; then
        IS_PI=true
    fi

    echo -e "${BLUE}Platform Detection${NC}"
    echo "  OS:           $OS"
    echo "  Architecture: $ARCH"
    echo "  Package Mgr:  $PKG_MGR"
    echo "  ARM:          $IS_ARM"
    echo "  Raspberry Pi: $IS_PI"
    echo ""
}

# ── Helpers ───────────────────────────────────────────────────────────
log_ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
log_warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
log_fail() { echo -e "  ${RED}✗${NC} $1"; }
log_info() { echo -e "  ${CYAN}→${NC} $1"; }

check_venv() {
    if [ ! -f "$PIP" ]; then
        echo -e "${RED}Error: Virtual environment not found at $VENV_DIR${NC}"
        echo "Run setup-production.sh first, or create one:"
        echo "  cd opencv_surveillance && python3 -m venv .venv"
        exit 1
    fi
}

# Check if a Python package is importable
is_installed() {
    "$PYTHON" -c "import $1" 2>/dev/null
}

# ── System-level prerequisite installers ──────────────────────────────
install_cmake() {
    echo -e "${BLUE}Installing cmake (required to build dlib)...${NC}"
    case "$PKG_MGR" in
        apt)
            sudo apt-get update -qq && sudo apt-get install -y cmake build-essential
            ;;
        brew)
            brew install cmake
            ;;
        dnf)
            sudo dnf install -y cmake gcc-c++ make
            ;;
        pacman)
            sudo pacman -S --noconfirm cmake base-devel
            ;;
        *)
            log_fail "No package manager — install cmake manually: https://cmake.org/download/"
            return 1
            ;;
    esac
}

install_portaudio() {
    echo -e "${BLUE}Installing PortAudio (required for pyaudio)...${NC}"
    case "$PKG_MGR" in
        apt)
            sudo apt-get update -qq && sudo apt-get install -y portaudio19-dev python3-pyaudio
            ;;
        brew)
            brew install portaudio
            ;;
        dnf)
            sudo dnf install -y portaudio-devel
            ;;
        pacman)
            sudo pacman -S --noconfirm portaudio
            ;;
        *)
            log_fail "No package manager — install PortAudio manually: http://www.portaudio.com/download.html"
            return 1
            ;;
    esac
}

# ── Dependency Installers (multi-strategy) ────────────────────────────

install_dlib() {
    local dep_name="dlib"
    local features="Face Recognition, Face Clustering"

    echo ""
    echo -e "${BOLD}[$dep_name]${NC} — required for: $features"

    # Already installed?
    if is_installed dlib; then
        log_ok "dlib already installed"
        return 0
    fi

    # Raspberry Pi warning
    if [ "$IS_PI" = true ]; then
        echo ""
        log_warn "dlib compilation on Raspberry Pi takes 2+ hours and may fail on Pi 3 (insufficient RAM)."
        log_warn "Pi 4 with 4GB+ RAM is recommended. Swap space of 2GB+ helps."
        echo ""
        read -rp "  Attempt dlib install on Pi? (y/N): " choice
        if [[ ! "$choice" =~ ^[Yy]$ ]]; then
            FAILED_DEPS+=("$dep_name")
            DISABLED_FEATURES+=("$features")
            return 1
        fi
    fi

    # Strategy 1: System package manager (Linux only — no dlib in brew)
    if [ "$PKG_MGR" = "apt" ]; then
        log_info "Trying: apt install python3-dlib..."
        if sudo apt-get install -y python3-dlib 2>/dev/null; then
            # Verify it's importable in our venv (apt installs to system python)
            if is_installed dlib; then
                log_ok "dlib installed via apt"
                return 0
            fi
            log_warn "apt installed dlib to system Python, not venv — trying pip next"
        fi
    fi

    # Strategy 2: pip pre-built wheel
    log_info "Trying: pip install dlib (pre-built wheel)..."
    if "$PIP" install "dlib>=19.24.0" 2>/dev/null; then
        log_ok "dlib installed via pip wheel"
        return 0
    fi

    # Strategy 3: Ensure cmake, then pip install from source
    log_info "No pre-built wheel available. Attempting source build..."
    if ! command -v cmake &>/dev/null; then
        install_cmake || {
            log_fail "Cannot install cmake — dlib source build not possible"
            FAILED_DEPS+=("$dep_name")
            DISABLED_FEATURES+=("$features")
            return 1
        }
    fi

    log_info "Building dlib from source (this may take 10-120 minutes)..."
    if "$PIP" install "dlib>=19.24.0" --no-binary dlib 2>&1 | tail -5; then
        log_ok "dlib built from source"
        return 0
    fi

    log_fail "dlib installation failed"
    FAILED_DEPS+=("$dep_name")
    DISABLED_FEATURES+=("$features")
    return 1
}

install_face_recognition() {
    local dep_name="face_recognition"
    local features="Face Recognition, Face Detection, Face Clustering"

    echo ""
    echo -e "${BOLD}[$dep_name]${NC} — required for: $features"

    if is_installed face_recognition; then
        log_ok "face_recognition already installed"
        return 0
    fi

    # face_recognition requires dlib
    if ! is_installed dlib; then
        log_warn "face_recognition requires dlib (not installed)"
        FAILED_DEPS+=("$dep_name")
        DISABLED_FEATURES+=("$features")
        return 1
    fi

    # Strategy 1: pip install
    log_info "Trying: pip install face_recognition..."
    if "$PIP" install "face_recognition>=1.3.0" 2>/dev/null; then
        log_ok "face_recognition installed via pip"
        return 0
    fi

    log_fail "face_recognition installation failed"
    FAILED_DEPS+=("$dep_name")
    DISABLED_FEATURES+=("$features")
    return 1
}

install_torch() {
    local dep_name="torch"
    local features="YOLO Object Detection (vehicles, animals, packages)"

    echo ""
    echo -e "${BOLD}[$dep_name + torchvision]${NC} — required for: $features"

    if is_installed torch; then
        log_ok "torch already installed"
        return 0
    fi

    # Pi / ARM warning
    if [ "$IS_ARM" = true ]; then
        local torch_size="~800MB"
        if [ "$IS_PI" = true ]; then
            torch_size="~800MB (inference will be very slow on Pi)"
        fi
        echo ""
        log_warn "torch download is $torch_size on ARM."
        read -rp "  Install torch on this ARM device? (y/N): " choice
        if [[ ! "$choice" =~ ^[Yy]$ ]]; then
            FAILED_DEPS+=("$dep_name")
            DISABLED_FEATURES+=("$features")
            return 1
        fi
    fi

    # Strategy 1: pip install (PyTorch has ARM wheels for Linux)
    log_info "Trying: pip install torch torchvision..."
    if [ "$IS_ARM" = true ] && [ "$PLATFORM" = "linux" ]; then
        # Use PyTorch's ARM-specific index for Linux ARM
        if "$PIP" install torch torchvision --index-url https://download.pytorch.org/whl/cpu 2>/dev/null; then
            log_ok "torch installed via PyTorch CPU wheels (ARM)"
            return 0
        fi
    fi

    if "$PIP" install "torch>=2.0.0" "torchvision>=0.15.0" 2>/dev/null; then
        log_ok "torch + torchvision installed via pip"
        return 0
    fi

    # Strategy 2: CPU-only wheels (smaller download)
    log_info "Trying CPU-only torch wheels..."
    if "$PIP" install torch torchvision --index-url https://download.pytorch.org/whl/cpu 2>/dev/null; then
        log_ok "torch installed via CPU-only wheels"
        return 0
    fi

    log_fail "torch installation failed"
    FAILED_DEPS+=("$dep_name")
    DISABLED_FEATURES+=("$features")
    return 1
}

install_ultralytics() {
    local dep_name="ultralytics"
    local features="YOLO Object Detection (vehicles, animals, packages)"

    echo ""
    echo -e "${BOLD}[$dep_name]${NC} — required for: $features"

    if is_installed ultralytics; then
        log_ok "ultralytics already installed"
        return 0
    fi

    if ! is_installed torch; then
        log_warn "ultralytics requires torch (not installed)"
        FAILED_DEPS+=("$dep_name")
        DISABLED_FEATURES+=("$features")
        return 1
    fi

    log_info "Trying: pip install ultralytics..."
    if "$PIP" install "ultralytics>=8.0.0" 2>/dev/null; then
        log_ok "ultralytics installed"
        return 0
    fi

    log_fail "ultralytics installation failed"
    FAILED_DEPS+=("$dep_name")
    DISABLED_FEATURES+=("$features")
    return 1
}

install_pyaudio() {
    local dep_name="pyaudio"
    local features="Two-Way Audio (microphone capture/playback)"

    echo ""
    echo -e "${BOLD}[$dep_name]${NC} — required for: $features"

    if is_installed pyaudio; then
        log_ok "pyaudio already installed"
        return 0
    fi

    # PortAudio is required
    if ! pkg-config --exists portaudio-2.0 2>/dev/null && ! [ -f /opt/homebrew/lib/libportaudio.dylib ] && ! [ -f /usr/local/lib/libportaudio.dylib ]; then
        install_portaudio || {
            FAILED_DEPS+=("$dep_name")
            DISABLED_FEATURES+=("$features")
            return 1
        }
    fi

    log_info "Trying: pip install pyaudio..."
    if "$PIP" install "pyaudio>=0.2.13" 2>/dev/null; then
        log_ok "pyaudio installed"
        return 0
    fi

    log_fail "pyaudio installation failed"
    FAILED_DEPS+=("$dep_name")
    DISABLED_FEATURES+=("$features")
    return 1
}

install_aiortc() {
    local dep_name="aiortc"
    local features="Two-Way Audio (WebRTC streaming)"

    echo ""
    echo -e "${BOLD}[$dep_name + av]${NC} — required for: $features"

    if is_installed aiortc; then
        log_ok "aiortc already installed"
        return 0
    fi

    # ARM compilation can be problematic
    if [ "$IS_ARM" = true ]; then
        log_warn "aiortc requires compiling native extensions on ARM."
        read -rp "  Attempt aiortc install? (y/N): " choice
        if [[ ! "$choice" =~ ^[Yy]$ ]]; then
            FAILED_DEPS+=("$dep_name")
            DISABLED_FEATURES+=("$features")
            return 1
        fi
    fi

    # Need system deps for av/aiortc
    if [ "$PKG_MGR" = "apt" ]; then
        log_info "Installing system dependencies for aiortc..."
        sudo apt-get install -y libavformat-dev libavcodec-dev libavdevice-dev \
            libavutil-dev libswscale-dev libswresample-dev libavfilter-dev \
            libopus-dev libvpx-dev pkg-config 2>/dev/null || true
    fi

    log_info "Trying: pip install aiortc av..."
    if "$PIP" install "aiortc>=1.6.0" "av>=11.0.0" 2>/dev/null; then
        log_ok "aiortc + av installed"
        return 0
    fi

    log_fail "aiortc installation failed"
    FAILED_DEPS+=("$dep_name")
    DISABLED_FEATURES+=("$features")
    return 1
}

# ── Summary & User Decision ───────────────────────────────────────────

show_summary() {
    echo ""
    echo -e "${BLUE}════════════════════════════════════════${NC}"
    echo -e "${BLUE}  Dependency Installation Summary${NC}"
    echo -e "${BLUE}════════════════════════════════════════${NC}"
    echo ""

    if [ ${#FAILED_DEPS[@]} -eq 0 ]; then
        echo -e "  ${GREEN}All optional dependencies installed successfully!${NC}"
        echo "  All features are available."
        return 0
    fi

    echo -e "  ${YELLOW}Some dependencies could not be installed:${NC}"
    echo ""

    # Deduplicate features
    declare -A seen_features
    for feat in "${DISABLED_FEATURES[@]}"; do
        IFS=',' read -ra parts <<< "$feat"
        for part in "${parts[@]}"; do
            part="$(echo "$part" | sed 's/^ *//;s/ *$//')"
            seen_features["$part"]=1
        done
    done

    echo -e "  ${BOLD}Failed packages:${NC}"
    for dep in "${FAILED_DEPS[@]}"; do
        echo -e "    ${RED}✗${NC} $dep"
    done

    echo ""
    echo -e "  ${BOLD}Features that will be disabled:${NC}"
    for feat in "${!seen_features[@]}"; do
        echo -e "    ${YELLOW}⚠${NC} $feat"
    done

    echo ""
    echo -e "  ${BOLD}Features that still work:${NC}"
    echo -e "    ${GREEN}✓${NC} Motion Detection (OpenCV)"
    echo -e "    ${GREEN}✓${NC} Camera Management"
    echo -e "    ${GREEN}✓${NC} Recording & Timeline"
    echo -e "    ${GREEN}✓${NC} Email/SMS Notifications"
    echo -e "    ${GREEN}✓${NC} Smart Home Integrations (MQTT, HomeKit)"
    echo -e "    ${GREEN}✓${NC} Web Dashboard"
    echo -e "    ${GREEN}✓${NC} API & Authentication"
    echo ""

    read -rp "  Continue with disabled features? (Y/n): " choice
    if [[ "$choice" =~ ^[Nn]$ ]]; then
        echo ""
        echo -e "${YELLOW}Installation cancelled.${NC}"
        echo "You can re-run this script after manually installing the failed dependencies."
        echo ""
        echo "Manual install hints:"
        for dep in "${FAILED_DEPS[@]}"; do
            case "$dep" in
                dlib)
                    echo "  dlib:             https://github.com/davisking/dlib#installation"
                    ;;
                face_recognition)
                    echo "  face_recognition: pip install face_recognition (requires dlib)"
                    ;;
                torch)
                    echo "  torch:            https://pytorch.org/get-started/locally/"
                    ;;
                ultralytics)
                    echo "  ultralytics:      pip install ultralytics (requires torch)"
                    ;;
                pyaudio)
                    echo "  pyaudio:          Install PortAudio first, then pip install pyaudio"
                    ;;
                aiortc)
                    echo "  aiortc:           https://github.com/aiortc/aiortc#linux"
                    ;;
            esac
        done
        exit 1
    fi

    echo ""
    echo -e "${GREEN}Continuing with available features.${NC}"
    echo "The application will automatically disable unavailable features at startup."
}

# ── Main ──────────────────────────────────────────────────────────────

main() {
    echo ""
    echo -e "${BLUE}════════════════════════════════════════${NC}"
    echo -e "${BLUE}  OpenEye — Smart Dependency Installer${NC}"
    echo -e "${BLUE}════════════════════════════════════════${NC}"
    echo ""

    detect_platform
    check_venv

    echo -e "${BLUE}Installing optional heavy dependencies...${NC}"
    echo "Core dependencies (FastAPI, OpenCV, etc.) should already be installed."
    echo "This script handles optional packages that require compilation or"
    echo "platform-specific installation."
    echo ""

    # Install in dependency order
    install_dlib          || true
    install_face_recognition || true
    install_torch         || true
    install_ultralytics   || true
    install_pyaudio       || true
    install_aiortc        || true

    show_summary

    echo ""
    echo -e "${GREEN}Done.${NC} Run OpenEye with:"
    echo "  cd opencv_surveillance"
    echo "  source .venv/bin/activate"
    echo "  python -m uvicorn backend.main:app --host 0.0.0.0 --port 8200"
    echo ""
}

main "$@"
