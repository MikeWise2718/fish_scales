# Edit Tab: Regenerate Connections Feature

## Problem Statement

After manually adding, moving, or deleting tubercles in the Edit tab, users must switch to the Extraction tab to click "Extract Connections Only" to regenerate connections. This workflow is disruptive and unintuitive.

Users should be able to regenerate connections directly from the Edit tab where they are doing their editing work.

## Current State

### Connection Regeneration Location
- **Currently**: Only available in Extraction tab via "Extract Connections Only" button
- **Graph type setting**: Configure tab's `neighbor_graph` dropdown (delaunay/gabriel/rng)

### Edit Tab Connection Operations
- Add ITC (manual click-to-click)
- Add Chain Mode (auto-connect while adding tubercles)
- Delete Selected ITC
- Delete Multiple ITC

### Relevant Endpoints
| Endpoint | Purpose |
|----------|---------|
| `POST /api/regenerate-connections` | Full regeneration with parameters |
| `POST /api/connections/clear` | Clear all connections |
| `POST /api/auto-connect` | MCP-style auto-connect |

## Proposed Solution

### New UI Element

Add a **"Regenerate Connections"** button to the Edit tab, in the "Modify Connection" section:

```
┌─────────────────────────────────────────┐
│ Modify Connection                       │
├─────────────────────────────────────────┤
│ [Delete Selected]  [Delete Multiple]    │
│                                         │
│ ─────────────────────────────────────── │
│                                         │
│ [🔄 Regenerate Connections ▼]           │
│    └─ Dropdown: Delaunay/Gabriel/RNG    │
└─────────────────────────────────────────┘
```

### UI Options

**Option A: Button with inline dropdown**
- Single row with button + graph type selector
- Uses current Configure tab value as default
- Compact, stays in Edit context

**Option B: Simple button using Configure setting**
- Just a button, always uses `neighbor_graph` from Configure tab
- Simplest implementation
- Tooltip shows current graph type

**Option C: Button with confirmation dialog**
- Button opens modal showing:
  - Current tubercle count
  - Current connection count (to be cleared)
  - Graph type selector
  - "Regenerate" / "Cancel" buttons

### Recommended: Option A

A button with an adjacent dropdown provides:
- Quick access without leaving Edit tab
- Visibility of which algorithm will be used
- No extra clicks for power users
- Default syncs from Configure tab

### Behavior

1. **Click "Regenerate Connections"**:
   - Clear all existing connections
   - Regenerate using selected graph type
   - Use current `cull_long_edges` and `cull_factor` from Configure tab
   - Update overlay immediately
   - Record undo state (connections before regeneration)
   - Log event to session log

2. **Graph type dropdown**:
   - Options: Delaunay, Gabriel, RNG
   - Default: Current value from Configure tab's `neighbor_graph`
   - Changing dropdown does NOT auto-regenerate (requires button click)
   - Optionally: sync back to Configure tab when changed

3. **Undo support**:
   - Regeneration should be undoable
   - Store previous edges array before regeneration

### Implementation Files

| File | Changes |
|------|---------|
| `templates/workspace.html` | Add button + dropdown to Edit tab (lines ~676-695) |
| `static/js/editor.js` | Add `regenerateConnections()` function |
| `static/js/configure.js` | Export/share `neighbor_graph` value |
| `static/css/main.css` | Style for inline button+dropdown (if needed) |

### API Usage

Reuse existing endpoint - no backend changes needed:

```javascript
// editor.js
async function regenerateConnections() {
    const graphType = document.getElementById('editGraphType').value;
    const params = window.configureModule?.getParams() || {};

    const response = await fetch('/api/regenerate-connections', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            tubercles: getCurrentTubercles(),
            graph_type: graphType,
            cull_long_edges: params.cull_long_edges ?? true,
            cull_factor: params.cull_factor ?? 1.8
        })
    });

    // Update UI with new edges
    // Record undo state
    // Log event
}
```

## Edge Cases

1. **No tubercles**: Disable button, show tooltip "No tubercles to connect"
2. **Single tubercle**: Allow click but result will be 0 connections
3. **Dirty state**: Regeneration marks data as dirty (unsaved changes)
4. **During other operations**: Disable during Add TUB/ITC modes

## Testing

1. Add tubercles manually, click Regenerate - connections appear
2. Change graph type, click Regenerate - connection count changes appropriately
3. Undo after regeneration - previous connections restored
4. Switch to Data tab - ITC table shows updated connections
5. Save annotations - new connections persisted correctly

## Future Considerations

- **Keyboard shortcut**: e.g., `Ctrl+Shift+C` for quick regeneration
- **Auto-regenerate toggle**: Option to auto-regenerate after each tubercle edit
- **Preview mode**: Show proposed connections before committing

## Summary

Add a "Regenerate Connections" button with graph type dropdown to the Edit tab's "Modify Connection" section. This allows users to clear and recalculate connections without leaving their editing workflow. Implementation reuses existing `/api/regenerate-connections` endpoint with no backend changes required.
