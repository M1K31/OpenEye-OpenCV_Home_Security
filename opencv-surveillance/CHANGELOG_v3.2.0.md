# OpenEye v3.2.0 - Major UI/UX Restructure

## Release Date: October 7, 2025

## Overview
Complete restructure of the OpenEye UI with unified dark theme, consolidated settings, and improved navigation.

## Major Changes

### 1. **Unified Global Dark Theme** 
All pages now use a consistent dark theme with the following color palette:

- **Main Background**: `#262626` (dark gray)
- **Panel Background**: `#333333` (slightly darker gray)
- **Panel Borders**: `#4d4d4d` (lighter gray)
- **Headers & Text**: `#ffffff` (white)
- **Links**: `#007bff` (blue for clickable text)
- **Input Borders**: `#666666` (mid-tone gray)
- **Active State**: `#606060` (light gray)
- **Success**: `#28a745` (green)
- **Error**: `#dc3545` (red)
- **Warning**: `#ffc107` (yellow/orange)

Files Modified:
- Created `frontend/src/global-theme.css` - Global CSS variables and styling
- Updated `frontend/src/main.jsx` - Import global theme
- Updated `frontend/src/pages/LoginPage.jsx` - Dark theme styling
- Updated `frontend/src/pages/FirstRunSetup.css` - Dark theme for setup
- Updated `frontend/src/pages/DashboardPage.jsx` - Dark theme styling

### 2. **Settings Page Restructure**
Cameras, Faces, Alerts, and Themes are now consolidated into a unified Settings page with tabs.

**New Settings Structure**:
```
Settings (⚙️)
├── Cameras (📹)
├── Faces (👤)
├── Alerts (🔔)
└── Themes (🎨)
```

Files Modified:
- Replaced `frontend/src/pages/SettingsPage.jsx` - New tabbed interface
- Updated `frontend/src/pages/CameraManagementPage.jsx` - Added `embedded` prop support
- Updated `frontend/src/pages/FaceManagementPage.jsx` - Added `embedded` prop support
- Updated `frontend/src/pages/AlertSettingsPage.jsx` - Added `embedded` prop support
- Updated `frontend/src/pages/ThemeSelectorPage.jsx` - Added `embedded` prop support

### 3. **Simplified Dashboard**
Dashboard now has only two buttons in the header:
- ⚙️ **Settings** - Access all configuration
- 🚪 **Logout** - Exit the system

Files Modified:
- Updated `frontend/src/pages/DashboardPage.jsx` - Simplified header, dark theme styling

### 4. **Navigation Fixes**
- Fixed browser back button issue from Faces page
- All embedded pages hide their "Back to Dashboard" buttons when embedded in Settings
- Consistent navigation patterns using React Router's `useNavigate` hook

Files Modified:
- Updated `frontend/src/App.jsx` - Removed onBack prop from ThemeSelectorPage route
- Updated `frontend/src/pages/ThemeSelectorPage.jsx` - Uses useNavigate instead of callback

## Technical Details

### CSS Variables (Available Globally)
```css
--bg-main: #262626
--bg-panel: #333333
--border-panel: #4d4d4d
--border-input: #666666
--state-active: #606060
--text-primary: #ffffff
--text-link: #007bff
--color-success: #28a745
--color-error: #dc3545
--color-warning: #ffc107
--bg-hover: #404040
--bg-input: #2a2a2a
--shadow: rgba(0, 0, 0, 0.5)
```

### Embedded Page Pattern
Pages now accept an `embedded` prop to hide back navigation:

```jsx
const PageComponent = ({ embedded = false }) => {
  return (
    <div>
      {!embedded && (
        <button onClick={() => navigate('/')}>Back to Dashboard</button>
      )}
      {/* Page content */}
    </div>
  );
};
```

## Breaking Changes
- Theme customization moved from dedicated page to Settings → Themes tab
- Individual top-level navigation buttons removed from Dashboard
- Old SettingsPage.jsx backed up to SettingsPage.jsx.backup
- Old FirstRunSetup.css backed up to FirstRunSetup.css.backup

## User Experience Improvements
✅ Consistent dark theme across all pages (no more bright flashes)
✅ Centralized settings - everything in one place
✅ Cleaner Dashboard with less clutter
✅ Fixed browser back button navigation issues
✅ Better accessibility with high-contrast dark theme
✅ Responsive design maintained

## Migration Notes
- No database changes required
- No backend changes required
- Frontend-only update
- Existing user accounts and data preserved

## Next Steps for v3.2.1
- [ ] Add save confirmations to Alerts and Faces pages
- [ ] Implement Settings backend API endpoints
- [ ] Add keyboard navigation improvements
- [ ] Optimize theme switching performance
- [ ] Add export/import for all settings

## Files Backed Up
- `frontend/src/pages/SettingsPage.jsx.backup` (old settings implementation)
- `frontend/src/pages/FirstRunSetup.css.backup` (old light theme setup)
