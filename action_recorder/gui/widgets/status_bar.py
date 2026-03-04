"""Status bar widget for ActionRecorder Pro."""

import tkinter as tk
from tkinter import ttk


class StatusBar(ttk.Frame):
    """Bottom status bar showing recording state, region, action count, duration."""

    def __init__(self, parent):
        super().__init__(parent, relief=tk.SUNKEN)

        self._state_var = tk.StringVar(value="Ready")
        self._region_var = tk.StringVar(value="Region: Not Selected")
        self._actions_var = tk.StringVar(value="Actions: 0")
        self._duration_var = tk.StringVar(value="Duration: 0:00")

        # State label with color indicator
        self._state_frame = ttk.Frame(self)
        self._state_frame.pack(side=tk.LEFT, padx=(5, 15))
        self._state_indicator = tk.Canvas(
            self._state_frame, width=10, height=10, highlightthickness=0
        )
        self._state_indicator.pack(side=tk.LEFT, padx=(0, 5))
        self._state_dot = self._state_indicator.create_oval(1, 1, 9, 9, fill="gray")
        ttk.Label(self._state_frame, textvariable=self._state_var).pack(side=tk.LEFT)

        # Separator
        ttk.Separator(self, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)

        # Region info
        ttk.Label(self, textvariable=self._region_var).pack(side=tk.LEFT, padx=10)
        ttk.Separator(self, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)

        # Action count
        ttk.Label(self, textvariable=self._actions_var).pack(side=tk.LEFT, padx=10)
        ttk.Separator(self, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)

        # Duration
        ttk.Label(self, textvariable=self._duration_var).pack(side=tk.LEFT, padx=10)

    def set_state(self, state: str, color: str = "gray"):
        self._state_var.set(state)
        self._state_indicator.itemconfig(self._state_dot, fill=color)

    def set_region(self, text: str):
        self._region_var.set(f"Region: {text}")

    def set_action_count(self, count: int):
        self._actions_var.set(f"Actions: {count}")

    def set_duration(self, ms: int):
        seconds = ms // 1000
        minutes = seconds // 60
        secs = seconds % 60
        self._duration_var.set(f"Duration: {minutes}:{secs:02d}")
