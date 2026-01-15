# AgenticEdit Tab Specification

## Overview

The **AgenticEdit** tab provides an LLM-driven interface for automated tubercle pattern completion. Unlike the AgenticExtraction tab (which optimizes detection parameters), this tab uses an LLM vision model to visually analyze the image and add missing tubercles to achieve:

1. **High hexagonalness score** - tubercles arranged in a regular hexagonal pattern
2. **High area coverage** - all visible tubercles in the scale area are detected

The agent continues iterating until it can no longer make significant improvements, rather than stopping at a fixed target.

### Comparison with AgenticExtraction

| Aspect | AgenticExtraction | AgenticEdit |
|--------|-------------------|-------------|
| **Goal** | Find optimal extraction parameters | Complete pattern with high hexagonalness AND coverage |
| **LLM Action** | Adjust parameters, run extraction | Analyze image, add/delete/move tubercles |
| **Output** | Optimal parameter values | Complete annotation set |
| **Primary Tools** | `set_params`, `run_extraction` | `add_tubercle`, `delete_tubercle`, `get_screenshot` |
| **Iterations** | 5-10 (parameter tuning) | 10-30 (pattern completion) |
| **Stopping Condition** | Target score reached | No significant improvement possible |
| **Requires Existing Tubercles** | No (starts from scratch) | Yes (works with initial extraction) |

### Workflow Integration

```
1. Load image, set calibration
2. [OPTIONAL] Run AgenticExtraction → get optimal params
3. Run extraction with parameters
4. [AgenticEdit] Run pattern completion agent → fill gaps
5. Generate connections (auto-connect)
6. Save results
```

---

## User Interface Design

### Tab Position

Insert **AgenticEdit** tab after **Edit** tab:
1. Image
2. Calibration
3. Extraction
4. Configure
5. Edit
6. **AgenticEdit** ← NEW
7. Data
8. Log
9. Settings
10. About

### Tab Visibility

Like AgenticExtraction, this tab is hidden by default and enabled via environment variable:

```bash
export FISH_SCALE_AGENT_TABS=1           # All agent tabs
export FISH_SCALE_AGENT_TABS=editing     # Just AgenticEdit tab
export FISH_SCALE_AGENT_TABS=extraction,editing  # Both tabs
uv run fish-scale-ui
```

### UI Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│ AgenticEdit                                                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─ Configuration ─────────────────────────────────────────────┐   │
│  │                                                              │   │
│  │  Provider: [Claude ▼]    Model: [claude-sonnet-4 ▼]         │   │
│  │                          (input: $3.00/M, output: $15.00/M) │   │
│  │                                                              │   │
│  │  Max Iterations: [30]   Plateau Threshold: [3] iterations   │   │
│  │                                                              │   │
│  │  [✓] Auto-connect after completion (Gabriel graph)          │   │
│  │  [✓] Delete edge tubercles (boundary cleanup)               │   │
│  │                                                              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─ Controls ──────────────────────────────────────────────────┐   │
│  │                                                              │   │
│  │  [▶ Start]  [■ Stop]  [↺ Reset]  [✓ Accept Result]          │   │
│  │                                                              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─ Status ─────────────────────────────────────────── [▼] ────┐   │
│  │                                                              │   │
│  │  State: Running          Phase: Pattern Completion          │   │
│  │  Iteration: 12/30        Tubercles: 47 (+12)                │   │
│  │  Hexagonalness: 0.682    Coverage: 85%                      │   │
│  │  Elapsed: 2:34           Plateau: 0/3 iterations            │   │
│  │                                                              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─ Costs ──────────────────────────────────────────── [▼] ────┐   │
│  │                                                              │   │
│  │  Model: claude-sonnet-4-20250514 (Anthropic)                │   │
│  │  Input Tokens: 125,432   Output Tokens: 3,891               │   │
│  │  Estimated Cost: $0.43   Last Step: $0.038                  │   │
│  │                                                              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─ Progress Chart ─────────────────────────────────── [▼] ────┐   │
│  │                                                              │   │
│  │    0.75 ┤                                                    │   │
│  │         │                         ╭─────────                 │   │
│  │    0.70 ┤                    ╭────╯                          │   │
│  │         │               ╭────╯                               │   │
│  │    0.65 ┤          ╭────╯                                    │   │
│  │         │     ╭────╯                                         │   │
│  │    0.60 ┤─────╯                                              │   │
│  │         └────────────────────────────────────────────────    │   │
│  │           1   5   10   15   20   25   Iteration              │   │
│  │                                                              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─ LLM Communication ──────────────────────────────── [▼] ────┐   │
│  │                                                              │   │
│  │  ┌─ Last Prompt Sent ──────────────────────── [Copy] ───┐   │   │
│  │  │ { "system": "You are an expert...",                  │   │   │
│  │  │   "tools": [...],                                    │   │   │
│  │  │   "messages": [...] }                                │   │   │
│  │  └──────────────────────────────────────────────────────┘   │   │
│  │                                                              │   │
│  │  ┌─ Last LLM Response ─────────────────────── [Copy] ───┐   │   │
│  │  │ { "text": "I can see a gap...",                      │   │   │
│  │  │   "tool_calls": [{"name": "add_tubercle", ...}],     │   │   │
│  │  │   "usage": {"input": 12345, "output": 567} }         │   │   │
│  │  └──────────────────────────────────────────────────────┘   │   │
│  │                                                              │   │
│  │  ┌─ Action Summary ───────────────────── [Copy] [Clear] ┐   │   │
│  │  │ [14:32:05] Started pattern completion                │   │   │
│  │  │ [14:32:08] Screenshot captured (2048x1536)           │   │   │
│  │  │ [14:32:15] Added tubercle at (456, 234)              │   │   │
│  │  │ [14:32:18] Added tubercle at (512, 289)              │   │   │
│  │  │ [14:32:22] Hexagonalness: 0.612 → 0.645 (+0.033)     │   │   │
│  │  │ ...                                                  │   │   │
│  │  └──────────────────────────────────────────────────────┘   │   │
│  │                                                              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Collapsible Sections

All sections (Status, Costs, Progress Chart, LLM Communication) should be collapsible with state persisted to `localStorage`:
- Key: `agenticEditSection_{sectionName}_collapsed`
- Default: Status expanded, others collapsed

---

## Backend Architecture

### New API Endpoints

Add to `src/fish_scale_ui/routes/agent_api.py`:

#### `POST /api/agent/edit/start`

Start the pattern completion agent as a subprocess.

**Request:**
```json
{
    "provider": "claude",           // Required: claude|gemini|openrouter
    "model": "claude-sonnet-4-20250514",  // Optional: specific model
    "max_iterations": 30,           // Optional, default 30
    "plateau_threshold": 3,         // Optional, default 3 - stop after N iterations without improvement
    "auto_connect": true,           // Optional, default true
    "auto_connect_method": "gabriel", // Optional: delaunay|gabriel|rng
    "cleanup_boundary": true,       // Optional, default true
    "verbose": true                 // Optional, default true
}
```

**Response:**
```json
{
    "success": true,
    "session_id": "edit-abc123",
    "status_file": "/tmp/agent_edit_abc123_status.json"
}
```

#### `GET /api/agent/edit/status/<session_id>`

Get current status from the running agent.

**Response:**
```json
{
    "success": true,
    "state": "running",             // starting|running|completed|stopped|failed
    "phase": "pattern_completion",  // phase name
    "iteration": 12,
    "max_iterations": 30,
    "tubercle_count": 47,
    "tubercle_delta": 12,           // +/- since start
    "itc_count": 89,
    "hexagonalness": 0.682,
    "coverage_percent": 85,         // estimated area coverage
    "plateau_count": 0,             // iterations since last improvement
    "plateau_threshold": 3,
    "elapsed_seconds": 154,
    "step_time_seconds": 8.2,
    "log_lines": ["[14:32:05] ...", "..."],
    "last_prompt": "{ ... }",       // JSON string, base64 truncated
    "last_response": "{ ... }",     // JSON string
    "costs": {
        "provider": "claude",
        "model": "claude-sonnet-4-20250514",
        "input_tokens": 125432,
        "output_tokens": 3891,
        "estimated_cost": 0.43,
        "last_step_cost": 0.038
    }
}
```

#### `POST /api/agent/edit/stop/<session_id>`

Stop the running agent.

**Response:**
```json
{
    "success": true,
    "final_hexagonalness": 0.682,
    "tubercles_added": 12,
    "tubercles_deleted": 2
}
```

### Agent CLI Command

Add `edit` subcommand to `fish-scale-agent`:

```bash
uv run fish-scale-agent edit <image> \
    --calibration 0.1 \
    --provider claude \
    --model claude-sonnet-4-20250514 \
    --max-iterations 30 \
    --plateau-threshold 3 \
    --auto-connect \
    --auto-connect-method gabriel \
    --cleanup-boundary \
    --ui-url http://localhost:5010 \
    -v
```

### Agent Implementation

Create `src/fish_scale_agent/editing_agent.py`:

```python
class EditingAgent:
    """LLM-driven pattern completion agent."""

    def __init__(
        self,
        provider: AgentLLMProvider,
        ui_url: str = "http://localhost:5010",
        verbose: bool = False,
    ):
        self.provider = provider
        self.ui_url = ui_url
        self.verbose = verbose
        self.http = httpx.Client(base_url=ui_url, timeout=60.0)

    async def run(
        self,
        max_iterations: int = 30,
        plateau_threshold: int = 3,
        auto_connect: bool = True,
        auto_connect_method: str = "gabriel",
        cleanup_boundary: bool = True,
    ) -> EditingResult:
        """Run the pattern completion agent loop.

        Continues until:
        - max_iterations reached, OR
        - plateau_threshold consecutive iterations without improvement
        """
        ...
```

---

## Agent Tools

The editing agent needs a focused subset of tools for pattern completion:

### Primary Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_screenshot` | Capture current view with overlay | `overlay: bool`, `numbers: bool` |
| `get_state` | Get current tubercle/edge counts and hexagonalness | - |
| `add_tubercle` | Add a tubercle at pixel coordinates | `x: float`, `y: float`, `radius?: float` |
| `delete_tubercle` | Remove a tubercle by ID | `id: int` |
| `move_tubercle` | Reposition a tubercle | `id: int`, `x: float`, `y: float` |
| `auto_connect` | Generate connections | `method: str` |
| `get_statistics` | Get detailed metrics including hexagonalness | - |
| `finish` | Signal completion and stop the loop | `reason: str` |

### Tool Definitions

```python
EDITING_TOOLS = [
    ToolDefinition(
        name="get_screenshot",
        description="""Capture the current image view with tubercle overlay.

Returns a PNG image showing:
- The SEM image of the fish scale
- Detected tubercles as colored circles (cyan = extracted, green = manual)
- Connection lines between neighboring tubercles (if any)

Use this to visually analyze the pattern and identify gaps.""",
        parameters={
            "type": "object",
            "properties": {
                "overlay": {
                    "type": "boolean",
                    "description": "Show tubercle circles and connections (default: true)",
                    "default": True,
                },
                "numbers": {
                    "type": "boolean",
                    "description": "Show tubercle ID numbers (default: false)",
                    "default": False,
                },
            },
        },
    ),

    ToolDefinition(
        name="get_state",
        description="""Get the current state including tubercle count, edge count, hexagonalness, and coverage.

Returns:
- tubercle_count: Number of detected tubercles
- edge_count: Number of connections
- hexagonalness: Score from 0-1 measuring pattern regularity
- hexagonalness_components: Breakdown of spacing/degree/edge_ratio scores
- coverage_percent: Estimated percentage of scale area covered by detections
- image_dimensions: Width and height in pixels""",
        parameters={"type": "object", "properties": {}},
    ),

    ToolDefinition(
        name="add_tubercle",
        description="""Add a new tubercle at the specified pixel coordinates.

IMPORTANT:
- Coordinates are in IMAGE pixels, not screen pixels
- Use get_screenshot to determine where to add
- The radius is auto-calculated from existing tubercles if not provided
- Only add tubercles where you see BRIGHT circular spots
- Do NOT add in dark/black background areas

Returns the created tubercle with its ID.""",
        parameters={
            "type": "object",
            "properties": {
                "x": {
                    "type": "number",
                    "description": "X coordinate in image pixels",
                },
                "y": {
                    "type": "number",
                    "description": "Y coordinate in image pixels",
                },
                "radius": {
                    "type": "number",
                    "description": "Radius in pixels (auto-calculated if not provided)",
                },
            },
            "required": ["x", "y"],
        },
    ),

    ToolDefinition(
        name="delete_tubercle",
        description="""Delete a tubercle by its ID.

Use this to remove:
- False positives (detections that aren't real tubercles)
- Edge tubercles that hurt hexagonalness
- Duplicates or overlapping detections

WARNING: This also removes all connections to the deleted tubercle.""",
        parameters={
            "type": "object",
            "properties": {
                "id": {
                    "type": "integer",
                    "description": "ID of the tubercle to delete",
                },
            },
            "required": ["id"],
        },
    ),

    ToolDefinition(
        name="move_tubercle",
        description="""Move a tubercle to new coordinates.

Use this to:
- Correct slightly misaligned tubercle positions
- Center a tubercle on its actual location""",
        parameters={
            "type": "object",
            "properties": {
                "id": {
                    "type": "integer",
                    "description": "ID of the tubercle to move",
                },
                "x": {
                    "type": "number",
                    "description": "New X coordinate in image pixels",
                },
                "y": {
                    "type": "number",
                    "description": "New Y coordinate in image pixels",
                },
            },
            "required": ["id", "x", "y"],
        },
    ),

    ToolDefinition(
        name="auto_connect",
        description="""Generate connections between tubercles using a graph algorithm.

Methods:
- delaunay: All Delaunay triangulation edges (most connections)
- gabriel: Gabriel graph - removes edges with empty diametral circle (recommended)
- rng: Relative Neighborhood Graph (fewest connections)

Typically called after adding all tubercles to establish the neighbor graph.""",
        parameters={
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["delaunay", "gabriel", "rng"],
                    "description": "Graph algorithm to use (default: gabriel)",
                    "default": "gabriel",
                },
            },
        },
    ),

    ToolDefinition(
        name="get_statistics",
        description="""Get detailed measurement statistics.

Returns:
- Tubercle statistics: count, mean/std/min/max diameter
- Edge statistics: count, mean/std/min/max spacing
- Hexagonalness: overall score and component breakdown
- Degree distribution: histogram of neighbor counts""",
        parameters={"type": "object", "properties": {}},
    ),

    ToolDefinition(
        name="finish",
        description="""Signal that the pattern completion is done.

Call this when:
- The pattern appears visually complete (all visible tubercles detected)
- Good area coverage has been achieved
- Further additions would not improve hexagonalness or coverage
- You've determined the image quality prevents better results
- No more gaps are visible in the pattern

The agent will also auto-stop after plateau_threshold iterations without improvement.""",
        parameters={
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Brief explanation of why you're finishing",
                },
            },
            "required": ["reason"],
        },
    ),
]
```

---

## System Prompt

Create `EDITING_AGENT_SYSTEM_PROMPT` in `src/fish_scale_agent/prompts.py`:

```python
EDITING_AGENT_SYSTEM_PROMPT = """You are an expert at analyzing SEM (Scanning Electron Microscope) images of ganoid fish scales and identifying tubercle patterns.

## Your Task

You are working with a partially-detected set of tubercles on a fish scale image. Your goals are:

1. **High area coverage** - Detect ALL visible tubercles in the scale area
2. **High hexagonalness** - Ensure the pattern forms a regular hexagonal lattice
3. **No false positives** - Only mark actual tubercles, not noise or artifacts

Continue working until you cannot make any more meaningful improvements. The system will auto-stop after {plateau_threshold} iterations without improvement.

## Understanding the Image

Fish scale tubercles appear as:
- BRIGHT circular/oval spots on a darker background
- Arranged in a roughly hexagonal (honeycomb) pattern
- Each tubercle should have approximately 5-7 neighbors
- Spacing between tubercles is roughly uniform

The overlay shows:
- CYAN circles = automatically extracted tubercles
- GREEN circles = manually added tubercles
- LINES = connections between neighboring tubercles

## Quality Metrics

### Hexagonalness Score (0-1)

Measures pattern regularity:

```
Hexagonalness = 0.40 × Spacing Uniformity + 0.45 × Degree Score + 0.15 × Edge Ratio
```

Components:
- **Spacing Uniformity (40%)**: How consistent are the edge lengths? Lower CV = higher score
- **Degree Score (45%)**: Do tubercles have 5-7 neighbors? (optimal for hexagons)
- **Edge Ratio (15%)**: Is the edge/node ratio close to 2.5? (ideal for hexagonal lattice)

### Area Coverage

Measures completeness - what percentage of the visible scale area has been annotated. Higher coverage means fewer missed tubercles. Look for:
- Gaps in the interior of the pattern
- Edge regions where tubercles may have been missed
- Corners that may not have been fully analyzed

**Coverage Calculation**: Coverage is estimated using the convex hull of detected tubercles:
```
coverage_percent = (convex_hull_area / total_scale_area) × density_factor
```
Where `density_factor` accounts for expected spacing based on mean tubercle diameter.

This is an approximation - the LLM should use visual inspection as the primary guide for completeness.

## Strategy

### Phase 1: Visual Assessment
1. Get a screenshot with overlay to see current state
2. Get statistics to know current hexagonalness and counts
3. Identify the scale area vs. background (don't add in black areas!)
4. Identify obvious gaps in the hexagonal pattern

### Phase 2: Pattern Completion
For each iteration:
1. Get a screenshot to see current state
2. Identify 1-3 locations where tubercles are missing
3. For each missing tubercle:
   - Estimate coordinates based on neighboring pattern
   - Verify the location shows a bright spot (real tubercle)
   - Call add_tubercle(x, y)
4. Check hexagonalness after each batch of additions
5. If score decreased, consider deleting the last additions

### Phase 3: Refinement
1. Look for false positives (circles where there's no bright spot)
2. Look for edge tubercles with only 1-2 neighbors (hurt degree score)
3. Consider deleting these if it would improve hexagonalness
4. Run auto_connect with gabriel method to regenerate connections

### Phase 4: Completion

Call `finish()` when ANY of these conditions are met:
1. All visible tubercles have been detected (good coverage)
2. The hexagonal pattern is complete with no obvious gaps
3. Further additions don't improve hexagonalness (diminishing returns)
4. Image quality prevents better detection

The system will also auto-stop after {plateau_threshold} iterations without improvement.

## Important Guidelines

1. **ALWAYS get a screenshot first** before deciding where to add tubercles
2. **Use image pixel coordinates** - the screenshot dimensions tell you the coordinate range
3. **Only add where you see bright spots** - don't add in dark background areas
4. **Maximize coverage** - scan the entire image, including edges and corners
5. **Check progress frequently** - get_state after every few additions
6. **Don't over-add** - adding false positives hurts both hexagonalness and data quality
7. **Work systematically** - scan left-to-right or top-to-bottom to ensure full coverage
8. **Continue until complete** - don't stop early if there are still visible gaps

## Coordinate System

- Origin (0, 0) is TOP-LEFT of the image
- X increases to the RIGHT
- Y increases DOWNWARD
- Typical image size: 1500-2500 pixels in each dimension
- Screenshot dimensions are provided with each capture

## Example Workflow

```
1. get_screenshot() → See image with 35 detected tubercles
2. get_state() → hexagonalness: 0.58, coverage: 60%, tubercles: 35
3. Analyze: "I see gaps in the upper-left corner and center region"
4. add_tubercle(x=450, y=300) → Added tubercle #36
5. add_tubercle(x=520, y=350) → Added tubercle #37
6. add_tubercle(x=480, y=400) → Added tubercle #38
7. get_state() → hexagonalness: 0.64, coverage: 68%, tubercles: 38 (improved!)
8. get_screenshot() → Verify additions look correct, scan for more gaps
9. Continue scanning all regions systematically
10. get_state() → hexagonalness: 0.72, coverage: 92%, tubercles: 52
11. get_screenshot() → No more obvious gaps visible
12. auto_connect(method="gabriel") → Generate final connections
13. finish(reason="Pattern complete - all visible tubercles detected, coverage 92%")
```

## Current Session Info

- Image: {image_name}
- Dimensions: {image_width} x {image_height} pixels
- Calibration: {calibration} µm/pixel
- Starting tubercles: {initial_tubercle_count}
- Starting hexagonalness: {initial_hexagonalness}
- Starting coverage: {initial_coverage}%
- Max iterations: {max_iterations}
- Plateau threshold: {plateau_threshold} iterations
"""
```

---

## Frontend Implementation

### File: `src/fish_scale_ui/static/js/agent_editing.js`

```javascript
/**
 * AgenticEdit tab controller
 * Manages the LLM-driven pattern completion workflow
 */

const agentEditing = (function() {
    'use strict';

    // State
    const state = {
        isRunning: false,
        sessionId: null,
        currentIteration: 0,
        maxIterations: 30,
        plateauThreshold: 3,
        plateauCount: 0,
        initialTubercleCount: 0,
        currentTubercleCount: 0,
        initialHexagonalness: 0,
        currentHexagonalness: 0,
        initialCoverage: 0,
        currentCoverage: 0,
        startTime: null,
        pollingInterval: null,
        history: [],         // [{iteration, hexagonalness, coverage, tubercleCount}]
        actionSummary: [],   // User-facing action log
        costs: {
            provider: null,
            model: null,
            inputTokens: 0,
            outputTokens: 0,
            estimatedCost: 0,
            lastStepCost: 0,
        },
        lastPrompt: null,
        lastResponse: null,
    };

    // DOM Elements
    let elements = {};

    /**
     * Initialize the module
     */
    function init() {
        // Cache DOM elements
        elements = {
            // Configuration
            provider: document.getElementById('editAgentProvider'),
            model: document.getElementById('editAgentModel'),
            maxIterations: document.getElementById('editAgentMaxIterations'),
            plateauThreshold: document.getElementById('editAgentPlateauThreshold'),
            autoConnect: document.getElementById('editAgentAutoConnect'),
            autoConnectMethod: document.getElementById('editAgentAutoConnectMethod'),
            cleanupBoundary: document.getElementById('editAgentCleanupBoundary'),

            // Control buttons
            startBtn: document.getElementById('startEditAgentBtn'),
            stopBtn: document.getElementById('stopEditAgentBtn'),
            resetBtn: document.getElementById('resetEditAgentBtn'),
            acceptBtn: document.getElementById('acceptEditResultBtn'),

            // Status display
            stateDisplay: document.getElementById('editAgentState'),
            phaseDisplay: document.getElementById('editAgentPhase'),
            iterationDisplay: document.getElementById('editAgentIteration'),
            tubercleDisplay: document.getElementById('editAgentTubercleCount'),
            hexDisplay: document.getElementById('editAgentHexagonalness'),
            coverageDisplay: document.getElementById('editAgentCoverage'),
            elapsedDisplay: document.getElementById('editAgentElapsed'),
            plateauDisplay: document.getElementById('editAgentPlateau'),

            // Cost display
            costModel: document.getElementById('editAgentCostModel'),
            costInput: document.getElementById('editAgentCostInputTokens'),
            costOutput: document.getElementById('editAgentCostOutputTokens'),
            costEstimate: document.getElementById('editAgentCostEstimate'),
            costLastStep: document.getElementById('editAgentCostLastStep'),

            // Chart
            chartCanvas: document.getElementById('editAgentChart'),

            // LLM Communication
            promptDisplay: document.getElementById('editAgentPrompt'),
            responseDisplay: document.getElementById('editAgentResponse'),
            actionLog: document.getElementById('editAgentActionLog'),
        };

        // Setup event listeners
        setupEventListeners();

        // Load providers
        loadProviders();

        // Restore collapsed section states
        restoreCollapsedStates();
    }

    /**
     * Setup event listeners
     */
    function setupEventListeners() {
        elements.provider?.addEventListener('change', onProviderChange);
        elements.startBtn?.addEventListener('click', startAgent);
        elements.stopBtn?.addEventListener('click', stopAgent);
        elements.resetBtn?.addEventListener('click', reset);
        elements.acceptBtn?.addEventListener('click', acceptResult);

        // Collapsible section toggles
        document.querySelectorAll('.edit-agent-section-toggle').forEach(toggle => {
            toggle.addEventListener('click', () => toggleSection(toggle));
        });

        // Copy buttons
        document.getElementById('copyEditPromptBtn')?.addEventListener('click', () => {
            copyToClipboard(state.lastPrompt, 'Prompt copied');
        });
        document.getElementById('copyEditResponseBtn')?.addEventListener('click', () => {
            copyToClipboard(state.lastResponse, 'Response copied');
        });
        document.getElementById('copyEditActionsBtn')?.addEventListener('click', () => {
            copyToClipboard(state.actionSummary.join('\n'), 'Actions copied');
        });
        document.getElementById('clearEditActionsBtn')?.addEventListener('click', clearActionLog);
    }

    /**
     * Load available providers
     */
    async function loadProviders() {
        try {
            const response = await fetch('/api/agent/providers');
            const data = await response.json();

            if (data.providers) {
                populateProviderSelect(data.providers);
            }
        } catch (error) {
            console.error('Failed to load providers:', error);
        }
    }

    /**
     * Start the editing agent
     */
    async function startAgent() {
        // Validate prerequisites
        if (!validatePrerequisites()) {
            return;
        }

        // Get configuration
        const config = {
            provider: elements.provider.value,
            model: elements.model.value || undefined,
            max_iterations: parseInt(elements.maxIterations.value) || 30,
            plateau_threshold: parseInt(elements.plateauThreshold.value) || 3,
            auto_connect: elements.autoConnect.checked,
            auto_connect_method: elements.autoConnectMethod.value,
            cleanup_boundary: elements.cleanupBoundary.checked,
            verbose: true,
        };

        // Record initial state
        const stats = await getStatistics();
        state.initialTubercleCount = stats?.tubercle_count || 0;
        state.initialHexagonalness = stats?.hexagonalness || 0;
        state.initialCoverage = stats?.coverage_percent || 0;
        state.maxIterations = config.max_iterations;
        state.plateauThreshold = config.plateau_threshold;

        try {
            const response = await fetch('/api/agent/edit/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config),
            });

            const data = await response.json();

            if (data.success) {
                state.isRunning = true;
                state.sessionId = data.session_id;
                state.startTime = Date.now();

                updateButtonStates();
                addAction('Started pattern completion agent');
                startPolling();
            } else {
                window.app?.showToast(data.error || 'Failed to start agent', 'error');
            }
        } catch (error) {
            console.error('Failed to start agent:', error);
            window.app?.showToast('Failed to start agent', 'error');
        }
    }

    /**
     * Stop the running agent
     */
    async function stopAgent() {
        if (!state.sessionId) return;

        try {
            await fetch(`/api/agent/edit/stop/${state.sessionId}`, {
                method: 'POST',
            });

            state.isRunning = false;
            stopPolling();
            updateButtonStates();
            addAction('Agent stopped by user');
        } catch (error) {
            console.error('Failed to stop agent:', error);
        }
    }

    /**
     * Poll for status updates
     */
    function startPolling() {
        state.pollingInterval = setInterval(pollStatus, 1000);
    }

    function stopPolling() {
        if (state.pollingInterval) {
            clearInterval(state.pollingInterval);
            state.pollingInterval = null;
        }
    }

    async function pollStatus() {
        if (!state.sessionId) return;

        try {
            const response = await fetch(`/api/agent/edit/status/${state.sessionId}`);
            const data = await response.json();

            if (data.success) {
                updateStatus(data);

                // Check for completion
                if (data.state === 'completed' || data.state === 'stopped' || data.state === 'failed') {
                    state.isRunning = false;
                    stopPolling();
                    updateButtonStates();
                    addAction(`Agent ${data.state}: ${data.reason || ''}`);

                    // Refresh the overlay to show final state
                    window.overlay?.refresh();
                }
            }
        } catch (error) {
            console.error('Status poll failed:', error);
        }
    }

    /**
     * Update UI with status data
     */
    function updateStatus(data) {
        // Update state
        state.currentIteration = data.iteration || 0;
        state.currentTubercleCount = data.tubercle_count || 0;
        state.currentHexagonalness = data.hexagonalness || 0;
        state.currentCoverage = data.coverage_percent || 0;
        state.plateauCount = data.plateau_count || 0;

        // Update displays
        elements.stateDisplay.textContent = data.state || 'unknown';
        elements.phaseDisplay.textContent = data.phase || '-';
        elements.iterationDisplay.textContent = `${data.iteration || 0}/${state.maxIterations}`;

        const delta = state.currentTubercleCount - state.initialTubercleCount;
        const deltaStr = delta >= 0 ? `+${delta}` : `${delta}`;
        elements.tubercleDisplay.textContent = `${state.currentTubercleCount} (${deltaStr})`;

        elements.hexDisplay.textContent = (data.hexagonalness || 0).toFixed(3);
        elements.coverageDisplay.textContent = `${(data.coverage_percent || 0).toFixed(0)}%`;

        // Elapsed time
        if (state.startTime) {
            const elapsed = Math.floor((Date.now() - state.startTime) / 1000);
            elements.elapsedDisplay.textContent = formatTime(elapsed);
        }

        // Plateau counter
        elements.plateauDisplay.textContent = `${state.plateauCount}/${state.plateauThreshold}`;

        // Update costs
        if (data.costs) {
            updateCosts(data.costs);
        }

        // Update LLM communication
        if (data.last_prompt) {
            state.lastPrompt = data.last_prompt;
            elements.promptDisplay.textContent = truncateBase64(data.last_prompt);
        }
        if (data.last_response) {
            state.lastResponse = data.last_response;
            elements.responseDisplay.textContent = data.last_response;
        }

        // Add to history and update chart
        state.history.push({
            iteration: data.iteration,
            hexagonalness: data.hexagonalness,
            coverage: data.coverage_percent,
            tubercleCount: data.tubercle_count,
        });
        updateChart();

        // Parse action log from log_lines
        if (data.log_lines) {
            parseLogLines(data.log_lines);
        }
    }

    /**
     * Update the progress chart
     */
    function updateChart() {
        const canvas = elements.chartCanvas;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;

        // Clear
        ctx.clearRect(0, 0, width, height);

        if (state.history.length < 2) return;

        // Draw hexagonalness line chart
        const padding = 40;
        const chartWidth = width - padding * 2;
        const chartHeight = height - padding * 2;

        const minY = 0;
        const maxY = 1;
        const maxX = state.maxIterations;

        ctx.strokeStyle = '#4CAF50';
        ctx.lineWidth = 2;
        ctx.beginPath();

        // Draw hexagonalness line (green)
        state.history.forEach((point, i) => {
            const x = padding + (point.iteration / maxX) * chartWidth;
            const y = padding + chartHeight - ((point.hexagonalness - minY) / (maxY - minY)) * chartHeight;

            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        });
        ctx.stroke();

        // Draw coverage line (blue)
        ctx.strokeStyle = '#2196F3';
        ctx.lineWidth = 2;
        ctx.beginPath();
        state.history.forEach((point, i) => {
            const x = padding + (point.iteration / maxX) * chartWidth;
            const y = padding + chartHeight - (((point.coverage || 0) / 100 - minY) / (maxY - minY)) * chartHeight;

            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        });
        ctx.stroke();

        // Labels
        ctx.fillStyle = '#888';
        ctx.font = '10px monospace';
        ctx.fillText('Iteration', width - 50, height - 5);

        // Legend
        ctx.fillStyle = '#4CAF50';
        ctx.fillText('Hexagonalness', 5, 12);
        ctx.fillStyle = '#2196F3';
        ctx.fillText('Coverage', 5, 24);
    }

    // ... Additional helper functions ...

    return {
        init,
        startAgent,
        stopAgent,
        reset,
        getState: () => state,
    };
})();

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    agentEditing.init();
});
```

---

## HTML Template Addition

Add to `src/fish_scale_ui/templates/workspace.html` in the tabs section:

```html
<!-- AgenticEdit Tab (hidden by default, enabled via env var) -->
{% if config.agent_tabs_enabled and ('editing' in config.agent_tabs or config.agent_tabs == '1') %}
<div id="tab-agentic-edit" class="tab-content">
    <div class="tab-scroll-container">

        <!-- Configuration Section -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">Configuration</span>
            </div>
            <div class="panel-body">
                <div class="form-row">
                    <div class="form-group">
                        <label for="editAgentProvider">Provider</label>
                        <select id="editAgentProvider" class="form-control">
                            <option value="">Select provider...</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="editAgentModel">Model</label>
                        <select id="editAgentModel" class="form-control">
                            <option value="">Default</option>
                        </select>
                        <small id="editAgentModelPricing" class="text-muted"></small>
                    </div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label for="editAgentMaxIterations">Max Iterations</label>
                        <input type="number" id="editAgentMaxIterations" class="form-control"
                               value="30" min="5" max="50" step="5">
                    </div>
                    <div class="form-group">
                        <label for="editAgentPlateauThreshold">Plateau Threshold</label>
                        <input type="number" id="editAgentPlateauThreshold" class="form-control"
                               value="3" min="1" max="10" step="1">
                        <small class="text-muted">Stop after N iterations without improvement</small>
                    </div>
                </div>

                <div class="form-row">
                    <div class="form-group checkbox-group">
                        <label>
                            <input type="checkbox" id="editAgentAutoConnect" checked>
                            Auto-connect after completion
                        </label>
                        <select id="editAgentAutoConnectMethod" class="form-control form-control-sm">
                            <option value="gabriel" selected>Gabriel graph</option>
                            <option value="delaunay">Delaunay</option>
                            <option value="rng">RNG</option>
                        </select>
                    </div>
                    <div class="form-group checkbox-group">
                        <label>
                            <input type="checkbox" id="editAgentCleanupBoundary" checked>
                            Delete boundary tubercles
                        </label>
                    </div>
                </div>
            </div>
        </div>

        <!-- Control Buttons -->
        <div class="panel">
            <div class="panel-body button-row">
                <button id="startEditAgentBtn" class="btn btn-primary">
                    <span class="icon">▶</span> Start
                </button>
                <button id="stopEditAgentBtn" class="btn btn-danger" disabled>
                    <span class="icon">■</span> Stop
                </button>
                <button id="resetEditAgentBtn" class="btn btn-secondary">
                    <span class="icon">↺</span> Reset
                </button>
                <button id="acceptEditResultBtn" class="btn btn-success" disabled>
                    <span class="icon">✓</span> Accept Result
                </button>
            </div>
        </div>

        <!-- Status Section (collapsible) -->
        <div class="panel collapsible">
            <div class="panel-header edit-agent-section-toggle" data-section="status">
                <span class="panel-title">Status</span>
                <span class="collapse-icon">▼</span>
            </div>
            <div class="panel-body" id="editAgentStatusBody">
                <div class="status-grid">
                    <div class="status-item">
                        <label>State</label>
                        <span id="editAgentState">Idle</span>
                    </div>
                    <div class="status-item">
                        <label>Phase</label>
                        <span id="editAgentPhase">-</span>
                    </div>
                    <div class="status-item">
                        <label>Iteration</label>
                        <span id="editAgentIteration">0/30</span>
                    </div>
                    <div class="status-item">
                        <label>Tubercles</label>
                        <span id="editAgentTubercleCount">0</span>
                    </div>
                    <div class="status-item">
                        <label>Hexagonalness</label>
                        <span id="editAgentHexagonalness">0.000</span>
                    </div>
                    <div class="status-item">
                        <label>Coverage</label>
                        <span id="editAgentCoverage">0%</span>
                    </div>
                    <div class="status-item">
                        <label>Elapsed</label>
                        <span id="editAgentElapsed">0:00</span>
                    </div>
                    <div class="status-item">
                        <label>Plateau</label>
                        <span id="editAgentPlateau">0/3</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Costs Section (collapsible) -->
        <div class="panel collapsible">
            <div class="panel-header edit-agent-section-toggle" data-section="costs">
                <span class="panel-title">Costs</span>
                <span class="collapse-icon">▶</span>
            </div>
            <div class="panel-body collapsed" id="editAgentCostsBody">
                <div class="costs-grid">
                    <div class="cost-item">
                        <label>Model</label>
                        <span id="editAgentCostModel">-</span>
                    </div>
                    <div class="cost-item">
                        <label>Input Tokens</label>
                        <span id="editAgentCostInputTokens">0</span>
                    </div>
                    <div class="cost-item">
                        <label>Output Tokens</label>
                        <span id="editAgentCostOutputTokens">0</span>
                    </div>
                    <div class="cost-item">
                        <label>Estimated Cost</label>
                        <span id="editAgentCostEstimate">$0.00</span>
                    </div>
                    <div class="cost-item">
                        <label>Last Step</label>
                        <span id="editAgentCostLastStep">$0.00</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Progress Chart (collapsible) -->
        <div class="panel collapsible">
            <div class="panel-header edit-agent-section-toggle" data-section="chart">
                <span class="panel-title">Progress Chart</span>
                <span class="collapse-icon">▶</span>
            </div>
            <div class="panel-body collapsed" id="editAgentChartBody">
                <canvas id="editAgentChart" width="400" height="200"></canvas>
            </div>
        </div>

        <!-- LLM Communication (collapsible) -->
        <div class="panel collapsible">
            <div class="panel-header edit-agent-section-toggle" data-section="llm">
                <span class="panel-title">LLM Communication</span>
                <span class="collapse-icon">▶</span>
            </div>
            <div class="panel-body collapsed" id="editAgentLLMBody">
                <div class="llm-section">
                    <div class="llm-header">
                        <span>Last Prompt Sent</span>
                        <button id="copyEditPromptBtn" class="btn btn-sm">Copy</button>
                    </div>
                    <pre id="editAgentPrompt" class="llm-content"></pre>
                </div>

                <div class="llm-section">
                    <div class="llm-header">
                        <span>Last LLM Response</span>
                        <button id="copyEditResponseBtn" class="btn btn-sm">Copy</button>
                    </div>
                    <pre id="editAgentResponse" class="llm-content"></pre>
                </div>

                <div class="llm-section">
                    <div class="llm-header">
                        <span>Action Summary</span>
                        <button id="copyEditActionsBtn" class="btn btn-sm">Copy</button>
                        <button id="clearEditActionsBtn" class="btn btn-sm">Clear</button>
                    </div>
                    <textarea id="editAgentActionLog" class="action-log" readonly></textarea>
                </div>
            </div>
        </div>

    </div>
</div>
{% endif %}
```

---

## Status Line Output Format

The agent subprocess outputs structured `STATUS:` lines for the backend monitor:

```
STATUS: {"iteration": 12, "max_iterations": 30, "phase": "pattern_completion", "hexagonalness": 0.682, "coverage_percent": 85, "tubercles": 47, "edges": 89, "plateau_count": 0, "action": "add_tubercle", "x": 456, "y": 234}
```

Log line formats:
```
[HH:MM:SS] Started pattern completion (max_iter: 30, plateau: 3)
[HH:MM:SS] Screenshot captured (2048x1536)
[HH:MM:SS] Added tubercle #47 at (456, 234)
[HH:MM:SS] Deleted tubercle #23 (false positive)
[HH:MM:SS] Hexagonalness: 0.612 → 0.645, Coverage: 78% → 82%
[HH:MM:SS] Plateau: 0/3 (improved)
[HH:MM:SS] Plateau: 2/3 (no change)
[HH:MM:SS] Usage: 12345 input, 567 output, $0.0234 (claude-sonnet-4-20250514)
[HH:MM:SS] LLM-Prompt: { ... }
[HH:MM:SS] LLM-Response: { ... }
[HH:MM:SS] Finished: Pattern complete, coverage 92%
```

---

## File Changes Summary

### New Files

| File | Description |
|------|-------------|
| `src/fish_scale_agent/editing_agent.py` | Core editing agent class |
| `src/fish_scale_ui/static/js/agent_editing.js` | Frontend controller |

### Modified Files

| File | Changes |
|------|---------|
| `src/fish_scale_agent/cli.py` | Add `edit` subcommand |
| `src/fish_scale_agent/prompts.py` | Add `EDITING_AGENT_SYSTEM_PROMPT` |
| `src/fish_scale_ui/routes/agent_api.py` | Add `/api/agent/edit/*` endpoints |
| `src/fish_scale_ui/templates/workspace.html` | Add AgenticEdit tab HTML |
| `src/fish_scale_ui/static/css/main.css` | Styles for AgenticEdit tab (if needed) |
| `src/fish_scale_ui/app.py` | Parse `FISH_SCALE_AGENT_TABS` for editing |

---

## Testing Plan

### Unit Tests

1. **Agent class tests** (`tests/test_editing_agent.py`):
   - Test tool execution mappings
   - Test prompt generation
   - Test stopping conditions

2. **API endpoint tests** (`tests/test_agent_edit_api.py`):
   - Test `/api/agent/edit/start` with various configs
   - Test `/api/agent/edit/status` response format
   - Test `/api/agent/edit/stop` cleanup

### Integration Tests

1. **End-to-end agent run**:
   - Start agent on test image
   - Verify tubercles are added
   - Verify hexagonalness and coverage improve
   - Verify agent stops after plateau threshold reached

2. **UI integration**:
   - Test tab visibility with env var
   - Test provider/model selection
   - Test status polling and display updates

### Manual Testing Checklist

- [ ] Tab appears when `FISH_SCALE_AGENT_TABS=editing`
- [ ] Provider dropdown populates correctly
- [ ] Model dropdown updates when provider changes
- [ ] Start button disabled when no image loaded
- [ ] Start button disabled when no calibration set
- [ ] Progress chart updates during run
- [ ] Costs accumulate correctly
- [ ] Stop button terminates agent
- [ ] Overlay updates in real-time as tubercles are added
- [ ] Final result can be saved

---

## Design Decisions

The following questions have been resolved with concrete recommendations:

### 1. Undo Integration
**Decision**: Do NOT add agent edits to the undo stack.

**Rationale**: Agent runs can add 20-50+ tubercles, which would create an unmanageable undo history. Instead:
- Agent creates a new annotation set before starting (preserving the original)
- User can switch back to the pre-agent set if unhappy with results
- The "Reset" button restores the original state

### 2. Real-time Overlay Updates
**Decision**: Update overlay in real-time after each `add_tubercle` call.

**Rationale**: Real-time feedback is essential for user confidence that the agent is working correctly. To prevent flickering:
- Use `requestAnimationFrame` for smooth updates
- Debounce rapid consecutive updates (max 10 updates/second)
- The overlay update is lightweight (just redrawing circles)

### 3. Boundary Cleanup
**Decision**: Delete tubercles with fewer than 2 neighbors after auto-connect.

**Rationale**:
- Tubercles with 0-1 neighbors are typically false positives at image edges
- Tubercles with 2 neighbors might be legitimate edge cases, but hurt hexagonalness significantly
- The LLM should make this decision per-tubercle based on visual inspection
- The checkbox enables/disables a post-processing pass that removes <2 neighbor tubercles

### 4. Multiple Runs
**Decision**: Each run modifies the current annotation set (no new set created).

**Rationale**:
- Creating a new set for each run would clutter the sets list
- User should manually save a new set before running if they want to preserve state
- The overlay shows changes in real-time so user can stop if unhappy
- A warning toast is shown if the current set has unsaved changes

### 5. Initial Extraction Requirement
**Decision**: Allow starting with zero tubercles, no warning needed.

**Rationale**:
- The agent is a visual pattern completion tool - it looks at the image and adds tubercles where it sees bright spots
- This works identically whether starting from 0 or 50 existing tubercles
- The API auto-calculates tubercle radius from image analysis, so no anchor points are needed for sizing
- Starting from scratch just means more tubercles to add (more iterations), not a different workflow

---

## Implementation Phases

### Phase 1: Core Agent (Backend) - COMPLETED (2026-01-14, v0.1.4)
- [x] Create `editing_agent.py` with tool definitions
- [x] Add `EDITING_AGENT_SYSTEM_PROMPT` to prompts.py
- [x] Add `edit` subcommand to CLI
- [x] Test agent via CLI

**Implementation Notes:**
- Created `src/fish_scale_agent/editing_agent.py` (~750 lines) with:
  - `EditingState` dataclass for tracking progress
  - `EDITING_TOOLS` list with 8 tool definitions
  - `EditingAgent` class with HTTP client, tool execution, coverage estimation
  - `StopEditing` exception for loop termination
  - Plateau detection for auto-stopping
- Added `EDITING_AGENT_SYSTEM_PROMPT` to `prompts.py` (~130 lines)
- Added `edit` subcommand to `cli.py` with `cmd_edit()` function
- Updated `__init__.py` to export: `EditingAgent`, `EditingState`, `EDITING_TOOLS`, `EDITING_AGENT_SYSTEM_PROMPT`
- Version updated to 0.1.4 in all 5 required files

**CLI Usage (available now):**
```bash
# Start UI first
uv run fish-scale-ui

# Run editing agent via CLI
uv run fish-scale-agent edit test_images/image.tif --calibration 0.1 -v
uv run fish-scale-agent edit --help  # See all options
```

### Phase 2: API Endpoints - COMPLETED (2026-01-14, v0.2.0)
- [x] Add `/api/agent/edit/start` endpoint
- [x] Add `/api/agent/edit/status/<session_id>` endpoint
- [x] Add `/api/agent/edit/stop/<session_id>` endpoint
- [x] Add subprocess monitoring with background thread

**Implementation Notes:**
- Added 3 edit agent endpoints to `agent_api.py`:
  - `POST /api/agent/edit/start` - Start editing agent subprocess
  - `GET /api/agent/edit/status/<session_id>` - Poll status
  - `POST /api/agent/edit/stop/<session_id>` - Stop agent
- Uses separate tracking dict `_running_edit_agents` with thread lock
- Parses STATUS, Usage, LLM-Prompt, LLM-Response lines from agent output
- Session IDs prefixed with "edit-" for disambiguation

### Phase 3: Frontend UI - COMPLETED (2026-01-14, v0.2.0)
- [x] Add HTML template for AgenticEdit tab
- [x] Create `agent_editing.js` module
- [x] Implement polling and status display
- [x] Add progress chart (dual-line: hexagonalness + coverage)

**Implementation Notes:**
- Created `static/js/agent_editing.js` (~900 lines) with:
  - Provider/model selection mirroring AgenticExtraction
  - Status polling every 1000ms
  - Progress chart showing hexagonalness (green) and coverage (blue)
  - Collapsible sections with localStorage persistence
  - LLM prompt/response display with copy buttons
  - Action summary log
  - Cost tracking (tokens + estimated cost)
- Updated `workspace.html`:
  - Full AgenticEdit tab implementation replacing placeholder
  - Tab button renamed from "Agent Editing" to "AgenticEdit"
  - Added script include for agent_editing.js
- Reuses existing CSS classes from AgenticExtraction tab

### Phase 4: Integration & Polish
- [ ] Test end-to-end workflow
- [ ] Verify CSS styling works
- [ ] Handle edge cases and errors
- [ ] Update CLAUDE.md documentation

---

## Version

When implementing this feature, increment the minor version (e.g., 0.2.0 → 0.3.0) since it adds significant new functionality.

- Phase 1 implementation: 0.1.3 → 0.1.4 (backend functionality without UI)
- Phase 2+3 implementation: 0.1.4 → 0.2.0 (API endpoints + frontend UI)
