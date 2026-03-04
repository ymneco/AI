"""High-precision timing utilities for ActionRecorder Pro."""

import ctypes
import time

from utils.logging_config import get_logger

logger = get_logger("timing")

# Windows multimedia timer API
try:
    winmm = ctypes.windll.winmm
    _HAS_WINMM = True
except Exception:
    _HAS_WINMM = False

BUSY_WAIT_THRESHOLD_NS = 2_000_000  # 2ms


class PrecisionTimer:
    """High-resolution timer using time.perf_counter_ns().

    For waits < 2ms: uses busy-wait spin loop.
    For waits >= 2ms: sleeps for (wait - 2ms) then busy-waits remainder.
    Optionally uses timeBeginPeriod(1) to improve Windows sleep resolution.
    """

    def __init__(self, use_high_res: bool = True):
        self._use_high_res = use_high_res and _HAS_WINMM
        self._start_ns = 0
        self._active = False

    def start(self):
        if self._use_high_res:
            try:
                winmm.timeBeginPeriod(1)
            except Exception:
                pass
        self._start_ns = time.perf_counter_ns()
        self._active = True

    def elapsed_ns(self) -> int:
        return time.perf_counter_ns() - self._start_ns

    def wait_until_ns(self, target_ns: int):
        """Wait until elapsed time reaches target_ns."""
        while True:
            remaining = target_ns - self.elapsed_ns()
            if remaining <= 0:
                return
            if remaining > BUSY_WAIT_THRESHOLD_NS:
                # Sleep for most of the wait, leaving 2ms for busy-wait
                sleep_s = (remaining - BUSY_WAIT_THRESHOLD_NS) / 1_000_000_000
                time.sleep(sleep_s)
            # Busy-wait for the final portion

    def wait_ns(self, duration_ns: int):
        """Wait for a specified duration in nanoseconds."""
        target = time.perf_counter_ns() + duration_ns
        while True:
            remaining = target - time.perf_counter_ns()
            if remaining <= 0:
                return
            if remaining > BUSY_WAIT_THRESHOLD_NS:
                sleep_s = (remaining - BUSY_WAIT_THRESHOLD_NS) / 1_000_000_000
                time.sleep(sleep_s)

    def cleanup(self):
        if self._use_high_res and self._active:
            try:
                winmm.timeEndPeriod(1)
            except Exception:
                pass
            self._active = False

    def __del__(self):
        self.cleanup()
