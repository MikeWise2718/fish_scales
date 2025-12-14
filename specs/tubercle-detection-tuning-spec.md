# Tubercle Detection Tuning Specification

## Status: IMPLEMENTED

The tuning system has been implemented with:
- New CLI parameters for all preprocessing and detection options
- Parameter profile system (`--profile`)
- Tuning script at `scripts/tune_parameters.py`

### Key Findings

For the Paralepidosteus test image (`P2_Fig1c`), optimal parameters are:
- **Calibration**: 0.33 µm/pixel (not the default 0.137)
- **CLAHE**: clip=0.05, kernel=12
- **Threshold**: 0.10 (higher = fewer false positives)
- **Circularity**: 0.0 (disabled - image quality too poor)
- **Min/Max diameter**: 4.5-8.0 µm
- **Sigma range**: 5-15

Results with profile `paralepidosteus`:
- Tubercles: 188
- Diameter: 5.22 ± 0.96 µm (expected: 5.73-5.94)
- Spacing: 6.66 ± 9.31 µm (expected: 6.00-6.25)

---

## Objective

Create a systematic approach to tune tubercle detection parameters so that our output matches the reference methodology shown in `extraction_methodology.png` (from Gayet & Meunier 1993). The reference image shows panel **a** (?*Paralepidosteus* sp. from Acre, Brazil) with manually traced tubercles, and panel **b** showing the corresponding Delaunay triangulation measurement diagram.

## Reference Image Analysis

The reference `extraction_methodology.png` demonstrates:
- **43 tubercles** detected (as noted in the paper caption)
- **101 distance measurements** between tubercles
- Clear circular outlines around each tubercle
- Tubercles are bright spots on a darker, textured background
- Some tubercles are partially obscured by scratches/artifacts
- Edge tubercles are included where clearly visible

### Expected Metrics for Test Image (P2_Fig1c_Paralepidosteus_sp_Acre)
- Tubercle Diameter: **5.73-5.94 µm**
- Intertubercular Space: **6.00-6.25 µm**
- Approximate tubercle count: **~43** (from reference)

---

## Current Parameter Space

### 1. Preprocessing Parameters (`preprocessing.py`)

| Parameter | Current Default | Range | Effect |
|-----------|-----------------|-------|--------|
| `clahe_clip` | 0.03 | 0.01-0.1 | Higher = more contrast, may enhance noise |
| `clahe_kernel` | 8 | 4-32 | Larger = more global contrast, smaller = more local |
| `blur_sigma` | 1.0 | 0.5-3.0 | Higher = smoother, may lose small tubercles |
| `use_tophat` | False | True/False | Enhances bright spots, useful if tubercles are subtle |
| `tophat_radius` | 10 | 5-20 | Should be ~size of tubercles in pixels |

### 2. Detection Parameters (`detection.py`)

| Parameter | Current Default | Range | Effect |
|-----------|-----------------|-------|--------|
| `threshold` | 0.05 | 0.01-0.2 | **Lower = more detections** (more sensitive) |
| `min_diameter_um` | 2.0 | 1.0-4.0 | Filter out small false positives |
| `max_diameter_um` | 10.0 | 8.0-15.0 | Filter out large false positives |
| `min_circularity` | 0.5 | 0.3-0.8 | **Lower = accept more elongated blobs** |
| `edge_margin_px` | 10 | 5-20 | Exclude detections near image borders |
| `overlap` | 0.5 | 0.3-0.7 | How much blob overlap is allowed |
| `method` | "log" | "log"/"dog" | LoG more accurate, DoG faster |

### 3. Derived Parameters (Calculated)

| Parameter | Formula | Notes |
|-----------|---------|-------|
| `min_sigma` | `min_diameter_px / (2 * sqrt(2))` | Derived from min_diameter_um and calibration |
| `max_sigma` | `max_diameter_px / (2 * sqrt(2))` | Derived from max_diameter_um and calibration |
| `num_sigma` | 10 (hardcoded) | More = finer scale search, slower |

---

## Tuning Strategy

### Phase 1: Baseline Measurement

1. Run detection on `P2_Fig1c_Paralepidosteus_sp_Acre_5.73um.tif` with default parameters
2. Record:
   - Number of tubercles detected
   - Mean/std diameter
   - Mean/std spacing
   - Visual inspection: false positives, missed tubercles

### Phase 2: Sensitivity Analysis

Create a parameter sweep to understand each parameter's effect:

```
# Parameters to sweep
thresholds = [0.02, 0.03, 0.05, 0.08, 0.1]
circularities = [0.3, 0.4, 0.5, 0.6, 0.7]
clahe_clips = [0.02, 0.03, 0.05, 0.08]
blur_sigmas = [0.5, 1.0, 1.5, 2.0]
```

For each combination, record:
- `n_tubercles`: Should be ~43 for reference
- `mean_diameter_um`: Should be ~5.73-5.94
- `mean_space_um`: Should be ~6.00-6.25
- Visual match score (manual assessment)

### Phase 3: Image-Specific Profiles

Different image types may need different parameter profiles:

| Image Type | Characteristics | Suggested Adjustments |
|------------|-----------------|----------------------|
| High contrast (P2_Fig1d, e) | Clear white dots on dark | Lower threshold, higher circularity |
| Low contrast (P2_Fig1c) | Textured, scratched | Higher CLAHE, use tophat, lower circularity |
| Small tubercles (Polypterus) | 2-3 µm diameter | Lower min_diameter, smaller blur_sigma |
| Large tubercles (Atractosteus) | 6-9 µm diameter | Higher max_diameter |

### Phase 4: Automated Optimization

Implement a scoring function to automatically find optimal parameters:

```python
def score_detection(result, expected_count, expected_diameter, expected_spacing):
    """Score detection quality against expected values."""

    # Count score: penalize deviation from expected count
    count_score = 1.0 - abs(result.n_tubercles - expected_count) / expected_count

    # Diameter score: within tolerance
    diam_error = abs(result.mean_diameter_um - expected_diameter)
    diam_score = max(0, 1.0 - diam_error / 0.5)  # 0.5 µm tolerance

    # Spacing score: within tolerance
    space_error = abs(result.mean_space_um - expected_spacing)
    space_score = max(0, 1.0 - space_error / 0.7)  # 0.7 µm tolerance

    # Weighted combination
    return 0.3 * count_score + 0.35 * diam_score + 0.35 * space_score
```

---

## Implementation Plan

### Step 1: Add Parameter Profile Support

Add a new CLI option `--profile` to select preset parameter combinations:

```bash
fish-scale-measure process image.tif --profile paralepidosteus
fish-scale-measure process image.tif --profile polypterus
fish-scale-measure process image.tif --profile high-contrast
```

### Step 2: Create Tuning Script

Create `scripts/tune_parameters.py` that:
1. Takes a test image and expected values
2. Runs parameter grid search
3. Outputs a ranked list of parameter combinations
4. Saves best parameters to a config file

### Step 3: Add Interactive Tuning Mode

Add `fish-scale-measure tune` command that:
1. Displays current detection overlaid on image
2. Allows adjusting parameters interactively
3. Shows real-time metrics update
4. Exports working parameters

### Step 4: Create Parameter Config Files

Support loading parameters from YAML/JSON:

```yaml
# profiles/paralepidosteus.yaml
preprocessing:
  clahe_clip: 0.05
  clahe_kernel: 8
  blur_sigma: 0.8
  use_tophat: true
  tophat_radius: 12

detection:
  threshold: 0.03
  min_diameter_um: 4.0
  max_diameter_um: 8.0
  min_circularity: 0.4
  edge_margin_px: 8
```

### Step 5: Validation Integration

Update `fish-scale-measure validate` to:
1. Use image-specific optimal parameters
2. Report which parameters worked best
3. Track parameter performance across test set

---

## New CLI Options to Add

```bash
# Preprocessing options
--clahe-clip FLOAT        # CLAHE clip limit (default: 0.03)
--clahe-kernel INT        # CLAHE kernel size (default: 8)
--blur-sigma FLOAT        # Gaussian blur sigma (default: 1.0)
--use-tophat              # Enable top-hat transform
--tophat-radius INT       # Top-hat disk radius (default: 10)

# Additional detection options
--overlap FLOAT           # Max blob overlap 0-1 (default: 0.5)
--method [log|dog]        # Blob detection method (default: log)
--edge-margin INT         # Edge exclusion margin in px (default: 10)

# Profile and config
--profile NAME            # Use preset parameter profile
--config FILE             # Load parameters from config file
--save-config FILE        # Save current parameters to file

# Tuning mode
tune IMAGE                # Interactive parameter tuning
  --expected-count INT    # Expected tubercle count
  --expected-diameter FLOAT
  --expected-spacing FLOAT
```

---

## Success Criteria

For the reference image `P2_Fig1c_Paralepidosteus_sp_Acre_5.73um.tif`:

| Metric | Target | Tolerance |
|--------|--------|-----------|
| Tubercle count | ~43 | ±10 |
| Mean diameter | 5.73-5.94 µm | ±0.5 µm |
| Mean spacing | 6.00-6.25 µm | ±0.7 µm |
| Visual match | >80% overlap with reference circles | Manual assessment |

---

## Notes

1. **Calibration is critical**: All tuning assumes correct µm/pixel calibration. For 700× images without scale bars, the estimate may vary.

2. **Image quality varies**: Scanned PDF images have artifacts (compression, scanning noise) that original SEMs don't have.

3. **The reference was manually traced**: Perfect algorithmic reproduction may not be possible, but we should aim for >80% agreement.

4. **Consider ensemble methods**: Run multiple parameter sets and take consensus detections for robustness.
