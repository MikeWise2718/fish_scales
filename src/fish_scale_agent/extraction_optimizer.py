"""Extraction parameter optimization via LLM agent.

This module implements an LLM-powered agent that iteratively tunes extraction
parameters to maximize detection quality (measured by hexagonalness score).
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import httpx

from .agent_run_logger import AgentRunLogger
from .providers.base import AgentLLMProvider, ToolDefinition


@dataclass
class TrialRecord:
    """Record of a single parameter trial."""

    iteration: int
    params: dict
    metrics: dict
    screenshot_path: str | None = None  # Optional: save for debugging
    llm_reasoning: str = ""  # What the LLM said about this trial


@dataclass
class OptimizationState:
    """Tracks optimization progress."""

    iteration: int
    current_params: dict
    current_metrics: dict
    best_params: dict
    best_metrics: dict
    best_iteration: int
    history: list[TrialRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "iteration": self.iteration,
            "current_params": self.current_params,
            "current_metrics": self.current_metrics,
            "best_params": self.best_params,
            "best_metrics": self.best_metrics,
            "best_iteration": self.best_iteration,
            "history": [
                {
                    "iteration": t.iteration,
                    "params": t.params,
                    "metrics": t.metrics,
                    "screenshot_path": t.screenshot_path,
                    "llm_reasoning": t.llm_reasoning,
                }
                for t in self.history
            ],
        }


def is_duplicate(
    params: dict, history: list[TrialRecord], tolerance: float = 0.01
) -> bool:
    """Check if params are too similar to a previous trial.

    Args:
        params: Parameter dict to check
        history: List of previous trials
        tolerance: Maximum difference allowed for numerical params

    Returns:
        True if params are too similar to a previous trial
    """
    if not history:
        return False

    # Get numeric parameters for comparison
    numeric_keys = {
        "threshold",
        "min_diameter_um",
        "max_diameter_um",
        "min_circularity",
        "clahe_clip",
        "clahe_kernel",
        "blur_sigma",
    }

    for trial in history:
        # Check if all numeric params are within tolerance
        all_similar = True
        for key in numeric_keys:
            current_val = params.get(key)
            trial_val = trial.params.get(key)

            # Skip if either value is missing
            if current_val is None or trial_val is None:
                continue

            # Check if values are similar
            if isinstance(current_val, (int, float)) and isinstance(
                trial_val, (int, float)
            ):
                # Use relative tolerance for non-zero values
                if trial_val != 0:
                    rel_diff = abs(current_val - trial_val) / abs(trial_val)
                    if rel_diff > tolerance:
                        all_similar = False
                        break
                elif current_val != 0:
                    all_similar = False
                    break

        # Check string params (method, neighbor_graph) must match exactly
        if all_similar:
            for key in ["method", "neighbor_graph"]:
                if params.get(key) != trial.params.get(key):
                    all_similar = False
                    break

        if all_similar:
            return True

    return False


# Tool definitions for parameter optimization
# These are a minimal, focused set compared to the full agent tools
OPTIMIZATION_TOOLS = [
    ToolDefinition(
        name="run_extraction",
        description="Execute tubercle extraction with current parameters. Returns metrics including tubercle count, hexagonalness score, and diameter/spacing statistics.",
        parameters={"type": "object", "properties": {}},
    ),
    ToolDefinition(
        name="get_screenshot",
        description="Capture current view of the image with tubercle overlay for visual analysis. Returns the image along with width and height in pixels.",
        parameters={
            "type": "object",
            "properties": {
                "include_overlay": {
                    "type": "boolean",
                    "description": "Whether to include tubercle/connection overlay",
                    "default": True,
                },
            },
        },
    ),
    ToolDefinition(
        name="get_metrics",
        description="Get current quality metrics including hexagonalness score, tubercle count, diameter and spacing statistics.",
        parameters={"type": "object", "properties": {}},
    ),
    ToolDefinition(
        name="get_params",
        description="Get current extraction parameter values.",
        parameters={"type": "object", "properties": {}},
    ),
    ToolDefinition(
        name="set_params",
        description="Update extraction parameters. Only provided parameters are updated. Parameters: threshold (0.01-0.5, lower = more sensitive), min_diameter_um (2-10), max_diameter_um (5-20), min_circularity (0-1, higher = rounder), clahe_clip (0.01-0.1), clahe_kernel (4-16), blur_sigma (0.5-3.0), neighbor_graph (delaunay/gabriel/rng).",
        parameters={
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["log", "dog", "ellipse", "lattice"],
                    "description": "Detection method (log is recommended)",
                },
                "threshold": {
                    "type": "number",
                    "description": "Detection sensitivity (0.01-0.5, lower = more sensitive, higher = fewer false positives)",
                },
                "min_diameter_um": {
                    "type": "number",
                    "description": "Minimum tubercle diameter in micrometers (filters small noise)",
                },
                "max_diameter_um": {
                    "type": "number",
                    "description": "Maximum tubercle diameter in micrometers",
                },
                "min_circularity": {
                    "type": "number",
                    "description": "Minimum circularity (0-1, higher = require rounder shapes)",
                },
                "clahe_clip": {
                    "type": "number",
                    "description": "CLAHE contrast limit (0.01-0.1, higher = more contrast enhancement)",
                },
                "clahe_kernel": {
                    "type": "integer",
                    "description": "CLAHE kernel size (4-16)",
                },
                "blur_sigma": {
                    "type": "number",
                    "description": "Gaussian blur sigma (0.5-3.0, higher = smoother image)",
                },
                "neighbor_graph": {
                    "type": "string",
                    "enum": ["delaunay", "gabriel", "rng"],
                    "description": "Graph type for neighbor connections (affects hexagonalness)",
                },
            },
        },
    ),
    ToolDefinition(
        name="load_profile",
        description="Load a preset parameter profile. Available profiles: default, paralepidosteus, lepisosteus, atractosteus, polypterus, high-contrast, low-contrast, scanned-pdf.",
        parameters={
            "type": "object",
            "properties": {
                "profile_name": {
                    "type": "string",
                    "description": "Name of the profile to load",
                },
            },
            "required": ["profile_name"],
        },
    ),
    ToolDefinition(
        name="accept_result",
        description="Signal that the current result is acceptable and stop optimization. Use this when: (1) hexagonalness is above target, (2) no further improvement seems possible, or (3) visual inspection shows good coverage.",
        parameters={
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Explanation for why this result is acceptable",
                },
            },
            "required": ["reason"],
        },
    ),
    ToolDefinition(
        name="get_history",
        description="Get history of all tried parameter combinations and their scores. Use this to avoid repeating failed combinations and understand what adjustments have helped or hurt.",
        parameters={"type": "object", "properties": {}},
    ),
]


# System prompt for the extraction optimizer
OPTIMIZER_SYSTEM_PROMPT = """You are an expert at optimizing image analysis parameters for detecting tubercles (small circular structures) on fish scale SEM images.

## Your Goal

Maximize the HEXAGONALNESS SCORE (0-1), which measures how well the detected tubercle pattern matches an ideal hexagonal lattice. Fish scale tubercles naturally form hexagonal patterns, so higher hexagonalness indicates better detection quality.

**Primary Objective:** Achieve hexagonalness >= target threshold (typically 0.70)

**Secondary Objectives:**
- Appropriate tubercle count for image size (typically 30-200)
- Low coefficient of variation for diameter and spacing (CV < 0.30)
- Visual correctness (no obvious missed/false detections)

## Hexagonalness Formula

The hexagonalness score combines three components:
```
Hexagonalness = 0.40 × Spacing Uniformity + 0.45 × Degree Score + 0.15 × Edge Ratio Score
```

- **Spacing Uniformity (40%):** How consistent edge lengths are (lower CV = better)
- **Degree Score (45%):** How many nodes have 5-7 neighbors (ideal for hexagonal lattice)
- **Edge Ratio Score (15%):** Edges-to-nodes ratio near 2.5 (hexagonal characteristic)

## Parameter Effects Reference

| Parameter | Range | Effect of INCREASING | When to INCREASE | When to DECREASE |
|-----------|-------|---------------------|------------------|------------------|
| threshold | 0.01-0.5 | Fewer detections, rejects weak blobs | Many false positives, noisy background | Too few tubercles, missing obvious ones |
| min_diameter_um | 2-10 µm | Filters out small detections | Detecting noise/artifacts/dust | Missing small tubercles |
| max_diameter_um | 5-20 µm | Allows larger detections | Missing large tubercles | Detecting merged/oversized blobs |
| min_circularity | 0-1 | Requires rounder shapes | Detecting elongated/irregular blobs | Rejecting valid slightly oval tubercles |
| clahe_clip | 0.01-0.1 | More contrast enhancement | Low contrast, faint tubercles | Over-enhancement, noise amplification |
| blur_sigma | 0.5-3.0 | Smoother image, merged features | Too much noise/speckle | Losing fine detail, merging tubercles |

**Detection Method Options:**
- `log` (default) - Laplacian of Gaussian, best accuracy for circular blobs
- `dog` - Difference of Gaussian, faster but less accurate
- `ellipse` - Ellipse fitting, good for oval tubercles
- `lattice` - Hexagonal lattice-aware, experimental

**Neighbor Graph Types (affects hexagonalness calculation):**
- `delaunay` - All Delaunay triangulation edges (may include long edges)
- `gabriel` - Gabriel graph, removes edges through empty circles (recommended)
- `rng` - Relative Neighborhood Graph, most conservative (fewest edges)

## Available Profiles

Use `load_profile(profile_name)` to start from a preset configuration:

| Profile | Best For | Key Settings |
|---------|----------|--------------|
| default | General starting point | threshold=0.05, min_diameter=5µm, circularity=0.5 |
| paralepidosteus | Paralepidosteus species | Optimized for typical morphology |
| lepisosteus | Lepisosteus species | Adjusted for size differences |
| atractosteus | Atractosteus species | Fine-tuned parameters |
| polypterus | Polypteridae family | Different tubercle characteristics |
| high-contrast | Clear, well-defined tubercles | Lower threshold, higher circularity |
| low-contrast | Faint, poorly defined tubercles | Higher CLAHE, lower threshold |
| scanned-pdf | Scanned literature figures | Handles lower resolution/noise |

## Two-Phase Optimization Strategy

### Phase 1: Profile Selection (Coarse Search)
If starting from scratch, quickly test 2-3 relevant profiles:
1. Run extraction with starting profile
2. Check hexagonalness and tubercle count
3. If score < 0.5, try an alternative profile
4. Select the best profile as your baseline

### Phase 2: Parameter Fine-Tuning (Local Search)
From your best baseline, make targeted adjustments:
1. Analyze the screenshot and metrics
2. Identify the primary issue (see diagnostic guide below)
3. Adjust ONE OR TWO parameters by 10-20%
4. Run extraction and compare to previous best
5. Accept improvement or revert and try different adjustment
6. Repeat until target reached or no improvement for 2-3 iterations

## Key Parameter Insights

**min_circularity is often the most impactful parameter:**
- Default 0.5 is often TOO STRICT for real-world images
- Fish scale tubercles are rarely perfectly circular - they're often oval or irregular
- TRY VALUES AS LOW AS 0.2-0.3 if you're missing obvious tubercles
- Only increase above 0.5 if you're detecting non-tubercle artifacts

**Recommended starting adjustments if detection is poor:**
1. First try min_circularity = 0.3 (most images benefit from this)
2. Then adjust threshold if needed
3. Finally tune diameter ranges

## Diagnostic Guide

**Low hexagonalness + high tubercle count (>150):**
→ Likely detecting false positives. INCREASE threshold or min_circularity.

**Low hexagonalness + low tubercle count (<30):**
→ Missing tubercles. DECREASE min_circularity to 0.3 or lower, then threshold.

**Low hexagonalness + moderate count (50-100) + high spacing CV:**
→ Inconsistent spacing detection. Try different neighbor_graph (gabriel → rng).

**Low hexagonalness + good count + many irregular shapes:**
→ INCREASE min_circularity to reject non-circular blobs.

**Good hexagonalness but poor visuals:**
→ Trust the metrics less; focus on visual verification.

**Clustered detections in one area, gaps elsewhere:**
→ Adjust preprocessing: INCREASE clahe_clip for low-contrast regions.

## Few-Shot Examples of Good Reasoning

**Example 1 - Reducing False Positives:**
"Looking at the screenshot, I see many small detected circles in the noisy background area (top-left corner) that aren't actual tubercles. The threshold is 0.05 which is quite sensitive. I'll increase it to 0.07 to reject these low-confidence detections while keeping the clear tubercles in the center."

**Example 2 - Handling Missing Tubercles (circularity is key!):**
"The hexagonalness is only 0.52 with 28 tubercles. Visually, I can see at least 20-30 more obvious tubercles that weren't detected. The current min_circularity of 0.5 is likely too strict - real tubercles are often oval or irregular. I'll aggressively lower it to 0.25 to capture these. If that causes false positives, I can increase threshold to compensate."

**Example 3 - Connection Graph Adjustment:**
"We have 67 tubercles with hexagonalness 0.58. The spacing standard deviation is high (3.2 µm vs mean of 7.8 µm). Looking at the connections, I see some very long edges crossing the pattern. Switching from delaunay to gabriel should remove these spurious long connections and improve the degree distribution."

**Example 4 - Profile Switching:**
"The initial extraction with default profile gave hexagonalness 0.41 with many merged detections. The tubercles in this image appear smaller and more densely packed than typical. I'll try the 'polypterus' profile which has smaller diameter ranges and different preprocessing."

**Example 5 - Plateau Detection:**
"Iteration 6: hexagonalness 0.69 (was 0.68, 0.67, 0.69 in previous 3 iterations). We've been oscillating around 0.68-0.69 for several iterations. The visual quality looks good with no obvious missed or false detections. Further parameter tweaks aren't improving the score. I'll accept this result as optimal for this image."

## Important Guidelines

1. **Always run extraction first** before making judgments - don't guess.

2. **Check history before changing parameters** - avoid repeating failed combinations.

3. **Make small adjustments (10-20%)** - large jumps often overshoot.

4. **Change ONE or TWO parameters at a time** - isolates cause and effect.

5. **Watch for oscillation** - if hexagonalness bounces between similar values for 3+ iterations, you've likely found the optimum.

6. **Visual verification matters** - high hexagonalness with bad visuals may indicate overfitting.

7. **Edge effects are normal** - incomplete patterns at image boundaries are expected.

8. **Know when to stop:**
   - Target hexagonalness achieved (>= 0.70 typically)
   - No improvement for 2-3 consecutive iterations
   - Visual inspection shows good coverage with minimal errors

9. **Avoid common traps:**
   - Don't keep lowering threshold indefinitely - causes false positives
   - Don't chase perfect hexagonalness (0.9+) - may indicate over-detection
   - Don't ignore visual evidence that contradicts metrics

## Tools Available

| Tool | Description |
|------|-------------|
| `run_extraction()` | Execute detection with current params, returns metrics |
| `get_screenshot(include_overlay)` | Capture current view for visual analysis |
| `get_metrics()` | Get quality metrics (hexagonalness, counts, statistics) |
| `get_params()` | Get current parameter values |
| `set_params(...)` | Update one or more parameters |
| `load_profile(profile_name)` | Load a preset parameter profile |
| `get_history()` | Get history of tried params and their scores |
| `accept_result(reason)` | Signal optimization complete with explanation |

## Output Format

After each extraction, report:
1. Key metrics (hexagonalness, tubercle count, diameter/spacing stats)
2. Visual observations from screenshot
3. Your reasoning for next adjustment
4. Which parameters you're changing and why

When accepting a result, explain:
1. Why you believe this is optimal (or acceptable)
2. Any remaining issues that couldn't be resolved
3. Summary of what worked and what didn't
"""


def build_iteration_prompt(
    iteration: int,
    max_iterations: int,
    current_params: dict,
    current_metrics: dict,
    prev_metrics: dict | None,
    best_metrics: dict,
    best_iteration: int,
    history_summary: list[dict] | None = None,
) -> str:
    """Build the iteration context prompt to send after each extraction.

    This provides the LLM with structured context about the current state,
    previous results, and guidance based on whether the score improved.

    Args:
        iteration: Current iteration number (1-indexed)
        max_iterations: Maximum iterations allowed
        current_params: Currently active parameters
        current_metrics: Metrics from the most recent extraction
        prev_metrics: Metrics from the previous extraction (None if first)
        best_metrics: Best metrics achieved so far
        best_iteration: Which iteration achieved best metrics
        history_summary: Optional summary of trial history

    Returns:
        Formatted prompt string with iteration context
    """
    lines = []

    # Header
    lines.append(f"## Iteration {iteration}/{max_iterations}")
    lines.append("")

    # Current parameters (formatted nicely)
    lines.append("### Current Parameters")
    key_params = [
        "threshold",
        "min_diameter_um",
        "max_diameter_um",
        "min_circularity",
        "clahe_clip",
        "blur_sigma",
        "neighbor_graph",
        "method",
    ]
    param_strs = []
    for key in key_params:
        if key in current_params:
            val = current_params[key]
            if isinstance(val, float):
                param_strs.append(f"{key}={val:.3f}")
            else:
                param_strs.append(f"{key}={val}")
    lines.append(", ".join(param_strs))
    lines.append("")

    # Previous best
    best_hex = best_metrics.get("hexagonalness", 0)
    lines.append(f"### Best So Far")
    lines.append(
        f"Hexagonalness: {best_hex:.3f} (iteration {best_iteration}), "
        f"Tubercles: {best_metrics.get('n_tubercles', 0)}"
    )
    lines.append("")

    # Current metrics
    curr_hex = current_metrics.get("hexagonalness", 0)
    curr_count = current_metrics.get("n_tubercles", 0)
    lines.append("### Current Metrics")
    lines.append(f"- Hexagonalness: {curr_hex:.3f}")
    lines.append(f"- Tubercles: {curr_count}")

    if current_metrics.get("mean_diameter_um"):
        mean_d = current_metrics["mean_diameter_um"]
        std_d = current_metrics.get("std_diameter_um", 0)
        cv_d = std_d / mean_d if mean_d > 0 else 0
        lines.append(
            f"- Mean diameter: {mean_d:.2f} µm (std: {std_d:.2f}, CV: {cv_d:.2f})"
        )

    if current_metrics.get("mean_space_um"):
        mean_s = current_metrics["mean_space_um"]
        std_s = current_metrics.get("std_space_um", 0)
        cv_s = std_s / mean_s if mean_s > 0 else 0
        lines.append(
            f"- Mean spacing: {mean_s:.2f} µm (std: {std_s:.2f}, CV: {cv_s:.2f})"
        )

    lines.append("")

    # Comparison to previous
    if prev_metrics:
        prev_hex = prev_metrics.get("hexagonalness", 0)
        prev_count = prev_metrics.get("n_tubercles", 0)

        hex_delta = curr_hex - prev_hex
        count_delta = curr_count - prev_count

        lines.append("### Change from Previous")

        if hex_delta > 0.01:
            lines.append(
                f"- Hexagonalness: IMPROVED by {hex_delta:+.3f} ({prev_hex:.3f} -> {curr_hex:.3f})"
            )
        elif hex_delta < -0.01:
            lines.append(
                f"- Hexagonalness: DECREASED by {hex_delta:+.3f} ({prev_hex:.3f} -> {curr_hex:.3f})"
            )
        else:
            lines.append(f"- Hexagonalness: UNCHANGED (~{curr_hex:.3f})")

        if count_delta != 0:
            lines.append(
                f"- Tubercles: {count_delta:+d} ({prev_count} -> {curr_count})"
            )

        lines.append("")

    # Guidance based on result
    lines.append("### Guidance")

    if prev_metrics is None:
        # First iteration
        lines.append(
            "This is your initial extraction. Analyze the results and screenshot to identify "
            "any issues (false positives, missed tubercles, irregular shapes, poor connections). "
            "Then decide whether to adjust parameters or try a different profile."
        )
    elif curr_hex >= best_hex and curr_hex > prev_metrics.get("hexagonalness", 0):
        # Score improved - this is the new best
        lines.append(
            "GOOD: The score improved and this is a new best result! "
            "Analyze what changed and consider whether further small adjustments "
            "in the same direction could yield additional improvement. "
            "If the score is above target or visually excellent, consider accepting."
        )
    elif curr_hex > prev_metrics.get("hexagonalness", 0):
        # Score improved but not new best
        lines.append(
            "The score improved from the previous iteration but hasn't exceeded "
            "the best result yet. Continue refining in this direction."
        )
    elif curr_hex < prev_metrics.get("hexagonalness", 0) - 0.02:
        # Score decreased significantly
        lines.append(
            "WARNING: The score DECREASED significantly. Your last parameter change "
            "made things worse. Consider reverting that change and trying a different "
            "adjustment instead. Check the screenshot to understand what went wrong "
            "(e.g., too many false positives, missing tubercles, bad connections)."
        )
    else:
        # Score roughly unchanged
        lines.append(
            "The score is roughly unchanged. This could indicate you're near an optimum, "
            "or that the parameter you adjusted doesn't strongly affect this image. "
            "Try a different parameter, or if you've been oscillating around the same "
            "score for 2-3 iterations, consider accepting the result."
        )

    lines.append("")

    # Recent history if provided
    if history_summary and len(history_summary) > 1:
        lines.append("### Recent History")
        for trial in history_summary[-5:]:  # Show last 5
            iter_num = trial.get("iteration", "?")
            hex_score = trial.get("hexagonalness", 0)
            count = trial.get("n_tubercles", 0)
            lines.append(f"- Iter {iter_num}: hexagonalness={hex_score:.3f}, tubercles={count}")
        lines.append("")

    # Iterations remaining warning
    remaining = max_iterations - iteration
    if remaining <= 2:
        lines.append(f"**NOTE:** Only {remaining} iteration(s) remaining. ")
        if remaining == 1:
            lines.append(
                "This is your last chance to improve. Make your best adjustment "
                "or accept the current result if it's satisfactory."
            )
        else:
            lines.append(
                "Consider whether to make a final adjustment or accept the best result."
            )
        lines.append("")

    lines.append(
        "Analyze the screenshot (if not already done), explain your reasoning, "
        "and either adjust parameters for another extraction or call accept_result "
        "if you're satisfied."
    )

    return "\n".join(lines)


# Few-shot examples that can be included in prompts for specific scenarios
FEW_SHOT_FALSE_POSITIVES = """**Observation:** I see 87 detected tubercles but many small circles (especially in the background corners) don't look like real tubercles - they appear to be noise or artifacts.

**Reasoning:** The threshold of 0.04 is very sensitive and picking up weak signals. The min_circularity of 0.4 is also quite permissive.

**Action:** I'll increase threshold from 0.04 to 0.06 to reject low-confidence detections. This should remove the noise while keeping the clear tubercles.

```
set_params({"threshold": 0.06})
run_extraction()
```"""

FEW_SHOT_MISSING_TUBERCLES = """**Observation:** Only 24 tubercles detected, but I can clearly see 40-50 bright circular spots in the image. Many obvious tubercles in the center weren't detected.

**Reasoning:** The threshold of 0.15 is quite conservative and the min_diameter_um of 6.0 might be filtering out smaller tubercles.

**Action:** I'll lower threshold to 0.10 and reduce min_diameter_um to 4.5 to capture more of the visible tubercles.

```
set_params({"threshold": 0.10, "min_diameter_um": 4.5})
run_extraction()
```"""

FEW_SHOT_CONNECTION_ISSUES = """**Observation:** 52 tubercles detected with hexagonalness of 0.55. Looking at the connections, I see several very long edges that cross the pattern diagonally - these shouldn't exist in a proper hexagonal arrangement.

**Reasoning:** The Delaunay triangulation includes all possible edges, but some cross empty regions where there are no tubercles. Switching to Gabriel graph should remove edges that pass through empty circles.

**Action:** Change neighbor_graph from delaunay to gabriel.

```
set_params({"neighbor_graph": "gabriel"})
run_extraction()
```"""

FEW_SHOT_ACCEPTING_RESULT = """**Observation:** Iteration 8: hexagonalness = 0.72, tubercles = 48. Previous iterations were 0.71, 0.70, 0.72, 0.71 - we've been oscillating around 0.71 for 4 iterations now.

**Reasoning:** The score has plateaued and visual inspection shows good coverage:
- Most visible tubercles are detected
- No obvious false positives
- Connections form a reasonable hexagonal pattern
- Edge regions have some gaps but that's expected

Further parameter tweaking isn't improving the score. The target was 0.70 and we've exceeded it.

**Action:** Accept this result as optimal.

```
accept_result("Target hexagonalness (0.70) achieved with score of 0.72. Pattern shows good coverage with 48 tubercles. Score has plateaued over 4 iterations, indicating this is near-optimal for this image.")
```"""


class StopOptimization(Exception):
    """Exception raised to signal that optimization should stop."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class ExtractionOptimizer:
    """Orchestrates parameter optimization via LLM agent.

    Uses an LLM provider to iteratively adjust extraction parameters,
    seeking to maximize the hexagonalness score while maintaining
    reasonable detection coverage.
    """

    def __init__(
        self,
        provider: AgentLLMProvider,
        ui_base_url: str = "http://localhost:5010",
        verbose: bool = False,
        log_callback: Callable[[str], None] | None = None,
        run_logger: AgentRunLogger | None = None,
    ):
        """Initialize the optimizer.

        Args:
            provider: LLM provider instance (e.g., ClaudeAgentProvider)
            ui_base_url: Base URL of the fish-scale-ui Flask application
            verbose: Whether to print detailed logs
            log_callback: Optional callback for log messages
            run_logger: Optional logger for detailed prompt/response logging
        """
        self.provider = provider
        self.ui_url = ui_base_url.rstrip("/")
        self.verbose = verbose
        self.log_callback = log_callback
        self._client = httpx.Client(timeout=120)

        # Run logger for detailed prompt/response tracking
        self.run_logger = run_logger or AgentRunLogger()

        # Optimization state
        self._state: OptimizationState | None = None
        self._target_hexagonalness: float = 0.7
        self._max_iterations: int = 10
        self._accepted: bool = False
        self._accept_reason: str = ""
        self._extraction_count: int = 0  # Track actual extraction runs

    def _log(self, message: str):
        """Log a message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {message}"
        if self.verbose:
            print(log_line, flush=True)  # Flush for subprocess capture
        if self.log_callback:
            self.log_callback(log_line)

    def _api_url(self, endpoint: str) -> str:
        """Build full API URL for tool endpoints."""
        return f"{self.ui_url}/api/tools/{endpoint.lstrip('/')}"

    def _execute_tool(self, name: str, args: dict) -> Any:
        """Execute a tool by calling the appropriate API endpoint.

        Args:
            name: Tool name
            args: Tool arguments

        Returns:
            Tool result

        Raises:
            StopOptimization: When optimization should stop (target reached or accepted)
        """
        # Check if we should stop before executing any more tools
        if self._accepted:
            raise StopOptimization(self._accept_reason or "Result already accepted")

        self._log(f"Tool: {name}({args})")

        try:
            if name == "run_extraction":
                result = self._run_extraction()
                # Check stopping conditions after extraction
                self._check_stopping_conditions()
                return result
            elif name == "get_screenshot":
                return self._get_screenshot(args.get("include_overlay", True))
            elif name == "get_metrics":
                return self._get_metrics()
            elif name == "get_params":
                return self._get_params()
            elif name == "set_params":
                return self._set_params(args)
            elif name == "load_profile":
                return self._load_profile(args.get("profile_name", "default"))
            elif name == "accept_result":
                result = self._accept_result(args.get("reason", ""))
                # Raise to stop the loop immediately
                raise StopOptimization(self._accept_reason)
            elif name == "get_history":
                return self._get_history()
            else:
                raise ValueError(f"Unknown tool: {name}")

        except StopOptimization:
            # Re-raise StopOptimization without wrapping
            raise
        except httpx.HTTPStatusError as e:
            self._log(f"HTTP Error: {e}")
            raise Exception(f"API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            self._log(f"Tool error: {e}")
            raise

    def _check_stopping_conditions(self) -> None:
        """Check if optimization should stop based on current state.

        Raises:
            StopOptimization: If target hexagonalness is achieved or max iterations reached
        """
        if not self._state:
            return

        current_hex = self._state.current_metrics.get("hexagonalness", 0)

        # Check if target hexagonalness achieved
        if current_hex >= self._target_hexagonalness:
            reason = f"Target hexagonalness achieved: {current_hex:.3f} >= {self._target_hexagonalness}"
            self._accepted = True
            self._accept_reason = reason
            self._log(f"AUTO-ACCEPT: {reason}")
            raise StopOptimization(reason)

        # Check if max iterations reached
        if self._extraction_count >= self._max_iterations:
            reason = f"Maximum iterations reached: {self._extraction_count}"
            self._accepted = True
            self._accept_reason = reason
            self._log(f"MAX ITERATIONS: {reason}")
            raise StopOptimization(reason)

    def _run_extraction(self) -> dict:
        """Run extraction with current parameters."""
        # Increment extraction counter
        self._extraction_count += 1

        # Get current params
        params_resp = self._client.get(self._api_url("/params"))
        params_resp.raise_for_status()
        params = params_resp.json().get("parameters", {})

        # Run extraction
        resp = self._client.post(f"{self.ui_url}/api/extract", json=params)
        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            raise Exception(data["error"])

        # Get statistics (includes hexagonalness)
        stats_resp = self._client.get(self._api_url("/statistics"))
        stats_resp.raise_for_status()
        stats = stats_resp.json()

        n_tubercles = len(data.get("tubercles", []))
        n_edges = len(data.get("edges", []))

        # Build metrics dict
        metrics = {
            "n_tubercles": n_tubercles,
            "n_edges": n_edges,
            "hexagonalness": stats.get("hexagonalness_score", 0),
            "mean_diameter_um": stats.get("mean_diameter_um", 0),
            "std_diameter_um": stats.get("std_diameter_um", 0),
            "mean_space_um": stats.get("mean_space_um", 0),
            "std_space_um": stats.get("std_space_um", 0),
        }

        self._log(
            f"Extraction [{self._extraction_count}/{self._max_iterations}]: "
            f"{n_tubercles} tubercles, hexagonalness={metrics['hexagonalness']:.3f}"
        )

        # Update state
        if self._state:
            self._state.iteration = self._extraction_count
            self._state.current_metrics = metrics
            self._state.current_params = params.copy()

            # Check if this is the best result
            if metrics["hexagonalness"] > self._state.best_metrics.get(
                "hexagonalness", 0
            ):
                self._state.best_metrics = metrics.copy()
                self._state.best_params = params.copy()
                self._state.best_iteration = self._extraction_count
                self._log(f"New best! hexagonalness={metrics['hexagonalness']:.3f}")

            # Record this trial in history
            self._record_trial("")

        return {
            "success": True,
            "iteration": self._extraction_count,
            "metrics": metrics,
            "message": f"Extraction [{self._extraction_count}/{self._max_iterations}]: {n_tubercles} tubercles, hexagonalness={metrics['hexagonalness']:.3f}",
        }

    def _get_screenshot(self, include_overlay: bool = True) -> dict:
        """Capture current view."""
        params = {
            "overlay": str(include_overlay).lower(),
            "numbers": "false",
            "scale_bar": "false",
        }
        resp = self._client.get(self._api_url("/screenshot"), params=params)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            raise Exception(data.get("error", "Screenshot failed"))

        width = data.get("width", 0)
        height = data.get("height", 0)
        self._log(f"Screenshot: {width}x{height} pixels")

        return {
            "image_data": data["image_b64"],
            "width": width,
            "height": height,
            "note": f"Image dimensions: {width}x{height} pixels",
        }

    def _get_metrics(self) -> dict:
        """Get current quality metrics."""
        resp = self._client.get(self._api_url("/statistics"))
        resp.raise_for_status()
        stats = resp.json()

        return {
            "hexagonalness": stats.get("hexagonalness_score", 0),
            "n_tubercles": stats.get("n_tubercles", 0),
            "n_edges": stats.get("n_edges", 0),
            "mean_diameter_um": stats.get("mean_diameter_um", 0),
            "std_diameter_um": stats.get("std_diameter_um", 0),
            "mean_space_um": stats.get("mean_space_um", 0),
            "std_space_um": stats.get("std_space_um", 0),
            "target_hexagonalness": self._target_hexagonalness,
        }

    def _get_params(self) -> dict:
        """Get current parameter values."""
        resp = self._client.get(self._api_url("/params"))
        resp.raise_for_status()
        return resp.json().get("parameters", {})

    def _set_params(self, params: dict) -> dict:
        """Update extraction parameters."""
        resp = self._client.post(self._api_url("/params"), json=params)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            raise Exception(data.get("error", "Set params failed"))

        updated = data.get("parameters", {})
        self._log(f"Params updated: {params}")

        if self._state:
            self._state.current_params.update(updated)

        return updated

    def _load_profile(self, profile_name: str) -> dict:
        """Load a preset parameter profile."""
        # The UI has a profile loading endpoint
        resp = self._client.post(
            f"{self.ui_url}/api/profile", json={"name": profile_name}
        )
        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            raise Exception(data["error"])

        self._log(f"Loaded profile: {profile_name}")

        if self._state:
            self._state.current_params = data.get("parameters", {})

        return {
            "success": True,
            "profile": profile_name,
            "parameters": data.get("parameters", {}),
        }

    def _accept_result(self, reason: str) -> dict:
        """Signal that optimization should stop."""
        self._accepted = True
        self._accept_reason = reason
        self._log(f"Result accepted: {reason}")

        return {
            "accepted": True,
            "reason": reason,
            "best_iteration": self._state.best_iteration if self._state else 0,
            "best_hexagonalness": (
                self._state.best_metrics.get("hexagonalness", 0) if self._state else 0
            ),
        }

    def _get_history(self) -> dict:
        """Get history of tried parameter combinations."""
        if not self._state:
            return {"trials": [], "best_iteration": 0}

        trials = []
        for trial in self._state.history:
            trials.append(
                {
                    "iteration": trial.iteration,
                    "hexagonalness": trial.metrics.get("hexagonalness", 0),
                    "n_tubercles": trial.metrics.get("n_tubercles", 0),
                    "params_summary": {
                        k: trial.params.get(k)
                        for k in [
                            "threshold",
                            "min_diameter_um",
                            "min_circularity",
                            "blur_sigma",
                        ]
                        if k in trial.params
                    },
                }
            )

        return {
            "trials": trials,
            "best_iteration": self._state.best_iteration,
            "best_hexagonalness": self._state.best_metrics.get("hexagonalness", 0),
            "current_iteration": self._state.iteration,
        }

    def _record_trial(self, llm_reasoning: str = "") -> None:
        """Record the current state as a trial in history."""
        if not self._state:
            return

        trial = TrialRecord(
            iteration=self._state.iteration,
            params=self._state.current_params.copy(),
            metrics=self._state.current_metrics.copy(),
            screenshot_path=None,
            llm_reasoning=llm_reasoning,
        )
        self._state.history.append(trial)

    def load_image(self, image_path: str | Path) -> dict:
        """Load an image into the UI.

        Args:
            image_path: Path to the image file

        Returns:
            Image info dict
        """
        path = str(Path(image_path).resolve())
        self._log(f"Loading image: {path}")
        resp = self._client.post(self._api_url("/load-image"), json={"path": path})
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise Exception(data.get("error", "Load failed"))
        return data

    def set_calibration(self, um_per_px: float) -> dict:
        """Set the calibration.

        Args:
            um_per_px: Micrometers per pixel

        Returns:
            Calibration info dict
        """
        self._log(f"Setting calibration: {um_per_px} um/px")
        resp = self._client.post(
            self._api_url("/calibration"), json={"um_per_px": um_per_px}
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise Exception(data.get("error", "Calibration failed"))
        return data.get("calibration", {})

    async def optimize(
        self,
        image_path: str,
        calibration: float,
        starting_profile: str = "default",
        target_hexagonalness: float = 0.7,
        max_iterations: int = 10,
        on_iteration: Callable[[OptimizationState], None] | None = None,
    ) -> OptimizationState:
        """Run the optimization loop.

        Args:
            image_path: Path to the image file
            calibration: Calibration value (micrometers per pixel)
            starting_profile: Initial parameter profile to load
            target_hexagonalness: Target hexagonalness score (0-1)
            max_iterations: Maximum optimization iterations
            on_iteration: Callback after each extraction iteration

        Returns:
            Final optimization state with best parameters found
        """
        self._log(f"Starting optimization: target={target_hexagonalness}, max_iter={max_iterations}")
        self._log(f"Provider: {self.provider.provider_name}/{self.provider.model_name}")

        # Store config and reset counters
        self._target_hexagonalness = target_hexagonalness
        self._max_iterations = max_iterations
        self._accepted = False
        self._accept_reason = ""
        self._extraction_count = 0

        # Load image and set calibration
        self.load_image(image_path)
        self.set_calibration(calibration)

        # Load starting profile
        try:
            self._load_profile(starting_profile)
        except Exception as e:
            self._log(f"Warning: Could not load profile {starting_profile}: {e}")

        # Get initial params
        initial_params = self._get_params()

        # Initialize state
        self._state = OptimizationState(
            iteration=0,
            current_params=initial_params,
            current_metrics={},
            best_params=initial_params.copy(),
            best_metrics={"hexagonalness": 0},
            best_iteration=0,
            history=[],
        )

        # Build initial user message
        user_message = f"""Optimize extraction parameters for this fish scale image.

Target hexagonalness: {target_hexagonalness}
Maximum iterations: {max_iterations}
Starting profile: {starting_profile}
Calibration: {calibration} um/px

Start by running extraction with the current parameters to establish a baseline, then analyze the results and iteratively improve.

When you achieve hexagonalness >= {target_hexagonalness} or believe no further improvement is possible, call accept_result with your reasoning."""

        # Start run logging
        log_file = self.run_logger.start_run(
            image_path=image_path,
            calibration=calibration,
            provider=self.provider.provider_name,
            model=self.provider.model_name,
            target_hexagonalness=target_hexagonalness,
            max_iterations=max_iterations,
            initial_profile=starting_profile,
            system_prompt=OPTIMIZER_SYSTEM_PROMPT,
            user_message=user_message,
        )
        self._log(f"Run log: {log_file}")

        # Reset usage tracking if provider supports it
        if hasattr(self.provider, "reset_usage"):
            self.provider.reset_usage()

        # Callback wrapper to notify on iteration changes
        last_iteration = [0]  # Use list for closure mutability

        def on_agent_iteration(agent_iter):
            """Handle each agent iteration from the provider."""
            # Log usage after every LLM call for real-time cost tracking
            if hasattr(self.provider, "get_usage"):
                usage = self.provider.get_usage()
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
                cost_usd = usage.get("cost_usd", 0)
                model = usage.get("model", self.provider.model_name)
                self._log(f"Usage: {input_tokens} input, {output_tokens} output, ${cost_usd:.4f} ({model})")

            # Log the full LLM response as JSON (includes text and tool calls)
            if agent_iter and agent_iter.response_json:
                # Replace newlines with pipe separator for single-line logging
                response_oneline = agent_iter.response_json.replace('\n', ' | ')
                self._log(f"LLM-Response: {response_oneline}")

            # Log prompt statistics and content
            if agent_iter and agent_iter.prompt_size_bytes > 0:
                self._log(f"Prompt-Stats: size={agent_iter.prompt_size_bytes}")
                # Log full prompt content (with base64 already truncated by provider)
                if agent_iter.prompt_content:
                    # Replace newlines with pipe separator for single-line logging
                    prompt_oneline = agent_iter.prompt_content.replace('\n', ' | ')
                    # No truncation - user wants full prompt for analysis
                    # Base64 data is already truncated by the provider
                    self._log(f"LLM-Prompt: {prompt_oneline}")

            # Only notify callback when extraction count changes
            if self._state and self._state.iteration != last_iteration[0]:
                # End previous iteration log if any
                if last_iteration[0] > 0:
                    self.run_logger.end_iteration()

                last_iteration[0] = self._state.iteration

                # Start new iteration log
                phase = "profile_selection" if self._state.iteration == 1 else "tuning"
                self.run_logger.start_iteration(self._state.iteration, phase)
                self.run_logger.log_metrics(
                    self._state.current_metrics,
                    self._state.current_params
                )

                if on_iteration:
                    on_iteration(self._state)

        # Wrap tool executor to log tool calls
        def logged_tool_executor(name: str, args: dict):
            result = self._execute_tool(name, args)
            self.run_logger.log_tool_call(name, args, result)
            return result

        # Execute agent loop
        final_response = ""
        final_status = "completed"
        try:
            final_response = await self.provider.run_agent_loop(
                tools=OPTIMIZATION_TOOLS,
                tool_executor=logged_tool_executor,
                system_prompt=OPTIMIZER_SYSTEM_PROMPT,
                user_message=user_message,
                max_iterations=max_iterations * 5,  # Allow more LLM calls than extraction iterations
                on_iteration=on_agent_iteration,
            )
            self._log(f"Agent completed normally: {final_response[:200] if final_response else '(no response)'}...")
        except StopOptimization as e:
            # Expected termination - optimization goal reached
            self._log(f"Optimization stopped: {e.reason}")
            final_status = "completed"
        except Exception as e:
            self._log(f"Agent error: {e}")
            final_status = "error"
            # Log error to run log
            import traceback
            error_msg = traceback.format_exc()
            self._log(f"Traceback: {error_msg}")
            self.run_logger.log_error(error_msg)

        # End final iteration log
        if last_iteration[0] > 0:
            self.run_logger.end_iteration()

        # Final callback notification
        if on_iteration and self._state:
            on_iteration(self._state)

        # Log final results
        if self._state:
            self._log("=" * 50)
            self._log("OPTIMIZATION COMPLETE")
            self._log(f"  Extractions run: {self._extraction_count}")
            self._log(f"  Best iteration: {self._state.best_iteration}")
            self._log(f"  Best hexagonalness: {self._state.best_metrics.get('hexagonalness', 0):.3f}")
            self._log(f"  Best tubercles: {self._state.best_metrics.get('n_tubercles', 0)}")
            self._log(f"  Accepted: {self._accepted}")
            if self._accept_reason:
                self._log(f"  Reason: {self._accept_reason}")
            self._log("=" * 50)

        # Log usage stats if available
        usage = {}
        if hasattr(self.provider, "get_usage"):
            usage = self.provider.get_usage()
            self._log(f"Usage: {usage.get('total_tokens', 0):,} tokens, ${usage.get('cost_usd', 0):.4f}")

        # End run logging
        self.run_logger.end_run(
            status=final_status,
            final_metrics=self._state.current_metrics if self._state else None,
            final_params=self._state.best_params if self._state else None,
            best_iteration=self._state.best_iteration if self._state else 0,
            best_hexagonalness=self._state.best_metrics.get("hexagonalness", 0) if self._state else 0,
            accept_reason=self._accept_reason,
        )

        return self._state

    def optimize_sync(
        self,
        image_path: str,
        calibration: float,
        starting_profile: str = "default",
        target_hexagonalness: float = 0.7,
        max_iterations: int = 10,
        on_iteration: Callable[[OptimizationState], None] | None = None,
    ) -> OptimizationState:
        """Synchronous version of optimize().

        Args:
            image_path: Path to the image file
            calibration: Calibration value (micrometers per pixel)
            starting_profile: Initial parameter profile to load
            target_hexagonalness: Target hexagonalness score (0-1)
            max_iterations: Maximum optimization iterations
            on_iteration: Callback after each extraction iteration

        Returns:
            Final optimization state with best parameters found
        """
        import asyncio

        return asyncio.run(
            self.optimize(
                image_path=image_path,
                calibration=calibration,
                starting_profile=starting_profile,
                target_hexagonalness=target_hexagonalness,
                max_iterations=max_iterations,
                on_iteration=on_iteration,
            )
        )

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
