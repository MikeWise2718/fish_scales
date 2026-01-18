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

## Version Management

**IMPORTANT:** The version number MUST be updated with every code change.

Version is tracked in these locations (all must be updated together):
- `pyproject.toml` - line 3: `version = "X.Y.Z"  # Updated: YYYY-MM-DD`
- `src/fish_scale_analysis/__init__.py` - `__version__` and `__version_date__`
- `src/fish_scale_ui/__init__.py` - `__version__` and `__version_date__`
- `src/fish_scale_mcp/__init__.py` - `__version__` and `__version_date__`
- `src/fish_scale_agent/__init__.py` - `__version__` and `__version_date__`

**Format:**
```python
__version__ = "0.1.1"
__version_date__ = "2026-01-14"
```

**Versioning scheme:**
- Patch (0.0.X): Bug fixes, minor changes, refactoring
- Minor (0.X.0): New features, significant enhancements
- Major (X.0.0): Breaking changes, major architectural changes

When making code changes, increment the patch version and update the date to today's date in all locations.

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
│   │   │   └── tools_api.py            # Tool endpoints for agents (/api/tools/*)
│   │   ├── services/
│   │   │   ├── extraction.py          # Wrapper around CLI extraction
│   │   │   ├── persistence.py         # Annotation save/load
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
│   │       └── help/
│   │           ├── parameters.html    # Detection parameter documentation
│   │           └── hexagonalness.html # Hexagonalness metrics documentation
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
│           ├── claude.py              # Anthropic Claude provider (default)
│           ├── gemini.py              # Google Gemini provider
│           └── openrouter.py          # OpenRouter provider (multi-model)
│
├── tests/                             # Pytest test suite
├── test_images/                       # Reference images with known values
├── images/                            # High-resolution SEM images
├── annotations/                       # Saved annotation files (gitignored)
├── log/                               # JSONL session logs (gitignored)
├── output/                            # CLI output (gitignored)
├── docs/                              # Documentation (annotations-persistence.md, etc.)
├── specs/                             # Specification documents
└── pyproject.toml
```

## Key Concepts

### Terminology
- **TUB** (Tubercle) - A single detected tubercle, displayed as a circle
- **ITC** (Intertubercular Connection) - A link between neighboring tubercles
- **Annotations** - Complete set of TUB/ITC annotations for an image (formerly "SLO")

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
Users can save multiple annotation sets per image for comparison (e.g., different parameters, before/after editing). Sets are stored in v2 annotations format with backward compatibility for v1 files.

### File Formats
- `*_annotations.json` - Complete annotation data (v2 supports multiple sets)
- `*_tub.csv` - Tubercle data export
- `*_itc.csv` - Connection data export

See [docs/annotations-persistence.md](docs/annotations-persistence.md) for detailed format specification.

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

## MCP Server & Tool Endpoints

The MCP (Model Context Protocol) server enables LLM agents to control the fish-scale-ui application programmatically. The underlying REST API endpoints are at `/api/tools/*` and can be called directly by agents or via the MCP server.

**Architecture:**
- **Direct HTTP agents** (like `fish-scale-agent`) call `/api/tools/*` endpoints directly
- **MCP server** (`fish-scale-mcp`) wraps these same endpoints with MCP protocol (stdio JSON-RPC)

### Tool Endpoints (`/api/tools/*`)

| Endpoint | Description |
|----------|-------------|
| `GET /api/tools/screenshot` | Capture current view as base64 PNG |
| `GET /api/tools/state` | Get complete current state |
| `POST /api/tools/load-image` | Load an image file |
| `POST /api/tools/calibration` | Set µm/pixel calibration |
| `GET/POST /api/tools/params` | Get/set extraction parameters |
| `POST /api/tools/extract` | Run automated tubercle detection |
| `POST /api/tools/add-tubercle` | Add a tubercle |
| `POST /api/tools/move-tubercle` | Move a tubercle |
| `POST /api/tools/delete-tubercle` | Delete a tubercle |
| `POST /api/tools/auto-connect` | Generate connections (delaunay/gabriel/rng) |
| `GET /api/tools/statistics` | Get measurement statistics |
| `POST /api/tools/save` | Save annotations to file |

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
| OpenRouter | anthropic/claude-sonnet-4 | `OPENROUTER_API_KEY` | Implemented - access to many models |
| Ollama | llama3.2-vision | `OLLAMA_HOST` (optional) | Implemented - local LLM inference |

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

# Use Ollama (local LLM - no API key required)
export OLLAMA_HOST=http://localhost:11434  # Optional, this is the default
uv run fish-scale-agent edit image.tif --provider ollama --model llama3.2-vision --calibration 0.14
```

### Agent Run Logs

Agent runs are logged to multiple locations for debugging:

**Session logs (JSONL format):**
```
log/YYYY-MM-DD_HHMMSS.jsonl    # UI session logs with agent events
```

**Detailed agent logs (per-run):**
```
C:\Users\<user>\AppData\Local\Temp\fish-scale-agent\agent-<type>-<session-id>.log
```

Where `<type>` is:
- `edit` - Editing agent (pattern completion, bright spots)
- `optimize` - Extraction optimizer agent

**Markdown run summaries:**
```
agent_logs\YYYY-MM-DDTHH-MM-SS_extraction.md
```

The detailed `.log` files contain:
- Full LLM prompts sent (with base64 truncated)
- Full LLM responses (text + tool calls)
- Token usage per call with cost estimates
- Tool execution results
- STATUS lines for UI parsing

**Example log analysis:**
```bash
# View latest agent log
ls -lt /c/Users/$USER/AppData/Local/Temp/fish-scale-agent/*.log | head -5

# Search for LLM responses in a log
grep "LLM-Response" agent-edit-*.log

# Find conversational responses (model asking instead of acting)
grep -i "would you like" agent-*.log
```

### Debug Seeds (Coordinate Verification)

Debug seeds are markers placed at known positions to diagnose whether the VLM correctly understands the image coordinate system. This feature helps identify issues like:
- VLM generating idealized patterns instead of detecting actual features
- Coordinate transformation problems
- VLM hallucinating content

**CLI Usage:**
```bash
# Run with corner seeds (5 points at corners + center)
uv run fish-scale-agent edit image.tif --debug-seeds corners --calibration 0.14 -v

# Run with 3x3 grid seeds (9 points)
uv run fish-scale-agent edit image.tif --debug-seeds grid3x3 --calibration 0.14

# Run with cross pattern (5 points in + shape)
uv run fish-scale-agent edit image.tif --debug-seeds cross --calibration 0.14

# Custom seed positions (x,y pairs separated by semicolons)
uv run fish-scale-agent edit image.tif --debug-seeds "100,100;350,255;600,400"

# Custom seed radius (default: 15px)
uv run fish-scale-agent edit image.tif --debug-seeds corners --debug-seed-radius 20
```

**UI Usage:**
In the AgenticEdit tab, use the "Debug Seeds" dropdown to select a pattern (Corners, Grid 3×3, Cross) before starting the agent. Analysis results appear in the "Debug Seed Analysis" section after agent completion.

**Seed Patterns:**
| Pattern | Points | Description |
|---------|--------|-------------|
| `corners` | 5 | 4 corners (15% margin) + center |
| `grid3x3` | 9 | 3×3 grid at 20%, 50%, 80% of width/height |
| `cross` | 5 | Center + 4 cardinal directions |
| custom | N | User-specified x,y coordinates |

**Analysis Results:**
- **Mean Position Error**: How accurately VLM reports seed positions
- **Systematic Offset**: Consistent (dx, dy) shift indicating coordinate transform issue
- **Overlapping Tubercles**: VLM adding tubercles on top of seeds (not seeing them)
- **Regular Grid Detected**: VLM hallucinating idealized pattern instead of detecting features

**Diagnostic Outcomes:**
| Observation | Diagnosis |
|-------------|-----------|
| VLM reports seeds accurately (< 10px error) | Coordinates working correctly |
| VLM reports seeds with consistent offset | Coordinate transformation bug |
| VLM adds tubercles on top of seeds | VLM not perceiving overlay |
| VLM adds regular grid ignoring seeds | VLM hallucinating ideal pattern |

### Selectable Agent Goals

The editing agent supports two goals:

| Goal ID | Name | Description |
|---------|------|-------------|
| `hex_pattern` | Hexagonal Pattern Completion | Complete the hexagonal tubercle pattern (default behavior) |
| `bright_spots` | Find N Brightest Spots | Locate the N brightest circular spots in the image |

**CLI Usage:**
```bash
# Default: hexagonal pattern completion
uv run fish-scale-agent edit image.tif --calibration 0.14

# Bright spots goal: find 20 brightest spots with 30px min separation
uv run fish-scale-agent edit image.tif --calibration 0.14 --goal bright_spots --spot-count 20 --min-separation 30

# Customize spot count
uv run fish-scale-agent edit image.tif --calibration 0.14 --goal bright_spots -n 50 --min-separation 25
```

**UI Usage:**
In the AgenticEdit tab Configuration section, use the "Agent Goal" dropdown to select between:
- **Hexagonal Pattern Completion** (default) - Completes the tubercle pattern
- **Find N Brightest Spots** - Simpler test mode for VLM feature localization

When "Find N Brightest Spots" is selected, additional parameters appear:
- **Number of Spots (N)**: Target count of spots to find (default: 20)
- **Min Separation (px)**: Minimum pixel distance between spots (default: 30)

**Purpose of Bright Spots Goal:**
This simpler test mode isolates the VLM's feature localization capability by removing pattern-completion complexity. It helps diagnose whether VLMs can accurately locate visual features (bright spots) without requiring semantic pattern reasoning.

**Evaluation Metrics (for bright_spots goal):**
- **Mean Intensity**: Average pixel intensity at placed spot centers
- **Brightness Ranking Score**: 0-1 measure of whether truly brightest spots were found
- **Separation Violations**: Number of spot pairs violating minimum separation

## Extraction Parameter Optimization Agent

A separate LLM-powered agent for finding optimal extraction parameters, complementing the pattern completion agent above.

### Purpose
Find optimal extraction parameters by iteratively adjusting settings and evaluating results, eliminating manual trial-and-error parameter tuning.

### Comparison with Pattern Completion Agent
| Aspect | Pattern Completion Agent | Extraction Optimizer |
|--------|-------------------------|---------------------|
| Goal | Add missing tubercles | Find optimal parameters |
| Output | Full annotation set | Optimal parameter values |
| Method | Manual tubercle addition | Parameter adjustment |
| Iterations | 10-30 (adding tubercles) | 5-10 (tuning params) |

### Two-Phase Optimization Strategy
1. **Profile Selection** - Try candidate profiles, select best as starting point
2. **Parameter Fine-Tuning** - LLM analyzes visuals + metrics, proposes targeted adjustments

### Enabling Agent Tabs
```bash
export FISH_SCALE_AGENT_TABS=1           # All agent tabs
export FISH_SCALE_AGENT_TABS=extraction  # Just extraction tab
uv run fish-scale-ui
```

### CLI Usage
```bash
uv run fish-scale-agent optimize image.tif --calibration 0.1 \
    --provider claude --target-score 0.7 --max-iterations 10
```

### Parameter Effects Reference

**Detection Parameters:**
| Parameter | Range | Default | Effect |
|-----------|-------|---------|--------|
| Threshold | 0.01–0.50 | 0.05 | Lower = more sensitive (may include noise); Higher = only strong features |
| Min Diameter | 0.5–20.0 µm | 2.0 | Filters out smaller blobs |
| Max Diameter | 1.0–50.0 µm | 10.0 | Filters out larger blobs |
| Circularity | 0.0–1.0 | 0.5 | 0.0 = any shape; 1.0 = perfect circles only |

**Preprocessing Parameters:**
| Parameter | Range | Default | Effect |
|-----------|-------|---------|--------|
| CLAHE Clip | 0.01–0.20 | 0.03 | Higher = stronger contrast enhancement |
| CLAHE Kernel | 4–32 | 8 | Smaller = more local contrast; Larger = smoother |
| Blur Sigma | 0.0–5.0 | 1.0 | Higher = more smoothing, may merge features |

**Tuning Guidelines:**
- **Too many detections**: Increase threshold, increase min_diameter, increase circularity
- **Too few detections**: Decrease threshold, decrease circularity (try 0.2-0.3), decrease min_diameter
- **Noisy detections**: Increase blur_sigma, adjust CLAHE clip
- **Missing faint tubercles**: Decrease threshold, increase CLAHE clip

### Key Implementation Files
```
src/fish_scale_agent/
├── extraction_optimizer.py    # Core optimizer module
├── agent_run_logger.py        # JSONL run logging
└── cli.py                     # optimize subcommand

src/fish_scale_ui/
├── routes/agent_api.py        # Agent control endpoints
├── templates/workspace.html   # Agent tabs HTML
└── static/js/agent_extraction.js  # Agent tab JavaScript
```

### Agent Extraction Tab Monitoring

The Agent Extraction tab provides comprehensive real-time monitoring:

**Costs Section:**
- Model name and provider
- Input/Output token counts (updated after each LLM call)
- Total estimated cost
- **Last Step Cost** - incremental cost of the most recent API call

**LLM Communication Section (collapsible):**

| Section | Content | Copy Button |
|---------|---------|-------------|
| Last Prompt Sent | Full prompt JSON (system + tools + messages) with base64 truncated | Yes |
| Last LLM Response | Full response JSON (text + tool_calls + stop_reason + usage) | Yes |
| Action Summary | Timestamped log of all agent actions | Yes + Clear |

**Prompt Statistics Header:**
```
--- Prompt Statistics ---
Iteration: 3/10
Hexagonalness: 0.720
Tubercles: 45
ITC: 89
Prompt Size: 156.2 KB
-------------------------
```

**Log Line Formats (for debugging):**
```
[HH:MM:SS] Usage: 12345 input, 567 output, $0.0234 (claude-sonnet-4-20250514)
[HH:MM:SS] LLM-Response: { | "text": "...", | "tool_calls": [...] | }
[HH:MM:SS] Prompt-Stats: size=123456
[HH:MM:SS] LLM-Prompt: { | "system": "...", | "tools": [...], | "messages": [...] | }
```

### Known Challenges & Mitigations
1. **VLM parameter understanding** (40-55% confidence): VLMs may not deeply understand parameter→visual effect mapping
2. **Complex parameter interactions**: 9 parameters with non-linear interactions
3. **Convergence not guaranteed**: May oscillate without gradient-like reasoning

**Recommended approach**: Use VLM for qualitative feedback ("too many false positives", "gaps in corners") and let controller apply deterministic adjustments, rather than asking VLM for specific parameter values.

### Workflow Integration
```
1. Load image, set calibration
2. [OPTIMIZER] Run Extraction Optimizer → get optimal params
3. Run extraction with optimal params
4. [PATTERN AGENT] Run Pattern Completion Agent → add missed tubercles
5. Generate connections
6. Save results
```

## Hexagonalness Metrics

The hexagonalness score measures how well detected tubercle patterns match an ideal hexagonal lattice. The formula is:

```
Hexagonalness = 0.40 × Spacing Uniformity + 0.45 × Degree Score + 0.15 × Edge Ratio Score
```

**Components:**
- **Spacing Uniformity** (40%): `max(0, 1 - 2 × CV)` where CV = coefficient of variation of edge lengths
- **Degree Score** (45%): Weighted score based on neighbor counts (5-7 neighbors → 1.0, 4/8 → 0.7, 3/9 → 0.3)
- **Edge Ratio Score** (15%): `max(0, 1 - |ratio - 2.5| / 2)` where ratio = edges/nodes

**Reliability:**
- `high`: 15+ nodes (statistically reliable)
- `low`: 4-14 nodes (may be unreliable)
- `none`: <4 nodes (insufficient data)

**Implementation:**
- Single source of truth: `fish_scale_ui/routes/tools_api.py` → `_calculate_hexagonalness_from_dicts()`
- API endpoint: `GET /api/hexagonalness` (supports custom weights via query params)
- JavaScript modules call the API endpoint for all hexagonalness calculations

## Screenshots and Debugging

When the user provides screenshots for debugging UI issues, they are typically located at:
```
C:\Users\mike\Pictures\screenshots\
```

Use the Read tool to view screenshot images when debugging visual issues.

## Documentation

User guides and reference documentation are in `docs/`:
- `annotations-persistence.md` - Annotation file format and storage details
- `openrouter-how-to.md` - Guide to using OpenRouter with the LLM agent
- `fish-scale-metrics-extraction.md` - High-level algorithm description
- `implementation-history.md` - Development history (Dec 2025), includes detailed Extraction Optimizer implementation notes

## Specifications

Detailed specifications are in the `specs/` folder:
- `implementation-plan.md` - Original CLI implementation plan
- `ui-fish-scale-measure-spec-revised.md` - Complete UI specification
- `ui-implementation-phases.md` - UI implementation phases and status
- `ui-multiple-tubelinksets.md` - Multiple annotation sets feature spec
- `mcp-agent-tubercle-detection-spec.md` - MCP server and agent specification
- `mcp-testing.md` - MCP server testing strategy and results
- `dataset-history-tracking.md` - Dataset provenance/history tracking (proposed)
- `AI-Extraction-Assistent.md` - AI parameter optimization assistant spec with open questions and feasibility analysis
- `extraction-agent.md` - Extraction agent specification
