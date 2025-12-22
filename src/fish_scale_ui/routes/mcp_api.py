"""MCP API routes for Fish Scale UI.

These endpoints are designed to be called by the MCP server to control
the fish-scale-ui application programmatically.
"""

from flask import Blueprint, request, jsonify, current_app
from pathlib import Path

mcp_bp = Blueprint('mcp', __name__)


def get_state_refs():
    """Get references to the shared state from the main API module."""
    from fish_scale_ui.routes.api import _current_image, _extraction_data
    return _current_image, _extraction_data


@mcp_bp.route('/screenshot', methods=['GET'])
def get_screenshot():
    """Capture current view as base64 PNG with optional overlay.

    Query params:
        overlay: bool - Whether to include tubercle/connection overlay (default: true)
        numbers: bool - Whether to show tubercle ID numbers (default: false)
        scale_bar: bool - Whether to show scale bar (default: false)

    Returns:
        {
            "success": true,
            "image_b64": "base64-encoded PNG...",
            "width": int,
            "height": int
        }
    """
    from fish_scale_mcp.screenshot import render_screenshot
    from PIL import Image

    _current_image, _extraction_data = get_state_refs()

    if not _current_image.get('web_path'):
        return jsonify({'error': 'No image loaded'}), 400

    show_overlay = request.args.get('overlay', 'true').lower() == 'true'
    show_numbers = request.args.get('numbers', 'false').lower() == 'true'
    show_scale_bar = request.args.get('scale_bar', 'false').lower() == 'true'

    try:
        # Get image dimensions
        with Image.open(_current_image['web_path']) as img:
            width, height = img.size

        if show_overlay:
            image_b64 = render_screenshot(
                image_path=_current_image['web_path'],
                tubercles=_extraction_data.get('tubercles', []),
                connections=_extraction_data.get('edges', []),
                calibration=_current_image.get('calibration'),
                show_tubercles=True,
                show_connections=True,
                show_numbers=show_numbers,
                show_scale_bar=show_scale_bar,
                debug_shapes=_extraction_data.get('debug_shapes', []),
            )
        else:
            # Just return the image without overlay
            from fish_scale_mcp.screenshot import render_thumbnail
            import base64
            import io

            with Image.open(_current_image['web_path']) as img:
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                buffer.seek(0)
                image_b64 = base64.b64encode(buffer.read()).decode('utf-8')

        return jsonify({
            'success': True,
            'image_b64': image_b64,
            'width': width,
            'height': height,
        })

    except Exception as e:
        return jsonify({'error': f'Failed to capture screenshot: {str(e)}'}), 500


@mcp_bp.route('/state', methods=['GET'])
def get_state():
    """Get complete current state.

    Returns:
        {
            "image": {
                "loaded": bool,
                "filename": str,
                "path": str,
                "rotation": int,
                "width": int,
                "height": int
            },
            "calibration": {
                "um_per_px": float,
                "method": str
            },
            "tubercles": [...],
            "edges": [...],
            "statistics": {...},
            "parameters": {...},
            "dirty": bool
        }
    """
    from PIL import Image

    _current_image, _extraction_data = get_state_refs()

    # Get image info
    image_info = {'loaded': False}
    if _current_image.get('web_path'):
        try:
            with Image.open(_current_image['web_path']) as img:
                width, height = img.size
            image_info = {
                'loaded': True,
                'filename': _current_image.get('filename'),
                'path': _current_image.get('path'),
                'rotation': _current_image.get('rotation', 0),
                'width': width,
                'height': height,
            }
        except Exception:
            pass

    return jsonify({
        'image': image_info,
        'calibration': _current_image.get('calibration'),
        'tubercles': _extraction_data.get('tubercles', []),
        'edges': _extraction_data.get('edges', []),
        'statistics': _extraction_data.get('statistics', {}),
        'parameters': _extraction_data.get('parameters', {}),
        'dirty': _extraction_data.get('dirty', False),
        'debug_shapes': _extraction_data.get('debug_shapes', []),
    })


@mcp_bp.route('/params', methods=['GET', 'POST'])
def handle_params():
    """Get or set extraction parameters.

    GET returns current parameters.
    POST sets parameters (partial update supported).

    POST body:
        {
            "method": "log",
            "threshold": 0.05,
            "min_diameter_um": 2.0,
            "max_diameter_um": 10.0,
            "min_circularity": 0.5,
            "clahe_clip": 0.03,
            "clahe_kernel": 8,
            "blur_sigma": 1.0,
            "neighbor_graph": "delaunay"
        }
    """
    _current_image, _extraction_data = get_state_refs()

    if request.method == 'GET':
        return jsonify({
            'parameters': _extraction_data.get('parameters', {})
        })

    # POST - update parameters
    data = request.get_json() or {}

    # Get current params or defaults
    params = _extraction_data.get('parameters', {}).copy()

    # Update with provided values
    valid_keys = [
        'method', 'threshold', 'min_diameter_um', 'max_diameter_um',
        'min_circularity', 'clahe_clip', 'clahe_kernel', 'blur_sigma',
        'neighbor_graph', 'edge_margin_px'
    ]

    for key in valid_keys:
        if key in data:
            params[key] = data[key]

    _extraction_data['parameters'] = params

    return jsonify({
        'success': True,
        'parameters': params
    })


@mcp_bp.route('/tubercle', methods=['POST', 'PUT', 'DELETE'])
def handle_tubercle():
    """Add, move, or delete a tubercle.

    POST (add):
        {"x": float, "y": float, "radius": float}
        Returns: {"success": true, "tubercle": {...}, "id": int}

    PUT (move):
        {"id": int, "x": float, "y": float}
        Returns: {"success": true, "tubercle": {...}}

    DELETE:
        {"id": int}
        Returns: {"success": true}
    """
    from fish_scale_ui.services.logging import log_event

    _current_image, _extraction_data = get_state_refs()
    data = request.get_json() or {}

    if not _current_image.get('calibration'):
        return jsonify({'error': 'Calibration not set'}), 400

    um_per_px = _current_image['calibration'].get('um_per_px', 0.33)
    tubercles = _extraction_data.get('tubercles', [])

    if request.method == 'POST':
        # Add new tubercle
        x = data.get('x')
        y = data.get('y')
        radius = data.get('radius')

        if x is None or y is None:
            return jsonify({'error': 'x and y coordinates required'}), 400

        # Auto-calculate radius if not provided (use mean of existing)
        if radius is None:
            if tubercles:
                radius = sum(t.get('radius_px', 10) for t in tubercles) / len(tubercles)
            else:
                radius = 10  # Default

        # Generate new ID (max + 1)
        new_id = max((t.get('id', 0) for t in tubercles), default=0) + 1

        diameter_px = radius * 2
        diameter_um = diameter_px * um_per_px

        new_tub = {
            'id': new_id,
            'centroid_x': float(x),
            'centroid_y': float(y),
            'radius_px': float(radius),
            'diameter_px': float(diameter_px),
            'diameter_um': float(diameter_um),
            'circularity': 1.0,  # Perfect circle for manual additions
            'source': 'manual',  # Track origin for coloring
        }

        tubercles.append(new_tub)
        _extraction_data['tubercles'] = tubercles
        _extraction_data['dirty'] = True

        log_event('mcp_tubercle_added', {'id': new_id, 'x': x, 'y': y, 'radius': radius})

        return jsonify({
            'success': True,
            'tubercle': new_tub,
            'id': new_id,
        })

    elif request.method == 'PUT':
        # Move tubercle
        tub_id = data.get('id')
        new_x = data.get('x')
        new_y = data.get('y')

        if tub_id is None:
            return jsonify({'error': 'Tubercle ID required'}), 400

        # Find and update tubercle
        for tub in tubercles:
            if tub.get('id') == tub_id:
                if new_x is not None:
                    tub['centroid_x'] = float(new_x)
                if new_y is not None:
                    tub['centroid_y'] = float(new_y)

                _extraction_data['dirty'] = True
                log_event('mcp_tubercle_moved', {'id': tub_id, 'x': new_x, 'y': new_y})

                return jsonify({
                    'success': True,
                    'tubercle': tub,
                })

        return jsonify({'error': f'Tubercle {tub_id} not found'}), 404

    elif request.method == 'DELETE':
        # Delete tubercle
        tub_id = data.get('id')

        if tub_id is None:
            return jsonify({'error': 'Tubercle ID required'}), 400

        # Remove tubercle
        original_count = len(tubercles)
        tubercles = [t for t in tubercles if t.get('id') != tub_id]

        if len(tubercles) == original_count:
            return jsonify({'error': f'Tubercle {tub_id} not found'}), 404

        # Also remove any connections involving this tubercle
        edges = _extraction_data.get('edges', [])
        edges = [e for e in edges if e.get('id1') != tub_id and e.get('id2') != tub_id]

        _extraction_data['tubercles'] = tubercles
        _extraction_data['edges'] = edges
        _extraction_data['dirty'] = True

        log_event('mcp_tubercle_deleted', {'id': tub_id})

        return jsonify({'success': True})


@mcp_bp.route('/connection', methods=['POST', 'DELETE'])
def handle_connection():
    """Add or delete a connection between tubercles.

    POST (add):
        {"id1": int, "id2": int}
        Returns: {"success": true, "connection": {...}}

    DELETE:
        {"id1": int, "id2": int}
        Returns: {"success": true}
    """
    from fish_scale_ui.services.logging import log_event
    import math

    _current_image, _extraction_data = get_state_refs()
    data = request.get_json() or {}

    if not _current_image.get('calibration'):
        return jsonify({'error': 'Calibration not set'}), 400

    um_per_px = _current_image['calibration'].get('um_per_px', 0.33)
    tubercles = _extraction_data.get('tubercles', [])
    edges = _extraction_data.get('edges', [])

    id1 = data.get('id1')
    id2 = data.get('id2')

    if id1 is None or id2 is None:
        return jsonify({'error': 'id1 and id2 required'}), 400

    # Normalize order (smaller ID first)
    if id1 > id2:
        id1, id2 = id2, id1

    if request.method == 'POST':
        # Check if connection already exists
        for edge in edges:
            e_id1, e_id2 = edge.get('id1'), edge.get('id2')
            if e_id1 > e_id2:
                e_id1, e_id2 = e_id2, e_id1
            if e_id1 == id1 and e_id2 == id2:
                return jsonify({'error': 'Connection already exists'}), 400

        # Find tubercles
        tub1 = next((t for t in tubercles if t.get('id') == id1), None)
        tub2 = next((t for t in tubercles if t.get('id') == id2), None)

        if not tub1 or not tub2:
            return jsonify({'error': 'One or both tubercles not found'}), 404

        # Calculate distances
        x1, y1 = tub1['centroid_x'], tub1['centroid_y']
        x2, y2 = tub2['centroid_x'], tub2['centroid_y']
        r1, r2 = tub1.get('radius_px', 10), tub2.get('radius_px', 10)

        center_dist_px = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        edge_dist_px = max(0, center_dist_px - r1 - r2)

        new_edge = {
            'id1': id1,
            'id2': id2,
            'x1': x1,
            'y1': y1,
            'x2': x2,
            'y2': y2,
            'center_distance_um': center_dist_px * um_per_px,
            'edge_distance_um': edge_dist_px * um_per_px,
        }

        edges.append(new_edge)
        _extraction_data['edges'] = edges
        _extraction_data['dirty'] = True

        log_event('mcp_connection_added', {'id1': id1, 'id2': id2})

        return jsonify({
            'success': True,
            'connection': new_edge,
        })

    elif request.method == 'DELETE':
        # Remove connection
        original_count = len(edges)

        def matches(edge):
            e_id1, e_id2 = edge.get('id1'), edge.get('id2')
            if e_id1 > e_id2:
                e_id1, e_id2 = e_id2, e_id1
            return e_id1 == id1 and e_id2 == id2

        edges = [e for e in edges if not matches(e)]

        if len(edges) == original_count:
            return jsonify({'error': 'Connection not found'}), 404

        _extraction_data['edges'] = edges
        _extraction_data['dirty'] = True

        log_event('mcp_connection_deleted', {'id1': id1, 'id2': id2})

        return jsonify({'success': True})


@mcp_bp.route('/connections/clear', methods=['POST'])
def clear_connections():
    """Remove all connections.

    Returns: {"success": true, "removed_count": int}
    """
    from fish_scale_ui.services.logging import log_event

    _current_image, _extraction_data = get_state_refs()

    edges = _extraction_data.get('edges', [])
    count = len(edges)

    _extraction_data['edges'] = []
    _extraction_data['dirty'] = True if count > 0 else _extraction_data.get('dirty', False)

    log_event('mcp_connections_cleared', {'count': count})

    return jsonify({
        'success': True,
        'removed_count': count,
    })


@mcp_bp.route('/auto-connect', methods=['POST'])
def auto_connect():
    """Auto-generate connections using specified graph method.

    POST body:
        {"method": "delaunay" | "gabriel" | "rng"}

    Returns:
        {"success": true, "n_edges": int, "edges": [...]}
    """
    from fish_scale_ui.services.logging import log_event
    from fish_scale_analysis.core.measurement import (
        filter_to_gabriel,
        filter_to_rng,
    )
    from scipy.spatial import Delaunay
    import numpy as np
    import math

    _current_image, _extraction_data = get_state_refs()
    data = request.get_json() or {}

    method = data.get('method', 'gabriel')
    if method not in ('delaunay', 'gabriel', 'rng'):
        return jsonify({'error': f'Invalid method: {method}. Use delaunay, gabriel, or rng'}), 400

    if not _current_image.get('calibration'):
        return jsonify({'error': 'Calibration not set'}), 400

    um_per_px = _current_image['calibration'].get('um_per_px', 0.33)
    tubercles = _extraction_data.get('tubercles', [])

    if len(tubercles) < 2:
        return jsonify({'error': 'Need at least 2 tubercles for auto-connect'}), 400

    try:
        # Build centroids array
        centroids = np.array([[t['centroid_x'], t['centroid_y']] for t in tubercles])
        radii = np.array([t.get('radius_px', 10) for t in tubercles])

        # Build Delaunay triangulation (need at least 3 points for triangulation)
        if len(tubercles) < 3:
            # With only 2 tubercles, just connect them directly
            edge_indices = [(0, 1)]
        else:
            tri = Delaunay(centroids)

            # Extract all Delaunay edges first
            delaunay_edges = set()
            for simplex in tri.simplices:
                for i in range(3):
                    edge = tuple(sorted([simplex[i], simplex[(i + 1) % 3]]))
                    delaunay_edges.add(edge)

            # Filter based on method
            if method == 'delaunay':
                edge_indices = list(delaunay_edges)
            elif method == 'gabriel':
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

        _extraction_data['edges'] = edges
        _extraction_data['dirty'] = True

        # Update statistics including hexagonalness
        tubercles = _extraction_data.get('tubercles', [])
        if edges:
            edge_distances = [e['edge_distance_um'] for e in edges]
            _extraction_data['statistics']['n_edges'] = len(edges)
            _extraction_data['statistics']['mean_space_um'] = np.mean(edge_distances)
            _extraction_data['statistics']['std_space_um'] = np.std(edge_distances)

        # Recalculate hexagonalness after connection changes
        hex_metrics = _calculate_hexagonalness_from_dicts(tubercles, edges)
        _extraction_data['statistics'].update(hex_metrics)

        log_event('mcp_auto_connect', {
            'method': method,
            'n_edges': len(edges),
            'hexagonalness_score': hex_metrics.get('hexagonalness_score'),
            'reliability': hex_metrics.get('reliability'),
        })

        return jsonify({
            'success': True,
            'n_edges': len(edges),
            'edges': edges,
        })

    except Exception as e:
        return jsonify({'error': f'Auto-connect failed: {str(e)}'}), 500


@mcp_bp.route('/calibration', methods=['GET', 'POST'])
def handle_calibration():
    """Get or set calibration.

    GET returns current calibration.

    POST body:
        {"um_per_px": float}
        or
        {"scale_um": float, "scale_px": float}

    Returns:
        {"success": true, "calibration": {"um_per_px": float, "method": str}}
    """
    from fish_scale_ui.services.logging import log_event

    _current_image, _extraction_data = get_state_refs()

    if request.method == 'GET':
        return jsonify({
            'calibration': _current_image.get('calibration'),
        })

    data = request.get_json() or {}

    if 'um_per_px' in data:
        _current_image['calibration'] = {
            'um_per_px': float(data['um_per_px']),
            'method': data.get('method', 'manual'),
        }
    elif 'scale_um' in data and 'scale_px' in data:
        um_per_px = float(data['scale_um']) / float(data['scale_px'])
        _current_image['calibration'] = {
            'um_per_px': um_per_px,
            'method': 'scale_bar',
        }
    else:
        return jsonify({'error': 'Provide um_per_px or scale_um and scale_px'}), 400

    log_event('mcp_calibration_set', _current_image['calibration'])

    return jsonify({
        'success': True,
        'calibration': _current_image['calibration'],
    })


@mcp_bp.route('/save', methods=['POST'])
def save_slo():
    """Save current state to SLO file.

    Returns:
        {"success": true, "files": {"slo": str, "tub_csv": str, "itc_csv": str}}
    """
    from fish_scale_ui.services.logging import log_event
    from fish_scale_ui.services.persistence import save_slo as persist_slo

    _current_image, _extraction_data = get_state_refs()

    if not _current_image.get('filename'):
        return jsonify({'error': 'No image loaded'}), 400

    tubercles = _extraction_data.get('tubercles', [])
    edges = _extraction_data.get('edges', [])

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
            statistics=_extraction_data.get('statistics', {}),
            parameters=_extraction_data.get('parameters', {}),
        )

        if result['success']:
            _current_image['slo_saved'] = True
            _extraction_data['dirty'] = False

            log_event('mcp_slo_saved', {
                'filename': _current_image['filename'],
                'n_tubercles': len(tubercles),
                'n_edges': len(edges),
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': f'Save failed: {str(e)}'}), 500


@mcp_bp.route('/load-image', methods=['POST'])
def load_image():
    """Load an image file for processing.

    POST body:
        {"path": str}  # Path to image file

    Returns:
        {"success": true, "filename": str, "width": int, "height": int}
    """
    from fish_scale_ui.services.logging import log_event
    from fish_scale_ui.services.recent_images import add_recent_image, init_recent_images
    from fish_scale_ui.routes.api import convert_to_web_format
    from PIL import Image
    import shutil
    import uuid

    _current_image, _extraction_data = get_state_refs()
    data = request.get_json() or {}

    image_path = data.get('path')
    if not image_path:
        return jsonify({'error': 'Path required'}), 400

    image_path = Path(image_path)
    if not image_path.exists():
        return jsonify({'error': f'File not found: {image_path}'}), 404

    try:
        # Copy to uploads folder
        ext = image_path.suffix.lower().lstrip('.')
        unique_id = uuid.uuid4().hex
        unique_name = f"{unique_id}.{ext}"
        save_path = current_app.config['UPLOAD_FOLDER'] / unique_name
        shutil.copy2(image_path, save_path)

        # Convert to web-displayable format if needed
        web_path = convert_to_web_format(save_path, save_path)
        web_name = web_path.name

        with Image.open(web_path) as img:
            width, height = img.size

        # Update state
        _current_image['path'] = str(save_path)
        _current_image['web_path'] = str(web_path)
        _current_image['filename'] = image_path.name
        _current_image['rotation'] = 0
        _current_image['calibration'] = None
        _current_image['slo_saved'] = False

        # Clear extraction data
        _extraction_data['tubercles'] = []
        _extraction_data['edges'] = []
        _extraction_data['statistics'] = {}
        _extraction_data['parameters'] = {}
        _extraction_data['dirty'] = False

        # Add to recent images
        init_recent_images(current_app.config['APP_ROOT'])
        add_recent_image(str(image_path), image_path.name)

        log_event('mcp_image_loaded', {
            'filename': image_path.name,
            'width': width,
            'height': height,
        })

        return jsonify({
            'success': True,
            'filename': image_path.name,
            'width': width,
            'height': height,
        })

    except Exception as e:
        return jsonify({'error': f'Failed to load image: {str(e)}'}), 500


@mcp_bp.route('/debug-shapes', methods=['GET', 'POST', 'DELETE'])
def handle_debug_shapes():
    """Manage debug shapes (rectangles, markers) for visualization.

    GET returns current debug shapes.

    POST (add):
        {
            "type": "rectangle",
            "x": float,
            "y": float,
            "width": float,
            "height": float,
            "label": str (optional),
            "color": str (optional, default: "magenta")
        }
        Returns: {"success": true, "shape": {...}, "id": int}

    DELETE:
        {"id": int} - delete specific shape
        {} - delete all shapes
        Returns: {"success": true}
    """
    from fish_scale_ui.services.logging import log_event

    _current_image, _extraction_data = get_state_refs()

    # Initialize debug_shapes if not present
    if 'debug_shapes' not in _extraction_data:
        _extraction_data['debug_shapes'] = []

    shapes = _extraction_data['debug_shapes']

    if request.method == 'GET':
        return jsonify({
            'success': True,
            'shapes': shapes,
        })

    elif request.method == 'POST':
        data = request.get_json() or {}
        shape_type = data.get('type', 'rectangle')

        if shape_type == 'rectangle':
            x = data.get('x')
            y = data.get('y')
            width = data.get('width')
            height = data.get('height')

            if any(v is None for v in [x, y, width, height]):
                return jsonify({'error': 'x, y, width, height required for rectangle'}), 400

            new_id = max((s.get('id', 0) for s in shapes), default=0) + 1

            shape = {
                'id': new_id,
                'type': 'rectangle',
                'x': float(x),
                'y': float(y),
                'width': float(width),
                'height': float(height),
                'label': data.get('label', ''),
                'color': data.get('color', 'magenta'),
            }

            shapes.append(shape)
            log_event('mcp_debug_shape_added', shape)

            return jsonify({
                'success': True,
                'shape': shape,
                'id': new_id,
            })
        else:
            return jsonify({'error': f'Unknown shape type: {shape_type}'}), 400

    elif request.method == 'DELETE':
        data = request.get_json() or {}
        shape_id = data.get('id')

        if shape_id is not None:
            # Delete specific shape
            original_count = len(shapes)
            _extraction_data['debug_shapes'] = [s for s in shapes if s.get('id') != shape_id]
            if len(_extraction_data['debug_shapes']) == original_count:
                return jsonify({'error': f'Shape {shape_id} not found'}), 404
            log_event('mcp_debug_shape_deleted', {'id': shape_id})
        else:
            # Delete all shapes
            _extraction_data['debug_shapes'] = []
            log_event('mcp_debug_shapes_cleared', {'count': len(shapes)})

        return jsonify({'success': True})


@mcp_bp.route('/statistics', methods=['GET'])
def get_statistics():
    """Get current statistics including hexagonalness metrics.

    Returns:
        {
            "n_tubercles": int,
            "n_edges": int,
            "mean_diameter_um": float,
            "std_diameter_um": float,
            "mean_space_um": float,
            "std_space_um": float,
            "suggested_genus": str,
            "classification_confidence": str,
            "hexagonalness_score": float (0-1, 1=perfect hex),
            "spacing_uniformity": float (0-1),
            "degree_score": float (0-1),
            "mean_degree": float,
            "spacing_cv": float
        }
    """
    import numpy as np
    from collections import defaultdict
    from fish_scale_analysis.models import GENUS_REFERENCE_RANGES

    _current_image, _extraction_data = get_state_refs()

    tubercles = _extraction_data.get('tubercles', [])
    edges = _extraction_data.get('edges', [])

    stats = {
        'n_tubercles': len(tubercles),
        'n_edges': len(edges),
    }

    if tubercles:
        diameters = [t.get('diameter_um', 0) for t in tubercles]
        stats['mean_diameter_um'] = float(np.mean(diameters))
        stats['std_diameter_um'] = float(np.std(diameters))

    if edges:
        spacings = [e.get('edge_distance_um', 0) for e in edges]
        stats['mean_space_um'] = float(np.mean(spacings))
        stats['std_space_um'] = float(np.std(spacings))

    # Classification
    if stats.get('mean_diameter_um') and stats.get('mean_space_um'):
        mean_d = stats['mean_diameter_um']
        mean_s = stats['mean_space_um']

        best_genus = None
        best_score = float('inf')

        for genus, ranges in GENUS_REFERENCE_RANGES.items():
            d_mid = (ranges['diameter_min'] + ranges['diameter_max']) / 2
            s_mid = (ranges['space_min'] + ranges['space_max']) / 2
            score = abs(mean_d - d_mid) + abs(mean_s - s_mid)
            if score < best_score:
                best_score = score
                best_genus = genus

        stats['suggested_genus'] = best_genus
        stats['classification_confidence'] = 'high' if best_score < 2 else 'medium' if best_score < 4 else 'low'

    # Calculate hexagonalness metrics
    hex_metrics = _calculate_hexagonalness_from_dicts(tubercles, edges)
    stats.update(hex_metrics)

    # Update stored statistics
    _extraction_data['statistics'] = stats

    return jsonify(stats)


def _calculate_hexagonalness_from_dicts(
    tubercles: list,
    edges: list,
    min_nodes_for_reliable: int = 15,
) -> dict:
    """
    Calculate hexagonalness metrics from dict representations.

    This is a standalone version that works with the dict format used in the API,
    mirroring the logic in fish_scale_analysis.core.measurement.calculate_hexagonalness.
    """
    import numpy as np
    from collections import defaultdict

    result = {
        'hexagonalness_score': 0.0,
        'spacing_uniformity': 0.0,
        'degree_score': 0.0,
        'edge_ratio_score': 0.0,
        'mean_degree': 0.0,
        'degree_histogram': {},
        'spacing_cv': 1.0,
        'reliability': 'none',
        'n_nodes': 0,
    }

    if not tubercles or len(tubercles) < 4:
        return result

    n_nodes = len(tubercles)
    result['n_nodes'] = n_nodes
    result['reliability'] = 'high' if n_nodes >= min_nodes_for_reliable else 'low'

    # 1. Spacing uniformity (coefficient of variation)
    if edges:
        spacings = [e.get('edge_distance_um', 0) for e in edges if e.get('edge_distance_um', 0) > 0]
        if spacings:
            mean_spacing = np.mean(spacings)
            std_spacing = np.std(spacings)
            cv = std_spacing / mean_spacing if mean_spacing > 0 else 1.0
            result['spacing_cv'] = float(cv)
            # Score: CV of 0 = perfect (1.0), CV of 0.5+ = poor (0.0)
            result['spacing_uniformity'] = float(max(0, 1 - 2 * cv))

    # 2. Degree distribution (neighbors per node)
    degree = defaultdict(int)
    tubercle_ids = {t.get('id') for t in tubercles}

    for e in edges:
        # Edges can have either 'tubercle_a_id'/'tubercle_b_id' or 'id1'/'id2'
        # Use explicit None check to handle id=0 correctly (0 is falsy)
        a_id = e.get('tubercle_a_id') if e.get('tubercle_a_id') is not None else e.get('id1')
        b_id = e.get('tubercle_b_id') if e.get('tubercle_b_id') is not None else e.get('id2')
        if a_id in tubercle_ids:
            degree[a_id] += 1
        if b_id in tubercle_ids:
            degree[b_id] += 1

    # Include nodes with 0 connections
    for t in tubercles:
        tid = t.get('id')
        if tid not in degree:
            degree[tid] = 0

    degrees = list(degree.values())
    if degrees:
        result['mean_degree'] = float(np.mean(degrees))

        # Build histogram
        histogram = defaultdict(int)
        for d in degrees:
            histogram[d] += 1
        result['degree_histogram'] = dict(histogram)

        # Score: weighted by how close to ideal 5-7 neighbors
        weighted_score = 0
        for d in degrees:
            if 5 <= d <= 7:
                weighted_score += 1.0
            elif d == 4 or d == 8:
                weighted_score += 0.7
            elif d == 3 or d == 9:
                weighted_score += 0.3
            # 0-2 or 10+ get 0

        result['degree_score'] = float(weighted_score / len(degrees))

    # 3. Edge/node ratio (ideal is ~2.5 accounting for edge effects)
    n_nodes = len(tubercles)
    n_edges = len(edges)
    if n_nodes > 0:
        ratio = n_edges / n_nodes
        ideal_ratio = 2.5
        deviation = abs(ratio - ideal_ratio)
        result['edge_ratio_score'] = float(max(0, 1 - deviation / 2))

    # 4. Composite hexagonalness score
    score = (
        0.40 * result['spacing_uniformity'] +
        0.45 * result['degree_score'] +
        0.15 * result['edge_ratio_score']
    )
    result['hexagonalness_score'] = float(score)

    return result
