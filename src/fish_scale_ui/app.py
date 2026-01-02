"""Flask application factory for Fish Scale Measurement UI."""

import os
from pathlib import Path

from flask import Flask


def get_agent_tabs_config():
    """Determine which agent tabs to show.

    Environment variable FISH_SCALE_AGENT_TABS controls visibility:
    - Not set or empty: all agent tabs hidden
    - '1', 'true', 'yes': all agent tabs shown
    - Comma-separated list: show specified tabs (e.g., 'extraction,editing')

    Returns:
        dict: {'extraction': bool, 'editing': bool}
    """
    value = os.environ.get('FISH_SCALE_AGENT_TABS', '').lower()
    if not value:
        return {'extraction': False, 'editing': False}
    if value in ('1', 'true', 'yes'):
        return {'extraction': True, 'editing': True}
    tabs = [t.strip() for t in value.split(',')]
    return {
        'extraction': 'extraction' in tabs,
        'editing': 'editing' in tabs,
    }


def create_app(config=None):
    """Create and configure the Flask application."""
    app = Flask(__name__,
                static_folder='static',
                template_folder='templates')

    # Default configuration
    app_root = Path(__file__).parent.parent.parent  # Project root (fish_scales/)
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
    (app.config['APP_ROOT'] / 'annotations').mkdir(parents=True, exist_ok=True)

    # Register blueprints
    from fish_scale_ui.routes.main import main_bp
    from fish_scale_ui.routes.api import api_bp
    from fish_scale_ui.routes.mcp_api import mcp_bp  # Tool endpoints for automation
    from fish_scale_ui.routes.agent_api import agent_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(mcp_bp, url_prefix='/api/tools')  # Renamed from /api/mcp
    app.register_blueprint(agent_bp, url_prefix='/api/agent')

    # Initialize logging service
    from fish_scale_ui.services.logging import init_logging
    init_logging(app)

    # Register context processor for agent tabs
    @app.context_processor
    def inject_agent_tabs():
        return {'agent_tabs': get_agent_tabs_config()}

    return app
