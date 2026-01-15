# Bright Spot Detection Goal Specification

**Status:** Planning
**Created:** 2026-01-15
**Purpose:** Add a simpler VLM test mode to diagnose whether VLMs can accurately localize visual features

---

## Problem Statement

### Original Issue

The current AgenticEditing agent asks the VLM to complete a hexagonal tubercle pattern. Testing (2026-01-15) revealed that while:
- VLMs understand coordinates correctly (debug seeds verified this)
- VLMs avoid overlapping existing markers
- VLMs don't hallucinate regular grid patterns

**The VLM-placed tubercles do NOT align with actual bright spots in the image.**

This suggests the task may be too complex. The VLM must:
1. Understand the hexagonal pattern concept
2. Identify gaps in the existing pattern
3. Locate actual bright spots (features)
4. Place markers at precise pixel coordinates

This combines semantic reasoning (pattern completion) with precise visual localization - potentially too much for current VLMs.

### Proposed Solution

Add a simpler test mode: **"Find the N brightest spots in this image"**

This isolates the feature localization capability by:
- Removing pattern-completion complexity
- Focusing purely on "where are bright spots?"
- Providing a quantifiable N parameter for controlled testing
- Enabling comparison across different N values and VLM providers

---

## Bug Fix: LLM Prompt/Response Display Not Working

### Root Cause Analysis

The "Last LLM Prompt" and "Last LLM Response" containers in the AgenticEdit tab are empty because of a parsing bug.

**In `agent_api.py` lines 608-611:**
```python
if line_str.startswith('LLM-Prompt:'):
    status['last_prompt'] = line_str[11:].replace(' | ', '\n')
elif line_str.startswith('LLM-Response:'):
    status['last_response'] = line_str[13:].replace(' | ', '\n')
```

**But `editing_agent.py` logs with timestamps:**
```python
def _log(self, message: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_line = f"[{timestamp}] {message}"  # <-- Timestamp prefix!
```

**Actual log line format:**
```
[10:15:32] LLM-Prompt: {...}
```

The `startswith('LLM-Prompt:')` check fails because the line starts with `[10:15:32] `.

### Fix Required

Change the parsing from `startswith()` to `in` check:

```python
# In _monitor_edit_agent_process()
if 'LLM-Prompt:' in line_str:
    # Extract content after 'LLM-Prompt:'
    idx = line_str.index('LLM-Prompt:')
    status['last_prompt'] = line_str[idx + 11:].replace(' | ', '\n')
elif 'LLM-Response:' in line_str:
    idx = line_str.index('LLM-Response:')
    status['last_response'] = line_str[idx + 13:].replace(' | ', '\n')
```

This matches the approach already used in `agent_editing.js` (line 949):
```javascript
if (line.includes('LLM-Prompt:')) {
    const match = line.match(/LLM-Prompt:\s*(.+)$/i);
```

---

## Feature: Selectable Agent Goals

### Goals Overview

| Goal ID | Name | Description | Parameters |
|---------|------|-------------|------------|
| `hex_pattern` | Hexagonal Pattern Completion | Complete the hexagonal tubercle pattern (current behavior) | plateau_threshold, max_iterations |
| `bright_spots` | Find N Brightest Spots | Locate the N brightest circular spots in the image | N (spot count), min_separation |

### Goal Selection UI

Add to AgenticEdit tab Configuration section:

```
Agent Goal: [Hexagonal Pattern ▼]
            - Hexagonal Pattern Completion (default)
            - Find N Brightest Spots

[When "Find N Brightest Spots" selected:]
Number of Spots (N): [20____]
Min Separation (px): [30____]
```

### UI Implementation

**In `workspace.html`, add after Debug Seeds row:**

```html
<!-- Agent Goal Selection -->
<div class="agent-config-row">
    <label for="editAgentGoal">Agent Goal:</label>
    <select id="editAgentGoal" class="config-select">
        <option value="hex_pattern" selected>Hexagonal Pattern Completion</option>
        <option value="bright_spots">Find N Brightest Spots</option>
    </select>
</div>

<!-- Bright Spots Parameters (shown when goal=bright_spots) -->
<div id="editAgentBrightSpotsParams" class="agent-goal-params" style="display: none;">
    <div class="agent-config-row">
        <label for="editAgentSpotCount">Number of Spots (N):</label>
        <input type="number" id="editAgentSpotCount" class="config-input"
               value="20" min="1" max="200" step="1">
    </div>
    <div class="agent-config-row">
        <label for="editAgentMinSeparation">Min Separation (px):</label>
        <input type="number" id="editAgentMinSeparation" class="config-input"
               value="30" min="10" max="100" step="5">
    </div>
</div>
```

**In `agent_editing.js`, add goal toggle handler:**

```javascript
document.getElementById('editAgentGoal')?.addEventListener('change', (e) => {
    const brightSpotsParams = document.getElementById('editAgentBrightSpotsParams');
    if (brightSpotsParams) {
        brightSpotsParams.style.display = e.target.value === 'bright_spots' ? 'block' : 'none';
    }
});
```

---

## Backend Implementation

### CLI Changes (`cli.py`)

Add goal parameter to `edit` command:

```python
@click.option(
    '--goal',
    type=click.Choice(['hex_pattern', 'bright_spots']),
    default='hex_pattern',
    help='Agent goal: hex_pattern (complete pattern) or bright_spots (find N brightest)'
)
@click.option(
    '--spot-count', '-n',
    type=int,
    default=20,
    help='Number of spots to find (for bright_spots goal)'
)
@click.option(
    '--min-separation',
    type=int,
    default=30,
    help='Minimum pixel separation between spots (for bright_spots goal)'
)
def edit(image, provider, model, calibration, max_iterations, ...,
         goal, spot_count, min_separation):
```

### Agent API Changes (`agent_api.py`)

Pass goal parameters in `/api/agent/edit/start`:

```python
@agent_bp.route('/edit/start', methods=['POST'])
def start_edit_agent():
    # ... existing code ...

    goal = data.get('goal', 'hex_pattern')
    spot_count = data.get('spot_count', 20)
    min_separation = data.get('min_separation', 30)

    # Add to command
    cmd.extend(['--goal', goal])
    if goal == 'bright_spots':
        cmd.extend(['--spot-count', str(spot_count)])
        cmd.extend(['--min-separation', str(min_separation)])
```

### Editing Agent Changes (`editing_agent.py`)

Add goal parameter to `run()`:

```python
async def run(
    self,
    image_path: str | None = None,
    calibration: float | None = None,
    max_iterations: int = 30,
    plateau_threshold: int = 3,
    goal: str = "hex_pattern",  # NEW
    spot_count: int = 20,        # NEW
    min_separation: int = 30,    # NEW
    ...
) -> EditingState:
```

Select system prompt based on goal:

```python
if goal == "bright_spots":
    from .prompts import BRIGHT_SPOT_SYSTEM_PROMPT
    system_prompt = BRIGHT_SPOT_SYSTEM_PROMPT.format(
        spot_count=spot_count,
        min_separation=min_separation,
        image_width=image_width,
        image_height=image_height,
        calibration=cal_value,
    )
else:
    # Use existing EDITING_AGENT_SYSTEM_PROMPT
    system_prompt = EDITING_AGENT_SYSTEM_PROMPT.format(...)
```

---

## Bright Spot Detection System Prompt

**Add to `prompts.py`:**

```python
BRIGHT_SPOT_SYSTEM_PROMPT = """You are analyzing a grayscale SEM image to locate the brightest circular spots.

## Your Task

Find exactly {spot_count} of the brightest circular spots in this image and mark them with add_tubercle().

## What Makes a "Bright Spot"

- HIGH INTENSITY (white/light gray) circular or oval region
- Typically 10-30 pixels in diameter
- Contrasts clearly against the darker background
- Should be actual image features, not noise or artifacts

## Rules

1. **Find exactly {spot_count} spots** - no more, no less
2. **Prioritize brightness** - find the BRIGHTEST spots first
3. **Minimum separation** - spots must be at least {min_separation} pixels apart
4. **Only real features** - do NOT mark background noise or artifacts
5. **Accurate positions** - place markers at the CENTER of each bright spot

## Strategy

1. Get a screenshot to see the image
2. Identify the {spot_count} brightest circular spots
3. For each spot (starting with brightest):
   - Estimate the center coordinates (x, y)
   - Call add_tubercle(x, y)
4. Get a final screenshot to verify placements
5. Call finish() when all {spot_count} spots are marked

## Coordinate System

- Origin (0, 0) is TOP-LEFT
- X increases to the RIGHT
- Y increases DOWNWARD
- Image dimensions: {image_width} x {image_height} pixels
- Calibration: {calibration} um/pixel

## Example

For an image with many bright tubercles, finding the 10 brightest:

```
1. get_screenshot() -> See grayscale image with bright circular spots
2. Identify the 10 brightest spots by visual inspection
3. add_tubercle(x=245, y=180)  # Brightest spot
4. add_tubercle(x=410, y=295)  # 2nd brightest
5. ... continue for all 10 ...
6. get_screenshot() -> Verify all 10 markers are on bright spots
7. finish(reason="Marked 10 brightest spots as requested")
```

## Evaluation Criteria

Your success will be measured by:
1. **Position accuracy**: How close are your markers to actual bright spots?
2. **Brightness ranking**: Did you find the truly brightest spots?
3. **Separation compliance**: Are all spots at least {min_separation}px apart?

## Important

- Do NOT complete any hexagonal pattern
- Do NOT add more than {spot_count} spots
- ONLY mark spots where you see actual bright circular features
- If you cannot find {spot_count} distinct bright spots, mark as many as you can find and explain
"""
```

---

## Analysis and Scoring

### Bright Spot Scoring

After agent completion, evaluate accuracy:

```python
def evaluate_bright_spot_detection(
    placed_spots: list[dict],
    image_path: str,
    expected_count: int,
    min_separation: int,
) -> dict:
    """Evaluate bright spot detection accuracy.

    Returns:
        {
            "spots_placed": int,
            "spots_expected": int,
            "separation_violations": int,  # Pairs < min_separation
            "mean_intensity": float,        # Avg pixel intensity at spot centers
            "intensity_ranking_score": float,  # 0-1, are these really the brightest?
            "position_variance": float,     # How scattered are the spots?
        }
    """
    from PIL import Image
    import numpy as np

    # Load image and convert to grayscale
    img = Image.open(image_path).convert('L')
    img_array = np.array(img)

    # Calculate metrics
    results = {
        "spots_placed": len(placed_spots),
        "spots_expected": expected_count,
    }

    # Check separations
    violations = 0
    for i, s1 in enumerate(placed_spots):
        for s2 in placed_spots[i+1:]:
            dist = ((s1['x'] - s2['x'])**2 + (s1['y'] - s2['y'])**2) ** 0.5
            if dist < min_separation:
                violations += 1
    results["separation_violations"] = violations

    # Sample intensity at placed spots
    intensities = []
    for spot in placed_spots:
        x, y = int(spot['x']), int(spot['y'])
        if 0 <= x < img_array.shape[1] and 0 <= y < img_array.shape[0]:
            # Average intensity in 5x5 region around center
            region = img_array[max(0,y-2):y+3, max(0,x-2):x+3]
            intensities.append(np.mean(region))

    results["mean_intensity"] = np.mean(intensities) if intensities else 0
    results["intensity_std"] = np.std(intensities) if intensities else 0

    # Compare to top-N brightest pixels in image
    # (simplified - real implementation would use blob detection)
    flat = img_array.flatten()
    top_n_threshold = np.percentile(flat, 100 - (expected_count / len(flat) * 100 * 10))
    bright_pixel_frac = sum(1 for i in intensities if i >= top_n_threshold) / len(intensities) if intensities else 0
    results["intensity_ranking_score"] = bright_pixel_frac

    return results
```

### UI Display for Bright Spot Results

Add section to show bright spot evaluation:

```html
<!-- Bright Spot Analysis Section (shown for bright_spots goal) -->
<div id="editBrightSpotAnalysis" class="agent-section" style="display: none;">
    <h3>Bright Spot Detection Results</h3>
    <div class="seed-analysis-summary">
        <div class="seed-analysis-row">
            <span class="seed-analysis-label">Spots Found:</span>
            <span id="brightSpotCount">-</span>
        </div>
        <div class="seed-analysis-row">
            <span class="seed-analysis-label">Target Count:</span>
            <span id="brightSpotTarget">-</span>
        </div>
        <div class="seed-analysis-row">
            <span class="seed-analysis-label">Mean Intensity:</span>
            <span id="brightSpotIntensity">-</span>
        </div>
        <div class="seed-analysis-row">
            <span class="seed-analysis-label">Separation Violations:</span>
            <span id="brightSpotViolations">-</span>
        </div>
        <div class="seed-analysis-row">
            <span class="seed-analysis-label">Brightness Ranking Score:</span>
            <span id="brightSpotRankScore">-</span>
        </div>
    </div>
</div>
```

---

## File Changes Summary

### Bug Fix (Priority 1)

| File | Change |
|------|--------|
| `src/fish_scale_ui/routes/agent_api.py` | Fix LLM-Prompt/LLM-Response parsing to handle timestamp prefix |

### New Feature (Priority 2)

| File | Change |
|------|--------|
| `src/fish_scale_agent/prompts.py` | Add `BRIGHT_SPOT_SYSTEM_PROMPT` |
| `src/fish_scale_agent/cli.py` | Add `--goal`, `--spot-count`, `--min-separation` options |
| `src/fish_scale_agent/editing_agent.py` | Add goal parameter, select prompt based on goal |
| `src/fish_scale_agent/bright_spot_analysis.py` | NEW: Evaluation functions for bright spot detection |
| `src/fish_scale_ui/routes/agent_api.py` | Pass goal parameters to CLI command |
| `src/fish_scale_ui/static/js/agent_editing.js` | Add goal selector, parameter visibility toggle |
| `src/fish_scale_ui/templates/workspace.html` | Add goal dropdown and bright_spots parameters |

---

## Implementation Phases

### Phase 1: Bug Fix (LLM Display) - HIGH PRIORITY

**Estimated scope:** Small fix, ~30 minutes

1. Fix parsing in `agent_api.py`:
   - Change `startswith('LLM-Prompt:')` to `'LLM-Prompt:' in line_str`
   - Extract content after the marker, not from fixed position
   - Same for `LLM-Response:`

2. Test:
   - Run agent
   - Verify prompt/response appear in UI

### Phase 2: Goal Selection UI

**Estimated scope:** Medium, ~1-2 hours

1. Add goal dropdown to `workspace.html`
2. Add parameter inputs for bright_spots goal
3. Add JavaScript toggle in `agent_editing.js`
4. Update `startAgent()` to send goal parameters
5. Update `/api/agent/edit/start` to receive and pass parameters

### Phase 3: Backend Goal Support

**Estimated scope:** Medium, ~2-3 hours

1. Add CLI options to `cli.py`
2. Add `BRIGHT_SPOT_SYSTEM_PROMPT` to `prompts.py`
3. Modify `editing_agent.py` to select prompt based on goal
4. Adjust success criteria (no hexagonalness for bright_spots)

### Phase 4: Analysis and Evaluation

**Estimated scope:** Medium, ~2-3 hours

1. Create `bright_spot_analysis.py` with evaluation functions
2. Add analysis section to UI
3. Output analysis in STATUS line for UI consumption
4. Add to run logger for comparison across runs

### Phase 5: Documentation

**Estimated scope:** Small, ~30 minutes

1. Update CLAUDE.md with bright_spots goal documentation
2. Update CLI help text
3. Add usage examples

---

## Testing Checklist

### Bug Fix Verification
- [ ] Start AgenticEdit agent
- [ ] Observe "Last LLM Prompt" populates with actual prompt
- [ ] Observe "Last LLM Response" populates with actual response
- [ ] Copy buttons work for prompt/response content

### Bright Spots Goal Testing
- [ ] Goal dropdown appears in Configuration
- [ ] Selecting "Find N Brightest Spots" shows N and separation inputs
- [ ] Selecting "Hexagonal Pattern" hides bright spots inputs
- [ ] Agent runs with bright_spots goal
- [ ] Agent receives correct system prompt
- [ ] Agent places approximately N spots
- [ ] Spots respect minimum separation (mostly)
- [ ] Analysis section shows results
- [ ] Compare VLM accuracy: Do placed spots align with actual bright regions?

### Cross-Provider Testing
Test with each provider to compare bright spot localization accuracy:
- [ ] Claude (claude-sonnet-4-20250514)
- [ ] Gemini (gemini-2.0-flash)
- [ ] OpenRouter (try multiple models)

---

## Success Metrics

### For Bug Fix
- LLM prompts and responses visible in UI during agent run

### For Bright Spots Feature
A successful implementation allows us to answer:
1. **Can the VLM find bright spots?** - Mean intensity of placed spots vs image mean
2. **How accurate is positioning?** - Variance from actual feature centers
3. **Does N affect accuracy?** - Compare N=10 vs N=50 vs N=100
4. **Which VLM is best?** - Compare Claude vs Gemini vs others

This simpler test case will help diagnose the fundamental VLM localization issue before investing more effort in the complex hexagonal pattern task.

---

## Open Questions

1. **Ground truth generation**: How do we get "correct" bright spot positions for comparison?
   - Option A: Manual annotation of a few test images
   - Option B: Use traditional CV (blob detection with high threshold) as ground truth
   - Option C: Just measure intensity at placed positions

2. **Stopping condition**: For bright_spots goal, when does agent stop?
   - Option A: After placing exactly N spots
   - Option B: After one pass (screenshot → N placements → finish)
   - Recommendation: Option B (single pass) to keep test clean

3. **Separation enforcement**: Should agent receive feedback if spots too close?
   - Option A: Just report violations at end
   - Option B: Reject placements that violate separation
   - Recommendation: Option A (post-hoc analysis) to see VLM's natural behavior

---

## Version

This feature will be implemented as version **0.2.12**.
