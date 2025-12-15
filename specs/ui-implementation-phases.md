# Fish Scale Measurement UI - Implementation Phases

Based on `ui-fish-scale-measure-spec-revised.md` with all proposed answers accepted.

## Overview

Three phases designed for:
- Equal testing load per phase
- Manual editing deferred to Phase 3
- Each phase implementable within single context window

---

## Phase 1: Core Infrastructure & Image Handling

**Goal:** Establish application skeleton with image loading, navigation, and calibration.

### 1.1 Flask Application Setup
- Project structure: `src/fish_scale_ui/`
- Flask app factory pattern
- Static file serving (`static/js/`, `static/css/`, `static/help/`)
- Template structure (`templates/`)
- Shared `.venv` with CLI tool

### 1.2 Image Loading Screen
- Dedicated startup screen (per SciPap pattern)
- Drag-and-drop zone for file upload
- Click-to-browse file system dialog
- Recent images list (last 10, stored in `<app_root>/recent_images.json`)
- Supported formats: TIF, TIFF, JPEG, JPG, PNG
- Error handling for corrupt/unsupported files

### 1.3 Main Working View Layout
- Left panel: Main Image display area
- Right panel: Tabbed container (Extraction, Configure, Edit, Data, Log, Settings, About)
- Fixed toolbar below image: "New Image", "Rotate Left", "Rotate Right", "Save SLO"

### 1.4 Image Navigation
- Mouse wheel zoom in/out (can be disabled in Settings)
- Click-and-drag pan
- Scroll bars for large images
- Zoom-to-fit button
- Keyboard: `+`/`-` zoom, `0` reset zoom

### 1.5 Image Rotation
- 90-degree increments (Rotate Left / Rotate Right buttons)
- Server-side rotation with image file overwrite
- Coordinate transformation for any existing overlay data

### 1.6 Calibration System
- Numeric input: scale bar µm and pixels
- Interactive scale bar tool: click two points, enter µm value
- Auto-estimation fallback with warning indicator
- Display current calibration (µm/pixel)

### 1.7 About Tab (Complete)
- Application name and version
- Python version
- Core library versions (scikit-image, scipy, flask, numpy)
- Git commit hash and date

### 1.8 Log Tab (Basic)
- Log display grid (Timestamp, Event Type, Details)
- JSONL file output to `<app_root>/log/`
- Session-based log files (timestamp in filename)
- Events: application start/exit, image loading

### 1.9 Settings Tab
- Enable/disable scroll wheel zoom (for touchpad users)
- Settings persisted to localStorage
- Reset to defaults button
- Placeholder for future settings (overlay grid, etc.)

### 1.10 CLI Parameters
- `--image-dir` / `-d`: Directory to browse for images (default: `test_images`)
- `--port` / `-p`: Port to run server on (default: 5010)
- `--no-browser`: Don't auto-open browser on startup
- `--debug`: Run Flask in debug mode

### 1.11 TIF/TIFF Browser Support
- Automatic conversion of TIF/TIFF to PNG for browser display
- Handles 16-bit grayscale (normalizes to 8-bit)
- Handles various color modes (CMYK, I, etc.)
- Original TIF preserved for processing, PNG used for display

### Phase 1 Testing Checklist
- [x] App startup and shutdown
- [x] Image loading via drag-drop
- [x] Image loading via file browser
- [x] Recent images persistence and display
- [x] All supported image formats load correctly
- [x] TIF/TIFF images display in browser (auto-converted to PNG)
- [x] Error messages for invalid files
- [x] Zoom in/out with mouse wheel
- [x] Pan with click-drag
- [x] Scroll bars functional
- [x] Zoom-to-fit button
- [x] Keyboard zoom shortcuts
- [x] Rotate left/right (verify image file updated)
- [x] Calibration numeric input
- [x] Calibration interactive scale bar tool
- [x] Auto-estimation warning displayed
- [x] About tab displays correct versions
- [x] Log tab displays events
- [x] Log files created in correct location
- [x] Settings tab displays and persists scroll wheel zoom setting
- [x] Disabling scroll wheel zoom works correctly
- [x] CLI `--port` parameter works
- [x] CLI `--image-dir` parameter works
- [x] CLI `--no-browser` parameter works
- [ ] `/api/browse` endpoint returns image directory listing

---

## Phase 2: Extraction Pipeline & Data Persistence

**Goal:** Complete extraction workflow with parameter configuration, data viewing, and file persistence.

### 2.1 Configure Tab (Complete)
**Detection Parameters:**
- `threshold` - slider/input with range
- `min-diameter` / `max-diameter` - numeric inputs (µm)
- `circularity` - slider (0-1)
- `method` - dropdown: log, dog, ellipse, lattice

**Preprocessing Parameters:**
- `clahe-clip` - numeric input
- `clahe-kernel` - numeric input
- `blur-sigma` - numeric input

**Neighbor Graph:**
- `neighbor-graph` - dropdown: delaunay, gabriel, rng

**Profile Presets:**
- Dropdown with all profiles from `profiles.py`
- Loading profile populates all fields

**Help System:**
- Help icon (?) next to each parameter
- Links to `static/help/parameters.html#<param>`
- Single HTML help page with anchor sections
- Wikipedia links for LoG, DoG, CLAHE, Delaunay, Gabriel graph

### 2.2 Extraction Tab (Complete)
- "Extract Tubercles and Connections" button
- Integration with existing `fish-scale-measure` core modules
- Parameter change indicator (visual highlight when params changed since last extraction)
- Confirmation dialog when navigating away with changed params

### 2.3 SLO Overlay Display
- Render TUBs as circles (cyan, 2px stroke)
- Render ITCs as lines (cyan, 2px stroke)
- Overlay scales with zoom
- No selection/editing in this phase (view only)

### 2.4 Data Tab (Complete)
**TUB Table (read-only):**
- Columns: ID, Center X, Center Y, Radius/Diameter, Circularity
- Click row → highlight TUB in image (yellow, 3px)
- Click TUB in image → highlight row in table

**ITC Table (read-only):**
- Columns: ID1, ID2, X1, Y1, X2, Y2, Distance (µm)
- Click row → highlight ITC in image
- Click ITC in image → highlight row in table

**Statistics Panel:**
- Number of Tubercles
- Mean diameter ± std dev (µm)
- Number of Connections
- Mean intertubercular space ± std dev (µm)
- Real-time updates when data changes

### 2.5 Data Persistence
**Save SLO:**
- Always-visible "Save SLO" button
- Output directory: `<app_root>/slo/`
- Files: `<image_name>_tub.csv`, `<image_name>_itc.csv`, `<image_name>_slo.json`
- Overwrite warning if files exist
- Calibration stored in SLO JSON

**Load SLO:**
- Load existing `*_slo.json` to continue editing
- Name mismatch warning (SLO vs current image)
- Restore calibration from loaded SLO

**Unsaved Changes:**
- Track dirty state
- `beforeunload` browser warning
- `Ctrl+S` keyboard shortcut to save

### 2.6 Enhanced Logging
- Extraction runs (parameters, TUB/ITC counts)
- SLO loading (filename, TUB/ITC counts)
- SLO saving (filename, TUB/ITC counts)

### Phase 2 Testing Checklist
- [x] All Configure parameters render and accept input
- [x] Profile dropdown populates fields correctly
- [x] Help icons open help page at correct section
- [x] Parameter change indicator appears/clears appropriately
- [ ] Changed params warning on tab navigation (deferred - not critical)
- [x] Extraction runs and produces overlay
- [x] Overlay renders correctly at various zoom levels
- [x] TUB table displays all tubercle data
- [x] ITC table displays all connection data
- [x] Table row click highlights overlay item
- [x] Overlay click highlights table row
- [x] Statistics display correct values
- [x] Statistics update after re-extraction
- [x] Save SLO creates all three files
- [x] Overwrite warning appears when files exist
- [x] Load SLO restores overlay and calibration
- [x] Name mismatch warning when loading mismatched SLO
- [x] Unsaved changes warning on browser close
- [x] Ctrl+S saves SLO
- [x] Log entries for extraction and save/load

---

## Phase 3: Manual Editing

**Goal:** Complete editing capabilities with undo/redo and all keyboard shortcuts.

### 3.1 Edit Tab UI
- "Add Tubercle" button → enter placement mode
- "Add Connection" button → enter connection mode
- "Move" button → enter move mode
- "Delete" button (or use keyboard)
- Radius adjustment: slider or +/- buttons (percentage-based)
- Checkbox: "Allow Delete without confirmation"
- Undo button (+ Ctrl+Z)
- Redo button (+ Ctrl+Y)

### 3.2 Selection System
- Click TUB/ITC to select
- Tab key cycles through TUB/ITC selection
- Visual feedback: selected = magenta (#FF00FF), 3px stroke
  - Note: Yellow was changed to magenta to avoid conflict with default ITC color (yellow)
- Escape to deselect or cancel current mode
- Overlapping TUBs: select closest center to click point

### 3.2.1 Overlay Toggles + Editing Interaction
- **Auto-enable on edit mode:** When entering Add Tubercle mode, auto-enable Tubes toggle if hidden
- **Auto-enable on edit mode:** When entering Add Connection mode, auto-enable Links toggle if hidden
- **Selection requires visibility:** Cannot select hidden elements (if Tubes hidden, cannot select TUBs)
- **Warning toast:** Show "Tubes enabled for editing" when auto-enabling toggles
- **Toggles remain independent:** User can still manually hide elements during editing (but selection/add will re-enable)

### 3.3 TUB Editing Operations
**Add:**
- Click "Add Tubercle" button
- Click on image to place new TUB
- Default radius (configurable or based on current mean)
- Escape to cancel placement mode

**Delete:**
- Select TUB, press Delete/Backspace or click Delete button
- Confirmation dialog (unless "Allow Delete without confirmation" checked)
- Auto-delete connected ITCs (single undoable operation)

**Move:**
- Select TUB, click "Move" button
- Click destination point
- Connected ITCs update automatically

**Resize:**
- Select TUB
- Use slider or +/- buttons to adjust radius
- Live preview during adjustment

**Nudge:**
- Arrow keys move selected TUB by 1 pixel

### 3.4 ITC Editing Operations
**Add:**
- Click "Add Connection" button
- Click first TUB (highlights)
- Click second TUB (creates connection)
- Escape to cancel

**Delete:**
- Select ITC, press Delete/Backspace or click Delete button
- Confirmation dialog (unless checkbox checked)

### 3.5 Undo/Redo System
- Maximum 100 operations in stack
- Operations tracked:
  - Add TUB
  - Delete TUB (includes auto-deleted ITCs)
  - Move TUB
  - Resize TUB
  - Add ITC
  - Delete ITC
- Undo restores complete previous state
- Redo reapplies undone operation

### 3.6 Keyboard Shortcuts (Complete)
| Key | Action |
|-----|--------|
| `Delete` / `Backspace` | Delete selected TUB/ITC |
| `Escape` | Deselect / cancel current mode |
| `Tab` | Cycle through TUB/ITC selection |
| `Ctrl+Z` | Undo |
| `Ctrl+Y` | Redo |
| `Ctrl+S` | Save SLO |
| `+` / `-` | Zoom in/out |
| `0` | Reset zoom to fit |
| Arrow keys | Nudge selected TUB by 1px |

### 3.7 Rotation with Edits Warning
- Applies to Rotate Left/Right buttons in Image tab
- If unsaved SLO changes exist when rotating:
- Dialog: "You have unsaved overlay changes. Rotating the image will save the rotated image to disk. Do you want to save your overlay first?"
- Options: "Save & Rotate", "Rotate without Saving", "Cancel"

### 3.8 Edit Logging
- Manual TUB additions (with position, radius)
- Manual TUB deletions (with ID)
- Manual ITC additions (with TUB IDs)
- Manual ITC deletions (with TUB IDs)

### Phase 3 Testing Checklist
- [ ] Click to select TUB works
- [ ] Click to select ITC works
- [ ] Tab cycles through selections
- [ ] Selection visual feedback (magenta, thicker) - distinguishable from yellow ITCs
- [ ] Escape deselects
- [ ] Add Tubercle mode and placement
- [ ] Add Connection mode (two-click)
- [ ] Delete TUB with confirmation
- [ ] Delete TUB without confirmation (checkbox)
- [ ] Delete TUB auto-removes connected ITCs
- [ ] Delete ITC with/without confirmation
- [ ] Move TUB updates position and ITCs
- [ ] Resize TUB with slider/buttons
- [ ] Arrow key nudge
- [ ] Undo reverses each operation type
- [ ] Redo reapplies undone operations
- [ ] Undo/redo chain works correctly
- [ ] Undo limit at 100 operations
- [ ] Undo TUB deletion restores TUB + ITCs
- [ ] All keyboard shortcuts functional
- [ ] Overlapping TUBs: closest center selected
- [ ] Rotation warning with unsaved changes (in Image tab)
- [ ] Statistics update after each edit
- [ ] Log entries for all edit operations
- [ ] Table/overlay selection sync during editing
- [ ] Add Tubercle auto-enables Tubes toggle if hidden
- [ ] Add Connection auto-enables Links toggle if hidden
- [ ] Cannot select TUBs when Tubes toggle is off
- [ ] Cannot select ITCs when Links toggle is off
- [ ] Toast notification shown when toggle auto-enabled

---

## Dependencies Between Phases

```
Phase 1 ──────────────────────────────────────────────────────────
    │
    │  Flask app, image handling, calibration, basic tabs
    │
    ▼
Phase 2 ──────────────────────────────────────────────────────────
    │
    │  Extraction integration, overlay display, data tables,
    │  file persistence (requires Phase 1 image/calibration)
    │
    ▼
Phase 3 ──────────────────────────────────────────────────────────

    Manual editing (requires Phase 2 overlay and data structures)
```

---

## Estimated Complexity

| Phase | New Files | Lines of Code (est.) | Primary Challenge |
|-------|-----------|---------------------|-------------------|
| 1 | ~8-10 | ~1500-2000 | Image handling, zoom/pan, calibration tool |
| 2 | ~5-7 | ~1500-2000 | Core integration, help system, file formats |
| 3 | ~3-5 | ~1200-1500 | Undo/redo architecture, edit modes |

---

## File Structure After All Phases

```
src/fish_scale_ui/
├── __init__.py
├── app.py                 # Flask app factory
├── routes/
│   ├── __init__.py
│   ├── main.py           # Main routes (index, image loading)
│   ├── api.py            # API routes (extraction, save/load)
│   └── files.py          # File handling routes
├── services/
│   ├── __init__.py
│   ├── extraction.py     # Wrapper around CLI extraction
│   ├── persistence.py    # SLO save/load
│   └── logging.py        # JSONL logging
├── static/
│   ├── css/
│   │   └── main.css
│   ├── js/
│   │   ├── main.js       # App initialization
│   │   ├── settings.js   # Settings management (localStorage)
│   │   ├── image.js      # Image display, zoom, pan
│   │   ├── overlay.js    # TUB/ITC rendering (Phase 2)
│   │   ├── calibration.js
│   │   ├── configure.js  # Parameter controls (Phase 2)
│   │   ├── data.js       # Data tables (Phase 2)
│   │   ├── editor.js     # Edit operations (Phase 3)
│   │   └── undo.js       # Undo/redo stack (Phase 3)
│   └── help/
│       └── parameters.html
├── templates/
│   ├── base.html
│   ├── index.html        # Image loading screen
│   └── workspace.html    # Main working view
log/                       # JSONL log files
slo/                       # Output files
```

---

## Implementation Status

### Phase 1: COMPLETED (2025-12-14)

All Phase 1 components have been implemented:

**Files Created:**
- `src/fish_scale_ui/__init__.py` - Package initialization
- `src/fish_scale_ui/app.py` - Flask app factory with IMAGE_DIR config
- `src/fish_scale_ui/run.py` - Entry point with CLI argument parsing
- `src/fish_scale_ui/routes/__init__.py`
- `src/fish_scale_ui/routes/main.py` - Main page routes
- `src/fish_scale_ui/routes/api.py` - API endpoints (image, calibration, browse)
- `src/fish_scale_ui/services/__init__.py`
- `src/fish_scale_ui/services/logging.py` - JSONL logging service
- `src/fish_scale_ui/services/recent_images.py` - Recent images management
- `src/fish_scale_ui/templates/base.html` - Base template
- `src/fish_scale_ui/templates/index.html` - Image loading screen
- `src/fish_scale_ui/templates/workspace.html` - Main workspace view with Settings tab
- `src/fish_scale_ui/static/css/main.css` - Styles (includes settings tab styles)
- `src/fish_scale_ui/static/js/main.js` - App initialization, tabs, toasts
- `src/fish_scale_ui/static/js/settings.js` - Settings management (localStorage)
- `src/fish_scale_ui/static/js/image.js` - Image viewer, zoom, pan (respects settings)
- `src/fish_scale_ui/static/js/calibration.js` - Calibration system

**Features Implemented:**
- [x] Flask app factory pattern
- [x] CLI parameters (`--image-dir`, `--port`, `--no-browser`, `--debug`)
- [x] Image loading screen with drag-and-drop
- [x] Click-to-browse file upload
- [x] Recent images list (persisted to JSON)
- [x] Supported formats: TIF, TIFF, JPEG, JPG, PNG
- [x] TIF/TIFF to PNG conversion for browser display (handles 16-bit, various modes)
- [x] Error handling for invalid files
- [x] Main workspace layout (left image panel, right tabs panel)
- [x] Tab navigation (Extraction, Configure, Edit, Data, Log, Settings, About)
- [x] Image toolbar (New Image, Rotate, Zoom, Save SLO)
- [x] Mouse wheel zoom (can be disabled in Settings)
- [x] Click-and-drag pan
- [x] Zoom-to-fit button
- [x] Keyboard shortcuts (+/- zoom, 0 reset)
- [x] Image rotation (90-degree increments)
- [x] Calibration numeric input (scale bar)
- [x] Calibration interactive scale bar tool
- [x] Auto-estimation warning display
- [x] Settings tab with scroll wheel zoom toggle
- [x] Settings persistence to localStorage
- [x] About tab with version info
- [x] Log tab with event display
- [x] JSONL log file output
- [x] `/api/browse` endpoint for image directory listing

**To Run:**
```bash
# Default (test_images on port 5010)
uv run fish-scale-ui

# Custom image directory and port
uv run fish-scale-ui -d /path/to/images -p 8080

# Without auto-opening browser
uv run fish-scale-ui --no-browser
```

### Phase 2a: UI Reorganization & Enhanced Features (2025-12-15)

**Goal:** Reorganize tabs for better workflow, add image editing capabilities, and enhance calibration display options.

#### 2a.1 Tab Reorganization
- Image tab becomes first tab (replaces toolbar for image operations)
- Calibration tab becomes second tab (moved from bottom panel)
- Tab order: Image, Calibration, Extraction, Configure, Edit, Data, Log, Settings, About

#### 2a.2 Image Tab (NEW - First Tab)
- **Rotate Controls:**
  - Rotate Left button (90° counter-clockwise)
  - Rotate Right button (90° clockwise)
  - Server-side rotation with file overwrite
- **Crop Function:**
  - "Crop" button to enter crop mode
  - Click-to-click interaction: click first corner, then click second corner (NOT drag)
  - Crosshair cursor in crop mode
  - Preview crop area with semi-transparent overlay on excluded regions
  - Confirm/Cancel buttons appear after second click
  - Press Escape or Cancel to exit crop mode
  - Server-side crop with file overwrite
- **Autocrop Function:**
  - "Autocrop" button to automatically remove empty/uniform border regions
  - Detects edges based on pixel variance threshold
  - Server-side autocrop with file overwrite
- **Save Button:**
  - "Save SLO" button moved from toolbar to Image tab
  - Shows unsaved indicator when changes exist

#### 2a.3 Calibration Tab (NEW - Second Tab)
- **Calibration Display:**
  - Current calibration value (µm/pixel)
  - Auto-estimated warning badge
- **Section Headers:** (larger font to stand out, grouped by method type)
  - **Numerical Scale Specification**
    - Scale bar measurement: µm and pixels inputs with Apply button
    - Direct input: µm/pixel value with Apply button
  - **Graphical Scale Specification**
    - "Manually Draw Scale Bar" button to interactively draw on image
  - **Automatic Scale Specification**
    - Apply Estimate button (~0.14 µm/px for 700x magnification)

#### 2a.3.1 Overlay Toggle Controls (Under Image)
- **Location:** Below the image toolbar, always visible
- **Purpose:** Quick toggles for overlay visibility (independent from Settings defaults)
- **Checkboxes:**
  - Numbers - Show/hide tubercle ID numbers
  - Tubes - Show/hide tubercle circles
  - Links - Show/hide connection lines (ITC)
  - Scale - Show/hide calibration scale bar
- **Behavior:**
  - These toggles only affect current session display
  - Do NOT modify Settings defaults (Settings controls initial state on load)
  - State resets to Settings defaults when loading new image

#### 2a.4 Toolbar Simplification
- Remove Rotate buttons from toolbar (moved to Image tab)
- Remove Save SLO button from toolbar (moved to Image tab)
- Keep: New Image, Zoom controls, Zoom level display

#### 2a.5 Zoom and Panel Behavior
- **Zoom to Fit:** Should scale image to fill available space (both up and down)
  - Remove 1x zoom cap to allow small images to scale up
  - Apply 95% margin for visual comfort
- **Panel Resizing:** Allow tabs panel to expand up to 80% of viewport width
  - Remove hard-coded 600px max-width constraint
  - Dynamic max-width based on viewport size

#### 2a.6 Calibration Scale Display (Settings Tab)
- **Show Calibration Scale:** Checkbox to enable/disable
- **Scale Position:** Dropdown with 8 options:
  - Top-Left, Top-Center, Top-Right
  - Middle-Left, Middle-Right
  - Bottom-Left, Bottom-Center, Bottom-Right
- **Scale Appearance:**
  - Labeled bar showing distance in µm
  - Contrasting color for visibility
  - Scales with zoom level

#### Phase 2a Testing Checklist
- [ ] Image tab is first tab in tab order
- [ ] Rotate Left/Right buttons work in Image tab
- [ ] Crop button enters crop mode with crosshair cursor
- [ ] First click sets first corner of crop region
- [ ] Second click sets second corner and shows preview
- [ ] Crop preview shows selected area with darkened excluded regions
- [ ] Crop confirm applies crop to image
- [ ] Crop cancel or Escape exits without changes
- [ ] Autocrop button removes empty borders
- [ ] Zoom to Fit scales small images up to fill available space
- [ ] Zoom to Fit works after autocrop
- [ ] Panel resizer allows expanding tabs panel beyond 600px
- [ ] Save SLO button works in Image tab
- [ ] Calibration tab is second tab
- [ ] Calibration tab has three section headers (Numerical, Graphical, Automatic)
- [ ] Section headers have larger font than regular headers
- [ ] All calibration methods work in Calibration tab
- [ ] "Manually Draw Scale Bar" button text updated
- [ ] Apply button for auto-estimate works
- [ ] Overlay toggle checkboxes appear below image toolbar
- [ ] Numbers toggle shows/hides tubercle IDs
- [ ] Tubes toggle shows/hides tubercle circles
- [ ] Links toggle shows/hides connection lines
- [ ] Scale toggle shows/hides calibration scale
- [ ] Overlay toggles do NOT modify Settings defaults
- [ ] Toolbar no longer has rotate/save buttons
- [ ] Calibration scale checkbox toggles scale display
- [ ] All 8 scale positions work correctly
- [ ] Scale shows correct measurement label
- [ ] Scale remains readable at different zoom levels

#### Phase 2a Implementation Status: COMPLETED (2025-12-15)

**Files Modified:**
- `src/fish_scale_ui/templates/workspace.html` - Added Image/Calibration tabs, reorganized tab order, Autocrop button
- `src/fish_scale_ui/routes/api.py` - Added `/api/crop` and `/api/autocrop` endpoints
- `src/fish_scale_ui/static/js/main.js` - Updated toolbar buttons, added Image tab rotate buttons
- `src/fish_scale_ui/static/js/image.js` - Added crop (click-to-click), autocrop, fixed zoomToFit for small images
- `src/fish_scale_ui/static/js/calibration.js` - Added Apply Estimate button handler
- `src/fish_scale_ui/static/js/settings.js` - Added calibration scale settings, increased panel max-width to 80vw
- `src/fish_scale_ui/static/js/overlay.js` - Added calibration scale rendering
- `src/fish_scale_ui/static/js/extraction.js` - Updated dirty indicator for Image tab
- `src/fish_scale_ui/static/css/main.css` - Added Phase 2a styles, increased tabs-panel max-width to 80vw

---

### Phase 2: COMPLETED (2025-12-15)

All Phase 2 components have been implemented:

**Files Created:**
- `src/fish_scale_ui/services/extraction.py` - Extraction wrapper around CLI core modules
- `src/fish_scale_ui/services/persistence.py` - SLO save/load functionality
- `src/fish_scale_ui/static/js/configure.js` - Configure tab parameter management
- `src/fish_scale_ui/static/js/extraction.js` - Extraction tab logic, save/load SLO
- `src/fish_scale_ui/static/js/overlay.js` - Canvas overlay rendering for TUBs/ITCs
- `src/fish_scale_ui/static/js/data.js` - Data tab tables and statistics
- `src/fish_scale_ui/static/help/parameters.html` - Parameter help documentation

**Files Updated:**
- `src/fish_scale_ui/routes/api.py` - Added extraction, profiles, SLO endpoints
- `src/fish_scale_ui/templates/workspace.html` - Complete Configure, Extraction, Data tabs
- `src/fish_scale_ui/static/css/main.css` - Phase 2 styles
- `src/fish_scale_ui/static/js/main.js` - Removed placeholder warnings
- `src/fish_scale_ui/static/js/image.js` - Added imageLoaded event
- `src/fish_scale_ui/static/js/calibration.js` - Added setCalibration method

**Features Implemented:**
- [x] Configure Tab with all detection/preprocessing parameters
- [x] Profile presets dropdown loading from profiles.py
- [x] Help icons linking to parameter documentation
- [x] Parameter change indicator
- [x] Extraction button with spinner
- [x] Integration with fish_scale_analysis core modules
- [x] Overlay rendering (TUBs as circles, ITCs as lines)
- [x] Click-to-select on overlay
- [x] TUB table with ID, X, Y, Diameter, Circularity
- [x] ITC table with ID1, ID2, Center Distance, Edge Distance
- [x] Statistics panel with mean/std values
- [x] Table row click highlights overlay item
- [x] Overlay click highlights table row
- [x] Save SLO (creates _tub.csv, _itc.csv, _slo.json)
- [x] Load SLO with name mismatch warning
- [x] Unsaved changes tracking with dirty indicator
- [x] beforeunload warning for unsaved changes
- [x] Ctrl+S keyboard shortcut for save
- [x] Enhanced logging for extraction/save/load events

**Phase 2.1 UI Improvements (2025-12-15):**
- [x] Toast notifications with colored backgrounds (beige for info, pink for errors)
- [x] Horizontally resizable panels (drag to resize image vs tabs panel)
- [x] Renamed "Connections" to "Intertubercular Connections" in Data tab
- [x] Overlay display settings:
  - Show/hide tubercle IDs as text
  - ID text size scaling
  - Tubercle color picker
  - Connection color picker
  - Connection endpoint mode (center or edge)
- [x] Collapsible settings sections by topic

### Phase 3: COMPLETED (2025-12-15)

All Phase 3 components have been implemented:

**Files Created:**
- `src/fish_scale_ui/static/js/undo.js` - Undo/redo system with 100 operation stack
- `src/fish_scale_ui/static/js/editor.js` - Edit mode management and operations

**Files Updated:**
- `src/fish_scale_ui/templates/workspace.html` - Edit tab UI with buttons and controls
- `src/fish_scale_ui/static/js/overlay.js` - Selection handling, edit mode click routing
- `src/fish_scale_ui/static/js/main.js` - Keyboard shortcuts for editing
- `src/fish_scale_ui/static/js/extraction.js` - Data modification events, rotation warning
- `src/fish_scale_ui/static/css/main.css` - Edit tab styles
- `src/fish_scale_ui/routes/api.py` - Log POST endpoint, save-slo with editor data

**Features Implemented:**
- [x] Edit Tab UI with Add Tubercle, Add Connection, Move, Delete buttons
- [x] Radius adjustment slider and +/- buttons
- [x] Undo/Redo buttons with stack (max 100 operations)
- [x] "Allow delete without confirmation" checkbox
- [x] Selection system (click to select TUB/ITC)
- [x] Tab key cycles through selections
- [x] Visual feedback: selected = magenta (#FF00FF), 3px stroke
- [x] Escape to deselect or cancel current mode
- [x] Overlapping TUBs: closest center selected
- [x] Auto-enable Tubes toggle when entering Add Tubercle mode
- [x] Auto-enable Links toggle when entering Add Connection mode
- [x] Cannot select hidden elements (respects toggle visibility)
- [x] Warning toast when toggle auto-enabled
- [x] Add Tubercle: click to place with default radius
- [x] Add Connection: two-click to select tubercles
- [x] Delete TUB with confirmation dialog
- [x] Delete TUB auto-removes connected ITCs
- [x] Move TUB: select, click Move, click destination
- [x] Resize TUB with slider or +/- buttons
- [x] Nudge: Arrow keys move selected TUB by 1px
- [x] Undo reverses all operation types
- [x] Redo reapplies undone operations
- [x] Keyboard shortcuts: Delete, Escape, Tab, Ctrl+Z, Ctrl+Y, Arrow keys
- [x] Rotation warning with unsaved changes (Save & Rotate, Rotate without Saving, Cancel)
- [x] Statistics update after each edit
- [x] Log entries for edit operations
- [x] Table/overlay selection sync during editing
