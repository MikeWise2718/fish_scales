"""JSONL logging service for Fish Scale UI."""

import json
from datetime import datetime
from pathlib import Path
from threading import Lock

_log_file = None
_log_lock = Lock()
_app_root = None


def init_logging(app):
    """Initialize logging for a new session."""
    global _log_file, _app_root
    _app_root = Path(app.config['APP_ROOT'])
    log_dir = _app_root / 'log'
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    _log_file = log_dir / f'{timestamp}.jsonl'

    log_event('application_start', {'version': '0.1.0'})


def log_event(event_type: str, details: dict = None):
    """Log an event to the JSONL file."""
    global _log_file, _log_lock

    if _log_file is None:
        return

    entry = {
        'timestamp': datetime.now().isoformat(),
        'event_type': event_type,
        'details': details or {}
    }

    with _log_lock:
        with open(_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + '\n')


def get_log_entries() -> list:
    """Get all log entries for the current session."""
    global _log_file

    if _log_file is None or not _log_file.exists():
        return []

    entries = []
    with open(_log_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    return entries


def get_log_file_path() -> Path:
    """Get the current log file path."""
    return _log_file
