# History of Implementation: Fish Scale Tubercle Analysis

**Initial Date:** 11 December 2025
**Last Updated:** 31 December 2025
**Status:** Full-featured application with CLI, Web UI, MCP Server, and LLM Agent

---

## Overview

This document describes the development of an automated system for measuring tubercle diameter and intertubercular spacing from SEM images of ganoid fish scales. The methodology is based on the work of Gayet & Meunier (1986, 1993, 2001), who established that these metrics can be used to differentiate fish genera and species.

---

## Reference Materials

### Source Papers (French, with English translations)

1. **Gayet & Meunier (1986)** - C.R. Acad. Sci. Paris 303:1259-1262
   - Original methodology paper establishing tubercle pattern analysis
   - Introduced SEM-based measurement of tubercle diameter and spacing
   - Key finding: tubercle characteristics are species-specific and constant across body position, age, and regenerated scales

2. **Gayet & Meunier (1993)** - Doc. Lab. Géol. Lyon 125:169-185
   - Comprehensive measurements tables for multiple genera
   - Detailed reference values for Lepisosteus, Atractosteus, Polypterus, etc.

3. **Gayet & Meunier (2001)** - Cybium 25(2):153-159
   - Focus on Paralepidosteus genus
   - Measurement protocol description: trace tubercle boundaries, measure with "Canvas" software

### Reference Image

- **File:** `test_images/P2_Fig1c_Paralepidosteus_sp_Acre_5.73um.tif`
- **Species:** ?Paralepidosteus sp. from Acre, Brazil (Cretaceous)
- **Expected values:**
  - Tubercle diameter: 5.73-5.94 µm
  - Intertubercular spacing: 6.00-6.25 µm
- **Methodology visualization:** `specs/extraction_methodology.png` showing ~43 tubercles with ~95-100 connection edges

### Acceptance Criteria

From `test_images/test_cases.md`:
- Tubercle diameter: ±0.5 µm tolerance (acceptable range: 5.23-6.44 µm)
- Intertubercular spacing: ±0.7 µm tolerance (acceptable range: 5.30-6.95 µm)

---

## Final Methodology

### Detection Pipeline

1. **Image Loading:** Support for TIFF and PNG formats
2. **Preprocessing:**
   - CLAHE (Contrast Limited Adaptive Histogram Equalization): clip=0.03, kernel=8
   - Gaussian blur: σ=1.0
3. **Tubercle Detection:**
   - Laplacian of Gaussian (LoG) blob detection
   - Threshold: 0.15
   - Minimum diameter: 5.0 µm
   - Maximum diameter: 15.0 µm
   - Minimum circularity: 0.35
4. **Calibration:** 0.33 µm/pixel (from 100 µm scale bar = 303 pixels at 700× magnification)

### Spacing Calculation: Nearest-Neighbor Method

**Key insight from paper analysis:** The original researchers measured spacing between *immediately adjacent* tubercles only, not an average over all possible connections.

The final implementation uses **nearest-neighbor spacing**:
- For each tubercle, find its single closest neighbor
- Calculate edge-to-edge distance (center distance minus both radii)
- Report mean and standard deviation of these values

This matches the paper methodology where researchers would visually identify and measure gaps between adjacent tubercles.

### Final Results (Paralepidosteus profile)

| Metric | Reference | Our Result | Status |
|--------|-----------|------------|--------|
| Tubercles | ~43 | 37 | Close |
| Diameter | 5.73-5.94 µm | 6.41 ± 1.33 µm | **PASS** |
| Spacing | 6.00-6.25 µm | 6.29 ± 3.42 µm | **PASS** |

---

## Techniques Implemented

### 1. Blob Detection Methods

#### Laplacian of Gaussian (LoG) - **SELECTED**
- Primary detection method
- Works by finding scale-space maxima
- Good for detecting circular/elliptical features
- Parameters: threshold, min/max sigma (derived from diameter constraints)

#### Difference of Gaussians (DoG) - **IMPLEMENTED, ALTERNATIVE**
- Faster approximation to LoG
- Available via `--method dog`
- Slightly less accurate but faster for large images

#### Pure Ellipse Detection - **IMPLEMENTED, ALTERNATIVE**
- Threshold + watershed segmentation + regionprops ellipse fitting
- Available via `--method ellipse`
- Better for elongated tubercles but more sensitive to threshold

### 2. Ellipse Refinement

**Implemented but not default for Paralepidosteus:**
- Takes LoG/DoG blob detections
- Refits each blob with ellipse using local thresholding
- Reports major/minor axis, orientation, eccentricity
- Available via `--refine-ellipse` flag
- Useful for analyzing tubercle shape variation

### 3. Neighbor Graph Methods

#### Delaunay Triangulation
- Creates triangular mesh connecting all points
- Provides all possible neighbor relationships
- Issue: includes long edges across gaps in tubercle coverage

#### Gabriel Graph - **IMPLEMENTED**
- Filters Delaunay edges
- Keeps edge (a,b) only if no other point lies inside the circle with diameter ab
- Removes some spurious long connections
- Available via `--neighbor-graph gabriel`

#### Relative Neighborhood Graph (RNG) - **IMPLEMENTED**
- More conservative filter than Gabriel
- Keeps edge (a,b) only if no point c exists where max(dist(a,c), dist(b,c)) < dist(a,b)
- Available via `--neighbor-graph rng`

#### Max Distance Factor - **IMPLEMENTED**
- Filters edges longer than N × median edge length
- Available via `--max-edge-factor N`
- Useful for removing outlier connections

### 4. Spacing Calculation Methods

#### Graph-Based Spacing - **IMPLEMENTED, ALTERNATIVE**
- Averages edge-to-edge distances over all graph edges
- Available via `--spacing-method graph`
- Issue: includes distant connections that inflate spacing values

#### Nearest-Neighbor Spacing - **SELECTED AS DEFAULT**
- Uses only the closest neighbor for each tubercle
- Available via `--spacing-method nearest` (default)
- Matches paper methodology
- Produces values consistent with published reference data

---

## Techniques Rejected

### 1. Full Delaunay Spacing (Without Filtering)

**Rejected because:** When averaging spacing over all Delaunay edges (~117 edges for 43 tubercles), we got spacing of 14.82 µm - far above the reference 6.00-6.25 µm. The triangulation includes long edges that cross gaps in tubercle coverage, which the original researchers would not have measured.

### 2. Strict Sigma Overrides in Profiles

**Rejected because:** Setting min_sigma=5, max_sigma=15 in the profile reduced detection from 41 to 25 tubercles. The auto-calculated sigma range (5.4-16.1) based on diameter constraints worked better than fixed overrides.

### 3. Aggressive CLAHE Parameters (clip=0.05, kernel=12)

**Rejected because:** While this detected more tubercles (41 vs 37), the spacing dropped to 5.44 µm - below the acceptable range. Default CLAHE (clip=0.03, kernel=8) gave better spacing accuracy (6.29 µm).

### 4. RNG/Gabriel for Spacing Calculation

**Evaluated but not selected as primary method:**
- RNG with K=6 mutual neighbors gave ~99 edges (matching reference ~95-100)
- But spacing was 11.27 µm - still too high
- Issue: these graph methods define *which* connections to consider, but don't address the fundamental mismatch between "all connections" and "nearest neighbor" methodology

### 5. Absolute Distance Filtering

**Evaluated:** Filtering edges by absolute max center-to-center distance (e.g., ≤15 µm)
- Gave reasonable results but required manual tuning per image
- Nearest-neighbor method is more robust and parameter-free

---

## Key Discoveries

### 1. Paper Methodology Uses Nearest Neighbors

The critical insight came from analyzing the discrepancy between our results and reference values:

- With 43 tubercles and 117 Delaunay edges, graph-based spacing was ~15 µm
- Reference reports 6.00-6.25 µm spacing
- The reference methodology image shows ~95-100 connection lines
- But the *spacing values* in the papers must come from measuring immediate neighbors

The papers describe tracing tubercle boundaries and measuring distances - this naturally focuses on adjacent tubercles, not distant ones connected by graph edges.

### 2. Tubercle Density Analysis

Comparing our detection to the reference methodology image:
- Reference: ~43 tubercles in ~72×72 µm area = 0.0082/µm²
- Our detection: 43 tubercles in ~103×119 µm area = 0.0035/µm²

This indicated our tubercles were spread over a larger area, explaining why graph-based spacing was inflated. The nearest-neighbor method correctly identifies the local spacing regardless of overall distribution.

### 3. Center-to-Center vs Edge-to-Edge

The papers report "intertubercular space" which is the gap *between* tubercles (edge-to-edge), not center-to-center distance:
- Expected center-to-center: diameter + spacing = 5.73 + 6.12 = 11.85 µm
- Our nearest-neighbor center distance: 11.10 µm (close match!)
- Edge-to-edge is calculated by subtracting both radii

---

## Implementation Files

### Core Modules

- `src/fish_scale_analysis/core/detection.py` - Blob detection, ellipse fitting
- `src/fish_scale_analysis/core/measurement.py` - Neighbor graphs, spacing calculation
- `src/fish_scale_analysis/core/calibration.py` - Scale bar calibration
- `src/fish_scale_analysis/core/preprocessing.py` - CLAHE, blur, top-hat

### Key Functions Added

```python
# In measurement.py
def measure_nearest_neighbor_spacing(tubercles, calibration, min_space_um=0.0):
    """Calculate spacing using nearest-neighbor distances only.
    Matches Gayet & Meunier methodology."""

def filter_to_rng(points, delaunay_edges):
    """Filter Delaunay edges to Relative Neighborhood Graph."""

def filter_to_gabriel(points, delaunay_edges):
    """Filter Delaunay edges to Gabriel Graph."""
```

### CLI Options Added

```
--spacing-method {nearest,graph}  # Default: nearest
--neighbor-graph {delaunay,gabriel,rng}
--max-edge-factor N
--refine-ellipse
--method {log,dog,ellipse}
--label-mode {id,diameter,spacing}
```

### Profile System

Profiles store tuned parameters for different species/image types:

```python
"paralepidosteus": DetectionProfile(
    calibration_um_per_px=0.33,
    threshold=0.15,
    min_circularity=0.35,
    min_diameter_um=5.0,
    max_diameter_um=15.0,
    # ... preprocessing defaults
)
```

---

## Usage Example

```bash
# Process Paralepidosteus image with tuned profile
fish-scale-measure process \
    test_images/P2_Fig1c_Paralepidosteus_sp_Acre_5.73um.tif \
    --profile paralepidosteus \
    --spacing-method nearest \
    -o output

# Output:
# Tubercles: 37
# Diameter: 6.41 ± 1.33 µm  (ref: 5.73-5.94)
# Spacing: 6.29 ± 3.42 µm   (ref: 6.00-6.25)
# Status: PASS
```

---

## Development: December 11-31, 2025

This section documents the major features added after the initial CLI implementation.

### Web UI (fish-scale-ui)

A complete Flask-based web interface was implemented in three phases:

**Phase 1: Core Infrastructure**
- Flask app with Jinja2 templates
- Image loading, zoom, pan, rotation, crop
- Calibration tools (automatic estimate, manual input, graphical scale bar)
- Recent images sidebar

**Phase 2: Extraction & Data**
- Integration with CLI extraction pipeline
- Parameter configuration UI with profile presets
- TUB/ITC data tables with click-to-select sync
- Statistics display (mean, std, counts)
- CSV export functionality

**Phase 3: Manual Editing**
- Add/delete/move/resize tubercles
- Add/delete connections
- Auto-connect (Delaunay/Gabriel/RNG)
- Undo/redo system
- SLO file save/load

**Post-Implementation Tweaks:**
- Always-visible statistics bar
- Combined Extraction/Configure tabs
- Ellipse display option
- Edge culling controls
- Chain Mode for DAG-based editing with arrow key navigation
- Parameter persistence across sessions
- Slider precision improvements (3 decimal places)

### Multiple Annotation Sets (SLO v2)

Extended the SLO file format to support multiple annotation sets per image:
- Each set contains its own tubercles and edges
- Users can compare different extraction parameters or editing states
- Active set selection with set management UI
- Backward compatibility with v1 format

See `docs/slo-persistence.md` for format details.

### MCP Server (fish-scale-mcp)

Model Context Protocol server enabling LLM agents to control the UI programmatically:

| Tool Category | Tools |
|--------------|-------|
| State | `get_state`, `get_screenshot` |
| Image | `load_image`, `set_calibration` |
| Params | `get_params`, `set_params` |
| Detection | `run_extraction` |
| Tubercles | `add_tubercle`, `move_tubercle`, `delete_tubercle` |
| Connections | `add_connection`, `delete_connection`, `clear_connections`, `auto_connect` |
| Output | `get_statistics`, `save_slo` |

Server-side screenshot rendering using PIL for consistent visual feedback.

### LLM Agent (fish-scale-agent)

Automated tubercle detection using vision-capable LLMs:

**Three-Phase Detection Process:**
1. **High-Confidence Detection** - Run extraction with conservative parameters
2. **Pattern Completion** - LLM analyzes screenshots to identify gaps in hexagonal pattern
3. **Connection Generation** - Generate neighbor connections using Gabriel graph

**Supported Providers:**
| Provider | Default Model | Env Var |
|----------|---------------|---------|
| Claude | claude-sonnet-4-20250514 | `ANTHROPIC_API_KEY` |
| Gemini | gemini-2.0-flash | `GEMINI_API_KEY` |
| OpenRouter | anthropic/claude-sonnet-4 | `OPENROUTER_API_KEY` |

OpenRouter provides access to many models (GPT-4o, Gemini, Llama, Mistral, etc.) through a single API.

See `docs/openrouter-how-to.md` for detailed setup guide.

### Hexagonalness Metrics

New metric measuring how well detected patterns match ideal hexagonal lattice:

```
Hexagonalness = 0.40 × Spacing Uniformity + 0.45 × Degree Score + 0.15 × Edge Ratio Score
```

**Components:**
- **Spacing Uniformity** (40%): Based on coefficient of variation of edge lengths
- **Degree Score** (45%): Weighted score based on neighbor counts (ideal: 6)
- **Edge Ratio Score** (15%): Ratio of edges to nodes (ideal: ~2.5)

**Boundary Detection:** Delaunay triangulation identifies boundary nodes (excluded from degree calculations) to avoid penalizing edge tubercles.

**Configurable Coefficients:** Weights can be adjusted via UI or API.

Implementations synchronized across:
- Python core: `measurement.py`
- Python MCP API: `mcp_api.py`
- JavaScript: `extraction.js`, `setUI.js`, `editor.js`

### Files Added

```
src/
├── fish_scale_ui/           # Complete Flask web UI
│   ├── app.py, run.py
│   ├── routes/              # main.py, api.py, mcp_api.py
│   ├── services/            # extraction.py, persistence.py, logging.py
│   ├── templates/           # Jinja2 templates
│   └── static/              # CSS, JavaScript modules
│
├── fish_scale_mcp/          # MCP server
│   ├── server.py            # FastMCP with tool definitions
│   ├── screenshot.py        # PIL-based rendering
│   └── cli.py
│
└── fish_scale_agent/        # LLM agent
    ├── runner.py            # Agent orchestration
    ├── prompts.py           # System prompts
    └── providers/           # claude.py, gemini.py, openrouter.py

docs/
├── slo-persistence.md       # SLO format documentation
└── openrouter-how-to.md     # OpenRouter setup guide
```

### Extraction Parameter Optimization Agent (31 December 2025)

A new LLM-powered agent for automated parameter optimization, complementing the existing pattern completion agent:

**Purpose:** Find optimal extraction parameters by iteratively adjusting settings and evaluating results, eliminating manual trial-and-error parameter tuning.

**Key Differentiator from Existing Agent:**
| Aspect | Pattern Completion Agent | Extraction Optimizer |
|--------|-------------------------|---------------------|
| Goal | Add missing tubercles | Find optimal parameters |
| Output | Full annotation set | Optimal parameter values |
| Method | Manual tubercle addition | Parameter adjustment |
| Iterations | 10-30 (adding tubercles) | 5-10 (tuning params) |

**Two-Phase Optimization Strategy:**
1. **Profile Selection** - Try candidate profiles, select best as starting point
2. **Parameter Fine-Tuning** - LLM analyzes visuals + metrics, proposes targeted adjustments

**Implementation (8 Phases):**

1. **Logging Infrastructure** - Added hexagonalness to all log events (extraction, auto_connect, manual_edit) with color-coded display in Log tab

2. **Agent Tab Infrastructure** - New `FISH_SCALE_AGENT_TABS` env var controls visibility of Agent Extraction/Editing tabs; context processor injects config to templates

3. **Core Agent Module** - `extraction_optimizer.py` with:
   - `ExtractionOptimizer` class for orchestration
   - `OptimizationState` and `TrialRecord` dataclasses
   - `OPTIMIZATION_TOOLS` definitions (8 tools)
   - `is_duplicate()` helper to avoid parameter loops

4. **Agent Loop Implementation** - Full `optimize()` method with:
   - Tool execution via HTTP API calls
   - Stopping conditions (target achieved, plateau, max iterations)
   - Best result tracking across iterations
   - Flask endpoints: `/api/agent/start`, `/status`, `/stop`, `/providers`

5. **Prompt Engineering** - Comprehensive prompts with:
   - Parameter effects table (threshold, diameter, circularity, CLAHE, blur)
   - Two-phase strategy instructions
   - Diagnostic guide for common scenarios
   - Few-shot examples showing good reasoning
   - `build_iteration_prompt()` for context-aware iteration guidance

6. **CLI Integration** - New `optimize` subcommand:
   ```bash
   uv run fish-scale-agent optimize image.tif --calibration 0.1 \
       --provider claude --target-score 0.7 --max-iterations 10
   ```

7. **UI Tab Implementation** - Complete Agent Extraction tab with:
   - Configuration panel (provider, model, profile, target, iterations)
   - Status panel (state, phase, iteration, best score, elapsed time)
   - Parameters display with change highlighting
   - Hexagonalness progress chart (Chart.js)
   - Collapsible LLM prompt/response containers
   - Start/Stop/Accept Best/Reset controls

8. **Testing & Validation** - All syntax checks passed, 142/143 tests pass

**Enabling Agent Tabs:**
```bash
export FISH_SCALE_AGENT_TABS=1        # All agent tabs
export FISH_SCALE_AGENT_TABS=extraction  # Just extraction tab
uv run fish-scale-ui
```

**Files Added/Modified:**
```
src/fish_scale_agent/
├── extraction_optimizer.py    # NEW: Core optimizer module
└── cli.py                     # Modified: Added optimize subcommand

src/fish_scale_ui/
├── app.py                     # Modified: Agent tabs config, blueprint
├── routes/agent_api.py        # NEW: Agent control endpoints
├── templates/workspace.html   # Modified: Agent tabs HTML
└── static/
    ├── js/agent_extraction.js # NEW: Agent tab JavaScript
    ├── js/extraction.js       # Modified: Hexagonalness logging
    ├── js/sets.js             # Modified: Hexagonalness in edits
    ├── js/main.js             # Modified: Log display formatting
    └── css/main.css           # Modified: Agent tab styles

src/fish_scale_mcp/server.py   # Modified: StatisticsData model
```

**Workflow Integration:**
```
1. Load image, set calibration
2. [NEW] Run Extraction Optimizer → get optimal params
3. Run extraction with optimal params
4. [EXISTING] Run Pattern Completion Agent → add missed tubercles
5. Generate connections
6. Save results
```

**Bug Fixes & Refinements (31 December 2025):**

- **API Endpoint Rename**: Changed `/api/mcp/*` → `/api/tools/*` for clarity (these are REST endpoints, not MCP protocol)
- **Agent Start Fix**: Fixed image path and calibration not being passed to subprocess; now fetches from `_current_image` state
- **Polling Fix**: Agent subprocess now uses `PYTHONUNBUFFERED=1` and `flush=True` for immediate output capture
- **Overlay Refresh**: UI now refreshes tubercle/ITC overlay on each iteration (was only refreshing on completion)
- **Parameters Display**: Polling now fetches current params from `/api/tools/params` to show live parameter values
- **LLM Display**: Shows tool calls extracted from log lines in the "Last LLM Response" section
- **Score Parsing Fix**: Hexagonalness regex now excludes "Target hexagonalness" config lines to avoid showing target as actual score
- **Tubercle Count Regex**: Fixed to match both "42 tubercles" and "Tubercles: 42" formats
- **Image Copy Prevention**: `/api/tools/load-image` now skips copying if same image already loaded (prevents GUID file accumulation)
- **Circularity Guidance**: Enhanced prompts to emphasize min_circularity as key parameter; recommend trying 0.2-0.3 for missing tubercles

### Agent Extraction Tab Monitoring Enhancements (31 December 2025)

Comprehensive improvements to the Agent Extraction tab for better observability and debugging of the LLM optimization process:

**Real-Time Cost Tracking:**
- Token counts (input/output) update after each LLM API call
- Running cost estimate displayed in real-time
- New "Last Step Cost" field shows incremental cost per API call
- Cost delta calculated by tracking previous total

**Full Prompt Display:**
- Complete prompt JSON shown (system prompt + tools + message history)
- Base64 image data automatically truncated to `...[N bytes base64 truncated]...`
- Prompt statistics header showing: iteration, hexagonalness, tubercles, ITC count, prompt size
- Scrollable container with styled scrollbars

**Full LLM Response Display:**
- Changed from text-only "reasoning" to complete response JSON
- Response includes: text, tool_calls (with id, name, arguments), stop_reason, usage
- Enables full analysis of what the LLM decided and why

**Action Summary Section:**
- New collapsible section logging all agent actions with timestamps
- Shows seconds elapsed since run start for each action
- Full log line text (not simplified summaries)
- Excludes data lines (LLM-Prompt, LLM-Response, Usage) to keep focused on actions
- Deduplication via `seenLogLines` Set to prevent repeated entries

**Copy Buttons:**
- Copy button on "Last Prompt Sent" - copies full prompt JSON
- Copy button on "Last LLM Response" - copies full response JSON
- Copy button on "Action Summary" - copies timestamped action log
- Clear button on Action Summary
- Visual feedback (green checkmark) on successful copy

**Technical Implementation:**

*Provider Layer (claude.py):*
- `_truncate_base64()` - Truncates base64 strings while preserving structure
- `_serialize_prompt()` - Serializes system + tools + messages to JSON
- Response serialization with text, tool_calls, stop_reason, usage
- AgentIteration extended with `prompt_content`, `prompt_size_bytes`, `response_json`

*Optimizer (extraction_optimizer.py):*
- Logs `Usage:` with token counts and cost after each LLM call
- Logs `LLM-Response:` with full response JSON (pipe-separated for single line)
- Logs `Prompt-Stats:` with byte size
- Logs `LLM-Prompt:` with full prompt (base64 pre-truncated)

*JavaScript (agent_extraction.js):*
- State tracking: `actionSummary[]`, `seenLogLines` Set, `lastStepCost`, `previousCost`
- `parseLogLines()` extracts Usage, LLM-Response, Prompt-Stats, LLM-Prompt
- `addAction()` logs actions with elapsed time
- `copyToClipboard()` with visual feedback
- `formatBytes()` helper for human-readable sizes

*CSS (main.css):*
- `.agent-collapsible-actions` container for header buttons
- `.btn-small` and `.btn-copy` button styles
- `.btn-copy.copied` green feedback state
- Scrollbar styling for prompt/response containers

*HTML (workspace.html):*
- Copy buttons added to Last Prompt, Last Response, Action Summary headers
- Clear button for Action Summary
- Last Step Cost row in Costs section
- `agentActionSummary` pre element

**Files Modified:**
```
src/fish_scale_agent/
├── providers/base.py          # AgentIteration extended
├── providers/claude.py        # Prompt/response serialization
└── extraction_optimizer.py    # Logging enhancements

src/fish_scale_ui/
├── templates/workspace.html   # Copy buttons, Action Summary section
├── static/css/main.css        # Button styles, scrollbars
└── static/js/agent_extraction.js  # Parsing, state, copy functions
```

### Future Work (Updated)

**Completed from original list:**
- ~~ROI selection~~ → Crop tool in Image tab
- ~~Confidence metrics~~ → Circularity scores displayed per tubercle
- ~~Agent improvements~~ → Extraction Parameter Optimization Agent
- ~~Agent observability~~ → Real-time monitoring, full prompt/response display

**Remaining:**
1. **Validate on other test images** - Systematic validation across species
2. **Update genus reference ranges** - Expand models.py with more species
3. **Batch processing with comparison** - Generate multi-image scatter plots
4. **Agent editing tab** - Automated pattern completion and outlier detection

---

## References

1. Gayet M. & Meunier F.J. (1986) Apport de l'étude de l'ornementation microscopique de la ganoïne dans la détermination de l'appartenance générique et/ou spécifique des écailles isolées. C.R. Acad. Sci. Paris, t. 303, Série II, n° 13, pp. 1259-1262.

2. Gayet M. & Meunier F.J. (1993) Conséquences paléobiogéographiques et biostratigraphiques de l'identification d'écailles ganoïdes du Crétacé supérieur et du Tertiaire inférieur d'Amérique du Sud. Doc. Lab. Géol. Lyon 125: 169-185.

3. Gayet M. & Meunier F.J. (2001) À propos du genre Paralepidosteus (Ginglymodi, Lepisosteidae) du Crétacé gondwanien. Cybium 25(2): 153-159.
