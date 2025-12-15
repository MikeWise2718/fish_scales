# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fish Scale Metrics Extraction - A Python toolset for extracting tubercle diameter and intertubercular space measurements from SEM (Scanning Electron Microscope) images of ganoid fish scales. These measurements differentiate between fish families/genera (Lepisosteidae, Polypteridae, Semionotidae) based on methodology from Gayet & Meunier (1986, 1993) and Brito et al. (2000).

**Two interfaces are available:**
1. **CLI Tool** (`fish-scale-measure`) - Command-line processing for single images or batches
2. **Web UI** (`fish-scale-ui`) - Flask-based graphical interface with manual editing capabilities

## Development Commands

```bash
# Setup (using uv package manager)
uv venv
uv pip install -e ".[dev]"

# Run tests
uv run pytest                           # All tests
uv run pytest tests/test_detection.py   # Single test file
uv run pytest -k "test_name"            # Single test by name
uv run pytest --cov=fish_scale_analysis # With coverage

# CLI usage
uv run fish-scale-measure process <image>      # Process single image
uv run fish-scale-measure process ref          # Use test image alias
uv run fish-scale-measure batch <directory>    # Process multiple images
uv run fish-scale-measure benchmark            # Validate against known test values

# Web UI usage
uv run fish-scale-ui                           # Start with defaults (port 5010)
uv run fish-scale-ui -d /path/to/images        # Custom image directory
uv run fish-scale-ui -p 8080                   # Custom port
uv run fish-scale-ui --no-browser              # Don't auto-open browser
uv run fish-scale-ui --debug                   # Flask debug mode
```

## Project Structure

```
fish_scales/
├── src/
│   ├── fish_scale_analysis/           # Core analysis library + CLI
│   │   ├── cli.py                     # CLI entry point
│   │   ├── models.py                  # Data classes (Tubercle, MeasurementResult, etc.)
│   │   ├── profiles.py                # Parameter presets for different species/images
│   │   ├── core/
│   │   │   ├── calibration.py         # Scale bar detection, µm/pixel calculation
│   │   │   ├── preprocessing.py       # CLAHE enhancement, Gaussian blur
│   │   │   ├── detection.py           # Blob detection (LoG/DoG/ellipse/lattice)
│   │   │   ├── measurement.py         # Delaunay/Gabriel/RNG triangulation, spacing
│   │   │   └── lattice.py             # Hexagonal lattice-aware detection
│   │   └── output/
│   │       ├── csv_writer.py          # CSV output
│   │       ├── visualization.py       # Matplotlib figure generation
│   │       └── logger.py              # Timestamped text logging
│   │
│   └── fish_scale_ui/                 # Flask Web UI
│       ├── app.py                     # Flask app factory
│       ├── run.py                     # Entry point with CLI args
│       ├── routes/
│       │   ├── main.py                # Page routes
│       │   └── api.py                 # API endpoints (extraction, save/load, etc.)
│       ├── services/
│       │   ├── extraction.py          # Wrapper around CLI extraction
│       │   ├── persistence.py         # SLO save/load
│       │   ├── logging.py             # JSONL logging
│       │   └── recent_images.py       # Recent images management
│       ├── templates/                 # Jinja2 templates
│       └── static/
│           ├── css/main.css
│           ├── js/                    # JavaScript modules
│           │   ├── main.js            # App initialization, tabs
│           │   ├── image.js           # Zoom, pan, crop, rotate
│           │   ├── overlay.js         # TUB/ITC rendering, selection
│           │   ├── calibration.js     # Scale bar calibration
│           │   ├── configure.js       # Parameter controls
│           │   ├── extraction.js      # Extraction workflow, save/load
│           │   ├── data.js            # Data tables, statistics
│           │   ├── editor.js          # Manual editing operations
│           │   ├── undo.js            # Undo/redo system
│           │   ├── sets.js            # Multiple annotation sets
│           │   └── settings.js        # User preferences
│           └── help/parameters.html   # Parameter documentation
│
├── tests/                             # Pytest test suite
├── test_images/                       # Reference images with known values
├── images/                            # High-resolution SEM images
├── slo/                               # Saved annotation files (gitignored)
├── log/                               # JSONL session logs (gitignored)
├── output/                            # CLI output (gitignored)
├── specs/                             # Specification documents
└── pyproject.toml
```

## Key Concepts

### Terminology
- **TUB** (Tubercle) - A single detected tubercle, displayed as a circle
- **ITC** (Intertubercular Connection) - A link between neighboring tubercles
- **SLO** (Scales and Links Overlay) - Complete set of TUB/ITC annotations for an image

### Data Models (`models.py`)
- `CalibrationData` - Pixel-to-micrometer conversion with `px_to_um()` and `um_to_px()` methods
- `Tubercle` - Single detected tubercle with position, diameter, circularity, optional ellipse parameters
- `NeighborEdge` - Edge between neighboring tubercles with center and edge-to-edge distances
- `MeasurementResult` - Complete results including statistics and genus classification

### Parameter Profiles (`profiles.py`)
Predefined parameter sets: `default`, `paralepidosteus`, `lepisosteus`, `polypterus`, `high-contrast`, `low-contrast`, `scanned-pdf`

### Detection Methods
- `log` (default) - Laplacian of Gaussian blob detection
- `dog` - Difference of Gaussian (faster, less accurate)
- `ellipse` - Threshold + ellipse fitting
- `lattice` - Hexagonal lattice-aware detection

### Neighbor Graph Types
- `delaunay` - All Delaunay edges
- `gabriel` - Gabriel graph (fewer edges)
- `rng` - Relative Neighborhood Graph (most conservative)

## Web UI Features

### Tabs (in order)
1. **Image** - Rotate, crop, autocrop, save operations
2. **Calibration** - Automatic estimate, manual input, graphical scale bar tool
3. **Extraction** - Run automated detection with configured parameters
4. **Configure** - All detection/preprocessing parameters, profile presets
5. **Edit** - Add/delete/move/resize tubercles and connections, undo/redo
6. **Data** - TUB/ITC tables with click-to-select sync
7. **Log** - Session event log
8. **Settings** - Display preferences (zoom behavior, overlay colors, etc.)
9. **About** - Version info

### Multiple Annotation Sets
Users can save multiple annotation sets per image for comparison (e.g., different parameters, before/after editing). Sets are stored in v2 SLO format with backward compatibility for v1 files.

### File Formats
- `*_slo.json` - Complete annotation data (v2 supports multiple sets)
- `*_tub.csv` - Tubercle data export
- `*_itc.csv` - Connection data export

## Test Images and Validation

Test images in `test_images/` have known expected values from original research papers (see `test_images/test_cases.md`). The `benchmark` command validates measurements against these values.

**Acceptance criteria:**
- Tubercle Diameter: ± 0.5 µm
- Intertubercular Space: ± 0.7 µm
- Correct genus classification

## CLI Output Structure

Each CLI run creates a timestamped directory in `output/` containing:
- `processing_log.txt` - Detailed log
- `*_summary.csv` - Summary statistics
- `*_tubercles.csv` - Per-tubercle measurements
- `*_edges.csv` - Neighbor edge measurements
- `*_detection.png` - Two-panel visualization (detected tubercles + geometry diagram)

## Specifications

Detailed specifications are in the `specs/` folder:
- `implementation-plan.md` - Original CLI implementation plan
- `ui-fish-scale-measure-spec-revised.md` - Complete UI specification
- `ui-implementation-phases.md` - UI implementation phases and status
- `ui-multiple-tubelinksets.md` - Multiple annotation sets feature spec
