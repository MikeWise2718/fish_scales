# Edit Tubercle Auto-Sizing Specification

## Overview

When manually adding tubercles in the Edit tab, provide an option to automatically determine the tubercle size by analyzing the image at the click location using the current detection parameters. This eliminates the need to manually adjust each tubercle's size after placement.

## Problem Statement

Currently, when adding a tubercle manually:
1. The tubercle is created with a **fixed default diameter** (either user-specified or calculated from the mean of existing tubercles)
2. Users often need to manually resize the tubercle afterward using the radius slider
3. This is tedious when adding many tubercles to images where tubercle sizes vary across the field

## Proposed Solution

Add an **"Auto-size from image"** checkbox in the Edit tab. When enabled:
1. Clicking to add a tubercle triggers a localized blob detection at the click location
2. The detected blob's diameter is used for the new tubercle
3. If no blob is detected, fall back to the default diameter behavior

### User Experience Flow

```
1. User enables "Auto-size from image" checkbox
2. User enters "Add Tubercle" mode
3. User clicks on an image location where a tubercle should be
4. System extracts a small region around the click point
5. System runs blob detection on that region using current Configure tab parameters
6. If blob detected:
   - Create tubercle with detected diameter
   - Optionally: snap to detected center (Phase 2)
   - Show toast: "Added tubercle #N (auto-sized: X.XX µm)"
7. If no blob detected:
   - Create tubercle with default diameter
   - Show toast: "Added tubercle #N (using default size)"
```

## UI Design

### Edit Tab Changes

Add a checkbox near the existing "Default Diameter" input:

```
Add/Chain Mode Settings
├── Default Diameter: [____] µm  (?)
│   └── Auto: 4.523 µm
└── [x] Auto-size from image      (?)
    └── Hint: Uses current detection parameters
```

**Checkbox behavior:**
- Enabled by default: **No** (preserve backward compatibility)
- Disabled when: Calibration not set (same as default diameter field)
- Persisted: In user settings (global, not per-image)

### Help Tooltip Content

> **Auto-size from image**
>
> When enabled, analyzes the image at the click location to determine the optimal tubercle size using the current detection parameters (threshold, min/max diameter, CLAHE settings, etc.).
>
> If no tubercle-like feature is detected at the click location, falls back to the Default Diameter value.
>
> **Tip:** Ensure your Configure tab parameters are set appropriately for the image before using this feature.

## Technical Design

### New API Endpoint

```
POST /api/analyze-point
```

**Request Body:**
```json
{
  "x": 245.5,
  "y": 312.8,
  "parameters": {
    "method": "log",
    "threshold": 0.05,
    "min_diameter_um": 2.0,
    "max_diameter_um": 10.0,
    "min_circularity": 0.5,
    "clahe_clip": 0.03,
    "clahe_kernel": 8,
    "blur_sigma": 1.0
  }
}
```

**Response (blob detected):**
```json
{
  "success": true,
  "detected": true,
  "diameter_px": 28.5,
  "diameter_um": 4.275,
  "center_x": 244.2,
  "center_y": 313.1,
  "circularity": 0.87,
  "confidence": 0.92
}
```

**Response (no blob detected):**
```json
{
  "success": true,
  "detected": false,
  "reason": "no_blob_found"
}
```

**Response (error):**
```json
{
  "success": false,
  "error": "Calibration not set"
}
```

### Backend Implementation

Location: `src/fish_scale_ui/routes/api.py`

```python
@api_bp.route('/analyze-point', methods=['POST'])
def analyze_point():
    """Analyze image at a point to detect tubercle size.

    Extracts a region around the specified point, runs blob detection
    with the given parameters, and returns the detected blob info.
    """
    from fish_scale_ui.services.extraction import analyze_point_for_tubercle

    if not _current_image['path']:
        return jsonify({'error': 'No image loaded'}), 400

    if not _current_image.get('calibration'):
        return jsonify({'error': 'Calibration not set'}), 400

    data = request.get_json() or {}
    x = float(data.get('x', 0))
    y = float(data.get('y', 0))
    parameters = data.get('parameters', {})

    um_per_px = _current_image['calibration'].get('um_per_px', 0.33)
    image_path = _current_image.get('web_path') or _current_image['path']

    try:
        result = analyze_point_for_tubercle(
            image_path=image_path,
            x=x,
            y=y,
            um_per_px=um_per_px,
            **parameters
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

### Extraction Service Addition

Location: `src/fish_scale_ui/services/extraction.py`

```python
def analyze_point_for_tubercle(
    image_path: str,
    x: float,
    y: float,
    um_per_px: float,
    method: str = "log",
    threshold: float = 0.05,
    min_diameter_um: float = 2.0,
    max_diameter_um: float = 10.0,
    min_circularity: float = 0.5,
    clahe_clip: float = 0.03,
    clahe_kernel: int = 8,
    blur_sigma: float = 1.0,
) -> dict:
    """
    Analyze a point in the image to detect if there's a tubercle there.

    Extracts a region around (x, y), runs blob detection, and returns
    the closest blob to the click point.

    Returns:
        Dictionary with detection results or {"detected": False}
    """
    # Calculate region size based on max_diameter
    # Use 3x max diameter to ensure we capture the full blob
    max_diameter_px = max_diameter_um / um_per_px
    region_size = int(max_diameter_px * 3)
    region_size = max(50, min(200, region_size))  # Clamp to reasonable range

    # Load image
    image = load_image(Path(image_path))
    h, w = image.shape[:2]

    # Calculate region bounds (centered on click point)
    half = region_size // 2
    x_min = max(0, int(x - half))
    x_max = min(w, int(x + half))
    y_min = max(0, int(y - half))
    y_max = min(h, int(y + half))

    # Extract and preprocess region
    region = image[y_min:y_max, x_min:x_max]
    preprocessed, _ = preprocess_pipeline(
        region,
        clahe_clip=clahe_clip,
        clahe_kernel=clahe_kernel,
        blur_sigma=blur_sigma,
    )

    # Create local calibration for the region
    calibration = CalibrationData(
        um_per_pixel=um_per_px,
        scale_bar_length_um=0,
        scale_bar_length_px=0,
        method="manual"
    )

    # Detect tubercles in the region
    tubercles = detect_tubercles(
        preprocessed,
        calibration,
        min_diameter_um=min_diameter_um,
        max_diameter_um=max_diameter_um,
        threshold=threshold,
        min_circularity=min_circularity,
        edge_margin_px=0,  # Don't exclude edges in small region
        method=method,
        refine_ellipse=True,
    )

    if not tubercles:
        return {"success": True, "detected": False, "reason": "no_blob_found"}

    # Find the blob closest to the click point (in local coordinates)
    click_local_x = x - x_min
    click_local_y = y - y_min

    closest = None
    closest_dist = float('inf')

    for tub in tubercles:
        dx = tub.centroid[0] - click_local_x
        dy = tub.centroid[1] - click_local_y
        dist = (dx**2 + dy**2) ** 0.5
        if dist < closest_dist:
            closest_dist = dist
            closest = tub

    # Check if closest blob is within reasonable distance
    # (should be within the detected radius)
    if closest_dist > closest.radius_px * 1.5:
        return {"success": True, "detected": False, "reason": "click_not_on_blob"}

    # Convert center back to global coordinates
    global_x = closest.centroid[0] + x_min
    global_y = closest.centroid[1] + y_min

    return {
        "success": True,
        "detected": True,
        "diameter_px": closest.diameter_px,
        "diameter_um": closest.diameter_um,
        "radius_px": closest.radius_px,
        "center_x": global_x,
        "center_y": global_y,
        "circularity": closest.circularity,
    }
```

### Frontend Implementation

Location: `src/fish_scale_ui/static/js/editor.js`

**State variables:**
```javascript
let autoSizeEnabled = false;
```

**New functions:**
```javascript
/**
 * Set auto-size enabled state
 */
function setAutoSizeEnabled(enabled) {
    autoSizeEnabled = enabled;
    // Persist to settings
    window.settings?.set('editor.autoSizeEnabled', enabled);
}

/**
 * Get auto-size enabled state
 */
function isAutoSizeEnabled() {
    return autoSizeEnabled;
}

/**
 * Analyze a point to get auto-sized diameter
 * @returns {Promise<{diameter_px: number, center_x: number, center_y: number} | null>}
 */
async function analyzePointForSize(x, y) {
    const params = window.configure?.getCurrentParams() || {};

    try {
        const response = await fetch('/api/analyze-point', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ x, y, parameters: params })
        });

        const result = await response.json();

        if (result.success && result.detected) {
            return {
                diameter_px: result.diameter_px,
                diameter_um: result.diameter_um,
                radius_px: result.radius_px,
                center_x: result.center_x,
                center_y: result.center_y,
            };
        }
        return null;
    } catch (error) {
        console.error('Auto-size analysis failed:', error);
        return null;
    }
}
```

**Modified `addTubercle` function:**
```javascript
async function addTubercle(x, y) {
    const calibration = getCalibration();
    const umPerPx = calibration?.um_per_px || 0.14;

    let effectiveRadius = getEffectiveDefaultRadius();
    let autoSized = false;

    // Try auto-sizing if enabled
    if (autoSizeEnabled) {
        const analysis = await analyzePointForSize(x, y);
        if (analysis) {
            effectiveRadius = analysis.radius_px;
            autoSized = true;
            // Optional Phase 2: snap to detected center
            // x = analysis.center_x;
            // y = analysis.center_y;
        }
    }

    const newTub = {
        id: nextTubId++,
        centroid_x: x,
        centroid_y: y,
        radius_px: effectiveRadius,
        diameter_um: (effectiveRadius * 2) * umPerPx,
        circularity: 1.0,
    };

    tubercles.push(newTub);

    // ... rest of existing code ...

    // Updated toast message
    const sizeInfo = autoSized
        ? `auto-sized: ${newTub.diameter_um.toFixed(2)} µm`
        : `default: ${newTub.diameter_um.toFixed(2)} µm`;
    window.app?.showToast(`Added tubercle #${newTub.id} (${sizeInfo})`, 'success');
}
```

### HTML Changes

Location: `src/fish_scale_ui/templates/workspace.html`

Add after the default diameter input:
```html
<div class="form-group">
    <label>
        <input type="checkbox" id="autoSizeEnabled">
        Auto-size from image
        <a href="/static/help/editing.html#auto-size"
           target="_blank"
           class="help-link"
           title="Help">?</a>
    </label>
    <span id="autoSizeHint" class="input-hint">
        Uses current detection parameters
    </span>
</div>
```

### Help Documentation Update

Add new section to `src/fish_scale_ui/static/help/editing.html`:

```html
<div class="section" id="auto-size">
    <h3 class="param-name">Auto-size from Image</h3>
    <p>When enabled, analyzes the image at each click location to automatically determine the correct tubercle size.</p>

    <h4>How It Works</h4>
    <ol class="step-list">
        <li>When you click to add a tubercle, a small region around the click point is extracted</li>
        <li>The region is analyzed using the current detection parameters from the Configure tab</li>
        <li>If a tubercle-like feature is detected, its measured diameter is used</li>
        <li>If no feature is detected, the Default Diameter is used as a fallback</li>
    </ol>

    <h4>When to Use</h4>
    <ul>
        <li><strong>Variable tubercle sizes:</strong> When tubercles vary significantly in size across the image</li>
        <li><strong>Filling gaps:</strong> When adding missed tubercles that should match their neighbors</li>
        <li><strong>Accurate measurements:</strong> When precise diameter measurements are important</li>
    </ul>

    <h4>When NOT to Use</h4>
    <ul>
        <li><strong>Noisy images:</strong> Detection may pick up noise instead of the intended feature</li>
        <li><strong>Uniform tubercles:</strong> If all tubercles are similar size, default diameter is faster</li>
        <li><strong>Low contrast:</strong> Detection may fail in areas with poor contrast</li>
    </ul>

    <div class="note">
        <strong>Requires Calibration:</strong> This feature requires calibration to be set because the detection parameters use micrometer-based size filters.
    </div>

    <div class="tip">
        <strong>Tip:</strong> Ensure your Configure tab parameters (threshold, min/max diameter, CLAHE settings) are appropriate for the image before enabling auto-size.
    </div>
</div>
```

## Implementation Phases

### Phase 1: Basic Auto-Sizing (MVP) - COMPLETE
- [x] Add checkbox UI
- [x] Add `/api/analyze-point` endpoint
- [x] Add `analyze_point_for_tubercle()` service function
- [x] Modify `addTubercle()` to call analysis when enabled
- [x] Add fallback to default diameter
- [x] Add toast notifications indicating auto-sized vs default
- [x] Persist checkbox state in settings
- [x] Update help documentation
- [x] Include ellipse parameters (major/minor axis, orientation, eccentricity) in detection
- [x] Fire `calibrationChanged` event when calibration is set

### Phase 2: Auto-Position - COMPLETE
- [x] Snap to detected center (enabled automatically with auto-size)
- [x] Adjust click position to detected blob center
- [x] Works in both Add Tubercle and Chain Mode

### Phase 3: Preview Mode (Future)
- [ ] Show ghost circle at detected size while hovering
- [ ] Update in real-time as cursor moves
- [ ] Performance optimization needed for smooth experience

## Performance Considerations

1. **Region size**: Use ~3x max_diameter to ensure blob is fully captured without processing too much image data. Clamp to 50-200 pixels.

2. **Latency**: Target <100ms for analysis. The small region size and single-blob detection should be fast.

3. **Caching**: Consider caching the preprocessed image if multiple clicks happen in quick succession.

4. **Loading indicator**: For slow connections, show a brief loading state on the cursor.

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Click on empty area (no blob) | Fall back to default diameter, show info toast |
| Click between two blobs | Use closest blob within 1.5x radius threshold |
| Click on edge of image | Clamp region to image bounds, may detect partial blob |
| Detection parameters too strict | May not detect blob, falls back to default |
| Calibration not set | Checkbox disabled with tooltip explanation |
| Very large max_diameter (>50µm) | Region clamped to 200px to prevent slowdown |
| Multiple blobs in region | Use the one closest to click point |

## Testing Strategy

### Unit Tests
```python
def test_analyze_point_finds_blob():
    """Test that analyze_point detects a blob at known location."""

def test_analyze_point_no_blob():
    """Test fallback when no blob at location."""

def test_analyze_point_uses_parameters():
    """Test that detection respects passed parameters."""

def test_analyze_point_region_bounds():
    """Test proper handling of clicks near image edges."""
```

### Integration Tests
- Manual testing with reference images
- Verify toast messages show correct auto-sized vs default
- Verify checkbox state persists across page reload
- Verify disabled state when calibration not set

### User Acceptance
- Test with real SEM images
- Verify auto-sized tubercles match expected dimensions
- Gather feedback on UX (latency, accuracy, usefulness)

## Rollback Plan

Feature is entirely additive and opt-in:
- Checkbox defaults to unchecked (off)
- Removing checkbox restores original behavior
- No database/file format changes required
- Can be disabled via feature flag if issues arise

## Open Questions

1. **Should auto-position be included in Phase 1?**
   - Pro: More useful feature, click approximately and get perfect placement
   - Con: More complex, may be confusing if center shifts unexpectedly
   - **Recommendation**: Start with diameter-only, add position in Phase 2 based on feedback

2. **Should analysis use the already-preprocessed image if available?**
   - If extraction was just run, we could reuse that preprocessed image
   - Would need to cache it and track if parameters changed
   - **Recommendation**: Keep it simple for Phase 1, always preprocess fresh

3. **What if the detected diameter is vastly different from existing tubercles?**
   - Could indicate noise or artifact
   - Option: Add confidence threshold, fall back if too different
   - **Recommendation**: Trust the detection for Phase 1, let user resize if wrong

---

*Last updated: 2026-01-14*
*Author: Claude*
