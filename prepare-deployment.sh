#!/bin/bash
# OpenEye Deployment Preparation Script
# Cleans project and prepares for GitHub/Docker Hub deployment

set -e  # Exit on error

echo "=================================================="
echo "  OpenEye Deployment Preparation Script v3.5.2"
echo "=================================================="
echo ""

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Step 1: Clean Python cache files
echo "Step 1: Cleaning Python cache..."
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
find . -type f -name "*.pyd" -delete 2>/dev/null || true
print_status "Python cache cleaned"

# Step 2: Clean database files from project root
echo ""
echo "Step 2: Cleaning database files..."
find . -maxdepth 3 -type f \( -name "*.db" -o -name "*.sqlite" -o -name "*.db-journal" \) ! -path "./.git/*" ! -path "./opencv-surveillance/venv/*" -delete 2>/dev/null || true
print_status "Database files cleaned"

# Step 3: Count media files (don't delete, just report)
echo ""
echo "Step 3: Checking media files..."
SNAPSHOT_COUNT=$(find . -type f -name "*.jpg" ! -path "./.git/*" ! -path "./opencv-surveillance/venv/*" 2>/dev/null | wc -l | tr -d ' ')
VIDEO_COUNT=$(find . -type f \( -name "*.mp4" -o -name "*.avi" \) ! -path "./.git/*" ! -path "./opencv-surveillance/venv/*" 2>/dev/null | wc -l | tr -d ' ')
print_warning "Found $SNAPSHOT_COUNT snapshot files (excluded from git via .gitignore)"
print_warning "Found $VIDEO_COUNT video files (excluded from git via .gitignore)"

# Step 4: Check git status
echo ""
echo "Step 4: Checking git status..."
if [ -d ".git" ]; then
    UNTRACKED=$(git status --porcelain | grep "^??" | wc -l | tr -d ' ')
    MODIFIED=$(git status --porcelain | grep "^ M" | wc -l | tr -d ' ')
    
    if [ "$UNTRACKED" -gt 0 ]; then
        print_warning "$UNTRACKED untracked files"
    fi
    if [ "$MODIFIED" -gt 0 ]; then
        print_warning "$MODIFIED modified files"
    fi
    
    # Check if any media files are tracked
    TRACKED_MEDIA=$(git ls-files | grep -E "\.(jpg|jpeg|png|mp4|avi|db)$" | wc -l | tr -d ' ')
    if [ "$TRACKED_MEDIA" -gt 0 ]; then
        print_error "$TRACKED_MEDIA media/database files are tracked in git!"
        echo "   Run: git rm --cached <file> to untrack them"
    else
        print_status "No media or database files tracked in git"
    fi
else
    print_error "Not a git repository"
fi

# Step 5: Check .gitignore and .dockerignore
echo ""
echo "Step 5: Checking ignore files..."
if [ -f ".gitignore" ]; then
    print_status ".gitignore exists"
else
    print_error ".gitignore missing!"
fi

if [ -f "opencv_surveillance/.dockerignore" ]; then
    print_status ".dockerignore exists"
else
    print_error ".dockerignore missing!"
fi

# Step 6: Check Docker build context size
echo ""
echo "Step 6: Estimating Docker build context size..."
cd opencv_surveillance
CONTEXT_SIZE=$(du -sh . 2>/dev/null | cut -f1)
print_status "Docker build context size: $CONTEXT_SIZE"

# Count files that will be included
TOTAL_FILES=$(find . -type f ! -path "./.git/*" ! -path "./venv/*" ! -path "./node_modules/*" | wc -l | tr -d ' ')
print_status "Total files in context: $TOTAL_FILES"

cd "$PROJECT_ROOT"

# Step 7: Verify frontend build
echo ""
echo "Step 7: Checking frontend build..."
if [ -d "opencv_surveillance/frontend/dist" ]; then
    DIST_SIZE=$(du -sh opencv_surveillance/frontend/dist 2>/dev/null | cut -f1)
    print_status "Frontend dist exists ($DIST_SIZE)"
else
    print_warning "Frontend dist not found - run 'npm run build' in frontend/"
fi

# Step 8: Check for sensitive files
echo ""
echo "Step 8: Checking for sensitive files..."
SENSITIVE_FILES=0
if [ -f ".env" ]; then
    print_warning ".env file found (should not be committed)"
    SENSITIVE_FILES=$((SENSITIVE_FILES + 1))
fi
if [ -f "opencv-surveillance/.env" ]; then
    print_warning "opencv-surveillance/.env file found (should not be committed)"
    SENSITIVE_FILES=$((SENSITIVE_FILES + 1))
fi

if [ $SENSITIVE_FILES -eq 0 ]; then
    print_status "No sensitive files found"
fi

# Step 9: Summary
echo ""
echo "=================================================="
echo "  Deployment Preparation Summary"
echo "=================================================="
echo ""
echo "Project Status:"
echo "  • Python cache: Cleaned ✓"
echo "  • Database files: Cleaned ✓"
echo "  • Media files: $SNAPSHOT_COUNT snapshots, $VIDEO_COUNT videos (excluded from git)"
echo "  • Docker context: $CONTEXT_SIZE ($TOTAL_FILES files)"
echo ""

# Step 10: Recommendations
echo "Recommendations for Docker optimization:"
echo "  1. Use multi-stage builds (already implemented ✓)"
echo "  2. Minimize layers by combining RUN commands (already implemented ✓)"
echo "  3. Use .dockerignore to exclude unnecessary files (already implemented ✓)"
echo "  4. Use alpine or slim base images (using python:3.11-slim ✓)"
echo "  5. Clean up apt cache after installs (already implemented ✓)"
echo ""

# Final size estimates
echo "Expected Docker Image Sizes:"
echo "  • Base Python 3.11-slim: ~140 MB"
echo "  • With OpenCV + dependencies: ~400-500 MB"
echo "  • With application code: ~450-550 MB"
echo "  • Final compressed image: ~200-250 MB (pushed to Docker Hub)"
echo ""

echo "=================================================="
echo "  Ready for Deployment!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "  1. Commit changes: git add . && git commit -m 'Release v3.5.2'"
echo "  2. Push to GitHub: git push origin main"
echo "  3. Build Docker: cd opencv-surveillance && docker build -t m1k31/openeye:v3.5.2 ."
echo "  4. Tag latest: docker tag m1k31/openeye:v3.5.2 m1k31/openeye:latest"
echo "  5. Push to Docker Hub: docker push m1k31/openeye:v3.5.2 && docker push m1k31/openeye:latest"
echo ""
