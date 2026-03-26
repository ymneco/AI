"""GPU detection and CUDA availability checks."""

import subprocess
from spatial.utils.logging_config import get_logger

log = get_logger("gpu")


def check_cuda_available() -> bool:
    """Check if CUDA is available via PyTorch."""
    try:
        import torch
        available = torch.cuda.is_available()
        if available:
            log.info(
                "CUDA available: %s (%s)",
                torch.cuda.get_device_name(0),
                f"{torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB",
            )
        else:
            log.warning("CUDA not available — GPU acceleration disabled")
        return available
    except ImportError:
        log.warning("PyTorch not installed — GPU acceleration disabled")
        return False


def check_nvidia_smi() -> dict | None:
    """Query nvidia-smi for GPU info. Returns None if unavailable."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(", ")
            return {
                "name": parts[0],
                "memory_mb": int(parts[1]),
                "driver": parts[2],
            }
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None
