# Fish Scale Metrics Extraction

A Python CLI tool for extracting tubercle diameter and intertubercular space measurements from SEM (Scanning Electron Microscope) images of ganoid fish scales.

## Purpose

This tool measures two key taxonomic metrics from fish scale images:

1. **Tubercle Diameter (µm)** - The diameter of microscopic tubercles on the ganoine surface
2. **Intertubercular Space (µm)** - The edge-to-edge distance between adjacent tubercles

These measurements can differentiate between fish families, genera, and sometimes species within Lepisosteidae, Polypteridae, and Semionotidae, as established by Gayet & Meunier (1986, 1993) and Brito et al. (2000).

## Reference Ranges

| Genus | Tubercle Diameter (µm) | Intertubercular Space (µm) |
|-------|------------------------|----------------------------|
| *Lepisosteus* | 3.79 - 5.61 | 3.14 - 4.75 |
| *Atractosteus* | 5.68 - 9.07 | 1.89 - 2.82 |
| *Polypterus* | 2.19 - 3.03 | 5.57 - 8.54 |
| *Obaichthys* | 4.73 - 5.27 | 4.55 - 4.79 |
| *Paralepidosteus* | 5.73 - 5.94 | 6.00 - 6.25 |

## Installation

### Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) package manager (recommended)

### Setup

```bash
# Clone the repository
cd fish_scales

# Create virtual environment and install dependencies with uv
uv venv
uv pip install -e ".[dev]"

# Or with pip
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Usage

### Process a Single Image

```bash
fish-scale-measure process path/to/image.tif

# With manual calibration (recommended for accuracy)
fish-scale-measure process image.tif --scale-bar-um 10 --scale-bar-px 73

# Adjust detection parameters
fish-scale-measure process image.tif --threshold 0.03 --min-diameter 2.5 --max-diameter 8.0
```

### Process Multiple Images

```bash
fish-scale-measure batch path/to/images/

# Generate a scatter plot comparing all samples
fish-scale-measure batch images/ --scatter

# Skip visualization generation for faster processing
fish-scale-measure batch images/ --no-viz
```

### Run Validation Tests

```bash
# Validate against test images with known expected values
fish-scale-measure validate

# Specify custom test directory
fish-scale-measure validate --test-dir path/to/test_images
```

## Command Line Options

### `process` command

| Option | Description | Default |
|--------|-------------|---------|
| `image` | Path to TIFF image file | (required) |
| `-o, --output` | Output directory | `./output` |
| `--scale-bar-um` | Scale bar length in µm | auto-estimate |
| `--scale-bar-px` | Scale bar length in pixels | auto-estimate |
| `--min-diameter` | Minimum tubercle diameter (µm) | 2.0 |
| `--max-diameter` | Maximum tubercle diameter (µm) | 10.0 |
| `--threshold` | Detection threshold (lower = more sensitive) | 0.05 |
| `--circularity` | Minimum circularity filter (0-1) | 0.5 |
| `-v, --verbose` | Verbose output | off |
| `--no-viz` | Skip visualization generation | off |
| `--show-preprocessing` | Generate preprocessing steps figure | off |

### `batch` command

Same options as `process`, plus:

| Option | Description | Default |
|--------|-------------|---------|
| `directory` | Directory containing TIFF images | (required) |
| `--scatter` | Generate scatter plot of all results | off |

## Output

Each run creates a timestamped output directory with:

```
output/
└── 20240115_143217/
    ├── processing_log.txt       # Detailed processing log
    ├── image_name_summary.csv   # Summary statistics
    ├── image_name_tubercles.csv # Per-tubercle measurements
    ├── image_name_edges.csv     # Neighbor edge measurements
    └── image_name_detection.png # Two-panel visualization
```

### Visualization

The tool generates a two-panel figure:
- **Panel A**: Original image with detected tubercles circled
- **Panel B**: Geometry diagram showing tubercle positions and Delaunay neighbor connections

### CSV Output

**Summary CSV:**
```csv
image,n_tubercles,calibration_um_per_px,mean_diameter_um,std_diameter_um,mean_space_um,std_space_um,suggested_genus,confidence
image.tif,127,0.137,3.79,0.38,3.14,0.71,Lepisosteus,high
```

**Tubercle Details CSV:**
```csv
tubercle_id,centroid_x,centroid_y,diameter_px,diameter_um,area_px,circularity
1,145.3,203.7,27.6,3.79,598.2,0.89
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=fish_scale_analysis

# Run specific test file
pytest tests/test_detection.py

# Run integration tests only
pytest tests/test_integration.py -v
```

## Test Images

The `test_images/` directory contains 10 reference images extracted from the original research papers with known expected values. These are used for validation:

| Image | Expected Diameter (µm) | Expected Spacing (µm) |
|-------|------------------------|------------------------|
| P1_Fig3_Lepisosteus_osseus | 3.79 | 3.14 |
| P1_Fig4_Atractosteus_simplex | 7.07 | 2.61 |
| P1_Fig2_Polypterus_bichir | 2.63 | 6.19 |
| ... | ... | ... |

See `test_images/test_cases.md` for the complete list.

## Acceptance Criteria

| Metric | Acceptable Error |
|--------|------------------|
| Tubercle Diameter | ± 0.5 µm |
| Intertubercular Space | ± 0.7 µm |
| Genus Classification | Correct assignment |

## Algorithm Overview

1. **Calibration**: Convert pixels to micrometers using scale bar or 700× magnification estimate
2. **Preprocessing**: CLAHE enhancement, Gaussian blur for noise reduction
3. **Detection**: Laplacian of Gaussian (LoG) blob detection with circularity filtering
4. **Measurement**: Delaunay triangulation for neighbor identification, edge-to-edge spacing calculation
5. **Classification**: Compare metrics against reference ranges for genus suggestion

## Project Structure

```
fish_scales/
├── src/fish_scale_analysis/
│   ├── cli.py                  # Command-line interface
│   ├── models.py               # Data classes
│   ├── core/
│   │   ├── calibration.py      # Scale calibration
│   │   ├── preprocessing.py    # Image enhancement
│   │   ├── detection.py        # Tubercle detection
│   │   └── measurement.py      # Metrics calculation
│   └── output/
│       ├── csv_writer.py       # CSV output
│       ├── logger.py           # Logging utilities
│       └── visualization.py    # Figure generation
├── tests/                      # Pytest test suite
├── test_images/                # Reference images
├── images/                     # User images for analysis
└── output/                     # Generated output
```

## References

- Gayet, M. & Meunier, F.J. (1986). Apport de l'étude de l'ornementation microscopique de la ganoïne dans la détermination de l'appartenance générique et/ou spécifique des écailles isolées. C.R. Acad. Sci. Paris, 303, II (13), pp. 1259-1261.

- Gayet, M. & Meunier, F.J. (1993). Conséquences paléobiogéographiques et biostratigraphiques de l'identification d'écailles ganoïdes du Crétacé supérieur et du Tertiaire inférieur d'Amérique du Sud. Doc. Lab. Géol. Lyon, 125, pp. 169-185.

- Brito, P.M., Meunier, F.J. & Gayet, M. (2000). The morphology and histology of the scales of the Cretaceous gar Obaichthys (Actinopterygii, Lepisosteidae): phylogenetic implications. C.R. Acad. Sci. Paris, 331, pp. 823-829.

## License

[Add license information]
