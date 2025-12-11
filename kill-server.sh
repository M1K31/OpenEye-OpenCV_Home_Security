#!/bin/bash

# Copyright (c) 2025 M1K31
# OpenEye Surveillance System - Force Kill Script
#
# This script FORCE KILLS any process on port 8000 (kill -9)
# Use stop-server.sh for graceful shutdown instead.
# This script is for emergency situations when graceful shutdown fails.

echo "🔪 Force killing processes on port 8000..."

# Find and kill any process on port 8000
PIDS=$(lsof -ti:8000 2>/dev/null)

if [ -z "$PIDS" ]; then
    echo "✓ No processes found on port 8000"
    exit 0
fi

echo "Found processes: $PIDS"
echo "$PIDS" | xargs kill -9 2>/dev/null || true

echo "✓ Force killed all processes on port 8000"
echo ""
echo "⚠ WARNING: This was a force kill (SIGKILL)."
echo "   Use ./stop-server.sh for graceful shutdown."