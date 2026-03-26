"""Windows/Linux platform compatibility utilities."""

import os
import platform
import shutil


def is_windows() -> bool:
    return platform.system() == "Windows"


def find_binary(name: str, env_var: str | None = None) -> str | None:
    """Find an external binary by name, checking env var first, then PATH."""
    if env_var:
        path = os.environ.get(env_var)
        if path:
            # Normalize and check
            path = os.path.normpath(path)
            if os.path.isfile(path):
                return path

    found = shutil.which(name)
    if found:
        return found

    # Check vendor directory relative to project root
    # spatial/utils/platform_compat.py -> spatial/utils -> spatial -> project_root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if is_windows():
        vendor_candidates = [
            os.path.join(project_root, "vendor", name, "COLMAP.bat"),
            os.path.join(project_root, "vendor", name, f"{name}.exe"),
            os.path.join(project_root, "vendor", name, "bin", f"{name}.exe"),
            os.path.join(os.environ.get("PROGRAMFILES", ""), "COLMAP", f"{name}.bat"),
        ]
    else:
        vendor_candidates = [
            os.path.join(project_root, "vendor", name, name),
            os.path.join(project_root, "vendor", name, "bin", name),
        ]

    for p in vendor_candidates:
        p = os.path.normpath(p)
        if os.path.isfile(p):
            return p

    return None


def normalize_path(path: str) -> str:
    """Normalize path separators for the current platform."""
    return os.path.normpath(path)
