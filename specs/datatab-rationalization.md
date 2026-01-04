# Data Tab Rationalization Specification

## Problem Statement

The Data tab currently mixes stored data (persisted in annotation files) with computed/derived statistics without clear distinction. Users cannot easily understand:
1. What data is saved when they export annotations
2. What is calculated on-the-fly and will be regenerated on load
3. Some stored fields are not visible at all (source, ellipse params, per-set parameters)

## Goals

1. **Clear visual separation** between stored vs computed data
2. **All stored data viewable** - nothing hidden from the user
3. **Intuitive organization** - logical grouping that matches mental model
4. **Maintain existing functionality** - no regression in features

---

## Annotation File Format (v3.0)

This specification introduces version 3.0 of the annotation file format with enhanced metadata and per-set provenance tracking.

### File Metadata Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `format` | string | Yes | Format identifier: `"fish-scale-annotations"` |
| `version` | string | Yes | Semantic version: `"3.0"` |
| `purpose` | string | Yes | Human-readable description of format purpose |
| `image_name` | string | Yes | Source image filename (not full path) |
| `created` | string | Yes | ISO 8601 timestamp when file was first created |
| `modified` | string | Yes | ISO 8601 timestamp of last modification |
| `calibration` | object | Yes | Current calibration (image-level) |
| `parameters` | object | No | Current/working extraction parameters |
| `activeSetId` | string | Yes | ID of currently active annotation set |
| `sets` | array | Yes | Array of annotation sets |

### Per-Set Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique set identifier (UUID or sequential) |
| `name` | string | Yes | User-defined name (max 20 chars) |
| `createdAt` | string | Yes | ISO 8601 timestamp when set was created |
| `modifiedAt` | string | Yes | ISO 8601 timestamp of last modification |
| `calibration_um_per_pixel` | number | Yes | Calibration snapshot at set creation |
| `parameters` | object | No | Extraction parameters used to create this set |
| `tubercles` | array | Yes | Array of tubercle objects |
| `edges` | array | Yes | Array of edge/connection objects |
| `history` | array | No | Array of history event objects |

### Example Annotation File

```json
{
  "format": "fish-scale-annotations",
  "version": "3.0",
  "purpose": "Tubercle and intertubercular space annotations for SEM fish scale classification",
  "image_name": "P1_Fig4_Atractosteus_simplex_7.07um.tif",
  "created": "2025-01-15T10:30:00Z",
  "modified": "2025-01-15T14:22:35Z",

  "calibration": {
    "um_per_pixel": 0.10,
    "method": "manual",
    "scale_bar_length_um": 100,
    "scale_bar_length_px": 1000
  },

  "parameters": {
    "method": "log",
    "threshold": 0.05,
    "min_diameter_um": 2.0,
    "max_diameter_um": 10.0,
    "min_circularity": 0.5,
    "clahe_clip": 0.03,
    "clahe_kernel": 8,
    "blur_sigma": 1.0,
    "neighbor_graph": "gabriel",
    "cull_factor": 1.8
  },

  "activeSetId": "set-2",

  "sets": [
    {
      "id": "set-1",
      "name": "Initial Extraction",
      "createdAt": "2025-01-15T10:30:00Z",
      "modifiedAt": "2025-01-15T10:30:00Z",
      "calibration_um_per_pixel": 0.10,
      "parameters": {
        "method": "log",
        "threshold": 0.05,
        "min_diameter_um": 2.0,
        "max_diameter_um": 10.0,
        "min_circularity": 0.5,
        "clahe_clip": 0.03,
        "clahe_kernel": 8,
        "blur_sigma": 1.0,
        "neighbor_graph": "gabriel",
        "cull_factor": 1.8
      },
      "tubercles": [
        {
          "id": 1,
          "centroid_x": 150.5,
          "centroid_y": 200.3,
          "diameter_px": 45.2,
          "diameter_um": 4.52,
          "radius_px": 22.6,
          "circularity": 0.95,
          "source": "extracted"
        },
        {
          "id": 2,
          "centroid_x": 180.2,
          "centroid_y": 210.1,
          "diameter_px": 43.1,
          "diameter_um": 4.31,
          "radius_px": 21.55,
          "circularity": 0.92,
          "source": "extracted",
          "major_axis_px": 44.5,
          "minor_axis_px": 41.7,
          "major_axis_um": 4.45,
          "minor_axis_um": 4.17,
          "orientation": 0.785,
          "eccentricity": 0.35
        }
      ],
      "edges": [
        {
          "id1": 1,
          "id2": 2,
          "x1": 150.5,
          "y1": 200.3,
          "x2": 180.2,
          "y2": 210.1,
          "center_distance_um": 3.20,
          "edge_distance_um": 1.58
        }
      ],
      "history": [
        {
          "type": "extraction",
          "timestamp": "2025-01-15T10:30:00Z",
          "calibration_um_per_pixel": 0.10,
          "tubercles": 45,
          "connections": 89,
          "method": "log",
          "parameters": {
            "threshold": 0.05,
            "min_diameter_um": 2.0
          }
        }
      ]
    },
    {
      "id": "set-2",
      "name": "After Manual Edit",
      "createdAt": "2025-01-15T11:00:00Z",
      "modifiedAt": "2025-01-15T14:22:35Z",
      "calibration_um_per_pixel": 0.10,
      "parameters": {
        "method": "log",
        "threshold": 0.05
      },
      "tubercles": [
        {
          "id": 1,
          "centroid_x": 150.5,
          "centroid_y": 200.3,
          "diameter_px": 45.2,
          "diameter_um": 4.52,
          "radius_px": 22.6,
          "circularity": 0.95,
          "source": "extracted"
        },
        {
          "id": 3,
          "centroid_x": 220.0,
          "centroid_y": 195.5,
          "diameter_px": 42.0,
          "diameter_um": 4.20,
          "radius_px": 21.0,
          "circularity": 0.88,
          "source": "manual"
        }
      ],
      "edges": [],
      "history": [
        {
          "type": "clone",
          "timestamp": "2025-01-15T11:00:00Z",
          "source_set": "Initial Extraction"
        },
        {
          "type": "manual_edit",
          "timestamp": "2025-01-15T14:22:35Z",
          "calibration_um_per_pixel": 0.10,
          "summary": "Deleted 1 tubercle, added 1 tubercle"
        }
      ]
    }
  ]
}
```

### Version History

| Version | Changes |
|---------|---------|
| 1.0 | Original format with single tubercle/edge arrays |
| 2.0 | Added multiple annotation sets support |
| 3.0 | Added per-set calibration snapshots, `format`/`version`/`purpose` metadata, `source` field on tubercles, calibration in history events |

### Backward Compatibility

- **v1.0 files**: Loaded as single set, no calibration snapshot (uses current)
- **v2.0 files**: Loaded with sets intact, no calibration snapshot (uses current)
- **v3.0 files**: Full provenance tracking

When saving, always write v3.0 format. The loader should detect version from the `version` field (or infer from structure for legacy files).

---

## Current vs Proposed Structure

### Current Structure (flat, mixed)
```
Data Tab
├── Set selector dropdown
├── Statistics Panel (mixed stored counts + computed stats)
├── TUB table (partial - missing source, ellipse)
├── ITC table
└── History (collapsible)
```

### Proposed Structure (three-panel, separated by scope)
```
Data Tab
├── Set selector dropdown
│
├── IMAGE-LEVEL DATA PANEL (shared across all sets)
│   └── Calibration (current value, link to edit)
│
├── SET DATA PANEL (per-set stored data)
│   ├── Set Information (name, created, modified, calibration snapshot)
│   ├── Extraction Parameters (params used for this set)
│   ├── Tubercles table (enhanced with source column)
│   ├── Connections table
│   └── History
│
└── COMPUTED STATISTICS PANEL (derived, not saved)
    ├── Summary counts (n_tubercles, n_edges, boundary/interior)
    ├── Measurements (mean/std diameter, mean/std space)
    ├── Classification (genus, confidence)
    └── Hexagonalness metrics (score + components)
```

---

## Data Classification

### Stored Data (persisted in `*_annotations.json`)

#### Image-Level Data (shared across all sets)

| Category | Fields | Currently Visible |
|----------|--------|-------------------|
| **Calibration** | um_per_pixel, method | In Calibration tab only |
| **Current Parameters** | method, threshold, min/max_diameter, etc. | In Configure tab |

#### Per-Set Data

| Category | Fields | Currently Visible |
|----------|--------|-------------------|
| **Set Metadata** | id, name, createdAt, modifiedAt | No |
| **Set Parameters** | parameters used when set was created | Only via History "Restore" |
| **Set Calibration** | calibration value when set was created | **No - not currently stored** |
| **Tubercle** | id, centroid_x/y, diameter_px/um, radius_px, circularity | Yes |
| **Tubercle** | source ("extracted"/"manual") | **No** |
| **Tubercle** | ellipse params (major/minor axis, orientation, eccentricity) | **No** |
| **Edge** | id1, id2, x1/y1/x2/y2, center_distance_um, edge_distance_um | Yes |
| **History** | event log with timestamps | Yes |
| **History Events** | calibration at time of event | **No - not currently stored** |

**Important**: Calibration affects all µm values. When calibration changes after a set is created, the stored µm values become inconsistent with the current calibration. We need to record calibration at key moments (set creation, extraction events) to maintain provenance.

### Computed Data (calculated on-the-fly, not saved)

| Category | Fields | Source |
|----------|--------|--------|
| **Counts** | n_tubercles, n_edges | Array lengths |
| **Counts** | n_boundary, n_interior | Count is_boundary flags |
| **Diameter Stats** | mean_diameter_um, std_diameter_um | From tubercle diameters |
| **Spacing Stats** | mean_space_um, std_space_um | From edge_distance_um values |
| **Classification** | suggested_genus, confidence | From mean values vs reference ranges |
| **Hexagonalness** | score, spacing_uniformity, degree_score, edge_ratio_score | From edge topology |
| **Hex Supporting** | spacing_cv, mean_degree, reliability | From edge/node analysis |
| **Per-Tubercle** | is_boundary flag | Delaunay triangulation |

---

## UI Design

### Three-Panel Layout

#### Image-Level Data Panel
- **Header**: "Image-Level Data" with image icon, subtitle "Shared across all annotation sets"
- **Visual**: Solid border, neutral background
- **Content**: Calibration display (read-only reference to Calibration tab)
- **Default**: Collapsed (single line of info, low priority)

#### Set Data Panel
- **Header**: "Set Data" with layers icon, subtitle "Data for current annotation set"
- **Visual**: Solid border, slightly darker header background
- **Sections**: All collapsible with expand/collapse toggles

#### Computed Statistics Panel
- **Header**: "Computed Statistics" with calculator icon, subtitle "Calculated from stored data (not saved)"
- **Visual**: Dashed border, lighter appearance to indicate "derived"
- **Content**: Current statistics panel content, reorganized

### Image-Level Data Panel Content

```
▸ Image-Level Data
    Calibration: 0.10 µm/px (manual)        [Edit in Calibration tab]
```
- Shows current calibration value
- Link to Calibration tab for editing
- Default: collapsed

### New Subsections in Set Data Panel

#### 1. Set Information (new)
```
▸ Set Information
    Name:     Base
    Created:  2025-01-15 10:30:00
    Modified: 2025-01-15 11:45:23
    Calibration: 0.10 µm/px  ✓
```
- Default: collapsed
- Shows set metadata that was previously invisible
- Shows calibration snapshot from when set was created
- If calibration differs from current: show ⚠️ warning with tooltip

#### 2. Extraction Parameters (new)
```
▸ Extraction Parameters
    Method: log | Threshold: 0.05 | Diameter: 2.0-10.0 µm
    Circularity: 0.5 | CLAHE: 0.03/8 | Blur: 1.0
    Graph: gabriel | Cull: 1.8x

    [Apply to Configure]
```
- Default: collapsed
- Shows parameters stored with this set (or "No parameters recorded" for legacy sets)
- "Apply to Configure" button copies these params to Configure tab

#### 3. Enhanced Tubercles Table
```
▸ Tubercles (45)                              [Columns ▼]
    ID | X | Y | Diam (µm) | Circ | Source | Bdry
    ─────────────────────────────────────────────────
    1  | 150 | 200 | 4.52 | 95% | extracted | -
    2  | 180 | 210 | 4.31 | 92% | manual    | -
```
- **New column: Source** - shows "extracted" or "manual" with distinct styling
- **Column visibility dropdown** - toggle optional columns:
  - Default visible: ID, X, Y, Diam, Circ, Source
  - Optional: Bdry, Major Axis, Minor Axis, Orientation, Eccentricity
- Manual tubercles styled differently (italic, accent color)

#### 4. Connections Table (unchanged structure)
- Keep current columns: ID1, ID2, Center (µm), Edge (µm)

#### 5. History (moved into Stored Data panel)
- Keep current implementation
- Logical grouping with other stored data

### Computed Statistics Panel Content

Reorganize existing statistics into clear groups:

```
COMPUTED STATISTICS
───────────────────────────────────────────────

Summary
    Tubercles:   45  (32 interior, 13 boundary)
    Connections: 89

Measurements
    Mean Diameter: 4.52 ± 0.34 µm
    Mean Space:    2.15 ± 0.28 µm

Classification
    Suggested Genus: Atractosteus (high confidence)

───────────────────────────────────────────────

Hexagonalness: 0.720 / 1.0                  [?]
    Spacing Uniformity: 0.812 (40%)         [?]
    Degree Score:       0.687 (45%)         [?]
    Edge Ratio Score:   0.621 (15%)         [?]
    ────
    Spacing CV:   0.094                     [?]
    Mean Degree:  5.82 neighbors            [?]
```

---

## Implementation Plan

### Phase 1: Data Model Changes (sets.js, persistence.py)

1. Add `calibration_um_per_pixel` field to set structure
2. Capture calibration snapshot when creating new sets
3. Capture calibration snapshot on extraction events in history
4. Update `save_annotations()` to persist per-set calibration
5. Update `load_annotations()` to read per-set calibration (with fallback for legacy)

### Phase 2: HTML Structure (workspace.html)

1. Create three-panel structure: Image-Level, Set Data, Computed Statistics
2. Add "Image-Level Data" panel with calibration display
3. Add "Set Data" panel with header
4. Add "Computed Statistics" panel with header
5. Add new "Set Information" section (with calibration + mismatch warning)
6. Add new "Extraction Parameters" section
7. Move History section into Set Data panel
8. Add Source column to TUB table header
9. Add column visibility toggle button

### Phase 3: CSS Styling (main.css)

1. Add `.data-panel`, `.image-level-panel`, `.set-data-panel`, `.computed-stats-panel` styles
2. Add `.data-panel-header` with icon and subtitle styling
3. Visual distinction: solid borders for stored, dashed for computed
4. Add `.source-extracted` and `.source-manual` column styles
5. Add `.calibration-mismatch` warning styles
6. Add collapsible section styles (`.data-section.collapsible`)
7. Add column dropdown styles

### Phase 4: JavaScript Logic (data.js)

1. Add `renderImageLevelData()` function
2. Add `renderSetInfo()` function with calibration mismatch detection
3. Add `renderSetParameters()` function
4. Add `applyParametersToConfigure()` function
5. Add `recalculateWithCurrentCalibration()` function (for Q11)
6. Enhance `renderTubercleTable()` with Source column
7. Add column visibility state and toggle logic
8. Add collapsible section toggle handlers
9. Update `setData()` to call new render functions

### Phase 5: Integration & Testing

1. Wire up "Apply to Configure" button to configure.js
2. Wire up "Recalculate" button for calibration mismatch
3. Add event listeners for set/calibration changes
4. Test with legacy v1 annotation files (no per-set calibration)
5. Test calibration mismatch detection and recalculation
6. Test with sets that have/don't have ellipse data

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/fish_scale_ui/templates/workspace.html` | Restructure Data tab with three panels |
| `src/fish_scale_ui/static/css/main.css` | Add panel, mismatch warning, and column styles |
| `src/fish_scale_ui/static/js/data.js` | New render functions, calibration display, column toggles |
| `src/fish_scale_ui/static/js/sets.js` | Add `calibration_um_per_pixel` to set structure, capture on creation |
| `src/fish_scale_ui/static/js/extraction.js` | Record calibration in history events |
| `src/fish_scale_ui/static/js/configure.js` | Add `applyParameters()` public method |
| `src/fish_scale_ui/services/persistence.py` | Persist/load per-set calibration |
| `docs/annotations-persistence.md` | Document new per-set calibration field |

---

## Edge Cases

1. **Legacy sets without parameters**: Show "No parameters recorded for this set"
2. **Legacy sets without calibration snapshot**: Use current calibration, show "Calibration not recorded (legacy set)"
3. **Calibration mismatch**: Show warning icon, offer recalculation button
4. **Tubercles without source field**: Default to "extracted"
5. **Tubercles without ellipse data**: Hide ellipse columns or show "-"
6. **Empty annotation set**: Show appropriate empty states in all panels
7. **No calibration set at all**: Show "No calibration" in Image-Level panel, link to Calibration tab

---

## Future Considerations

- Export options could respect the stored/computed distinction
- "What's saved" indicator could appear during save operations
- Computed statistics could optionally be cached in annotation files for performance

---

## Open Design Questions

### Q1: Should the Boundary column move to Stored Data?

**Context**: The `is_boundary` flag is currently computed via Delaunay triangulation during measurement, but it's derived purely from the stored edge topology. It could arguably be:
- Stored with each tubercle (current: not stored)
- Computed and shown in the TUB table in Stored Data panel
- Shown only in Computed Statistics as a count

**Recommendation**: Keep `is_boundary` as **computed** but show the Bdry column in the TUB table as an optional column. Add a footnote or tooltip: "Boundary status is computed from connection topology". This matches the current behavior and avoids storing redundant data.

---

### Q2: How should calibration be displayed and stored?

**Context**: Calibration (`um_per_pixel`, method) is stored in the annotation JSON file at the image level. However, all µm measurements in sets depend on calibration. If calibration changes after extraction, stored µm values become inconsistent.

**Current problem**:
- Calibration is stored once at image level
- Sets store µm values computed with whatever calibration existed at extraction time
- If user changes calibration later, old sets have stale µm values
- No record of what calibration was used for each set/event

**Display Options**:
- A) Show current calibration in a new "Image-Level Data" section in Stored Data panel
- B) Show per-set calibration (the value when set was created) in Set Information
- C) Both A and B

**Storage Options**:
- X) Store `calibration_um_per_pixel` with each set (snapshot at creation)
- Y) Store `calibration_um_per_pixel` with each history event (extraction, add-tubercle, etc.)
- Z) Both X and Y

**Recommendation**:
- Display: **Option C** - Show both. Image-level section shows current calibration. Per-set section shows "Calibration at creation: X µm/px" with warning if it differs from current.
- Storage: **Option X** - Store calibration snapshot with each set. History events that use calibration (extraction) should also record it for full provenance. This allows detecting "this set was created with different calibration" and potentially offering recalculation.

**Proposed set structure addition**:
```json
{
  "id": "set-1",
  "name": "Initial Extraction",
  "createdAt": "2025-01-15T10:30:00",
  "calibration_um_per_pixel": 0.1,  // NEW: snapshot at creation
  "parameters": {...},
  "tubercles": [...],
  "edges": [...]
}
```

**UI indication**: If `set.calibration_um_per_pixel !== current_calibration`, show warning icon with tooltip: "This set was created with calibration 0.10 µm/px (current: 0.15 µm/px). Measurements may be inconsistent."

---

### Q3: How to handle the "Apply to Configure" interaction?

**Context**: When user clicks "Apply to Configure" to copy stored parameters to the Configure tab, what should happen?

**Options**:
- A) Silently apply, show toast notification
- B) Apply and switch to Configure tab
- C) Show confirmation dialog first
- D) Apply and highlight changed fields in Configure tab

**Recommendation**: **Option A** - Silently apply with toast notification ("Parameters applied to Configure tab"). Users can then navigate to Configure when ready. Switching tabs automatically is disruptive; confirmation dialogs add friction for a non-destructive action.

---

### Q4: Default collapsed/expanded state for new sections?

**Context**: The new Set Information and Extraction Parameters sections need default states.

**Options**:
- A) Both collapsed by default (keep Data tab compact)
- B) Both expanded by default (make stored data prominent)
- C) Set Info collapsed, Parameters expanded (params more useful)
- D) Persist user preference in settings

**Recommendation**: **Option A** - Both collapsed by default. The TUB and ITC tables are the primary content users interact with. Metadata and parameters are reference information that most users check occasionally. This keeps the tab scannable. Add **Option D** as a future enhancement.

---

### Q5: Column visibility persistence?

**Context**: The new column toggles for TUB table (Source, Bdry, Ellipse columns) - should visibility persist?

**Options**:
- A) Reset to defaults on page reload
- B) Persist in localStorage (like other settings)
- C) Persist per-image in annotation file

**Recommendation**: **Option B** - Persist in localStorage via the existing settings system. Column preferences are user preferences, not data. They should survive page reloads but not be part of the annotation file.

---

### Q6: What to show when a set has no stored parameters?

**Context**: Legacy sets and manually-created sets may not have stored parameters.

**Options**:
- A) Show "No parameters recorded" text
- B) Hide the Extraction Parameters section entirely
- C) Show "No parameters recorded" with link to add current params

**Recommendation**: **Option A** - Show "No parameters recorded for this set" as muted text. Hiding the section would be inconsistent and confusing. Option C adds complexity for an edge case.

---

### Q7: Should computed statistics be collapsible?

**Context**: The Computed Statistics panel could be fully collapsible like the Stored Data panel.

**Options**:
- A) Always expanded (statistics are primary output)
- B) Collapsible with default expanded
- C) Collapsible with default collapsed (emphasize stored data)

**Recommendation**: **Option B** - Collapsible with default expanded. Most users want to see statistics, but power users working on many sets may want to collapse it to focus on the data. Matches the flexibility of the Stored Data panel.

---

### Q8: Visual treatment of the two panels?

**Context**: How distinct should the visual styling be between Stored vs Computed panels?

**Options**:
- A) Subtle distinction (different header backgrounds only)
- B) Moderate distinction (solid vs dashed borders as proposed)
- C) Strong distinction (different background colors for entire panels)
- D) Icon-only distinction (rely on header icons and labels)

**Recommendation**: **Option B** - Moderate distinction with solid vs dashed borders. This is noticeable without being visually heavy. The semantic meaning (solid = permanent, dashed = derived/ephemeral) is intuitive. Strong color differences could make the UI feel fragmented.

---

### Q9: Should the stats bar (always visible) indicate data source?

**Context**: The compact stats bar above the image shows TUB count, diameter, ITC count, space, and hex score. These are all computed values.

**Options**:
- A) Leave as-is (it's a summary view, distinction not needed)
- B) Add subtle indicator (e.g., calculator icon)
- C) Remove it entirely (redundant with Data tab)

**Recommendation**: **Option A** - Leave as-is. The stats bar is a quick reference while working in other tabs. Adding visual noise there would reduce its utility. Users who care about the stored/computed distinction will use the Data tab.

---

### Q10: Order of panels?

**Context**: What order should the three panels appear?

**Options**:
- A) Image-Level → Set Data → Computed Statistics
- B) Set Data → Image-Level → Computed Statistics
- C) Computed Statistics first (most commonly viewed)

**Recommendation**: **Option A** - Image-Level → Set Data → Computed Statistics. This follows the logical hierarchy: image-wide context first, then set-specific data, then derived statistics. Image-Level panel will usually be collapsed, so Set Data (with tables) is effectively at the top.

---

### Q11: What to do when set calibration differs from current?

**Context**: If a set was created with calibration 0.10 µm/px but current calibration is 0.15 µm/px, all stored µm values are "wrong" relative to current calibration.

**Options**:
- A) Display only: Show warning icon, tooltip explains mismatch
- B) Offer recalculation: "Recalculate µm values with current calibration" button
- C) Auto-recalculate: Always display with current calibration (store px, compute µm on display)
- D) Block editing: Warn user before allowing edits to mismatched sets

**Recommendation**: **Option B** - Show warning and offer optional recalculation. The button would:
1. Recompute all `diameter_um` from `diameter_px * current_calibration`
2. Recompute all `edge_distance_um` and `center_distance_um`
3. Update `set.calibration_um_per_pixel` to current value
4. Add history event: "Recalibrated from 0.10 to 0.15 µm/px"

This preserves provenance while giving users a clear path to fix mismatches. Option C (auto-recalculate) would lose the original measurements, which may be intentional for comparison.

---

### Q12: Should parameters also be stored at image level?

**Context**: Currently `parameters` is stored at image level in the JSON, but the spec proposes storing parameters per-set. Should we keep both?

**Options**:
- A) Image-level only (current) - represents "last used" parameters
- B) Per-set only - each set records what was used to create it
- C) Both - image-level for "current/next extraction", per-set for provenance

**Recommendation**: **Option C** - Keep both. Image-level parameters are the "working" parameters shown in Configure tab. Per-set parameters record "what was used" for provenance. This matches how calibration will work (image-level current + per-set snapshot).
