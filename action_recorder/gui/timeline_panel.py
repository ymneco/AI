"""Timeline panel for viewing and scrubbing recorded actions."""

import tkinter as tk
from tkinter import ttk
from typing import List, Optional

from core.action_types import ActionEvent, ActionType, RecordingSession
from gui.widgets.timeline_canvas import TimelineCanvas
from storage.database import DatabaseManager
from storage.models import SessionDAO, ActionDAO
from utils.logging_config import get_logger

logger = get_logger("timeline_panel")


class TimelinePanel(ttk.Frame):
    """Tab panel with timeline visualization and action detail view."""

    def __init__(self, parent, db: DatabaseManager):
        super().__init__(parent)
        self._db = db
        self._session_dao = SessionDAO(db)
        self._action_dao = ActionDAO(db)
        self._events: List[ActionEvent] = []
        self._current_event_index: int = -1

        self._build_ui()

    def _build_ui(self):
        # Top controls
        control_frame = ttk.Frame(self)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(control_frame, text="Session:").pack(side=tk.LEFT, padx=(0, 5))
        self._session_var = tk.StringVar()
        self._session_combo = ttk.Combobox(
            control_frame, textvariable=self._session_var,
            state="readonly", width=40
        )
        self._session_combo.pack(side=tk.LEFT, padx=(0, 10))
        self._session_combo.bind("<<ComboboxSelected>>", self._on_session_selected)

        ttk.Button(control_frame, text="Refresh", command=self._refresh_sessions).pack(
            side=tk.LEFT, padx=5
        )

        # Zoom controls
        ttk.Label(control_frame, text="Zoom:").pack(side=tk.RIGHT, padx=(10, 5))
        ttk.Button(control_frame, text="-", width=3,
                   command=lambda: self._timeline.set_zoom(
                       self._timeline._zoom / 1.5
                   )).pack(side=tk.RIGHT)
        ttk.Button(control_frame, text="+", width=3,
                   command=lambda: self._timeline.set_zoom(
                       self._timeline._zoom * 1.5
                   )).pack(side=tk.RIGHT)

        # Timeline canvas
        timeline_frame = ttk.LabelFrame(self, text="Timeline")
        timeline_frame.pack(fill=tk.X, padx=5, pady=5)

        self._timeline = TimelineCanvas(
            timeline_frame, height=80,
            on_cursor_move=self._on_cursor_move
        )
        self._timeline.pack(fill=tk.X, padx=5, pady=5)

        # Legend
        legend_frame = ttk.Frame(timeline_frame)
        legend_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        legends = [
            ("Mouse Click", "#2196F3"),
            ("Mouse Move", "#4CAF50"),
            ("Key Press", "#9C27B0"),
            ("Key Combo", "#F44336"),
            ("Scroll", "#009688"),
            ("Drag", "#FF9800"),
        ]
        for name, color in legends:
            c = tk.Canvas(legend_frame, width=12, height=12, highlightthickness=0)
            c.create_rectangle(0, 0, 12, 12, fill=color, outline="")
            c.pack(side=tk.LEFT, padx=(10, 2))
            ttk.Label(legend_frame, text=name, font=("Segoe UI", 8)).pack(
                side=tk.LEFT, padx=(0, 5)
            )

        # Action detail
        detail_frame = ttk.LabelFrame(self, text="Action Detail")
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self._detail_text = tk.Text(
            detail_frame, height=8, wrap=tk.WORD,
            font=("Consolas", 10), state=tk.DISABLED,
            bg="#1e1e1e", fg="#d4d4d4"
        )
        self._detail_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Session data for combobox mapping
        self._session_list: List[RecordingSession] = []
        self._refresh_sessions()

    def _refresh_sessions(self):
        """Reload session list for the combobox."""
        self._session_list = self._session_dao.get_all(limit=100)
        names = [
            f"{s.name} ({s.action_count} actions, {s.duration_ms // 1000}s)"
            for s in self._session_list
        ]
        self._session_combo["values"] = names

    def load_session(self, session: RecordingSession):
        """Load a specific session into the timeline."""
        if not session.session_id:
            return

        self._events = self._action_dao.get_by_session(session.session_id)
        self._timeline.set_events(self._events)
        self._current_event_index = -1

        logger.info(f"Timeline loaded: session={session.session_id}, "
                     f"{len(self._events)} events")

    def _on_session_selected(self, event=None):
        index = self._session_combo.current()
        if 0 <= index < len(self._session_list):
            self.load_session(self._session_list[index])

    def _on_cursor_move(self, timestamp_ns: int):
        """Find the nearest event to the cursor position and show details."""
        if not self._events:
            return

        # Binary search for nearest event
        nearest_idx = 0
        min_diff = abs(self._events[0].timestamp_ns - timestamp_ns)

        for i, e in enumerate(self._events):
            diff = abs(e.timestamp_ns - timestamp_ns)
            if diff < min_diff:
                min_diff = diff
                nearest_idx = i

        if nearest_idx != self._current_event_index:
            self._current_event_index = nearest_idx
            self._show_event_detail(self._events[nearest_idx], nearest_idx)

    def _show_event_detail(self, event: ActionEvent, index: int):
        """Display detailed info about the selected event."""
        ms = event.timestamp_ns // 1_000_000
        seconds = ms // 1000
        minutes = seconds // 60
        secs = seconds % 60
        millis = ms % 1000

        lines = [
            f"Event #{index + 1} of {len(self._events)}",
            f"{'=' * 40}",
            f"Type:       {event.action_type.name}",
            f"Time:       {minutes}:{secs:02d}.{millis:03d}",
        ]

        if event.x is not None and event.y is not None:
            lines.append(f"Position:   ({event.x}, {event.y}) absolute")
        if event.region_x is not None and event.region_y is not None:
            lines.append(f"Region Pos: ({event.region_x}, {event.region_y}) relative")

        if event.button:
            lines.append(f"Button:     {event.button}")
        if event.key:
            lines.append(f"Key:        {event.key}")
        if event.key_char:
            lines.append(f"Character:  '{event.key_char}'")
        if event.modifiers:
            lines.append(f"Modifiers:  {', '.join(event.modifiers)}")
        if event.scroll_dx or event.scroll_dy:
            lines.append(f"Scroll:     dx={event.scroll_dx}, dy={event.scroll_dy}")
        if event.metadata:
            for k, v in event.metadata.items():
                lines.append(f"Meta [{k}]:  {v}")

        self._detail_text.config(state=tk.NORMAL)
        self._detail_text.delete("1.0", tk.END)
        self._detail_text.insert("1.0", "\n".join(lines))
        self._detail_text.config(state=tk.DISABLED)
