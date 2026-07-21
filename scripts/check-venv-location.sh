#!/usr/bin/env bash
# Fails if the OpenEye runtime venv lives on a removable/external volume.
# An mmap'd C-extension (opencv/av) on a force-unmounted volume crashes with SIGBUS.
set -euo pipefail
VENV="${OPENEYE_VENV:-$HOME/.local/share/openeye/venv}"
if [ -d "$(dirname "${BASH_SOURCE[0]}")/../opencv_surveillance/venv" ]; then
    echo "FAIL: legacy venv still present on the repo volume (opencv_surveillance/venv)"; exit 1
fi
case "$VENV" in
  /Volumes/*) echo "FAIL: venv is on an external volume: $VENV"; exit 1 ;;
esac
[ -x "$VENV/bin/python3" ] || { echo "FAIL: no interpreter at $VENV/bin/python3"; exit 1; }

PLIST="$HOME/Library/LaunchAgents/com.smartindustries.openeye.plist"
if [ -f "$PLIST" ] && grep -q '/Volumes/' "$PLIST"; then
    echo "FAIL: launchd plist still references an external volume:"
    grep -n '/Volumes/' "$PLIST"
    exit 1
fi

echo "OK: internal-disk venv at $VENV"
