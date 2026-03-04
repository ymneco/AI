"""Core data classes used throughout ActionRecorder Pro."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class ActionType(Enum):
    MOUSE_MOVE = auto()
    MOUSE_CLICK = auto()
    MOUSE_DOUBLE_CLICK = auto()
    MOUSE_SCROLL = auto()
    MOUSE_DRAG_START = auto()
    MOUSE_DRAG_END = auto()
    KEY_PRESS = auto()
    KEY_RELEASE = auto()
    KEY_COMBO = auto()
    SCREENSHOT = auto()
    PAUSE_MARKER = auto()
    RESUME_MARKER = auto()


@dataclass
class ActionEvent:
    action_type: ActionType
    timestamp_ns: int  # relative to recording start (perf_counter_ns)
    x: Optional[int] = None  # absolute screen coordinate
    y: Optional[int] = None
    region_x: Optional[int] = None  # coordinate relative to selected region
    region_y: Optional[int] = None
    button: Optional[str] = None  # 'left', 'right', 'middle'
    key: Optional[str] = None  # key name
    key_char: Optional[str] = None  # printable character
    scroll_dx: int = 0
    scroll_dy: int = 0
    modifiers: list = field(default_factory=list)  # ['ctrl', 'shift', 'alt']
    screenshot_path: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class ScreenRegion:
    left: int
    top: int
    width: int
    height: int
    monitor_index: int = 0
    dpi_scale: float = 1.0

    def contains(self, x: int, y: int) -> bool:
        return (self.left <= x < self.left + self.width and
                self.top <= y < self.top + self.height)

    def to_relative(self, x: int, y: int) -> tuple:
        return (x - self.left, y - self.top)

    def to_absolute(self, rx: int, ry: int) -> tuple:
        return (rx + self.left, ry + self.top)


@dataclass
class RecordingSession:
    session_id: Optional[int] = None
    name: str = ""
    created_at: str = ""
    updated_at: str = ""
    region: Optional[ScreenRegion] = None
    duration_ms: int = 0
    action_count: int = 0
    tags: list = field(default_factory=list)
    notes: str = ""
    is_template: bool = False
    default_speed: float = 1.0
    loop_count: int = 1


@dataclass
class ActionPattern:
    pattern_id: Optional[int] = None
    name: str = ""
    description: str = ""
    symbol_sequence: str = ""
    action_types: list = field(default_factory=list)
    avg_duration_ms: int = 0
    frequency: int = 1
    confidence: float = 0.5
    created_at: str = ""
    updated_at: str = ""
    is_active: bool = True
    user_confirmed: bool = False


@dataclass
class Prediction:
    prediction_id: Optional[int] = None
    pattern: Optional[ActionPattern] = None
    message: str = ""
    remaining_actions: list = field(default_factory=list)
    confidence: float = 0.0
    match_score: float = 0.0
