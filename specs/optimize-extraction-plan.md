# Gradient-Based Hexagonalness Optimizer - Implementation Plan

## Overview

Implement a deterministic gradient-based optimizer that iteratively adjusts extraction parameters to maximize the hexagonalness score. Uses numerical gradient estimation via central finite differences.

## Files to Create

### 1. `src/fish_scale_ui/services/optimizer.py`
Core gradient optimization logic:
- `GradientOptimizer` class with parameter bounds and learning rates
- `estimate_gradient(params)` - Central finite differences (14 extractions)
- `step(params)` - One gradient ascent step
- `check_convergence(prev_score, new_score, iteration)` - Stop conditions
- Uses `ThreadPoolExecutor` for parallel extractions

**Parameters to optimize (7 total):**
| Parameter | Range | Step (delta) | Learning Rate |
|-----------|-------|--------------|---------------|
| threshold | 0.01-0.50 | 0.01 | 0.005 |
| min_diameter_um | 0.5-20.0 | 0.5 | 0.25 |
| max_diameter_um | 1.0-50.0 | 1.0 | 0.5 |
| min_circularity | 0.0-1.0 | 0.05 | 0.025 |
| clahe_clip | 0.01-0.20 | 0.01 | 0.005 |
| clahe_kernel | 4-32 | 2 | 1.0 (int) |
| blur_sigma | 0.0-5.0 | 0.2 | 0.1 |

### 2. `src/fish_scale_ui/static/js/optimize.js`
Frontend optimization UI module:
- `runStep()` - Single gradient step
- `runAuto()` - Auto-optimize until convergence
- `stop()` - Cancel running optimization
- `handleStepResult(result)` - Update params, overlay, stats
- `getEnabledParams()` - Get checked parameters

### 3. `tests/test_optimizer.py`
Unit tests for gradient optimizer

## Files to Modify

### 1. `src/fish_scale_ui/routes/api.py`
Add three endpoints after existing `/api/extract` endpoint (~line 451):

```python
# Module-level state
_optimizer_state = {'running': False, 'stop_requested': False}

@api_bp.route('/optimize-step', methods=['POST'])
def optimize_step():
    """One gradient step. Returns new_params, gradient, hexagonalness, tubercles, edges, statistics."""

@api_bp.route('/optimize-auto', methods=['POST'])
def optimize_auto():
    """Auto-optimize. Returns SSE stream with progress/step/complete events."""

@api_bp.route('/optimize-stop', methods=['POST'])
def optimize_stop():
    """Cancel running optimization."""
```

### 2. `src/fish_scale_ui/templates/workspace.html`
Add optimization section after extraction-actions div (after line 488):
- Parameter checkboxes (default: threshold, min_circularity, blur_sigma)
- Settings: delta threshold (0.001), max iterations (20), target score (0.85)
- Status display: iteration, hexagonalness, delta, best score
- Buttons: Step, Auto, Stop
- Progress bar for gradient estimation

### 3. `src/fish_scale_ui/static/css/main.css`
Add styles for `.optimization-section`, `.optimize-*` classes

### 4. `src/fish_scale_ui/templates/workspace.html` (script section)
Add `<script src="optimize.js">` after other JS includes (~line 1428)

## API Design

### POST /api/optimize-step
**Request:**
```json
{
  "params": {"threshold": 0.05, "min_diameter_um": 2.0, ...},
  "enabled_params": ["threshold", "min_circularity", "blur_sigma"]
}
```
**Response:**
```json
{
  "success": true,
  "new_params": {...},
  "gradient": {"threshold": -0.52, ...},
  "hexagonalness": 0.723,
  "prev_hexagonalness": 0.711,
  "delta": 0.012,
  "tubercles": [...],
  "edges": [...],
  "statistics": {...},
  "extractions_performed": 15
}
```

### POST /api/optimize-auto
**Request:** Same as optimize-step + `max_iterations`, `delta_threshold`, `target_score`
**Response:** SSE stream with events: `progress`, `step`, `complete`, `error`

## Algorithm

```python
def estimate_gradient(params, enabled_params):
    gradient = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for param in enabled_params:
            delta = PARAMETERS[param]['step']
            params_plus = {**params, param: clamp(params[param] + delta)}
            params_minus = {**params, param: clamp(params[param] - delta)}
            futures[f'{param}_plus'] = executor.submit(run_extraction, params_plus)
            futures[f'{param}_minus'] = executor.submit(run_extraction, params_minus)

        for param in enabled_params:
            delta = PARAMETERS[param]['step']
            score_plus = futures[f'{param}_plus'].result()['hexagonalness']
            score_minus = futures[f'{param}_minus'].result()['hexagonalness']
            gradient[param] = (score_plus - score_minus) / (2 * delta)
    return gradient

def step(params, enabled_params):
    gradient = estimate_gradient(params, enabled_params)
    new_params = {}
    for param, value in params.items():
        if param in enabled_params:
            lr = PARAMETERS[param]['lr']
            new_params[param] = clamp(value + lr * gradient[param])
        else:
            new_params[param] = value
    result = run_extraction(new_params)
    return new_params, gradient, result
```

## Convergence Criteria
Stop when ANY condition is met:
1. `|score_new - score_prev| < 0.001`
2. `iteration >= max_iterations` (default 20)
3. `score >= target_score` (default 0.85)
4. User clicks Stop

## UI Placement
Configure tab, after "Run Extraction" section (line 488), before tab pane close.

## Performance
- Single extraction: 1-3 seconds
- Gradient estimation (14 parallel with 4 workers): 3-10 seconds
- Full optimization (20 iterations): 1-4 minutes

## Implementation Order
1. Backend service (`optimizer.py`) - core logic
2. API endpoints in `api.py`
3. Frontend JS (`optimize.js`)
4. HTML UI in `workspace.html`
5. CSS styles in `main.css`
6. Tests
