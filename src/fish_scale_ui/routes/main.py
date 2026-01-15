"""Main routes for Fish Scale UI."""

import os
import subprocess
import sys
from pathlib import Path

from flask import Blueprint, render_template, current_app, send_from_directory

main_bp = Blueprint('main', __name__)


def get_version_info():
    """Get version information for About tab."""
    import numpy
    import scipy
    import skimage
    import flask
    from fish_scale_ui import __version__, __version_date__

    # Get git info
    git_hash = 'unknown'
    git_date = 'unknown'
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True, text=True, timeout=5,
            cwd=current_app.config['APP_ROOT']
        )
        if result.returncode == 0:
            git_hash = result.stdout.strip()

        result = subprocess.run(
            ['git', 'log', '-1', '--format=%ci'],
            capture_output=True, text=True, timeout=5,
            cwd=current_app.config['APP_ROOT']
        )
        if result.returncode == 0:
            git_date = result.stdout.strip()[:10]  # Just the date part
    except Exception:
        pass

    return {
        'app_version': __version__,
        'app_version_date': __version_date__,
        'python_version': sys.version.split()[0],
        'numpy_version': numpy.__version__,
        'scipy_version': scipy.__version__,
        'skimage_version': skimage.__version__,
        'flask_version': flask.__version__,
        'git_hash': git_hash,
        'git_date': git_date,
    }


@main_bp.route('/')
def index():
    """Render the image loading screen."""
    from fish_scale_ui.services.recent_images import get_recent_images, init_recent_images
    init_recent_images(current_app.config['APP_ROOT'])
    recent = get_recent_images()
    return render_template('index.html', recent_images=recent)


@main_bp.route('/workspace')
def workspace():
    """Render the main workspace view."""
    version_info = get_version_info()
    return render_template('workspace.html', version_info=version_info)


@main_bp.route('/uploads/<path:filename>')
def serve_upload(filename):
    """Serve uploaded images."""
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)
