#!/bin/bash
# Path Audit Script - v3.5.5
# Audits codebase for hardcoded paths that should use PathManager
#
# Usage:
#   ./scripts/audit-paths.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Change to project root
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

echo "========================================"
echo "Path Audit Report"
echo "========================================"
echo ""
echo "Project root: $PROJECT_ROOT"
echo ""

echo "=== 1. Searching for Hardcoded Paths in Backend ==="
echo ""

echo -e "${YELLOW}Searching for 'recordings' paths...${NC}"
grep -rn '"recordings"' opencv_surveillance/backend/ --include="*.py" 2>/dev/null | \
    grep -v "\.pyc" | \
    grep -v "__pycache__" | \
    grep -v "# recordings" | \
    head -20 || echo "None found"

echo ""
echo -e "${YELLOW}Searching for 'data/snapshots' paths...${NC}"
grep -rn '"data/snapshots"' opencv_surveillance/backend/ --include="*.py" 2>/dev/null | \
    grep -v "\.pyc" | \
    grep -v "__pycache__" | \
    head -20 || echo "None found"

echo ""
echo -e "${YELLOW}Searching for 'data/faces' or 'faces' paths...${NC}"
grep -rn '"faces"' opencv_surveillance/backend/ --include="*.py" 2>/dev/null | \
    grep -v "\.pyc" | \
    grep -v "__pycache__" | \
    grep -v "# faces" | \
    grep -v "known_faces" | \
    grep -v "detected_faces" | \
    head -20 || echo "None found"

echo ""
echo "=== 2. Checking PathManager Usage ==="
echo ""

echo -e "${BLUE}Files importing PathManager:${NC}"
grep -rn "from backend.core.paths import" opencv_surveillance/backend/ --include="*.py" 2>/dev/null | \
    grep -v "__pycache__" || echo "None found"

echo ""
echo "=== 3. Files That Should Use PathManager ==="
echo ""

echo -e "${YELLOW}Finding files with path references that don't import PathManager...${NC}"
echo ""

# Create temp file for results
TEMP_FILE=$(mktemp)

# Find files with path keywords
find opencv_surveillance/backend -name "*.py" -type f 2>/dev/null | while read file; do
    # Skip __pycache__ and test files
    if [[ "$file" == *"__pycache__"* ]] || [[ "$file" == *"test_"* ]]; then
        continue
    fi

    # Check if file contains path keywords
    if grep -q -E 'recordings|snapshots|faces.*folder|data/' "$file" 2>/dev/null; then
        # Check if it imports PathManager
        if ! grep -q "from backend.core.paths import" "$file" 2>/dev/null; then
            # Check if it's the paths.py file itself
            if [[ "$file" != *"paths.py" ]]; then
                echo "$file" >> "$TEMP_FILE"
            fi
        fi
    fi
done

if [ -s "$TEMP_FILE" ]; then
    cat "$TEMP_FILE" | while read file; do
        echo -e "${RED}⚠️  $file${NC}"

        # Show relevant lines
        echo "    Path references:"
        grep -n -E 'recordings|snapshots|data/|faces' "$file" 2>/dev/null | head -3 | sed 's/^/      /'
        echo ""
    done
else
    echo -e "${GREEN}✓ All files with path references are using PathManager!${NC}"
fi

rm -f "$TEMP_FILE"

echo ""
echo "=== 4. Database Path Format Check ==="
echo ""

echo -e "${BLUE}Checking database for path formats...${NC}"
cd opencv_surveillance

if [ -f "surveillance.db" ]; then
    echo ""
    echo "Sample snapshot paths:"
    python3 -c "
import sqlite3
conn = sqlite3.connect('surveillance.db')
cursor = conn.cursor()
try:
    cursor.execute('SELECT snapshot_path FROM motion_detection_events WHERE snapshot_path IS NOT NULL LIMIT 5')
    for row in cursor.fetchall():
        path = row[0]
        if path.startswith('/'):
            print(f'  ❌ ABSOLUTE: {path}')
        else:
            print(f'  ✓ RELATIVE: {path}')
except Exception as e:
    print(f'  Error: {e}')
finally:
    conn.close()
" 2>/dev/null || echo "  Database query failed"

    echo ""
    echo "Sample recording paths:"
    python3 -c "
import sqlite3
conn = sqlite3.connect('surveillance.db')
cursor = conn.cursor()
try:
    cursor.execute('SELECT recording_path FROM recording_events WHERE recording_path IS NOT NULL LIMIT 5')
    for row in cursor.fetchall():
        path = row[0]
        if path.startswith('/'):
            print(f'  ❌ ABSOLUTE: {path}')
        else:
            print(f'  ✓ RELATIVE: {path}')
except Exception as e:
    print(f'  Error: {e}')
finally:
    conn.close()
" 2>/dev/null || echo "  Database query failed"
else
    echo "  Database not found: surveillance.db"
fi

cd ..

echo ""
echo "=== 5. Frontend Path References ==="
echo ""

echo -e "${YELLOW}Checking for direct file paths in frontend...${NC}"
grep -rn "file://" opencv_surveillance/frontend/src/ --include="*.jsx" --include="*.js" 2>/dev/null || \
    echo -e "${GREEN}✓ No direct file:// paths found${NC}"

echo ""
echo -e "${YELLOW}Checking for hardcoded /recordings/ or /data/ paths...${NC}"
grep -rn '"/recordings/\|"/data/' opencv_surveillance/frontend/src/ --include="*.jsx" --include="*.js" 2>/dev/null | \
    head -10 || echo -e "${GREEN}✓ No hardcoded paths found (or all are API endpoints)${NC}"

echo ""
echo "========================================"
echo "Audit Complete"
echo "========================================"
echo ""
echo "Recommendations:"
echo "1. Update any files shown in red (⚠️) to use PathManager"
echo "2. Ensure all database paths are relative (not absolute)"
echo "3. Frontend should only use API endpoints, not direct paths"
echo ""
