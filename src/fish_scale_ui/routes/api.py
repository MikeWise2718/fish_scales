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


@api_bp.route('/log', methods=['GET'])
def get_log():
    """Get current session log entries."""
    from fish_scale_ui.services.logging import get_log_entries
    return jsonify({'entries': get_log_entries()})


@api_bp.route('/current-image', methods=['GET'])
def get_current_image():
    """Get current image info."""
    if not _current_image['path']:
        return jsonify({'loaded': False})

    return jsonify({
        'loaded': True,
        'filename': _current_image['filename'],
        'rotation': _current_image['rotation'],
        'calibration': _current_image['calibration']
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
