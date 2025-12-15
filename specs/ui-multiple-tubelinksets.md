# Multiple Tubercle/Link Sets Feature Specification

## Overview

This feature enables users to save, manage, and rapidly switch between multiple sets of tubercle and link annotations for a single image. This supports comparative analysis workflows where researchers need to compare different detection parameters, manual annotations, or annotation versions.

## Use Cases

1. **Parameter Comparison**: Run extraction with different parameters, save each result as a separate set, quickly compare
2. **Annotation Versions**: Save work-in-progress, create alternative annotations, compare approaches
3. **Before/After Editing**: Save original extraction as "Base", make manual edits in a new set, compare
4. **Multi-Annotator Review**: Different researchers annotate the same image, compare results

## User Interface

### Set Selector Bar

A new horizontal bar added below the overlay toggles, containing:

```
┌─────────────────────────────────────────────────────────────────┐
│ [Base*] [Manual Edit] [High Contrast] [+]        [Save] [⚙]   │
└─────────────────────────────────────────────────────────────────┘
```

**Components:**
- **Set Buttons**: Toggle buttons for each saved set (active set highlighted)
- **Asterisk (*)**: Indicates unsaved changes in that set
- **[+] Button**: Create new set
- **[Save] Button**: Save current set (enabled when dirty)
- **[⚙] Button**: Set management dropdown (Rename, Delete, Duplicate)

### Button States

| State | Appearance |
|-------|------------|
| Active set | Primary color, bold text |
| Inactive set | Secondary/outline style |
| Unsaved changes | Asterisk (*) after name |
| Hover | Slight highlight |

### Set Management Menu (⚙)

Dropdown menu with options:
- **Rename Set...** - Opens rename dialog
- **Duplicate Set...** - Creates copy with new name
- **Delete Set** - Removes set (with confirmation)
- **Export Set...** - Export single set as SLO file
- **Import Set...** - Import SLO file as new set

### Create New Set Dialog

```
┌─────────────────────────────────────────┐
│ Create New Set                      [X] │
├─────────────────────────────────────────┤
│ Name: [________________________]        │
│                                         │
│ Initial Contents:                       │
│ ○ Empty (start fresh)                   │
│ ○ Copy from current set                 │
│ ○ Run extraction with current params    │
│                                         │
│              [Cancel] [Create]          │
└─────────────────────────────────────────┘
```

### Rename Set Dialog

```
┌─────────────────────────────────────────┐
│ Rename Set                          [X] │
├─────────────────────────────────────────┤
│ Current name: Base                      │
│ New name: [________________________]    │
│                                         │
│              [Cancel] [Rename]          │
└─────────────────────────────────────────┘
```

### Unsaved Changes Warning

When switching sets with unsaved changes:

```
┌─────────────────────────────────────────┐
│ Unsaved Changes                     [X] │
├─────────────────────────────────────────┤
│ Set "Base" has unsaved changes.         │
│ What would you like to do?              │
│                                         │
│  [Save & Switch] [Switch Without Saving] [Cancel]  │
└─────────────────────────────────────────┘
```

## Data Model

### In-Memory Structure

```javascript
// New state in a sets management module
const setsState = {
    currentSetId: 'base',
    sets: {
        'base': {
            id: 'base',
            name: 'Base',
            tubercles: [...],
            edges: [...],
            isDirty: false,
            undoStack: [...],
            redoStack: [...],
            createdAt: '2025-12-15T10:00:00Z',
            modifiedAt: '2025-12-15T10:30:00Z'
        },
        'manual-edit': {
            id: 'manual-edit',
            name: 'Manual Edit',
            tubercles: [...],
            edges: [...],
            isDirty: true,
            undoStack: [...],
            redoStack: [...],
            createdAt: '2025-12-15T10:15:00Z',
            modifiedAt: '2025-12-15T10:45:00Z'
        }
    },
    setOrder: ['base', 'manual-edit']  // Display order
};
```

### Shared Data (Not Per-Set)

The following remain shared across all sets:
- Image data and path
- Calibration settings
- Extraction parameters (in Configure tab)
- Display settings (overlay toggles, colors, etc.)

## File Format

### New SLO Format (v2)

```json
{
    "version": 2,
    "image": "P2_Fig1c_Paralepidosteus_sp_Acre_5.73um.tif",
    "calibration": {
        "um_per_px": 0.33,
        "method": "scale_bar"
    },
    "activeSetId": "base",
    "sets": [
        {
            "id": "base",
            "name": "Base",
            "createdAt": "2025-12-15T10:00:00Z",
            "modifiedAt": "2025-12-15T10:30:00Z",
            "tubercles": [...],
            "edges": [...]
        },
        {
            "id": "manual-edit",
            "name": "Manual Edit",
            "createdAt": "2025-12-15T10:15:00Z",
            "modifiedAt": "2025-12-15T10:45:00Z",
            "tubercles": [...],
            "edges": [...]
        }
    ]
}
```

### Backward Compatibility

When loading v1 SLO files (no version field or version: 1):
- Import tubercles/edges as a single set named "Base"
- Convert to v2 format in memory
- Save as v2 format

## Module Changes

### New Module: `sets.js`

Core functionality:
- `init()` - Initialize with default "Base" set
- `createSet(name, initialContent)` - Create new set
- `switchSet(setId)` - Switch active set
- `deleteSet(setId)` - Delete a set
- `renameSet(setId, newName)` - Rename a set
- `duplicateSet(setId, newName)` - Duplicate a set
- `getCurrentSet()` - Get active set data
- `getSetList()` - Get list of all sets (for UI)
- `markDirty(setId)` - Mark set as having unsaved changes
- `markClean(setId)` - Mark set as saved
- `hasUnsavedChanges(setId)` - Check dirty state

Events dispatched:
- `setCreated` - New set created
- `setDeleted` - Set deleted
- `setRenamed` - Set renamed
- `setChanged` - Active set switched
- `setDirtyStateChanged` - Dirty state changed

### Changes to `editor.js`

- Get/set data through `sets.js` instead of local arrays
- Undo/redo operations scoped to current set
- Mark current set dirty on any edit
- Clear undo/redo stacks when switching sets (stacks are per-set)

### Changes to `overlay.js`

- Render data from current set via `sets.js`
- Selection state is per-set or cleared on switch (TBD)

### Changes to `data.js`

- Display statistics for current set
- Update tables for current set
- Listen for `setChanged` event to refresh

### Changes to `extraction.js`

- Results go to current set (replacing existing data)
- Option to create new set with extraction results

### Changes to `app.js` (SLO save/load)

- Save all sets in v2 format
- Load and convert v1 format
- Handle per-set dirty state for save warnings

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+1` through `Ctrl+9` | Switch to set 1-9 |
| `Ctrl+N` | Create new set |
| `Ctrl+S` | Save current set |

## Workflow Examples

### Workflow 1: Parameter Comparison

1. Load image, calibrate
2. Set extraction parameters for high sensitivity
3. Click "Extract" → results in "Base" set
4. Click [+] → "Copy from current set" → name "High Sensitivity"
5. Go back to Base, change parameters to low sensitivity
6. Click "Extract" → Base now has low sensitivity results
7. Click set buttons to compare

### Workflow 2: Manual Editing Comparison

1. Load image with existing SLO (Base set)
2. Click [+] → "Copy from current set" → name "Edited"
3. Make manual edits in "Edited" set
4. Click between "Base" and "Edited" to compare before/after

### Workflow 3: Multi-Annotator

1. Annotator A creates annotations, saves as SLO
2. Annotator B loads SLO, clicks [+] → "Empty" → name "Annotator B"
3. Annotator B creates their annotations
4. Compare sets to see agreement/disagreement

## Implementation Phases

### Phase 1: Core Infrastructure
- [ ] Create `sets.js` module with basic operations
- [ ] Add set selector bar UI (static, single "Base" set)
- [ ] Migrate data storage to use sets module
- [ ] Update overlay/data/editor to use sets module
- [ ] Per-set dirty state tracking

### Phase 2: Set Management
- [ ] Create new set functionality
- [ ] Switch between sets
- [ ] Delete set (with confirmation)
- [ ] Rename set
- [ ] Duplicate set

### Phase 3: Persistence
- [ ] v2 SLO format implementation
- [ ] Backward compatible loading of v1 files
- [ ] Save all sets
- [ ] Unsaved changes warning on set switch

### Phase 4: Undo/Redo Per-Set
- [ ] Move undo/redo stacks into set data
- [ ] Clear/restore stacks on set switch
- [ ] Update undo/redo button states per set

### Phase 5: Polish
- [ ] Keyboard shortcuts
- [ ] Export single set
- [ ] Import set from file
- [ ] Set management dropdown menu

## Testing Checklist

- [ ] Default "Base" set created on image load
- [ ] Create new empty set
- [ ] Create new set as copy
- [ ] Switch between sets updates overlay
- [ ] Switch between sets updates statistics
- [ ] Switch between sets updates data tables
- [ ] Dirty indicator shows on edits
- [ ] Save clears dirty indicator
- [ ] Unsaved changes warning on switch
- [ ] Delete set with confirmation
- [ ] Cannot delete last set
- [ ] Rename set updates button
- [ ] Duplicate set creates independent copy
- [ ] v1 SLO loads as Base set
- [ ] v2 SLO loads all sets
- [ ] Save creates v2 format
- [ ] Undo/redo isolated per set
- [ ] Keyboard shortcuts work
- [ ] Maximum 10 sets enforced
- [ ] Long set names truncated in buttons

---

## Open Questions

### Q1: Should calibration be shared across all sets or per-set?

**Proposed Answer:** Shared across all sets.

*Rationale:* Calibration is a property of the image (pixel-to-micrometer conversion), not the annotation. Different annotation sets on the same image should use the same calibration.

- [X] Accepted
- [ ] Alternative: _________________________________

---

### Q2: When running extraction, should results replace current set or create a new set?

**Proposed Answer:** Replace current set data, with a warning if the set has existing data.

*Rationale:* Most common workflow is iterating on extraction parameters. Creating a new set each time would clutter the UI. Users who want to preserve should duplicate first.

*Warning dialog:*
```
Set "Base" already has data (45 tubercles, 120 connections).
Running extraction will replace this data.
[Replace] [Create New Set] [Cancel]
```

- [X] Accepted
- [ ] Alternative: _________________________________

---

### Q3: Should undo/redo work across sets or be per-set?

**Proposed Answer:** Per-set. Each set maintains its own undo/redo stack.

*Rationale:*
- Undo should not affect a different set than you're working on
- Switching sets and undoing would be confusing if it affected the previous set
- Users expect undo to reverse their recent actions in the current context

- [X] Accepted
- [ ] Alternative: _________________________________

---

### Q4: What should happen to selection state when switching sets?

**Proposed Answer:** Clear selection when switching sets.

*Rationale:* Selected tubercle/edge IDs may not exist in the target set, or may refer to different items. Clearing avoids confusion.

- [X] Accepted
- [ ] Alternative: _________________________________

---

### Q5: Should there be a "compare" mode showing multiple sets overlaid with different colors?

**Proposed Answer:** Defer to Phase 2. Initial implementation focuses on rapid switching. Compare overlay is a future enhancement.

*Rationale:* Adds significant complexity (color coding, legend, selection handling). Rapid switching achieves 80% of the value with 20% of the effort.

- [ ] Accepted
- [X] Alternative: _I think it is more likely week will want side-by-side than overlaid. I think overlaid will be hard to optically understand. Don't plan on implementing this unless I ask for it.__________________

---

### Q6: How should the set selector bar handle many sets (approaching max of 10)?

**Proposed Answer:** Horizontal scrolling if buttons exceed available width, with scroll indicators.

*Alternative considered:* Dropdown menu. Rejected because it adds a click and hides the set names.

- [X] Accepted
- [ ] Alternative: _________________________________

---

### Q7: Should set names have character limits or validation?

**Proposed Answer:**
- Maximum 30 characters
- No special characters that would break JSON/filenames (no `/\:*?"<>|`)
- Names must be unique within the image
- Whitespace trimmed

- [ ] Accepted
- [X] Alternative: Let's cap it at 20. Otherwise accepted.

---

### Q8: What should the extraction "Create New Set" option do exactly?

**Proposed Answer:**
1. Create a new set with the provided name
2. Switch to that set
3. Run extraction with current parameters
4. Results go into the new set

This combines set creation and extraction in one step for convenience.

- [X] Accepted
- [ ] Alternative: _________________________________

---

### Q9: Should there be a visual indicator in the stats bar showing which set is active?

**Proposed Answer:** Yes, add the set name to the stats bar, e.g., `[Base] TUB: 45 | Ø: 3.21 µm | ...`

*Rationale:* Reinforces which set is being viewed, especially useful when stats bar is the only visible indicator (tabs panel collapsed).

- [X] Accepted
- [ ] Alternative: _________________________________

---

### Q10: How should "Save" work with multiple sets?

**Proposed Answer:** "Save" (Ctrl+S) saves the entire SLO file with ALL sets, not just the current set.

*Rationale:*
- Simpler mental model (one file = all sets)
- Prevents data loss from forgetting to save other sets
- Matches typical document model (save saves everything)

The dirty indicator should show if ANY set has unsaved changes.

- [X] Accepted
- [ ] Alternative: _________________________________

---

## Future Enhancements (Out of Scope)

These are explicitly NOT part of this feature but noted for future consideration:

1. **Compare Overlay Mode**: Show two sets overlaid with different colors
2. **Set Statistics Comparison**: Side-by-side statistics table
3. **Set Diff View**: Highlight tubercles/edges that differ between sets
4. **Set Comments/Notes**: Add text notes to each set
5. **Set Locking**: Lock a set to prevent accidental edits
6. **Set Colors**: Assign colors to sets for visual differentiation
7. **Bulk Operations**: Delete multiple sets, merge sets
