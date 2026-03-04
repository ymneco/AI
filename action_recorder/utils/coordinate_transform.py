"""Coordinate transformation utilities for multi-monitor and DPI support."""

from core.action_types import ScreenRegion


def remap_coordinates(
    x: int, y: int,
    source_region: ScreenRegion,
    target_region: ScreenRegion
) -> tuple:
    """Remap absolute coordinates from source region to target region.

    Handles different region sizes by scaling proportionally.
    """
    # Convert to relative (0.0 - 1.0) within source region
    if source_region.width == 0 or source_region.height == 0:
        return (target_region.left, target_region.top)

    rel_x = (x - source_region.left) / source_region.width
    rel_y = (y - source_region.top) / source_region.height

    # Clamp to 0-1
    rel_x = max(0.0, min(1.0, rel_x))
    rel_y = max(0.0, min(1.0, rel_y))

    # Map to target region
    new_x = int(target_region.left + rel_x * target_region.width)
    new_y = int(target_region.top + rel_y * target_region.height)

    return (new_x, new_y)


def adjust_for_dpi(x: int, y: int, dpi_scale: float) -> tuple:
    """Adjust coordinates for DPI scaling."""
    if dpi_scale == 1.0:
        return (x, y)
    return (int(x / dpi_scale), int(y / dpi_scale))
