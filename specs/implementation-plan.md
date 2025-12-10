# Fish Scale Metrics Extraction: Implementation Plan

## Overview

This document describes the implementation plan for a Python CLI program that extracts tubercle diameter and intertubercular space measurements from SEM images of ganoid fish scales.

---

## Project Structure

```
fish_scales/
├── src/
│   └── fish_scale_analysis/
│       ├── __init__.py
│       ├── cli.py                 # Command-line interface (rich-argparse)
│       ├── core/
│       │   ├── __init__.py
│       │   ├── calibration.py     # Scale bar detection and µm/pixel calculation
│       │   ├── preprocessing.py   # Image enhancement (CLAHE, blur, etc.)
│       │   ├── detection.py       # Tubercle detection (blob detection)
│       │   └── measurement.py     # Diameter and spacing calculation
│       ├── output/
│       │   ├── __init__.py
│       │   ├── csv_writer.py      # CSV output for metrics
│       │   ├── visualization.py   # Matplotlib figure generation
│       │   └── logger.py          # Timestamped text logging
│       └── models.py              # Data classes for Tubercle, MeasurementResult, etc.
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # Pytest fixtures
│   ├── test_calibration.py
│   ├── test_preprocessing.py
│   ├── test_detection.py
│   ├── test_measurement.py
│   └── test_integration.py        # End-to-end tests against test_images/
├── test_images/                   # (existing) Test cases with known expected values
├── images/                        # (existing) Real images for analysis
├── output/                        # Generated output (gitignored)
├── pyproject.toml                 # Project config with uv
├── README.md                      # Usage documentation
└── .gitignore
```

---

## Module Design

### 1. `models.py` - Data Structures

Define dataclasses for clean data passing between modules:

```python
@dataclass
class Tubercle:
    centroid: Tuple[float, float]  # (x, y) in pixels
    diameter_px: float
    diameter_um: float
    area_px: float
    circularity: float

@dataclass
class MeasurementResult:
    image_path: str
    calibration_um_per_px: float
    n_tubercles: int
    tubercle_diameters: List[float]  # Individual measurements in µm
    intertubercular_spaces: List[float]  # Individual measurements in µm
    mean_diameter: float
    std_diameter: float
    mean_space: float
    std_space: float
    suggested_genus: Optional[str]

@dataclass
class CalibrationData:
    um_per_pixel: float
    scale_bar_length_um: float
    scale_bar_length_px: float
    method: str  # "manual" or "automatic"
```

### 2. `core/calibration.py` - Scale Calibration

**Purpose:** Extract µm/pixel ratio from scale bar or manual input.

**Functions:**
- `calibrate_from_manual_input(scale_bar_um: float, scale_bar_px: float) -> CalibrationData`
- `calibrate_from_image(image: np.ndarray) -> CalibrationData` (future: OCR-based)
- `estimate_calibration_700x() -> CalibrationData` - Default for 700× SEM images

**Implementation Notes:**
- For initial version, use manual calibration with sensible defaults for 700× magnification
- All test images use 700× magnification with 10 µm scale bars
- Store typical pixel dimensions for 700× images to estimate if not provided

### 3. `core/preprocessing.py` - Image Enhancement

**Purpose:** Prepare SEM images for reliable tubercle detection.

**Functions:**
- `load_image(path: Path) -> np.ndarray` - Load TIFF using tifffile/PIL
- `to_grayscale(image: np.ndarray) -> np.ndarray`
- `apply_clahe(image: np.ndarray, clip_limit=2.0, tile_size=8) -> np.ndarray`
- `apply_gaussian_blur(image: np.ndarray, sigma=1.0) -> np.ndarray`
- `apply_morphological_opening(image: np.ndarray, kernel_size=3) -> np.ndarray`
- `preprocess_pipeline(image: np.ndarray) -> np.ndarray` - Combined preprocessing

**Implementation Notes:**
- Use `scikit-image` for CLAHE (`skimage.exposure.equalize_adapthist`)
- Use `scipy.ndimage` or `cv2` for Gaussian blur
- Morphological operations via `skimage.morphology`
- Return intermediate images for visualization/debugging

### 4. `core/detection.py` - Tubercle Detection

**Purpose:** Identify individual tubercles and their boundaries.

**Functions:**
- `detect_blobs_log(image: np.ndarray, min_sigma, max_sigma, threshold) -> List[Tuple]`
- `detect_blobs_dog(image: np.ndarray, ...) -> List[Tuple]` - Alternative method
- `filter_by_circularity(blobs, image, min_circularity=0.7) -> List[Tubercle]`
- `detect_tubercles(image: np.ndarray, um_per_pixel: float, params: dict) -> List[Tubercle]`

**Implementation Notes:**
- Primary method: Laplacian of Gaussian (LoG) blob detection via `skimage.feature.blob_log`
- Expected tubercle size: 2-10 µm → calculate sigma range from calibration
- Filter detected blobs by:
  - Size (within expected µm range)
  - Circularity (> 0.7 for round tubercles)
  - Edge exclusion (ignore partial tubercles at image borders)
- Return list of `Tubercle` objects with pixel and µm measurements

### 5. `core/measurement.py` - Metric Calculation

**Purpose:** Calculate tubercle diameters and intertubercular spacing.

**Functions:**
- `measure_diameters(tubercles: List[Tubercle]) -> Dict` - Statistics on diameters
- `build_neighbor_graph(tubercles: List[Tubercle]) -> scipy.spatial.Delaunay`
- `measure_intertubercular_spaces(tubercles: List[Tubercle], triangulation) -> Dict`
- `classify_genus(mean_diameter: float, mean_space: float) -> str`
- `process_image(image_path: Path, calibration: CalibrationData) -> MeasurementResult`

**Implementation Notes:**
- Use Delaunay triangulation (`scipy.spatial.Delaunay`) to identify natural neighbors
- Intertubercular space = center-to-center distance minus both radii (edge-to-edge)
- Filter out edges where spacing is negative (overlapping detections)
- Genus classification based on reference ranges from papers:

| Genus | Diameter (µm) | Space (µm) |
|-------|---------------|------------|
| *Lepisosteus* | 3.79 - 5.61 | 3.14 - 4.75 |
| *Atractosteus* | 5.68 - 9.07 | 1.89 - 2.82 |
| *Polypterus* | 2.19 - 3.03 | 5.57 - 8.54 |
| *Obaichthys* | 4.73 - 5.27 | 4.55 - 4.79 |
| *Paralepidosteus* | 5.73 - 5.94 | 6.00 - 6.25 |

### 6. `output/visualization.py` - Figure Generation

**Purpose:** Create the two-panel visualization showing detection results.

**Functions:**
- `create_detection_overlay(image: np.ndarray, tubercles: List[Tubercle]) -> Figure`
- `create_geometry_diagram(tubercles: List[Tubercle], triangulation) -> Figure`
- `create_combined_figure(image, tubercles, triangulation, output_path) -> None`
- `create_scatter_plot(results: List[MeasurementResult], output_path) -> None`

**Output Format (matching specs/extraction_methodology.png):**
```
┌─────────────────────────────────────────────────────────┐
│  (a) Detection Overlay       │  (b) Geometry Diagram   │
│  ┌─────────────────────────┐ │ ┌─────────────────────┐ │
│  │  Original SEM image     │ │ │  Schematic view     │ │
│  │  with detected tubercles│ │ │  - Circles for      │ │
│  │  circled in color       │ │ │    tubercles        │ │
│  │                         │ │ │  - Lines showing    │ │
│  │                         │ │ │    Delaunay edges   │ │
│  │                         │ │ │  - Distance labels  │ │
│  └─────────────────────────┘ │ └─────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Implementation Notes:**
- Use `matplotlib` with two subplots side-by-side
- Panel (a): Original image with detected tubercles outlined as circles
- Panel (b): White background with:
  - Circles representing tubercles (sized proportionally)
  - Delaunay triangulation edges as lines
  - Optional: distance annotations on edges
- Save as PNG at high DPI (300)

### 7. `output/csv_writer.py` - CSV Output

**Purpose:** Write per-tubercle and summary data to CSV files.

**Functions:**
- `write_tubercle_details(tubercles: List[Tubercle], output_path: Path) -> None`
- `write_summary(result: MeasurementResult, output_path: Path) -> None`
- `append_to_batch_csv(result: MeasurementResult, output_path: Path) -> None`

**CSV Format (per-tubercle):**
```csv
tubercle_id,centroid_x,centroid_y,diameter_px,diameter_um,circularity
1,145.3,203.7,12.4,4.52,0.89
2,178.9,198.2,11.8,4.30,0.92
...
```

**CSV Format (summary):**
```csv
image,n_tubercles,mean_diameter_um,std_diameter_um,mean_space_um,std_space_um,suggested_genus
P1_Fig3_Lepisosteus.tif,127,3.79,0.38,3.14,0.71,Lepisosteus
```

### 8. `output/logger.py` - Text Logging

**Purpose:** Create timestamped logs of all processing steps.

**Functions:**
- `setup_logger(output_dir: Path) -> logging.Logger`
- `log_phase(logger, phase_name: str, details: dict) -> None`

**Log Format:**
```
[2024-01-15 14:32:17] === Processing: P1_Fig3_Lepisosteus_osseus.tif ===
[2024-01-15 14:32:17] CALIBRATION: 0.365 µm/pixel (manual, 10µm bar = 27.4px)
[2024-01-15 14:32:18] PREPROCESSING: CLAHE applied (clip=2.0, tiles=8x8)
[2024-01-15 14:32:18] DETECTION: Found 127 tubercles (min_sigma=2.7, max_sigma=13.7)
[2024-01-15 14:32:19] MEASUREMENT: Diameter = 3.79 ± 0.38 µm
[2024-01-15 14:32:19] MEASUREMENT: Spacing = 3.14 ± 0.71 µm
[2024-01-15 14:32:19] CLASSIFICATION: Suggested genus = Lepisosteus
[2024-01-15 14:32:19] OUTPUT: Saved to output/20240115_143217/
```

### 9. `cli.py` - Command Line Interface

**Purpose:** Entry point with rich-argparse for argument parsing.

**Commands:**

```bash
# Process single image
fish-scale-measure process <image.tif> [options]

# Process batch of images
fish-scale-measure batch <directory> [options]

# Run validation against test images
fish-scale-measure validate
```

**Arguments:**
```
positional arguments:
  image                 Path to TIFF image file

options:
  -h, --help            Show help message
  -o, --output DIR      Output directory (default: ./output)
  --scale-bar-um FLOAT  Scale bar length in µm (default: 10.0)
  --scale-bar-px FLOAT  Scale bar length in pixels (required for manual calibration)
  --auto-calibrate      Attempt automatic scale bar detection (experimental)
  --min-diameter FLOAT  Minimum expected tubercle diameter in µm (default: 2.0)
  --max-diameter FLOAT  Maximum expected tubercle diameter in µm (default: 10.0)
  --threshold FLOAT     Blob detection threshold (default: 0.1)
  --circularity FLOAT   Minimum circularity filter (default: 0.7)
  -v, --verbose         Verbose output
  --no-viz              Skip visualization generation
```

**Output Structure:**
```
output/
└── 20240115_143217/              # Timestamped directory
    ├── log.txt                   # Processing log
    ├── summary.csv               # Summary results
    ├── tubercle_details.csv      # Per-tubercle measurements
    ├── P1_Fig3_detection.png     # Two-panel visualization
    └── P1_Fig3_geometry.png      # Optional separate geometry diagram
```

---

## Dependencies

```toml
[project]
name = "fish-scale-analysis"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "numpy>=1.24.0",
    "scipy>=1.10.0",
    "scikit-image>=0.21.0",
    "tifffile>=2023.7.0",
    "pillow>=10.0.0",
    "matplotlib>=3.7.0",
    "rich>=13.0.0",
    "rich-argparse>=1.4.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
]

[project.scripts]
fish-scale-measure = "fish_scale_analysis.cli:main"
```

---

## Testing Strategy

### Unit Tests

1. **test_calibration.py**
   - Test manual calibration calculation
   - Test default 700× estimation

2. **test_preprocessing.py**
   - Test grayscale conversion
   - Test CLAHE enhancement
   - Test blur application

3. **test_detection.py**
   - Test blob detection on synthetic images with known blob count
   - Test circularity filtering
   - Test size filtering

4. **test_measurement.py**
   - Test Delaunay triangulation construction
   - Test edge-to-edge distance calculation
   - Test genus classification logic

### Integration Tests

**test_integration.py** - End-to-end tests using test_images/:

```python
@pytest.mark.parametrize("test_case", [
    ("P1_Fig3_Lepisosteus_osseus_3.79um.tif", 3.79, 3.14, 0.5, 0.7),
    ("P1_Fig4_Atractosteus_simplex_7.07um.tif", 7.07, 2.61, 0.5, 0.7),
    ("P1_Fig2_Polypterus_bichir_2.63um.tif", 2.63, 6.19, 0.5, 0.7),
    # ... all 10 test cases
])
def test_measurement_accuracy(test_case):
    filename, expected_diam, expected_space, diam_tol, space_tol = test_case
    result = process_image(TEST_IMAGES_DIR / filename, calibration)
    assert abs(result.mean_diameter - expected_diam) <= diam_tol
    assert abs(result.mean_space - expected_space) <= space_tol
```

### Acceptance Criteria (from test_cases.md)

| Metric | Acceptable Error |
|--------|------------------|
| Tubercle Diameter | ± 0.5 µm |
| Intertubercular Space | ± 0.7 µm |
| Genus Classification | Correct assignment |

---

## Implementation Phases

### Phase 1: Core Infrastructure
1. Set up project structure with pyproject.toml
2. Implement `models.py` data classes
3. Implement `calibration.py` (manual calibration only)
4. Implement `preprocessing.py` pipeline
5. Basic CLI skeleton with rich-argparse

### Phase 2: Detection & Measurement
1. Implement `detection.py` with LoG blob detection
2. Implement `measurement.py` with Delaunay triangulation
3. Implement genus classification logic

### Phase 3: Output Generation
1. Implement `csv_writer.py`
2. Implement `logger.py`
3. Implement `visualization.py` two-panel figure

### Phase 4: Testing & Validation
1. Create pytest fixtures with test images
2. Write unit tests for each module
3. Write integration tests against all 10 test cases
4. Tune detection parameters to meet acceptance criteria

### Phase 5: Documentation & Polish
1. Write README.md with usage instructions
2. Add --help documentation for all CLI options
3. Add example outputs to documentation

---

## Visualization Specification

The two-panel figure (matching `specs/extraction_methodology.png`) should:

### Panel A: Detection Overlay
- Background: Original SEM image (grayscale)
- Overlay: Detected tubercles circled with colored outlines
- Circle color: Green for valid detections
- Circle thickness: 2px
- Optional: Red circles for filtered-out detections

### Panel B: Geometry Diagram
- Background: White
- Tubercles: Hollow circles at detected positions
- Circle size: Proportional to measured diameter
- Delaunay edges: Thin gray lines connecting neighbors
- Labels: Tubercle IDs inside circles
- Optional: Edge distance labels (µm values)

### Figure Properties
- Size: 12" × 6" (landscape)
- DPI: 300
- Format: PNG
- Subplot titles: "(a) Detected Tubercles" and "(b) Neighbor Geometry"

---

## Edge Cases & Error Handling

1. **No scale bar provided**: Warn user, use default 700× estimation with disclaimer
2. **Few tubercles detected (<10)**: Warn that results may be unreliable
3. **No tubercles detected**: Error with suggestions (adjust threshold, check image quality)
4. **Overlapping detections**: Filter by non-maximum suppression
5. **Partial tubercles at edges**: Exclude based on distance from image border
6. **Very dark/bright images**: CLAHE should handle, but warn if histogram is extreme
7. **Non-TIFF format**: Attempt to load with PIL, warn if not TIFF
8. **Corrupt image file**: Graceful error with clear message

---

## Future Enhancements (Out of Scope)

These are noted for future consideration but NOT part of current implementation:

1. **Automatic scale bar detection** - OCR to read scale bar value from image
2. **Flask web UI** - As specified in ui-fish-scale-measure-spec.md
3. **Batch comparison plots** - Scatter plot comparing multiple samples
4. **Reference database** - Store known species measurements for automatic classification
5. **GPU acceleration** - For processing large batches

---

## Summary

This implementation plan describes a modular Python CLI tool for extracting tubercle metrics from fish scale SEM images. The design prioritizes:

1. **Modularity** - Separate modules for each processing phase, enabling reuse in pytest, CLI, and future Flask UI
2. **Testability** - Clear acceptance criteria with 10 validated test cases
3. **User Experience** - Rich terminal output, clear logging, visual results
4. **Scientific Accuracy** - Implementation based on established methodology from Gayet & Meunier papers

The implementation follows the processing pipeline from `docs/fish-scale-metrics-extraction.md` and produces output matching the visualization style in `specs/extraction_methodology.png`.
