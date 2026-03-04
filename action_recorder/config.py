"""Global constants and default settings for ActionRecorder Pro."""

import os

# Application
APP_NAME = "ActionRecorder Pro"
APP_VERSION = "1.0.0"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "recordings.db")
SCREENSHOTS_DIR = os.path.join(DATA_DIR, "screenshots")
LOG_DIR = os.path.join(DATA_DIR, "logs")

# Recording defaults
DEFAULT_MOUSE_THROTTLE_PX = 3
DEFAULT_SCREENSHOT_INTERVAL_MS = 2000
DEFAULT_RECORD_MOUSE_MOVES = True

# Replay defaults
DEFAULT_REPLAY_SPEED = 1.0
REPLAY_SPEED_MIN = 0.1
REPLAY_SPEED_MAX = 10.0
BUSY_WAIT_THRESHOLD_NS = 2_000_000  # 2ms

# Timing
USE_HIGH_RES_TIMER = True

# Assistant defaults
DEFAULT_CONFIDENCE_THRESHOLD = 0.7
SLIDING_WINDOW_SIZE = 15
MIN_PATTERN_FREQUENCY = 3
MIN_PATTERN_LENGTH = 3
MAX_PATTERN_LENGTH = 20
SPATIAL_GRID_SIZE = 4  # 4x4 grid for coordinate clustering

# GUI
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
TOAST_DISPLAY_SECONDS = 8
TIMELINE_ZOOM_LEVELS = [0.25, 0.5, 1.0, 2.0, 4.0, 8.0]

# Hotkey defaults
HOTKEY_RECORD = "<F9>"
HOTKEY_PAUSE = "<F10>"
HOTKEY_STOP = "<F11>"
HOTKEY_REPLAY = "<F5>"
HOTKEY_ABORT = "<Escape>"
