"""Spatial Awareness - 3D Factory Reconstruction CLI Entry Point."""

import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from spatial.cli import app

if __name__ == "__main__":
    app()
