# Coordinate Grid Overlay Specification

## Overview

Add a coordinate grid overlay to the left-hand image panel, controlled by a checkbox like the other display options (Tubes, ITCs, Scale, etc.). The grid displays coordinate values in the same units as the Tubercle X and Y columns in the Data tab.

## Current State Analysis

### Display Toggle System (workspace.html:134-160)
Existing overlay toggle checkboxes under the image panel:
- `toggleNumbers` - Tube IDs
- `toggleTubes` - Tubes (checked by default)
- `toggleItcIds` - ITC IDs
- `toggleLinks` - ITCs (checked by default)
- `toggleScale` - Scale bar
- `showEllipses` - Ellipses

### Overlay Rendering (overlay.js)
- Toggle state stored in `toggleState` object (line 28-35)
- `bindToggleHandlers()` wires up checkbox change events (line 117-163)
- `render()` function conditionally draws overlays based on toggle state (line 255-376)
- `drawCalibrationScale()` (line 525-612) provides a model for drawing calibrated overlays

### Data Tab X/Y Display (data.js:221-224)
Currently displays tubercle coordinates as:
```javascript
<td>${tub.centroid_x.toFixed(1)}</td>
<td>${tub.centroid_y.toFixed(1)}</td>
```
- Values are in **pixels** (from `models.py:30` - `centroid: Tuple[float, float]  # (x, y) in pixels`)
- Table headers show just "X" and "Y" without units (workspace.html:959-960)

### Coordinate System
- Origin: Top-left of image = (0, 0)
- Units: Currently pixels in the UI, but scientific measurements should be in µm
- Calibration: Available via `window.calibration.getCurrentCalibration()` with `um_per_px` property

## Requirements

### 1. Coordinate Grid Overlay

Add a new checkbox "Grid" to the overlay toggles that displays a coordinate grid on the image canvas.

**Grid Characteristics:**
- Lines drawn at regular intervals across the image
- Coordinate labels at grid intersections or along edges
- Grid spacing adapts to image size and zoom level
- Uses calibration to show coordinates in µm (micrometers)
- Fallback: Shows pixel coordinates if no calibration is set

**Visual Design:**
- Grid lines: Semi-transparent (e.g., `rgba(255, 255, 255, 0.3)`)
- Labels: White text with dark outline for visibility (similar to existing ID labels)
- Grid should not obscure image content excessively
- Position labels along top and left edges, outside the main content area if possible

**Grid Spacing Algorithm:**
1. Calculate image dimensions in µm using calibration
2. Choose "nice" grid spacing from: [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000] µm
3. Target approximately 5-10 grid lines per axis
4. Adjust spacing based on current zoom level to prevent overcrowding

### 2. Data Tab Unit Labels

Update the Data tab table to show units for X and Y coordinates:
- Change header from "X" to "X (µm)"
- Change header from "Y" to "Y (µm)"
- Convert displayed values from pixels to µm using calibration
- If no calibration: Show "X (px)" / "Y (px)" and display pixel values

### 3. Coordinate Consistency

The coordinate grid overlay must display coordinates in the same unit system as the Data tab:
- **With calibration**: Both show µm coordinates
- **Without calibration**: Both show pixel coordinates
- Origin (0, 0) is always top-left of the image

## Implementation Plan

### Phase 1: Add Grid Toggle Checkbox

**File: `src/fish_scale_ui/templates/workspace.html`**

Add new checkbox after the existing toggles (around line 159):
```html
<label class="overlay-toggle" title="Show/hide coordinate grid">
    <input type="checkbox" id="toggleGrid">
    <span>Grid</span>
</label>
```

### Phase 2: Update Overlay Toggle State

**File: `src/fish_scale_ui/static/js/overlay.js`**

1. Add to `toggleState` object (line 28-35):
```javascript
let toggleState = {
    numbers: false,
    tubes: true,
    itcIds: false,
    links: true,
    scale: false,
    ellipses: false,
    grid: false  // NEW
};
```

2. Add to `updateToggleUI()` function:
```javascript
const gridEl = document.getElementById('toggleGrid');
if (gridEl) gridEl.checked = toggleState.grid;
```

3. Add to `bindToggleHandlers()` function:
```javascript
const gridEl = document.getElementById('toggleGrid');
if (gridEl) {
    gridEl.addEventListener('change', function() {
        toggleState.grid = this.checked;
        render();
    });
}
```

4. Add to `render()` function (after `drawCalibrationScale()`):
```javascript
if (toggleState.grid) {
    drawCoordinateGrid();
}
```

### Phase 3: Implement Grid Drawing Function

**File: `src/fish_scale_ui/static/js/overlay.js`**

Add new function `drawCoordinateGrid()`:

```javascript
function drawCoordinateGrid() {
    if (!canvas || !ctx) return;

    // Get calibration
    const calibration = window.calibration && window.calibration.getCurrentCalibration();
    const umPerPx = calibration ? calibration.um_per_px : null;
    const hasCalibration = umPerPx !== null;

    // Calculate image dimensions
    const imageWidth = canvas.width;
    const imageHeight = canvas.height;

    // Determine coordinate system (µm if calibrated, px otherwise)
    const widthUnits = hasCalibration ? imageWidth * umPerPx : imageWidth;
    const heightUnits = hasCalibration ? imageHeight * umPerPx : imageHeight;
    const unitLabel = hasCalibration ? 'µm' : 'px';

    // Choose nice grid spacing
    const niceValues = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000];
    const targetLines = 6; // Aim for ~6 lines per axis
    const targetSpacing = Math.max(widthUnits, heightUnits) / targetLines;

    let gridSpacing = niceValues[0];
    for (const val of niceValues) {
        if (val >= targetSpacing) {
            gridSpacing = val;
            break;
        }
    }

    // Convert spacing to pixels
    const spacingPx = hasCalibration ? gridSpacing / umPerPx : gridSpacing;

    // Draw settings
    const gridColor = 'rgba(255, 255, 255, 0.25)';
    const labelColor = '#ffffff';
    const labelShadow = '#000000';
    const fontSize = 11;
    const padding = 4;

    ctx.save();

    // Draw vertical grid lines and X-axis labels
    ctx.strokeStyle = gridColor;
    ctx.lineWidth = 1;
    ctx.font = `${fontSize}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';

    for (let x = 0; x <= imageWidth; x += spacingPx) {
        const coordValue = hasCalibration ? x * umPerPx : x;

        // Draw vertical line
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, imageHeight);
        ctx.stroke();

        // Draw X label at top
        if (x > 0 && x < imageWidth - 20) {
            const label = formatCoordLabel(coordValue);
            // Draw with shadow for visibility
            ctx.fillStyle = labelShadow;
            ctx.fillText(label, x + 1, padding + 1);
            ctx.fillStyle = labelColor;
            ctx.fillText(label, x, padding);
        }
    }

    // Draw horizontal grid lines and Y-axis labels
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';

    for (let y = 0; y <= imageHeight; y += spacingPx) {
        const coordValue = hasCalibration ? y * umPerPx : y;

        // Draw horizontal line
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(imageWidth, y);
        ctx.stroke();

        // Draw Y label at left
        if (y > 10 && y < imageHeight - 10) {
            const label = formatCoordLabel(coordValue);
            ctx.fillStyle = labelShadow;
            ctx.fillText(label, padding + 1, y + 1);
            ctx.fillStyle = labelColor;
            ctx.fillText(label, padding, y);
        }
    }

    // Draw origin label with unit
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    const originLabel = `0 ${unitLabel}`;
    ctx.fillStyle = labelShadow;
    ctx.fillText(originLabel, padding + 1, padding + 1);
    ctx.fillStyle = labelColor;
    ctx.fillText(originLabel, padding, padding);

    ctx.restore();
}

// Format coordinate label (remove unnecessary decimals)
function formatCoordLabel(value) {
    if (value === 0) return '0';
    if (value >= 100) return Math.round(value).toString();
    if (value >= 10) return value.toFixed(0);
    if (value >= 1) return value.toFixed(1);
    return value.toFixed(2);
}
```

### Phase 4: Update Data Tab Headers and Values

**File: `src/fish_scale_ui/templates/workspace.html`**

Change table headers (around line 959-960):
```html
<th data-col="x" id="tubColX">X (px)</th>
<th data-col="y" id="tubColY">Y (px)</th>
```

**File: `src/fish_scale_ui/static/js/data.js`**

1. Update `renderTubercleTable()` to convert coordinates:

```javascript
function renderTubercleTable() {
    const tbody = document.getElementById('tubTableBody');
    if (!tbody) return;

    tbody.innerHTML = '';
    updateColumnVisibility();
    updateCoordinateHeaders();  // NEW: Update headers based on calibration

    const colCount = 6 + (columnVisibility.source ? 1 : 0);
    const calibration = window.calibration?.getCurrentCalibration();
    const hasCalibration = calibration && calibration.um_per_px;

    if (tubercles.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = `<td colspan="${colCount}" class="empty-table">No tubercles detected</td>`;
        tbody.appendChild(row);
        return;
    }

    tubercles.forEach(tub => {
        const row = document.createElement('tr');
        row.dataset.tubId = tub.id;
        const boundaryStr = tub.is_boundary ? 'Y' : 'N';
        const sourceStr = tub.source || 'extracted';
        const sourceClass = columnVisibility.source ? '' : 'col-optional';
        const sourceVisible = columnVisibility.source ? 'visible' : '';

        // Convert coordinates to µm if calibrated
        let xDisplay, yDisplay;
        if (hasCalibration) {
            xDisplay = (tub.centroid_x * calibration.um_per_px).toFixed(1);
            yDisplay = (tub.centroid_y * calibration.um_per_px).toFixed(1);
        } else {
            xDisplay = tub.centroid_x.toFixed(1);
            yDisplay = tub.centroid_y.toFixed(1);
        }

        row.innerHTML = `
            <td>${tub.id}</td>
            <td>${xDisplay}</td>
            <td>${yDisplay}</td>
            <td>${tub.diameter_um.toFixed(2)}</td>
            <td>${(tub.circularity * 100).toFixed(1)}%</td>
            <td>${boundaryStr}</td>
            <td class="${sourceClass} ${sourceVisible}">${sourceStr}</td>
        `;
        row.addEventListener('click', () => {
            highlightTubercleRow(tub.id);
            if (window.overlay) {
                window.overlay.highlightTubercle(tub.id);
            }
        });
        tbody.appendChild(row);
    });
}
```

2. Add helper function to update column headers:

```javascript
function updateCoordinateHeaders() {
    const calibration = window.calibration?.getCurrentCalibration();
    const hasCalibration = calibration && calibration.um_per_px;
    const unit = hasCalibration ? 'µm' : 'px';

    const xHeader = document.getElementById('tubColX');
    const yHeader = document.getElementById('tubColY');

    if (xHeader) xHeader.textContent = `X (${unit})`;
    if (yHeader) yHeader.textContent = `Y (${unit})`;
}
```

3. Update calibration change listener to re-render table:

```javascript
document.addEventListener('calibrationChanged', () => {
    renderImageLevelData();
    renderSetCalibration();
    renderTubercleTable();  // NEW: Re-render to update coordinates
});
```

## Settings Integration (Optional Enhancement)

Add grid customization options to the Settings tab:

- Grid line color/opacity
- Grid label size
- Grid position preference (labels inside vs outside)
- Minimum grid spacing

## Testing Checklist

1. **Toggle functionality**
   - [ ] Grid checkbox appears in overlay toggles
   - [ ] Checking/unchecking shows/hides grid
   - [ ] Grid state persists correctly with other toggles

2. **Grid rendering**
   - [ ] Grid lines draw correctly across image
   - [ ] Grid spacing is reasonable (5-10 lines)
   - [ ] Labels are readable and positioned correctly
   - [ ] Grid works with zoom/pan

3. **Coordinate consistency**
   - [ ] With calibration: Grid shows µm, Data tab shows µm
   - [ ] Without calibration: Grid shows px, Data tab shows px
   - [ ] Clicking a tubercle in overlay → Data tab coordinates match grid position

4. **Edge cases**
   - [ ] Very large images (>5000px)
   - [ ] Very small images (<500px)
   - [ ] Extreme calibration values
   - [ ] No calibration set

## Files to Modify

| File | Changes |
|------|---------|
| `src/fish_scale_ui/templates/workspace.html` | Add Grid checkbox, update table headers with IDs |
| `src/fish_scale_ui/static/js/overlay.js` | Add toggle state, handler, and `drawCoordinateGrid()` function |
| `src/fish_scale_ui/static/js/data.js` | Convert X/Y to µm, update headers dynamically |

## Version Update

Per project conventions, increment patch version in:
- `pyproject.toml`
- `src/fish_scale_analysis/__init__.py`
- `src/fish_scale_ui/__init__.py`
- `src/fish_scale_mcp/__init__.py`
- `src/fish_scale_agent/__init__.py`
