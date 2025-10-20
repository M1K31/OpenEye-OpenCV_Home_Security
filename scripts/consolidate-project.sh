#!/bin/bash
# Project Consolidation Script - v3.5.5
# Removes duplicate directories and consolidates project structure
#
# Usage:
#   ./scripts/consolidate-project.sh --dry-run   # Show what would be deleted
#   ./scripts/consolidate-project.sh --execute   # Actually delete files
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default to dry-run
DRY_RUN=true

# Parse arguments
if [ "$1" == "--execute" ]; then
    DRY_RUN=false
    echo -e "${RED}⚠️  EXECUTE MODE - Files will be PERMANENTLY DELETED${NC}"
    echo ""
    read -p "Are you sure you want to continue? (type 'yes' to confirm): " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        echo "Cancelled."
        exit 1
    fi
elif [ "$1" == "--dry-run" ] || [ -z "$1" ]; then
    DRY_RUN=true
    echo -e "${BLUE}ℹ️  DRY RUN MODE - No files will be deleted${NC}"
else
    echo "Usage: $0 [--dry-run|--execute]"
    exit 1
fi

echo ""
echo "========================================"
echo "Project Consolidation Script"
echo "========================================"
echo ""

# Change to project root
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

echo "Project root: $PROJECT_ROOT"
echo ""

# Function to delete directory
delete_dir() {
    local dir=$1
    local reason=$2

    if [ -d "$dir" ]; then
        local size=$(du -sh "$dir" 2>/dev/null | cut -f1)
        local count=$(find "$dir" -type f 2>/dev/null | wc -l)

        echo -e "${YELLOW}📁 $dir${NC}"
        echo "   Size: $size"
        echo "   Files: $count"
        echo "   Reason: $reason"

        if [ "$DRY_RUN" = false ]; then
            echo -e "   ${RED}✗ DELETING...${NC}"
            rm -rf "$dir"
            echo -e "   ${GREEN}✓ Deleted${NC}"
        else
            echo -e "   ${BLUE}ℹ️  Would delete (dry-run)${NC}"
        fi
        echo ""
    else
        echo -e "${BLUE}ℹ️  Already deleted: $dir${NC}"
        echo ""
    fi
}

echo "=== Phase 1: Delete Obsolete Directories ==="
echo ""

# 1. Delete obsolete opencv-surveillance/ (hyphen)
delete_dir "./opencv-surveillance" "Obsolete backend copy (missing 11+ routes)"

# 2. Delete nested duplicate
delete_dir "./opencv_surveillance/opencv_surveillance" "Accidental nested duplicate"

echo "=== Phase 2: Delete Empty Root-Level Directories ==="
echo ""

# 3. Delete empty root-level directories
delete_dir "./data" "Empty root-level data directory"
delete_dir "./recordings" "Empty root-level recordings directory"
delete_dir "./faces" "Empty root-level faces directory"

echo "=== Phase 3: Delete Empty Test Directories ==="
echo ""

# 4. Delete empty test directories
delete_dir "./test-data" "Empty test data directory"
delete_dir "./test-faces" "Empty test faces directory"
delete_dir "./test-recordings" "Empty test recordings directory"

echo "=== Phase 4: Delete Empty Backend Directories ==="
echo ""

# 5. Delete empty backend/data/ and backend/recordings/
delete_dir "./opencv_surveillance/backend/data" "Empty backend data directory"
delete_dir "./opencv_surveillance/backend/recordings" "Empty backend recordings directory"

echo "=== Phase 5: Delete Empty Faces Subdirectories ==="
echo ""

# 6. Delete empty faces with subdirs
delete_dir "./opencv_surveillance/faces" "Empty faces directory with subdirs"

echo ""
echo "========================================"
echo "Summary"
echo "========================================"
echo ""

if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}ℹ️  DRY RUN COMPLETE${NC}"
    echo ""
    echo "No files were deleted."
    echo ""
    echo "To actually delete these directories, run:"
    echo -e "${GREEN}  ./scripts/consolidate-project.sh --execute${NC}"
else
    echo -e "${GREEN}✓ CONSOLIDATION COMPLETE${NC}"
    echo ""
    echo "Deleted directories have been removed."
    echo ""
    echo "Next steps:"
    echo "1. Test the application: ./start-local.sh"
    echo "2. Run path audit: ./scripts/audit-paths.sh"
    echo "3. Commit changes: git add -A && git commit -m 'refactor: Consolidate project structure'"
fi

echo ""
