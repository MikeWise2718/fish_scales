"""Configuration management for ADW execution logging.

Provides two-stage configuration loading with local settings taking precedence over global:
1. Local: .adw/settings.json (in working directory)
2. Global: ~/.adw/settings.json (in user home directory)

Settings are merged with local values overriding global values.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Literal

# Default settings
DEFAULTS = {
    "verbosity": 1,
    "claude_mode": "default",
}

# Settings file name
SETTINGS_FILENAME = "settings.json"

# Cache for loaded settings
_settings_cache: Optional[Dict[str, Any]] = None


def _get_global_config_path() -> Path:
    """Get path to global config directory (~/.adw/)."""
    return Path.home() / ".adw"


def _get_local_config_path() -> Path:
    """Get path to local config directory (.adw/ in current working directory)."""
    return Path.cwd() / ".adw"


def _load_json_file(path: Path) -> Optional[Dict[str, Any]]:
    """Load JSON file if it exists.

    Args:
        path: Path to JSON file

    Returns:
        Parsed JSON as dict, or None if file doesn't exist or is invalid
    """
    if not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _resolve_path(path_str: str, base_dir: Optional[Path] = None) -> str:
    """Resolve a path string to an absolute path.

    Supports:
    - Absolute paths: /var/log/adw
    - Relative paths: logs/adw (resolved from base_dir or cwd)
    - Home-relative: ~/adw-logs (tilde expansion)

    Args:
        path_str: Path string to resolve
        base_dir: Base directory for relative paths (defaults to cwd)

    Returns:
        Absolute path string
    """
    if not path_str:
        return path_str

    # Expand tilde
    path = Path(os.path.expanduser(path_str))

    # If already absolute, return as-is
    if path.is_absolute():
        return str(path)

    # Resolve relative to base_dir or cwd
    if base_dir:
        return str(base_dir / path)
    else:
        return str(Path.cwd() / path)


def load_adw_settings(force_reload: bool = False) -> Optional[Dict[str, Any]]:
    """Load and merge ADW settings from global and local config files.

    Settings are merged with local values overriding global values.
    Results are cached for performance.

    Args:
        force_reload: If True, bypass cache and reload from files

    Returns:
        Merged settings dict, or None if no config files exist
    """
    global _settings_cache

    if not force_reload and _settings_cache is not None:
        return _settings_cache

    # Load global settings
    global_path = _get_global_config_path() / SETTINGS_FILENAME
    global_settings = _load_json_file(global_path) or {}

    # Load local settings
    local_path = _get_local_config_path() / SETTINGS_FILENAME
    local_settings = _load_json_file(local_path) or {}

    # If neither file exists, return None (logging disabled)
    if not global_settings and not local_settings:
        _settings_cache = None
        return None

    # Merge settings: global as base, local overrides
    merged = {**DEFAULTS, **global_settings, **local_settings}

    _settings_cache = merged
    return merged


def clear_settings_cache() -> None:
    """Clear the settings cache. Useful for testing."""
    global _settings_cache
    _settings_cache = None


def get_logging_directory() -> Optional[str]:
    """Get resolved logging directory path, or None if logging disabled.

    Returns:
        Absolute path to logging directory, or None if not configured
    """
    settings = load_adw_settings()
    if not settings:
        return None

    logging_dir = settings.get("logging_directory")
    if not logging_dir:
        return None

    return _resolve_path(logging_dir)


def get_log_file_path() -> Optional[str]:
    """Get full path to the log file, or None if logging disabled.

    Returns:
        Absolute path to adw_execution.log.jsonl, or None if not configured
    """
    logging_dir = get_logging_directory()
    if not logging_dir:
        return None

    return os.path.join(logging_dir, "adw_execution.log.jsonl")


def get_verbosity() -> int:
    """Get verbosity level (default: 1).

    Levels:
    - 0: Only file counts
    - 1: File names
    - 2: File names, sizes, and diff statistics

    Returns:
        Verbosity level (0, 1, or 2)
    """
    settings = load_adw_settings()
    if not settings:
        return DEFAULTS["verbosity"]

    verbosity = settings.get("verbosity", DEFAULTS["verbosity"])
    # Clamp to valid range
    return max(0, min(2, int(verbosity)))


def get_claude_mode() -> Literal["apikey", "max", "default"]:
    """Get configured Claude mode (default: "default").

    Values:
    - "apikey": Using ANTHROPIC_API_KEY for API access
    - "max": Using Claude Max subscription
    - "default": Auto-detect based on environment

    Returns:
        Claude mode string
    """
    settings = load_adw_settings()
    if not settings:
        return DEFAULTS["claude_mode"]

    mode = settings.get("claude_mode", DEFAULTS["claude_mode"])
    if mode not in ("apikey", "max", "default"):
        return "default"

    return mode


def detect_claude_mode() -> Literal["apikey", "max", "unknown"]:
    """Detect the actual Claude mode based on environment.

    Auto-detection logic:
    1. If ANTHROPIC_API_KEY is set -> "apikey"
    2. Else if Claude Max session detected -> "max"
    3. Else -> "unknown"

    Returns:
        Detected Claude mode
    """
    configured_mode = get_claude_mode()

    # If explicitly configured, return that
    if configured_mode in ("apikey", "max"):
        return configured_mode

    # Auto-detect
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "apikey"

    # Check for Claude Max indicators
    # Claude Max uses ~/.claude/credentials or similar
    claude_credentials = Path.home() / ".claude" / "credentials.json"
    if claude_credentials.exists():
        try:
            with open(claude_credentials, "r") as f:
                creds = json.load(f)
                if creds.get("claudeMax") or creds.get("subscription_type") == "max":
                    return "max"
        except (json.JSONDecodeError, OSError, KeyError):
            pass

    return "unknown"


def is_logging_enabled() -> bool:
    """Check if execution logging is enabled.

    Returns:
        True if logging directory is configured, False otherwise
    """
    return get_logging_directory() is not None


def ensure_logging_directory() -> Optional[str]:
    """Ensure the logging directory exists, creating it if necessary.

    Returns:
        Path to logging directory, or None if logging disabled
    """
    logging_dir = get_logging_directory()
    if not logging_dir:
        return None

    os.makedirs(logging_dir, exist_ok=True)
    return logging_dir
