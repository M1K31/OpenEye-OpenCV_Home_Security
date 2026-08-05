#!/usr/bin/env bash
# OpenEye — sync the working tree into the installed app snapshot.
#
# The app does NOT run from this repository. OpenEye.app's launcher does
#
#     APP_DIR="$HOME/.local/share/openeye/app"; cd "$APP_DIR"
#
# and runs uvicorn from there, so the running service only ever sees what has
# been copied into that directory. Nothing performed that copy: restart.sh says
# "use this after syncing code changes" but no script did the syncing. The
# result was an install that sat a week behind the repository while fix after
# fix was committed and appeared to do nothing — including three NameError
# crashes on live routes. This script is that missing step.
#
# Data is never touched. recordings/, faces/, logs/, models/, surveillance.db and
# .env live in the install and are deliberately excluded below; a sync must never
# cost someone their footage or their configuration.
#
# Usage:
#   ./scripts/sync-app.sh              # show what would change, then ask
#   ./scripts/sync-app.sh --dry-run    # show what would change and stop
#   ./scripts/sync-app.sh --yes        # sync without prompting (for scripts)
#
# Env: OPENEYE_DATA_ROOT (default ~/.local/share/openeye)
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO_ROOT/opencv_surveillance"
DATA_ROOT="${OPENEYE_DATA_ROOT:-$HOME/.local/share/openeye}"
APP_DIR="$DATA_ROOT/app"

DRY_RUN=0
ASSUME_YES=0
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --yes|-y)  ASSUME_YES=1 ;;
        --help|-h) sed -n '2,24p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) echo -e "${RED}Unknown option: $arg${NC}"; exit 2 ;;
    esac
done

[ -d "$SRC" ]     || { echo -e "${RED}Source not found: $SRC${NC}"; exit 1; }
[ -d "$APP_DIR" ] || { echo -e "${RED}Install not found: $APP_DIR${NC}
Run the installer first — this script updates an existing install, it does not
create one."; exit 1; }
command -v rsync >/dev/null || { echo -e "${RED}rsync is required${NC}"; exit 1; }

# What never belongs in an install.
#
# Two categories, and they are different:
#   - developer/test material, which a user has no use for and which has leaked
#     into the install before (tests/, pytest.ini, audit_test_results.json)
#   - live state, which the install OWNS and the repository must never overwrite
#     (recordings, faces, logs, the database, .env)
# Everything rsync must not carry into the install. Excluded paths are also safe
# from --delete: without --delete-excluded, rsync leaves them alone on both sides.
#
# --delete-excluded is deliberately NOT used. It looks like the tidy way to purge
# developer material, but it also deletes every other excluded path — and a dry
# run of that configuration was one keystroke away from erasing every recording
# and face image on this machine. Protect rules can be written to prevent it, but
# getting them subtly wrong is silent and unrecoverable. Stale developer files are
# removed by PURGE_PATHS below instead: an explicit list, no globs over user data,
# auditable at a glance.
EXCLUDES=(
    # --- live state: the install owns these, never overwrite, never remove ---
    --exclude "/.env"
    --exclude "/surveillance.db*"
    --exclude "/recordings/"
    --exclude "/faces/"
    --exclude "/logs/"
    --exclude "/models/"
    --exclude "/data/"

    # --- developer and test material: never copied in ---
    --exclude "/tests/"
    --exclude "test_*.py"
    --exclude "test_*.html"
    --exclude "/pytest.ini"
    --exclude "/requirements-dev.txt"
    --exclude "/requirements-ci.txt"
    --exclude "/audit_test_results.json"
    --exclude "/security_bandit.json"
    --exclude "/create_test_user.py"
    --exclude "/htmlcov/"
    --exclude "/coverage.xml"
    --exclude "/.coverage"
    --exclude "/.pytest_cache/"
    --exclude "/Dockerfile.dev"

    # --- build and editor noise ---
    --exclude "__pycache__/"
    --exclude "*.pyc"
    --exclude ".DS_Store"
    --exclude "/venv/"
    --exclude "node_modules/"
    --exclude "/frontend/src/"
    --exclude "/.git/"
)

# Developer material that earlier installs copied in and that must be removed.
# Every entry is a literal path relative to the install root. No wildcards that
# could reach user data, and nothing here is ever a directory the app writes to.
PURGE_PATHS=(
    "tests"
    "pytest.ini"
    "requirements-dev.txt"
    "requirements-ci.txt"
    "audit_test_results.json"
    "security_bandit.json"
    "test_photos_audit.py"
    "create_test_user.py"
    "test_login.html"
    "test_ffmpeg_recorder.py"
    "test_hardware_encoding_integration.py"
    "test_motion_zones.py"
    "test_recording_manual.py"
    ".pytest_cache"
    "htmlcov"
    "coverage.xml"
    ".coverage"
    "Dockerfile.dev"
    "=1.3.0"
    ".DS_Store"
)

echo -e "${BLUE}OpenEye — sync working tree into the installed app${NC}"
echo "  from : $SRC"
echo "  to   : $APP_DIR"
echo

# --itemize-changes so the operator sees exactly what moves, not just a count.
CHANGES="$(rsync -ain --delete-after "${EXCLUDES[@]}" "$SRC/" "$APP_DIR/" \
           | grep -vE '^\.d\.\.t|^cd\+\+\+\+\+\+\+' || true)"

if [ -z "$CHANGES" ]; then
    echo -e "${GREEN}Already in sync — nothing to copy.${NC}"
    exit 0
fi

echo -e "${YELLOW}Changes to apply:${NC}"
echo "$CHANGES" | sed 's/^/  /'
echo
COUNT="$(printf '%s\n' "$CHANGES" | grep -c . || true)"
echo "  $COUNT path(s)"
echo

echo -e "${YELLOW}Developer material to remove from the install:${NC}"
PURGE_FOUND=0
for rel in "${PURGE_PATHS[@]}"; do
    if [ -e "$APP_DIR/$rel" ]; then
        echo "  purge  $rel"
        PURGE_FOUND=1
    fi
done
[ "$PURGE_FOUND" -eq 0 ] && echo "  (none present)"
echo

if [ "$DRY_RUN" -eq 1 ]; then
    echo -e "${BLUE}--dry-run: nothing was written.${NC}"
    exit 0
fi

if [ "$ASSUME_YES" -eq 0 ]; then
    read -r -p "Apply these changes? [y/N] " reply
    case "$reply" in
        [yY]|[yY][eE][sS]) ;;
        *) echo "Aborted."; exit 0 ;;
    esac
fi

rsync -a --delete-after "${EXCLUDES[@]}" "$SRC/" "$APP_DIR/"

# Remove developer material left by earlier installs. Guarded: only paths inside
# APP_DIR, and never one of the directories the running app writes to.
for rel in "${PURGE_PATHS[@]}"; do
    target="$APP_DIR/$rel"
    case "$rel" in
        recordings|faces|logs|models|data|.env|surveillance.db*|"")
            echo "refusing to purge protected path: $rel" >&2; continue ;;
    esac
    [ -e "$target" ] && rm -rf "$target" && echo "  removed $rel"
done

# Stale bytecode can shadow a just-updated module.
find "$APP_DIR" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true

echo -e "${GREEN}Sync complete.${NC}"
echo
echo "The running service is still on the OLD code until it restarts:"
echo -e "  ${BLUE}./restart.sh${NC}"
