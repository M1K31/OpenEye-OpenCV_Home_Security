# Universal Component CSS Variables Reference

This document defines all CSS variables required by the Universal Component Library (Button, TextField, Card, Switch).

## Required Variables for All Themes

Each theme MUST define these variables to ensure universal components work correctly:

### Core Colors

```css
/* Primary Interactive Color */
--accent-color: #007AFF;              /* Main interactive color (blue by default) */
--accent-color-alpha: rgba(0, 122, 255, 0.1); /* 10% opacity for focus rings */

/* Text Colors */
--text-primary: #000000;              /* Primary text */
--text-secondary: #6E6E73;            /* Secondary/muted text */
--text-tertiary: #8E8E93;             /* Tertiary/placeholder text */

/* Background Colors */
--background-primary: #FFFFFF;        /* Main background */
--background-secondary: #F5F5F7;      /* Secondary background */
--card-background: #FFFFFF;           /* Card background */
--input-background: #FFFFFF;          /* Input background */
--search-background: rgba(142, 142, 147, 0.12); /* Search input background */

/* Border Colors */
--border-color: #E5E5EA;              /* Default border */
--border-hover: #D1D1D6;              /* Border on hover */
--card-border: rgba(0, 0, 0, 0.08);   /* Card border */

/* State Colors */
--success-color: #34C759;             /* Success state */
--error-color: #FF3B30;               /* Error/destructive state */
--warning-color: #FF9500;             /* Warning state */
```

### Button Variables

```css
/* Primary Button */
--button-primary-bg: var(--accent-color, #007AFF);
--button-primary-text: #FFFFFF;
--button-primary-hover-bg: #0051D5;
--button-primary-shadow: 0 2px 8px rgba(0,0,0,0.1);
--button-primary-hover-shadow: 0 4px 12px rgba(0,0,0,0.15);

/* Secondary Button */
--button-secondary-bg: transparent;
--button-secondary-text: var(--accent-color, #007AFF);
--button-secondary-border: var(--accent-color, #007AFF);
--button-secondary-hover-bg: rgba(0, 122, 255, 0.08);

/* Tertiary Button */
--button-tertiary-bg: transparent;
--button-tertiary-text: var(--accent-color, #007AFF);
--button-tertiary-hover-bg: rgba(0, 122, 255, 0.08);

/* Destructive Button */
--button-destructive-bg: var(--error-color, #FF3B30);
--button-destructive-text: #FFFFFF;
--button-destructive-hover-bg: #D70015;
```

### Switch Variables

```css
/* Switch Track (OFF state) */
--switch-track-off: rgba(120, 120, 128, 0.32);
--switch-track-off-hover: rgba(120, 120, 128, 0.4);

/* Switch Track (ON state) */
--switch-track-on: var(--accent-color, #34C759);
--switch-track-on-hover: #30D158;

/* Switch Thumb */
--switch-thumb: #FFFFFF;
--switch-thumb-disabled: #F2F2F7;

/* Switch Disabled */
--switch-track-disabled: rgba(120, 120, 128, 0.16);
```

### Spacing (8pt Grid)

```css
--spacing-xs: 8px;
--spacing-sm: 16px;
--spacing-md: 24px;
--spacing-lg: 32px;
--spacing-xl: 48px;
```

### Border Radius

```css
--radius-sm: 8px;
--radius-md: 12px;
--radius-lg: 16px;
--radius-full: 9999px;
```

### Transitions

```css
--transition-fast: 150ms;
--transition-normal: 200ms;
--transition-slow: 300ms;
```

### Shadows

```css
--shadow-sm: 0 2px 8px rgba(0,0,0,0.08);
--shadow-md: 0 4px 16px rgba(0,0,0,0.12);
--shadow-lg: 0 8px 32px rgba(0,0,0,0.16);
```

## Dark Mode Adjustments

For dark themes, adjust these variables:

```css
@media (prefers-color-scheme: dark) {
  --text-primary: #FFFFFF;
  --text-secondary: #AEAEB2;
  --text-tertiary: #8E8E93;

  --background-primary: #000000;
  --background-secondary: #1C1C1E;
  --card-background: #1C1C1E;
  --input-background: #1C1C1E;

  --border-color: #38383A;
  --border-hover: #48484A;
  --card-border: rgba(255, 255, 255, 0.08);

  --switch-track-off: rgba(120, 120, 128, 0.38);
  --switch-thumb: #1C1C1E;

  --shadow-sm: 0 2px 8px rgba(0,0,0,0.3);
  --shadow-md: 0 4px 16px rgba(0,0,0,0.4);
  --shadow-lg: 0 8px 32px rgba(0,0,0,0.5);
}
```

## Theme Color Mapping

Each theme should adapt these variables to match its color palette:

### Example: Superman Theme
```css
html.sman-theme {
  --accent-color: #D32F2F;              /* Superman red */
  --text-primary: #FFD700;              /* Gold text */
  --background-primary: #0D47A1;        /* Blue background */
  --button-primary-bg: #D32F2F;
  --button-primary-text: #FFD700;
  --switch-track-on: #D32F2F;
  /* ... etc */
}
```

### Example: Batman Theme
```css
html.bman-theme {
  --accent-color: #EDC233;              /* Batman gold */
  --text-primary: #EDC233;
  --background-primary: #111111;        /* Dark background */
  --button-primary-bg: #EDC233;
  --button-primary-text: #111111;
  --switch-track-on: #EDC233;
  /* ... etc */
}
```

## Implementation Checklist

For each theme, ensure:
- [ ] All 9 themes have `html.{theme}-theme` selector
- [ ] All core colors defined
- [ ] All button variables defined (4 variants)
- [ ] All switch variables defined
- [ ] Spacing, radius, transitions, shadows inherited from :root
- [ ] Colors match theme's aesthetic (e.g., Superman = red/blue/gold)
- [ ] Contrast ratios meet WCAG AA (4.5:1 minimum)
- [ ] Dark themes use appropriate adjustments
