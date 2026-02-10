#!/bin/bash
# Copyright (c) 2025 M1K31
# OpenEye Surveillance System - Graceful Shutdown Script
#
# This script gracefully stops the OpenEye server by:
# 1. Finding the uvicorn process
# 2. Sending SIGTERM for graceful shutdown
# 3. Waiting up to 10 seconds for cleanup
# 4. Force killing if graceful shutdown fails
# 5. Cleaning up any orphaned processes

set -e

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
    # Also find by port
    PORT_PIDS=$(lsof -ti :8000 2>/dev/null || true)
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

# Use pkill as a fallback to catch any remaining processes
echo ""
echo -e "${BLUE}Running pkill cleanup...${NC}"
pkill -9 -f "uvicorn backend.main:app" 2>/dev/null && echo "  ✓ Killed uvicorn processes via pkill" || echo "  ✓ No additional uvicorn processes found"

# Verify port 8000 is free
echo ""
echo -e "${BLUE}Verifying port 8000 is available...${NC}"
sleep 1  # Brief pause to let OS release the port
PORT_CHECK=$(lsof -ti:8000 || true)
if [ -n "$PORT_CHECK" ]; then
    echo -e "${YELLOW}⚠ Port 8000 still in use by PID: $PORT_CHECK${NC}"
    echo "  Killing process on port 8000..."
    kill -9 $PORT_CHECK 2>/dev/null || true
    sleep 1
    echo -e "${GREEN}  ✓ Port 8000 freed${NC}"
else
    echo -e "${GREEN}✓ Port 8000 is available${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ OpenEye server stopped successfully${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "You can now restart the server with: ./start-local.sh"
