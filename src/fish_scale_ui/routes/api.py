"""API routes for Fish Scale UI."""

import os
import shutil
import uuid
from pathlib import Path

from flask import Blueprint, request, jsonify, current_app, send_file
import numpy as np
from PIL import Image

api_bp = Blueprint('api', __name__)

# In-memory storage for current session
_current_image = {
    'path': None,      # Original file path (for processing)
    'web_path': None,  # Web-displayable version (PNG for TIF files)
    'filename': None,
    'rotation': 0,
    'calibration': None,
    'slo_saved': False,  # Track if we've saved SLO this session (skip overwrite warning)
}

# In-memory storage for extraction results
_extraction_data = {
    'tubercles': [],
    'edges': [],
    'statistics': {},
    'parameters': {},
    'dirty': False,  # Track unsaved changes
}


def allowed_file(filename):
    """Check if file extension is allowed."""
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in current_app.config['ALLOWED_EXTENSIONS']


def convert_to_web_format(image_path, output_path):
    """Convert image to web-displayable PNG format.

    TIF/TIFF files cannot be displayed by browsers, so we convert them to PNG.
    Returns the path to the converted image (or original if no conversion needed).
    """
    ext = image_path.suffix.lower()

    # These formats need conversion
    if ext in ('.tif', '.tiff'):
        with Image.open(image_path) as img:
            # Convert to RGB if necessary (handles 16-bit, CMYK, etc.)
            if img.mode in ('I;16', 'I;16B', 'I;16L', 'I;16N'):
                # 16-bit grayscale - normalize to 8-bit
                import numpy as np
                arr = np.array(img, dtype=np.float32)
                arr = (arr - arr.min()) / (arr.max() - arr.min()) * 255
                img = Image.fromarray(arr.astype(np.uint8))
            elif img.mode == 'I':
                # 32-bit integer - normalize
                import numpy as np
                arr = np.array(img, dtype=np.float32)
                arr = (arr - arr.min()) / (arr.max() - arr.min()) * 255
                img = Image.fromarray(arr.astype(np.uint8))
            elif img.mode not in ('RGB', 'RGBA', 'L', 'LA'):
                img = img.convert('RGB')

            # Save as PNG
            png_path = output_path.with_suffix('.png')
            img.save(png_path, 'PNG')
            return png_path

    return image_path


@api_bp.route('/upload', methods=['POST'])
def upload_image():
    """Handle image upload."""
    from fish_scale_ui.services.logging import log_event
    from fish_scale_ui.services.recent_images import add_recent_image, init_recent_images

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': f'Unsupported file format. Allowed: TIF, TIFF, JPEG, JPG, PNG'}), 400

    # Save with unique name to avoid conflicts
    ext = file.filename.rsplit('.', 1)[-1].lower()
    unique_id = uuid.uuid4().hex
    unique_name = f"{unique_id}.{ext}"
    save_path = current_app.config['UPLOAD_FOLDER'] / unique_name

    try:
        file.save(save_path)

        # Convert to web-displayable format if needed (TIF -> PNG)
        web_path = convert_to_web_format(save_path, save_path)
        web_name = web_path.name

        # Get dimensions from the web-ready image
        with Image.open(web_path) as img:
            width, height = img.size

        # Update current image state (store original for processing, web version for display)
        _current_image['path'] = str(save_path)  # Original for processing
        _current_image['web_path'] = str(web_path)  # Converted for display
        _current_image['filename'] = file.filename
        _current_image['rotation'] = 0
        _current_image['calibration'] = None
        _current_image['slo_saved'] = False  # Reset on new image

        # Add to recent images
        init_recent_images(current_app.config['APP_ROOT'])
        add_recent_image(str(save_path), file.filename)

        # Log the event
        log_event('image_loaded', {
            'filename': file.filename,
            'width': width,
            'height': height
        })

        return jsonify({
            'success': True,
            'filename': file.filename,
            'url': f'/uploads/{web_name}',
            'width': width,
            'height': height
        })

    except Exception as e:
        if save_path.exists():
            save_path.unlink()
        return jsonify({'error': f'Failed to load image: {str(e)}'}), 400


@api_bp.route('/load-recent', methods=['POST'])
def load_recent():
    """Load a recently opened image."""
    from fish_scale_ui.services.logging import log_event
    from fish_scale_ui.services.recent_images import add_recent_image, init_recent_images

    data = request.get_json()
    if not data or 'path' not in data:
        return jsonify({'error': 'No path provided'}), 400

    image_path = Path(data['path'])
    if not image_path.exists():
        return jsonify({'error': 'Image file no longer exists'}), 404

    try:
        # Copy to uploads folder
        ext = image_path.suffix.lower().lstrip('.')
        unique_id = uuid.uuid4().hex
        unique_name = f"{unique_id}.{ext}"
        save_path = current_app.config['UPLOAD_FOLDER'] / unique_name
        shutil.copy2(image_path, save_path)

        # Convert to web-displayable format if needed (TIF -> PNG)
        web_path = convert_to_web_format(save_path, save_path)
        web_name = web_path.name

        with Image.open(web_path) as img:
            width, height = img.size

        _current_image['path'] = str(save_path)  # Original for processing
        _current_image['web_path'] = str(web_path)  # Converted for display
        _current_image['filename'] = image_path.name
        _current_image['rotation'] = 0
        _current_image['calibration'] = None
        _current_image['slo_saved'] = False  # Reset on new image

        init_recent_images(current_app.config['APP_ROOT'])
        add_recent_image(str(image_path), image_path.name)

        log_event('image_loaded', {
            'filename': image_path.name,
            'width': width,
            'height': height,
            'source': 'recent'
        })

        return jsonify({
            'success': True,
            'filename': image_path.name,
            'url': f'/uploads/{web_name}',
            'width': width,
            'height': height
        })

    except Exception as e:
        return jsonify({'error': f'Failed to load image: {str(e)}'}), 400


@api_bp.route('/rotate', methods=['POST'])
def rotate_image():
    """Rotate the current image by 90 degrees."""
    from fish_scale_ui.services.logging import log_event

    data = request.get_json()
    direction = data.get('direction', 'right')

    if not _current_image['path']:
        return jsonify({'error': 'No image loaded'}), 400

    try:
        # Use web_path for display (it's the PNG version for TIF files)
        web_path = Path(_current_image.get('web_path') or _current_image['path'])

        with Image.open(web_path) as img:
            if direction == 'left':
                rotated = img.rotate(90, expand=True)
                _current_image['rotation'] = (_current_image['rotation'] - 90) % 360
            else:
                rotated = img.rotate(-90, expand=True)
                _current_image['rotation'] = (_current_image['rotation'] + 90) % 360

            rotated.save(web_path, 'PNG' if web_path.suffix.lower() == '.png' else None)
            width, height = rotated.size

        log_event('image_rotated', {
            'direction': direction,
            'new_rotation': _current_image['rotation']
        })

        return jsonify({
            'success': True,
            'width': width,
            'height': height,
            'rotation': _current_image['rotation'],
            'url': f'/uploads/{web_path.name}?t={uuid.uuid4().hex[:8]}'
        })

    except Exception as e:
        return jsonify({'error': f'Failed to rotate image: {str(e)}'}), 400


@api_bp.route('/calibration', methods=['GET', 'POST'])
def calibration():
    """Get or set calibration data."""
    from fish_scale_ui.services.logging import log_event

    if request.method == 'GET':
        return jsonify({
            'calibration': _current_image.get('calibration'),
            'is_auto': _current_image.get('calibration') is None
        })

    data = request.get_json()

    if 'um_per_px' in data:
        _current_image['calibration'] = {
            'um_per_px': float(data['um_per_px']),
            'method': data.get('method', 'manual')
        }
    elif 'scale_um' in data and 'scale_px' in data:
        um_per_px = float(data['scale_um']) / float(data['scale_px'])
        _current_image['calibration'] = {
            'um_per_px': um_per_px,
            'method': 'scale_bar'
        }
    else:
        return jsonify({'error': 'Invalid calibration data'}), 400

    log_event('calibration_set', _current_image['calibration'])

    return jsonify({
        'success': True,
        'calibration': _current_image['calibration']
    })


@api_bp.route('/log', methods=['GET', 'POST'])
def handle_log():
    """Get or add log entries."""
    from fish_scale_ui.services.logging import get_log_entries, log_event

    if request.method == 'GET':
        return jsonify({'entries': get_log_entries()})

    # POST - add a log entry
    data = request.get_json() or {}
    event_type = data.get('event_type', 'unknown')
    details = data.get('details', {})

    log_event(event_type, details)
    return jsonify({'success': True})


@api_bp.route('/current-image', methods=['GET'])
def get_current_image():
    """Get current image info."""
    if not _current_image.get('path'):
        return jsonify({'loaded': False})

    # Build web URL from web_path
    web_url = None
    if _current_image.get('web_path'):
        web_path = Path(_current_image['web_path'])
        web_url = f"/uploads/{web_path.name}"

    return jsonify({
        'loaded': True,
        'filename': _current_image.get('filename'),
        'rotation': _current_image.get('rotation', 0),
        'calibration': _current_image.get('calibration'),
        'web_url': web_url,
    })


@api_bp.route('/browse', methods=['GET'])
def browse_images():
    """Browse images in the configured image directory."""
    image_dir = Path(current_app.config['IMAGE_DIR'])
    subdir = request.args.get('subdir', '')

    # Resolve the target directory, preventing directory traversal
    if subdir:
        target_dir = (image_dir / subdir).resolve()
        # Security check: ensure we're still within image_dir
        try:
            target_dir.relative_to(image_dir)
        except ValueError:
            return jsonify({'error': 'Invalid directory'}), 400
    else:
        target_dir = image_dir

    if not target_dir.exists():
        return jsonify({'error': 'Directory not found'}), 404

    allowed_ext = current_app.config['ALLOWED_EXTENSIONS']

    files = []
    directories = []

    try:
        for entry in sorted(target_dir.iterdir()):
            if entry.is_dir():
                directories.append({
                    'name': entry.name,
                    'path': str(entry.relative_to(image_dir)) if subdir else entry.name
                })
            elif entry.is_file():
                ext = entry.suffix.lower().lstrip('.')
                if ext in allowed_ext:
                    files.append({
                        'name': entry.name,
                        'path': str(entry),
                        'size': entry.stat().st_size,
                        'modified': entry.stat().st_mtime
                    })
    except PermissionError:
        return jsonify({'error': 'Permission denied'}), 403

    return jsonify({
        'directory': str(target_dir),
        'relative_path': subdir or '',
        'parent': str(Path(subdir).parent) if subdir and subdir != '.' else None,
        'directories': directories,
        'files': files
    })


@api_bp.route('/profiles', methods=['GET'])
def get_profiles():
    """Get list of available detection profiles."""
    from fish_scale_ui.services.extraction import get_profiles_list
    return jsonify({'profiles': get_profiles_list()})


@api_bp.route('/extract', methods=['POST'])
def extract():
    """Run tubercle extraction on the current image."""
    from fish_scale_ui.services.logging import log_event
    from fish_scale_ui.services.extraction import run_extraction

    if not _current_image['path']:
        return jsonify({'error': 'No image loaded'}), 400

    if not _current_image.get('calibration'):
        return jsonify({'error': 'Calibration not set'}), 400

    data = request.get_json() or {}

    # Get calibration
    calibration = _current_image['calibration']
    um_per_px = calibration.get('um_per_px', 0.33)

    try:
        # Use web_path (converted PNG) not original path (TIF)
        # to ensure extraction coordinates match displayed image
        image_to_process = _current_image.get('web_path') or _current_image['path']
        result = run_extraction(
            image_path=image_to_process,
            um_per_px=um_per_px,
            method=data.get('method', 'log'),
            threshold=float(data.get('threshold', 0.05)),
            min_diameter_um=float(data.get('min_diameter_um', 2.0)),
            max_diameter_um=float(data.get('max_diameter_um', 10.0)),
            min_circularity=float(data.get('min_circularity', 0.5)),
            clahe_clip=float(data.get('clahe_clip', 0.03)),
            clahe_kernel=int(data.get('clahe_kernel', 8)),
            blur_sigma=float(data.get('blur_sigma', 1.0)),
            neighbor_graph=data.get('neighbor_graph', 'delaunay'),
            cull_long_edges=data.get('cull_long_edges', True),
            cull_factor=float(data.get('cull_factor', 1.8)),
        )

        # Store extraction results
        _extraction_data['tubercles'] = result['tubercles']
        _extraction_data['edges'] = result['edges']
        _extraction_data['statistics'] = result['statistics']
        _extraction_data['parameters'] = result['parameters']
        _extraction_data['dirty'] = True

        # Log the extraction
        log_event('extraction_complete', {
            'n_tubercles': result['statistics']['n_tubercles'],
            'n_edges': result['statistics']['n_edges'],
            'method': result['parameters']['method'],
            'hexagonalness_score': result['statistics'].get('hexagonalness_score'),
            'reliability': result['statistics'].get('reliability'),
        })

        return jsonify(result)

    except Exception as e:
        log_event('extraction_failed', {'error': str(e)})
        return jsonify({'error': f'Extraction failed: {str(e)}'}), 500


@api_bp.route('/extraction-data', methods=['GET'])
def get_extraction_data():
    """Get current extraction data."""
    return jsonify({
        'tubercles': _extraction_data['tubercles'],
        'edges': _extraction_data['edges'],
        'statistics': _extraction_data['statistics'],
        'parameters': _extraction_data['parameters'],
        'dirty': _extraction_data['dirty'],
    })


@api_bp.route('/regenerate-connections', methods=['POST'])
def regenerate_connections():
    """Regenerate connections for given tubercles using specified graph method.

    POST body:
        {
            "tubercles": [...],
            "graph_type": "delaunay" | "gabriel" | "rng",
            "cull_long_edges": true | false,
            "cull_factor": float (default 1.8)
        }

    Returns:
        {"success": true, "edges": [...], "statistics": {...}}
    """
    from fish_scale_ui.services.logging import log_event
    from fish_scale_analysis.core.measurement import filter_to_gabriel, filter_to_rng
    from scipy.spatial import Delaunay
    import numpy as np
    import math

    if not _current_image.get('calibration'):
        return jsonify({'error': 'Calibration not set'}), 400

    data = request.get_json() or {}
    tubercles = data.get('tubercles', [])
    graph_type = data.get('graph_type', 'gabriel')
    cull_long_edges = data.get('cull_long_edges', True)
    cull_factor = float(data.get('cull_factor', 1.8))

    if graph_type not in ('delaunay', 'gabriel', 'rng'):
        return jsonify({'error': f'Invalid graph_type: {graph_type}'}), 400

    if len(tubercles) < 2:
        return jsonify({
            'success': True,
            'edges': [],
            'statistics': {'n_edges': 0, 'mean_space_um': 0, 'std_space_um': 0}
        })

    um_per_px = _current_image['calibration'].get('um_per_px', 0.33)

    try:
        # Build centroids array
        centroids = np.array([[t['centroid_x'], t['centroid_y']] for t in tubercles])
        radii = np.array([t.get('radius_px', 10) for t in tubercles])

        # Build Delaunay triangulation
        if len(tubercles) < 3:
            # With only 2 tubercles, just connect them directly
            edge_indices = [(0, 1)]
        else:
            tri = Delaunay(centroids)

            # Extract all Delaunay edges
            delaunay_edges = set()
            for simplex in tri.simplices:
                for i in range(3):
                    edge = tuple(sorted([simplex[i], simplex[(i + 1) % 3]]))
                    delaunay_edges.add(edge)

            # Filter based on graph type
            if graph_type == 'delaunay':
                edge_indices = list(delaunay_edges)
            elif graph_type == 'gabriel':
                edge_indices = list(filter_to_gabriel(centroids, delaunay_edges))
            else:  # rng
                edge_indices = list(filter_to_rng(centroids, delaunay_edges))

        # Convert to edge objects with distance calculations
        edges = []
        for i, j in edge_indices:
            tub1 = tubercles[i]
            tub2 = tubercles[j]

            x1, y1 = tub1['centroid_x'], tub1['centroid_y']
            x2, y2 = tub2['centroid_x'], tub2['centroid_y']
            r1, r2 = radii[i], radii[j]

            center_dist_px = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            edge_dist_px = max(0, center_dist_px - r1 - r2)

            edges.append({
                'id1': tub1['id'],
                'id2': tub2['id'],
                'x1': x1,
                'y1': y1,
                'x2': x2,
                'y2': y2,
                'center_distance_um': center_dist_px * um_per_px,
                'edge_distance_um': edge_dist_px * um_per_px,
            })

        # Cull long edges if enabled
        if cull_long_edges and edges:
            avg_center_distance = np.mean([e['center_distance_um'] for e in edges])
            max_allowed = avg_center_distance * cull_factor
            edges = [e for e in edges if e['center_distance_um'] <= max_allowed]

        # Calculate statistics
        statistics = {'n_edges': len(edges), 'mean_space_um': 0, 'std_space_um': 0}
        if edges:
            edge_distances = [e['edge_distance_um'] for e in edges]
            statistics['mean_space_um'] = float(np.mean(edge_distances))
            statistics['std_space_um'] = float(np.std(edge_distances))

        log_event('regenerate_connections', {
            'graph_type': graph_type,
            'n_tubercles': len(tubercles),
            'n_edges': len(edges),
            'cull_long_edges': cull_long_edges,
            'cull_factor': cull_factor,
        })

        return jsonify({
            'success': True,
            'edges': edges,
            'statistics': statistics,
        })

    except Exception as e:
        log_event('regenerate_connections_failed', {'error': str(e)})
        return jsonify({'error': f'Regenerate connections failed: {str(e)}'}), 500


@api_bp.route('/save-slo', methods=['POST'])
def save_slo():
    """Save SLO data to files.

    Supports both v1 (legacy) and v2 (multiple sets) formats.
    v2 format includes 'version': 2 and 'sets': [...] in the request.
    """
    from fish_scale_ui.services.logging import log_event
    from fish_scale_ui.services.persistence import save_slo as persist_slo

    if not _current_image['filename']:
        return jsonify({'error': 'No image loaded'}), 400

    data = request.get_json() or {}
    force = data.get('force', False)
    version = data.get('version', 1)

    # Check for v2 format (multiple sets)
    if version == 2 and 'sets' in data:
        sets = data.get('sets', [])
        activeSetId = data.get('activeSetId')
        statistics = data.get('statistics', {})
        parameters = data.get('parameters', {})

        # Count total tubercles across all sets
        total_tubercles = sum(len(s.get('tubercles', [])) for s in sets)
        total_edges = sum(len(s.get('edges', [])) for s in sets)

        # Allow saving even with 0 tubercles for v2 (empty sets are valid)
        if len(sets) == 0:
            return jsonify({'error': 'No sets to save'}), 400

        slo_dir = current_app.config['APP_ROOT'] / 'slo'

        try:
            result = persist_slo(
                slo_dir=slo_dir,
                image_name=_current_image['filename'],
                calibration=_current_image.get('calibration', {}),
                version=2,
                sets=sets,
                activeSetId=activeSetId,
                statistics=statistics,
                parameters=parameters,
            )

            # Skip overwrite warning if we've already saved this session
            if _current_image.get('slo_saved') and result.get('existing_files'):
                result['existing_files'] = []

            if result['success']:
                # Mark that we've saved this session
                _current_image['slo_saved'] = True

                # Update server-side cache with active set data
                active_set = None
                for s in sets:
                    if s.get('id') == activeSetId:
                        active_set = s
                        break
                if not active_set and sets:
                    active_set = sets[0]

                if active_set:
                    _extraction_data['tubercles'] = active_set.get('tubercles', [])
                    _extraction_data['edges'] = active_set.get('edges', [])
                _extraction_data['statistics'] = statistics
                _extraction_data['parameters'] = parameters
                _extraction_data['dirty'] = False

                log_event('slo_saved', {
                    'filename': _current_image['filename'],
                    'version': 2,
                    'n_sets': len(sets),
                    'n_tubercles': total_tubercles,
                    'n_edges': total_edges,
                })

            return jsonify(result)

        except Exception as e:
            log_event('slo_save_failed', {'error': str(e)})
            return jsonify({'error': f'Save failed: {str(e)}'}), 500

    # V1 format (legacy)
    tubercles = data.get('tubercles', _extraction_data.get('tubercles', []))
    edges = data.get('edges', _extraction_data.get('edges', []))
    statistics = data.get('statistics', _extraction_data.get('statistics', {}))
    parameters = data.get('parameters', _extraction_data.get('parameters', {}))

    if not tubercles:
        return jsonify({'error': 'No data to save'}), 400

    slo_dir = current_app.config['APP_ROOT'] / 'slo'

    try:
        result = persist_slo(
            slo_dir=slo_dir,
            image_name=_current_image['filename'],
            calibration=_current_image.get('calibration', {}),
            tubercles=tubercles,
            edges=edges,
            statistics=statistics,
            parameters=parameters,
        )

        # Skip overwrite warning if we've already saved this session
        if _current_image.get('slo_saved') and result.get('existing_files'):
            result['existing_files'] = []

        if result['success']:
            # Mark that we've saved this session
            _current_image['slo_saved'] = True

            # Update server-side cache
            _extraction_data['tubercles'] = tubercles
            _extraction_data['edges'] = edges
            _extraction_data['statistics'] = statistics
            _extraction_data['parameters'] = parameters
            _extraction_data['dirty'] = False

            log_event('slo_saved', {
                'filename': _current_image['filename'],
                'n_tubercles': len(tubercles),
                'n_edges': len(edges),
            })

        return jsonify(result)

    except Exception as e:
        log_event('slo_save_failed', {'error': str(e)})
        return jsonify({'error': f'Save failed: {str(e)}'}), 500


@api_bp.route('/load-slo', methods=['POST'])
def load_slo():
    """Load SLO data from a file."""
    from fish_scale_ui.services.logging import log_event
    from fish_scale_ui.services.persistence import load_slo as load_slo_file

    data = request.get_json() or {}
    slo_path = data.get('path')

    if not slo_path:
        # Try to find SLO for current image
        if not _current_image['filename']:
            return jsonify({'error': 'No image loaded and no path provided'}), 400

        slo_dir = current_app.config['APP_ROOT'] / 'slo'
        base_name = Path(_current_image['filename']).stem
        slo_path = slo_dir / f"{base_name}_slo.json"

    try:
        result = load_slo_file(slo_path)

        if result['success']:
            slo_data = result['data']

            # Check image name match
            name_match = True
            if _current_image['filename']:
                loaded_name = slo_data.get('image_name', '')
                if loaded_name and loaded_name != _current_image['filename']:
                    name_match = False

            # Update extraction data - handle both v1 and v2 formats
            if slo_data.get('version') == 2 and slo_data.get('sets'):
                # V2 format: get data from active set
                active_set_id = slo_data.get('activeSetId')
                active_set = None
                for s in slo_data['sets']:
                    if s.get('id') == active_set_id:
                        active_set = s
                        break
                if not active_set and slo_data['sets']:
                    active_set = slo_data['sets'][0]

                if active_set:
                    _extraction_data['tubercles'] = active_set.get('tubercles', [])
                    _extraction_data['edges'] = active_set.get('edges', [])
                else:
                    _extraction_data['tubercles'] = []
                    _extraction_data['edges'] = []
            else:
                # V1 format: get data from root level
                _extraction_data['tubercles'] = slo_data.get('tubercles', [])
                _extraction_data['edges'] = slo_data.get('edges', [])

            _extraction_data['statistics'] = slo_data.get('statistics', {})
            _extraction_data['parameters'] = slo_data.get('parameters', {})
            _extraction_data['dirty'] = False

            # Update calibration if present
            if slo_data.get('calibration'):
                _current_image['calibration'] = slo_data['calibration']

            # Mark as saved since we loaded existing files
            _current_image['slo_saved'] = True

            log_event('slo_loaded', {
                'filename': slo_data.get('image_name', 'unknown'),
                'n_tubercles': len(_extraction_data['tubercles']),
                'n_edges': len(_extraction_data['edges']),
            })

            return jsonify({
                'success': True,
                'data': slo_data,
                'name_match': name_match,
            })

        return jsonify(result)

    except Exception as e:
        log_event('slo_load_failed', {'error': str(e)})
        return jsonify({'error': f'Load failed: {str(e)}'}), 500


@api_bp.route('/list-slo', methods=['GET'])
def list_slo():
    """List available SLO files."""
    from fish_scale_ui.services.persistence import list_slo_files

    slo_dir = current_app.config['APP_ROOT'] / 'slo'
    image_name = request.args.get('image')

    files = list_slo_files(slo_dir, image_name)
    return jsonify({'files': files})


@api_bp.route('/dirty-state', methods=['GET', 'POST'])
def dirty_state():
    """Get or set the dirty state."""
    if request.method == 'GET':
        return jsonify({'dirty': _extraction_data['dirty']})

    data = request.get_json() or {}
    if 'dirty' in data:
        _extraction_data['dirty'] = bool(data['dirty'])
    return jsonify({'dirty': _extraction_data['dirty']})


@api_bp.route('/crop', methods=['POST'])
def crop_image():
    """Crop the current image to the specified region."""
    from fish_scale_ui.services.logging import log_event

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No crop data provided'}), 400

    x = int(data.get('x', 0))
    y = int(data.get('y', 0))
    width = int(data.get('width', 0))
    height = int(data.get('height', 0))

    if width <= 0 or height <= 0:
        return jsonify({'error': 'Invalid crop dimensions'}), 400

    if not _current_image['path']:
        return jsonify({'error': 'No image loaded'}), 400

    try:
        # Use web_path for display (it's the PNG version for TIF files)
        web_path = Path(_current_image.get('web_path') or _current_image['path'])

        with Image.open(web_path) as img:
            # Ensure crop region is within image bounds
            img_width, img_height = img.size
            x = max(0, min(x, img_width - 1))
            y = max(0, min(y, img_height - 1))
            width = min(width, img_width - x)
            height = min(height, img_height - y)

            # Perform the crop
            cropped = img.crop((x, y, x + width, y + height))
            cropped.save(web_path, 'PNG' if web_path.suffix.lower() == '.png' else None)

            new_width, new_height = cropped.size

        # Clear any existing extraction data since the image changed
        _extraction_data['tubercles'] = []
        _extraction_data['edges'] = []
        _extraction_data['statistics'] = {}
        _extraction_data['parameters'] = {}
        _extraction_data['dirty'] = False

        log_event('image_cropped', {
            'x': x,
            'y': y,
            'width': new_width,
            'height': new_height,
            'original_width': img_width,
            'original_height': img_height
        })

        return jsonify({
            'success': True,
            'width': new_width,
            'height': new_height,
            'url': f'/uploads/{web_path.name}?t={uuid.uuid4().hex[:8]}'
        })

    except Exception as e:
        return jsonify({'error': f'Failed to crop image: {str(e)}'}), 400


@api_bp.route('/autocrop', methods=['POST'])
def autocrop_image():
    """Automatically crop the image to remove empty/uniform borders."""
    from fish_scale_ui.services.logging import log_event

    if not _current_image['path']:
        return jsonify({'error': 'No image loaded'}), 400

    try:
        # Use web_path for display (it's the PNG version for TIF files)
        web_path = Path(_current_image.get('web_path') or _current_image['path'])

        with Image.open(web_path) as img:
            original_width, original_height = img.size

            # Convert to numpy array for edge detection
            img_array = np.array(img.convert('L'))  # Convert to grayscale

            # Find rows and columns that are not uniform (have variance)
            # Threshold for detecting "non-empty" content
            threshold = 10

            # Check each row for variance
            row_variance = np.var(img_array, axis=1)
            col_variance = np.var(img_array, axis=0)

            # Find first and last rows/cols with content
            non_empty_rows = np.where(row_variance > threshold)[0]
            non_empty_cols = np.where(col_variance > threshold)[0]

            if len(non_empty_rows) == 0 or len(non_empty_cols) == 0:
                return jsonify({'error': 'Could not detect content boundaries'}), 400

            top = int(non_empty_rows[0])
            bottom = int(non_empty_rows[-1]) + 1
            left = int(non_empty_cols[0])
            right = int(non_empty_cols[-1]) + 1

            # Add small padding (5 pixels)
            padding = 5
            top = max(0, top - padding)
            bottom = min(original_height, bottom + padding)
            left = max(0, left - padding)
            right = min(original_width, right + padding)

            # Check if crop would actually change anything
            if top == 0 and bottom == original_height and left == 0 and right == original_width:
                return jsonify({'error': 'No empty borders detected'}), 400

            # Perform the crop
            cropped = img.crop((left, top, right, bottom))
            cropped.save(web_path, 'PNG' if web_path.suffix.lower() == '.png' else None)

            new_width, new_height = cropped.size

        # Clear any existing extraction data since the image changed
        _extraction_data['tubercles'] = []
        _extraction_data['edges'] = []
        _extraction_data['statistics'] = {}
        _extraction_data['parameters'] = {}
        _extraction_data['dirty'] = False

        log_event('image_autocropped', {
            'original_width': original_width,
            'original_height': original_height,
            'new_width': new_width,
            'new_height': new_height,
            'removed_top': top,
            'removed_left': left,
        })

        return jsonify({
            'success': True,
            'width': new_width,
            'height': new_height,
            'url': f'/uploads/{web_path.name}?t={uuid.uuid4().hex[:8]}'
        })

    except Exception as e:
        return jsonify({'error': f'Failed to autocrop image: {str(e)}'}), 400
