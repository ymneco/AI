"""Treeview-based action list widget for ActionRecorder Pro."""

import tkinter as tk
from tkinter import ttk
from typing import List

from core.action_types import ActionEvent, ActionType


# Color mapping for action types
ACTION_COLORS = {
    ActionType.MOUSE_MOVE: "#4CAF50",       # green
    ActionType.MOUSE_CLICK: "#2196F3",      # blue
    ActionType.MOUSE_DOUBLE_CLICK: "#1565C0",
    ActionType.MOUSE_SCROLL: "#009688",     # teal
    ActionType.MOUSE_DRAG_START: "#FF9800", # orange
    ActionType.MOUSE_DRAG_END: "#FF9800",
    ActionType.KEY_PRESS: "#9C27B0",        # purple
    ActionType.KEY_RELEASE: "#7B1FA2",
    ActionType.KEY_COMBO: "#F44336",        # red
    ActionType.SCREENSHOT: "#607D8B",       # blue-grey
    ActionType.PAUSE_MARKER: "#FFC107",     # amber
    ActionType.RESUME_MARKER: "#FFC107",
}


class ActionListWidget(ttk.Frame):
    """Scrollable list showing recorded actions."""

    def __init__(self, parent):
        super().__init__(parent)

        # Column definitions
        columns = ("index", "type", "time", "position", "detail")
        self._tree = ttk.Treeview(
            self, columns=columns, show="headings", height=15
        )

        self._tree.heading("index", text="#")
        self._tree.heading("type", text="Type")
        self._tree.heading("time", text="Time")
        self._tree.heading("position", text="Position")
        self._tree.heading("detail", text="Detail")

        self._tree.column("index", width=50, anchor=tk.CENTER)
        self._tree.column("type", width=120)
        self._tree.column("time", width=100, anchor=tk.CENTER)
        self._tree.column("position", width=120, anchor=tk.CENTER)
        self._tree.column("detail", width=200)

        # Scrollbar
        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)

        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._auto_scroll = True

    def add_event(self, index: int, event: ActionEvent):
        """Add a single event to the list."""
        time_str = self._format_time(event.timestamp_ns)
        pos_str = ""
        if event.region_x is not None and event.region_y is not None:
            pos_str = f"({event.region_x}, {event.region_y})"

        detail = self._format_detail(event)

        self._tree.insert("", tk.END, values=(
            index, event.action_type.name, time_str, pos_str, detail
        ))

        if self._auto_scroll:
            children = self._tree.get_children()
            if children:
                self._tree.see(children[-1])

    def clear(self):
        self._tree.delete(*self._tree.get_children())

    def load_events(self, events: List[ActionEvent]):
        self.clear()
        for i, event in enumerate(events):
            self.add_event(i, event)

    def _format_time(self, timestamp_ns: int) -> str:
        ms = timestamp_ns // 1_000_000
        seconds = ms // 1000
        minutes = seconds // 60
        secs = seconds % 60
        millis = ms % 1000
        return f"{minutes}:{secs:02d}.{millis:03d}"

    def _format_detail(self, event: ActionEvent) -> str:
        if event.action_type in (ActionType.MOUSE_CLICK, ActionType.MOUSE_DOUBLE_CLICK):
            pressed = event.metadata.get("pressed", "")
            action = "down" if pressed else "up"
            return f"{event.button} {action}"

        if event.action_type == ActionType.MOUSE_SCROLL:
            return f"dx={event.scroll_dx} dy={event.scroll_dy}"

        if event.action_type in (ActionType.KEY_PRESS, ActionType.KEY_RELEASE):
            key = event.key_char or event.key or ""
            return key

        if event.action_type == ActionType.KEY_COMBO:
            mods = "+".join(event.modifiers)
            key = event.key_char or event.key or ""
            return f"{mods}+{key}" if mods else key

        if event.action_type == ActionType.PAUSE_MARKER:
            return "Paused"
        if event.action_type == ActionType.RESUME_MARKER:
            return "Resumed"

        return ""
