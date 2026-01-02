# Gradient-Based Hexagonalness Optimization

## Overview

This specification describes a gradient-based optimization feature for the Extraction tab that iteratively adjusts extraction parameters to maximize the Hexagonalness score. Unlike the existing LLM-powered `extraction_optimizer.py`, this approach uses deterministic numerical gradient ascent.

## User Requirements

1. **Manual Step Mode**: Button to perform one gradient step at a time
2. **Automatic Mode**: Button that runs optimization until convergence (with stop button)
3. **Live UI Updates**: Overlay updates with new TUB/ITC after each iteration
4. **Display Precision**: Hexagonalness displayed to 3 decimal places in lower right

## Technical Approach

### Gradient Estimation

Since Hexagonalness is not analytically differentiable with respect to extraction parameters (it's computed from blob detection output), we use **numerical gradient estimation via central finite differences**:

```
gradient[i] = (H(params + δ*e_i) - H(params - δ*e_i)) / (2δ)
```

Where:
- `H(params)` = Hexagonalness score from extraction with given parameters
- `δ` = Step size for parameter `i`
- `e_i` = Unit vector in direction of parameter `i`

### Parameters to Optimize

| Parameter | Range | Default | Step Size (δ) | Notes |
|-----------|-------|---------|---------------|-------|
| threshold | 0.01-0.50 | 0.05 | 0.01 | Detection sensitivity |
| min_diameter_um | 0.5-20.0 | 2.0 | 0.5 | Filter small blobs |
| max_diameter_um | 1.0-50.0 | 10.0 | 1.0 | Filter large blobs |
| min_circularity | 0.0-1.0 | 0.5 | 0.05 | Shape filter |
| clahe_clip | 0.01-0.20 | 0.03 | 0.01 | Contrast enhancement |
| clahe_kernel | 4-32 | 8 | 2 | Integer, CLAHE tile size |
| blur_sigma | 0.0-5.0 | 1.0 | 0.2 | Gaussian smoothing |

**Total: 7 parameters** → Each gradient estimation requires 14 extraction calls.

### Optimization Algorithm

```python
def gradient_ascent_step(params, learning_rates, bounds):
    """One step of gradient ascent."""
    gradient = estimate_gradient(params)

    # Update parameters with bounds checking
    for i, param in enumerate(params):
        new_value = param + learning_rates[i] * gradient[i]
        params[i] = clamp(new_value, bounds[i].min, bounds[i].max)

    return params, gradient

def optimize(params, target_delta=0.001, max_iterations=20):
    """Run optimization until convergence."""
    prev_score = evaluate(params)

    for iteration in range(max_iterations):
        params, gradient = gradient_ascent_step(params, learning_rates, bounds)
        score = evaluate(params)

        yield params, score, iteration  # For UI updates

        # Convergence check
        if abs(score - prev_score) < target_delta:
            break

        prev_score = score

    return params
```

### Learning Rates (Per-Parameter)

Different parameters have different scales. Use normalized learning rates:

| Parameter | Learning Rate | Rationale |
|-----------|---------------|-----------|
| threshold | 0.005 | Small changes have large effect |
| min_diameter_um | 0.25 | Medium sensitivity |
| max_diameter_um | 0.5 | Medium sensitivity |
| min_circularity | 0.025 | Very sensitive |
| clahe_clip | 0.005 | Small changes |
| clahe_kernel | 1 | Integer steps |
| blur_sigma | 0.1 | Medium sensitivity |

### Convergence Criteria

Stop when ANY of these conditions is met:
1. **Delta threshold**: `|H_new - H_prev| < 0.001`
2. **Max iterations**: `iteration >= 20`
3. **Score threshold**: `H >= 0.85` (excellent quality)
4. **User cancellation**: Stop button clicked

## Architecture

### Option A: Server-Side Gradient Computation (Recommended)

New API endpoint handles gradient computation and returns updated parameters:

```
POST /api/optimize-step
Request:
{
    "current_params": {...},
    "step_sizes": {...},        // Optional override
    "learning_rates": {...}     // Optional override
}

Response:
{
    "success": true,
    "new_params": {...},
    "gradient": {...},
    "hexagonalness": 0.723,
    "delta": 0.012,
    "tubercles": [...],
    "edges": [...],
    "statistics": {...},
    "iterations_internal": 14   // Number of extractions performed
}
```

**Advantages:**
- Fewer HTTP round trips (1 call per step vs 14)
- Parallel extraction calls on server
- Better error handling

**Disadvantages:**
- More complex backend
- Longer request time (~30-60 seconds per step)

### Option B: Client-Side Orchestration

JavaScript orchestrates gradient estimation by making multiple `/api/extract` calls:

**Advantages:**
- Simpler backend (no new endpoints)
- Progressive UI updates during gradient estimation

**Disadvantages:**
- Many HTTP round trips (14+ per step)
- More network overhead
- Harder to parallelize

### Recommendation: Hybrid Approach

Use **Option A** (server-side) for gradient computation, but add a streaming/progress endpoint for real-time updates:

```
GET /api/optimize-step/progress?request_id=xxx
→ Server-Sent Events stream with progress updates
```

Or use WebSocket for bidirectional communication.

## Implementation Plan

### Phase 1: Backend API

1. **New file**: `src/fish_scale_ui/services/optimizer.py`
   - `GradientOptimizer` class with:
     - `estimate_gradient(params)` - Compute numerical gradient
     - `step(params, learning_rates)` - One optimization step
     - `run(params, max_iterations, callback)` - Full optimization loop
   - Uses existing `run_extraction()` from `services/extraction.py`
   - Supports parallel extraction via `concurrent.futures`

2. **New endpoint** in `routes/api.py`:
   ```python
   @api_bp.route('/optimize-step', methods=['POST'])
   def optimize_step():
       """Perform one gradient ascent step."""

   @api_bp.route('/optimize-auto', methods=['POST'])
   def optimize_auto():
       """Run automatic optimization (streaming response)."""

   @api_bp.route('/optimize-stop', methods=['POST'])
   def optimize_stop():
       """Cancel running optimization."""
   ```

### Phase 2: Frontend UI

1. **Update `workspace.html`** - Add optimization controls to Configure tab:
   ```html
   <div class="optimization-section">
       <h3>Optimize Parameters</h3>
       <div class="optimization-controls">
           <button id="optimizeStepBtn">Step</button>
           <button id="optimizeAutoBtn">Auto</button>
           <button id="optimizeStopBtn" disabled>Stop</button>
       </div>
       <div class="optimization-status">
           <span id="optimizeIteration">-</span>
           <span id="optimizeHexScore">-</span>
           <span id="optimizeDelta">-</span>
       </div>
       <div class="optimization-settings">
           <label>Convergence delta:
               <input type="number" id="optimizeDeltaThreshold" value="0.001" step="0.001">
           </label>
           <label>Max iterations:
               <input type="number" id="optimizeMaxIterations" value="20">
           </label>
       </div>
   </div>
   ```

2. **New file**: `src/fish_scale_ui/static/js/optimize.js`
   - `runOptimizeStep()` - Single step
   - `runOptimizeAuto()` - Automatic loop
   - `stopOptimize()` - Cancel
   - `updateUIFromOptimization(result)` - Update overlay and stats

3. **Update hexagonalness display** in `workspace.html`:
   - Change stats bar display from `.toFixed(2)` to `.toFixed(3)` (line ~1540)

### Phase 3: Progress Feedback

1. **Progress indicator** during gradient estimation:
   - Show "Estimating gradient... (7/14 extractions)"
   - Progress bar for long operations

2. **History tracking**:
   - Record each step in optimization history
   - Display history chart (iteration vs hexagonalness)

## API Specification

### POST /api/optimize-step

Performs one gradient ascent step.

**Request Body:**
```json
{
    "params": {
        "threshold": 0.05,
        "min_diameter_um": 2.0,
        "max_diameter_um": 10.0,
        "min_circularity": 0.5,
        "clahe_clip": 0.03,
        "clahe_kernel": 8,
        "blur_sigma": 1.0
    },
    "learning_rates": {
        "threshold": 0.005,
        "min_diameter_um": 0.25,
        ...
    },
    "step_sizes": {
        "threshold": 0.01,
        ...
    }
}
```

**Response:**
```json
{
    "success": true,
    "new_params": {...},
    "hexagonalness": 0.723,
    "prev_hexagonalness": 0.711,
    "delta": 0.012,
    "gradient": {
        "threshold": -0.52,
        "min_diameter_um": 0.08,
        ...
    },
    "tubercles": [...],
    "edges": [...],
    "statistics": {...},
    "extractions_performed": 15
}
```

### POST /api/optimize-auto

Runs automatic optimization with streaming progress.

**Request Body:**
```json
{
    "params": {...},
    "delta_threshold": 0.001,
    "max_iterations": 20,
    "target_score": 0.85
}
```

**Response:** Server-Sent Events stream
```
event: progress
data: {"iteration": 1, "hexagonalness": 0.65, "status": "estimating_gradient"}

event: progress
data: {"iteration": 1, "hexagonalness": 0.68, "status": "step_complete", "delta": 0.03}

event: complete
data: {"final_params": {...}, "final_score": 0.78, "iterations": 8, "reason": "converged"}
```

### POST /api/optimize-stop

Cancels running optimization.

**Response:**
```json
{
    "success": true,
    "stopped_at_iteration": 5,
    "current_params": {...},
    "current_score": 0.72
}
```

## UI Behavior

### Step Mode

1. User clicks "Step" button
2. Button disabled, shows spinner
3. Backend computes gradient (14 extractions, ~30-60s)
4. UI updates with new params, tubercles, edges
5. Stats panel shows new hexagonalness (3 decimals)
6. Configure tab inputs update to new values
7. Button re-enabled

### Auto Mode

1. User clicks "Auto" button
2. "Auto" disabled, "Stop" enabled
3. Progress indicator shows iteration count
4. After each step:
   - Overlay updates with new detection
   - Stats update
   - Parameter inputs update
5. Continues until convergence or stop clicked
6. Final state: best parameters applied, "Auto" re-enabled

### Visual Feedback

- **Hexagonalness trend**: Small arrow (↑/↓) next to score showing direction
- **Parameter changes**: Highlight changed parameters briefly
- **Progress**: "Optimizing... Step 3/20 (Hexagonalness: 0.712 → 0.723)"

## Performance Considerations

### Extraction Time

- Single extraction: ~1-3 seconds
- Gradient estimation (14 extractions): ~15-45 seconds
- Full optimization (20 iterations): ~5-15 minutes

### Optimization Strategies

1. **Parallel extraction**: Run + and - perturbations concurrently
2. **Caching**: Cache extraction results for identical parameters
3. **Reduced parameter set**: Allow user to select which parameters to optimize
4. **Adaptive step sizes**: Reduce learning rate if oscillating

### Memory

- Store optimization history for undo/analysis
- Limit history to last 50 iterations

## Testing Strategy

### Unit Tests

1. `test_gradient_estimation.py`:
   - Verify gradient direction (increase param → increase/decrease H)
   - Test bounds handling
   - Test with known simple function

2. `test_optimizer_convergence.py`:
   - Verify convergence on test images
   - Test max iterations cutoff
   - Test delta threshold

### Integration Tests

1. API endpoint tests with mock extraction
2. Full optimization run on test image
3. UI interaction tests

### Manual Testing

1. Verify overlay updates during optimization
2. Check parameter input synchronization
3. Test stop button during optimization
4. Verify 3 decimal precision in display

## Comparison with Existing LLM Optimizer

| Aspect | LLM Optimizer | Gradient Optimizer |
|--------|---------------|-------------------|
| Cost | ~$0.05-0.50 per run | Free |
| Speed | 5-10 minutes | 5-15 minutes |
| Determinism | Non-deterministic | Deterministic |
| Intelligence | Can reason about visuals | Purely numerical |
| Local optima | May escape via reasoning | May get stuck |
| User control | Limited | Fine-grained |

**Recommendation**: Keep both options. Gradient optimizer for quick, free iterations. LLM optimizer for difficult cases requiring visual reasoning.

## Files to Modify/Create

### New Files
- `src/fish_scale_ui/services/optimizer.py` - Core optimization logic
- `src/fish_scale_ui/static/js/optimize.js` - Frontend optimization UI
- `tests/test_optimizer.py` - Unit tests

### Modified Files
- `src/fish_scale_ui/routes/api.py` - Add optimization endpoints
- `src/fish_scale_ui/templates/workspace.html` - Add optimization UI section
- `src/fish_scale_ui/static/css/main.css` - Styling for optimization UI

## Open Questions

1. **Where to place UI controls?**
   - Option A: In Configure tab (parameters are there)
   - Option B: In Extraction tab (extraction action)
   - Option C: New "Optimize" tab
   - **Recommendation**: Configure tab, below parameter controls

2. **Which parameters to optimize by default?**
   - All 7 parameters
   - Subset (threshold, min_circularity, clahe_clip most impactful)
   - User-selectable checkboxes
   - **Recommendation**: User-selectable with sensible defaults (threshold, min_circularity, blur_sigma)

3. **Handling noisy gradient estimates?**
   - Single-shot (current design)
   - Averaged over multiple estimates
   - Use larger step sizes
   - **Recommendation**: Start with single-shot, add averaging if needed

4. **Should we optimize neighbor_graph type?**
   - It's categorical, not continuous
   - Could try all 3 and pick best
   - **Recommendation**: No, keep as user choice

## Timeline Estimates

Phase 1 (Backend): Core implementation
Phase 2 (Frontend): UI integration
Phase 3 (Polish): Progress feedback, testing, refinement

## Appendix: Hexagonalness Formula

For reference, the hexagonalness score is computed as:

```
Hexagonalness = 0.40 × Spacing Uniformity + 0.45 × Degree Score + 0.15 × Edge Ratio Score
```

Where:
- **Spacing Uniformity** = `max(0, 1 - 2 × CV)` (CV = coefficient of variation of edge lengths)
- **Degree Score** = Weighted average based on neighbor counts (5-7 neighbors → 1.0, 4/8 → 0.7, 3/9 → 0.3)
- **Edge Ratio Score** = `max(0, 1 - |ratio - 2.5| / 2)` where ratio = edges/nodes

Implementation locations:
- Python: `fish_scale_analysis/core/measurement.py` → `calculate_hexagonalness()`
- JavaScript: `extraction.js` → `calculateHexagonalness()`
