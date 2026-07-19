#!/usr/bin/env bash
# Uninstall OpenEye but KEEP user data:
#   - the surveillance.db database (admin account + configured cameras)
#   - the .env file (JWT secret, so existing sessions/tokens stay valid)
#   - all media: recordings/, faces/, data/snapshots, data/thumbnails
#
# Removes only the service, the Python venv, the frontend build, and caches, so a
# later ./opencv_surveillance/scripts/install-local.sh restores your system with
# your account, cameras, and footage intact.
#
# For a complete wipe (including the database and footage) use ./uninstall.sh
set -euo pipefail
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/uninstall.sh" --keep-data "$@"
