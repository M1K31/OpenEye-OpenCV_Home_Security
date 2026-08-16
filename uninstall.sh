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

# Where a bundled installation keeps its data. This is NOT the same place as the
# source install's DATA_ROOT above, and it is the larger of the two by far — the
# database, galleries, recordings and snapshots all live here. Without it a
# "full purge" left tens of gigabytes behind while reporting success, which is
# both a surprise on a machine someone is trying to reclaim and a way for a
# supposedly clean reinstall to inherit the previous install's state.
case "$(uname -s)" in
    Darwin) BUNDLE_DATA_ROOT="$HOME/Library/Application Support/OpenEye" ;;
    *)      BUNDLE_DATA_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/openeye" ;;
esac

# The built application bundle, which is a build artifact rather than user data.
BUNDLE_APP="$PROJECT_ROOT/dist"

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
# The app directory is supposed to hold only synced code, so this used to be an
# unconditional "rm -rf $APP_DIR" that ran here in the build-artifacts step,
# ahead of the --keep-data guard below. It is not only code. Because the runtime
# resolved relative storage paths against its working directory rather than the
# configured location, live installs keep surveillance.db, faces/ and
# recordings/ inside this directory — so --keep-data would delete the database
# and every recording while printing "Kept: surveillance.db ... recordings/".
#
# Under --keep-data, remove the code and leave anything that holds user data,
# using the same protected set as scripts/sync-app.sh. A full purge still takes
# the whole directory.
if $KEEP_DATA; then
    if [ -d "$APP_DIR" ]; then
        while IFS= read -r entry; do
            case "$(basename "$entry")" in
                recordings|faces|data|logs|models|.env) continue ;;
                surveillance.db|surveillance.db-shm|surveillance.db-wal) continue ;;
                *) run "rm -rf \"$entry\"" ;;
            esac
        done < <(find "$APP_DIR" -mindepth 1 -maxdepth 1)
        echo "  ✓ app code removed, user data under $APP_DIR kept"
    fi
else
    run "rm -rf \"$APP_DIR\""
    echo "  ✓ app snapshot removed ($APP_DIR)"
fi
run "rm -rf \"$OPENCV_DIR/frontend/dist\" \"$OPENCV_DIR/frontend/node_modules\""
# The built .app is a build artifact rather than user data, so it goes in both
# modes — keeping it after an uninstall would leave a bundle that still launches
# and recreates state the user just asked to be rid of.
#
# Removed twice on purpose. Deleting a directory Finder has open races with
# Finder writing .DS_Store back into it: the contents go, then the final rmdir
# fails with "Directory not empty" over a file that did not exist when the
# delete started. One retry settles it, and reporting success only after the
# directory is actually gone keeps the summary honest.
if [ -d "$BUNDLE_APP" ]; then
    run "rm -rf \"$BUNDLE_APP\" 2>/dev/null || true"
    run "rm -rf \"$BUNDLE_APP\" 2>/dev/null || true"
    if $DRY || [ ! -d "$BUNDLE_APP" ]; then
        echo "  ✓ built application bundle removed ($BUNDLE_APP)"
    else
        echo -e "${YELLOW}  ! $BUNDLE_APP could not be fully removed; delete it by hand${NC}"
    fi
fi
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
    # The bundled installation's data root — the database, galleries, recordings
    # and snapshots, and by far the largest thing OpenEye owns. Skipped when it
    # is the same directory as DATA_ROOT, which is the case for a Linux source
    # install. Without this a "full purge" reported success while leaving tens of
    # gigabytes in place, and a supposedly clean reinstall inherited the previous
    # installation's database.
    if [ "$BUNDLE_DATA_ROOT" != "$DATA_ROOT" ] && [ -d "$BUNDLE_DATA_ROOT" ]; then
        run "rm -rf \"$BUNDLE_DATA_ROOT\""
        echo "  ✓ bundled application data removed ($BUNDLE_DATA_ROOT)"
    fi

    # State macOS keeps for an application *outside* its bundle and data root.
    # None of it is large, but it is what makes a "clean" reinstall not clean:
    # ~/Library/Logs/OpenEye survived from an install three weeks dead, and the
    # CrashReporter entries keep an app's crash history alive across reinstalls.
    if [ "$(uname -s)" = "Darwin" ]; then
        for leftover in \
            "$HOME/Library/Logs/OpenEye" \
            "$HOME/Library/Preferences/$LABEL.plist" \
            "$HOME/Library/Caches/$LABEL" \
            "$HOME/Library/Saved Application State/$LABEL.savedState" \
            "$HOME/Library/HTTPStorages/$LABEL" ; do
            [ -e "$leftover" ] && run "rm -rf \"$leftover\""
        done
        run "rm -f \"$HOME/Library/Application Support/CrashReporter\"/*[Oo]pen[Ee]ye*.plist 2>/dev/null || true"
        echo "  ✓ macOS application state removed (logs, caches, crash history)"

        # The camera and microphone grants belong to the bundle identity, not to
        # the files just deleted, so they outlive an uninstall. Leaving them means
        # a reinstall silently inherits an approval the user never granted it,
        # which is indistinguishable from a permission that is working.
        run "tccutil reset Camera $LABEL >/dev/null 2>&1 || true"
        run "tccutil reset Microphone $LABEL >/dev/null 2>&1 || true"
        echo "  ✓ camera and microphone permissions reset"
    fi
    echo "  ✓ database, .env, and media removed"
fi

# Remove the prefix itself. On a FULL purge take the whole directory: OpenEye
# owns it exclusively, and removing its contents piecemeal then rmdir'ing left
# the prefix behind whenever anything unexpected was inside — a stray macOS
# .DS_Store was enough, since a bare rmdir is a no-op on a non-empty directory.
# Under --keep-data the surgical path is correct: the db/media must survive, so
# only try the rmdir, which harmlessly does nothing while they are there.
if $KEEP_DATA; then
    run "rmdir \"$DATA_ROOT\" 2>/dev/null || true"
else
    run "rm -rf \"$DATA_ROOT\""
fi

echo -e "${BLUE}[5/5] Done.${NC}"
echo -e "${GREEN}OpenEye uninstalled.${NC} Reinstall with: ./opencv_surveillance/scripts/install-local.sh"
$KEEP_DATA || echo -e "${YELLOW}Remember to remove any firewall rules / port-forwards for port $PORT.${NC}"
