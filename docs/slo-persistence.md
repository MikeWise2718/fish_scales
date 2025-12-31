# SLO Persistence - Annotation Data Storage

This document describes how annotation data (tubercles and connections) are saved and loaded.

## Storage Location

All annotation files are saved in the **`slo/`** directory at the project root. This directory is gitignored.

## Files Created Per Image

For each image, three files are created using the image's base name:

| File | Format | Content |
|------|--------|---------|
| `<image_name>_slo.json` | JSON | Complete annotation data (all sets) |
| `<image_name>_tub.csv` | CSV | Tubercle data from the active set |
| `<image_name>_itc.csv` | CSV | Connection data from the active set |

**Example:** For `P1_Fig4_Atractosteus_simplex_7.07um.tif`:
- `slo/P1_Fig4_Atractosteus_simplex_7.07um_slo.json`
- `slo/P1_Fig4_Atractosteus_simplex_7.07um_tub.csv`
- `slo/P1_Fig4_Atractosteus_simplex_7.07um_itc.csv`

## SLO JSON Format

### Version 2 (Current - Multiple Sets)

```json
{
  "version": 2,
  "created": "2025-01-15T10:30:00",
  "image_name": "example.tif",
  "calibration": {
    "um_per_pixel": 0.1,
    "method": "manual"
  },
  "parameters": {
    "method": "log",
    "min_sigma": 5.0,
    "max_sigma": 15.0,
    ...
  },
  "statistics": {
    "tubercle_diameter_mean": 7.2,
    "intertubercular_space_mean": 12.5,
    ...
  },
  "activeSetId": "set-1",
  "sets": [
    {
      "id": "set-1",
      "name": "Initial Extraction",
      "tubercles": [
        {
          "id": 1,
          "centroid_x": 150.5,
          "centroid_y": 200.3,
          "diameter_px": 45.2,
          "diameter_um": 4.52,
          "radius_px": 22.6,
          "circularity": 0.95
        }
      ],
      "edges": [
        {
          "id1": 1,
          "id2": 2,
          "x1": 150.5,
          "y1": 200.3,
          "x2": 180.2,
          "y2": 210.1,
          "center_distance_um": 3.2,
          "edge_distance_um": 1.5
        }
      ]
    },
    {
      "id": "set-2",
      "name": "After Manual Edit",
      "tubercles": [...],
      "edges": [...]
    }
  ]
}
```

### Version 1 (Legacy - Single Set)

```json
{
  "version": "1.0",
  "created": "2025-01-15T10:30:00",
  "image_name": "example.tif",
  "calibration": {...},
  "parameters": {...},
  "statistics": {...},
  "tubercles": [...],
  "edges": [...]
}
```

V1 files are automatically supported when loading - the system treats them as a single set.

## CSV Export Format

### Tubercle CSV (`*_tub.csv`)

| Column | Description |
|--------|-------------|
| `id` | Unique tubercle identifier |
| `centroid_x` | X coordinate in pixels |
| `centroid_y` | Y coordinate in pixels |
| `diameter_px` | Diameter in pixels |
| `diameter_um` | Diameter in micrometers |
| `radius_px` | Radius in pixels |
| `circularity` | Circularity score (0-1) |

### Connection CSV (`*_itc.csv`)

| Column | Description |
|--------|-------------|
| `id1` | First tubercle ID |
| `id2` | Second tubercle ID |
| `x1`, `y1` | First tubercle coordinates |
| `x2`, `y2` | Second tubercle coordinates |
| `center_distance_um` | Center-to-center distance in micrometers |
| `edge_distance_um` | Edge-to-edge distance (intertubercular space) |

## Implementation

The persistence logic is in `src/fish_scale_ui/services/persistence.py`:
- `save_slo()` - Save annotation data to files
- `load_slo()` - Load SLO JSON file
- `list_slo_files()` - List available SLO files for an image
