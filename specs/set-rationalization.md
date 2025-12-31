# Set Concept Rationalization

## Problem Statement

The current "Set" concept in the UI is not immediately understandable to users:

1. **No Label**: The stats bar shows the set name (e.g., "Base") without any label indicating what it is
2. **Hidden in Extraction Tab**: Set management buttons are only visible in the set-selector-bar above the image, which is visually associated with the Extraction tab workflow
3. **No Context in Data Tab**: The Data tab displays statistics without indicating which set they belong to
4. **No Context in Edit Tab**: The Edit tab provides no indication of which set is being edited
5. **Inconsistent Access**: Users must mentally track which set is active across different tabs

## Goals

1. Make the "Set" concept immediately understandable
2. Provide consistent set context across all relevant tabs
3. Allow set switching from multiple locations (not just Extraction tab)
4. Reduce cognitive load by always showing which set is being viewed/edited

---

## Proposed Changes

### 1. Stats Bar Enhancement

**Current:**
```
[Base] TUB: 65  Ø: 5.38µm  ITC: 161  Space: 3.59µm  ...
```

**Proposed:**
```
Set: [Base ▾] TUB: 65  Ø: 5.38µm  ITC: 161  Space: 3.59µm  ...
```

**Changes:**
- Add "Set:" label before the set name
- Make the set name a dropdown button (with ▾ indicator)
- Clicking opens a dropdown with:
  - List of all sets (click to switch)
  - Divider
  - "New Set..." option (opens create dialog)
  - "Manage Sets..." option (scrolls to Extraction tab set-selector)

**Rationale:** The stats bar is always visible, making it the ideal location for a quick set switcher. The label clarifies what "Base" means.

### 2. Data Tab Header

**Current:**
```
Data
─────────────────────────
Statistics
  Tubercles: 65
  ...
```

**Proposed:**
```
Data
─────────────────────────
Current Set: [Base ▾]  [+ New Set]
─────────────────────────
Statistics
  Tubercles: 65
  ...
```

**Changes:**
- Add a "current-set-header" section at the top of the Data tab
- Display "Current Set:" label with the set name
- Include a dropdown (same as stats bar) for switching sets
- Include a "+ New Set" button for quick creation
- Style consistently with other tab headers

**Rationale:** Users viewing data need to know which set's data they're seeing. Quick access to other sets allows comparison without tab-switching.

### 3. Edit Tab Header

**Current:**
```
Edit [?]
Manually edit tubercles and connections.
─────────────────────────
Add
  [Add Tubercle] [Add Connection]
  ...
```

**Proposed:**
```
Edit [?]
Manually edit tubercles and connections.
─────────────────────────
Editing Set: [Base]
─────────────────────────
Add
  [Add Tubercle] [Add Connection]
  ...
```

**Changes:**
- Add an "editing-set-indicator" below the tab description
- Display "Editing Set:" label with the set name (non-editable display)
- Consider a small link/button to switch sets (with unsaved changes warning)
- Style as a subtle info bar (not a full control panel)

**Rationale:** When editing, users need constant awareness of which set they're modifying. A simpler display (vs. full dropdown) emphasizes that editing is in-progress.

### 4. Set Selector Bar Improvements

**Current location:** Above the image, always visible

**Proposed changes:**
- Add a subtle label: "Sets:" before the set buttons
- Consider moving to a more prominent/discoverable location OR
- Keep current location but ensure other access points (stats bar, Data tab) make it discoverable

### 5. Create Set Dialog Enhancement

**Current options:**
- Empty (start fresh)
- Copy from current set
- Run extraction with current params

**Proposed additional option:**
- Copy from: [dropdown of all sets]

This allows copying from any set, not just the current one.

---

## Implementation Plan

### Phase 1: Labels and Context (High Priority)

1. **Stats Bar Label**
   - File: `workspace.html`
   - Add "Set:" label before `#statsBarSetName`
   - CSS: Style label consistently with other stats bar labels

2. **Data Tab Header**
   - File: `workspace.html`
   - Add `current-set-header` div at top of Data tab pane
   - Include set name display and "+ New Set" button
   - File: `data.js` or new `setUI.js` extension
   - Update header when set changes

3. **Edit Tab Indicator**
   - File: `workspace.html`
   - Add `editing-set-indicator` div below tab description
   - File: `editor.js`
   - Update indicator when set changes

### Phase 2: Set Switching Dropdowns (Medium Priority)

4. **Stats Bar Dropdown**
   - File: `workspace.html`
   - Convert set name to dropdown button
   - File: `setUI.js`
   - Implement dropdown rendering and click handlers
   - Handle set switching with unsaved changes check

5. **Data Tab Dropdown**
   - Reuse stats bar dropdown component/logic
   - File: `data.js` or `setUI.js`
   - Sync with stats bar dropdown state

### Phase 3: Create Dialog Enhancement (Low Priority)

6. **Copy From Any Set**
   - File: `setUI.js`
   - Modify `showCreateSetDialog()` to include set dropdown
   - Populate dropdown with all sets when "Copy from:" is selected

---

## UI Mockups

### Stats Bar (Phase 1)
```
┌─────────────────────────────────────────────────────────────┐
│ Set: Base  │ TUB: 65 │ Ø: 5.38µm │ ITC: 161 │ Space: 3.59µm │
└─────────────────────────────────────────────────────────────┘
```

### Stats Bar with Dropdown (Phase 2)
```
┌─────────────────────────────────────────────────────────────┐
│ Set: [Base ▾]│ TUB: 65 │ Ø: 5.38µm │ ITC: 161 │ Space: 3.59µm│
└──────┬──────────────────────────────────────────────────────┘
       │ ┌─────────────────┐
       └─│ ● Base          │
         │   Extracted     │
         │   Manual Edit   │
         ├─────────────────┤
         │ + New Set...    │
         │ ⚙ Manage Sets...│
         └─────────────────┘
```

### Data Tab Header (Phase 1 & 2)
```
┌─────────────────────────────────────────┐
│ Data                                    │
├─────────────────────────────────────────┤
│ Current Set: [Base ▾]  [+ New Set]      │
├─────────────────────────────────────────┤
│ Statistics                              │
│   Tubercles: 65                         │
│   Mean Diameter: 5.38 µm                │
│   ...                                   │
└─────────────────────────────────────────┘
```

### Edit Tab Indicator (Phase 1)
```
┌─────────────────────────────────────────┐
│ Edit [?]                                │
│ Manually edit tubercles and connections.│
├─────────────────────────────────────────┤
│ 📝 Editing: Base                        │
├─────────────────────────────────────────┤
│ Add                                     │
│   [Add Tubercle] [Add Connection]       │
│   ...                                   │
└─────────────────────────────────────────┘
```

---

## CSS Considerations

### New Classes Needed

```css
/* Stats bar set label */
.stats-bar-set-label {
    color: var(--text-muted);
    font-size: 0.8rem;
    margin-right: 0.25rem;
}

/* Stats bar set dropdown */
.stats-bar-set-dropdown {
    position: relative;
    display: inline-flex;
    align-items: center;
}

.stats-bar-set-btn {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 0.25rem;
    padding: 0.125rem 0.5rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 0.25rem;
}

/* Tab set header */
.tab-set-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.5rem 0;
    margin-bottom: 0.75rem;
    border-bottom: 1px solid var(--border-color);
}

.tab-set-label {
    color: var(--text-muted);
    font-size: 0.9rem;
}

/* Edit tab indicator */
.editing-set-indicator {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    background: var(--bg-secondary);
    border-radius: 0.25rem;
    margin-bottom: 1rem;
    font-size: 0.9rem;
}

.editing-set-indicator::before {
    content: "📝";
}
```

---

## Event Handling

The existing `setChanged` event should be used to update all new UI elements:

```javascript
document.addEventListener('setChanged', (e) => {
    const set = e.detail.set;

    // Update stats bar
    updateStatsBarSetName();

    // Update Data tab header
    updateDataTabSetHeader(set);

    // Update Edit tab indicator
    updateEditTabIndicator(set);
});
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `workspace.html` | Stats bar label, Data tab header, Edit tab indicator |
| `main.css` | New classes for set UI elements |
| `setUI.js` | Dropdown logic, event handlers, new render functions |
| `data.js` | Listen for set changes, update header |
| `editor.js` | Listen for set changes, update indicator |

---

## Testing Checklist

- [ ] Stats bar shows "Set:" label
- [ ] Data tab shows current set name
- [ ] Edit tab shows current set name
- [ ] Set name updates across all locations when switching sets
- [ ] Dropdown (Phase 2) allows switching from stats bar
- [ ] Dropdown (Phase 2) allows switching from Data tab
- [ ] "+ New Set" button in Data tab opens create dialog
- [ ] Unsaved changes warning appears when switching sets
- [ ] Create dialog allows copying from any set (Phase 3)
- [ ] All set indicators sync correctly after save/load SLO

---

## Future Considerations

1. **Set Comparison View**: Side-by-side comparison of two sets' statistics
2. **Set Merge**: Combine annotations from multiple sets
3. **Set Export**: Export individual sets to separate SLO files
4. **Set Colors**: Assign colors to sets for visual differentiation in overlay
