"""Persistence service for annotation files."""

import json
import csv
from datetime import datetime
from pathlib import Path
from typing import Optional


def save_annotations(
    annotations_dir: Path,
    image_name: str,
    calibration: dict,
    tubercles: list = None,
    edges: list = None,
    statistics: dict = None,
    parameters: dict = None,
    version: int = 1,
    sets: list = None,
    activeSetId: str = None,
) -> dict:
    """
    Save annotation data to files.

    Supports two formats:
    - v1 (legacy): Single set with tubercles and edges at root level
    - v2 (new): Multiple sets with data in sets array

    Creates:
    - <image_name>_tub.csv - Tubercle data (from active set in v2)
    - <image_name>_itc.csv - Intertubercular connection data (from active set in v2)
    - <image_name>_annotations.json - Full annotation data

    Args:
        annotations_dir: Directory to save files to
        image_name: Base name of the image (without extension)
        calibration: Calibration data dict
        tubercles: List of tubercle dicts (v1 format)
        edges: List of edge dicts (v1 format)
        statistics: Statistics dict
        parameters: Extraction parameters dict
        version: Annotation format version (1 or 2)
        sets: List of set dicts (v2 format)
        activeSetId: ID of the active set (v2 format)

    Returns:
        Dict with success status and file paths
    """
    annotations_dir = Path(annotations_dir)
    annotations_dir.mkdir(parents=True, exist_ok=True)

    # Clean up image name (remove extension)
    base_name = Path(image_name).stem

    # File paths
    tub_path = annotations_dir / f"{base_name}_tub.csv"
    itc_path = annotations_dir / f"{base_name}_itc.csv"
    annotations_path = annotations_dir / f"{base_name}_annotations.json"

    # Check for existing files
    existing_files = []
    if tub_path.exists():
        existing_files.append(str(tub_path.name))
    if itc_path.exists():
        existing_files.append(str(itc_path.name))
    if annotations_path.exists():
        existing_files.append(str(annotations_path.name))

    # Determine the data to write to CSV (active set for v2, or root level for v1)
    if version == 2 and sets:
        # Find the active set to export CSVs
        active_set = None
        for s in sets:
            if s.get('id') == activeSetId:
                active_set = s
                break
        if not active_set and sets:
            active_set = sets[0]

        csv_tubercles = active_set.get('tubercles', []) if active_set else []
        csv_edges = active_set.get('edges', []) if active_set else []
    else:
        csv_tubercles = tubercles or []
        csv_edges = edges or []

    # Save TUB CSV (from active set)
    with open(tub_path, 'w', newline='', encoding='utf-8') as f:
        if csv_tubercles:
            writer = csv.DictWriter(f, fieldnames=['id', 'centroid_x', 'centroid_y',
                                                    'diameter_px', 'diameter_um',
                                                    'radius_px', 'circularity'],
                                    extrasaction='ignore')  # Ignore extra fields like ellipse params
            writer.writeheader()
            writer.writerows(csv_tubercles)

    # Save ITC CSV (from active set)
    with open(itc_path, 'w', newline='', encoding='utf-8') as f:
        if csv_edges:
            writer = csv.DictWriter(f, fieldnames=['id1', 'id2', 'x1', 'y1', 'x2', 'y2',
                                                   'center_distance_um', 'edge_distance_um'])
            writer.writeheader()
            writer.writerows(csv_edges)

    # Build annotation JSON data
    if version == 2:
        # V2 format with multiple sets
        annotations_data = {
            'format': 'annotations-v2',
            'version': 2,
            'created': datetime.now().isoformat(),
            'image_name': image_name,
            'calibration': calibration,
            'parameters': parameters or {},
            'statistics': statistics or {},
            'activeSetId': activeSetId,
            'sets': sets or [],
        }
    else:
        # V1 format (legacy)
        annotations_data = {
            'format': 'annotations-v1',
            'version': '1.0',
            'created': datetime.now().isoformat(),
            'image_name': image_name,
            'calibration': calibration,
            'parameters': parameters or {},
            'statistics': statistics or {},
            'tubercles': tubercles or [],
            'edges': edges or [],
        }

    with open(annotations_path, 'w', encoding='utf-8') as f:
        json.dump(annotations_data, f, indent=2)

    return {
        'success': True,
        'files': {
            'tub_csv': str(tub_path),
            'itc_csv': str(itc_path),
            'annotations_json': str(annotations_path),
        },
        'existing_files': existing_files,
    }


def load_annotations(annotations_path: Path) -> dict:
    """
    Load annotation data from a JSON file.

    Args:
        annotations_path: Path to the annotations JSON file

    Returns:
        Dict with annotation data or error
    """
    annotations_path = Path(annotations_path)

    if not annotations_path.exists():
        return {'success': False, 'error': 'Annotations file not found'}

    try:
        with open(annotations_path, 'r', encoding='utf-8') as f:
            annotations_data = json.load(f)

        return {
            'success': True,
            'data': annotations_data,
        }
    except json.JSONDecodeError as e:
        return {'success': False, 'error': f'Invalid JSON: {str(e)}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def list_annotation_files(annotations_dir: Path, image_name: Optional[str] = None) -> list:
    """
    List annotation files in a directory.

    Args:
        annotations_dir: Directory to search
        image_name: If provided, only list files for this image

    Returns:
        List of annotation file info dicts
    """
    annotations_dir = Path(annotations_dir)
    if not annotations_dir.exists():
        return []

    files = []

    # Look for both new (*_annotations.json) and legacy (*_slo.json) files
    if image_name:
        patterns = [
            f"{Path(image_name).stem}_annotations.json",
            f"{Path(image_name).stem}_slo.json",  # Legacy support
        ]
    else:
        patterns = ["*_annotations.json", "*_slo.json"]

    for pattern in patterns:
        for annotations_file in annotations_dir.glob(pattern):
            try:
                with open(annotations_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                files.append({
                    'path': str(annotations_file),
                    'filename': annotations_file.name,
                    'image_name': data.get('image_name', ''),
                    'created': data.get('created', ''),
                    'n_tubercles': len(data.get('tubercles', [])),
                    'n_edges': len(data.get('edges', [])),
                })
            except Exception:
                continue

    return files


# Backwards compatibility aliases
save_slo = save_annotations
load_slo = load_annotations
list_slo_files = list_annotation_files
