"""Core recording engine for capturing mouse and keyboard actions."""

import os
import threading
import time
from collections import deque
from typing import Callable, List, Optional, Set

from pynput import mouse, keyboard

from config import (
    DEFAULT_MOUSE_THROTTLE_PX, DEFAULT_SCREENSHOT_INTERVAL_MS, SCREENSHOTS_DIR
)
from core.action_types import ActionEvent, ActionType, ScreenRegion
from core.screen_capture import ScreenCapture
from utils.logging_config import get_logger

logger = get_logger("recorder")


class ActionRecorder:
    """Captures mouse and keyboard events within a defined ScreenRegion.

    Uses pynput listeners in daemon threads.
    Events outside the region are filtered out.
    Supports pause/resume with marker events.
    """

    def __init__(self, region: ScreenRegion,
                 mouse_throttle_px: int = DEFAULT_MOUSE_THROTTLE_PX,
                 screenshot_interval_ms: int = DEFAULT_SCREENSHOT_INTERVAL_MS,
                 record_mouse_moves: bool = True,
                 session_id: int = 0,
                 on_event: Optional[Callable[[ActionEvent], None]] = None):
        self._region = region
        self._mouse_throttle_px = mouse_throttle_px
        self._screenshot_interval_ms = screenshot_interval_ms
        self._record_mouse_moves = record_mouse_moves
        self._session_id = session_id
        self._on_event = on_event

        self._events: deque = deque()
        self._recording = False
        self._paused = False
        self._start_time_ns: int = 0

        self._mouse_listener: Optional[mouse.Listener] = None
        self._keyboard_listener: Optional[keyboard.Listener] = None
        self._screenshot_thread: Optional[threading.Thread] = None
        self._stop_screenshot = threading.Event()

        self._last_mouse_x: int = 0
        self._last_mouse_y: int = 0
        self._modifier_state: Set[str] = set()
        self._screen_capture = ScreenCapture()
        self._lock = threading.Lock()

        # Drag detection
        self._mouse_pressed = False
        self._drag_started = False

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def event_count(self) -> int:
        return len(self._events)

    @property
    def elapsed_ms(self) -> int:
        if not self._recording:
            return 0
        return (time.perf_counter_ns() - self._start_time_ns) // 1_000_000

    def start(self):
        """Start recording actions."""
        if self._recording:
            return

        self._events.clear()
        self._recording = True
        self._paused = False
        self._start_time_ns = time.perf_counter_ns()

        # Start mouse listener
        self._mouse_listener = mouse.Listener(
            on_move=self._on_mouse_move,
            on_click=self._on_mouse_click,
            on_scroll=self._on_scroll,
        )
        self._mouse_listener.daemon = True
        self._mouse_listener.start()

        # Start keyboard listener
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._keyboard_listener.daemon = True
        self._keyboard_listener.start()

        # Start screenshot thread
        if self._screenshot_interval_ms > 0:
            self._stop_screenshot.clear()
            self._screenshot_thread = threading.Thread(
                target=self._capture_screenshot_loop, daemon=True
            )
            self._screenshot_thread.start()

        logger.info("Recording started")

    def pause(self):
        """Pause recording (listeners stay active but events are discarded)."""
        if not self._recording or self._paused:
            return
        self._paused = True
        self._add_event(ActionEvent(
            action_type=ActionType.PAUSE_MARKER,
            timestamp_ns=self._elapsed(),
        ))
        logger.info("Recording paused")

    def resume(self):
        """Resume recording."""
        if not self._recording or not self._paused:
            return
        self._paused = False
        self._add_event(ActionEvent(
            action_type=ActionType.RESUME_MARKER,
            timestamp_ns=self._elapsed(),
        ))
        logger.info("Recording resumed")

    def stop(self) -> List[ActionEvent]:
        """Stop recording and return all captured events."""
        if not self._recording:
            return []

        self._recording = False
        self._paused = False

        # Stop listeners
        if self._mouse_listener:
            self._mouse_listener.stop()
            self._mouse_listener = None
        if self._keyboard_listener:
            self._keyboard_listener.stop()
            self._keyboard_listener = None

        # Stop screenshot thread
        self._stop_screenshot.set()
        if self._screenshot_thread:
            self._screenshot_thread.join(timeout=2)
            self._screenshot_thread = None

        events = list(self._events)
        logger.info(f"Recording stopped. {len(events)} events captured")
        return events

    def _elapsed(self) -> int:
        return time.perf_counter_ns() - self._start_time_ns

    def _add_event(self, event: ActionEvent):
        with self._lock:
            self._events.append(event)
        if self._on_event:
            self._on_event(event)

    def _on_mouse_move(self, x: int, y: int):
        if not self._recording or self._paused:
            return
        if not self._record_mouse_moves:
            return
        if not self._region.contains(x, y):
            return

        # Throttle: skip if movement is too small
        dx = abs(x - self._last_mouse_x)
        dy = abs(y - self._last_mouse_y)
        if dx < self._mouse_throttle_px and dy < self._mouse_throttle_px:
            return

        self._last_mouse_x = x
        self._last_mouse_y = y

        rx, ry = self._region.to_relative(x, y)

        # Check for drag
        action_type = ActionType.MOUSE_MOVE
        if self._mouse_pressed and not self._drag_started:
            self._drag_started = True
            action_type = ActionType.MOUSE_DRAG_START

        self._add_event(ActionEvent(
            action_type=action_type,
            timestamp_ns=self._elapsed(),
            x=x, y=y,
            region_x=rx, region_y=ry,
            modifiers=list(self._modifier_state),
        ))

    def _on_mouse_click(self, x: int, y: int, button, pressed: bool):
        if not self._recording or self._paused:
            return
        if not self._region.contains(x, y):
            return

        rx, ry = self._region.to_relative(x, y)
        button_name = button.name if hasattr(button, "name") else str(button)

        if pressed:
            self._mouse_pressed = True
            self._drag_started = False
            action_type = ActionType.MOUSE_CLICK
        else:
            if self._drag_started:
                action_type = ActionType.MOUSE_DRAG_END
            else:
                # Release without drag - this is the actual click completion
                # The press was already recorded, so just record the release
                action_type = ActionType.MOUSE_CLICK
            self._mouse_pressed = False
            self._drag_started = False

        self._add_event(ActionEvent(
            action_type=action_type,
            timestamp_ns=self._elapsed(),
            x=x, y=y,
            region_x=rx, region_y=ry,
            button=button_name,
            modifiers=list(self._modifier_state),
            metadata={"pressed": pressed},
        ))

    def _on_scroll(self, x: int, y: int, dx: int, dy: int):
        if not self._recording or self._paused:
            return
        if not self._region.contains(x, y):
            return

        rx, ry = self._region.to_relative(x, y)

        self._add_event(ActionEvent(
            action_type=ActionType.MOUSE_SCROLL,
            timestamp_ns=self._elapsed(),
            x=x, y=y,
            region_x=rx, region_y=ry,
            scroll_dx=dx, scroll_dy=dy,
            modifiers=list(self._modifier_state),
        ))

    def _on_key_press(self, key):
        if not self._recording or self._paused:
            return

        key_name, key_char = self._parse_key(key)

        # Track modifier state
        if key_name in ("ctrl_l", "ctrl_r", "ctrl"):
            self._modifier_state.add("ctrl")
        elif key_name in ("shift", "shift_l", "shift_r"):
            self._modifier_state.add("shift")
        elif key_name in ("alt_l", "alt_r", "alt", "alt_gr"):
            self._modifier_state.add("alt")
        elif key_name in ("cmd", "cmd_l", "cmd_r"):
            self._modifier_state.add("cmd")

        # Detect key combos (modifier + key)
        action_type = ActionType.KEY_PRESS
        if self._modifier_state and key_name not in (
            "ctrl_l", "ctrl_r", "ctrl", "shift", "shift_l", "shift_r",
            "alt_l", "alt_r", "alt", "alt_gr", "cmd", "cmd_l", "cmd_r"
        ):
            action_type = ActionType.KEY_COMBO

        self._add_event(ActionEvent(
            action_type=action_type,
            timestamp_ns=self._elapsed(),
            key=key_name,
            key_char=key_char,
            modifiers=list(self._modifier_state),
        ))

    def _on_key_release(self, key):
        if not self._recording or self._paused:
            return

        key_name, key_char = self._parse_key(key)

        # Update modifier state
        if key_name in ("ctrl_l", "ctrl_r", "ctrl"):
            self._modifier_state.discard("ctrl")
        elif key_name in ("shift", "shift_l", "shift_r"):
            self._modifier_state.discard("shift")
        elif key_name in ("alt_l", "alt_r", "alt", "alt_gr"):
            self._modifier_state.discard("alt")
        elif key_name in ("cmd", "cmd_l", "cmd_r"):
            self._modifier_state.discard("cmd")

        self._add_event(ActionEvent(
            action_type=ActionType.KEY_RELEASE,
            timestamp_ns=self._elapsed(),
            key=key_name,
            key_char=key_char,
            modifiers=list(self._modifier_state),
        ))

    def _parse_key(self, key) -> tuple:
        """Parse a pynput key into (key_name, key_char)."""
        try:
            # Character key
            key_char = key.char
            key_name = key.char
            return (key_name, key_char)
        except AttributeError:
            # Special key
            key_name = key.name if hasattr(key, "name") else str(key)
            return (key_name, None)

    def _capture_screenshot_loop(self):
        """Periodically capture screenshots of the recording region."""
        session_dir = os.path.join(SCREENSHOTS_DIR, str(self._session_id))

        while not self._stop_screenshot.wait(self._screenshot_interval_ms / 1000.0):
            if not self._recording or self._paused:
                continue

            try:
                img = self._screen_capture.capture_region(self._region)
                path = self._screen_capture.save_screenshot(img, session_dir)
                self._add_event(ActionEvent(
                    action_type=ActionType.SCREENSHOT,
                    timestamp_ns=self._elapsed(),
                    screenshot_path=path,
                ))
            except Exception as e:
                logger.error(f"Screenshot capture error: {e}")
