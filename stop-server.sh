#!/bin/bash
# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# OpenEye Surveillance System - Graceful Shutdown Script
#
# This script gracefully stops the OpenEye server by:
# 1. Finding the uvicorn process
# 2. Sending SIGTERM for graceful shutdown
# 3. Waiting up to 10 seconds for cleanup
# 4. Force killing if graceful shutdown fails
# 5. Cleaning up any orphaned processes

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/openeye-port.sh
source "$SCRIPT_DIR/scripts/lib/openeye-port.sh"
PORT="$(openeye_resolve_port)"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}OpenEye Server Shutdown Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to check if process exists
process_exists() {
    kill -0 "$1" 2>/dev/null
}

# Function to find uvicorn processes
find_uvicorn_pids() {
    # Find by command pattern
    PIDS=$(ps aux | grep -E "(uvicorn.*backend\.main:app|python.*backend/main\.py)" | grep -v grep | awk '{print $2}')
    # Also find by port — but only processes that are actually OpenEye.
    # `lsof -ti` alone also returns processes that merely hold a CONNECTION to
    # the port, which is how this script came to threaten unrelated software.
    PORT_PIDS=$(openeye_service_pids "$PORT")
    # Combine and deduplicate
    echo "$PIDS $PORT_PIDS" | tr ' ' '\n' | sort -u | tr '\n' ' '
}

# Find all uvicorn processes
PIDS=$(find_uvicorn_pids)

if [ -z "$PIDS" ]; then
    echo -e "${YELLOW}⚠ No OpenEye server processes found${NC}"
    echo "The server is not running."
    exit 0
fi

echo -e "${GREEN}Found OpenEye server process(es):${NC}"
for PID in $PIDS; do
    ps -p "$PID" -o pid,cmd | tail -n +2
done
echo ""

# Send SIGTERM to all processes
echo -e "${BLUE}[1/3] Sending SIGTERM for graceful shutdown...${NC}"
for PID in $PIDS; do
    if process_exists "$PID"; then
        kill -TERM "$PID" 2>/dev/null || true
        echo "  ✓ Sent SIGTERM to PID $PID"
    fi
done
echo ""

# Wait for graceful shutdown with countdown
echo -e "${BLUE}[2/3] Waiting for graceful shutdown (10s timeout)...${NC}"
TIMEOUT=10
ELAPSED=0

while [ $ELAPSED -lt $TIMEOUT ]; do
    REMAINING=$((TIMEOUT - ELAPSED))
    
    # Check if any processes are still running
    STILL_RUNNING=""
    for PID in $PIDS; do
        if process_exists "$PID"; then
            STILL_RUNNING="$STILL_RUNNING $PID"
        fi
    done
    
    # If no processes running, we're done
    if [ -z "$STILL_RUNNING" ]; then
        echo -e "\r${GREEN}  ✓ All processes stopped gracefully (${ELAPSED}s)${NC}"
        echo ""
        break
    fi
    
    # Show countdown
    echo -ne "\r  Waiting... ${REMAINING}s remaining (PIDs:$STILL_RUNNING)  "
    sleep 1
    ELAPSED=$((ELAPSED + 1))
done

echo ""

# Check if we need to force kill
FORCE_KILL_NEEDED=""
for PID in $PIDS; do
    if process_exists "$PID"; then
        FORCE_KILL_NEEDED="$FORCE_KILL_NEEDED $PID"
    fi
done

if [ -n "$FORCE_KILL_NEEDED" ]; then
    echo -e "${YELLOW}[3/3] Force killing remaining processes...${NC}"
    for PID in $FORCE_KILL_NEEDED; do
        if process_exists "$PID"; then
            kill -9 "$PID" 2>/dev/null || true
            echo -e "  ${YELLOW}⚠ Force killed PID $PID${NC}"
        fi
    done
    echo ""
    echo -e "${YELLOW}⚠ Some processes required force kill. Check logs for errors.${NC}"
else
    echo -e "${GREEN}✓ All processes stopped gracefully${NC}"
fi

# Clean up any orphaned Python processes from this project
echo ""
echo -e "${BLUE}Checking for orphaned processes...${NC}"
PROJECT_DIR=$(cd "$(dirname "$0")" && pwd)
ORPHANED=$(ps aux | grep python | grep "$PROJECT_DIR" | grep -v grep | grep -v "$$" | awk '{print $2}' || true)

if [ -n "$ORPHANED" ]; then
    echo -e "${YELLOW}Found orphaned Python processes:${NC}"
    ps aux | grep python | grep "$PROJECT_DIR" | grep -v grep | grep -v "$$"
    echo ""
    echo -e "${YELLOW}Cleaning up orphaned processes...${NC}"
    for PID in $ORPHANED; do
        if process_exists "$PID"; then
            kill -9 "$PID" 2>/dev/null || true
            echo "  ✓ Killed orphaned PID $PID"
        fi
    done
else
    echo -e "${GREEN}✓ No orphaned processes found${NC}"
fi

# Verify the port is free.
#
# The unconditional `pkill -9 -f "uvicorn backend.main:app"` that used to run
# here has been removed. It fired even when the graceful path had already
# succeeded, and it matched on a command-line pattern across the whole host
# rather than the PIDs this script tracked — so a second OpenEye instance (a
# developer checkout beside an installed copy, which this project supports) was
# killed as collateral.
echo ""
echo -e "${BLUE}Verifying port $PORT is available...${NC}"
sleep 1  # Brief pause to let OS release the port
REMAINING=$(openeye_service_pids "$PORT")
if [ -n "$REMAINING" ]; then
    echo -e "${YELLOW}⚠ OpenEye still on port $PORT (PID: $REMAINING) — force killing${NC}"
    kill -9 $REMAINING 2>/dev/null || true
    sleep 1
    echo -e "${GREEN}  ✓ Port $PORT freed${NC}"
else
    OTHERS=$(lsof -ti:"$PORT" 2>/dev/null || true)
    if [ -n "$OTHERS" ]; then
        # Report it; do not kill it. Another application holding our port is a
        # conflict worth surfacing, not something to terminate silently.
        echo -e "${YELLOW}⚠ Port $PORT is held by another application (left untouched):${NC}"
        for pid in $OTHERS; do
            echo "    PID $pid: $(ps -o command= -p "$pid" 2>/dev/null | cut -c1-80)"
        done
    else
        echo -e "${GREEN}✓ Port $PORT is available${NC}"
    fi
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ OpenEye server stopped successfully${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "You can now restart the server with: ./start-local.sh"
