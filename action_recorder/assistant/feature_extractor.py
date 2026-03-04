"""Feature extraction from raw action events for pattern matching."""

from typing import List

from config import SPATIAL_GRID_SIZE
from core.action_types import ActionEvent, ActionType, ScreenRegion
from utils.logging_config import get_logger

logger = get_logger("feature_extractor")


class FeatureExtractor:
    """Transforms raw ActionEvent sequences into symbolic tokens for pattern matching.

    Each action is converted to a string token:
    - MOUSE_CLICK at grid cell (r,c) -> "MC_r_c"
    - KEY_COMBO Ctrl+C -> "KC_ctrl+c"
    - KEY_PRESS 'a' -> "KP_a"
    - MOUSE_MOVE -> "MM" (collapsed, not pattern-significant)
    - MOUSE_SCROLL -> "MS"
    - MOUSE_DRAG_START -> "MDS"
    - MOUSE_DRAG_END -> "MDE"
    """

    def __init__(self, region: ScreenRegion = None, grid_size: int = SPATIAL_GRID_SIZE):
        self._region = region
        self._grid_size = grid_size

    def set_region(self, region: ScreenRegion):
        self._region = region

    def symbolize(self, event: ActionEvent) -> str:
        """Convert a single event to a symbol token."""
        at = event.action_type

        if at == ActionType.MOUSE_CLICK:
            cell = self._get_grid_cell(event.region_x, event.region_y)
            pressed = event.metadata.get("pressed", True)
            if pressed:
                return f"MC_{cell}"
            else:
                return f"MR_{cell}"  # mouse release

        elif at == ActionType.MOUSE_DOUBLE_CLICK:
            cell = self._get_grid_cell(event.region_x, event.region_y)
            return f"MDC_{cell}"

        elif at == ActionType.MOUSE_SCROLL:
            direction = "up" if event.scroll_dy > 0 else "down"
            return f"MS_{direction}"

        elif at == ActionType.MOUSE_DRAG_START:
            cell = self._get_grid_cell(event.region_x, event.region_y)
            return f"MDS_{cell}"

        elif at == ActionType.MOUSE_DRAG_END:
            cell = self._get_grid_cell(event.region_x, event.region_y)
            return f"MDE_{cell}"

        elif at == ActionType.KEY_COMBO:
            mods = "+".join(sorted(event.modifiers))
            key = event.key or ""
            return f"KC_{mods}+{key}"

        elif at == ActionType.KEY_PRESS:
            key = event.key_char or event.key or "?"
            return f"KP_{key}"

        elif at == ActionType.KEY_RELEASE:
            return ""  # Skip releases in symbolization

        elif at == ActionType.MOUSE_MOVE:
            return "MM"

        elif at == ActionType.SCREENSHOT:
            return ""  # Skip screenshots

        elif at in (ActionType.PAUSE_MARKER, ActionType.RESUME_MARKER):
            return ""  # Skip markers

        return f"UNK_{at.name}"

    def symbolize_sequence(self, events: List[ActionEvent],
                           skip_moves: bool = True,
                           skip_releases: bool = True) -> List[str]:
        """Convert a sequence of events to symbol tokens.

        Filters out empty tokens and optionally mouse moves and key releases.
        """
        symbols = []
        prev_symbol = ""

        for event in events:
            if skip_moves and event.action_type == ActionType.MOUSE_MOVE:
                continue
            if skip_releases and event.action_type == ActionType.KEY_RELEASE:
                continue

            symbol = self.symbolize(event)
            if not symbol:
                continue

            # Collapse consecutive identical symbols
            if symbol == prev_symbol and symbol == "MM":
                continue

            symbols.append(symbol)
            prev_symbol = symbol

        return symbols

    def _get_grid_cell(self, rx: int, ry: int) -> str:
        """Map region-relative coordinates to a grid cell identifier."""
        if rx is None or ry is None or self._region is None:
            return "0_0"

        if self._region.width <= 0 or self._region.height <= 0:
            return "0_0"

        col = min(self._grid_size - 1,
                  max(0, int(rx / self._region.width * self._grid_size)))
        row = min(self._grid_size - 1,
                  max(0, int(ry / self._region.height * self._grid_size)))

        return f"{row}_{col}"
