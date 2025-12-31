# Extraction Parameter Optimization Agent Specification

**Status:** Proposed
**Created:** 31 December 2025
**Purpose:** Automated optimization of extraction parameters using LLM-guided iterative refinement.

---

## 1. Overview

### 1.1 Problem Statement

The current extraction workflow requires users to:
1. Manually select parameter profiles or adjust individual parameters
2. Run extraction and visually inspect results
3. Iterate until satisfied (often 5-15 attempts)

This is tedious and requires domain expertise to know which parameters affect what.

### 1.2 Proposed Solution

An LLM-powered agent that:
1. Starts with a baseline parameter set (profile or default)
2. Runs extraction and analyzes results (metrics + visual)
3. Reasons about what to adjust based on observed issues
4. Iterates until quality metrics plateau or reach acceptable thresholds
5. Returns the best parameter set found

### 1.3 Key Differentiator from Existing Agent

The **existing agent** (`fish-scale-agent`) focuses on:
- Phase 1: Conservative automated extraction
- Phase 2: **Manual tubercle addition** via LLM visual analysis
- Phase 3: Connection generation

The **proposed extraction agent** focuses on:
- **Parameter optimization only** - finding the best extraction settings
- No manual tubercle addition (that's a separate workflow)
- Purely optimizing what the automated extraction can achieve

These are complementary: the extraction agent finds optimal automated detection, then the existing agent could enhance it further with manual additions.

---

## 2. Architecture

### 2.1 High-Level Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Extraction Optimization Agent                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │  Start   │───▶│  Analyze │───▶│  Adjust  │───▶│ Evaluate │  │
│  │ Baseline │    │  Results │    │  Params  │    │ & Decide │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│       │                                               │          │
│       │              ◀────── iterate ──────────◀──────┘          │
│       │                                               │          │
│       │                                        ┌──────────┐      │
│       └─────────────────────────────────────▶ │  Return  │      │
│                                                │   Best   │      │
│                                                └──────────┘      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
            ┌─────────────────────────────────┐
            │         Fish Scale UI           │
            │  ┌─────────────────────────┐   │
            │  │   MCP API Endpoints     │   │
            │  │  /api/mcp/params        │   │
            │  │  /api/mcp/extract       │   │
            │  │  /api/mcp/screenshot    │   │
            │  │  /api/mcp/statistics    │   │
            │  └─────────────────────────┘   │
            └─────────────────────────────────┘
```

### 2.2 Components

#### 2.2.1 ExtractionOptimizer (New Module)

Location: `src/fish_scale_agent/extraction_optimizer.py`

```python
class ExtractionOptimizer:
    """Orchestrates parameter optimization via LLM agent."""

    def __init__(
        self,
        provider: AgentLLMProvider,
        ui_base_url: str = "http://localhost:5010",
    ):
        ...

    async def optimize(
        self,
        image_path: str,
        calibration: float,
        starting_profile: str = "default",
        target_hexagonalness: float = 0.7,
        max_iterations: int = 10,
        on_iteration: Callable[[OptimizationIteration], None] = None,
    ) -> OptimizationResult:
        """Run the optimization loop."""
        ...
```

#### 2.2.2 Tool Definitions

A minimal, focused tool set for parameter optimization:

| Tool | Description | Parameters |
|------|-------------|------------|
| `run_extraction` | Execute extraction with current params | None |
| `get_screenshot` | Capture visual state for analysis | `include_overlay: bool` |
| `get_metrics` | Get current quality metrics | None |
| `get_params` | Get current parameter values | None |
| `set_params` | Update extraction parameters | `{param: value, ...}` |
| `load_profile` | Load a preset profile | `profile_name: str` |
| `accept_result` | Signal satisfaction, stop iteration | `reason: str` |
| `get_history` | Get history of tried params and scores | None |

#### 2.2.3 Quality Metrics

The agent evaluates extraction quality using:

**Primary Metric: Hexagonalness Score (0-1)**
- Already implemented in the codebase
- Combines spacing uniformity, degree distribution, edge ratio
- Higher = better hexagonal pattern match

**Secondary Metrics:**
- `n_tubercles` - Count of detected tubercles
- `mean_diameter_um` - Average tubercle diameter
- `std_diameter_um` - Diameter variation (lower = more uniform)
- `mean_space_um` - Average intertubercular spacing
- `std_space_um` - Spacing variation
- `coverage_ratio` - Estimated fraction of visible tubercles detected

**Visual Analysis:**
- Obvious missed tubercles (gaps in pattern)
- False positives (circles on non-tubercle features)
- Edge effects (too many/few tubercles at image boundaries)
- Size appropriateness (detected circles match visible tubercle sizes)

### 2.3 Communication: MCP vs Direct API

**Decision: Use direct HTTP API calls (not MCP stdio transport)**

Rationale:
1. The existing agent infrastructure uses HTTP calls to the UI API
2. MCP stdio transport adds complexity without clear benefit here
3. OpenRouter/OpenAI tool calling works with any tool definitions
4. The UI already exposes all needed endpoints at `/api/mcp/*`

The agent defines "tools" as structured function descriptions for the LLM, then executes them via HTTP calls - exactly as the existing agent does.

---

## 3. Optimization Strategy

### 3.1 Two-Phase Approach

#### Phase 1: Profile Selection (Coarse Search)

1. Try 3-4 relevant profiles (e.g., default, species-specific, contrast variants)
2. Run extraction with each
3. Score each result
4. Select best as starting point

This quickly narrows the search space.

#### Phase 2: Parameter Fine-Tuning (Local Search)

1. Start from best profile params
2. LLM analyzes visual results and metrics
3. LLM proposes targeted adjustments (e.g., "lower threshold to catch more tubercles")
4. Run extraction, compare to previous best
5. Accept/reject adjustment, repeat

### 3.2 Parameter Effects (Domain Knowledge for Prompts)

| Parameter | Effect of Increasing | When to Increase |
|-----------|---------------------|------------------|
| `threshold` | Fewer detections, higher confidence | Too many false positives |
| `min_diameter_um` | Filters out small detections | Detecting noise/artifacts |
| `max_diameter_um` | Allows larger detections | Missing large tubercles |
| `min_circularity` | Requires rounder shapes | Detecting non-circular blobs |
| `clahe_clip` | More contrast enhancement | Low contrast images |
| `blur_sigma` | Smoother image, merged features | Too much noise |

### 3.3 Stopping Criteria

The agent stops when ANY of:

1. **Target achieved**: `hexagonalness_score >= target_hexagonalness`
2. **Plateau detected**: No improvement for 3 consecutive iterations
3. **Max iterations**: `iteration >= max_iterations`
4. **LLM decides**: Agent calls `accept_result` with reasoning

### 3.4 Avoiding Loops

The agent maintains a history of tried parameter sets and their scores. The prompt instructs:
- Don't retry exact parameter combinations
- Track which adjustments helped/hurt
- Prefer small adjustments to large jumps after initial exploration

---

## 4. LLM Provider Integration

### 4.1 OpenRouter as Primary Provider

OpenRouter provides:
- Access to many vision-capable models (Claude, GPT-4, Gemini, Llama, etc.)
- Unified API (OpenAI-compatible)
- Cost tracking per model
- Ability to experiment with different models

### 4.2 Model Selection Considerations

| Capability | Importance | Notes |
|------------|------------|-------|
| Vision | Required | Must analyze screenshots |
| Tool calling | Required | Must use structured tools |
| Reasoning | Important | Better parameter adjustment logic |
| Cost | Variable | Tradeoff with quality |

**Recommended models for experimentation:**

| Model | Strengths | Cost (approx) |
|-------|-----------|---------------|
| `anthropic/claude-sonnet-4` | Best reasoning + vision | $3/$15 per M tokens |
| `google/gemini-2.0-flash-001` | Fast, good vision, cheap | $0.10/$0.40 |
| `openai/gpt-4o` | Strong vision + tools | $2.5/$10 |
| `qwen/qwen2.5-vl-72b-instruct:free` | Free tier, decent | Free |

### 4.3 Provider Interface

Extend existing `AgentLLMProvider` base class:

```python
class AgentLLMProvider(ABC):
    @abstractmethod
    async def run_agent_loop(
        self,
        tools: list[ToolDefinition],
        tool_executor: Callable[[str, dict], Any],
        system_prompt: str,
        user_message: str,
        max_iterations: int = 20,
        on_iteration: Callable[[AgentIteration], None] = None,
    ) -> str:
        """Run agent loop until completion."""
        ...
```

The existing `OpenRouterAgentProvider` already implements this.

---

## 5. Prompt Design

### 5.1 System Prompt Structure

```
You are an expert at optimizing image analysis parameters for detecting
tubercles (small circular structures) on fish scale SEM images.

## Your Goal
Find extraction parameters that maximize detection quality, measured by:
1. Hexagonalness score (primary) - how well the pattern matches ideal hexagonal
2. Appropriate tubercle count for image size
3. Reasonable diameter and spacing statistics
4. Visual correctness (no obvious missed/false detections)

## Available Parameters
[Table of parameters with ranges and effects]

## Strategy
1. Start by evaluating the initial extraction
2. Identify issues: missed tubercles, false positives, edge problems
3. Adjust ONE OR TWO parameters at a time
4. Track what worked and what didn't
5. Stop when satisfied or no further improvement possible

## Tools
[Tool descriptions]

## Important Guidelines
- Don't retry exact parameter combinations
- Small adjustments (10-20%) are usually better than large jumps
- If hexagonalness > 0.7 and visuals look good, you can accept
- Watch for overfitting (good score but bad visuals)
```

### 5.2 Iteration Prompts

After each extraction, the agent receives:

```
Iteration 3/10
Current parameters: {threshold: 0.08, min_diameter_um: 4.0, ...}
Previous best score: 0.62 (iteration 2)

Metrics:
- Hexagonalness: 0.58 (decreased from 0.62)
- Tubercles: 52 (was 47)
- Mean diameter: 6.2 µm
- Mean spacing: 8.1 µm

[Screenshot attached]

The score decreased. Analyze what went wrong and try a different adjustment.
```

### 5.3 Few-Shot Examples (Optional)

Include 1-2 examples of good reasoning:

```
Example: "I see many small false positives in the noisy background area.
The threshold is 0.05 which is quite sensitive. I'll increase it to 0.08
to reject these low-confidence detections while keeping the clear tubercles."
```

---

## 6. State Management

### 6.1 Optimization State

```python
@dataclass
class OptimizationState:
    """Tracks optimization progress."""

    iteration: int
    current_params: dict
    current_metrics: dict
    best_params: dict
    best_metrics: dict
    best_iteration: int
    history: list[TrialRecord]  # All tried combinations

@dataclass
class TrialRecord:
    """Record of a single parameter trial."""

    iteration: int
    params: dict
    metrics: dict
    screenshot_path: str | None  # Optional: save for debugging
    llm_reasoning: str  # What the LLM said about this trial
```

### 6.2 History Tracking

The agent tracks tried combinations to avoid loops:

```python
def is_duplicate(params: dict, history: list[TrialRecord], tolerance: float = 0.01) -> bool:
    """Check if params are too similar to a previous trial."""
    for trial in history:
        if all(
            abs(params.get(k, 0) - trial.params.get(k, 0)) < tolerance
            for k in params
        ):
            return True
    return False
```

---

## 7. UI Integration: Agent Extraction Tab

### 7.1 Separate Tab (Not Part of Existing Extraction Tab)

The agent functionality lives in a **dedicated "Agent Extraction" tab**, separate from the manual Extraction tab. This keeps the manual workflow uncluttered while providing full visibility into agent operations.

### 7.2 Tab Visibility Control

**Environment Variable:** `FISH_SCALE_AGENT_TABS`

| Value | Effect |
|-------|--------|
| Not set (default) | Agent tabs hidden |
| `1` or `true` | All agent tabs visible |
| `extraction` | Only Agent Extraction tab visible |
| `extraction,editing` | Both agent tabs visible |

```bash
# Enable all agent tabs
export FISH_SCALE_AGENT_TABS=1

# Enable only extraction agent
export FISH_SCALE_AGENT_TABS=extraction

# Default: tabs hidden (for production/normal users)
# (no env var set)
```

**Implementation in Flask:**

```python
# In app.py or config.py
def get_agent_tabs_config():
    """Determine which agent tabs to show."""
    value = os.environ.get('FISH_SCALE_AGENT_TABS', '').lower()
    if not value:
        return {'extraction': False, 'editing': False}
    if value in ('1', 'true', 'yes'):
        return {'extraction': True, 'editing': True}
    tabs = [t.strip() for t in value.split(',')]
    return {
        'extraction': 'extraction' in tabs,
        'editing': 'editing' in tabs,
    }
```

**In Jinja template:**

```html
{% if agent_tabs.extraction %}
<div class="tab" data-tab="agent-extraction">Agent Extraction</div>
{% endif %}
{% if agent_tabs.editing %}
<div class="tab" data-tab="agent-editing">Agent Editing</div>
{% endif %}
```

### 7.3 Process Architecture (Option A: External Agent Process)

The UI drives the agent via an **external subprocess**:

```
┌─────────────────┐      spawn       ┌─────────────────────────┐
│   Flask UI      │ ───────────────▶ │  Agent Process          │
│                 │                   │  (fish-scale-agent      │
│  /api/agent/    │ ◀─── status ───  │   optimize ...)         │
│    start        │      file/pipe   │                         │
│    status       │                   │  Writes progress to     │
│    stop         │                   │  temp status file       │
└─────────────────┘                   └───────────┬─────────────┘
        │                                         │
        │ poll for updates                        │ HTTP calls
        ▼                                         ▼
┌─────────────────┐                   ┌─────────────────────────┐
│   Browser JS    │                   │  UI API Endpoints       │
│                 │                   │  /api/mcp/extract       │
│  Polls /api/    │                   │  /api/mcp/screenshot    │
│  agent/status   │                   │  /api/mcp/params        │
└─────────────────┘                   └─────────────────────────┘
```

**Why Option A (External Process):**
- Same agent code for CLI and UI usage
- Clean process isolation (agent crash doesn't affect UI)
- Easy to kill/restart agent
- Progress communicated via status file (JSON)

**Status File Structure** (`/tmp/fish-scale-agent-<session-id>.json`):
```json
{
    "state": "running",
    "iteration": 5,
    "max_iterations": 10,
    "elapsed_seconds": 47.3,
    "phase": "fine_tuning",
    "current_params": { ... },
    "current_metrics": { "hexagonalness": 0.67, "n_tubercles": 42 },
    "best_iteration": 4,
    "best_metrics": { "hexagonalness": 0.72, "n_tubercles": 38 },
    "history": [ ... ],
    "last_prompt": "Iteration 5/10\nCurrent parameters: ...",
    "last_response": "The hexagonalness decreased from 0.72 to 0.67...",
    "usage": {
        "input_tokens": 8420,
        "output_tokens": 2150,
        "model": "anthropic/claude-sonnet-4"
    }
}
```

### 7.4 Tab Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ [Image] [Calibration] [Extraction] [Configure] [Edit] [Data] ...            │
│                                    [Agent Extraction] [Agent Editing]       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                    │                                        │
│                                    │  Agent Extraction                      │
│                                    │  ═══════════════════════════════════  │
│                                    │                                        │
│      Image with Overlay            │  ┌─ Configuration ─────────────────┐  │
│      (TUBs + ITCs visible)         │  │ Provider: [OpenRouter ▼]        │  │
│                                    │  │ Model:    [claude-sonnet-4 ▼]   │  │
│                                    │  │ Profile:  [default ▼]           │  │
│                                    │  │ Target:   [0.70] hexagonalness  │  │
│                                    │  │ Max iter: [10]                  │  │
│                                    │  │                                 │  │
│                                    │  │ [▶ Start Optimization]          │  │
│                                    │  └─────────────────────────────────┘  │
│                                    │                                        │
│                                    │  ┌─ Status ────────────────────────┐  │
│                                    │  │ Phase: Fine-tuning (iter 5/10)  │  │
│                                    │  │ Elapsed: 47.3s (this iter: 8.2s)│  │
│                                    │  │ Current: 0.67  Best: 0.72 (#4)  │  │
│                                    │  │                                 │  │
│                                    │  │ [■ Stop] [Accept Best]          │  │
│                                    │  └─────────────────────────────────┘  │
│                                    │                                        │
│                                    │  ┌─ Current Parameters ────────────┐  │
│                                    │  │ threshold:     0.08 (was 0.05)◄ │  │
│                                    │  │ min_diameter:  4.5 µm           │  │
│                                    │  │ ... (collapsed if many)         │  │
│                                    │  └─────────────────────────────────┘  │
│                                    │                                        │
│                                    │  ┌─ Hexagonalness Progress ────────┐  │
│                                    │  │  [Chart: iterations vs score]   │  │
│                                    │  └─────────────────────────────────┘  │
│                                    │                                        │
│                                    │  ▶ Last Prompt Sent (click to expand) │
│                                    │  ▶ Last LLM Response (click to expand)│
│                                    │                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.5 Timing and Progress Display

The status panel shows timing at multiple granularities:

```
┌─ Status ─────────────────────────────────────────────────────┐
│ Phase: Fine-tuning                                           │
│ Iteration: 5 of 10                                           │
│ ─────────────────────────────────────────────────────────── │
│ Total elapsed:      47.3s                                    │
│ This iteration:      8.2s                                    │
│ Avg per iteration:   9.5s                                    │
│ ─────────────────────────────────────────────────────────── │
│ Current hexagonalness: 0.67                                  │
│ Best hexagonalness:    0.72 (iteration 4)                    │
│ ─────────────────────────────────────────────────────────── │
│ Tokens: 8,420 in / 2,150 out                                 │
│ Est. cost: $0.058                                            │
│ Model: anthropic/claude-sonnet-4                             │
│                                                              │
│ [■ Stop]  [Accept Best]  [Reset]                             │
└──────────────────────────────────────────────────────────────┘
```

**Timing fields:**
- `Total elapsed` - Wallclock time since Start clicked
- `This iteration` - Time spent on current iteration (resets each iteration)
- `Avg per iteration` - Running average for ETA estimation

### 7.6 Collapsible LLM Prompt/Response Containers

Two collapsible sections show the raw LLM communication:

#### Last Prompt Sent (collapsed by default)

```
▶ Last Prompt Sent [+8.2s into iteration 5]
```

When expanded:

```
▼ Last Prompt Sent [+8.2s into iteration 5]
┌──────────────────────────────────────────────────────────────┐
│ Iteration 5/10                                               │
│ Current parameters: {threshold: 0.08, min_diameter_um: 4.5}  │
│ Previous best score: 0.72 (iteration 4)                      │
│                                                              │
│ Metrics after last extraction:                               │
│ - Hexagonalness: 0.67 (decreased from 0.72)                  │
│ - Tubercles: 45 (was 38)                                     │
│ - Mean diameter: 6.1 µm                                      │
│                                                              │
│ [Screenshot was attached]                                    │
│                                                              │
│ The score decreased. Analyze what went wrong and try a       │
│ different adjustment.                                        │
└──────────────────────────────────────────────────────────────┘
```

#### Last LLM Response (collapsed by default)

```
▶ Last LLM Response [received at +12.4s]
```

When expanded:

```
▼ Last LLM Response [received at +12.4s]
┌──────────────────────────────────────────────────────────────┐
│ The hexagonalness decreased from 0.72 to 0.67 after I        │
│ lowered the threshold. Looking at the screenshot, I can see  │
│ several false positives appeared in the noisy background     │
│ area in the upper-left corner.                               │
│                                                              │
│ The additional 7 tubercles detected are likely noise. I'll   │
│ revert the threshold change and instead try increasing       │
│ min_circularity to filter out the irregular shapes.          │
│                                                              │
│ Tool calls:                                                  │
│ - set_params({threshold: 0.05, min_circularity: 0.55})       │
│ - run_extraction()                                           │
└──────────────────────────────────────────────────────────────┘
```

**Features:**
- Shows timestamp relative to iteration/process start
- Scrollable if content is long (max-height with overflow)
- Monospace font for readability
- Copy button to copy contents to clipboard

### 7.7 Completion Summary

When optimization completes, the status panel transforms to show final results:

```
┌─ Optimization Complete ──────────────────────────────────────┐
│ ✓ Target achieved (hexagonalness ≥ 0.70)                     │
│ ─────────────────────────────────────────────────────────── │
│ Best result: Iteration 4 of 7 used                           │
│ Final hexagonalness: 0.72                                    │
│ Tubercles: 38  |  Connections: 94                            │
│ ─────────────────────────────────────────────────────────── │
│ Total wallclock time: 1m 23.4s                               │
│ ─────────────────────────────────────────────────────────── │
│ Model: anthropic/claude-sonnet-4                             │
│ Tokens: 12,450 input / 3,200 output (15,650 total)           │
│ Estimated cost: $0.085                                       │
│ ─────────────────────────────────────────────────────────── │
│ Optimal parameters:                                          │
│   threshold: 0.05                                            │
│   min_diameter_um: 4.5                                       │
│   min_circularity: 0.5                                       │
│   ... (expand for all)                                       │
│                                                              │
│ [Apply to Configure Tab]  [Save Parameters]  [New Run]       │
└──────────────────────────────────────────────────────────────┘
```

**Completion reasons:**
- `✓ Target achieved` - hexagonalness reached target
- `✓ Optimization complete` - plateau detected, no further improvement
- `⚠ Max iterations reached` - stopped at limit
- `⚠ Stopped by user` - user clicked Stop
- `✗ Error occurred` - agent failed (show error message)

### 7.8 Hexagonalness Progress Chart

**Features:**
- X-axis: Iteration number (1, 2, 3, ...)
- Y-axis: Hexagonalness score (0.0 to 1.0)
- Line connecting all points
- Highlight marker on best score achieved
- Target line (horizontal dashed line at target score)
- Updates in real-time as iterations complete

**Implementation options:**
- Chart.js (lightweight, interactive)
- Simple SVG (minimal dependencies)
- Canvas-based (performant)

**Recommendation:** Use Chart.js for interactivity (hover to see iteration details).

```javascript
// Example Chart.js configuration
const hexChart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: [], // iteration numbers
        datasets: [{
            label: 'Hexagonalness',
            data: [], // scores
            borderColor: '#4CAF50',
            tension: 0.1,
        }]
    },
    options: {
        scales: {
            y: { min: 0, max: 1, title: { text: 'Hexagonalness' } },
            x: { title: { text: 'Iteration' } }
        },
        plugins: {
            annotation: {
                annotations: {
                    targetLine: {
                        type: 'line',
                        yMin: 0.7,
                        yMax: 0.7,
                        borderColor: '#FF9800',
                        borderDash: [5, 5],
                        label: { content: 'Target', enabled: true }
                    }
                }
            }
        }
    }
});
```

### 7.9 Current Parameters Display

Live display of the parameters currently being used/tested:

- Updates after each `set_params` call
- Highlights changed parameters (briefly flash or color)
- Shows comparison to initial/best parameters

```
┌─ Current Parameters (changed from best) ─┐
│ method:        log                        │
│ threshold:     0.08  (was 0.05) ◄         │
│ min_diameter:  4.5 µm                     │
│ max_diameter:  12.0 µm                    │
│ min_circular:  0.5                        │
│ clahe_clip:    0.03                       │
│ blur_sigma:    1.0                        │
└───────────────────────────────────────────┘
```

### 7.10 Agent Controls

| Button | Action |
|--------|--------|
| **Start Optimization** | Begin the optimization loop |
| **Stop** | Interrupt optimization, keep current state |
| **Accept Best** | Stop and apply best parameters found |
| **Reset** | Clear optimization state, return to initial |

### 7.11 Future: Agent Editing Tab

The same pattern applies to the future Agent Editing tab:

- Controlled by `FISH_SCALE_AGENT_TABS=editing` or `=1`
- Separate from manual Edit tab
- Shows agent status, current operations, progress metrics
- Different set of controls appropriate for editing operations

---

## 8. Logging Requirements

### 8.1 Hexagonalness in All Log Events

**Requirement:** Hexagonalness score MUST be included in the session log for all events that modify the annotation state.

This enables:
- Tracking quality over time
- Comparing manual vs automated results
- Debugging optimization issues
- Auditing dataset provenance

### 8.2 Events That Must Include Hexagonalness

| Event Type | When Logged | Hexagonalness Source |
|------------|-------------|---------------------|
| `extraction` | After extraction completes | Calculated from result |
| `auto_connect` | After connection regeneration | Recalculated |
| `manual_edit` | On save (consolidated edits) | Calculated at save time |
| `agent_iteration` | After each agent iteration | From iteration metrics |
| `agent_complete` | When agent finishes | Final best score |

### 8.3 Log Event Schema Updates

#### Extraction Event (existing, add hexagonalness)

```json
{
    "timestamp": "2025-12-31T10:30:00.000Z",
    "event": "extraction",
    "params": { ... },
    "result": {
        "n_tubercles": 43,
        "n_edges": 112,
        "hexagonalness": 0.67,
        "mean_diameter_um": 6.8,
        "mean_space_um": 8.2
    }
}
```

#### Auto-Connect Event (existing, add hexagonalness)

```json
{
    "timestamp": "2025-12-31T10:35:00.000Z",
    "event": "auto_connect",
    "method": "gabriel",
    "result": {
        "n_edges": 98,
        "hexagonalness": 0.71
    }
}
```

#### Manual Edit Event (existing, add hexagonalness)

```json
{
    "timestamp": "2025-12-31T10:40:00.000Z",
    "event": "manual_edit",
    "summary": "+5 tubercles, -2 tubercles, moved 3",
    "result": {
        "n_tubercles": 46,
        "n_edges": 106,
        "hexagonalness": 0.68
    }
}
```

#### Agent Iteration Event (new)

```json
{
    "timestamp": "2025-12-31T11:00:00.000Z",
    "event": "agent_iteration",
    "iteration": 5,
    "max_iterations": 10,
    "phase": "fine_tuning",
    "timing": {
        "elapsed_seconds": 47.3,
        "iteration_seconds": 8.2
    },
    "params": {
        "threshold": 0.08,
        "min_diameter_um": 4.5,
        "max_diameter_um": 12.0,
        "min_circularity": 0.5
    },
    "result": {
        "n_tubercles": 42,
        "n_edges": 104,
        "hexagonalness": 0.72,
        "is_best": true
    },
    "llm": {
        "input_tokens": 1850,
        "output_tokens": 420
    },
    "llm_reasoning": "Increased threshold to reduce false positives..."
}
```

#### Agent Complete Event (new)

```json
{
    "timestamp": "2025-12-31T11:05:00.000Z",
    "event": "agent_complete",
    "reason": "target_achieved",
    "iterations_used": 7,
    "best_iteration": 5,
    "best_params": {
        "threshold": 0.05,
        "min_diameter_um": 4.5,
        "max_diameter_um": 12.0,
        "min_circularity": 0.5,
        "clahe_clip": 0.03,
        "blur_sigma": 1.0
    },
    "best_result": {
        "n_tubercles": 42,
        "n_edges": 104,
        "hexagonalness": 0.72,
        "mean_diameter_um": 6.8,
        "std_diameter_um": 1.2,
        "mean_space_um": 8.1,
        "std_space_um": 1.8
    },
    "timing": {
        "wallclock_seconds": 83.4,
        "avg_iteration_seconds": 11.9
    },
    "llm": {
        "provider": "openrouter",
        "model": "anthropic/claude-sonnet-4",
        "input_tokens": 12450,
        "output_tokens": 3200,
        "total_tokens": 15650,
        "estimated_cost_usd": 0.085
    }
}
```

**Required fields for `agent_complete`:**

| Field | Type | Description |
|-------|------|-------------|
| `reason` | string | Why optimization stopped: `target_achieved`, `plateau_detected`, `max_iterations`, `user_stopped`, `error` |
| `iterations_used` | int | Total iterations executed |
| `best_iteration` | int | Which iteration produced best result |
| `best_params` | object | Complete parameter set for best result |
| `best_result` | object | Metrics from best iteration including hexagonalness |
| `timing.wallclock_seconds` | float | Total elapsed time from start to finish |
| `timing.avg_iteration_seconds` | float | Average time per iteration |
| `llm.provider` | string | Provider name (openrouter, claude, gemini) |
| `llm.model` | string | Full model identifier |
| `llm.input_tokens` | int | Total input tokens consumed |
| `llm.output_tokens` | int | Total output tokens generated |
| `llm.total_tokens` | int | Sum of input + output |
| `llm.estimated_cost_usd` | float | Estimated cost based on model pricing |

### 8.4 Implementation Locations

**Session Log (JSONL file):**
- Location: `log/<image_name>_<timestamp>.jsonl`
- All events written here for analysis

**Dataset History (SLO file):**
- Location: `slo/<image_name>_slo.json` → `sets[].history[]`
- Subset of events (extraction, auto_connect, manual_edit, agent phases)

**UI Log Tab:**
- Real-time display of events
- Filterable by event type
- Hexagonalness shown for relevant events

### 8.5 Logging Implementation Changes

#### In extraction.js (add hexagonalness to extraction log)

```javascript
// After extraction completes
window.app.logEvent('extraction', {
    params: params,
    result: {
        n_tubercles: result.statistics.n_tubercles,
        n_edges: result.statistics.n_edges,
        hexagonalness: result.statistics.hexagonalness_score,
        mean_diameter_um: result.statistics.mean_diameter_um,
        mean_space_um: result.statistics.mean_space_um,
    }
});
```

#### In editor.js / sets.js (add hexagonalness on save)

```javascript
// When consolidating edits on save
function consolidateEdits() {
    // ... existing code ...

    // Calculate current hexagonalness
    const stats = window.extraction?.calculateStatistics();

    window.app.logEvent('manual_edit', {
        summary: buildSummary(pendingEdits),
        result: {
            n_tubercles: tubercles.length,
            n_edges: edges.length,
            hexagonalness: stats?.hexagonalness_score || 0,
        }
    });
}
```

#### New: agent_extraction.js

```javascript
// After each agent iteration
function logIteration(iteration, params, result, reasoning) {
    window.app.logEvent('agent_iteration', {
        iteration: iteration,
        max_iterations: config.maxIterations,
        params: params,
        result: {
            n_tubercles: result.n_tubercles,
            n_edges: result.n_edges,
            hexagonalness: result.hexagonalness,
            is_best: result.hexagonalness > state.bestScore,
        },
        llm_reasoning: reasoning,
    });
}
```

---

## 9. CLI Interface

### 9.1 Command Structure

```bash
# Basic usage
uv run fish-scale-agent optimize <image> --calibration 0.5

# With options
uv run fish-scale-agent optimize <image> \
    --calibration 0.5 \
    --provider openrouter \
    --model google/gemini-2.0-flash-001 \
    --profile default \
    --target-score 0.7 \
    --max-iterations 10 \
    -v
```

### 9.2 Output

```
Fish Scale Extraction Optimizer
================================
Image: P1_Fig4_Atractosteus_simplex_7.07um.tif
Provider: openrouter (google/gemini-2.0-flash-001)
Starting profile: default
Target hexagonalness: 0.70

Iteration 1/10: Running initial extraction...
  → Hexagonalness: 0.45, Tubercles: 23
  → Agent: "Low count, threshold too high. Lowering to 0.03."

Iteration 2/10: Running extraction...
  → Hexagonalness: 0.58, Tubercles: 41 (+18)
  → Agent: "Better! But some false positives visible. Try min_circularity 0.5."

Iteration 3/10: Running extraction...
  → Hexagonalness: 0.67, Tubercles: 38 (-3)
  → Agent: "Good improvement. Fine-tuning min_diameter to 4.5."

...

Optimization Complete
─────────────────────
Best result: Iteration 5
  Hexagonalness: 0.72
  Tubercles: 42
  Mean diameter: 7.1 µm
  Mean spacing: 6.8 µm

Optimal parameters:
  threshold: 0.05
  min_diameter_um: 4.5
  max_diameter_um: 12.0
  min_circularity: 0.5
  clahe_clip: 0.03
  blur_sigma: 1.0

Usage: 1,247 input + 892 output tokens (~$0.02)
```

---

## 10. Implementation Plan

### Phase 1: Logging Infrastructure (Foundation)

**Prerequisite:** Add hexagonalness to all log events before agent work begins.

1. Update `extraction.js` to include hexagonalness in extraction log events
2. Update `sets.js` `consolidateEdits()` to include hexagonalness in manual_edit events
3. Update auto-connect logging to include hexagonalness
4. Verify existing log events display correctly in Log tab
5. Add hexagonalness column to Log tab display

### Phase 2: Agent Tab Infrastructure

1. Add `FISH_SCALE_AGENT_TABS` environment variable support in Flask
2. Create `get_agent_tabs_config()` helper function
3. Update `workspace.html` template with conditional agent tabs
4. Create basic `agent-extraction` tab content panel (static HTML)
5. Create `agent_extraction.js` module skeleton
6. Add CSS for agent tab layout

### Phase 3: Core Agent Module

1. Create `extraction_optimizer.py` module in `fish_scale_agent`
2. Define tool schemas for optimization
3. Implement `OptimizationState` and `TrialRecord` classes
4. Add `get_metrics` endpoint if not already exposing all needed data
5. Write unit tests for state management

### Phase 4: Agent Loop Implementation

1. Implement `ExtractionOptimizer.optimize()` method
2. Wire up tool execution to UI API calls
3. Implement history tracking and duplicate detection
4. Add iteration callbacks for progress reporting
5. Integration test with mock LLM responses

### Phase 5: Prompt Engineering

1. Write comprehensive system prompt with domain knowledge
2. Create iteration prompt templates
3. Add few-shot examples
4. Test with real images and iterate on prompts
5. Document parameter effects and optimization strategies

### Phase 6: CLI Integration

1. Add `optimize` subcommand to `fish-scale-agent` CLI
2. Implement argument parsing for all options
3. Add progress output formatting
4. Support multiple providers/models via flags

### Phase 7: UI Tab Implementation

1. Implement configuration panel (provider, model, profile, target, max iterations)
2. Implement current parameters display with live updates
3. Add Chart.js and implement hexagonalness progress chart
4. Implement status panel with iteration progress
5. Wire up Start/Stop/Accept buttons
6. Add WebSocket or polling for real-time updates from agent
7. Add agent iteration events to Log tab

### Phase 8: Testing & Refinement

1. Test with diverse images (different species, quality levels)
2. Compare results across different LLM models
3. Tune stopping criteria and iteration limits
4. Benchmark cost vs quality for different models
5. Document best practices and model recommendations
6. End-to-end testing of UI agent tab workflow

---

## 11. Comparison: This Agent vs Existing Agent

| Aspect | Existing Agent (`runner.py`) | Extraction Optimizer (proposed) |
|--------|------------------------------|--------------------------------|
| **Goal** | Complete tubercle detection | Find optimal extraction params |
| **Manual edits** | Yes (Phase 2 adds tubercles) | No |
| **Output** | Full annotation set | Optimal parameter values |
| **Iteration focus** | Adding missed tubercles | Adjusting detection params |
| **When to use** | After extraction params tuned | Before manual refinement |
| **Typical iterations** | 10-30 (adding tubercles) | 5-10 (tuning params) |

**Workflow integration:**

```
1. Load image, set calibration
2. [NEW] Run Extraction Optimizer → get optimal params
3. Run extraction with optimal params
4. [EXISTING] Run Pattern Completion Agent → add missed tubercles
5. Generate connections
6. Save results
```

---

## 12. Open Questions

### 12.1 Profile Selection Strategy

**Q:** Should Phase 1 (profile selection) be automated or user-guided?

**Options:**
- A) Agent tries all profiles automatically
- B) User selects 2-3 candidate profiles
- C) Agent guesses based on image characteristics (magnification, contrast)

**Recommendation:** Start with (A), allow (B) as optimization.

### 12.2 Visual Analysis Depth

**Q:** How much should the agent rely on visual analysis vs metrics?

**Options:**
- A) Primarily metrics, visual as tiebreaker
- B) Equal weight
- C) Primarily visual, metrics as sanity check

**Recommendation:** (A) - metrics are more consistent; visual catches edge cases.

### 12.3 Multi-Objective Optimization

**Q:** What if hexagonalness conflicts with other goals (e.g., count)?

**Example:** Higher threshold → better hexagonalness but fewer tubercles.

**Recommendation:** Define composite score or let user set priorities.

### 12.4 Calibration Sensitivity

**Q:** Should the agent also tune calibration?

**Consideration:** Wrong calibration affects all um-based parameters.

**Recommendation:** Initially require user-provided calibration; future work could include calibration estimation.

### 12.5 Connection Type Interaction

**Q:** Should the agent also optimize connection parameters (graph type, culling)?

**Consideration:** Hexagonalness depends on connection graph.

**Recommendation:** Include `neighbor_graph` and `cull_factor` in tunable params.

---

## 13. Success Criteria

The extraction optimizer is successful if:

1. **Quality:** Achieves hexagonalness >= 0.65 on 80%+ of test images
2. **Efficiency:** Finds good params in <= 10 iterations typically
3. **Cost:** Total cost < $0.10 per optimization run (using efficient models)
4. **Usability:** Clear progress feedback, actionable final output
5. **Consistency:** Similar results when run multiple times on same image

---

## 14. Future Extensions

### 14.1 Learning from History

Store successful optimizations to:
- Suggest starting profiles for similar images
- Build image-type classifiers
- Fine-tune prompts based on what worked

### 14.2 Batch Optimization

Optimize parameters across multiple images simultaneously:
- Find params that work well on average
- Identify image-specific adjustments needed

### 14.3 Edit Tab Agent

Apply similar architecture to automate Edit tab operations:
- Identify and fix obvious errors (isolated tubercles, missing connections)
- Suggest manual review areas
- Semi-automated refinement

### 14.4 Active Learning

Let user provide feedback during optimization:
- "This area has too many false positives"
- "These tubercles should be detected"
- Agent incorporates feedback into next iteration
