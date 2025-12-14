# Fish Scale Measurement UI - Revised Specification

A graphical user interface for measuring tubercle diameter and intertubercular space from SEM images of ganoid fish scales, with support for both automated extraction and manual editing.

## 1. Background

### 1.1 Context
- This application builds on `fish-scale-measure`, a Python CLI tool for extracting tubercle metrics from SEM (Scanning Electron Microscope) images of ganoid fish scales.
- It shares a project folder and codebase with the CLI tool.
- Background information can be found in `README.md`, the `docs/` subfolder, and the `specs/` subfolder.
- Reference image: `test_images/extraction_methodology.png` illustrates the measurement methodology.
- The automated extraction algorithm produces helpful but not always adequate results, necessitating human editing capabilities.
- UI design is inspired by "SciPap" (see `specs/scipap.jpg` and `specs/scipap_imageloading.png`), a Python Flask app with a multi-tabbed interface.

### 1.2 Purpose
Measure two key taxonomic metrics from fish scale images:
1. **Tubercle Diameter (µm)** - The diameter of microscopic tubercles on the ganoine surface
2. **Intertubercular Space (µm)** - The edge-to-edge distance between adjacent tubercles

These measurements help identify fish families, genera, and sometimes species within Lepisosteidae, Polypteridae, and Semionotidae.

### 1.3 Audience
- Primarily paleontologists researching fish fossils

---

## 2. Terminology

| Abbreviation | Full Name | Description |
|--------------|-----------|-------------|
| **MI** | Main Image | The image currently being viewed and edited |
| **SLO** | Scales and Links Overlay | The complete set of detected/edited TUB and ITC overlaid on the image |
| **TUB** | Tubercle | A single detected tubercle, displayed as a circle showing location and extent |
| **ITC** | Intertubercular Connection | A link between two neighboring tubercles, displayed as a line |

In the UI, use the full names "Tubercles" and "Intertubercular Connections" where space permits.

---

## 3. Application Layout

### 3.1 Overall Structure
- **Left panel**: Main Image (MI) display area with navigation controls
- **Right panel**: Tabbed interface for various operations
- **Always-visible button**: "Save SLO" button (can be placed on left or right side)

### 3.2 Image Loading Screen
At application startup and when loading a new image, display a dedicated image selection screen (similar to SciPap's upload screen in `specs/scipap_imageloading.png`):
- Drag-and-drop zone for file upload
- Click to browse file system
- List of recently opened images
- Supported formats: TIF, TIFF, JPEG, JPG, PNG

### 3.3 Main Working View
Once an image is loaded:
- **Left side**: Main Image with SLO overlay
  - Rotate Left / Rotate Right buttons (90-degree increments)
  - "New Image" button to return to image loading screen
  - Zoom controls and scroll bars
- **Right side**: Tabbed container with the following tabs:
  - Extraction
  - Configure
  - Edit
  - Data
  - Log
  - About

---

## 4. Image Navigation

### 4.1 Zoom and Pan
- **Mouse wheel**: Zoom in/out
- **Click and drag**: Pan the image
- **Scroll bars**: Navigate large images
- **Zoom-to-fit button**: Reset view to fit entire image

### 4.2 Image Rotation
- **Granularity**: 90-degree increments only (0°, 90°, 180°, 270°)
- **Controls**: "Rotate Left" and "Rotate Right" buttons below the main image
- **Coordinate transformation**: When rotated, all TUB and ITC coordinates are transformed to match
- **Save behavior**: Rotation can be saved to the original image file (overwrites original - this is acceptable as rotation is reversible)

---

## 5. Calibration

### 5.1 Calibration Methods
The UI supports two calibration methods:

1. **Numeric Input**: Enter scale bar values directly
   - Scale bar length in µm
   - Scale bar length in pixels

2. **Interactive Scale Bar Tool**: Draw on the image
   - Click two points on a known scale bar in the image
   - Enter the distance in µm
   - System calculates pixels automatically

3. **Auto-estimation**: If no calibration provided, estimate based on 700× magnification (with warning)

### 5.2 Calibration Display
- Current calibration (µm/pixel) should be displayed in the UI
- Warning indicator when using auto-estimated calibration

---

## 6. Tabs

### 6.1 Extraction Tab
Primary tab for running automated tubercle detection.

**Controls:**
- **"Extract Tubercles and Connections" button**: Runs extraction algorithm
  - Discards current SLO and generates new TUB and ITC based on current parameters
  - Only visible/active when this tab is selected
- **Parameter status indicator**: Visual highlight when parameters have been changed since last extraction
- **Warning**: If navigating away from changed parameters without extracting, display confirmation dialog

### 6.2 Configure Tab
Set all extraction parameters. All CLI parameters should be exposed:

**Detection Parameters:**
- `threshold` - Blob detection threshold (lower = more sensitive)
- `min-diameter` - Minimum expected tubercle diameter in µm
- `max-diameter` - Maximum expected tubercle diameter in µm
- `circularity` - Minimum circularity filter (0-1)
- `method` - Detection method dropdown: log, dog, ellipse, lattice

**Preprocessing Parameters:**
- `clahe-clip` - CLAHE clip limit for contrast enhancement
- `clahe-kernel` - CLAHE kernel size
- `blur-sigma` - Gaussian blur sigma for noise reduction

**Neighbor Graph:**
- `neighbor-graph` - Graph type dropdown: delaunay, gabriel, rng

**Profile Presets:**
- Dropdown to select predefined parameter profiles (e.g., paralepidosteus, polypterus, scanned-pdf)
- Loading a profile populates all parameter fields

**Help System:**
- Each parameter input widget has a help icon (?)
- Clicking the help icon opens a static HTML help page
- The help page scrolls to the section for that specific parameter
- Help page is located in the source code directory and is editable
- Include links to relevant Wikipedia pages where appropriate

### 6.3 Edit Tab
Manual editing of TUB and ITC overlays.

**Selection:**
- **Click**: Select a TUB or ITC by clicking directly on it
- **Tab key**: Cycle through TUB/ITC selection
- **Visual feedback**: Selected items shown in different color with thicker lines
- No marquee/multi-select

**TUB Editing:**
- **Add**: Click "Add Tubercle" button, then click on image location to place new TUB
- **Delete**: Delete selected TUB (confirmation dialog unless "Allow Delete without confirmation" is checked)
- **Move**: Click "Move" button, then click destination point to relocate selected TUB
- **Change Radius**: Slider or +/- buttons to increase/decrease radius by configurable percentage

**ITC Editing:**
- **Add**: Click "Add Connection" button, then click two TUBs sequentially to create connection
- **Delete**: Delete selected ITC (confirmation dialog unless "Allow Delete without confirmation" is checked)

**Editing Options:**
- Checkbox: "Allow Delete without confirmation"

**Undo/Redo:**
- Undo button (Ctrl+Z)
- Redo button (Ctrl+Y)
- Maintains edit history for the current session

### 6.4 Data Tab
View numerical data for all TUB and ITC.

**TUB Table (read-only):**
- ID, Center X, Center Y, Radius/Diameter, Circularity
- Click row to highlight corresponding TUB in image
- Clicking TUB in image highlights corresponding row

**ITC Table (read-only):**
- ID1, ID2, X1, Y1, X2, Y2, Distance (µm)
- Click row to highlight corresponding ITC in image
- Clicking ITC in image highlights corresponding row

**Statistics Panel:**
- Number of Tubercles
- Mean diameter ± std dev (µm)
- Number of Connections
- Mean intertubercular space ± std dev (µm)
- Note: Genus classification not included for now

**Real-time Updates:**
- Statistics update immediately when TUB/ITC are added, deleted, or modified
- Lightweight calculations only (no re-extraction)

### 6.5 Log Tab
View application event log.

**Display:**
- Log entries shown in a scrollable grid/table
- Columns: Timestamp, Event Type, Details

**Logged Events:**
- Application start and exit
- Image loading (with filename)
- SLO loading (with filename, TUB count, ITC count)
- SLO saving (with filename, TUB count, ITC count)
- Extraction runs (with parameter summary, resulting TUB/ITC counts)
- Manual TUB additions/deletions
- Manual ITC additions/deletions

**Log File:**
- Format: JSONL (JSON Lines) for compatibility with lnav
- Location: `log/` directory
- Filename: Timestamp accurate to the second (e.g., `2025-01-15_143052.jsonl`)
- New log file created for each application session

### 6.6 About Tab
Application information.

**Display:**
- Application name and version
- Python version
- Core library versions (scikit-image, scipy, flask, numpy)
- Git commit hash
- Git commit date (used as build date)
- Author/contact email

---

## 7. Data Persistence

### 7.1 Real-time Sync
- All TUB/ITC edits sync immediately to the server (in-memory state)
- Statistics recalculate immediately on changes
- **No auto-save to files** - explicit save action required

### 7.2 File Naming Convention
For an image named `example.tif`:
- `example_tub.csv` - Tubercle data
- `example_itc.csv` - Intertubercular connection data
- `example_slo.json` - Complete SLO with metadata

### 7.3 Output Directory
- All output files saved to a dedicated `slo/` directory
- Directory created if it doesn't exist

### 7.4 Save Workflow
- "Save SLO" button always visible in the interface
- **Overwrite warning**: If output files already exist, prompt user before overwriting
- **Name mismatch warning**: If loading an SLO file with a different base name than the current image, warn user and save to new file matching current image name

### 7.5 Loading Existing Work
- User can load an image and then load a matching SLO file to continue editing
- SLO files store all TUB and ITC data plus metadata

---

## 8. File Formats

### 8.1 TUB CSV (`*_tub.csv`)
Columns:
- `image_filename` - Source image name
- `shape` - "circle" or "ellipse"
- `center_x` - X coordinate of center (pixels)
- `center_y` - Y coordinate of center (pixels)
- `radius` - Circle radius (pixels), or 0 for ellipse
- `major_axis` - Ellipse major axis (pixels), or 0 for circle
- `minor_axis` - Ellipse minor axis (pixels), or 0 for circle
- `orientation` - Ellipse orientation (radians), or 0 for circle

### 8.2 ITC CSV (`*_itc.csv`)
Columns:
- `image_filename` - Source image name
- `id1` - First tubercle ID
- `x1` - First tubercle center X (pixels)
- `y1` - First tubercle center Y (pixels)
- `id2` - Second tubercle ID
- `x2` - Second tubercle center X (pixels)
- `y2` - Second tubercle center Y (pixels)

### 8.3 SLO JSON (`*_slo.json`)
Structure:
```json
{
  "metadata": {
    "image_filename": "example.tif",
    "creation_datetime": "2025-01-15T14:30:52",
    "calibration_um_per_px": 0.137,
    "extraction_parameters": { ... }
  },
  "tubercles": [ ... ],
  "connections": [ ... ]
}
```

---

## 9. Error Handling

### 9.1 Image Loading Failures
- Display clear error message to user for corrupt or unsupported files
- Log error details to the session log

### 9.2 Zero Detections
- If extraction finds zero tubercles, this is a valid (though unwanted) result
- Display informational message
- User can manually add tubercles via Edit tab

### 9.3 Large Images
- No special handling required for now
- Defer performance optimization until it becomes a problem

---

## 10. Technology & Implementation

### 10.1 Stack
- **Backend**: Python Flask
- **Frontend**: Vanilla JavaScript (no framework)
- **Package management**: uv package manager with shared `.venv`

### 10.2 Code Reuse
- Reuse extraction algorithms from `fish-scale-measure` CLI
- Shared models and core processing code

### 10.3 Image Handling
- Server-side image processing
- Defer optimization for large images until needed

---

## 11. Sample Files

Two sets of sample images available for testing:
- `images/` - 3 full-sized, high-resolution, recently scanned SEM images
- `test_images/` - ~13 smaller, older images extracted from research papers (some from 1980s)

---

## 12. Future Considerations

- AI-powered editing suggestions and automatic adjustment
- Batch processing support
- Side-by-side image comparison
- Genus classification display

---

## 13. Remaining Open Questions

### 13.1 UI/UX Details

1. **Selection color scheme**: What specific colors should be used for selected vs. unselected TUB/ITC? Need to ensure good contrast against grayscale SEM images.
   - PROPOSED: Unselected TUB/ITC = **cyan** (#00FFFF) with 2px line weight. Selected = **yellow** (#FFFF00) with 3px line weight. Both colors provide strong contrast against grayscale SEM images and are distinguishable from each other.
   - MW - ok

2. **"Save SLO" button placement**: Spec allows left or right - which is preferred? Should it be in a fixed toolbar or floating?
   - PROPOSED: Fixed toolbar below the main image on the **left side**, containing: "New Image", "Rotate Left", "Rotate Right", "Save SLO". This keeps image-related actions together and visible regardless of which tab is active.
   - MW - ok

3. **Confirmation dialogs**: Should deletion confirmations be modal dialogs, toast notifications, or inline confirmations?
   - PROPOSED: **Modal dialogs** for destructive actions (deletion confirmations, overwrite warnings, unsaved changes warnings). **Toast notifications** (auto-dismissing, bottom-right) for success confirmations (e.g., "SLO saved successfully").
   - MW - ok

4. **Tab order**: What is the preferred order of tabs? (Currently: Extraction, Configure, Edit, Data, Log, About)
   - PROPOSED: Keep current order. It follows a logical workflow: Configure parameters → Extract → Edit results → View Data. Log and About are utility tabs that belong at the end.
   - MW - ok

5. **Keyboard shortcuts**: Beyond Tab for cycling and Ctrl+Z/Y for undo/redo, what other shortcuts are needed? (e.g., Delete key for deletion, Escape to deselect)
   - PROPOSED:
     - `Delete` or `Backspace` - Delete selected TUB/ITC (respects "Allow Delete without confirmation" setting)
     - `Escape` - Deselect current selection, or cancel current operation (e.g., cancel "Add Tubercle" mode)
     - `Ctrl+S` - Save SLO
     - `+` / `-` - Zoom in/out
     - `0` - Reset zoom to fit
     - Arrow keys - Nudge selected TUB by 1 pixel in that direction
   - MW - ok

### 13.2 Technical Details

6. **SLO directory location**: Should `slo/` be relative to the image directory, relative to the application, or user-configurable?
   - PROPOSED: **Relative to the application root** (i.e., `<app_root>/slo/`). This keeps all output together and avoids permission issues with image directories that may be read-only or on network drives.
   - MW - ok

7. **Log directory location**: Should `log/` follow the same convention as `slo/`?
   - PROPOSED: Yes, **relative to the application root** (i.e., `<app_root>/log/`). Logs are application-level, not image-level, so they belong with the application.
   - MW - ok

8. **Session state**: If the user closes the browser/app with unsaved changes, should there be a warning? Should auto-recovery be implemented?
   - PROPOSED: **Yes, warn on close** with unsaved changes using the browser's `beforeunload` event ("You have unsaved changes. Are you sure you want to leave?"). **No auto-recovery** for v1 - adds complexity and users can explicitly save.
   - MW - ok

9. **Calibration persistence**: Should calibration be stored per-image (in SLO) and remembered when reopening?
   - PROPOSED: **Yes**, store calibration in the SLO JSON file. When loading an existing SLO, restore the saved calibration. This is critical data that users shouldn't have to re-enter.
   - MW - ok

10. **Recently opened images**: How many to store? Where to persist this list (localStorage, server-side)?
    - PROPOSED: Store **last 10 images**. Use **server-side** storage (simple JSON file at `<app_root>/recent_images.json`). This persists across browsers and is simpler than coordinating localStorage.
   - MW - ok

### 13.3 Help System

11. **Help page format**: Single HTML file with anchor links, or separate pages per parameter?
    - PROPOSED: **Single HTML file with anchor links**. Easier to maintain, loads once, allows users to scroll and read related parameters. Each parameter section has an `id` attribute for direct linking (e.g., `parameters.html#threshold`).
   - MW - ok

12. **Help page location**: `docs/parameter_help.html` or `static/help.html` or elsewhere?
    - PROPOSED: `static/help/parameters.html` - follows Flask conventions for static files, and the `help/` subdirectory allows for future expansion (e.g., `help/tutorial.html`, `help/faq.html`).
   - MW - ok

13. **Wikipedia links**: Which specific pages? Should links be validated/maintained?
    - PROPOSED: Include links to these relevant pages:
      - [Laplacian of Gaussian](https://en.wikipedia.org/wiki/Blob_detection#The_Laplacian_of_Gaussian) (for LoG method)
      - [Difference of Gaussians](https://en.wikipedia.org/wiki/Difference_of_Gaussians) (for DoG method)
      - [Adaptive histogram equalization](https://en.wikipedia.org/wiki/Adaptive_histogram_equalization) (for CLAHE)
      - [Delaunay triangulation](https://en.wikipedia.org/wiki/Delaunay_triangulation)
      - [Gabriel graph](https://en.wikipedia.org/wiki/Gabriel_graph)
    - Links should be validated at release time but don't need ongoing maintenance (Wikipedia URLs are stable).
   - MW - ok

### 13.4 Edge Cases

14. **Overlapping TUBs**: When clicking to select, what happens if two tubercles overlap at the click point?
    - PROPOSED: Select the TUB whose **center is closest** to the click point. This is intuitive and predictable. If user wants the other one, they can Tab to cycle through nearby TUBs.
   - MW - ok

15. **ITC without TUBs**: What happens to ITCs if one of their connected TUBs is deleted? Auto-delete the ITC?
    - PROPOSED: **Auto-delete the ITC**. An ITC without both endpoints is meaningless. This should be a single undoable operation (i.e., undoing the TUB deletion restores both the TUB and its connected ITCs).
   - MW - ok

16. **Maximum undo history**: How many operations to keep in undo stack? Memory considerations?
    - PROPOSED: **100 operations**. Each operation is lightweight (just storing coordinates and IDs), so memory is not a concern. 100 is generous enough that users won't hit the limit in normal use.
   - MW - ok

17. **Rotation with unsaved changes**: If user rotates image with unsaved SLO edits, should there be a warning before rotation (since image save is destructive)?
    - PROPOSED: **Yes, warn before rotation** if there are unsaved SLO changes. Message: "You have unsaved overlay changes. Rotating the image will save the rotated image to disk. Do you want to save your overlay first?" with options: "Save & Rotate", "Rotate without Saving", "Cancel".
   - MW - ok
