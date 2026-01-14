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
    'annotations_saved': False,  # Track if we've saved annotations this session (skip overwrite warning)
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
    """Handle image upload (drag-drop).

    Note: Drag-drop uploads are NOT added to recent images because we don't
    have access to the original file path (browser security restriction).
    Only files loaded via the file browser are tracked in recents.
    """
    from fish_scale_ui.services.logging import log_event

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
        _current_image['annotations_saved'] = False  # Reset on new image

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
        _current_image['annotations_saved'] = False  # Reset on new image

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
    """Browse images in a directory.

    Query parameters:
        path: Absolute path to browse (optional, defaults to IMAGE_DIR)
        subdir: Subdirectory relative to IMAGE_DIR (legacy, for backwards compatibility)

    Returns directory listing with files and subdirectories.
    """
    from fish_scale_ui.services.logging import log_event

    image_dir = Path(current_app.config['IMAGE_DIR'])

    # Support both absolute path and relative subdir
    abs_path = request.args.get('path', '')
    subdir = request.args.get('subdir', '')

    if abs_path:
        # Absolute path navigation
        target_dir = Path(abs_path).resolve()
    elif subdir:
        # Legacy: relative to IMAGE_DIR
        target_dir = (image_dir / subdir).resolve()
    else:
        # Default to IMAGE_DIR
        target_dir = image_dir.resolve()

    if not target_dir.exists():
        return jsonify({'error': 'Directory not found'}), 404

    if not target_dir.is_dir():
        return jsonify({'error': 'Not a directory'}), 400

    allowed_ext = current_app.config['ALLOWED_EXTENSIONS']

    files = []
    directories = []

    try:
        for entry in sorted(target_dir.iterdir()):
            if entry.is_dir():
                # Skip hidden directories
                if entry.name.startswith('.'):
                    continue
                directories.append({
                    'name': entry.name,
                    'path': str(entry.resolve())  # Always use absolute paths
                })
            elif entry.is_file():
                ext = entry.suffix.lower().lstrip('.')
                if ext in allowed_ext:
                    files.append({
                        'name': entry.name,
                        'path': str(entry.resolve()),
                        'size': entry.stat().st_size,
                        'modified': entry.stat().st_mtime
                    })
    except PermissionError:
        log_event('browse_permission_denied', {'directory': str(target_dir)})
        return jsonify({'error': 'Permission denied'}), 403

    # Determine parent directory (None if at filesystem root)
    parent_dir = target_dir.parent
    has_parent = parent_dir != target_dir  # At root, parent == self

    return jsonify({
        'directory': str(target_dir),
        'parent': str(parent_dir) if has_parent else None,
        'directories': directories,
        'files': files
    })


@api_bp.route('/profiles', methods=['GET'])
def get_profiles():
    """Get list of available detection profiles."""
    from fish_scale_ui.services.extraction import get_profiles_list
    return jsonify({'profiles': get_profiles_list()})


@api_bp.route('/profile', methods=['POST'])
def load_profile():
    """Load a specific detection profile by name.

    Request body:
        {"name": "default"}

    Returns:
        {"parameters": {...profile parameters...}}
    """
    from fish_scale_analysis.profiles import get_profile

    data = request.get_json() or {}
    profile_name = data.get('name', 'default')

    try:
        profile = get_profile(profile_name)
    except KeyError:
        return jsonify({'error': f'Unknown profile: {profile_name}'}), 404

    # Convert profile to parameters dict
    parameters = {
        'method': 'log',  # Default method
        'threshold': profile.threshold,
        'min_diameter_um': profile.min_diameter_um,
        'max_diameter_um': profile.max_diameter_um,
        'min_circularity': profile.min_circularity,
        'clahe_clip': profile.clahe_clip,
        'clahe_kernel': profile.clahe_kernel,
        'blur_sigma': profile.blur_sigma,
    }

    return jsonify({
        'success': True,
        'profile': profile_name,
        'parameters': parameters
    })


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


# Module-level state for optimization
_optimizer_state = {
    'running': False,
    'stop_requested': False,
    'current_iteration': 0,
    'best_score': 0,
    'best_params': None,
}


@api_bp.route('/optimize-step', methods=['POST'])
def optimize_step():
    """Perform one gradient ascent optimization step.

    POST body:
        {
            "params": {
                "threshold": 0.05,
                "min_diameter_um": 2.0,
                "max_diameter_um": 10.0,
                "min_circularity": 0.5,
                "clahe_clip": 0.03,
                "clahe_kernel": 8,
                "blur_sigma": 1.0,
                ...
            },
            "enabled_params": ["threshold", "min_circularity", "blur_sigma"],
            "iteration": 1,
            "max_iterations": 20,
            "delta_threshold": 0.001,
            "target_score": 0.85
        }

    Returns:
        {
            "success": true,
            "new_params": {...},
            "gradient": {...},
            "hexagonalness": 0.723,
            "prev_hexagonalness": 0.711,
            "delta": 0.012,
            "tubercles": [...],
            "edges": [...],
            "statistics": {...},
            "extractions_performed": 15,
            "should_stop": false,
            "stop_reason": ""
        }
    """
    from fish_scale_ui.services.logging import log_event
    from fish_scale_ui.services.optimizer import run_optimize_step, GradientOptimizer

    if not _current_image['path']:
        return jsonify({'error': 'No image loaded'}), 400

    if not _current_image.get('calibration'):
        return jsonify({'error': 'Calibration not set'}), 400

    if _optimizer_state['running']:
        return jsonify({'error': 'Optimization already running'}), 400

    data = request.get_json() or {}
    params = data.get('params', {})
    enabled_params = data.get('enabled_params')

    # Convergence parameters (for frontend-driven auto mode)
    iteration = data.get('iteration', 1)
    max_iterations = data.get('max_iterations', 20)
    delta_threshold = data.get('delta_threshold', 0.001)
    target_score = data.get('target_score', 0.85)

    # Get calibration
    calibration = _current_image['calibration']
    um_per_px = calibration.get('um_per_px', 0.33)

    # Use web_path for extraction consistency
    image_path = _current_image.get('web_path') or _current_image['path']

    try:
        _optimizer_state['running'] = True

        result = run_optimize_step(
            image_path=image_path,
            um_per_px=um_per_px,
            params=params,
            enabled_params=enabled_params,
        )

        # Check convergence
        should_stop, stop_reason = GradientOptimizer.check_convergence(
            prev_score=result['prev_hexagonalness'],
            new_score=result['hexagonalness'],
            iteration=iteration,
            delta_threshold=delta_threshold,
            max_iterations=max_iterations,
            target_score=target_score,
        )
        result['should_stop'] = should_stop
        result['stop_reason'] = stop_reason
        result['iteration'] = iteration

        # Update extraction data with the new results
        _extraction_data['tubercles'] = result['tubercles']
        _extraction_data['edges'] = result['edges']
        _extraction_data['statistics'] = result['statistics']
        _extraction_data['parameters'] = result['new_params']
        _extraction_data['dirty'] = True

        # Log the optimization step
        log_event('optimize_step', {
            'iteration': iteration,
            'prev_hexagonalness': result['prev_hexagonalness'],
            'hexagonalness': result['hexagonalness'],
            'delta': result['delta'],
            'enabled_params': enabled_params,
            'extractions_performed': result['extractions_performed'],
            'should_stop': should_stop,
            'stop_reason': stop_reason,
        })

        return jsonify(result)

    except Exception as e:
        log_event('optimize_step_failed', {'error': str(e)})
        return jsonify({'error': f'Optimization step failed: {str(e)}'}), 500

    finally:
        _optimizer_state['running'] = False


@api_bp.route('/optimize-auto', methods=['POST'])
def optimize_auto():
    """Run automatic optimization until convergence.

    POST body:
        {
            "params": {...},
            "enabled_params": ["threshold", "min_circularity", "blur_sigma"],
            "max_iterations": 20,
            "delta_threshold": 0.001,
            "target_score": 0.85
        }

    Returns:
        {
            "success": true,
            "final_params": {...},
            "final_score": 0.78,
            "iterations": 8,
            "reason": "converged",
            "history": [{"iteration": 1, "hexagonalness": 0.65, "delta": 0.03}, ...],
            "tubercles": [...],
            "edges": [...],
            "statistics": {...}
        }
    """
    from fish_scale_ui.services.logging import log_event
    from fish_scale_ui.services.optimizer import GradientOptimizer

    if not _current_image['path']:
        return jsonify({'error': 'No image loaded'}), 400

    if not _current_image.get('calibration'):
        return jsonify({'error': 'Calibration not set'}), 400

    if _optimizer_state['running']:
        return jsonify({'error': 'Optimization already running'}), 400

    data = request.get_json() or {}
    params = data.get('params', {})
    enabled_params = data.get('enabled_params')
    max_iterations = int(data.get('max_iterations', 20))
    delta_threshold = float(data.get('delta_threshold', 0.001))
    target_score = float(data.get('target_score', 0.85))

    # Get calibration
    calibration = _current_image['calibration']
    um_per_px = calibration.get('um_per_px', 0.33)

    # Use web_path for extraction consistency
    image_path = _current_image.get('web_path') or _current_image['path']

    try:
        _optimizer_state['running'] = True
        _optimizer_state['stop_requested'] = False
        _optimizer_state['current_iteration'] = 0
        _optimizer_state['best_score'] = 0
        _optimizer_state['best_params'] = None

        optimizer = GradientOptimizer(
            image_path=image_path,
            um_per_px=um_per_px,
            enabled_params=enabled_params,
        )

        current_params = params.copy()
        history = []
        prev_score = 0
        final_result = None
        reason = 'max_iterations'

        for iteration in range(1, max_iterations + 1):
            if _optimizer_state['stop_requested']:
                reason = 'stopped'
                break

            _optimizer_state['current_iteration'] = iteration

            # Run one step
            result = optimizer.step(current_params)
            current_params = result['new_params']
            new_score = result['hexagonalness']
            final_result = result

            # Track history
            history.append({
                'iteration': iteration,
                'hexagonalness': new_score,
                'delta': result['delta'],
            })

            # Track best
            if new_score > _optimizer_state['best_score']:
                _optimizer_state['best_score'] = new_score
                _optimizer_state['best_params'] = current_params.copy()

            # Check convergence
            should_stop, stop_reason = GradientOptimizer.check_convergence(
                prev_score=prev_score,
                new_score=new_score,
                iteration=iteration,
                delta_threshold=delta_threshold,
                max_iterations=max_iterations,
                target_score=target_score,
            )

            if should_stop:
                reason = stop_reason
                break

            prev_score = new_score

        # Update extraction data with final results
        if final_result:
            _extraction_data['tubercles'] = final_result['tubercles']
            _extraction_data['edges'] = final_result['edges']
            _extraction_data['statistics'] = final_result['statistics']
            _extraction_data['parameters'] = final_result['new_params']
            _extraction_data['dirty'] = True

        # Log the optimization
        log_event('optimize_auto_complete', {
            'iterations': len(history),
            'final_score': final_result['hexagonalness'] if final_result else 0,
            'reason': reason,
            'enabled_params': enabled_params,
        })

        return jsonify({
            'success': True,
            'final_params': current_params,
            'final_score': final_result['hexagonalness'] if final_result else 0,
            'iterations': len(history),
            'reason': reason,
            'history': history,
            'tubercles': final_result['tubercles'] if final_result else [],
            'edges': final_result['edges'] if final_result else [],
            'statistics': final_result['statistics'] if final_result else {},
        })

    except Exception as e:
        log_event('optimize_auto_failed', {'error': str(e)})
        return jsonify({'error': f'Optimization failed: {str(e)}'}), 500

    finally:
        _optimizer_state['running'] = False


@api_bp.route('/optimize-stop', methods=['POST'])
def optimize_stop():
    """Stop running optimization.

    Returns:
        {
            "success": true,
            "stopped_at_iteration": 5,
            "current_score": 0.72
        }
    """
    if not _optimizer_state['running']:
        return jsonify({'error': 'No optimization running'}), 400

    _optimizer_state['stop_requested'] = True

    return jsonify({
        'success': True,
        'stopped_at_iteration': _optimizer_state['current_iteration'],
        'best_score': _optimizer_state['best_score'],
    })


@api_bp.route('/optimize-status', methods=['GET'])
def optimize_status():
    """Get current optimization status.

    Returns:
        {
            "running": true,
            "current_iteration": 5,
            "best_score": 0.72
        }
    """
    return jsonify({
        'running': _optimizer_state['running'],
        'current_iteration': _optimizer_state['current_iteration'],
        'best_score': _optimizer_state['best_score'],
    })


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
        {"success": true, "edges": [...], "tubercles": [...], "statistics": {...}}

    Note: Returns updated tubercles with is_boundary flag set based on Delaunay boundary detection.
    """
    from fish_scale_ui.services.logging import log_event
    from fish_scale_analysis.core.measurement import filter_to_gabriel, filter_to_rng
    from scipy.spatial import Delaunay
    from collections import defaultdict
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
        # Mark all as boundary since there's no triangulation
        updated_tubercles = [{**t, 'is_boundary': True} for t in tubercles]
        return jsonify({
            'success': True,
            'edges': [],
            'tubercles': updated_tubercles,
            'statistics': {'n_edges': 0, 'mean_space_um': 0, 'std_space_um': 0, 'n_boundary': len(tubercles), 'n_interior': 0}
        })

    um_per_px = _current_image['calibration'].get('um_per_px', 0.33)

    try:
        # Build centroids array
        centroids = np.array([[t['centroid_x'], t['centroid_y']] for t in tubercles])
        radii = np.array([t.get('radius_px', 10) for t in tubercles])

        # Build Delaunay triangulation
        boundary_indices = set()
        if len(tubercles) < 3:
            # With only 2 tubercles, just connect them directly
            edge_indices = [(0, 1)]
            # Both are boundary nodes
            boundary_indices = {0, 1}
        else:
            tri = Delaunay(centroids)

            # Extract all Delaunay edges and count triangles per edge
            edge_count = defaultdict(int)
            for simplex in tri.simplices:
                for i in range(3):
                    edge = tuple(sorted([simplex[i], simplex[(i + 1) % 3]]))
                    edge_count[edge] += 1

            delaunay_edges = set(edge_count.keys())

            # Find boundary edges (appear in only one triangle)
            boundary_edges = {edge for edge, count in edge_count.items() if count == 1}

            # Find boundary nodes
            for edge in boundary_edges:
                boundary_indices.add(edge[0])
                boundary_indices.add(edge[1])

            # Filter based on graph type
            if graph_type == 'delaunay':
                edge_indices = list(delaunay_edges)
            elif graph_type == 'gabriel':
                edge_indices = list(filter_to_gabriel(centroids, delaunay_edges))
            else:  # rng
                edge_indices = list(filter_to_rng(centroids, delaunay_edges))

        # Update tubercles with boundary flag
        updated_tubercles = []
        for idx, t in enumerate(tubercles):
            updated_t = {**t, 'is_boundary': idx in boundary_indices}
            updated_tubercles.append(updated_t)

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
        statistics = {
            'n_edges': len(edges),
            'mean_space_um': 0,
            'std_space_um': 0,
            'n_boundary': len(boundary_indices),
            'n_interior': len(tubercles) - len(boundary_indices),
        }
        if edges:
            edge_distances = [e['edge_distance_um'] for e in edges]
            statistics['mean_space_um'] = float(np.mean(edge_distances))
            statistics['std_space_um'] = float(np.std(edge_distances))

        log_event('regenerate_connections', {
            'graph_type': graph_type,
            'n_tubercles': len(tubercles),
            'n_edges': len(edges),
            'n_boundary': len(boundary_indices),
            'cull_long_edges': cull_long_edges,
            'cull_factor': cull_factor,
        })

        # Update server-side state so hexagonalness API returns correct data
        _extraction_data['tubercles'] = updated_tubercles
        _extraction_data['edges'] = edges
        _extraction_data['statistics'] = statistics
        _extraction_data['dirty'] = True

        return jsonify({
            'success': True,
            'edges': edges,
            'tubercles': updated_tubercles,
            'statistics': statistics,
        })

    except Exception as e:
        log_event('regenerate_connections_failed', {'error': str(e)})
        return jsonify({'error': f'Regenerate connections failed: {str(e)}'}), 500


@api_bp.route('/save-annotations', methods=['POST'])
def save_annotations():
    """Save annotation data to files.

    Supports both v1 (legacy) and v2 (multiple sets) formats.
    v2 format includes 'version': 2 and 'sets': [...] in the request.
    """
    from fish_scale_ui.services.logging import log_event
    from fish_scale_ui.services.persistence import save_annotations as persist_annotations

    if not _current_image['filename']:
        return jsonify({'error': 'No image loaded'}), 400

    data = request.get_json() or {}
    force = data.get('force', False)
    version = data.get('version', 1)
    custom_filename = data.get('custom_filename')  # For Save As

    # Check for v2 format (multiple sets)
    if version == 2 and 'sets' in data:
        sets = data.get('sets', [])
        activeSetId = data.get('activeSetId')
        statistics = data.get('statistics', {})
        parameters = data.get('parameters', {})
        defaultTubercleDiameterUm = data.get('defaultTubercleDiameterUm')

        # Count total tubercles across all sets
        total_tubercles = sum(len(s.get('tubercles', [])) for s in sets)
        total_edges = sum(len(s.get('edges', [])) for s in sets)

        # Allow saving even with 0 tubercles for v2 (empty sets are valid)
        if len(sets) == 0:
            return jsonify({'error': 'No sets to save'}), 400

        annotations_dir = current_app.config['APP_ROOT'] / 'annotations'

        try:
            result = persist_annotations(
                annotations_dir=annotations_dir,
                image_name=_current_image['filename'],
                calibration=_current_image.get('calibration', {}),
                version=2,
                sets=sets,
                activeSetId=activeSetId,
                statistics=statistics,
                parameters=parameters,
                custom_filename=custom_filename,
                defaultTubercleDiameterUm=defaultTubercleDiameterUm,
            )

            # Skip overwrite warning if we've already saved this session
            if _current_image.get('annotations_saved') and result.get('existing_files'):
                result['existing_files'] = []

            if result['success']:
                # Mark that we've saved this session
                _current_image['annotations_saved'] = True

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

                log_event('annotations_saved', {
                    'filename': _current_image['filename'],
                    'version': 2,
                    'n_sets': len(sets),
                    'n_tubercles': total_tubercles,
                    'n_edges': total_edges,
                })

            return jsonify(result)

        except Exception as e:
            log_event('annotations_save_failed', {'error': str(e)})
            return jsonify({'error': f'Save failed: {str(e)}'}), 500

    # V1 format (legacy)
    tubercles = data.get('tubercles', _extraction_data.get('tubercles', []))
    edges = data.get('edges', _extraction_data.get('edges', []))
    statistics = data.get('statistics', _extraction_data.get('statistics', {}))
    parameters = data.get('parameters', _extraction_data.get('parameters', {}))

    if not tubercles:
        return jsonify({'error': 'No data to save'}), 400

    annotations_dir = current_app.config['APP_ROOT'] / 'annotations'

    try:
        result = persist_annotations(
            annotations_dir=annotations_dir,
            image_name=_current_image['filename'],
            calibration=_current_image.get('calibration', {}),
            tubercles=tubercles,
            edges=edges,
            statistics=statistics,
            parameters=parameters,
        )

        # Skip overwrite warning if we've already saved this session
        if _current_image.get('annotations_saved') and result.get('existing_files'):
            result['existing_files'] = []

        if result['success']:
            # Mark that we've saved this session
            _current_image['annotations_saved'] = True

            # Update server-side cache
            _extraction_data['tubercles'] = tubercles
            _extraction_data['edges'] = edges
            _extraction_data['statistics'] = statistics
            _extraction_data['parameters'] = parameters
            _extraction_data['dirty'] = False

            log_event('annotations_saved', {
                'filename': _current_image['filename'],
                'n_tubercles': len(tubercles),
                'n_edges': len(edges),
            })

        return jsonify(result)

    except Exception as e:
        log_event('annotations_save_failed', {'error': str(e)})
        return jsonify({'error': f'Save failed: {str(e)}'}), 500


@api_bp.route('/load-annotations', methods=['POST'])
def load_annotations():
    """Load annotation data from a file."""
    from fish_scale_ui.services.logging import log_event
    from fish_scale_ui.services.persistence import load_annotations as load_annotations_file

    data = request.get_json() or {}
    annotations_path = data.get('path')

    if not annotations_path:
        # Try to find annotations for current image
        if not _current_image['filename']:
            return jsonify({'error': 'No image loaded and no path provided'}), 400

        annotations_dir = current_app.config['APP_ROOT'] / 'annotations'
        base_name = Path(_current_image['filename']).stem
        # Try new naming first, fall back to legacy
        annotations_path = annotations_dir / f"{base_name}_annotations.json"
        if not annotations_path.exists():
            annotations_path = annotations_dir / f"{base_name}_slo.json"

    try:
        result = load_annotations_file(annotations_path)

        if result['success']:
            annotations_data = result['data']

            # Check image name match
            name_match = True
            if _current_image['filename']:
                loaded_name = annotations_data.get('image_name', '')
                if loaded_name and loaded_name != _current_image['filename']:
                    name_match = False

            # Update extraction data - handle both v1 and v2 formats
            if annotations_data.get('version') == 2 and annotations_data.get('sets'):
                # V2 format: get data from active set
                active_set_id = annotations_data.get('activeSetId')
                active_set = None
                for s in annotations_data['sets']:
                    if s.get('id') == active_set_id:
                        active_set = s
                        break
                if not active_set and annotations_data['sets']:
                    active_set = annotations_data['sets'][0]

                if active_set:
                    _extraction_data['tubercles'] = active_set.get('tubercles', [])
                    _extraction_data['edges'] = active_set.get('edges', [])
                else:
                    _extraction_data['tubercles'] = []
                    _extraction_data['edges'] = []
            else:
                # V1 format: get data from root level
                _extraction_data['tubercles'] = annotations_data.get('tubercles', [])
                _extraction_data['edges'] = annotations_data.get('edges', [])

            _extraction_data['statistics'] = annotations_data.get('statistics', {})
            _extraction_data['parameters'] = annotations_data.get('parameters', {})
            _extraction_data['dirty'] = False

            # Update calibration if present
            if annotations_data.get('calibration'):
                _current_image['calibration'] = annotations_data['calibration']

            # Mark as saved since we loaded existing files
            _current_image['annotations_saved'] = True

            log_event('annotations_loaded', {
                'filename': annotations_data.get('image_name', 'unknown'),
                'n_tubercles': len(_extraction_data['tubercles']),
                'n_edges': len(_extraction_data['edges']),
            })

            return jsonify({
                'success': True,
                'data': annotations_data,
                'name_match': name_match,
            })

        return jsonify(result)

    except Exception as e:
        log_event('annotations_load_failed', {'error': str(e)})
        return jsonify({'error': f'Load failed: {str(e)}'}), 500


@api_bp.route('/list-annotations', methods=['GET'])
def list_annotations():
    """List available annotation files."""
    from fish_scale_ui.services.persistence import list_annotation_files

    annotations_dir = current_app.config['APP_ROOT'] / 'annotations'
    image_name = request.args.get('image')

    files = list_annotation_files(annotations_dir, image_name)
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


@api_bp.route('/recalculate-boundaries', methods=['POST'])
def recalculate_boundaries():
    """Recalculate boundary status for tubercles based on Delaunay triangulation.

    POST body:
        {
            "tubercles": [...]
        }

    Returns:
        {"success": true, "tubercles": [...], "n_boundary": int, "n_interior": int}
    """
    from scipy.spatial import Delaunay
    from collections import defaultdict

    data = request.get_json() or {}
    tubercles = data.get('tubercles', [])

    if len(tubercles) < 3:
        # All nodes are boundary if less than 3
        updated = [{**t, 'is_boundary': True} for t in tubercles]
        return jsonify({
            'success': True,
            'tubercles': updated,
            'n_boundary': len(tubercles),
            'n_interior': 0,
        })

    try:
        # Build centroids array
        centroids = np.array([[t['centroid_x'], t['centroid_y']] for t in tubercles])

        # Build Delaunay triangulation
        tri = Delaunay(centroids)

        # Count triangles per edge to find boundary edges
        edge_count = defaultdict(int)
        for simplex in tri.simplices:
            for i in range(3):
                edge = tuple(sorted([simplex[i], simplex[(i + 1) % 3]]))
                edge_count[edge] += 1

        # Boundary edges appear in exactly one triangle
        boundary_edges = {edge for edge, count in edge_count.items() if count == 1}

        # Find boundary nodes
        boundary_indices = set()
        for edge in boundary_edges:
            boundary_indices.add(edge[0])
            boundary_indices.add(edge[1])

        # Update tubercles with boundary flag
        updated = []
        for idx, t in enumerate(tubercles):
            updated.append({**t, 'is_boundary': idx in boundary_indices})

        return jsonify({
            'success': True,
            'tubercles': updated,
            'n_boundary': len(boundary_indices),
            'n_interior': len(tubercles) - len(boundary_indices),
        })

    except Exception as e:
        return jsonify({'error': f'Boundary calculation failed: {str(e)}'}), 500


@api_bp.route('/user', methods=['GET', 'POST'])
def user_endpoint():
    """Get or set the current user.

    GET: Returns current user name and source
    POST: Sets user name (if not locked by env var)
    """
    from fish_scale_ui.services.user import (
        get_current_user,
        set_user,
        get_user_source,
        is_user_overridable
    )

    if request.method == 'GET':
        return jsonify({
            'user': get_current_user(),
            'source': get_user_source(),
            'overridable': is_user_overridable(),
        })

    # POST - set user
    data = request.get_json() or {}
    new_user = data.get('user', '').strip()

    if not new_user:
        return jsonify({'error': 'User name cannot be empty'}), 400

    if not is_user_overridable():
        return jsonify({
            'error': 'User is set by FISH_SCALE_USER environment variable and cannot be changed'
        }), 403

    set_user(new_user)
    return jsonify({
        'success': True,
        'user': get_current_user(),
        'source': get_user_source(),
    })


@api_bp.route('/hexagonalness', methods=['GET', 'POST'])
def calculate_hexagonalness():
    """Calculate hexagonalness with custom weights.

    GET query parameters:
        spacing_weight: float (default 0.40)
        degree_weight: float (default 0.45)
        edge_ratio_weight: float (default 0.15)

    POST body (optional - uses server state if not provided):
        {
            "tubercles": [...],
            "edges": [...],
            "spacing_weight": 0.40,
            "degree_weight": 0.45,
            "edge_ratio_weight": 0.15
        }

    Returns component scores and weighted hexagonalness score.
    """
    from fish_scale_ui.routes.mcp_api import _calculate_hexagonalness_from_dicts

    # Handle both GET and POST
    if request.method == 'POST':
        data = request.get_json() or {}
        spacing_weight = float(data.get('spacing_weight', 0.40))
        degree_weight = float(data.get('degree_weight', 0.45))
        edge_ratio_weight = float(data.get('edge_ratio_weight', 0.15))
        # Use provided data if available, otherwise fall back to server state
        tubercles = data.get('tubercles', _extraction_data.get('tubercles', []))
        edges = data.get('edges', _extraction_data.get('edges', []))
    else:
        # GET request - use query params and server state
        spacing_weight = float(request.args.get('spacing_weight', 0.40))
        degree_weight = float(request.args.get('degree_weight', 0.45))
        edge_ratio_weight = float(request.args.get('edge_ratio_weight', 0.15))
        tubercles = _extraction_data.get('tubercles', [])
        edges = _extraction_data.get('edges', [])

    # Use the canonical implementation from mcp_api
    result = _calculate_hexagonalness_from_dicts(tubercles, edges)

    # Recalculate composite score with custom weights (if different from defaults)
    if spacing_weight != 0.40 or degree_weight != 0.45 or edge_ratio_weight != 0.15:
        score = (
            spacing_weight * result['spacing_uniformity'] +
            degree_weight * result['degree_score'] +
            edge_ratio_weight * result['edge_ratio_score']
        )
        result['hexagonalness_score'] = float(score)

    return jsonify(result)


@api_bp.route('/analyze-point', methods=['POST'])
def analyze_point():
    """Analyze image at a point to detect tubercle size.

    Extracts a region around the specified point, runs blob detection
    with the given parameters, and returns the detected blob info.

    POST body:
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

    Returns (blob detected):
        {
            "success": true,
            "detected": true,
            "diameter_px": 28.5,
            "diameter_um": 4.275,
            "radius_px": 14.25,
            "center_x": 244.2,
            "center_y": 313.1,
            "circularity": 0.87
        }

    Returns (no blob detected):
        {
            "success": true,
            "detected": false,
            "reason": "no_blob_found"
        }
    """
    from fish_scale_ui.services.extraction import analyze_point_for_tubercle

    if not _current_image['path']:
        return jsonify({'success': False, 'error': 'No image loaded'}), 400

    if not _current_image.get('calibration'):
        return jsonify({'success': False, 'error': 'Calibration not set'}), 400

    data = request.get_json() or {}
    x = float(data.get('x', 0))
    y = float(data.get('y', 0))
    parameters = data.get('parameters', {})

    um_per_px = _current_image['calibration'].get('um_per_px', 0.33)
    image_path = _current_image.get('web_path') or _current_image['path']

    region_factor = float(data.get('region_factor', 6.0))

    try:
        result = analyze_point_for_tubercle(
            image_path=image_path,
            x=x,
            y=y,
            um_per_px=um_per_px,
            method=parameters.get('method', 'log'),
            threshold=float(parameters.get('threshold', 0.05)),
            min_diameter_um=float(parameters.get('min_diameter_um', 2.0)),
            max_diameter_um=float(parameters.get('max_diameter_um', 10.0)),
            min_circularity=float(parameters.get('min_circularity', 0.5)),
            clahe_clip=float(parameters.get('clahe_clip', 0.03)),
            clahe_kernel=int(parameters.get('clahe_kernel', 8)),
            blur_sigma=float(parameters.get('blur_sigma', 1.0)),
            region_factor=region_factor,
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
