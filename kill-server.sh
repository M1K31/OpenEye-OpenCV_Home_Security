#!/bin/bash
# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# OpenEye Surveillance System - Force Kill Script
#
# This script FORCE KILLS the OpenEye service (kill -9).
# Use stop-server.sh for graceful shutdown instead.
# This script is for emergency situations when graceful shutdown fails.
#
# Two things changed on 2026-08-20, both of which made this script dangerous:
#
#   1. It hardcoded port 8000. OpenEye's canonical port is 8200
#      (backend/core/config.py::DEFAULT_SERVICE_PORT), so on a default install
#      this script never found OpenEye at all.
#   2. It killed every PID `lsof -ti` returned for that port — which includes
#      processes that merely hold a connection, not just the listener. Combined
#      with (1) that meant `kill -9` against whatever unrelated software
#      happened to be using 8000.
#
# It now resolves the port the same way the application does, and only targets
# processes whose command line identifies them as OpenEye.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/openeye-port.sh
source "$SCRIPT_DIR/scripts/lib/openeye-port.sh"

PORT="$(openeye_resolve_port)"

echo "🔪 Force killing OpenEye on port $PORT..."

PIDS="$(openeye_service_pids "$PORT")"

if [ -z "$PIDS" ]; then
    echo "✓ No OpenEye process found on port $PORT"

    # If something else holds the port, say so rather than killing it. A port
    # conflict is a real problem worth reporting, but it is not this script's
    # to solve.
    OTHERS="$(lsof -ti:"$PORT" 2>/dev/null || true)"
    if [ -n "$OTHERS" ]; then
        echo ""
        echo "⚠ Port $PORT is held by another application — left untouched:"
        for pid in $OTHERS; do
            echo "    PID $pid: $(ps -o command= -p "$pid" 2>/dev/null | cut -c1-90)"
        done
    fi
    exit 0
fi

echo "Found OpenEye processes: $PIDS"
# shellcheck disable=SC2086
kill -9 $PIDS 2>/dev/null || true

echo "✓ Force killed OpenEye on port $PORT"
echo ""
echo "⚠ WARNING: This was a force kill (SIGKILL)."
echo "   In-flight recordings may be truncated and the database was not closed."
echo "   Use ./stop-server.sh for graceful shutdown."
