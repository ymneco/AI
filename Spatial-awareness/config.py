"""Spatial Awareness - Global Configuration"""

import os

# Load .env file if present
_env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.isfile(_env_file):
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

# Application
APP_NAME = "Spatial Awareness"
APP_VERSION = "0.1.0"

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
PROJECTS_DIR = os.path.join(DATA_DIR, "projects")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
CACHE_DIR = os.path.join(DATA_DIR, "cache")

# External binaries
COLMAP_BINARY = os.environ.get("COLMAP_PATH", "colmap")
FFMPEG_BINARY = os.environ.get("FFMPEG_PATH", "ffmpeg")

# Frame extraction defaults
DEFAULT_FRAME_FPS = 2.0
DEFAULT_IMAGE_MAX_SIZE = 3200  # px, longest edge

# COLMAP defaults
DEFAULT_SIFT_MAX_FEATURES = 8192
DEFAULT_MATCHER = "exhaustive"  # "exhaustive" or "sequential"

# Database
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{os.path.join(DATA_DIR, 'spatial.db')}",
)
