"""Screenshot capture utilities for ActionRecorder Pro."""

import os
import time

from PIL import Image, ImageGrab

from core.action_types import ScreenRegion
from utils.logging_config import get_logger

logger = get_logger("screen_capture")


class ScreenCapture:
    """Captures screenshots of a ScreenRegion using Pillow."""

    def capture_region(self, region: ScreenRegion) -> Image.Image:
        bbox = (
            region.left,
            region.top,
            region.left + region.width,
            region.top + region.height,
        )
        try:
            return ImageGrab.grab(bbox=bbox, all_screens=True)
        except Exception as e:
            logger.error(f"Screenshot capture failed: {e}")
            # Return a small blank image as fallback
            return Image.new("RGB", (region.width, region.height), (0, 0, 0))

    def capture_full_screen(self) -> Image.Image:
        return ImageGrab.grab(all_screens=True)

    def save_screenshot(self, image: Image.Image, session_dir: str,
                        prefix: str = "screenshot") -> str:
        os.makedirs(session_dir, exist_ok=True)
        timestamp = int(time.time() * 1000)
        filename = f"{prefix}_{timestamp}.png"
        filepath = os.path.join(session_dir, filename)
        image.save(filepath, "PNG", optimize=True)
        return filepath

    def compare_regions(self, img1: Image.Image, img2: Image.Image) -> float:
        """Compare two images and return similarity ratio (0.0 to 1.0).

        Uses simple pixel-level comparison for speed.
        """
        if img1.size != img2.size:
            img2 = img2.resize(img1.size)

        pixels1 = list(img1.getdata())
        pixels2 = list(img2.getdata())

        if not pixels1:
            return 1.0

        matching = sum(1 for p1, p2 in zip(pixels1, pixels2) if p1 == p2)
        return matching / len(pixels1)
