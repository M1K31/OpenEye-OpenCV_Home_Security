#!/bin/bash
# Documentation Cleanup and Consolidation Script
# Organizes project documentation according to best practices

set -e

echo "=================================================="
echo "  OpenEye Documentation Cleanup"
echo "=================================================="
echo ""

# Create docs folder if it doesn't exist
mkdir -p docs
mkdir -p docs/deployment
mkdir -p docs/development

echo "Step 1: Moving user-facing documentation to docs/..."

# Keep in root: README.md, CHANGELOG.md, LICENSE, DOCKER_HUB_OVERVIEW.md
# Move everything else to docs/

# Move deployment-related docs
if [ -f "DEPLOYMENT_COMPLETE_v3.5.2.md" ]; then
    mv DEPLOYMENT_COMPLETE_v3.5.2.md docs/deployment/
    echo "  ✓ Moved DEPLOYMENT_COMPLETE_v3.5.2.md"
fi

if [ -f "DEPLOYMENT_READY.md" ]; then
    mv DEPLOYMENT_READY.md docs/deployment/
    echo "  ✓ Moved DEPLOYMENT_READY.md"
fi

if [ -f "DOCKER_OPTIMIZATION_GUIDE.md" ]; then
    mv DOCKER_OPTIMIZATION_GUIDE.md docs/deployment/
    echo "  ✓ Moved DOCKER_OPTIMIZATION_GUIDE.md"
fi

if [ -f "DOCKER_HUB_INFO.md" ]; then
    mv DOCKER_HUB_INFO.md docs/deployment/
    echo "  ✓ Moved DOCKER_HUB_INFO.md"
fi

if [ -f "MEDIA_EXCLUSION_VERIFICATION.md" ]; then
    mv MEDIA_EXCLUSION_VERIFICATION.md docs/deployment/
    echo "  ✓ Moved MEDIA_EXCLUSION_VERIFICATION.md"
fi

# Move development/implementation docs
if [ -f "BACKEND_FRONTEND_INTEGRATION_AUDIT.md" ]; then
    mv BACKEND_FRONTEND_INTEGRATION_AUDIT.md docs/development/
    echo "  ✓ Moved BACKEND_FRONTEND_INTEGRATION_AUDIT.md"
fi

if [ -f "BACKEND_FRONTEND_QUICK_FIX_SUMMARY.md" ]; then
    mv BACKEND_FRONTEND_QUICK_FIX_SUMMARY.md docs/development/
    echo "  ✓ Moved BACKEND_FRONTEND_QUICK_FIX_SUMMARY.md"
fi

# Move feature-specific docs
if [ -f "MOTION_DETECTION_EVENTS_COMPLETE.md" ]; then
    mv MOTION_DETECTION_EVENTS_COMPLETE.md docs/development/
    echo "  ✓ Moved MOTION_DETECTION_EVENTS_COMPLETE.md"
fi

if [ -f "MOTION_DETECTION_EVENTS_IMPLEMENTATION.md" ]; then
    mv MOTION_DETECTION_EVENTS_IMPLEMENTATION.md docs/development/
    echo "  ✓ Moved MOTION_DETECTION_EVENTS_IMPLEMENTATION.md"
fi

if [ -f "MOTION_DETECTION_SUCCESS_REPORT.md" ]; then
    mv MOTION_DETECTION_SUCCESS_REPORT.md docs/development/
    echo "  ✓ Moved MOTION_DETECTION_SUCCESS_REPORT.md"
fi

if [ -f "MOTION_DETECTION_INTEGRATION_TEST_RESULTS.md" ]; then
    mv MOTION_DETECTION_INTEGRATION_TEST_RESULTS.md docs/development/
    echo "  ✓ Moved MOTION_DETECTION_INTEGRATION_TEST_RESULTS.md"
fi

echo ""
echo "Step 2: Removing session summaries and task-specific docs..."

# Remove session summaries (info already in CHANGELOG.md)
rm -f SESSION_SUMMARY_*.md
echo "  ✓ Removed session summaries"

# Remove version-specific task docs (info in CHANGELOG.md)
rm -f SNAPSHOT_DISPLAY_FIX_v3.5.2.md
rm -f SLIDER_VALIDATION_FIXES_v3.5.2.md
rm -f SNAPSHOTS_PATH_FEATURE_v3.5.2.md
rm -f USER_PATH_AUDIT_v3.5.2.md
rm -f HIG_SPLIT_VIEW_IMPLEMENTATION_v3.5.2.md
rm -f IMPLEMENTATION_SUMMARY_v3.5.2.md
rm -f TESTING_GUIDE_v3.5.2.md
echo "  ✓ Removed version-specific task documents"

# Remove release notes (info in CHANGELOG.md)
rm -f RELEASE_NOTES_v3.5.2.md
echo "  ✓ Removed release notes (consolidated in CHANGELOG.md)"

# Remove quick reference (duplicate of README sections)
rm -f QUICK_REFERENCE.md
echo "  ✓ Removed QUICK_REFERENCE.md"

echo ""
echo "Step 3: Documentation structure:"
echo ""
echo "Root files:"
ls -1 *.md 2>/dev/null || echo "  (none)"
echo ""
echo "docs/ folder:"
find docs -name "*.md" -type f 2>/dev/null | sed 's|^|  |' || echo "  (none)"
echo ""
echo "=================================================="
echo "  Cleanup Complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "  1. Review CHANGELOG.md for completeness"
echo "  2. Check README.md for GitHub audience"
echo "  3. Verify DOCKER_HUB_OVERVIEW.md for Docker users"
echo "  4. Remove hardcoded paths from all .md files"
echo "  5. Commit changes"
