"""Entry point for ActionRecorder Pro."""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    # 1. Set DPI awareness BEFORE any window creation
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    # 2. Setup logging
    from utils.logging_config import setup_logging
    setup_logging()

    # 3. Ensure data directories exist
    from config import DATA_DIR, SCREENSHOTS_DIR, LOG_DIR
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    # 4. Initialize database
    from storage.database import DatabaseManager
    db = DatabaseManager()
    db.initialize_schema()

    # 5. Launch GUI
    from gui.app import ActionRecorderApp
    app = ActionRecorderApp(db)
    app.run()


if __name__ == "__main__":
    main()
