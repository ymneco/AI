"""Custom Canvas widget for timeline visualization."""

import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Optional

from core.action_types import ActionEvent, ActionType


# Color mapping for action types on timeline
TIMELINE_COLORS = {
    ActionType.MOUSE_MOVE: "#4CAF50",
    ActionType.MOUSE_CLICK: "#2196F3",
    ActionType.MOUSE_DOUBLE_CLICK: "#1565C0",
    ActionType.MOUSE_SCROLL: "#009688",
    ActionType.MOUSE_DRAG_START: "#FF9800",
    ActionType.MOUSE_DRAG_END: "#FF9800",
    ActionType.KEY_PRESS: "#9C27B0",
    ActionType.KEY_RELEASE: "#7B1FA2",
    ActionType.KEY_COMBO: "#F44336",
    ActionType.SCREENSHOT: "#607D8B",
    ActionType.PAUSE_MARKER: "#FFC107",
    ActionType.RESUME_MARKER: "#FFC107",
}


class TimelineCanvas(tk.Canvas):
    """Visual timeline showing action events as colored blocks."""

    def __init__(self, parent, height: int = 80,
                 on_cursor_move: Optional[Callable[[int], None]] = None):
        super().__init__(parent, height=height, bg="#2d2d2d", highlightthickness=0)
        self._events: List[ActionEvent] = []
        self._duration_ns: int = 0
        self._zoom: float = 1.0
        self._scroll_offset: int = 0
        self._cursor_pos: int = 0  # position in nanoseconds
        self._on_cursor_move = on_cursor_move
        self._block_height = 30
        self._header_height = 20

        self.bind("<Configure>", self._on_resize)
        self.bind("<ButtonPress-1>", self._on_click)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<MouseWheel>", self._on_scroll)

    def set_events(self, events: List[ActionEvent]):
        """Load events into the timeline."""
        self._events = events
        if events:
            self._duration_ns = max(e.timestamp_ns for e in events)
        else:
            self._duration_ns = 0
        self._scroll_offset = 0
        self._cursor_pos = 0
        self._render()

    def set_cursor(self, timestamp_ns: int):
        """Move the cursor to a specific timestamp."""
        self._cursor_pos = timestamp_ns
        self._render()

    def set_zoom(self, zoom: float):
        self._zoom = max(0.1, min(20.0, zoom))
        self._render()

    def _on_resize(self, event=None):
        self._render()

    def _on_click(self, event):
        ns = self._x_to_ns(event.x)
        self._cursor_pos = max(0, min(self._duration_ns, ns))
        self._render()
        if self._on_cursor_move:
            self._on_cursor_move(self._cursor_pos)

    def _on_drag(self, event):
        self._on_click(event)

    def _on_scroll(self, event):
        if event.delta > 0:
            self._zoom *= 1.2
        else:
            self._zoom /= 1.2
        self._zoom = max(0.1, min(20.0, self._zoom))
        self._render()

    def _x_to_ns(self, x: int) -> int:
        """Convert canvas x coordinate to nanosecond timestamp."""
        if self._duration_ns <= 0:
            return 0
        width = self.winfo_width()
        visible_ns = self._duration_ns / self._zoom
        return int((x / width) * visible_ns + self._scroll_offset)

    def _ns_to_x(self, ns: int) -> float:
        """Convert nanosecond timestamp to canvas x coordinate."""
        if self._duration_ns <= 0:
            return 0
        width = self.winfo_width()
        visible_ns = self._duration_ns / self._zoom
        return ((ns - self._scroll_offset) / visible_ns) * width

    def _render(self):
        """Redraw the timeline."""
        self.delete("all")
        width = self.winfo_width()
        height = self.winfo_height()

        if not self._events or self._duration_ns <= 0:
            self.create_text(
                width // 2, height // 2,
                text="No events loaded", fill="#888", font=("Segoe UI", 10)
            )
            return

        # Draw time axis
        self._draw_time_axis(width)

        # Draw action blocks
        block_y = self._header_height + 5
        for event in self._events:
            x = self._ns_to_x(event.timestamp_ns)
            if x < -5 or x > width + 5:
                continue

            color = TIMELINE_COLORS.get(event.action_type, "#666")
            block_w = max(3, 6 / self._zoom)

            self.create_rectangle(
                x, block_y, x + block_w, block_y + self._block_height,
                fill=color, outline="", tags="event"
            )

        # Draw cursor
        cursor_x = self._ns_to_x(self._cursor_pos)
        self.create_line(
            cursor_x, 0, cursor_x, height,
            fill="#FF5722", width=2, tags="cursor"
        )

        # Draw cursor time label
        cursor_ms = self._cursor_pos // 1_000_000
        cursor_s = cursor_ms // 1000
        cursor_min = cursor_s // 60
        cursor_sec = cursor_s % 60
        cursor_mil = cursor_ms % 1000
        time_str = f"{cursor_min}:{cursor_sec:02d}.{cursor_mil:03d}"
        self.create_text(
            cursor_x + 5, 5,
            text=time_str, fill="#FF5722", anchor=tk.NW,
            font=("Segoe UI", 8)
        )

    def _draw_time_axis(self, width: int):
        """Draw time markings along the top."""
        visible_ns = self._duration_ns / self._zoom
        if visible_ns <= 0:
            return

        # Choose appropriate time interval
        total_s = visible_ns / 1_000_000_000
        intervals = [0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300]
        interval = 1.0
        for iv in intervals:
            if total_s / iv < 20:
                interval = iv
                break

        t = 0.0
        while t <= total_s:
            x = self._ns_to_x(int(t * 1_000_000_000))
            if 0 <= x <= width:
                minutes = int(t) // 60
                secs = int(t) % 60
                frac = t - int(t)

                if interval < 1:
                    label = f"{minutes}:{secs:02d}.{int(frac*10)}"
                else:
                    label = f"{minutes}:{secs:02d}"

                self.create_line(x, 0, x, self._header_height, fill="#555")
                self.create_text(
                    x + 2, 2, text=label, fill="#aaa",
                    anchor=tk.NW, font=("Segoe UI", 7)
                )
            t += interval
