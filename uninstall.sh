#!/usr/bin/env bash
# OpenEye Surveillance System — Uninstall (FULL removal by default).
#
# Removes everything the installer added: the launchd/systemd service, the Python
# venv, the frontend build + node_modules, Python caches, AND user data (the
# surveillance.db admin/camera database, the .env JWT secret, and all media —
# recordings, faces, snapshots, thumbnails).
#
# To keep your admin account, cameras, and footage for a later reinstall, use the
# sibling script that preserves user data.
#
# Usage:
#   ./uninstall.sh              # FULL removal (asks to confirm)
#   ./uninstall.sh --yes        # FULL removal, no prompt (CI/automation)
#   ./uninstall.sh --dry-run    # print what would be removed
#   ./uninstall-keep-data.sh    # remove service+venv+build, KEEP db/.env/media
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENCV_DIR="$PROJECT_ROOT/opencv_surveillance"
LABEL="com.smartindustries.openeye"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PORT="${OPENEYE_PORT:-8200}"
DATA_ROOT="${OPENEYE_DATA_ROOT:-$HOME/.local/share/openeye}"
APP_DIR="$DATA_ROOT/app"

KEEP_DATA=false; DRY=false
NONINTERACTIVE="${OPENEYE_NONINTERACTIVE:-${CI:-}}"
for a in "$@"; do
    case "$a" in
        --keep-data)                KEEP_DATA=true ;;
        -y|--yes|--non-interactive) NONINTERACTIVE=1 ;;
        --dry-run)                  DRY=true ;;
        -h|--help) grep '^#' "$0" | sed 's/^# \?//'; exit 0 ;;
        *) echo "Unknown option: $a"; exit 1 ;;
    esac
done
run() { if $DRY; then echo "[dry-run] $*"; else eval "$*"; fi; }

echo -e "${RED}=== OpenEye Uninstall ===${NC}"
if $KEEP_DATA; then
    echo "Mode: keep user data (database, .env, media)."
else
    echo -e "${YELLOW}Mode: FULL removal — deletes the admin/camera database and all footage.${NC}"
    if [ -z "$NONINTERACTIVE" ] && ! $DRY; then
        read -rp "Type 'yes' to permanently delete OpenEye and its data: " confirm
        [ "$confirm" = "yes" ] || { echo "Aborted."; exit 1; }
    fi
fi

# 1. Stop the server + free the port.
echo -e "${BLUE}[1/5] Stopping server...${NC}"
if [ -x "$OPENCV_DIR/stop.sh" ]; then
    run "\"$OPENCV_DIR/stop.sh\" >/dev/null 2>&1 || true"
fi
run "pkill -f 'uvicorn.*backend.main:app' 2>/dev/null || true"
PORT_PID="$(lsof -ti:"$PORT" 2>/dev/null || true)"
[ -n "$PORT_PID" ] && run "kill -9 $PORT_PID 2>/dev/null || true"

# 2. Remove the OS service.
echo -e "${BLUE}[2/5] Removing service...${NC}"
if [ -f "$PLIST" ]; then
    run "launchctl bootout gui/\$(id -u)/$LABEL 2>/dev/null || launchctl unload \"$PLIST\" 2>/dev/null || true"
    run "rm -f \"$PLIST\""
    echo "  ✓ launchd agent removed"
fi
if [ -f "/etc/systemd/system/openeye.service" ]; then
    run "sudo systemctl disable --now openeye 2>/dev/null || true"
    run "sudo rm -f /etc/systemd/system/openeye.service"
    run "sudo systemctl daemon-reload 2>/dev/null || true"
    echo "  ✓ systemd unit removed"
fi

# 3. Remove the venv + generated build artifacts + caches.
echo -e "${BLUE}[3/5] Removing runtime + build artifacts...${NC}"
for vdir in "$OPENCV_DIR/venv" "$OPENCV_DIR/.venv" "${OPENEYE_VENV:-$HOME/.local/share/openeye/venv}"; do
    [ -d "$vdir" ] && run "rm -rf \"$vdir\"" && echo "  ✓ venv removed ($vdir)"
done
run "rm -rf \"${OPENEYE_DATA_ROOT:-$HOME/.local/share/openeye}/app\""
echo "  ✓ app snapshot removed ($APP_DIR)"
run "rm -rf \"$OPENCV_DIR/frontend/dist\" \"$OPENCV_DIR/frontend/node_modules\""
run "find \"$OPENCV_DIR\" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true"
run "rm -f \"$OPENCV_DIR/start.sh\" \"$OPENCV_DIR/stop.sh\""
echo "  ✓ build + caches cleared"

# 4. User data — the database, config secret, and media.
echo -e "${BLUE}[4/5] Handling user data...${NC}"
if $KEEP_DATA; then
    echo "  • Kept: surveillance.db, .env, recordings/, faces/, data/"
else
    run "rm -f \"$OPENCV_DIR/surveillance.db\" \"$OPENCV_DIR/surveillance.db-shm\" \"$OPENCV_DIR/surveillance.db-wal\""
    run "rm -f \"$OPENCV_DIR/.env\""
    for d in recordings faces data/snapshots data/thumbnails; do
        [ -d "$OPENCV_DIR/$d" ] && run "rm -rf \"$OPENCV_DIR/$d\""
    done
    run "rm -f \"$DATA_ROOT/surveillance.db\" \"$DATA_ROOT/surveillance.db-shm\" \"$DATA_ROOT/surveillance.db-wal\""
    for d in recordings faces data; do
        run "rm -rf \"$DATA_ROOT/$d\""
    done
    echo "  ✓ database, .env, and media removed"
fi

# Clean up the now-empty prefix (bare rmdir is a no-op if anything remains,
# e.g. --keep-data left the db/media behind — that's intentional).
run "rmdir \"$HOME/.local/share/openeye\" 2>/dev/null || true"

echo -e "${BLUE}[5/5] Done.${NC}"
echo -e "${GREEN}OpenEye uninstalled.${NC} Reinstall with: ./opencv_surveillance/scripts/install-local.sh"
$KEEP_DATA || echo -e "${YELLOW}Remember to remove any firewall rules / port-forwards for port $PORT.${NC}"
