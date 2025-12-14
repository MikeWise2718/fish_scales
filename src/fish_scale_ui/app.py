"""Flask application factory for Fish Scale Measurement UI."""

import os
from pathlib import Path

from flask import Flask


def create_app(config=None):
    """Create and configure the Flask application."""
    app = Flask(__name__,
                static_folder='static',
                template_folder='templates')

    # Default configuration
    app_root = Path(__file__).parent.parent.parent.parent  # Project root
    app.config.update(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-key-change-in-production'),
        MAX_CONTENT_LENGTH=100 * 1024 * 1024,  # 100MB max upload
        APP_ROOT=app_root,
        UPLOAD_FOLDER=Path(__file__).parent / 'uploads',
        ALLOWED_EXTENSIONS={'tif', 'tiff', 'jpeg', 'jpg', 'png'},
        IMAGE_DIR=app_root / 'test_images',  # Default image directory
    )

    if config:
        app.config.update(config)

    # Ensure directories exist
    app.config['UPLOAD_FOLDER'].mkdir(parents=True, exist_ok=True)
    (app.config['APP_ROOT'] / 'log').mkdir(parents=True, exist_ok=True)
    (app.config['APP_ROOT'] / 'slo').mkdir(parents=True, exist_ok=True)

    # Register blueprints
    from fish_scale_ui.routes.main import main_bp
    from fish_scale_ui.routes.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    # Initialize logging service
    from fish_scale_ui.services.logging import init_logging
    init_logging(app)

    return app
