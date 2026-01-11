# Edit Tab State Feedback Specification

## Overview

This document specifies improvements to visual feedback when the Edit tab is in different editing modes. Currently, users may not realize they've entered a mode because feedback is limited to a small status text at the bottom of the Edit tab and subtle cursor changes.

## Current State Analysis

### Edit Modes (from `editor.js`)

| Mode | Constant | Description | Current Cursor | Current Status Text |
|------|----------|-------------|----------------|---------------------|
| None | `NONE` | Default state, no mode active | default | (empty) |
| Add Tubercle | `ADD_TUB` | Click to place tubercle | crosshair | "Click on image to place tubercle" |
| Add Connection | `ADD_ITC` | Click two tubercles to connect | pointer | "Click first tubercle" / "Click second tubercle to create connection" |
| Add Chain | `ADD_CHAIN` | Add tubercles with auto-connect | crosshair | "Click to place or select first tubercle" / "Selected: #N" |
| Move | `MOVE` | Move selected tubercle | move | "Click destination to move selected tubercle" |
| Delete Tubercles | `DELETE_MULTI_TUB` | Click tubercles to delete | crosshair | "Click tubercles to delete them" |
| Delete Connections | `DELETE_MULTI_ITC` | Click connections to delete | crosshair | "Click connections to delete them" |
| Area Select | `AREA_SELECT` | Drag to select area | crosshair | "Click and drag to select an area. Release to select items." |

### Current Feedback Mechanisms

1. **Cursor Changes** (`updateCursor()` in editor.js:284-307)
   - Applied to `#imageContainer`
   - Only 4 distinct cursors: default, crosshair, pointer, move
   - Subtle - easy to miss

2. **Button Active State** (`updateModeUI()` in editor.js:197-279)
   - Adds `.active` class to mode buttons
   - Visible only in Edit tab

3. **Status Text** (`#editStatus` element)
   - Located at bottom of Edit tab (line 807 in workspace.html)
   - Not visible when user is focused on the image
   - Small, easy to overlook

4. **Chain Mode Hint** (`#editModeHint`)
   - Only shows for chain mode
   - Displays keyboard shortcuts

### Problems

1. **Status text not visible** when looking at the image (it's at the bottom of the right panel)
2. **Cursor changes are subtle** and may blend with browser defaults
3. **No prominent indicator** in the left panel near the image
4. **Easy to forget** which mode is active when switching tabs
5. **Delete modes look identical** to Add Tubercle mode (all use crosshair cursor)

## Proposed Solution

### 1. Mode Indicator Banner in Left Panel

Add a prominent banner at the top of the left panel (image area) that shows when any edit mode is active.

**Location:** Above the image container, below the toolbar

**Design:**
```
┌─────────────────────────────────────────────────────┐
│ [icon] ADD TUBERCLE MODE                    [X Exit]│
│ Click anywhere on the image to place a tubercle     │
└─────────────────────────────────────────────────────┘
```

**Properties:**
- Background color varies by mode type:
  - Add modes (ADD_TUB, ADD_ITC, ADD_CHAIN): Blue (#3b82f6)
  - Delete modes (DELETE_MULTI_TUB, DELETE_MULTI_ITC): Red (#ef4444)
  - Move mode: Amber (#f59e0b)
  - Area Select: Purple (#8b5cf6)
- Icon on the left indicating mode type
- Mode name in bold
- Description text below
- Exit button (X) on the right to cancel mode
- Escape key also exits

### 2. Custom Cursors

Replace generic cursors with custom SVG cursors that clearly indicate the mode:

| Mode | Custom Cursor Design |
|------|---------------------|
| ADD_TUB | Crosshair with + sign |
| ADD_ITC | Two circles with connecting line |
| ADD_CHAIN | Chain link icon |
| MOVE | Four-way arrow |
| DELETE_MULTI_TUB | Circle with X |
| DELETE_MULTI_ITC | Line with X |
| AREA_SELECT | Selection rectangle outline |

**Implementation:** CSS `cursor: url('...'), fallback`

### 3. Image Container Border Glow

Add a colored border/glow to the image container when in an edit mode:

```css
.image-container.edit-mode-add {
    box-shadow: inset 0 0 0 3px rgba(59, 130, 246, 0.5);
}
.image-container.edit-mode-delete {
    box-shadow: inset 0 0 0 3px rgba(239, 68, 68, 0.5);
}
.image-container.edit-mode-move {
    box-shadow: inset 0 0 0 3px rgba(245, 158, 11, 0.5);
}
.image-container.edit-mode-select {
    box-shadow: inset 0 0 0 3px rgba(139, 92, 246, 0.5);
}
```

### 4. Toolbar Mode Indicator

Add a small mode indicator badge to the toolbar that persists even when not on the Edit tab:

**Location:** After the filename display in the toolbar

**Design:**
```
[New Image] [filename.tif        ] [ADD TUBERCLE ▼]  [toggles...]
```

- Clicking opens a quick menu to change or exit mode
- Badge color matches mode type
- Dropdown arrow for quick access

## Implementation Plan

### Phase 1: Mode Banner (Priority: High)

1. **HTML Changes** (`workspace.html`)
   - Add `#editModeBanner` element above image container
   - Structure: icon, title, description, exit button

2. **CSS Changes** (`main.css`)
   - Styles for `.edit-mode-banner`
   - Color variants for each mode type
   - Animation for show/hide

3. **JavaScript Changes** (`editor.js`)
   - Update `setMode()` to show/hide banner
   - Update `updateModeUI()` to set banner content
   - Add exit button handler

### Phase 2: Custom Cursors (Priority: Medium)

1. **Asset Creation**
   - Create SVG cursor files in `static/cursors/`
   - 7 custom cursor designs

2. **CSS Changes** (`main.css`)
   - Replace generic cursor rules with custom cursor URLs

### Phase 3: Container Border (Priority: Low)

1. **CSS Changes** (`main.css`)
   - Add box-shadow styles for each mode category

2. **JavaScript Changes** (`editor.js`)
   - Add/remove mode category classes on container

### Phase 4: Toolbar Indicator (Priority: Low)

1. **HTML Changes** (`workspace.html`)
   - Add toolbar badge element

2. **CSS Changes** (`main.css`)
   - Badge styles

3. **JavaScript Changes** (`editor.js`)
   - Update toolbar badge with mode changes

## Mode Banner Content Reference

| Mode | Icon | Title | Description |
|------|------|-------|-------------|
| ADD_TUB | ⊕ | Add Tubercle | Click on the image to place a new tubercle |
| ADD_ITC | ⟷ | Add Connection | Click first tubercle, then click second to connect |
| ADD_CHAIN | ⛓ | Chain Mode | Click to add connected tubercles. Arrow keys to navigate. |
| MOVE | ✥ | Move Tubercle | Click on image to move the selected tubercle |
| DELETE_MULTI_TUB | ⊖ | Delete Tubercles | Click on tubercles to delete them |
| DELETE_MULTI_ITC | ✂ | Delete Connections | Click on connections to delete them |
| AREA_SELECT | ▢ | Area Select | Click and drag to select multiple items |

## CSS Color Scheme

```css
:root {
    --edit-mode-add: #3b82f6;      /* Blue */
    --edit-mode-add-bg: #eff6ff;
    --edit-mode-delete: #ef4444;   /* Red */
    --edit-mode-delete-bg: #fef2f2;
    --edit-mode-move: #f59e0b;     /* Amber */
    --edit-mode-move-bg: #fffbeb;
    --edit-mode-select: #8b5cf6;   /* Purple */
    --edit-mode-select-bg: #f5f3ff;
}
```

## Accessibility Considerations

1. **Color is not the only indicator** - text and icons also communicate mode
2. **Keyboard accessible** - Escape key exits any mode
3. **Screen reader support** - Banner has appropriate ARIA attributes
4. **Focus management** - Exit button is focusable

## Testing Checklist

- [ ] Banner appears when entering each mode
- [ ] Banner hides when exiting mode (button click or Escape)
- [ ] Cursor changes are visible on all backgrounds
- [ ] Border glow is visible but not distracting
- [ ] Mode indicator persists when switching tabs
- [ ] All feedback updates correctly on mode change
- [ ] Performance not affected by CSS changes

## Related Files

- `src/fish_scale_ui/static/js/editor.js` - Edit mode logic
- `src/fish_scale_ui/static/css/main.css` - Styles
- `src/fish_scale_ui/templates/workspace.html` - HTML structure
- `src/fish_scale_ui/static/js/overlay.js` - Canvas interactions

## References

- Current `EditMode` enum: `editor.js:8-17`
- Current `setMode()`: `editor.js:90-137`
- Current `updateModeUI()`: `editor.js:197-279`
- Current `updateCursor()`: `editor.js:284-307`
- Edit status element: `workspace.html:807`
- Edit tab structure: `workspace.html:606-820`
