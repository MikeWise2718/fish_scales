"""Recent images management service."""

import json
from datetime import datetime
from pathlib import Path

MAX_RECENT_IMAGES = 10
_recent_file = None


def init_recent_images(app_root: Path):
    """Initialize recent images service."""
    global _recent_file
    _recent_file = app_root / 'recent_images.json'


def get_recent_images() -> list:
    """Get list of recently opened images."""
    global _recent_file

    if _recent_file is None or not _recent_file.exists():
        return []

    try:
        with open(_recent_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Filter out images that no longer exist
            valid = []
            for item in data:
                if Path(item['path']).exists():
                    valid.append(item)
            return valid[:MAX_RECENT_IMAGES]
    except (json.JSONDecodeError, KeyError):
        return []


def add_recent_image(image_path: str, filename: str):
    """Add an image to the recent images list."""
    global _recent_file

    if _recent_file is None:
        return

    recent = get_recent_images()

    # Remove if already in list
    recent = [r for r in recent if r['path'] != image_path]

    # Add to front
    recent.insert(0, {
        'path': image_path,
        'filename': filename,
        'opened_at': datetime.now().isoformat()
    })

    # Keep only last N
    recent = recent[:MAX_RECENT_IMAGES]

    with open(_recent_file, 'w', encoding='utf-8') as f:
        json.dump(recent, f, indent=2)
