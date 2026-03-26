"""
Download and install COLMAP pre-built binaries.

Usage:
    python scripts/install_colmap.py
    python scripts/install_colmap.py --version 3.11.1
"""

import os
import sys
import platform
import zipfile
import tarfile
import subprocess
import shutil
from pathlib import Path
from urllib.request import urlretrieve

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# COLMAP release info
COLMAP_VERSION = "4.0.2"
GITHUB_BASE = "https://github.com/colmap/colmap/releases/download"

# Pre-built binary URLs by platform
DOWNLOAD_URLS = {
    "Windows": {
        "cuda": f"{GITHUB_BASE}/{COLMAP_VERSION}/colmap-x64-windows-cuda.zip",
        "nocuda": f"{GITHUB_BASE}/{COLMAP_VERSION}/colmap-x64-windows-nocuda.zip",
    },
}

PROJECT_ROOT = Path(__file__).parent.parent
VENDOR_DIR = PROJECT_ROOT / "vendor"
COLMAP_DIR = VENDOR_DIR / "colmap"


def check_cuda_available() -> bool:
    """Check if CUDA toolkit is available."""
    try:
        result = subprocess.run(
            ["nvidia-smi"], capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_colmap_installed() -> str | None:
    """Check if COLMAP is already available."""
    # Check PATH
    colmap = shutil.which("colmap")
    if colmap:
        return colmap

    # Check vendor directory
    if platform.system() == "Windows":
        vendor_bin = COLMAP_DIR / "COLMAP.bat"
        if vendor_bin.exists():
            return str(vendor_bin)
    else:
        vendor_bin = COLMAP_DIR / "colmap"
        if vendor_bin.exists():
            return str(vendor_bin)

    return None


def download_with_progress(url: str, dest: str) -> str:
    """Download a file with progress display."""
    print(f"Downloading: {url}")
    print(f"       To: {dest}")

    def report(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            pct = min(downloaded / total_size * 100, 100)
            mb_down = downloaded / 1e6
            mb_total = total_size / 1e6
            print(f"\r  Progress: {pct:5.1f}% ({mb_down:.1f} / {mb_total:.1f} MB)", end="", flush=True)

    urlretrieve(url, dest, reporthook=report)
    print()  # newline after progress
    return dest


def install_windows(use_cuda: bool):
    """Install COLMAP on Windows from pre-built binaries."""
    variant = "cuda" if use_cuda else "nocuda"
    url = DOWNLOAD_URLS["Windows"][variant]
    zip_name = url.split("/")[-1]
    zip_path = VENDOR_DIR / zip_name

    VENDOR_DIR.mkdir(parents=True, exist_ok=True)

    # Download
    if not zip_path.exists():
        download_with_progress(url, str(zip_path))
    else:
        print(f"Using cached download: {zip_path}")

    # Extract
    print(f"Extracting to {COLMAP_DIR}...")
    if COLMAP_DIR.exists():
        shutil.rmtree(COLMAP_DIR)

    with zipfile.ZipFile(zip_path) as zf:
        # Find the root directory inside the zip
        top_dirs = {name.split("/")[0] for name in zf.namelist() if "/" in name}
        zf.extractall(VENDOR_DIR)

    # Rename extracted directory to 'colmap'
    for d in top_dirs:
        extracted = VENDOR_DIR / d
        if extracted.is_dir() and "COLMAP" in d.upper():
            extracted.rename(COLMAP_DIR)
            break

    # Verify
    bat_path = COLMAP_DIR / "COLMAP.bat"
    if not bat_path.exists():
        # Try to find the actual bat file
        for bat in COLMAP_DIR.rglob("COLMAP.bat"):
            bat_path = bat
            break

    if bat_path.exists():
        print(f"\nCOLMAP installed: {bat_path}")
        return str(bat_path)
    else:
        # Look for colmap.exe
        for exe in COLMAP_DIR.rglob("colmap.exe"):
            print(f"\nCOLMAP installed: {exe}")
            return str(exe)

    raise FileNotFoundError("COLMAP binary not found after extraction")


def install_linux():
    """Install COLMAP on Linux."""
    # Try apt first
    print("Attempting to install COLMAP via apt...")
    result = subprocess.run(
        ["which", "apt-get"], capture_output=True,
    )
    if result.returncode == 0:
        print("Run: sudo apt-get install -y colmap")
        print("Or build from source: https://colmap.github.io/install.html")
    else:
        print("Install COLMAP from source: https://colmap.github.io/install.html")
        print("Or use conda: conda install -c conda-forge colmap")


def update_env_file(colmap_path: str):
    """Write COLMAP path to .env file."""
    env_path = PROJECT_ROOT / ".env"
    lines = []
    if env_path.exists():
        lines = env_path.read_text().splitlines()

    # Remove existing COLMAP_PATH
    lines = [l for l in lines if not l.startswith("COLMAP_PATH=")]
    lines.append(f"COLMAP_PATH={colmap_path}")

    env_path.write_text("\n".join(lines) + "\n")
    print(f"Updated .env: COLMAP_PATH={colmap_path}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Install COLMAP")
    parser.add_argument("--version", default=COLMAP_VERSION)
    parser.add_argument("--no-cuda", action="store_true", help="Install CPU-only version")
    args = parser.parse_args()

    # Check if already installed
    existing = check_colmap_installed()
    if existing:
        print(f"COLMAP already available: {existing}")
        verify = subprocess.run(
            [existing, "help"], capture_output=True, text=True, timeout=10,
        )
        if verify.returncode in (0, 1):
            print("COLMAP is working correctly.")
            update_env_file(existing)
            return
        else:
            print("Existing COLMAP seems broken, reinstalling...")

    system = platform.system()
    use_cuda = not args.no_cuda and check_cuda_available()
    print(f"Platform: {system}, CUDA: {'yes' if use_cuda else 'no'}")

    if system == "Windows":
        colmap_path = install_windows(use_cuda)
        update_env_file(colmap_path)
    elif system == "Linux":
        install_linux()
    else:
        print(f"Unsupported platform: {system}")
        print("Please install COLMAP manually: https://colmap.github.io/install.html")
        sys.exit(1)

    print("\nDone! Verify with: python main.py info")


if __name__ == "__main__":
    main()
