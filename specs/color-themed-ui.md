# Configurable UI Theme Colors

## Overview

The Fish Scale UI uses a dark blue-gray color scheme (`#1e293b`, `#1a1a2e`) for the image panel, status bar, and various containers. This specification describes how to make these colors configurable and adds support for light/dark theme switching.

## Current State

### Dark Blue-Gray Colors in Use

| Color | Usage | Files |
|-------|-------|-------|
| `#1e293b` | Image panel background, stats bar, pre/code blocks | main.css:248, 1697, 2912 |
| `#1a1a2e` | Chart canvas background | agent_extraction.js:611 |
| `#e2e8f0` | Light text on dark backgrounds | main.css (multiple) |
| `#94a3b8` | Muted text on dark backgrounds | main.css:1697 |
| `#64748b` | Secondary text, borders, scrollbar thumb | main.css:2935 |
| `#334155` | Scrollbar track | main.css:2930 |
| `#333344` | Chart grid lines | agent_extraction.js:625 |

### Locations Requiring Updates

**CSS (main.css):**
- Line ~248: `.image-panel { background-color: #1e293b; }`
- Line ~1697: `.stats-bar { background-color: #1e293b; color: #94a3b8; }`
- Line ~1697: `.stats-bar-value { color: #e2e8f0; }`
- Line ~2912: `.agent-collapsible-content pre { background-color: #1e293b; color: #e2e8f0; }`
- Line ~2930: Scrollbar styling (track: `#334155`, thumb: `#64748b`, hover: `#94a3b8`)

**JavaScript (agent_extraction.js):**
- Line ~611: `ctx.fillStyle = '#1a1a2e';` (chart background)
- Line ~625: `ctx.strokeStyle = '#333344';` (grid lines)
- Line ~636: `ctx.fillStyle = '#888';` (axis labels)

---

## Implementation Plan

### Phase 1: CSS Custom Properties

**Add to `:root` section in main.css (after existing variables):**

```css
/* Theme: Dark panel colors (configurable) */
--dark-bg: #1e293b;              /* Main dark background (image panel, stats bar, pre blocks) */
--dark-bg-alt: #1a1a2e;          /* Darker variant (chart canvas) */
--dark-text: #e2e8f0;            /* Primary text on dark backgrounds */
--dark-text-muted: #94a3b8;      /* Muted/secondary text on dark */
--dark-text-dim: #64748b;        /* Dim text, borders */
--dark-border: #334155;          /* Borders, scrollbar track */
--dark-grid: #333344;            /* Chart grid lines */

/* Theme: Light panel colors (for light theme option) */
--light-bg: #f1f5f9;             /* Main light background */
--light-bg-alt: #e2e8f0;         /* Lighter variant */
--light-text: #1e293b;           /* Primary text on light backgrounds */
--light-text-muted: #475569;     /* Muted text on light */
--light-text-dim: #64748b;       /* Dim text */
--light-border: #cbd5e1;         /* Borders */
--light-grid: #94a3b8;           /* Chart grid lines */

/* Active theme (switched by JS based on user preference) */
--panel-bg-dark: var(--dark-bg);
--panel-bg-dark-alt: var(--dark-bg-alt);
--panel-text: var(--dark-text);
--panel-text-muted: var(--dark-text-muted);
--panel-text-dim: var(--dark-text-dim);
--panel-border: var(--dark-border);
--panel-grid: var(--dark-grid);
```

### Phase 2: Update CSS Selectors

Replace hardcoded colors with CSS variables:

```css
/* Image panel */
.image-panel {
    background-color: var(--panel-bg-dark);
}

/* Stats bar */
.stats-bar {
    background-color: var(--panel-bg-dark);
    border-top: 1px solid var(--panel-border);
    color: var(--panel-text-muted);
}

.stats-bar-value {
    color: var(--panel-text);
}

/* Agent collapsible content */
.agent-collapsible-content pre {
    background-color: var(--panel-bg-dark);
    color: var(--panel-text);
    border-radius: 0.25rem;
}

/* Scrollbars on dark backgrounds */
.agent-collapsible-content pre::-webkit-scrollbar-track {
    background: var(--panel-border);
}

.agent-collapsible-content pre::-webkit-scrollbar-thumb {
    background: var(--panel-text-dim);
}

.agent-collapsible-content pre::-webkit-scrollbar-thumb:hover {
    background: var(--panel-text-muted);
}
```

### Phase 3: JavaScript Canvas Colors

**Update agent_extraction.js chart drawing:**

```javascript
function getThemeColors() {
    const styles = getComputedStyle(document.documentElement);
    return {
        background: styles.getPropertyValue('--panel-bg-dark-alt').trim() || '#1a1a2e',
        grid: styles.getPropertyValue('--panel-grid').trim() || '#333344',
        text: styles.getPropertyValue('--panel-text-dim').trim() || '#64748b',
        textMuted: styles.getPropertyValue('--panel-text-muted').trim() || '#94a3b8',
    };
}

// In drawProgressChart():
const themeColors = getThemeColors();
ctx.fillStyle = themeColors.background;  // was '#1a1a2e'
ctx.fillRect(0, 0, width, height);

// Grid lines
ctx.strokeStyle = themeColors.grid;  // was '#333344'

// Axis labels
ctx.fillStyle = themeColors.text;  // was '#888'
```

### Phase 4: Settings UI

**Add to workspace.html after "Overlay Display" settings group:**

```html
<!-- Theme Colors Settings -->
<div class="settings-group collapsed" id="settingsThemeColors">
    <div class="settings-group-header">
        <h3>Theme Colors</h3>
        <span class="settings-group-toggle">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
        </span>
    </div>
    <div class="settings-group-content">
        <p class="setting-hint">Customize the image panel and container colors.</p>

        <!-- Theme Mode Selector -->
        <div class="setting-item">
            <label class="setting-label-text">Panel Theme</label>
            <div class="radio-group">
                <label class="radio-label">
                    <input type="radio" name="panelTheme" id="panelThemeDark" value="dark" checked>
                    <span>Dark</span>
                </label>
                <label class="radio-label">
                    <input type="radio" name="panelTheme" id="panelThemeLight" value="light">
                    <span>Light</span>
                </label>
                <label class="radio-label">
                    <input type="radio" name="panelTheme" id="panelThemeCustom" value="custom">
                    <span>Custom</span>
                </label>
            </div>
        </div>

        <!-- Custom Colors (shown only when Custom is selected) -->
        <div id="customThemeColors" style="display: none;">
            <div class="setting-item">
                <label class="setting-label-text">Panel Background</label>
                <p class="setting-hint">Image panel, stats bar, code blocks</p>
                <div class="color-input-group">
                    <input type="color" id="panelBgColorPicker" value="#1e293b">
                    <input type="text" id="panelBgColorText" value="#1e293b" class="color-text-input">
                </div>
            </div>

            <div class="setting-item">
                <label class="setting-label-text">Chart Background</label>
                <p class="setting-hint">Optimization progress chart</p>
                <div class="color-input-group">
                    <input type="color" id="panelBgAltColorPicker" value="#1a1a2e">
                    <input type="text" id="panelBgAltColorText" value="#1a1a2e" class="color-text-input">
                </div>
            </div>

            <div class="setting-item">
                <label class="setting-label-text">Primary Text</label>
                <p class="setting-hint">Main text on panel backgrounds</p>
                <div class="color-input-group">
                    <input type="color" id="panelTextColorPicker" value="#e2e8f0">
                    <input type="text" id="panelTextColorText" value="#e2e8f0" class="color-text-input">
                </div>
            </div>

            <div class="setting-item">
                <label class="setting-label-text">Muted Text</label>
                <p class="setting-hint">Labels, hints on panel backgrounds</p>
                <div class="color-input-group">
                    <input type="color" id="panelTextMutedColorPicker" value="#94a3b8">
                    <input type="text" id="panelTextMutedColorText" value="#94a3b8" class="color-text-input">
                </div>
            </div>

            <div class="setting-item">
                <label class="setting-label-text">Borders</label>
                <p class="setting-hint">Borders, scrollbar tracks</p>
                <div class="color-input-group">
                    <input type="color" id="panelBorderColorPicker" value="#334155">
                    <input type="text" id="panelBorderColorText" value="#334155" class="color-text-input">
                </div>
            </div>

            <div class="setting-item">
                <label class="setting-label-text">Grid Lines</label>
                <p class="setting-hint">Chart grid lines</p>
                <div class="color-input-group">
                    <input type="color" id="panelGridColorPicker" value="#333344">
                    <input type="text" id="panelGridColorText" value="#333344" class="color-text-input">
                </div>
            </div>
        </div>

        <!-- Reset Button -->
        <div class="setting-item">
            <button id="resetThemeColorsBtn" class="btn btn-secondary btn-sm">
                Reset Theme Colors
            </button>
        </div>
    </div>
</div>
```

### Phase 5: Settings Logic

**Add to settings.js defaults:**

```javascript
const defaults = {
    // ... existing defaults ...

    // Theme settings
    panelTheme: 'dark',  // 'dark', 'light', or 'custom'

    // Custom theme colors (used when panelTheme === 'custom')
    customPanelBg: '#1e293b',
    customPanelBgAlt: '#1a1a2e',
    customPanelText: '#e2e8f0',
    customPanelTextMuted: '#94a3b8',
    customPanelTextDim: '#64748b',
    customPanelBorder: '#334155',
    customPanelGrid: '#333344',
};
```

**Add theme color functions:**

```javascript
// Predefined themes
const THEMES = {
    dark: {
        panelBg: '#1e293b',
        panelBgAlt: '#1a1a2e',
        panelText: '#e2e8f0',
        panelTextMuted: '#94a3b8',
        panelTextDim: '#64748b',
        panelBorder: '#334155',
        panelGrid: '#333344',
    },
    light: {
        panelBg: '#f1f5f9',
        panelBgAlt: '#e2e8f0',
        panelText: '#1e293b',
        panelTextMuted: '#475569',
        panelTextDim: '#64748b',
        panelBorder: '#cbd5e1',
        panelGrid: '#94a3b8',
    },
};

function applyThemeColors() {
    const root = document.documentElement;
    let colors;

    if (current.panelTheme === 'custom') {
        colors = {
            panelBg: current.customPanelBg,
            panelBgAlt: current.customPanelBgAlt,
            panelText: current.customPanelText,
            panelTextMuted: current.customPanelTextMuted,
            panelTextDim: current.customPanelTextDim,
            panelBorder: current.customPanelBorder,
            panelGrid: current.customPanelGrid,
        };
    } else {
        colors = THEMES[current.panelTheme] || THEMES.dark;
    }

    root.style.setProperty('--panel-bg-dark', colors.panelBg);
    root.style.setProperty('--panel-bg-dark-alt', colors.panelBgAlt);
    root.style.setProperty('--panel-text', colors.panelText);
    root.style.setProperty('--panel-text-muted', colors.panelTextMuted);
    root.style.setProperty('--panel-text-dim', colors.panelTextDim);
    root.style.setProperty('--panel-border', colors.panelBorder);
    root.style.setProperty('--panel-grid', colors.panelGrid);

    // Dispatch event so canvas-based components can redraw
    window.dispatchEvent(new CustomEvent('themeColorsChanged'));
}

function bindThemeColorUI() {
    // Theme mode radio buttons
    const themeRadios = document.querySelectorAll('input[name="panelTheme"]');
    themeRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            set('panelTheme', this.value);
            toggleCustomColorsVisibility(this.value === 'custom');
            applyThemeColors();
        });
    });

    // Custom color pickers
    const colorSettings = [
        { picker: 'panelBgColorPicker', text: 'panelBgColorText', key: 'customPanelBg' },
        { picker: 'panelBgAltColorPicker', text: 'panelBgAltColorText', key: 'customPanelBgAlt' },
        { picker: 'panelTextColorPicker', text: 'panelTextColorText', key: 'customPanelText' },
        { picker: 'panelTextMutedColorPicker', text: 'panelTextMutedColorText', key: 'customPanelTextMuted' },
        { picker: 'panelBorderColorPicker', text: 'panelBorderColorText', key: 'customPanelBorder' },
        { picker: 'panelGridColorPicker', text: 'panelGridColorText', key: 'customPanelGrid' },
    ];

    colorSettings.forEach(({ picker, text, key }) => {
        bindColorPicker(picker, text, key, applyThemeColors);
    });

    // Reset button
    const resetBtn = document.getElementById('resetThemeColorsBtn');
    if (resetBtn) {
        resetBtn.addEventListener('click', resetThemeColors);
    }
}

function toggleCustomColorsVisibility(show) {
    const customSection = document.getElementById('customThemeColors');
    if (customSection) {
        customSection.style.display = show ? 'block' : 'none';
    }
}

function resetThemeColors() {
    set('panelTheme', 'dark');
    set('customPanelBg', defaults.customPanelBg);
    set('customPanelBgAlt', defaults.customPanelBgAlt);
    set('customPanelText', defaults.customPanelText);
    set('customPanelTextMuted', defaults.customPanelTextMuted);
    set('customPanelTextDim', defaults.customPanelTextDim);
    set('customPanelBorder', defaults.customPanelBorder);
    set('customPanelGrid', defaults.customPanelGrid);

    applyThemeColorsToUI();
    applyThemeColors();

    if (window.app && window.app.showToast) {
        window.app.showToast('Theme colors reset to defaults', 'success');
    }
}

function applyThemeColorsToUI() {
    // Set radio button
    const themeRadio = document.getElementById(`panelTheme${capitalize(current.panelTheme)}`);
    if (themeRadio) themeRadio.checked = true;

    // Toggle custom colors visibility
    toggleCustomColorsVisibility(current.panelTheme === 'custom');

    // Set custom color pickers
    setColorPickerValue('panelBgColorPicker', 'panelBgColorText', current.customPanelBg);
    setColorPickerValue('panelBgAltColorPicker', 'panelBgAltColorText', current.customPanelBgAlt);
    setColorPickerValue('panelTextColorPicker', 'panelTextColorText', current.customPanelText);
    setColorPickerValue('panelTextMutedColorPicker', 'panelTextMutedColorText', current.customPanelTextMuted);
    setColorPickerValue('panelBorderColorPicker', 'panelBorderColorText', current.customPanelBorder);
    setColorPickerValue('panelGridColorPicker', 'panelGridColorText', current.customPanelGrid);
}

function setColorPickerValue(pickerId, textId, value) {
    const picker = document.getElementById(pickerId);
    const text = document.getElementById(textId);
    if (picker) picker.value = value;
    if (text) text.value = value;
}

function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}
```

**Update init() and applyToUI():**

```javascript
function init() {
    load();
    bindUI();
    bindThemeColorUI();  // Add this
    applyToUI();
    applyThemeColors();  // Add this - apply saved theme on load
    // ... rest of init
}

function applyToUI() {
    // ... existing code ...
    applyThemeColorsToUI();  // Add this
}
```

**Update agent_extraction.js to listen for theme changes:**

```javascript
// At module initialization
window.addEventListener('themeColorsChanged', () => {
    // Redraw chart with new colors
    if (typeof drawProgressChart === 'function') {
        drawProgressChart();
    }
});
```

---

## Summary of Changes

| File | Additions | Modifications |
|------|-----------|---------------|
| `main.css` | ~20 lines (CSS variables) | ~15 lines (replace hardcoded colors) |
| `settings.js` | ~120 lines (theme functions) | ~10 lines (init/applyToUI) |
| `agent_extraction.js` | ~15 lines (getThemeColors, event listener) | ~5 lines (use theme colors) |
| `workspace.html` | ~80 lines (Theme Colors settings group) | 0 |

**Total: ~250 lines of new/modified code**

---

## Theme Presets

### Dark Theme (Default)
| Property | Value | Preview |
|----------|-------|---------|
| Panel Background | `#1e293b` | Dark blue-gray |
| Chart Background | `#1a1a2e` | Darker blue |
| Primary Text | `#e2e8f0` | Light gray |
| Muted Text | `#94a3b8` | Medium gray |
| Dim Text | `#64748b` | Darker gray |
| Borders | `#334155` | Dark border |
| Grid Lines | `#333344` | Subtle grid |

### Light Theme
| Property | Value | Preview |
|----------|-------|---------|
| Panel Background | `#f1f5f9` | Light gray |
| Chart Background | `#e2e8f0` | Lighter gray |
| Primary Text | `#1e293b` | Dark text |
| Muted Text | `#475569` | Medium dark |
| Dim Text | `#64748b` | Gray |
| Borders | `#cbd5e1` | Light border |
| Grid Lines | `#94a3b8` | Visible grid |

---

## Future Considerations

1. **System Theme Detection**: Could add `prefers-color-scheme` media query support
2. **Additional Themes**: Could add more preset themes (high contrast, solarized, etc.)
3. **Export/Import**: Allow users to export custom themes as JSON
4. **Per-Image Themes**: Different themes for different image types (though probably overkill)
