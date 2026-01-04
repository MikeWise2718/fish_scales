# Annotation Data Storage

This document describes how annotation data (tubercles and connections) are saved and loaded.

## Storage Location

All annotation files are saved in the **`annotations/`** directory at the project root. This directory is gitignored.

## Files Created Per Image

For each image, three files are created using the image's base name:

| File | Format | Content |
|------|--------|---------|
| `<image_name>_annotations.json` | JSON | Complete annotation data (all sets) |
| `<image_name>_tub.csv` | CSV | Tubercle data from the active set |
| `<image_name>_itc.csv` | CSV | Connection data from the active set |

**Example:** For `P1_Fig4_Atractosteus_simplex_7.07um.tif`:
- `annotations/P1_Fig4_Atractosteus_simplex_7.07um_annotations.json`
- `annotations/P1_Fig4_Atractosteus_simplex_7.07um_tub.csv`
- `annotations/P1_Fig4_Atractosteus_simplex_7.07um_itc.csv`

## Annotations JSON Format

### Version 3.0 (Current - Multiple Sets with Per-Set Calibration)

Version 3.0 introduces per-set calibration snapshots for provenance tracking and enhanced metadata.

```json
{
  "format": "fish-scale-annotations",
  "version": "3.0",
  "purpose": "Tubercle and intertubercular space annotations for SEM fish scale classification",
  "image_name": "example.tif",
  "created": "2025-01-15T10:30:00",
  "modified": "2025-01-15T14:45:00",
  "calibration": {
    "um_per_pixel": 0.1,
    "method": "manual",
    "source": "manual entry"
  },
  "parameters": {
    "method": "log",
    "threshold": 0.05,
    "min_diameter_um": 2.0,
    "max_diameter_um": 10.0,
    "min_circularity": 0.5
  },
  "activeSetId": "set-abc123",
  "sets": [
    {
      "id": "set-abc123",
      "name": "Initial Extraction",
      "createdAt": "2025-01-15T10:30:00",
      "modifiedAt": "2025-01-15T10:35:00",
      "calibration_um_per_pixel": 0.1,
      "parameters": {
        "method": "log",
        "threshold": 0.05,
        "min_diameter_um": 2.0,
        "max_diameter_um": 10.0,
        "min_circularity": 0.5,
        "graph_type": "gabriel"
      },
      "tubercles": [
        {
          "id": 1,
          "centroid_x": 150.5,
          "centroid_y": 200.3,
          "diameter_px": 45.2,
          "diameter_um": 4.52,
          "radius_px": 22.6,
          "circularity": 0.95,
          "is_boundary": false,
          "source": "extracted"
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
      ],
      "history": [
        {
          "type": "extraction",
          "timestamp": "2025-01-15T10:30:00",
          "user": "researcher",
          "method": "log",
          "n_tubercles": 45,
          "n_edges": 89,
          "parameters": {...},
          "calibration_um_per_pixel": 0.1
        }
      ]
    }
  ]
}
```

#### Key Changes in v3.0

| Field | Description |
|-------|-------------|
| `format` | Changed to `"fish-scale-annotations"` |
| `version` | String `"3.0"` instead of integer |
| `purpose` | New field describing file purpose |
| `modified` | Timestamp of last modification |
| `sets[].calibration_um_per_pixel` | **New**: Per-set calibration snapshot |
| `sets[].tubercles[].source` | **New**: `"extracted"` or `"manual"` |
| `sets[].history[].calibration_um_per_pixel` | **New**: Calibration recorded in history events |

### Version 2 (Legacy - Multiple Sets)

```json
{
  "format": "annotations-v2",
  "version": 2,
  "created": "2025-01-15T10:30:00",
  "image_name": "example.tif",
  "calibration": {
    "um_per_pixel": 0.1,
    "method": "manual"
  },
  "parameters": {...},
  "statistics": {...},
  "activeSetId": "set-1",
  "sets": [
    {
      "id": "set-1",
      "name": "Initial Extraction",
      "tubercles": [...],
      "edges": [...]
    }
  ]
}
```

V2 files are automatically upgraded to v3.0 format when saved.

### Version 1 (Legacy - Single Set)

```json
{
  "format": "annotations-v1",
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

V1 files are automatically converted to v3.0 multi-set format when saved.

## Calibration Provenance Tracking

### Per-Set Calibration Snapshots

Each set now stores the calibration value that was active when the set was created or extracted. This enables:

1. **Provenance tracking**: Know exactly what calibration was used for each extraction
2. **Mismatch detection**: UI warns if current calibration differs from set's stored calibration
3. **Recalculation**: Option to update measurements with new calibration

### Calibration Mismatch Warning

When the Data tab displays a set whose `calibration_um_per_pixel` differs from the current image calibration:

- A yellow warning banner appears
- Shows both calibration values
- Provides a "Recalculate" button to update the set's calibration

### History Event Calibration

Extraction and auto-connect history events now include `calibration_um_per_pixel` to record what calibration was active at that point in time.

## Backwards Compatibility

The system maintains full backwards compatibility:

| Loading | Behavior |
|---------|----------|
| V1 files | Converted to v3.0 with single set, calibration captured from current |
| V2 files | Sets receive `calibration_um_per_pixel` from current calibration |
| V3 files | Loaded as-is |

All saves are written in v3.0 format regardless of input version.

Legacy `*_slo.json` files are also supported when loading.

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
- `save_annotations()` - Save annotation data to files (always writes v3.0)
- `load_annotations()` - Load annotations JSON file (auto-detects version)
- `detect_annotation_version()` - Detect file version from structure
- `list_annotation_files()` - List available annotation files for an image

JavaScript implementation:
- `sets.js` - Manages set data including `calibration_um_per_pixel`
- `data.js` - Renders Data tab panels including calibration mismatch warnings
