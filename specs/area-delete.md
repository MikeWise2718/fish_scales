# Area Selection and Multi-Delete Feature

## Overview

Add the ability to select multiple tubercles and connections using a rectangular area selection tool, then delete them in a single operation. This enables efficient cleanup of incorrectly detected features.

## Current State Analysis

### Existing Selection Model
- **Single selection only**: `selectedTubId` and `selectedEdgeIdx` in overlay.js
- Selection is mutually exclusive (tubercle OR edge, never both)
- Click-to-select with hit detection (1.5x radius for tubercles, 10px for edges)

### Existing Delete Mechanisms
- `DELETE_SELECTED`: Delete single selected item
- `DELETE_MULTI_TUB`: Click-to-delete mode (one at a time)
- `DELETE_MULTI_ITC`: Click-to-delete mode (one at a time)
- All deletions support undo/redo via `undoManager`

### Coordinate Systems
- All data stored in **image coordinates**
- Canvas handles zoom/pan for display
- Click conversion: `(clientX - rect.left) * (canvas.width / rect.width)`

---

## Feature Requirements

### Functional Requirements

1. **Area Selection Tool**
   - User draws a rectangle by click-drag on canvas
   - All tubercles with centers inside the rectangle are selected
   - All connections with BOTH endpoints inside the rectangle are selected
   - Visual feedback shows selection rectangle while dragging

2. **Multi-Selection Display**
   - Selected tubercles rendered with distinct style (e.g., magenta fill + stroke)
   - Selected connections rendered with distinct style
   - Selection count displayed in status area

3. **Batch Delete**
   - Single action deletes all selected items
   - Confirmation dialog shows count: "Delete N tubercles and M connections?"
   - Can be configured to skip confirmation (existing checkbox)

4. **Undo/Redo Support**
   - Single undo restores ALL deleted items
   - New operation type: `DELETE_MULTI` (batch delete)

5. **Selection Management**
   - Escape key clears multi-selection
   - Clicking outside selection clears it
   - Shift+click adds to existing selection (stretch goal)

### Non-Functional Requirements

- Responsive: Selection rectangle updates at 60fps during drag
- Performant: Handle 200+ tubercles without lag
- Consistent: Follow existing UI patterns and styling

---

## Technical Design

### 1. Data Model Changes

#### overlay.js - New Selection State
```javascript
// Existing (keep for single selection compatibility)
let selectedTubId = null;
let selectedEdgeIdx = null;

// New multi-selection state
let selectedTubIds = new Set();      // Set of selected tubercle IDs
let selectedEdgeIdxs = new Set();    // Set of selected edge indices

// Area selection state
let isAreaSelecting = false;
let areaSelectStart = null;          // {x, y} in image coords
let areaSelectEnd = null;            // {x, y} in image coords
```

#### New Functions in overlay.js
```javascript
// Multi-selection management
function selectMultipleTubercles(ids) { ... }
function selectMultipleEdges(idxs) { ... }
function addToSelection(tubIds, edgeIdxs) { ... }
function clearMultiSelection() { ... }
function getSelectedTubercles() { ... }  // Returns array
function getSelectedEdges() { ... }      // Returns array
function hasMultiSelection() { ... }     // Returns boolean

// Area selection
function startAreaSelect(x, y) { ... }
function updateAreaSelect(x, y) { ... }
function finishAreaSelect() { ... }      // Returns {tubIds, edgeIdxs}
function cancelAreaSelect() { ... }
function isInAreaSelectMode() { ... }
```

### 2. Editor Mode Addition

#### editor.js - New Edit Mode
```javascript
const EditMode = {
    // ... existing modes ...
    AREA_SELECT: 'area_select',  // New mode for area selection
};
```

#### New Functions in editor.js
```javascript
function enterAreaSelectMode() {
    currentMode = EditMode.AREA_SELECT;
    updateEditStatus('Click and drag to select an area. Release to select items.');
    setCursor('crosshair');
    highlightButton('areaSelectBtn');
}

function exitAreaSelectMode() {
    currentMode = EditMode.NONE;
    window.overlay?.cancelAreaSelect();
    updateEditStatus('');
    resetCursor();
    unhighlightButton('areaSelectBtn');
}

function deleteMultiSelected() {
    const selectedTubs = window.overlay?.getSelectedTubercles() || [];
    const selectedEdges = window.overlay?.getSelectedEdges() || [];

    if (selectedTubs.length === 0 && selectedEdges.length === 0) {
        return;
    }

    // Confirmation
    const msg = `Delete ${selectedTubs.length} tubercle(s) and ${selectedEdges.length} connection(s)?`;
    if (!skipConfirm && !confirm(msg)) {
        return;
    }

    // Perform batch delete with single undo operation
    batchDelete(selectedTubs, selectedEdges);
}

function batchDelete(tubs, edges) {
    // Collect all data for undo
    const deletedTubs = [];
    const deletedEdges = [];
    const orphanedEdges = [];  // Edges connected to deleted tubs

    // Find all edges that will be orphaned
    tubs.forEach(tub => {
        const connected = findEdgesConnectedTo(tub.id);
        connected.forEach(e => orphanedEdges.push(e));
    });

    // Combine explicitly selected edges with orphaned edges
    const allEdgesToDelete = [...edges, ...orphanedEdges];
    const uniqueEdges = deduplicateEdges(allEdgesToDelete);

    // Store for undo
    deletedTubs.push(...tubs);
    deletedEdges.push(...uniqueEdges);

    // Remove from data
    tubs.forEach(t => removeTubercle(t.id));
    uniqueEdges.forEach(e => removeEdge(e));

    // Push single undo operation
    window.undoManager?.push({
        type: OperationType.DELETE_MULTI,
        data: { tubs: deletedTubs, edges: deletedEdges },
        redoData: { tubIds: tubs.map(t => t.id), edgeKeys: uniqueEdges.map(e => `${e.id1}-${e.id2}`) }
    });

    // Clear selection and refresh
    window.overlay?.clearMultiSelection();
    refreshDisplays();
}
```

### 3. Mouse Event Handling

#### overlay.js - Enhanced Event Handlers
```javascript
function handleMouseDown(e) {
    if (window.editor?.getCurrentMode() === 'area_select') {
        const {x, y} = getImageCoords(e);
        startAreaSelect(x, y);
        e.preventDefault();
    }
}

function handleMouseMove(e) {
    if (isAreaSelecting) {
        const {x, y} = getImageCoords(e);
        updateAreaSelect(x, y);
        render();  // Redraw with selection rectangle
    }
}

function handleMouseUp(e) {
    if (isAreaSelecting) {
        const {x, y} = getImageCoords(e);
        updateAreaSelect(x, y);
        const selected = finishAreaSelect();

        // Select items within rectangle
        selectMultipleTubercles(selected.tubIds);
        selectMultipleEdges(selected.edgeIdxs);

        // Dispatch event for UI updates
        dispatchMultiSelectionEvent(selected);
    }
}
```

#### Hit Detection for Area Selection
```javascript
function finishAreaSelect() {
    const rect = normalizeRect(areaSelectStart, areaSelectEnd);

    // Find tubercles with centers inside rectangle
    const tubIds = tubercles
        .filter(t => isPointInRect(t.centroid_x, t.centroid_y, rect))
        .map(t => t.id);

    // Find edges with BOTH endpoints inside rectangle
    const edgeIdxs = edges
        .map((e, idx) => ({e, idx}))
        .filter(({e}) =>
            isPointInRect(e.x1, e.y1, rect) &&
            isPointInRect(e.x2, e.y2, rect))
        .map(({idx}) => idx);

    isAreaSelecting = false;
    areaSelectStart = null;
    areaSelectEnd = null;

    return { tubIds, edgeIdxs };
}

function normalizeRect(p1, p2) {
    return {
        x: Math.min(p1.x, p2.x),
        y: Math.min(p1.y, p2.y),
        width: Math.abs(p2.x - p1.x),
        height: Math.abs(p2.y - p1.y)
    };
}

function isPointInRect(px, py, rect) {
    return px >= rect.x && px <= rect.x + rect.width &&
           py >= rect.y && py <= rect.y + rect.height;
}
```

### 4. Rendering Updates

#### overlay.js - Selection Rendering
```javascript
function render() {
    // ... existing rendering ...

    // Draw multi-selected tubercles
    selectedTubIds.forEach(id => {
        const tub = tubercles.find(t => t.id === id);
        if (tub) {
            drawTubercle(tub, {
                fillColor: 'rgba(255, 0, 255, 0.3)',  // Semi-transparent magenta
                strokeColor: '#ff00ff',
                strokeWidth: 3
            });
        }
    });

    // Draw multi-selected edges
    selectedEdgeIdxs.forEach(idx => {
        const edge = edges[idx];
        if (edge) {
            drawEdge(edge, {
                color: '#ff00ff',
                width: 3
            });
        }
    });

    // Draw selection rectangle while dragging
    if (isAreaSelecting && areaSelectStart && areaSelectEnd) {
        drawSelectionRect(areaSelectStart, areaSelectEnd);
    }
}

function drawSelectionRect(start, end) {
    ctx.save();
    ctx.strokeStyle = '#00ffff';
    ctx.lineWidth = 1;
    ctx.setLineDash([5, 5]);
    ctx.fillStyle = 'rgba(0, 255, 255, 0.1)';

    const rect = normalizeRect(start, end);
    ctx.fillRect(rect.x, rect.y, rect.width, rect.height);
    ctx.strokeRect(rect.x, rect.y, rect.width, rect.height);

    ctx.restore();
}
```

### 5. Undo/Redo Support

#### undo.js - New Operation Type
```javascript
const OperationType = {
    // ... existing types ...
    DELETE_MULTI: 'delete_multi',  // Batch delete tubercles and edges
};
```

#### editor.js - Handle Undo/Redo
```javascript
function handleUndo(operation) {
    switch (operation.type) {
        // ... existing cases ...

        case OperationType.DELETE_MULTI: {
            // Restore all deleted tubercles
            operation.data.tubs.forEach(t => {
                tubercles.push({ ...t });
            });
            // Restore all deleted edges
            operation.data.edges.forEach(e => {
                edges.push({ ...e });
            });
            break;
        }
    }
    refreshDisplays();
}

function handleRedo(operation) {
    switch (operation.type) {
        // ... existing cases ...

        case OperationType.DELETE_MULTI: {
            // Re-delete all tubercles
            operation.redoData.tubIds.forEach(id => {
                const idx = tubercles.findIndex(t => t.id === id);
                if (idx >= 0) tubercles.splice(idx, 1);
            });
            // Re-delete all edges (filter by key)
            edges = edges.filter(e => {
                const key = `${e.id1}-${e.id2}`;
                return !operation.redoData.edgeKeys.includes(key);
            });
            break;
        }
    }
    refreshDisplays();
}
```

### 6. UI Changes

#### workspace.html - Edit Tab Additions
```html
<!-- Add to Modify Tubercle section or create new "Selection" section -->
<div class="edit-section">
    <h4>Area Selection</h4>
    <button id="areaSelectBtn" class="edit-btn" title="Draw rectangle to select multiple items">
        Area Select
    </button>
    <button id="deleteMultiSelectedBtn" class="edit-btn" disabled
            title="Delete all selected items">
        Delete Selected (0)
    </button>
    <span id="multiSelectStatus" class="hint">No items selected</span>
</div>
```

#### CSS Additions
```css
#areaSelectBtn.active {
    background-color: #ff00ff;
    color: white;
}

.multi-selected {
    /* Applied to table rows in data tab */
    background-color: rgba(255, 0, 255, 0.2);
}
```

### 7. Event System

#### New Custom Events
```javascript
// Dispatched when multi-selection changes
document.dispatchEvent(new CustomEvent('multiSelectionChanged', {
    detail: {
        tubercleCount: selectedTubIds.size,
        edgeCount: selectedEdgeIdxs.size,
        tubercleIds: Array.from(selectedTubIds),
        edgeIndices: Array.from(selectedEdgeIdxs)
    }
}));
```

#### Event Listeners in editor.js
```javascript
document.addEventListener('multiSelectionChanged', (e) => {
    const { tubercleCount, edgeCount } = e.detail;
    const total = tubercleCount + edgeCount;

    // Update button state
    const btn = document.getElementById('deleteMultiSelectedBtn');
    btn.disabled = total === 0;
    btn.textContent = `Delete Selected (${total})`;

    // Update status
    const status = document.getElementById('multiSelectStatus');
    if (total === 0) {
        status.textContent = 'No items selected';
    } else {
        status.textContent = `${tubercleCount} tubercle(s), ${edgeCount} connection(s) selected`;
    }
});
```

---

## Implementation Plan

### Phase 1: Multi-Selection Infrastructure
1. Add `selectedTubIds` and `selectedEdgeIdxs` to overlay.js
2. Implement selection management functions
3. Update rendering to show multi-selected items
4. Add `multiSelectionChanged` event

### Phase 2: Area Selection Tool
1. Add `AREA_SELECT` mode to editor.js
2. Implement mouse event handlers for drag selection
3. Implement hit detection for rectangle selection
4. Add visual feedback (selection rectangle)

### Phase 3: Batch Delete
1. Add `DELETE_MULTI` operation type to undo.js
2. Implement `batchDelete()` function
3. Handle cascading edge deletion for selected tubercles
4. Implement undo/redo for batch operations

### Phase 4: UI Integration
1. Add "Area Select" button to Edit tab
2. Add "Delete Selected (N)" button
3. Add selection status display
4. Wire up event listeners
5. Add keyboard shortcut (e.g., 'A' for area select mode)

### Phase 5: Polish
1. Sync multi-selection with data tables (highlight rows)
2. Add Shift+click to add to selection (optional)
3. Test edge cases (empty selection, all items selected)
4. Performance testing with large datasets

---

## Testing Checklist

- [ ] Area select with only tubercles inside
- [ ] Area select with only connections inside
- [ ] Area select with both tubercles and connections
- [ ] Area select that captures nothing (too small)
- [ ] Delete multi-selected items
- [ ] Undo batch delete restores all items
- [ ] Redo batch delete removes all items again
- [ ] Escape cancels area selection mode
- [ ] Escape clears multi-selection
- [ ] Selection persists when zooming/panning
- [ ] Confirm dialog shows correct counts
- [ ] Skip confirm option works
- [ ] Status updates correctly
- [ ] Works after image rotation
- [ ] Works with multiple annotation sets

---

## Future Enhancements (Out of Scope)

- Shift+click to add individual items to selection
- Ctrl+A to select all
- Lasso selection (freeform shape)
- Selection inversion
- Save/load selections
- Selection by criteria (e.g., "select all tubercles < 2 µm")
