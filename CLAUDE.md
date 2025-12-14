# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fish Scale Metrics Extraction - A Python CLI tool for extracting tubercle diameter and intertubercular space measurements from SEM (Scanning Electron Microscope) images of ganoid fish scales. These measurements differentiate between fish families/genera (Lepisosteidae, Polypteridae, Semionotidae) based on methodology from Gayet & Meunier (1986, 1993) and Brito et al. (2000).

## Development Commands

```bash
# Setup (using uv package manager)
uv venv
uv pip install -e ".[dev]"

# Run tests
uv run pytest                           # All tests
uv run pytest tests/test_detection.py   # Single test file
uv run pytest -k "test_name"            # Single test by name
uv run pytest --cov=fish_scale_analysis # With coverage

# CLI usage (run via uv or after activating venv)
uv run fish-scale-measure process <image>      # Process single image
uv run fish-scale-measure process ref          # Use test image alias
uv run fish-scale-measure batch <directory>    # Process multiple images
uv run fish-scale-measure benchmark            # Validate against known test values

# Quick test with reference image
uv run fish-scale-measure process test_images/P2_Fig1c_Paralepidosteus_sp_Acre_5.73um.tif
```

## Architecture

### Core Pipeline (`src/fish_scale_analysis/core/`)
1. **Calibration** (`calibration.py`) - Convert pixels to micrometers using scale bar or 700× magnification estimate
2. **Preprocessing** (`preprocessing.py`) - CLAHE enhancement, Gaussian blur for noise reduction
3. **Detection** (`detection.py`) - Blob detection (LoG/DoG/ellipse/lattice methods) with circularity filtering
4. **Measurement** (`measurement.py`) - Delaunay/Gabriel/RNG triangulation for neighbor identification, edge-to-edge spacing calculation
5. **Classification** - Compare metrics against reference ranges in `models.py`

### Key Data Models (`models.py`)
- `CalibrationData` - Pixel-to-micrometer conversion with `px_to_um()` and `um_to_px()` methods
- `Tubercle` - Single detected tubercle with position, diameter, circularity, optional ellipse parameters
- `NeighborEdge` - Edge between neighboring tubercles with center and edge-to-edge distances
- `MeasurementResult` - Complete results including statistics and genus classification
- `GENUS_REFERENCE_RANGES` - Reference ranges for Lepisosteus, Atractosteus, Polypterus, Obaichthys, Paralepidosteus, Lepidotes

### Parameter Profiles (`profiles.py`)
Predefined parameter sets for different image types/species:
- `default` - General use parameters
- `paralepidosteus` - Large tubercles, wide spacing (calibration: 0.33 µm/px)
- `lepisosteus` - Medium tubercles, close spacing
- `polypterus` - Small tubercles (1.5-4.0 µm), wide spacing
- `high-contrast` / `low-contrast` - Image quality presets
- `scanned-pdf` - For images extracted from scanned PDFs

Usage: `fish-scale-measure process image.tif --profile paralepidosteus`

### CLI Image Aliases (`cli.py:TEST_IMAGE_ALIASES`)
Short aliases for test images: `ref`, `P1.1`-`P1.6`, `P2.1a`-`P2.1e`, `P3.4`, `P3.5`

### Detection Methods (`--method`)
- `log` (default) - Laplacian of Gaussian blob detection
- `dog` - Difference of Gaussian (faster, less accurate)
- `ellipse` - Threshold + ellipse fitting
- `lattice` - Hexagonal lattice-aware detection (`core/lattice.py`)

### Neighbor Graph Types (`--neighbor-graph`)
- `delaunay` - All Delaunay edges
- `gabriel` - Gabriel graph (fewer edges)
- `rng` - Relative Neighborhood Graph (most conservative, recommended for spacing)

### Spacing Methods (`--spacing-method`)
- `nearest` (default) - Nearest-neighbor distances only (matches Gayet & Meunier methodology)
- `graph` - All edges from the neighbor graph

## Test Images and Validation

Test images in `test_images/` have known expected values from original research papers (see `test_images/test_cases.md`). The `benchmark` command validates measurements against these values.

Acceptance criteria:
- Tubercle Diameter: ± 0.5 µm
- Intertubercular Space: ± 0.7 µm
- Correct genus classification

## Output Structure

Each run creates a timestamped directory in `output/` containing:
- `processing_log.txt` - Detailed log
- `*_summary.csv` - Summary statistics
- `*_tubercles.csv` - Per-tubercle measurements
- `*_edges.csv` - Neighbor edge measurements
- `*_detection.png` - Two-panel visualization (detected tubercles + geometry diagram)
