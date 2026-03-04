"""Region selection overlay integrated with the main GUI."""

import tkinter as tk
from typing import Callable

from core.action_types import ScreenRegion
from core.region_selector import RegionSelector


def select_region(parent: tk.Tk, callback: Callable[[ScreenRegion], None]):
    """Show region selection overlay and call callback with selected region."""
    # Minimize the main window during selection
    parent.iconify()
    parent.update()

    # Small delay to let the window minimize
    parent.after(200, lambda: _do_select(parent, callback))


def _do_select(parent: tk.Tk, callback: Callable[[ScreenRegion], None]):
    def on_region_selected(region: ScreenRegion):
        parent.deiconify()
        callback(region)

    selector = RegionSelector(on_region_selected, parent=parent)
    selector.show()
