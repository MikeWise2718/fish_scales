"""User management service for Fish Scale UI.

Handles user identity for history tracking with a priority hierarchy:
1. FISH_SCALE_USER environment variable (highest priority)
2. User config file (~/.fish_scale/config.json)
3. Default value "Mike Wise"
"""

import json
import os
from pathlib import Path
from typing import Optional

# Default user name
DEFAULT_USER = "Mike Wise"

# Config file location
CONFIG_DIR = Path.home() / ".fish_scale"
CONFIG_FILE = CONFIG_DIR / "config.json"


def _ensure_config_dir():
    """Ensure config directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _load_config() -> dict:
    """Load configuration from file."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_config(config: dict):
    """Save configuration to file."""
    _ensure_config_dir()
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)


def get_current_user() -> str:
    """Get the current user name.

    Priority:
    1. FISH_SCALE_USER environment variable
    2. Config file setting
    3. Default value

    Returns:
        The current user name
    """
    # Check environment variable first
    env_user = os.environ.get('FISH_SCALE_USER')
    if env_user:
        return env_user.strip()

    # Check config file
    config = _load_config()
    if config.get('user_name'):
        return config['user_name']

    # Return default
    return DEFAULT_USER


def set_user(user_name: str) -> bool:
    """Set the user name in config file.

    Note: This will NOT override an environment variable setting.
    The environment variable always takes precedence.

    Args:
        user_name: The user name to set

    Returns:
        True if successful
    """
    config = _load_config()
    config['user_name'] = user_name.strip()
    _save_config(config)
    return True


def get_user_source() -> str:
    """Get the source of the current user name.

    Returns:
        One of: 'environment', 'config', 'default'
    """
    if os.environ.get('FISH_SCALE_USER'):
        return 'environment'

    config = _load_config()
    if config.get('user_name'):
        return 'config'

    return 'default'


def is_user_overridable() -> bool:
    """Check if the user can be changed via UI.

    Returns:
        False if set by environment variable, True otherwise
    """
    return not bool(os.environ.get('FISH_SCALE_USER'))
