#!/bin/bash
# Copyright (c) 2025 Mikel Smart
# OpenEye Surveillance System - Uninstall Script
#
# This script safely removes OpenEye from your system:
# 1. Stops all running processes
# 2. Optionally backs up data
# 3. Removes software components
# 4. Cleans up system resources
# 5. Optionally removes data files

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
OPENCV_DIR="opencv_surveillance"
BACKUP_DIR="openeye_backup_$(date +%Y%m%d_%H%M%S)"

echo -e "${RED}========================================${NC}"
echo -e "${RED}OpenEye Uninstallation${NC}"
echo -e "${RED}========================================${NC}"
echo ""
echo -e "${YELLOW}⚠  WARNING: This will remove OpenEye from your system${NC}"
echo ""

# Change to script directory
cd "$(dirname "$0")"
PROJECT_ROOT=$(pwd)

# Confirm uninstall
read -p "Are you sure you want to uninstall OpenEye? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstall cancelled"
    exit 0
fi

echo ""

# Ask about data backup
echo -e "${CYAN}Data Backup Options:${NC}"
echo ""
echo "  1. Backup all data (recordings, faces, database, config)"
echo "  2. Backup only database and config"
echo "  3. No backup (delete everything)"
echo ""
read -p "Select option (1-3): " -n 1 -r BACKUP_OPTION
echo ""
echo ""

# Stop server
echo -e "${BLUE}[1/6] Stopping OpenEye server...${NC}"

if [ -f "stop-server.sh" ]; then
    ./stop-server.sh > /dev/null 2>&1 || true
    echo -e "${GREEN}  ✓ Server stopped${NC}"
else
    # Manual cleanup
    PIDS=$(ps aux | grep -E "(uvicorn.*backend\.main:app|python.*backend/main\.py)" | grep -v grep | awk '{print $2}' || true)
    if [ -n "$PIDS" ]; then
        for PID in $PIDS; do
            kill -9 "$PID" 2>/dev/null || true
        done
        echo -e "${GREEN}  ✓ Server processes killed${NC}"
    else
        echo "  No running processes found"
    fi
fi

# Free port 8000
PORT_PID=$(lsof -ti:8000 || true)
if [ -n "$PORT_PID" ]; then
    kill -9 $PORT_PID 2>/dev/null || true
    echo "  ✓ Port 8000 freed"
fi

echo ""

# Backup data
if [ "$BACKUP_OPTION" != "3" ]; then
    echo -e "${BLUE}[2/6] Backing up data...${NC}"

    mkdir -p "$BACKUP_DIR"
    cd "$OPENCV_DIR"

    # Backup database
    if [ -f "surveillance.db" ]; then
        cp surveillance.db "$PROJECT_ROOT/$BACKUP_DIR/"
        echo "  ✓ Database backed up"
    fi

    # Backup .env
    if [ -f ".env" ]; then
        cp .env "$PROJECT_ROOT/$BACKUP_DIR/"
        echo "  ✓ Configuration backed up"
    fi

    # Full backup includes media
    if [ "$BACKUP_OPTION" == "1" ]; then
        # Backup recordings
        if [ -d "recordings" ] && [ "$(ls -A recordings 2>/dev/null)" ]; then
            cp -r recordings "$PROJECT_ROOT/$BACKUP_DIR/"
            echo "  ✓ Recordings backed up"
        fi

        # Backup faces
        if [ -d "faces" ] && [ "$(ls -A faces 2>/dev/null)" ]; then
            cp -r faces "$PROJECT_ROOT/$BACKUP_DIR/"
            echo "  ✓ Face images backed up"
        fi

        # Backup snapshots
        if [ -d "data/snapshots" ] && [ "$(ls -A data/snapshots 2>/dev/null)" ]; then
            mkdir -p "$PROJECT_ROOT/$BACKUP_DIR/data"
            cp -r data/snapshots "$PROJECT_ROOT/$BACKUP_DIR/data/"
            echo "  ✓ Snapshots backed up"
        fi
    fi

    cd "$PROJECT_ROOT"
    echo -e "${GREEN}  ✓ Backup saved to: $BACKUP_DIR${NC}"
    echo ""
else
    echo -e "${BLUE}[2/6] Skipping backup...${NC}"
    echo -e "${YELLOW}  ⚠ No backup will be created${NC}"
    echo ""
fi

# Remove virtual environment
echo -e "${BLUE}[3/6] Removing virtual environment...${NC}"

REMOVED_VENV=false
for vdir in "$OPENCV_DIR/.venv" "$OPENCV_DIR/venv"; do
    if [ -d "$vdir" ]; then
        rm -rf "$vdir"
        echo -e "${GREEN}  ✓ Virtual environment removed ($vdir)${NC}"
        REMOVED_VENV=true
    fi
done
if [ "$REMOVED_VENV" = false ]; then
    echo "  No virtual environment found"
fi

echo ""

# Remove generated files
echo -e "${BLUE}[4/6] Removing generated files...${NC}"

cd "$OPENCV_DIR"

# Remove database
if [ -f "surveillance.db" ]; then
    rm -f surveillance.db
    rm -f surveillance.db-shm 2>/dev/null || true
    rm -f surveillance.db-wal 2>/dev/null || true
    echo "  ✓ Database removed"
fi

# Remove .env
if [ -f ".env" ]; then
    rm -f .env
    echo "  ✓ Environment file removed"
fi

# Remove frontend build
if [ -d "frontend/dist" ]; then
    rm -rf frontend/dist
    echo "  ✓ Frontend build removed"
fi

# Remove node_modules
if [ -d "frontend/node_modules" ]; then
    echo "  Removing node_modules (this may take a moment)..."
    rm -rf frontend/node_modules
    echo "  ✓ Node modules removed"
fi

# Remove Python cache
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
echo "  ✓ Python cache cleared"

cd "$PROJECT_ROOT"
echo ""

# Remove data files
echo -e "${BLUE}[5/6] Removing data files...${NC}"

cd "$OPENCV_DIR"

# Remove recordings
if [ -d "recordings" ]; then
    rm -rf recordings/*
    echo "  ✓ Recordings removed"
fi

# Remove faces
if [ -d "faces" ]; then
    rm -rf faces/*
    echo "  ✓ Face images removed"
fi

# Remove snapshots
if [ -d "data/snapshots" ]; then
    rm -rf data/snapshots/*
    echo "  ✓ Snapshots removed"
fi

# Remove thumbnails
if [ -d "data/thumbnails" ]; then
    rm -rf data/thumbnails/*
    echo "  ✓ Thumbnails removed"
fi

cd "$PROJECT_ROOT"
echo ""

# Clean up systemd (if installed)
echo -e "${BLUE}[6/6] Cleaning up system services...${NC}"

# macOS launchd agent
OPENEYE_PLIST="$HOME/Library/LaunchAgents/com.smartindustries.openeye.plist"
if [ -f "$OPENEYE_PLIST" ]; then
    echo "  Found launchd agent"
    launchctl unload "$OPENEYE_PLIST" 2>/dev/null || true
    rm -f "$OPENEYE_PLIST"
    echo -e "${GREEN}    ✓ launchd agent removed${NC}"
fi

if [ -f "/etc/systemd/system/openeye.service" ]; then
    echo "  Found systemd service"
    read -p "  Remove systemd service? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo systemctl stop openeye 2>/dev/null || true
        sudo systemctl disable openeye 2>/dev/null || true
        sudo rm /etc/systemd/system/openeye.service
        sudo systemctl daemon-reload
        echo -e "${GREEN}    ✓ Systemd service removed${NC}"
    fi
elif [ ! -f "$OPENEYE_PLIST" ]; then
    echo "  No system service found"
fi

echo ""

# Display summary
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ OpenEye Uninstalled Successfully${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if [ "$BACKUP_OPTION" != "3" ]; then
    echo -e "${CYAN}Backup Location:${NC}"
    echo "  $BACKUP_DIR"
    echo ""
    echo "To restore from backup:"
    echo "  1. Reinstall OpenEye"
    echo "  2. Copy files from backup directory to opencv_surveillance/"
    echo ""
fi

echo -e "${CYAN}Removed:${NC}"
echo "  ✓ Virtual environment"
echo "  ✓ Database"
echo "  ✓ Configuration files"
echo "  ✓ Generated files"
echo "  ✓ Media files (recordings, faces, snapshots)"
echo "  ✓ Frontend build"
echo "  ✓ Python cache"
echo ""

echo -e "${CYAN}Preserved:${NC}"
echo "  • Source code (in case you want to reinstall)"
echo "  • Documentation"
echo ""

echo "To reinstall OpenEye, run:"
echo -e "  ${YELLOW}./setup-production.sh${NC}"
echo ""

echo "To completely remove the project directory:"
echo -e "  ${YELLOW}cd .. && rm -rf $(basename "$PROJECT_ROOT")${NC}"
echo ""

echo -e "${YELLOW}⚠ Remember to remove any firewall rules or port forwards${NC}"
echo -e "${YELLOW}  you configured for OpenEye (port 8000)${NC}"
echo ""
