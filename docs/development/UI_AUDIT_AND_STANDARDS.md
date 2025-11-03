# OpenEye UI Audit & Design Standards v3.7.0

**Date**: 2025-11-01
**Design Philosophy**: Apple Human Interface Guidelines + Material-UI Components
**Goal**: Intuitive, consistent, accessible user interface across all themes

---

## 📋 Table of Contents

1. [Current State Audit](#current-state-audit)
2. [Design Principles](#design-principles)
3. [Component Standards](#component-standards)
4. [Page-by-Page Analysis](#page-by-page-analysis)
5. [Implementation Roadmap](#implementation-roadmap)

---

## 🔍 Current State Audit

### Pages Audited (19 Total)

#### Main Application Pages
1. **LiveDashboard** (sections/LiveDashboard.jsx)
2. **DashboardPage** (wrapper)
3. **RecordingsPage** (Events & History)
4. **TimelineView** (Timeline Playback)
5. **CameraManagementPage**
6. **CameraDiscoveryPage**
7. **FaceManagementPage**
8. **FaceClusteringPage**
9. **AutomationsPage**

#### System Pages
10. **AlertSettingsPage**
11. **NotificationSettingsPage**
12. **SystemSettingsPage**
13. **TwoFactorSettings**
14. **HardwareDetectionPage**
15. **PerformanceDashboard**
16. **ThemeSelectorPage**

#### Utility Pages
17. **LoginPage**
18. **FirstRunSetup**
19. **RecordingsPage** (duplicate listing?)

### Components Audited (20+ Total)
- AssignNameModal
- CameraSettingsModal
- ClusterCard, ClusterDetailModal, DeleteClusterModal, MergeClustersModal
- ErrorBoundary
- HelpButton
- KeyboardShortcuts
- LoadingSkeleton
- Modal (base component)
- MotionZoneEditor
- PipVideoPlayer
- PTZControl
- Pagination
- Switch
- WebSocketStatus

---

## 🎨 Design Principles (Apple HIG)

### Core Principles

#### 1. **Clarity**
- Text is legible at every size
- Icons are precise and lucid
- Adornments are subtle and appropriate
- Functionality is obvious

#### 2. **Deference**
- Fluid motion and crisp, beautiful interface
- Content fills the screen
- Translucency and blurring convey hierarchy

#### 3. **Depth**
- Visual layers and realistic motion
- Touch enhances delight and enables access
- Heightens focus and understanding

### Specific Guidelines Applied

#### Typography (HIG Foundations)
- **San Francisco Font Family** (fallback: system-ui, -apple-system)
- **Font Sizes**:
  - Large Title: 34px (bold)
  - Title 1: 28px (regular)
  - Title 2: 22px (regular)
  - Title 3: 20px (regular)
  - Headline: 17px (semibold)
  - Body: 17px (regular)
  - Callout: 16px (regular)
  - Subhead: 15px (regular)
  - Footnote: 13px (regular)
  - Caption 1: 12px (regular)
  - Caption 2: 11px (regular)

#### Color (HIG Foundations)
- **Semantic Colors**: Use meaning over arbitrary choices
  - Blue: Interactive elements
  - Green: Success, positive actions
  - Yellow: Warning
  - Red: Destructive actions, errors
  - Gray: Secondary elements
- **Dynamic Colors**: Adapt to light/dark modes
- **Vibrancy**: Layer colors for depth

#### Spacing (8pt Grid System)
- Base unit: 8px
- All margins, padding, gaps: multiples of 8 (8, 16, 24, 32, 40, 48...)
- Minimum touch target: 44x44px (Apple HIG)

#### Motion & Animation
- **Duration**: 200-300ms for most transitions
- **Easing**: ease-in-out for natural feel
- **Purpose**: Every animation should communicate or aid understanding

---

## 🧩 Component Standards (HIG + MUI)

### Button System

Following HIG button styles with MUI implementation:

#### Primary Button
```jsx
<Button
  variant="filled"
  size="large"
  sx={{
    minHeight: '44px',
    minWidth: '44px',
    borderRadius: '8px',
    textTransform: 'none',
    fontSize: '17px',
    fontWeight: 600,
    padding: '12px 24px',
    boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
    '&:hover': {
      boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
      transform: 'translateY(-1px)',
    },
    transition: 'all 200ms ease-in-out'
  }}
>
  Primary Action
</Button>
```

**Usage**: Main actions (Save, Submit, Confirm)
**Visual**: Filled, vibrant color, prominent

#### Secondary Button
```jsx
<Button
  variant="outlined"
  size="large"
  sx={{
    minHeight: '44px',
    borderRadius: '8px',
    textTransform: 'none',
    fontSize: '17px',
    fontWeight: 500,
    padding: '12px 24px',
    borderWidth: '1.5px',
  }}
>
  Secondary Action
</Button>
```

**Usage**: Alternative actions (Cancel, Back)
**Visual**: Outlined, less prominent

#### Tertiary Button
```jsx
<Button
  variant="text"
  size="medium"
  sx={{
    minHeight: '44px',
    borderRadius: '8px',
    textTransform: 'none',
    fontSize: '15px',
    fontWeight: 500,
    padding: '8px 16px',
  }}
>
  Tertiary Action
</Button>
```

**Usage**: Subtle actions (Learn More, View Details)
**Visual**: Text only, minimal

#### Destructive Button
```jsx
<Button
  variant="filled"
  color="error"
  sx={{
    minHeight: '44px',
    borderRadius: '8px',
    textTransform: 'none',
    fontSize: '17px',
    fontWeight: 600,
  }}
>
  Delete
</Button>
```

**Usage**: Dangerous actions (Delete, Remove, Clear)
**Visual**: Red, prominent, with confirmation modal

---

### Text Field System

Following HIG input design:

#### Standard Text Field
```jsx
<TextField
  variant="outlined"
  fullWidth
  sx={{
    '& .MuiOutlinedInput-root': {
      borderRadius: '8px',
      minHeight: '44px',
      fontSize: '17px',
      backgroundColor: 'var(--input-background)',
      '&:hover fieldset': {
        borderColor: 'var(--input-border-hover)',
        borderWidth: '1.5px',
      },
      '&.Mui-focused fieldset': {
        borderColor: 'var(--accent-color)',
        borderWidth: '2px',
      }
    },
    '& .MuiInputLabel-root': {
      fontSize: '17px',
      '&.Mui-focused': {
        color: 'var(--accent-color)',
      }
    }
  }}
  label="Label"
  placeholder="Placeholder text"
/>
```

**Features**:
- 44px minimum height
- 8px border radius
- Clear focus states
- Accessible labels
- Placeholder guidance

#### Search Field
```jsx
<TextField
  variant="outlined"
  fullWidth
  placeholder="Search..."
  InputProps={{
    startAdornment: (
      <InputAdornment position="start">
        <SearchIcon />
      </InputAdornment>
    ),
  }}
  sx={{
    '& .MuiOutlinedInput-root': {
      borderRadius: '24px', // Pill shape for search
      backgroundColor: 'var(--search-background)',
    }
  }}
/>
```

**Features**:
- Pill-shaped (24px radius)
- Search icon prefix
- Lighter background
- No label (uses placeholder)

---

### Switch/Toggle Component

Following iOS switch design (already created at Switch.jsx):

#### Standard Switch
```jsx
<Switch
  checked={enabled}
  onChange={(e) => setEnabled(e.target.checked)}
  sx={{
    width: '51px',
    height: '31px',
    padding: 0,
    '& .MuiSwitch-switchBase': {
      padding: '2px',
      '&.Mui-checked': {
        transform: 'translateX(20px)',
        '& + .MuiSwitch-track': {
          backgroundColor: 'var(--accent-color)',
          opacity: 1,
        },
        '& .MuiSwitch-thumb': {
          backgroundColor: '#fff',
        }
      }
    },
    '& .MuiSwitch-thumb': {
      width: '27px',
      height: '27px',
      backgroundColor: '#fff',
      boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
    },
    '& .MuiSwitch-track': {
      borderRadius: '31px',
      backgroundColor: 'var(--toggle-off-color)',
      opacity: 1,
    }
  }}
/>
```

**Features**:
- iOS-style 51x31px switch
- Smooth sliding animation
- Clear on/off states
- Accessible keyboard control

**Note**: Switch.jsx component already exists and should be reviewed for HIG compliance

---

### Card Component

Following HIG card/surface design:

#### Standard Card
```jsx
<Card
  sx={{
    borderRadius: '16px',
    boxShadow: '0 2px 16px rgba(0,0,0,0.08)',
    padding: '24px',
    backgroundColor: 'var(--card-background)',
    border: '1px solid var(--card-border)',
    transition: 'all 200ms ease-in-out',
    '&:hover': {
      boxShadow: '0 4px 24px rgba(0,0,0,0.12)',
      transform: 'translateY(-2px)',
    }
  }}
>
  <CardContent>
    {/* Content */}
  </CardContent>
</Card>
```

**Features**:
- 16px border radius (rounded corners)
- Subtle elevation shadow
- Hover lift effect
- Consistent padding (24px = 3 grid units)

#### Interactive Card (clickable)
- Add cursor: pointer
- Increase hover transform
- Add active state

---

### Modal/Dialog Component

Following HIG modal design:

#### Standard Modal
```jsx
<Modal
  open={open}
  onClose={onClose}
  sx={{
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  }}
>
  <Box
    sx={{
      backgroundColor: 'var(--modal-background)',
      borderRadius: '16px',
      boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
      padding: '32px',
      maxWidth: '600px',
      width: '90%',
      maxHeight: '90vh',
      overflow: 'auto',
    }}
  >
    {/* Modal content */}
  </Box>
</Modal>
```

**Features**:
- Centered on screen
- Rounded corners (16px)
- Backdrop blur (via CSS)
- Smooth fade-in animation
- Responsive sizing

---

## 📄 Page-by-Page Analysis

### 1. LiveDashboard

**Current Issues**:
- Mixed button styles
- Inconsistent spacing
- Camera cards lack hover states
- No skeleton loading states (✅ recently added)

**Recommendations**:
- Standardize camera card design
- Add hover lift effect
- Use consistent button sizes (44px min)
- Improve PiP button prominence

**Priority**: HIGH (main landing page)

---

### 2. CameraManagementPage

**Current Issues**:
- Form inputs vary in size/style
- Add Camera button needs prominence
- Table lacks hover states
- Action buttons inconsistent

**Recommendations**:
- Use MUI DataGrid for camera table
- Standardize all form fields
- Make "Add Camera" primary button
- Add row hover highlight

**Priority**: HIGH (frequently used)

---

### 3. FaceManagementPage / FaceClusteringPage

**Current Issues**:
- Upload button needs better visibility
- Face cards lack consistent sizing
- Clustering actions unclear
- Modal designs vary

**Recommendations**:
- Standardize face card component
- Make upload area drag-and-drop
- Improve clustering UI with progress indicators
- Consistent modal design

**Priority**: MEDIUM

---

### 4. AlertSettingsPage / NotificationSettingsPage

**Current Issues**:
- Toggle switches vary in design
- Form layout inconsistent
- Submit buttons placement varies

**Recommendations**:
- Use universal Switch component
- Form grid layout (8pt system)
- Fixed submit button position (bottom right)
- Clear section headers

**Priority**: MEDIUM

---

### 5. HardwareDetectionPage

**Current Issues**:
- Newly created, basic design
- Lacks interactive elements
- No feature management UI yet

**Recommendations**:
- Add feature toggle switches
- "Rescan Hardware" prominent button
- Progress indicators for scanning
- Hardware tier badge design

**Priority**: HIGH (new feature)

---

### 6. PerformanceDashboard

**Current Issues**:
- Exists but needs review
- Chart styling
- Metric card design

**Recommendations**:
- Consistent metric card style
- Recharts customization for theme
- Real-time update indicators
- Refresh button

**Priority**: MEDIUM

---

### 7. SystemSettingsPage

**Current Issues**:
- Many form fields
- Settings grouped poorly
- Save button placement

**Recommendations**:
- Tab-based organization
- Accordion for setting groups
- Auto-save with notification
- Clear reset to defaults option

**Priority**: MEDIUM

---

### 8. LoginPage / FirstRunSetup

**Current Issues**:
- Basic form design
- No password visibility toggle
- Submit button not prominent

**Recommendations**:
- Centered card design
- Password show/hide icon
- Large primary submit button
- Loading state on submit

**Priority**: LOW (simple, functional)

---

### 9. TimelineView

**Current Issues**:
- Complex interface
- Controls not intuitive
- Timeline scrubbing needs work

**Recommendations**:
- Larger playback controls (44px)
- Clear timeline markers
- Speed control prominent
- Event tags visible

**Priority**: MEDIUM

---

### 10. AutomationsPage

**Current Issues**:
- Rule cards basic design
- Add rule button needs prominence
- Condition builder complex

**Recommendations**:
- Visual rule cards with icons
- Prominent "Create Automation" button
- Drag-and-drop rule reordering
- Clear enable/disable switches

**Priority**: MEDIUM

---

## 🎨 Theme Consistency Requirements

### All 9 Themes Must Support:

1. **CSS Variables** (consistent naming):
```css
:root {
  /* Primary */
  --accent-color: #007AFF;
  --accent-hover: #0051D5;

  /* Backgrounds */
  --background-primary: #FFFFFF;
  --background-secondary: #F5F5F7;
  --card-background: #FFFFFF;
  --modal-background: #FFFFFF;

  /* Text */
  --text-primary: #000000;
  --text-secondary: #6E6E73;
  --text-tertiary: #8E8E93;

  /* Borders */
  --border-color: #E5E5EA;
  --border-hover: #D1D1D6;

  /* States */
  --success-color: #34C759;
  --warning-color: #FF9500;
  --error-color: #FF3B30;

  /* Interactive */
  --button-primary-bg: var(--accent-color);
  --button-primary-text: #FFFFFF;
  --button-secondary-border: var(--accent-color);
  --toggle-on-color: var(--accent-color);
  --toggle-off-color: #E5E5EA;

  /* Shadows */
  --shadow-sm: 0 2px 8px rgba(0,0,0,0.08);
  --shadow-md: 0 4px 16px rgba(0,0,0,0.12);
  --shadow-lg: 0 8px 32px rgba(0,0,0,0.16);

  /* Spacing (8pt grid) */
  --spacing-xs: 8px;
  --spacing-sm: 16px;
  --spacing-md: 24px;
  --spacing-lg: 32px;
  --spacing-xl: 48px;

  /* Border Radius */
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-full: 9999px;

  /* Transitions */
  --transition-fast: 150ms ease-in-out;
  --transition-normal: 200ms ease-in-out;
  --transition-slow: 300ms ease-in-out;
}
```

2. **Theme-Specific Overrides** (keep unique palettes):
- Default: Blue accent
- Superman: Red/Blue accent
- Batman: Dark gray/Yellow accent
- Spider-Man: Red/Blue accent
- Wonder Woman: Red/Gold accent
- Flash: Red/Yellow accent
- Aquaman: Teal/Orange accent
- Green Lantern: Green accent
- Cyberpunk: Neon accent

3. **Dark Mode Support**:
- Each theme must have dark variant
- Use `prefers-color-scheme` media query
- Adjust shadows for dark backgrounds
- Ensure text contrast ratios (WCAG AA)

---

## 🚀 Implementation Roadmap

### Phase 1: Component Library (Week 1)

**Priority**: Create universal components

1. **Button Component** (`components/Button.jsx`)
   - Primary, Secondary, Tertiary variants
   - Size options (small, medium, large)
   - Loading states
   - Icon support

2. **TextField Component** (`components/TextField.jsx`)
   - Standard, Search variants
   - Error states
   - Helper text
   - Character counter

3. **Switch Component** (enhance existing `components/Switch.jsx`)
   - Review for HIG compliance
   - Add label positioning
   - Add disabled state styling

4. **Card Component** (`components/Card.jsx`)
   - Standard, Interactive variants
   - Optional header/footer
   - Loading skeleton

5. **Modal Component** (enhance existing `components/Modal.jsx`)
   - Backdrop blur effect
   - Animation improvements
   - Standardized padding

**Estimated Time**: 2-3 days

---

### Phase 2: Theme Standardization (Week 1-2)

**Priority**: Ensure consistency across themes

1. **Update themes.css**
   - Standardize CSS variable names
   - Add missing variables
   - Ensure all 9 themes complete

2. **Create Theme Utility** (`utils/theme.js`)
   - Helper functions for dynamic theming
   - MUI theme provider integration

3. **Test All Themes**
   - Verify visual consistency
   - Check contrast ratios
   - Ensure dark mode support

**Estimated Time**: 1-2 days

---

### Phase 3: Page Updates (Week 2-3)

**Priority Order**:

1. **LiveDashboard** (HIGH - most visible)
   - Update camera cards
   - Standardize buttons
   - Improve PiP UI

2. **HardwareDetectionPage** (HIGH - new feature)
   - Add feature management UI
   - Rescan hardware button
   - Scan history display

3. **CameraManagementPage** (HIGH - frequently used)
   - Form standardization
   - Table improvements
   - Action button consistency

4. **AlertSettingsPage / NotificationSettingsPage** (MEDIUM)
   - Form layout
   - Switch components
   - Submit button placement

5. **FaceManagementPage / FaceClusteringPage** (MEDIUM)
   - Card consistency
   - Upload improvements
   - Modal standardization

6. **AutomationsPage** (MEDIUM)
   - Rule card design
   - Create automation flow
   - Enable/disable switches

7. **PerformanceDashboard** (MEDIUM)
   - Metric cards
   - Chart styling
   - Refresh button

8. **SystemSettingsPage** (MEDIUM)
   - Tab organization
   - Form groups
   - Save flow

9. **TimelineView** (MEDIUM)
   - Control sizing
   - Timeline design
   - Event markers

10. **LoginPage / FirstRunSetup** (LOW - functional)
    - Minor improvements
    - Consistency check

**Estimated Time**: 5-7 days

---

### Phase 4: Polish & Testing (Week 3-4)

1. **Accessibility Audit**
   - Keyboard navigation
   - Screen reader support
   - Focus indicators
   - ARIA labels

2. **Responsive Testing**
   - Mobile breakpoints
   - Tablet layouts
   - Desktop optimization

3. **Performance Testing**
   - Animation performance
   - Bundle size impact
   - Lazy loading components

4. **Cross-Browser Testing**
   - Chrome, Firefox, Safari, Edge
   - iOS Safari, Chrome Mobile

**Estimated Time**: 2-3 days

---

## 📊 Success Metrics

### Design Goals

1. **Consistency**: 95%+ component reuse across pages
2. **Accessibility**: WCAG AA compliance (4.5:1 contrast)
3. **Performance**: <50ms interaction response time
4. **Usability**: <3 clicks to any major feature

### User Experience Goals

1. **Clarity**: Users understand actions without help
2. **Efficiency**: Common tasks completed quickly
3. **Delight**: Smooth animations, satisfying interactions
4. **Trust**: Professional, polished appearance

---

## 📝 Notes

### MUI Integration Strategy

**Install MUI if not already**:
```bash
npm install @mui/material @emotion/react @emotion/styled
```

**Use MUI Components**:
- Button, TextField, Switch, Card, Modal
- DataGrid (for tables)
- Autocomplete (for search/filters)
- Accordion, Tabs (for organization)

**Customize with CSS Variables**:
- Override MUI theme with CSS vars
- Maintain theme switching capability
- Keep bundle size reasonable

### Apple HIG Resources

**Reference Links**:
- Getting Started: https://developer.apple.com/design/human-interface-guidelines/designing-for-macos
- Foundations: Typography, Color, Layout
- Patterns: Navigation, User Interaction
- Components: Buttons, Text Fields, Switches
- Technologies: Accessibility, Dark Mode

### Development Workflow

1. **Component First**: Build in isolation
2. **Theme Test**: Check all 9 themes
3. **Page Integration**: Update pages incrementally
4. **User Testing**: Gather feedback
5. **Iterate**: Refine based on usage

---

## ✅ Validation Checklist

Before considering UI overhaul complete:

- [ ] All components follow HIG principles
- [ ] 9 themes consistent (unique palettes preserved)
- [ ] All pages use universal components
- [ ] 44px minimum touch targets
- [ ] 8pt grid system throughout
- [ ] Smooth animations (200-300ms)
- [ ] Accessible keyboard navigation
- [ ] WCAG AA contrast ratios
- [ ] Responsive on mobile/tablet/desktop
- [ ] Dark mode support in all themes
- [ ] Loading states for async actions
- [ ] Error states clearly communicated
- [ ] Success feedback immediate

---

**Document Version**: 1.0
**Last Updated**: 2025-11-01
**Status**: Audit Complete - Implementation Pending
