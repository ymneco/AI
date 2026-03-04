"""Action replay engine for ActionRecorder Pro."""

import threading
import time
from enum import Enum, auto
from typing import Callable, List, Optional

import pyautogui

from core.action_types import ActionEvent, ActionType, ScreenRegion
from core.timing import PrecisionTimer
from utils.coordinate_transform import remap_coordinates
from utils.logging_config import get_logger

logger = get_logger("replayer")

# Configure pyautogui
pyautogui.FAILSAFE = True  # Move mouse to corner to abort


class ReplayState(Enum):
    IDLE = auto()
    PLAYING = auto()
    PAUSED = auto()
    STOPPED = auto()


class ActionReplayer:
    """Replays recorded action sequences with precise timing.

    Supports speed adjustment, coordinate remapping, and pause/resume.
    """

    def __init__(self, events: List[ActionEvent],
                 source_region: Optional[ScreenRegion] = None,
                 target_region: Optional[ScreenRegion] = None,
                 speed: float = 1.0,
                 on_progress: Optional[Callable[[int, int], None]] = None,
                 on_complete: Optional[Callable[[], None]] = None):
        self._events = events
        self._source_region = source_region
        self._target_region = target_region or source_region
        self._speed = max(0.1, min(10.0, speed))
        self._on_progress = on_progress
        self._on_complete = on_complete

        self._state = ReplayState.IDLE
        self._timer = PrecisionTimer()
        self._current_index = 0
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused initially

        # Remove pause gaps from timing
        self._adjusted_events = self._remove_pause_gaps(events)

    def play(self):
        """Play the recording (blocking - run in a thread)."""
        if self._state == ReplayState.PLAYING:
            return

        self._state = ReplayState.PLAYING
        self._timer.start()

        # Set pyautogui to no delay
        original_pause = pyautogui.PAUSE
        pyautogui.PAUSE = 0

        total = len(self._adjusted_events)
        logger.info(f"Replay started: {total} events at {self._speed}x speed")

        try:
            for i, event in enumerate(self._adjusted_events):
                if self._state == ReplayState.STOPPED:
                    break

                # Handle pause
                self._pause_event.wait()
                if self._state == ReplayState.STOPPED:
                    break

                self._current_index = i

                # Wait until the right time
                target_time_ns = int(event.timestamp_ns / self._speed)
                self._wait_until(target_time_ns)

                if self._state == ReplayState.STOPPED:
                    break

                # Execute the action
                self._execute_action(event)

                # Report progress
                if self._on_progress and i % 10 == 0:
                    self._on_progress(i + 1, total)

        except pyautogui.FailSafeException:
            logger.warning("Replay aborted: failsafe triggered (mouse moved to corner)")
        except Exception as e:
            logger.error(f"Replay error: {e}")
        finally:
            pyautogui.PAUSE = original_pause
            self._timer.cleanup()
            self._state = ReplayState.IDLE
            logger.info("Replay finished")
            if self._on_complete:
                self._on_complete()

    def pause(self):
        if self._state == ReplayState.PLAYING:
            self._state = ReplayState.PAUSED
            self._pause_event.clear()

    def resume(self):
        if self._state == ReplayState.PAUSED:
            self._state = ReplayState.PLAYING
            self._pause_event.set()

    def stop(self):
        self._state = ReplayState.STOPPED
        self._pause_event.set()  # Unblock if paused

    def set_speed(self, speed: float):
        self._speed = max(0.1, min(10.0, speed))

    def _wait_until(self, target_ns: int):
        """Wait until the timer reaches target_ns."""
        self._timer.wait_until_ns(target_ns)

    def _execute_action(self, event: ActionEvent):
        """Execute a single action event."""
        # Skip markers and screenshots
        if event.action_type in (
            ActionType.PAUSE_MARKER, ActionType.RESUME_MARKER, ActionType.SCREENSHOT
        ):
            return

        # Get coordinates
        x, y = self._get_target_coords(event)

        try:
            if event.action_type == ActionType.MOUSE_MOVE:
                if x is not None and y is not None:
                    pyautogui.moveTo(x, y, _pause=False)

            elif event.action_type == ActionType.MOUSE_CLICK:
                if x is not None and y is not None:
                    button = event.button or "left"
                    pressed = event.metadata.get("pressed", True)
                    if pressed:
                        pyautogui.mouseDown(x, y, button=button, _pause=False)
                    else:
                        pyautogui.mouseUp(x, y, button=button, _pause=False)

            elif event.action_type == ActionType.MOUSE_DOUBLE_CLICK:
                if x is not None and y is not None:
                    button = event.button or "left"
                    pyautogui.doubleClick(x, y, button=button, _pause=False)

            elif event.action_type == ActionType.MOUSE_SCROLL:
                if x is not None and y is not None:
                    pyautogui.scroll(event.scroll_dy, x=x, y=y, _pause=False)

            elif event.action_type == ActionType.MOUSE_DRAG_START:
                if x is not None and y is not None:
                    pyautogui.moveTo(x, y, _pause=False)
                    pyautogui.mouseDown(_pause=False)

            elif event.action_type == ActionType.MOUSE_DRAG_END:
                if x is not None and y is not None:
                    pyautogui.moveTo(x, y, _pause=False)
                    pyautogui.mouseUp(_pause=False)

            elif event.action_type == ActionType.KEY_PRESS:
                if event.key:
                    key = self._normalize_key(event.key)
                    pyautogui.keyDown(key, _pause=False)

            elif event.action_type == ActionType.KEY_RELEASE:
                if event.key:
                    key = self._normalize_key(event.key)
                    pyautogui.keyUp(key, _pause=False)

            elif event.action_type == ActionType.KEY_COMBO:
                if event.key and event.modifiers:
                    keys = [self._normalize_key(m) for m in event.modifiers]
                    keys.append(self._normalize_key(event.key))
                    pyautogui.hotkey(*keys, _pause=False)

        except Exception as e:
            logger.warning(f"Action execution failed: {event.action_type.name}: {e}")

    def _get_target_coords(self, event: ActionEvent) -> tuple:
        """Get target coordinates, remapping if regions differ."""
        if event.x is None or event.y is None:
            return (None, None)

        if (self._source_region and self._target_region and
                self._source_region != self._target_region):
            return remap_coordinates(
                event.x, event.y,
                self._source_region, self._target_region
            )
        return (event.x, event.y)

    def _normalize_key(self, key: str) -> str:
        """Normalize key names for pyautogui."""
        key_map = {
            "ctrl_l": "ctrl", "ctrl_r": "ctrl",
            "shift_l": "shift", "shift_r": "shift",
            "alt_l": "alt", "alt_r": "alt",
            "cmd_l": "win", "cmd_r": "win", "cmd": "win",
            "return": "enter",
            "escape": "esc",
            "backspace": "backspace",
            "space": "space",
        }
        return key_map.get(key.lower(), key)

    def _remove_pause_gaps(self, events: List[ActionEvent]) -> List[ActionEvent]:
        """Remove time gaps caused by pause/resume from event timestamps."""
        adjusted = []
        pause_offset_ns = 0
        pause_start_ns = 0
        in_pause = False

        for event in events:
            if event.action_type == ActionType.PAUSE_MARKER:
                in_pause = True
                pause_start_ns = event.timestamp_ns
                continue
            elif event.action_type == ActionType.RESUME_MARKER:
                if in_pause:
                    pause_offset_ns += event.timestamp_ns - pause_start_ns
                    in_pause = False
                continue

            if in_pause:
                continue

            # Create adjusted copy
            adjusted_event = ActionEvent(
                action_type=event.action_type,
                timestamp_ns=event.timestamp_ns - pause_offset_ns,
                x=event.x, y=event.y,
                region_x=event.region_x, region_y=event.region_y,
                button=event.button,
                key=event.key, key_char=event.key_char,
                scroll_dx=event.scroll_dx, scroll_dy=event.scroll_dy,
                modifiers=event.modifiers,
                screenshot_path=event.screenshot_path,
                metadata=event.metadata,
            )
            adjusted.append(adjusted_event)

        return adjusted
