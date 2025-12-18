# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fish Scale Metrics Extraction - A Python toolset for extracting tubercle diameter and intertubercular space measurements from SEM (Scanning Electron Microscope) images of ganoid fish scales. These measurements differentiate between fish families/genera (Lepisosteidae, Polypteridae, Semionotidae) based on methodology from Gayet & Meunier (1986, 1993) and Brito et al. (2000).

**Four interfaces are available:**
1. **CLI Tool** (`fish-scale-measure`) - Command-line processing for single images or batches
2. **Web UI** (`fish-scale-ui`) - Flask-based graphical interface with manual editing capabilities
3. **MCP Server** (`fish-scale-mcp`) - Model Context Protocol server for LLM agent control
4. **LLM Agent** (`fish-scale-agent`) - Automated tubercle detection using LLM vision (Gemini)

## Development Commands

```bash
# Setup (using uv package manager)
uv venv
uv pip install -e ".[dev,mcp,agent]"

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

# MCP Server usage
uv run fish-scale-mcp                          # Start MCP server (requires UI running)

# LLM Agent usage (requires UI running)
uv run fish-scale-agent providers              # List available LLM providers
uv run fish-scale-agent run <image>            # Run agent on image (Gemini default)
uv run fish-scale-agent run --provider gemini  # Explicit provider
uv run fish-scale-agent run --calibration 0.1  # Set calibration (µm/px)
uv run fish-scale-agent run -v                 # Verbose mode
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
│   ├── fish_scale_ui/                 # Flask Web UI
│   │   ├── app.py                     # Flask app factory
│   │   ├── run.py                     # Entry point with CLI args
│   │   ├── routes/
│   │   │   ├── main.py                # Page routes
│   │   │   ├── api.py                 # API endpoints (extraction, save/load, etc.)
│   │   │   └── mcp_api.py             # MCP server API endpoints
│   │   ├── services/
│   │   │   ├── extraction.py          # Wrapper around CLI extraction
│   │   │   ├── persistence.py         # SLO save/load
│   │   │   ├── logging.py             # JSONL logging
│   │   │   └── recent_images.py       # Recent images management
│   │   ├── templates/                 # Jinja2 templates
│   │   └── static/
│   │       ├── css/main.css
│   │       ├── js/                    # JavaScript modules
│   │       │   ├── main.js            # App initialization, tabs
│   │       │   ├── image.js           # Zoom, pan, crop, rotate
│   │       │   ├── overlay.js         # TUB/ITC rendering, selection
│   │       │   ├── calibration.js     # Scale bar calibration
│   │       │   ├── configure.js       # Parameter controls
│   │       │   ├── extraction.js      # Extraction workflow, save/load
│   │       │   ├── data.js            # Data tables, statistics
│   │       │   ├── editor.js          # Manual editing operations
│   │       │   ├── undo.js            # Undo/redo system
│   │       │   ├── sets.js            # Multiple annotation sets
│   │       │   └── settings.js        # User preferences
│   │       └── help/parameters.html   # Parameter documentation
│   │
│   ├── fish_scale_mcp/                # MCP Server for LLM agents
│   │   ├── __init__.py
│   │   ├── server.py                  # FastMCP server with tool definitions
│   │   ├── screenshot.py              # Server-side image rendering (PIL)
│   │   └── cli.py                     # CLI entry point
│   │
│   └── fish_scale_agent/              # LLM Agent for automated detection
│       ├── __init__.py
│       ├── runner.py                  # Agent orchestration
│       ├── prompts.py                 # System prompts for three-phase detection
│       ├── cli.py                     # CLI entry point
│       └── providers/
│           ├── __init__.py
│           ├── base.py                # AgentLLMProvider ABC
│           └── gemini.py              # Gemini provider implementation
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

## MCP Server

The MCP (Model Context Protocol) server enables LLM agents to control the fish-scale-ui application programmatically. This supports an agentic workflow where an LLM can:

1. Load images and set calibration
2. Run automated tubercle extraction
3. Add/move/delete tubercles manually
4. Generate connections (Delaunay/Gabriel/RNG graphs)
5. Capture screenshots for visual analysis
6. Save results to SLO files

### MCP Tools Available

| Tool | Description |
|------|-------------|
| `get_screenshot` | Capture current view as base64 PNG |
| `get_state` | Get complete current state |
| `load_image` | Load an image file |
| `set_calibration` | Set µm/pixel calibration |
| `get_params` / `set_params` | Get/set extraction parameters |
| `run_extraction` | Run automated tubercle detection |
| `add_tubercle` / `move_tubercle` / `delete_tubercle` | Tubercle CRUD |
| `add_connection` / `delete_connection` | Connection CRUD |
| `clear_connections` | Remove all connections |
| `auto_connect` | Generate connections (delaunay/gabriel/rng) |
| `get_statistics` | Get measurement statistics |
| `save_slo` | Save annotations to file |

### Running the MCP Server

```bash
# Start the Web UI first (MCP server requires it)
uv run fish-scale-ui

# In another terminal, start the MCP server
uv run fish-scale-mcp
```

## LLM Agent

The LLM Agent (`fish-scale-agent`) provides automated tubercle detection using vision-capable LLMs. It implements a three-phase detection process:

### Three-Phase Detection Process

1. **Phase 1: High-Confidence Detection** - Uses conservative parameters to find obvious tubercles that serve as anchor points
2. **Phase 2: Pattern Completion** - LLM analyzes screenshots to identify gaps in the hexagonal pattern and adds missing tubercles
3. **Phase 3: Connection Generation** - Generates neighbor connections using Gabriel graph algorithm

### Supported LLM Providers

| Provider | Model | API Key Env Var | Status |
|----------|-------|-----------------|--------|
| Claude | claude-sonnet-4-20250514 | `ANTHROPIC_API_KEY` | **Default** - with vision support |
| Gemini | gemini-2.0-flash | `GEMINI_API_KEY` | Implemented |
| OpenRouter | various | `OPENROUTER_API_KEY` | Planned |

### Running the Agent

```bash
# Prerequisites: Start the Web UI first
uv run fish-scale-ui

# In another terminal, run the agent
export ANTHROPIC_API_KEY=your_key_here
uv run fish-scale-agent run test_images/P1_Fig4_Atractosteus_simplex_7.07um.tif

# With options
uv run fish-scale-agent run image.tif --calibration 0.1 --max-iterations 30 -v

# Use Gemini instead
export GEMINI_API_KEY=your_key_here
uv run fish-scale-agent run image.tif --provider gemini
```

## Specifications

Detailed specifications are in the `specs/` folder:
- `implementation-plan.md` - Original CLI implementation plan
- `ui-fish-scale-measure-spec-revised.md` - Complete UI specification
- `ui-implementation-phases.md` - UI implementation phases and status
- `ui-multiple-tubelinksets.md` - Multiple annotation sets feature spec
- `mcp-agent-tubercle-detection-spec.md` - MCP server and agent specification
- `mcp-testing.md` - MCP server testing strategy and results
