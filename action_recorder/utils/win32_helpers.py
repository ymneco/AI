"""Windows API helpers for DPI awareness and monitor enumeration."""

import ctypes
import ctypes.wintypes
from dataclasses import dataclass
from typing import List

from utils.logging_config import get_logger

logger = get_logger("win32_helpers")


@dataclass
class MonitorInfo:
    index: int
    left: int
    top: int
    width: int
    height: int
    is_primary: bool
    dpi_x: int = 96
    dpi_y: int = 96


def set_dpi_awareness():
    """Set per-monitor DPI awareness V2. Must be called before any window creation."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        logger.info("DPI awareness set to Per-Monitor V2")
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            logger.info("DPI awareness set via SetProcessDPIAware (fallback)")
        except Exception as e:
            logger.warning(f"Failed to set DPI awareness: {e}")


def get_monitors() -> List[MonitorInfo]:
    """Enumerate all monitors and their geometry."""
    monitors = []

    def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
        rect = lprcMonitor.contents
        info = MonitorInfo(
            index=len(monitors),
            left=rect.left,
            top=rect.top,
            width=rect.right - rect.left,
            height=rect.bottom - rect.top,
            is_primary=(rect.left == 0 and rect.top == 0)
        )
        # Get DPI for this monitor
        try:
            dpi_x = ctypes.c_uint()
            dpi_y = ctypes.c_uint()
            ctypes.windll.shcore.GetDpiForMonitor(
                hMonitor, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y)
            )
            info.dpi_x = dpi_x.value
            info.dpi_y = dpi_y.value
        except Exception:
            pass
        monitors.append(info)
        return True

    MONITORENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_int,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.wintypes.RECT),
        ctypes.c_double
    )
    ctypes.windll.user32.EnumDisplayMonitors(
        None, None, MONITORENUMPROC(callback), 0
    )
    return monitors


def get_virtual_screen_rect() -> tuple:
    """Get the bounding rectangle of the virtual screen (all monitors)."""
    SM_XVIRTUALSCREEN = 76
    SM_YVIRTUALSCREEN = 77
    SM_CXVIRTUALSCREEN = 78
    SM_CYVIRTUALSCREEN = 79

    left = ctypes.windll.user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    top = ctypes.windll.user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    width = ctypes.windll.user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    height = ctypes.windll.user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    return (left, top, width, height)


def get_cursor_pos() -> tuple:
    """Get current cursor position in physical pixels."""
    point = ctypes.wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return (point.x, point.y)
