"""Screen region selection via transparent overlay."""

import tkinter as tk
from typing import Callable, Optional

from core.action_types import ScreenRegion
from utils.win32_helpers import get_virtual_screen_rect, get_monitors
from utils.logging_config import get_logger

logger = get_logger("region_selector")


class RegionSelector:
    """Creates a semi-transparent fullscreen overlay for region selection.

    User drags a rectangle to define the recording region.
    """

    def __init__(self, callback: Callable[[ScreenRegion], None],
                 parent: Optional[tk.Tk] = None):
        self._callback = callback
        self._parent = parent
        self._start_x = 0
        self._start_y = 0
        self._rect_id = None
        self._label_id = None
        self._overlay = None

    def show(self):
        """Show the region selection overlay."""
        vx, vy, vw, vh = get_virtual_screen_rect()

        if self._parent:
            self._overlay = tk.Toplevel(self._parent)
        else:
            self._overlay = tk.Tk()

        self._overlay.attributes("-fullscreen", True)
        self._overlay.attributes("-topmost", True)
        self._overlay.attributes("-alpha", 0.3)
        self._overlay.configure(bg="black")

        # Position to cover virtual screen
        self._overlay.geometry(f"{vw}x{vh}+{vx}+{vy}")

        self._canvas = tk.Canvas(
            self._overlay, bg="black",
            width=vw, height=vh,
            highlightthickness=0, cursor="crosshair"
        )
        self._canvas.pack(fill=tk.BOTH, expand=True)

        # Instructions label
        self._canvas.create_text(
            vw // 2, 30,
            text="Drag to select recording region  |  ESC to cancel",
            fill="white", font=("Segoe UI", 14)
        )

        self._canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self._canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self._overlay.bind("<Escape>", self._on_cancel)

        # Store virtual screen offset for coordinate correction
        self._vx = vx
        self._vy = vy

        if not self._parent:
            self._overlay.mainloop()

    def _on_mouse_down(self, event):
        self._start_x = event.x
        self._start_y = event.y
        if self._rect_id:
            self._canvas.delete(self._rect_id)
        if self._label_id:
            self._canvas.delete(self._label_id)

    def _on_mouse_drag(self, event):
        if self._rect_id:
            self._canvas.delete(self._rect_id)
        if self._label_id:
            self._canvas.delete(self._label_id)

        x1, y1 = self._start_x, self._start_y
        x2, y2 = event.x, event.y

        self._rect_id = self._canvas.create_rectangle(
            x1, y1, x2, y2,
            outline="#00ff00", width=2, dash=(5, 3)
        )

        w = abs(x2 - x1)
        h = abs(y2 - y1)
        self._label_id = self._canvas.create_text(
            (x1 + x2) // 2, min(y1, y2) - 15,
            text=f"{w} x {h}",
            fill="#00ff00", font=("Segoe UI", 11)
        )

    def _on_mouse_up(self, event):
        x1 = min(self._start_x, event.x)
        y1 = min(self._start_y, event.y)
        x2 = max(self._start_x, event.x)
        y2 = max(self._start_y, event.y)

        w = x2 - x1
        h = y2 - y1

        if w < 10 or h < 10:
            logger.warning("Selected region too small, ignoring")
            return

        # Adjust for virtual screen offset
        abs_left = x1 + self._vx
        abs_top = y1 + self._vy

        # Determine which monitor contains the center of the selection
        center_x = abs_left + w // 2
        center_y = abs_top + h // 2
        monitor_index = 0
        dpi_scale = 1.0

        monitors = get_monitors()
        for mon in monitors:
            if (mon.left <= center_x < mon.left + mon.width and
                    mon.top <= center_y < mon.top + mon.height):
                monitor_index = mon.index
                dpi_scale = mon.dpi_x / 96.0
                break

        region = ScreenRegion(
            left=abs_left,
            top=abs_top,
            width=w,
            height=h,
            monitor_index=monitor_index,
            dpi_scale=dpi_scale,
        )

        logger.info(f"Region selected: {region}")
        self._close()
        self._callback(region)

    def _on_cancel(self, event=None):
        logger.info("Region selection cancelled")
        self._close()

    def _close(self):
        if self._overlay:
            self._overlay.destroy()
            self._overlay = None
