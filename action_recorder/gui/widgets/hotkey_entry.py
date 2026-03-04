"""Custom widget for capturing hotkey combinations."""

import tkinter as tk
from tkinter import ttk


class HotkeyEntry(ttk.Frame):
    """Widget that captures keyboard shortcuts when focused."""

    def __init__(self, parent, initial_value: str = "",
                 on_change=None):
        super().__init__(parent)
        self._on_change = on_change
        self._value = initial_value

        self._var = tk.StringVar(value=initial_value)
        self._entry = ttk.Entry(self, textvariable=self._var,
                                 width=15, state="readonly",
                                 justify=tk.CENTER)
        self._entry.pack(side=tk.LEFT, padx=(0, 5))

        self._capture_btn = ttk.Button(self, text="Set",
                                        command=self._start_capture)
        self._capture_btn.pack(side=tk.LEFT)

        self._capturing = False

    def _start_capture(self):
        """Enter capture mode - next key press becomes the hotkey."""
        self._capturing = True
        self._var.set("Press a key...")
        self._capture_btn.config(text="Cancel")
        self._entry.focus_set()

        # Bind key events
        self._entry.bind("<KeyPress>", self._on_key_press)
        self._capture_btn.config(command=self._cancel_capture)

    def _on_key_press(self, event):
        if not self._capturing:
            return

        # Build key name
        parts = []
        if event.state & 0x4:
            parts.append("Ctrl")
        if event.state & 0x1:
            parts.append("Shift")
        if event.state & 0x8:
            parts.append("Alt")

        key_name = event.keysym
        if key_name not in ("Control_L", "Control_R", "Shift_L", "Shift_R",
                            "Alt_L", "Alt_R"):
            parts.append(key_name)
            self._value = "+".join(parts)
            self._var.set(self._value)
            self._stop_capture()

            if self._on_change:
                self._on_change(self._value)

    def _cancel_capture(self):
        self._var.set(self._value)
        self._stop_capture()

    def _stop_capture(self):
        self._capturing = False
        self._capture_btn.config(text="Set", command=self._start_capture)
        self._entry.unbind("<KeyPress>")

    def get(self) -> str:
        return self._value

    def set(self, value: str):
        self._value = value
        self._var.set(value)
