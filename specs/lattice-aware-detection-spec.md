# Lattice-Aware Tubercle Detection Specification

## Overview

This specification describes a lattice-aware detection algorithm that leverages the roughly hexagonal arrangement of tubercles on ganoid fish scales. Unlike the current local-only blob detection approach, this method uses global structural patterns to improve detection accuracy.

## Problem Statement

### Current Approach Limitations
The existing LoG/DoG blob detection:
- Treats each detection independently using only local intensity
- Has no concept of expected spatial arrangement
- Produces false positives (noise, artifacts) that don't fit the pattern
- Misses true tubercles that are slightly fainter but clearly part of the lattice
- Cannot disambiguate overlapping or touching tubercles

### Human Visual Strategy
When a human examines these images, they:
1. Identify a few obvious, high-contrast tubercles
2. Notice the regular hexagonal-like spacing pattern
3. Use this pattern to predict where other tubercles should be
4. Confirm predictions by looking for intensity peaks at expected locations
5. Accept fainter features that fit the pattern, reject bright artifacts that don't

## Proposed Algorithm: Seed-and-Propagate Lattice Detection

### Algorithm Overview

```
Phase 1: Seed Detection
    - Detect high-confidence seed tubercles (strict threshold)
    - Require minimum number of seeds to proceed

Phase 2: Lattice Estimation
    - Build local neighborhood graph from seeds
    - Estimate lattice parameters (spacing, orientation, regularity)
    - Validate that seeds form a roughly regular pattern

Phase 3: Propagation
    - Use lattice model to predict missing tubercle positions
    - Search for intensity evidence at predicted locations
    - Confirm or reject predictions based on local image features
    - Iteratively expand from confirmed detections

Phase 4: Refinement
    - Re-estimate lattice parameters with all confirmed points
    - Prune outliers that don't fit the refined model
    - Fill gaps where predictions have strong image support
```

### Phase 1: Seed Detection

**Goal:** Find a set of high-confidence tubercle detections to bootstrap the lattice model.

**Method:**
1. Run existing LoG blob detection with **strict parameters**:
   - Higher threshold (e.g., 0.08-0.10 instead of 0.05)
   - Stricter circularity (e.g., 0.7 instead of 0.5)
   - Size constraints from expected diameter range

2. Additional seed quality filters:
   - Local contrast ratio: peak intensity vs. surrounding annulus
   - Isolation score: not too close to image edges or other seeds
   - Symmetry score: intensity profile roughly symmetric around center

**Output:** List of seed tubercles with high confidence scores

**Minimum Requirements:**
- At least 5-10 seeds required to estimate lattice
- If fewer seeds found, fall back to current detection method with warning

### Phase 2: Lattice Estimation

**Goal:** Estimate the local hexagonal lattice parameters from seed points.

#### 2.1 Build Neighborhood Graph

```python
def build_seed_graph(seeds, max_distance_factor=2.5):
    """
    Connect seeds that are likely neighbors.

    Args:
        seeds: List of seed tubercle positions
        max_distance_factor: Maximum edge length as multiple of median distance

    Returns:
        Graph with seeds as nodes, edges between likely neighbors
    """
    # Use Delaunay triangulation as starting point
    # Filter edges by distance (remove long edges)
    # Result: graph where edges represent true neighbor relationships
```

#### 2.2 Estimate Lattice Vectors

For a hexagonal lattice, we expect:
- Two basis vectors **v1** and **v2**
- Angle between vectors ≈ 60° (or 120°)
- |v1| ≈ |v2| (equal spacing)

```python
def estimate_lattice_vectors(seed_graph):
    """
    Estimate the two lattice basis vectors from seed arrangement.

    Method:
    1. Collect all edge vectors from the graph
    2. Cluster edge vectors by direction (expect 3 dominant directions at 0°, 60°, 120°)
    3. Select two basis vectors that span the lattice
    4. Compute mean spacing and angular deviation

    Returns:
        v1, v2: Lattice basis vectors (as complex numbers or 2D vectors)
        spacing: Mean lattice spacing in pixels
        angle: Angle between basis vectors (should be ~60°)
        regularity_score: How well the seeds fit a regular lattice (0-1)
    """
```

#### 2.3 Lattice Quality Validation

Before proceeding, validate that seeds form a reasonable lattice:

| Check | Expected Value | Tolerance |
|-------|----------------|-----------|
| Angle between v1, v2 | 60° or 120° | ± 15° |
| Spacing ratio |v1|/|v2| | 1.0 | ± 0.3 |
| Regularity score | > 0.7 | - |
| Spacing vs. expected diameter | 1.5-4x diameter | - |

If validation fails, the image may not have regular tubercle arrangement (e.g., Semionotidae with irregular patterns). Fall back to local-only detection.

### Phase 3: Propagation

**Goal:** Use the lattice model to find tubercles that local detection missed.

#### 3.1 Predict Neighbor Positions

```python
def predict_neighbors(confirmed_tubercles, lattice_vectors, image_bounds):
    """
    For each confirmed tubercle, predict where its 6 hexagonal neighbors should be.

    Args:
        confirmed_tubercles: Set of confirmed tubercle positions
        lattice_vectors: (v1, v2) basis vectors
        image_bounds: Image dimensions for boundary checking

    Returns:
        List of (predicted_position, source_tubercle, direction) tuples
        Only includes positions not already confirmed and within image bounds
    """
    predictions = []

    # Six neighbor directions in hexagonal lattice
    directions = [
        v1,
        v2,
        v1 + v2,  # or v2 - v1 depending on convention
        -v1,
        -v2,
        -(v1 + v2)
    ]

    for tubercle in confirmed_tubercles:
        for direction in directions:
            predicted_pos = tubercle.position + direction
            if is_valid_position(predicted_pos, image_bounds, confirmed_tubercles):
                predictions.append(predicted_pos)

    return deduplicate_predictions(predictions)
```

#### 3.2 Validate Predictions Against Image

```python
def validate_prediction(image, predicted_position, expected_diameter, lattice_spacing):
    """
    Check if there's image evidence for a tubercle at the predicted position.

    Args:
        image: Preprocessed grayscale image
        predicted_position: (x, y) where we expect a tubercle
        expected_diameter: Expected tubercle diameter in pixels
        lattice_spacing: Expected distance to neighbors

    Returns:
        ValidatedTubercle or None

    Method:
    1. Extract local region around predicted position
    2. Find local intensity maximum within search radius
    3. Compute quality metrics for the candidate
    4. Accept if metrics pass thresholds (can be more lenient than seed detection)
    """
    search_radius = lattice_spacing * 0.3  # Allow 30% position deviation

    # Find intensity peak in search region
    local_region = extract_region(image, predicted_position, search_radius)
    peak_offset = find_intensity_peak(local_region)
    refined_position = predicted_position + peak_offset

    # Compute quality metrics
    metrics = compute_tubercle_metrics(image, refined_position, expected_diameter)

    # Thresholds can be more lenient since we have lattice support
    if (metrics.contrast_ratio > 1.2 and      # Lower than seed threshold
        metrics.circularity > 0.4 and          # Lower than seed threshold
        metrics.size_ratio > 0.6 and           # Size within 60-140% of expected
        metrics.size_ratio < 1.4):
        return ValidatedTubercle(refined_position, metrics)

    return None
```

#### 3.3 Propagation Loop

```python
def propagate_detections(seeds, image, lattice_vectors, params):
    """
    Iteratively expand from seeds using lattice predictions.

    Uses a priority queue to process predictions in order of confidence.
    """
    confirmed = set(seeds)
    processed_positions = set()  # Avoid re-checking same locations

    # Initialize queue with predictions from seeds
    queue = PriorityQueue()  # Priority by source tubercle confidence
    for prediction in predict_neighbors(confirmed, lattice_vectors):
        queue.add(prediction, priority=prediction.source_confidence)

    while not queue.empty():
        prediction = queue.pop()

        # Skip if too close to already-processed position
        if any(distance(prediction.pos, p) < min_separation for p in processed_positions):
            continue

        processed_positions.add(prediction.pos)

        # Validate against image
        result = validate_prediction(image, prediction.pos, params)

        if result is not None:
            confirmed.add(result)

            # Add new predictions from this confirmed tubercle
            new_predictions = predict_neighbors({result}, lattice_vectors)
            for new_pred in new_predictions:
                if new_pred.pos not in processed_positions:
                    queue.add(new_pred, priority=result.confidence)

    return confirmed
```

### Phase 4: Refinement

#### 4.1 Global Lattice Re-estimation

After propagation, re-estimate lattice parameters using all confirmed points:

```python
def refine_lattice_model(confirmed_tubercles):
    """
    Re-estimate lattice parameters with full set of detections.

    May reveal that initial estimate was slightly off.
    Can also detect local lattice distortions (non-uniform spacing).
    """
    # Rebuild neighborhood graph
    # Re-estimate lattice vectors
    # Compute per-tubercle deviation from ideal lattice position
    return refined_lattice, deviation_scores
```

#### 4.2 Outlier Pruning

```python
def prune_outliers(confirmed_tubercles, refined_lattice, max_deviation=0.4):
    """
    Remove detections that don't fit the refined lattice model.

    Args:
        max_deviation: Maximum allowed deviation from lattice position
                      (as fraction of lattice spacing)

    These are likely false positives that happened to have intensity peaks.
    """
    pruned = []
    for tubercle in confirmed_tubercles:
        nearest_lattice_pos = snap_to_lattice(tubercle.pos, refined_lattice)
        deviation = distance(tubercle.pos, nearest_lattice_pos) / lattice_spacing

        if deviation <= max_deviation:
            pruned.append(tubercle)

    return pruned
```

#### 4.3 Gap Filling

```python
def fill_gaps(confirmed_tubercles, refined_lattice, image, params):
    """
    Look for missing tubercles in the interior of the detected region.

    A gap is a lattice position surrounded by confirmed neighbors
    but without a detection. May indicate:
    - A tubercle we missed (try with even more lenient thresholds)
    - A true gap in the scale surface (accept as missing)
    """
    expected_positions = generate_lattice_positions(refined_lattice, image_bounds)

    for expected_pos in expected_positions:
        if not has_nearby_detection(expected_pos, confirmed_tubercles):
            # Count how many neighbors are confirmed
            neighbor_count = count_confirmed_neighbors(expected_pos, confirmed_tubercles)

            if neighbor_count >= 4:  # Well-supported gap
                # Try very lenient detection
                result = validate_prediction(image, expected_pos, params, lenient=True)
                if result:
                    confirmed_tubercles.add(result)

    return confirmed_tubercles
```

## Implementation Details

### Data Structures

```python
@dataclass
class LatticeModel:
    """Represents the estimated hexagonal lattice."""
    v1: np.ndarray          # First basis vector (2D)
    v2: np.ndarray          # Second basis vector (2D)
    origin: np.ndarray      # Reference point for lattice
    spacing: float          # Mean spacing in pixels
    angle: float            # Angle between v1 and v2 (radians)
    regularity: float       # Quality score 0-1

    def predict_position(self, i: int, j: int) -> np.ndarray:
        """Get lattice position at indices (i, j)."""
        return self.origin + i * self.v1 + j * self.v2

    def nearest_lattice_point(self, position: np.ndarray) -> Tuple[int, int, np.ndarray]:
        """Find nearest lattice point to a position."""
        # Solve for fractional indices, round to nearest integer
        pass


@dataclass
class PropagationParams:
    """Parameters controlling the propagation algorithm."""
    # Seed detection
    seed_threshold: float = 0.08
    seed_circularity: float = 0.7
    min_seeds: int = 5

    # Lattice validation
    min_regularity: float = 0.7
    angle_tolerance: float = 15.0  # degrees

    # Propagation
    search_radius_factor: float = 0.3  # Fraction of lattice spacing
    propagation_contrast_threshold: float = 1.2
    propagation_circularity: float = 0.4

    # Refinement
    max_lattice_deviation: float = 0.4  # Fraction of spacing
    gap_fill_min_neighbors: int = 4
```

### Integration with Existing Code

The lattice-aware detection should be integrated as a new detection method:

```python
# In detection.py

def detect_tubercles(
    image: np.ndarray,
    calibration: CalibrationData,
    method: str = "log",  # Add "lattice" as new option
    ...
) -> List[Tubercle]:

    if method == "lattice":
        return detect_tubercles_lattice(
            image, calibration,
            min_diameter_um=min_diameter_um,
            max_diameter_um=max_diameter_um,
            ...
        )
    elif method == "log":
        # Existing implementation
        ...
```

CLI integration:

```bash
# Use lattice-aware detection
fish-scale-measure process image.tif --method lattice

# With custom parameters
fish-scale-measure process image.tif --method lattice --seed-threshold 0.08 --min-seeds 10
```

### Handling Edge Cases

#### 1. Irregular Arrangements (Semionotidae)
Lepidotes and other Semionotidae have **irregular** tubercle arrangements. The lattice model will fail validation (low regularity score).

**Fallback:** Return to local-only detection with a warning:
```
WARNING: Low lattice regularity (0.45). Image may have irregular tubercle arrangement.
         Falling back to local blob detection.
```

#### 2. Insufficient Seeds
If strict seed detection finds fewer than `min_seeds` tubercles:

**Fallback:** Progressively relax seed thresholds, or fall back to local detection.

#### 3. Multiple Lattice Domains
Some images may have regions with different lattice orientations (e.g., near scale edges).

**Approach:**
- Detect lattice orientation locally (sliding window)
- Allow lattice parameters to vary smoothly across the image
- More complex: segment image into domains first

#### 4. Partial/Cropped Images
When tubercle field is cropped, propagation naturally stops at image boundaries.

**Consideration:** Don't penalize edge tubercles for missing neighbors.

#### 5. Image Artifacts
Scale bars, text labels, debris may create false intensity peaks.

**Mitigation:**
- Pre-mask known artifact regions (scale bar detection)
- Lattice consistency will reject isolated false positives
- Size filtering removes very large/small detections

## Validation Plan

### Unit Tests

1. **Synthetic lattice tests:**
   - Generate perfect hexagonal lattice with known positions
   - Add Gaussian noise to positions
   - Verify detection recovers >95% of points

2. **Lattice estimation tests:**
   - Known lattice vectors → verify estimation accuracy
   - Test with varying regularity levels

3. **Propagation tests:**
   - Sparse seeds → verify expansion to full lattice
   - Test termination conditions

### Integration Tests

Compare lattice method vs. current LoG method on test images:

| Image | LoG Detections | Lattice Detections | Expected | Notes |
|-------|----------------|--------------------| ---------|-------|
| P1_Fig3_Lepisosteus_osseus | ? | ? | ~50-80 | Regular pattern |
| P1_Fig2_Polypterus_bichir | ? | ? | ~30-50 | Small tubercles, wide spacing |
| P1_Fig1_Lepidotes_elvensis | ? | ? | ~40-60 | Irregular - expect fallback |

### Accuracy Metrics

For each test image with known expected values:
1. Mean diameter error (target: < 0.5 µm)
2. Mean spacing error (target: < 0.7 µm)
3. Detection count vs. manual count
4. False positive rate (detections not on tubercles)
5. False negative rate (missed tubercles)

## Performance Considerations

### Computational Complexity

| Phase | Complexity | Notes |
|-------|------------|-------|
| Seed detection | O(N) | Same as current LoG |
| Lattice estimation | O(S²) | S = number of seeds |
| Propagation | O(T × k) | T = final tubercle count, k = neighbors checked |
| Refinement | O(T²) | Neighborhood graph construction |

Total: O(N + T²) where N = image pixels, T = tubercle count

For typical images (1000×1000 pixels, ~100 tubercles), this should be <1 second.

### Memory Usage

- Seed storage: O(S)
- Propagation queue: O(T)
- Neighborhood graph: O(T²) edges worst case, O(T) typical

No significant memory concerns for expected image sizes.

## Future Enhancements

1. **Adaptive local lattice:** Allow lattice parameters to vary smoothly across image
2. **Multi-scale detection:** Handle images with varying magnification
3. **Confidence scoring:** Provide per-tubercle confidence based on both local and lattice evidence
4. **Interactive refinement:** Allow user to add/remove seeds and re-propagate
5. **Learning-based:** Train a model to recognize tubercle patterns directly

## References

- Hexagonal lattice detection in materials science: similar problems in crystallography
- RANSAC for model fitting with outliers
- Graph-based image segmentation
- Gayet & Meunier methodology papers (see main README)
