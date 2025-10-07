# Theme Rename + Docker Fix Update

## Changes Made

### 1. Fixed Docker "uvicorn: not found" Error ✅

**Problem**: Container running as user `openeye` couldn't find uvicorn because Python packages were installed to `/root/.local` but not accessible to non-root user.

**Solution**: 
- Updated Dockerfile to copy Python packages to `/home/openeye/.local` instead of `/root/.local`
- Updated entrypoint.sh to use `/home/openeye/.local/bin` in PATH
- Added proper ownership with `chown -R openeye:openeye /home/openeye/.local`

**Files Modified**:
- `opencv-surveillance/Dockerfile`
- `opencv-surveillance/docker/entrypoint.sh`

### 2. Updated Theme Names Across Project ✅

Changed theme names from full superhero names to abbreviated versions to avoid trademark issues:

| Old Name | New Name | Description |
|----------|----------|-------------|
| Superman | Sman | Classic red/blue |
| Batman | Bman | Dark knight |
| Wonder Woman | W Woman | Warrior gold |
| The Flash | Flah | Speed red |
| Aquaman | Aman | Ocean teal |
| Cyborg | Cy | Tech silver |
| Green Lantern | G Lantern | Willpower green |
| Default | Default | Professional blue |

**Files Modified**:
- `opencv-surveillance/frontend/src/pages/ThemeSelectorPage.jsx` - Display names and descriptions
- `opencv-surveillance/frontend/src/utils/helpContent.js` - Help text
- `README.md` - Already had correct names

**Files NOT Modified** (internal code identifiers remain the same):
- `ThemeContext.jsx` - Internal THEMES constants (superman, batman, etc.)
- CSS files - Theme class names remain unchanged (.superman-theme, etc.)
- This maintains backwards compatibility with saved user preferences

### 3. Next Steps

#### Consolidate Documentation Files (Recommended Structure):

**Keep as Primary Documentation**:
1. **README.md** - Main project overview, features, quickstart, architecture
2. **DOCKER_HUB_OVERVIEW.md** - Docker Hub specific info, pull instructions, quick start
3. **DOCKER_DEPLOYMENT_GUIDE.md** - Complete Docker deployment guide

**Consolidate Into README or Remove**:
- CAMERA_DISCOVERY_FEATURE.md → Integrate into README features section
- FIRST_RUN_SETUP_IMPLEMENTATION.md → Integrate into README or user guide
- HELP_SYSTEM_IMPLEMENTATION.md → Archive or move to docs/
- FINAL_VALIDATION_REPORT.md → Archive (historical)
- FINAL_PROJECT_CHECK_SUMMARY.md → Archive (historical)
- SECRET_KEYS_DOCUMENTATION.md → Archive (covered in DOCKER_DEPLOYMENT_GUIDE)
- DOCKER_DESKTOP_GUIDE_ADDED.md → Archive (covered in DOCKER_DEPLOYMENT_GUIDE)
- DOCKER_UPDATE_SUMMARY.md → Archive (historical)
- DEPLOYMENT_UPDATE_v3.1.0_DOCS.md → Archive (historical)
- RELEASE_NOTES_v3.1.0.md → Keep for releases

**Proposed Structure**:
```
/OpenEye/
├── README.md (Main project documentation - comprehensive)
├── DOCKER_HUB_OVERVIEW.md (Docker Hub description - concise)
├── LICENSE
├── RELEASE_NOTES_v3.1.0.md (Release notes)
├── opencv-surveillance/
│   ├── DOCKER_DEPLOYMENT_GUIDE.md (Detailed Docker guide)
│   └── docs/
│       ├── USER_GUIDE.md
│       ├── API_REFERENCE.md
│       └── archives/ (Historical implementation docs)
└── archives/ (Move old .md files here)
```

