import os
import uuid
from pathlib import Path

from config import settings


def generate_session_id() -> str:
    """Generate unique session ID"""
    return str(uuid.uuid4())


def ensure_storage_dirs():
    """Create storage directories if they don't exist"""
    paths = [settings.storage_path, settings.temp_path]
    for path in paths:
        Path(path).mkdir(parents=True, exist_ok=True)


def get_video_path(session_id: str, filename: str) -> str:
    """Get full path for a video file"""
    return os.path.join(settings.storage_path, session_id, filename)


def get_temp_path(filename: str) -> str:
    """Get full path for a temporary file"""
    return os.path.join(settings.temp_path, filename)
