# 8pt Grid Compliance Audit - Phase 2
**OpenEye v3.5.3 - Apple HIG Enhancement**

## Overview
This document tracks the conversion of hardcoded pixel values to 8pt grid system using CSS variables.

## 8pt Grid Reference

```css
--spacing-xs: 4px    /* 0.5 units - Micro spacing */
--spacing-sm: 8px    /* 1 unit - Small spacing */
--spacing-md: 16px   /* 2 units - Standard spacing */
--spacing-lg: 24px   /* 3 units - Large spacing */
--spacing-xl: 32px   /* 4 units - Extra large */
--spacing-2xl: 48px  /* 6 units - Section spacing */
```

## Conversion Table

| Old Value | New Variable | Use Case |
|-----------|-------------|----------|
| 2px | var(--spacing-xs, 4px) / 2 | Micro borders (avoid if possible) |
| 4px | var(--spacing-xs, 4px) | Tight spacing |
| 6px | Use 8px instead | ❌ Not 8pt aligned |
| 8px | var(--spacing-sm, 8px) | Small spacing |
| 10px | Use 8px or 12px | ❌ Not 8pt aligned |
| 12px | Use var(--spacing-sm, 8px) 1.5× | Acceptable for specific cases |
| 15px | Use 16px instead | ❌ Not 8pt aligned |
| 16px | var(--spacing-md, 16px) | Standard spacing |
| 20px | Use 16px or 24px | ❌ Not 8pt aligned |
| 24px | var(--spacing-lg, 24px) | Large spacing |
| 32px | var(--spacing-xl, 32px) | Extra large |
| 40px | Use 32px or 48px | ❌ Not 8pt aligned |
| 48px | var(--spacing-2xl, 48px) | Section spacing |
| 60px | Use 56px or 64px | ❌ Not 8pt aligned |

## Files Audited

### ✅ COMPLETED
- [x] `index.css` - Base styles (already updated in v3.5.3)
- [x] `themes.css` - Theme system (already updated in v3.5.3)
- [x] `HelpButton.css` - Help button (already updated in v3.5.3)
- [x] `LoadingSkeleton.css` - NEW component (8pt aligned)
- [x] `Modal.css` - NEW component (8pt aligned)
- [x] `KeyboardShortcuts.css` - NEW component (8pt aligned)

### 🔄 IN PROGRESS
- [ ] `global-theme.css` - Global theme overrides
- [ ] `MainLayout.css` - Main layout structure
- [ ] `Sidebar.css` - Sidebar navigation
- [ ] `LiveDashboard.css` - Dashboard sections
- [ ] `Section.css` - Section wrapper

### ⏸️ NOT STARTED
- [ ] Page-specific CSS files (RecordingsPage, FaceManagementPage, etc.)
- [ ] Component CSS files (CameraCard, EventTimeline, etc.)

## Non-Compliant Values Found

### global-theme.css
- Line 53: `padding: 20px` → Should be 16px or 24px
- Line 82: `padding: 10px 20px` → Should be 8px 16px or 8px 24px
- Line 175: `padding: 10px` → Should be 8px
- Line 213: `padding: 12px` → Acceptable (1.5 units)
- Line 242: `padding: 15px` → Should be 16px
- Line 344: `gap: 20px` → Should be 16px or 24px
- Line 350: `gap: 20px` → Should be 16px or 24px

### MainLayout.css
- Line 41: `gap: 15px` → Should be 16px
- Line 77: `gap: 20px` → Should be 16px or 24px
- Line 83: `padding: 6px 12px` → Should be 8px or 4px 8px
- Line 143: `padding: 10px 16px` → Should be 8px 16px

### Sidebar.css
- Line 186: `gap: 2px` → Should be 4px (minimum)
- Line 229: `padding: 10px 12px` → Should be 8px
- Line 284: `padding: 10px` → Should be 8px

### LiveDashboard.css
- Line 9: `gap: 20px` → Should be 16px or 24px
- Line 19: `padding: 12px 20px` → Should be 16px or 8px 16px
- Line 36: `gap: 10px` → Should be 8px
- Line 76: `gap: 20px` → Should be 16px or 24px
- Line 111: `gap: 20px` → Should be 16px or 24px
- Line 151: `padding: 4px 12px` → Acceptable
- Line 322: `padding: 2px 8px` → Should be 4px 8px
- Line 356: `padding: 40px 20px` → Should be 32px or 48px, 16px or 24px
- Line 373: `padding: 60px 20px` → Should be 64px or 56px, 16px or 24px

### Section.css
- Line 8: `padding: 20px` → Should be 16px or 24px
- Line 33: `padding: 60px 40px` → Should be 64px 32px or 48px
- Line 103: `padding: 40px 20px` → Should be 32px 16px or 48px 24px

## Impact Analysis

### Low Risk Changes (Visual rhythm improvement)
- `20px` → `24px` (spacing increases slightly)
- `10px` → `8px` (spacing decreases slightly)
- `15px` → `16px` (minimal change)

### Medium Risk Changes (May affect layouts)
- `gap: 20px` → `gap: 16px` (tighter grid layouts)
- `padding: 60px` → `padding: 64px` (larger sections)

### Theme Compatibility
All changes will use CSS variables, so:
- ✅ Colors remain unchanged
- ✅ Theme-specific backgrounds preserved
- ✅ Only spacing/sizing affected
- ✅ Visual hierarchy maintained

## Testing Checklist

After updates, verify:
- [ ] Live Dashboard camera grid spacing
- [ ] Sidebar navigation item spacing
- [ ] Section padding on all pages
- [ ] Button and input alignment
- [ ] Modal and panel spacing
- [ ] Mobile responsive layouts
- [ ] All theme variants (AquaSecurity, Sman, Bman, etc.)

## Implementation Order

1. **global-theme.css** - Affects all themes globally
2. **MainLayout.css** - Core layout structure
3. **Sidebar.css** - Navigation consistency
4. **LiveDashboard.css** - Most visible component
5. **Section.css** - Base section spacing
6. **Page-specific CSS** - Individual page polish

## Notes

- 12px is acceptable for specific cases (1.5 × 8px)
- 4px (--spacing-xs) is the minimum recommended spacing
- 2px should only be used for borders, not spacing
- When in doubt, round up to the next 8pt value
- Always include fallback values: `var(--spacing-md, 16px)`

---
**Last Updated:** October 15, 2025
**Version:** 3.5.3 Phase 2
**Author:** GitHub Copilot
