# Component API Reference - v3.5.3
**Quick reference for new Phase 2 components**

## LoadingSkeleton

Displays animated loading placeholders with Apple-style shimmer effect.

### Import
```jsx
import LoadingSkeleton, { 
  SkeletonCard, 
  SkeletonCameraCard, 
  SkeletonList,
  SkeletonEventTimeline 
} from './components/LoadingSkeleton';
```

### Basic Usage
```jsx
<LoadingSkeleton 
  variant="text"    // 'text' | 'card' | 'avatar' | 'button' | 'video'
  width="60%"       // String or number
  height={20}       // Number (pixels)
  count={1}         // Number of skeleton elements
  rounded={false}   // Force pill shape
  className=""      // Additional CSS classes
/>
```

### Pre-configured Patterns
```jsx
// Camera card with video placeholder
<SkeletonCameraCard />

// Generic card with image + text
<SkeletonCard />

// List of items with avatars
<SkeletonList count={5} />

// Timeline/activity feed
<SkeletonEventTimeline count={10} />
```

### Features
- ✅ Respects `prefers-reduced-motion`
- ✅ Respects user "Reduce Motion" setting
- ✅ Theme-aware backgrounds
- ✅ 8pt grid spacing
- ✅ Accessible (aria-label, role="status")

---

## Modal

Display content in an overlay with backdrop blur and focus trap.

### Import
```jsx
import Modal, { ConfirmModal } from './components/Modal';
```

### Basic Modal
```jsx
<Modal
  isOpen={isOpen}                    // Required: boolean
  onClose={() => setIsOpen(false)}   // Required: function
  title="Modal Title"                // Optional: string
  size="md"                          // Optional: 'sm' | 'md' | 'lg' | 'xl'
  showCloseButton={true}             // Optional: boolean (default: true)
  closeOnBackdropClick={true}        // Optional: boolean (default: true)
  closeOnEscape={true}               // Optional: boolean (default: true)
  footer={<div>Custom footer</div>}  // Optional: ReactNode
>
  <p>Modal content here</p>
</Modal>
```

### Confirmation Modal
```jsx
<ConfirmModal
  isOpen={showConfirm}
  onClose={() => setShowConfirm(false)}
  onConfirm={() => {
    // Handle confirmation
    console.log('User confirmed!');
  }}
  title="Confirm Action"
  message="Are you sure you want to proceed?"
  confirmText="Yes, Continue"        // Default: "Confirm"
  cancelText="No, Cancel"            // Default: "Cancel"
  variant="primary"                  // 'primary' | 'danger'
/>
```

### Size Variants
- **sm:** 400px - Quick confirmations
- **md:** 600px - Default, forms and content
- **lg:** 800px - Larger forms
- **xl:** 1200px - Galleries, tables

### Features
- ✅ Backdrop blur (10px, Safari compatible)
- ✅ Smooth animations (slide-up + fade)
- ✅ Focus trap (keyboard nav contained)
- ✅ Escape key closes
- ✅ Click outside closes
- ✅ Body scroll prevention
- ✅ Focus restoration
- ✅ Accessible (ARIA attributes)
- ✅ Mobile responsive
- ✅ Theme-aware

### Keyboard Support
- **Tab/Shift+Tab:** Navigate within modal
- **Escape:** Close modal (if enabled)
- **Enter:** Activates focused button

---

## KeyboardShortcuts

Displays keyboard shortcuts help panel with floating trigger button.

### Import
```jsx
import KeyboardShortcuts, { ShortcutHint } from './components/KeyboardShortcuts';
```

### Usage
```jsx
// Add once to MainLayout (already integrated)
<KeyboardShortcuts />

// Optional: Add inline hints next to buttons
<button onClick={handleSave}>
  Save Settings
  <ShortcutHint keys={['Cmd', 'S']} />
</button>
```

### Features
- ✅ Floating button (bottom right)
- ✅ Press `?` or `/` to open
- ✅ 4 categories of shortcuts
- ✅ Apple-style kbd elements
- ✅ Mobile responsive
- ✅ Theme-aware
- ✅ 44×44pt touch target

### Documented Shortcuts

**Navigation:**
- Tab - Move forward
- Shift+Tab - Move backward
- Enter - Activate buttons/links
- Space - Toggle checkboxes
- Escape - Close modals/dialogs

**General:**
- ? - Show shortcuts help
- / - Show shortcuts help (alternate)
- Cmd+K - Quick search
- Cmd+, - Open settings

**Dashboard:**
- 1, 2, 3 - Switch cameras
- R - Record toggle
- F - Fullscreen
- M - Mute/unmute

**Accessibility:**
- Cmd++ - Zoom in
- Cmd+- - Zoom out
- Cmd+0 - Reset zoom
- Ctrl+U - View source

---

## Theme System

All components use CSS variables for theme compatibility.

### Color Variables
```css
/* Text */
--text-primary      /* Main text */
--text-secondary    /* Supporting text */
--text-tertiary     /* Disabled/subtle text */
--text-link         /* Links and accents */

/* Backgrounds */
--bg-main           /* Page background */
--bg-panel          /* Card/panel background */
--bg-input          /* Input fields */
--bg-hover          /* Hover state */
--bg-active         /* Active state */

/* Borders */
--border-panel      /* Panel borders */
--border-input      /* Input borders */

/* Theme Colors */
--theme-primary     /* Primary action color */
--theme-accent      /* Secondary accent */
--color-success     /* Success state */
--color-warning     /* Warning state */
--color-error       /* Error state */
```

### Spacing (8pt Grid)
```css
--spacing-xs: 4px    /* 0.5 units - Tight */
--spacing-sm: 8px    /* 1 unit - Small */
--spacing-md: 16px   /* 2 units - Standard */
--spacing-lg: 24px   /* 3 units - Large */
--spacing-xl: 32px   /* 4 units - Extra large */
--spacing-2xl: 48px  /* 6 units - Sections */
```

### Border Radius
```css
--radius-sm: 8px     /* Small elements */
--radius-md: 12px    /* Cards, buttons */
--radius-lg: 16px    /* Modals, panels */
--radius-pill: 999px /* Fully rounded */
```

### Shadows (Elevation)
```css
--shadow-sm   /* Subtle elevation */
--shadow-md   /* Standard elevation */
--shadow-lg   /* Higher elevation */
--shadow-xl   /* Maximum elevation */
```

### Animation
```css
--anim-fast: 0.15s    /* Quick transitions */
--anim-normal: 0.25s  /* Standard transitions */
--anim-slow: 0.35s    /* Deliberate transitions */
--anim-ease: ease-out /* Easing function */
```

### Touch Targets
```css
--touch-target-min: 44px  /* Apple HIG minimum */
```

### Focus Indicators
```css
--focus-glow: rgba(theme-primary, 0.3)  /* Focus ring glow */
```

---

## Accessibility Features

### Reduced Motion
All animations respect user preferences:

```jsx
// System preference
@media (prefers-reduced-motion: reduce) {
  /* Disable animations */
}

// User toggle (System Settings → UI Accessibility)
html.reduce-motion * {
  /* Disable animations */
}
```

### Touch Targets
All interactive elements meet Apple HIG 44×44pt minimum:
```css
button, a, input {
  min-width: var(--touch-target-min, 44px);
  min-height: var(--touch-target-min, 44px);
}
```

### Focus Indicators
All focusable elements have visible focus:
```css
*:focus-visible {
  outline: 3px solid var(--theme-primary);
  outline-offset: 2px;
  box-shadow: 0 0 0 4px var(--focus-glow);
}
```

### ARIA Attributes
Components include proper ARIA:
- `role="dialog"` on modals
- `aria-modal="true"` on modals
- `aria-label` on icon buttons
- `aria-labelledby` linking titles
- `role="status"` on loading indicators

---

## Best Practices

### Using LoadingSkeleton
```jsx
// ✅ Good: Show skeleton while loading
{loading ? (
  <SkeletonCameraCard />
) : (
  <CameraCard data={cameraData} />
)}

// ❌ Bad: Don't show both skeleton and error
{loading && <SkeletonCard />}
{error && <ErrorMessage />}  // User sees both!

// ✅ Good: Show appropriate state
{loading ? <SkeletonCard /> : error ? <ErrorMessage /> : <Content />}
```

### Using Modal
```jsx
// ✅ Good: Single source of truth for open state
const [isOpen, setIsOpen] = useState(false);

<button onClick={() => setIsOpen(true)}>Open</button>
<Modal isOpen={isOpen} onClose={() => setIsOpen(false)}>
  <button onClick={() => setIsOpen(false)}>Close</button>
</Modal>

// ❌ Bad: Multiple state variables
const [modalOpen, setModalOpen] = useState(false);
const [showModal, setShowModal] = useState(false);  // Confusing!
```

### Using Spacing
```jsx
// ✅ Good: Use CSS variables
<div style={{ padding: 'var(--spacing-md, 16px)' }} />

// ❌ Bad: Hardcoded values
<div style={{ padding: '15px' }} />  // Not 8pt aligned!

// ✅ Good: Consistent spacing scale
<div style={{ 
  padding: 'var(--spacing-lg, 24px)',
  gap: 'var(--spacing-md, 16px)'
}} />
```

### Theming
```jsx
// ✅ Good: Use CSS variables for colors
<button style={{ 
  backgroundColor: 'var(--theme-primary)',
  color: '#ffffff'
}} />

// ❌ Bad: Hardcoded theme colors
<button style={{ 
  backgroundColor: '#007bff'  // Won't change with theme!
}} />
```

---

## Migration Guide

### Updating Existing Components

**Before:**
```jsx
const MyComponent = () => (
  <div style={{ 
    padding: '20px',
    backgroundColor: '#f0f0f0',
    borderRadius: '5px'
  }}>
    Content
  </div>
);
```

**After:**
```jsx
const MyComponent = () => (
  <div style={{ 
    padding: 'var(--spacing-lg, 24px)',           // 8pt grid
    backgroundColor: 'var(--bg-panel)',           // Theme-aware
    borderRadius: 'var(--radius-md, 12px)'        // Design token
  }}>
    Content
  </div>
);
```

### Adding Loading States

**Before:**
```jsx
const Dashboard = ({ cameras }) => (
  <div>
    {cameras.map(cam => <CameraCard key={cam.id} {...cam} />)}
  </div>
);
```

**After:**
```jsx
import { SkeletonCameraCard } from './components/LoadingSkeleton';

const Dashboard = ({ cameras, loading }) => (
  <div>
    {loading ? (
      Array.from({ length: 6 }).map((_, i) => (
        <SkeletonCameraCard key={i} />
      ))
    ) : (
      cameras.map(cam => <CameraCard key={cam.id} {...cam} />)
    )}
  </div>
);
```

### Replacing window.confirm()

**Before:**
```jsx
const handleDelete = () => {
  if (window.confirm('Delete this camera?')) {
    deleteCamera(id);
  }
};
```

**After:**
```jsx
import { ConfirmModal } from './components/Modal';

const [showConfirm, setShowConfirm] = useState(false);

const handleDelete = () => {
  setShowConfirm(true);
};

const confirmDelete = () => {
  deleteCamera(id);
  setShowConfirm(false);
};

// In render:
<ConfirmModal
  isOpen={showConfirm}
  onClose={() => setShowConfirm(false)}
  onConfirm={confirmDelete}
  title="Delete Camera?"
  message="This action cannot be undone."
  variant="danger"
/>
```

---

## Troubleshooting

### Modal doesn't close on Escape
Check that `closeOnEscape` prop is true (default):
```jsx
<Modal closeOnEscape={true} ... />
```

### Loading skeleton not animating
Check if reduce-motion is enabled. Skeletons will use pulse animation instead of shimmer when reduce-motion is active. This is by design.

### Theme colors not applying
Ensure CSS variables are defined in your theme file:
```css
:root {
  --theme-primary: #007bff;
  --text-primary: #333;
  /* ... etc */
}
```

### Keyboard shortcuts button not visible
Check that KeyboardShortcuts is rendered in MainLayout:
```jsx
// In MainLayout.jsx
<KeyboardShortcuts />
```

---

## Examples

See full examples in:
- `docs/PHASE2_IMPLEMENTATION_v3.5.3.md`
- `docs/testing/PHASE2_TESTING_GUIDE_v3.5.3.md`

For integration examples, search codebase for component imports.

---

**Last Updated:** October 16, 2025
**Version:** 3.5.3
